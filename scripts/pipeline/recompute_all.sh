#!/usr/bin/env bash
# Submit LEMON + Dortmund normative recomputes on AWS Batch, wait for both
# to finish, and download the merged outputs + per-subject checkpoints to
# local directories ready for the validation scripts.
#
# Usage:
#   scripts/pipeline/recompute_all.sh [OUTPUT_DIR]
#
# Environment (override before the call):
#   CHANNELS        37 (default) | 19
#   DATASETS        "lemon dortmund" (default). Space-separated subset.
#   EXTRA_FLAGS     "--source --ba-connectivity --dk-connectivity --save-psd" (default)
#   SLICES_LEMON    31 (default)
#   SLICES_DORTMUND 32 (default — bumps up for 608-subject scale)
#   AWS_PROFILE     picked up from env or aws-config.yaml
#
# Assumes you've already run terraform apply and populated aws-config.yaml.
# Assumes a clone of the repo with .venv/ installed (cloud_recompute needs
# to enumerate subjects locally for slice manifests).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

OUT_DIR="${1:-./results}"
CHANNELS="${CHANNELS:-37}"
DATASETS="${DATASETS:-lemon dortmund}"
EXTRA_FLAGS="${EXTRA_FLAGS:---source --ba-connectivity --dk-connectivity --save-psd}"
SLICES_LEMON="${SLICES_LEMON:-31}"
SLICES_DORTMUND="${SLICES_DORTMUND:-32}"

if [[ ! -x .venv/bin/python ]]; then
    echo "ERROR: .venv/bin/python not found. Run 'python3.10 -m venv .venv && .venv/bin/pip install -e \".[datasets,aws,dev]\"' first." >&2
    exit 1
fi

if [[ ! -f aws-config.yaml ]]; then
    echo "ERROR: aws-config.yaml missing. Copy from aws-config.example.yaml and fill in." >&2
    exit 1
fi

mkdir -p "$OUT_DIR"

# Pick data dir for each dataset. Override by exporting LEMON_DATA_DIR / DORTMUND_DATA_DIR.
data_dir_for() {
    local ds="$1"
    case "$ds" in
        lemon)    echo "${LEMON_DATA_DIR:-$HOME/Data/EEG/LEMON/EEG_Raw_BIDS_ID}" ;;
        dortmund) echo "${DORTMUND_DATA_DIR:-$HOME/Data/EEG/Dortmund}" ;;
        *)        echo "$HOME/Data/EEG/$(echo "$ds" | tr '[:lower:]' '[:upper:]')" ;;
    esac
}

slices_for() {
    local ds="$1"
    case "$ds" in
        lemon)    echo "$SLICES_LEMON" ;;
        dortmund) echo "$SLICES_DORTMUND" ;;
        *)        echo "32" ;;
    esac
}

# We submit and poll datasets sequentially — each recompute uses ~248 vCPU
# of our 256 spot quota, so parallel submission would just queue the second.
for ds in $DATASETS; do
    data_dir="$(data_dir_for "$ds")"
    slices="$(slices_for "$ds")"
    echo
    echo "================================================================"
    echo "Submitting $ds recompute (slices=$slices, data=$data_dir)"
    echo "================================================================"

    # --follow blocks until the merge job reaches a terminal state.
    .venv/bin/python scripts/cloud_recompute.py submit \
        --dataset "$ds" --channels "$CHANNELS" --condition both \
        --slices "$slices" \
        --data-dir "$data_dir" \
        $EXTRA_FLAGS \
        --follow

    # Pull the most recent run_id for this dataset (cloud_recompute doesn't
    # echo it in --follow mode's final line, so list and pick the newest).
    run_id=$(.venv/bin/python scripts/cloud_recompute.py list --limit 50 2>/dev/null \
        | awk -v ds="$ds" '$0 ~ "^"ds"-" {print $1; exit}')
    if [[ -z "$run_id" ]]; then
        echo "ERROR: could not identify run_id for $ds after submission." >&2
        exit 1
    fi
    echo "run_id: $run_id"

    # Download both the merged outputs AND the per-subject checkpoints.
    # The validators (validate_internal.py, validate_cross_dataset.py,
    # validate_literature.py) all read subjects/ directly.
    local_out="$OUT_DIR/$ds"
    mkdir -p "$local_out/subjects" "$local_out/out"

    echo "Downloading $run_id → $local_out/"
    bucket=$(awk '/^  bucket:/ {print $2}' aws-config.yaml)
    region=$(awk '/^  region:/ {print $2}' aws-config.yaml)
    profile=$(awk '/^  profile:/ {print $2}' aws-config.yaml)

    aws s3 sync "s3://$bucket/runs/$run_id/out/"      "$local_out/out/" \
        --profile "$profile" --region "$region" --no-progress
    aws s3 sync "s3://$bucket/runs/$run_id/subjects/" "$local_out/subjects/" \
        --profile "$profile" --region "$region" --no-progress

    echo "$run_id" > "$local_out/.run_id"
    echo "$ds: done — $(ls -1 "$local_out/subjects" | wc -l) subject checkpoints"
done

echo
echo "All recomputes complete. Outputs in $OUT_DIR/"
echo "Next: scripts/pipeline/validate_all.sh $OUT_DIR"
