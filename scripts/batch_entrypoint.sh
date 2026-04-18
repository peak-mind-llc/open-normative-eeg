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
        echo "--- syncing raw data mirror from ${DATA_MIRROR} ---"
        mkdir -p "${CHECKPOINT_LOCAL}/data"
        aws s3 sync "${DATA_MIRROR}" "${CHECKPOINT_LOCAL}/data/" --no-progress
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
