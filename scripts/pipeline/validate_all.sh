#!/usr/bin/env bash
# Run the full validation suite against pre-downloaded recompute results.
#
# Expects the layout produced by scripts/pipeline/recompute_all.sh:
#
#   RESULTS_DIR/
#     lemon/
#       subjects/*.json       # per-subject checkpoints
#       out/norms.json        # merged norm
#     dortmund/
#       subjects/*.json
#       out/norms.json
#
# Usage:
#   scripts/pipeline/validate_all.sh [RESULTS_DIR]
#
# Runs, in order:
#   1. validate_internal.py   (split-half reliability + physiological sanity)
#      on each dataset independently.
#   2. validate_literature.py (directional checks against published EEG findings)
#      on each dataset.
#   3. validate_cross_dataset.py (LEMON vs Dortmund agreement)
#      once across the two.
#   4. validate_source.py (source-level plausibility checks)
#      on each dataset.
#   5. generate_validation_report.py aggregates all four into a combined
#      markdown report per dataset, plus a combined two-dataset report.
#
# All intermediate JSONs end up under RESULTS_DIR/validation/.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

RESULTS_DIR="${1:-./results}"
VAL_DIR="$RESULTS_DIR/validation"
mkdir -p "$VAL_DIR"

PY=".venv/bin/python"
[[ -x "$PY" ]] || { echo "ERROR: .venv/bin/python not found. Activate or install venv first." >&2; exit 1; }

DATASETS_PRESENT=()
for ds in lemon dortmund; do
    if [[ -d "$RESULTS_DIR/$ds/subjects" ]]; then
        DATASETS_PRESENT+=("$ds")
    fi
done

if (( ${#DATASETS_PRESENT[@]} == 0 )); then
    echo "ERROR: no dataset subdirs with subjects/ found under $RESULTS_DIR" >&2
    echo "Run scripts/pipeline/recompute_all.sh first." >&2
    exit 1
fi

echo "Datasets found: ${DATASETS_PRESENT[*]}"
echo "Validation outputs → $VAL_DIR/"

# ─── Per-dataset validators ───────────────────────────────────────────────
for ds in "${DATASETS_PRESENT[@]}"; do
    subj="$RESULTS_DIR/$ds/subjects"

    echo
    echo "=== $ds: internal (split-half, EO/EC, IAF) ==="
    $PY scripts/validate_internal.py "$subj" \
        --output "$VAL_DIR/${ds}_internal.json"

    echo
    echo "=== $ds: literature (published EEG findings) ==="
    $PY scripts/validate_literature.py "$subj" \
        --output "$VAL_DIR/${ds}_literature.json"

    # validate_source.py expects the merged output dir, not subjects/
    merged="$RESULTS_DIR/$ds/out"
    if [[ -f "$merged/norms.json" ]]; then
        echo
        echo "=== $ds: source plausibility ==="
        $PY scripts/validate_source.py "$merged" \
            > "$VAL_DIR/${ds}_source.log" 2>&1 || {
            echo "  (validate_source.py exited non-zero; see $VAL_DIR/${ds}_source.log)"
        }
    fi
done

# ─── Cross-dataset (needs both) ───────────────────────────────────────────
if (( ${#DATASETS_PRESENT[@]} >= 2 )); then
    a="${DATASETS_PRESENT[0]}"
    b="${DATASETS_PRESENT[1]}"
    echo
    echo "=== cross-dataset: $a vs $b ==="
    $PY scripts/validate_cross_dataset.py \
        --dir-a "$RESULTS_DIR/$a/subjects" --label-a "$(echo "$a" | tr '[:lower:]' '[:upper:]')" \
        --dir-b "$RESULTS_DIR/$b/subjects" --label-b "$(echo "$b" | tr '[:lower:]' '[:upper:]')" \
        --output "$VAL_DIR/cross_dataset.json"
fi

# ─── Per-dataset report ──────────────────────────────────────────────────
for ds in "${DATASETS_PRESENT[@]}"; do
    echo
    echo "=== $ds: generating markdown report ==="
    cross_flag=()
    [[ -f "$VAL_DIR/cross_dataset.json" ]] && cross_flag=(--cross-dataset "$VAL_DIR/cross_dataset.json")
    $PY scripts/generate_validation_report.py \
        --internal   "$VAL_DIR/${ds}_internal.json" \
        --literature "$VAL_DIR/${ds}_literature.json" \
        "${cross_flag[@]}" \
        --label "$(echo "$ds" | tr '[:lower:]' '[:upper:]')" \
        --output "$VAL_DIR/${ds}_report.md"
done

echo
echo "Validation complete. Reports:"
for f in "$VAL_DIR"/*_report.md; do
    [[ -f "$f" ]] && echo "  $f"
done
echo "Raw JSONs: $VAL_DIR/"
