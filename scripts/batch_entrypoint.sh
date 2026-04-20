#!/usr/bin/env bash
# Container entrypoint for AWS Batch jobs. Two modes, selected by MODE env:
#
#   MODE=array (default) — one subject-range slice per AWS_BATCH_JOB_ARRAY_INDEX.
#   MODE=merge           — read all runs/$RUN_ID/subjects/*.json from S3 and
#                          aggregate into runs/$RUN_ID/out/.
#
# Docker CMD overrides (containerOverrides.command in Batch) cannot replace
# the image's ENTRYPOINT, so both job definitions run this same script and
# branch on MODE. cloud_recompute.py sets MODE=array|merge per job.
#
# Required env (both modes):
#   BUCKET           S3 bucket
#   RUN_ID           run identifier, becomes runs/<RUN_ID>/ prefix
#
# MODE=array additional required:
#   DATASET, CHANNELS, CONDITION, PER_SLICE, WORKERS, AWS_BATCH_JOB_ARRAY_INDEX
#
# MODE=array optional:
#   SOURCE_FLAGS     space-separated extra flags (e.g. "--source --ba-connectivity")
#   DATA_MIRROR      s3:// URI to sync raw data from
#   CHECKPOINT_LOCAL local work dir (default /work)
#   EXTRA_ARGS       extra flags passed through to build_norms.py

set -euo pipefail

MODE="${MODE:-array}"
: "${BUCKET:?BUCKET is required}"
: "${RUN_ID:?RUN_ID is required}"

CHECKPOINT_LOCAL="${CHECKPOINT_LOCAL:-/work}"
RUN_PREFIX="s3://${BUCKET}/runs/${RUN_ID}"

echo "=== batch_entrypoint ==="
echo "  mode          : ${MODE}"
echo "  run prefix    : ${RUN_PREFIX}"
echo "  BLAS threads  : OMP=${OMP_NUM_THREADS:-?} OPENBLAS=${OPENBLAS_NUM_THREADS:-?} MKL=${MKL_NUM_THREADS:-?}"

case "${MODE}" in

  array)
    : "${DATASET:?DATASET is required}"
    : "${CHANNELS:?CHANNELS is required}"
    : "${CONDITION:?CONDITION is required}"
    : "${PER_SLICE:?PER_SLICE is required}"
    : "${WORKERS:?WORKERS is required}"
    : "${AWS_BATCH_JOB_ARRAY_INDEX:?AWS_BATCH_JOB_ARRAY_INDEX must be set by Batch}"

    SOURCE_FLAGS="${SOURCE_FLAGS:-}"
    EXTRA_ARGS="${EXTRA_ARGS:-}"

    SLICE="$AWS_BATCH_JOB_ARRAY_INDEX"
    START=$((SLICE * PER_SLICE))
    END=$(((SLICE + 1) * PER_SLICE))

    echo "  slice         : ${SLICE}  (range ${START}:${END})"
    echo "  dataset       : ${DATASET}"
    echo "  channels      : ${CHANNELS}"
    echo "  condition     : ${CONDITION}"
    echo "  workers       : ${WORKERS}"
    echo "  source flags  : ${SOURCE_FLAGS:-<none>}"

    mkdir -p "${CHECKPOINT_LOCAL}/subjects" "${CHECKPOINT_LOCAL}/psd_checkpoints"

    echo "--- syncing prior checkpoints ---"
    aws s3 sync "${RUN_PREFIX}/subjects/"        "${CHECKPOINT_LOCAL}/subjects/"        --no-progress || true
    aws s3 sync "${RUN_PREFIX}/psd_checkpoints/" "${CHECKPOINT_LOCAL}/psd_checkpoints/" --no-progress || true

    if [[ -n "${DATA_MIRROR:-}" ]]; then
        mkdir -p "${CHECKPOINT_LOCAL}/data"
        # Try the per-slice manifest first: each container then pulls only its
        # own subjects (~per_slice/total of the mirror) instead of all 63 GB.
        # Fall back to full sync if the manifest is missing for any reason.
        MANIFEST="/tmp/slice_subjects.txt"
        if aws s3 cp "${RUN_PREFIX}/slices/${SLICE}.txt" "${MANIFEST}" --no-progress 2>/dev/null; then
            N_SUBJ=$(wc -l < "${MANIFEST}")
            echo "--- selective sync: ${N_SUBJ} subjects from ${DATA_MIRROR} ---"
            # Pass 1: metadata at the mirror root (CSVs, TSVs, JSONs). Small.
            aws s3 sync "${DATA_MIRROR}" "${CHECKPOINT_LOCAL}/data/" \
                --exclude "sub-*/*" --exclude "derivatives/*" --no-progress || true
            # Pass 2: only the subjects this slice needs. Build an --include list.
            INCLUDES=()
            while IFS= read -r sid; do
                [[ -z "$sid" ]] && continue
                INCLUDES+=("--include" "${sid}/*")
            done < "${MANIFEST}"
            aws s3 sync "${DATA_MIRROR}" "${CHECKPOINT_LOCAL}/data/" \
                --exclude "*" "${INCLUDES[@]}" --no-progress
        else
            echo "--- no slice manifest; full sync from ${DATA_MIRROR} ---"
            aws s3 sync "${DATA_MIRROR}" "${CHECKPOINT_LOCAL}/data/" --no-progress
        fi
        DATA_DIR="${CHECKPOINT_LOCAL}/data"
    else
        DATA_DIR="${CHECKPOINT_LOCAL}/data"
        mkdir -p "${DATA_DIR}"
    fi

    echo "--- running build_norms ---"
    # shellcheck disable=SC2086
    python /app/scripts/build_norms.py "${DATA_DIR}" \
        --dataset "${DATASET}" \
        --channels "${CHANNELS}" \
        --condition "${CONDITION}" \
        --subject-range "${START}:${END}" \
        --output "${CHECKPOINT_LOCAL}" \
        --checkpoint-sync "${RUN_PREFIX}/" \
        --jobs "${WORKERS}" \
        ${SOURCE_FLAGS} \
        ${EXTRA_ARGS}
    ;;

  merge)
    mkdir -p "${CHECKPOINT_LOCAL}/subjects" "${CHECKPOINT_LOCAL}/out"

    echo "--- syncing per-subject checkpoints ---"
    aws s3 sync "${RUN_PREFIX}/subjects/" "${CHECKPOINT_LOCAL}/subjects/" --no-progress

    echo "--- running build_norms.py --merge ---"
    python /app/scripts/build_norms.py --merge \
        --merge-dir "${CHECKPOINT_LOCAL}/subjects" \
        --output "${CHECKPOINT_LOCAL}/out"

    echo "--- uploading aggregated outputs ---"
    aws s3 sync "${CHECKPOINT_LOCAL}/out/" "${RUN_PREFIX}/out/" --no-progress
    ;;

  *)
    echo "Unknown MODE=${MODE}. Set MODE=array or MODE=merge." >&2
    exit 1
    ;;
esac

echo "=== batch_entrypoint done ==="
