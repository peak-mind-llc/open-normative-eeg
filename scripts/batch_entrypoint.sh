#!/usr/bin/env bash
# Container entrypoint for AWS Batch array jobs.
#
# Each array element receives AWS_BATCH_JOB_ARRAY_INDEX (0..N-1). That plus
# PER_SLICE determines the [START:END) subject range this container processes.
# Existing checkpoints for this run are pulled from S3 before processing so
# a preempted slice resumes cleanly; new checkpoints are uploaded after each
# subject via build_norms.py's --checkpoint-sync flag.
#
# Required env:
#   BUCKET           S3 bucket for run artifacts + (optional) data mirrors
#   RUN_ID           run identifier, becomes runs/<RUN_ID>/ prefix
#   DATASET          dataset loader key (lemon, dortmund, ...)
#   CHANNELS         19 or 37
#   CONDITION        eo | ec | both
#   PER_SLICE        subjects per array element
#   WORKERS          --jobs for the ProcessPoolExecutor (e.g. 4 on c6i.2xlarge)
#   SOURCE_FLAGS     space-separated extra flags, e.g. "--source --ba-connectivity"
#                    (use empty string for scalp-only runs)
#
# Optional env:
#   DATA_MIRROR      s3:// URI of the raw-data mirror for this dataset
#                    (e.g. s3://$BUCKET/mirrors/lemon/). If unset, assumes
#                    the loader can fetch data without a pre-staged mirror.
#   CHECKPOINT_LOCAL local work dir (default /work)
#   EXTRA_ARGS       anything else to pass through to build_norms.py

set -euo pipefail

: "${BUCKET:?BUCKET is required}"
: "${RUN_ID:?RUN_ID is required}"
: "${DATASET:?DATASET is required}"
: "${CHANNELS:?CHANNELS is required}"
: "${CONDITION:?CONDITION is required}"
: "${PER_SLICE:?PER_SLICE is required}"
: "${WORKERS:?WORKERS is required}"
: "${AWS_BATCH_JOB_ARRAY_INDEX:?AWS_BATCH_JOB_ARRAY_INDEX must be set by Batch}"

SOURCE_FLAGS="${SOURCE_FLAGS:-}"
CHECKPOINT_LOCAL="${CHECKPOINT_LOCAL:-/work}"
EXTRA_ARGS="${EXTRA_ARGS:-}"

SLICE="$AWS_BATCH_JOB_ARRAY_INDEX"
START=$((SLICE * PER_SLICE))
END=$(((SLICE + 1) * PER_SLICE))
RUN_PREFIX="s3://${BUCKET}/runs/${RUN_ID}"

echo "=== batch_entrypoint ==="
echo "  slice         : ${SLICE}  (range ${START}:${END})"
echo "  dataset       : ${DATASET}"
echo "  channels      : ${CHANNELS}"
echo "  condition     : ${CONDITION}"
echo "  workers       : ${WORKERS}"
echo "  run prefix    : ${RUN_PREFIX}"
echo "  source flags  : ${SOURCE_FLAGS:-<none>}"
echo "  BLAS threads  : OMP=${OMP_NUM_THREADS} OPENBLAS=${OPENBLAS_NUM_THREADS} MKL=${MKL_NUM_THREADS}"

mkdir -p "${CHECKPOINT_LOCAL}/subjects" "${CHECKPOINT_LOCAL}/psd_checkpoints"

# Resume: pull any checkpoints already written for this run. A prior array
# element (or an earlier attempt of this one after spot preemption) may have
# finished subjects in our range. load_checkpoints() in build_norms.py will
# skip them.
echo "--- syncing prior checkpoints ---"
aws s3 sync "${RUN_PREFIX}/subjects/"          "${CHECKPOINT_LOCAL}/subjects/"          --no-progress || true
aws s3 sync "${RUN_PREFIX}/psd_checkpoints/"   "${CHECKPOINT_LOCAL}/psd_checkpoints/"   --no-progress || true

# Pull raw data. For datasets with an S3 mirror, sync it locally first.
# For datasets whose loader downloads directly (e.g. HBN/OpenNeuro), skip this.
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
# SOURCE_FLAGS and EXTRA_ARGS are intentionally unquoted so they split on
# whitespace; callers should pass a single flat string.
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

echo "=== batch_entrypoint done ==="
