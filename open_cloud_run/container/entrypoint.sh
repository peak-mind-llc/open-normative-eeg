#!/usr/bin/env bash
# open_cloud_run — generic container entrypoint.
#
# Experiment images FROM a base that includes this script as their
# ENTRYPOINT. The script stays identical across experiments; only the
# DRIVER_CMD / MERGE_CMD env vars (set by submit.py) differ.
#
# MODE=array (default): read the slice manifest from S3, loop DRIVER_CMD
#   once per unit with $UNIT / $OUT_DIR set, sync outputs at slice end.
# MODE=merge: pull all units' outputs from S3, run MERGE_CMD, sync
#   aggregate outputs back up.
#
# Required env (both modes):
#   BUCKET, RUN_ID          — S3 scope
#   RUNS_PREFIX             — bucket prefix for per-run artifacts
#   OUT_DIR                 — local directory for driver/merge outputs
#
# MODE=array additional:
#   AWS_BATCH_JOB_ARRAY_INDEX  — set by Batch
#   DRIVER_CMD                 — shell command; $UNIT is substituted each iter
#
# MODE=merge additional:
#   MERGE_CMD                  — shell command, receives INPUTS_DIR + MERGE_OUT env
#
# Optional env:
#   CHECKPOINT_LOCAL   — local work dir (default /work)
#   BLAS_THREADS       — set to "1" to pin OMP/OPENBLAS/MKL (default: "1")
#
# Driver contract (what the DRIVER_CMD expects):
#   UNIT           — the current work unit identifier (string)
#   OUT_DIR        — directory to write outputs into ($CHECKPOINT_LOCAL/out/$UNIT/)
#   RUN_ID, BUCKET, SLICE_INDEX — informational; most drivers ignore
#
# See docs/open-cloud-run.md for the full contract.

set -euo pipefail

MODE="${MODE:-array}"
: "${BUCKET:?BUCKET is required}"
: "${RUN_ID:?RUN_ID is required}"
: "${RUNS_PREFIX:?RUNS_PREFIX is required}"
: "${OUT_DIR:?OUT_DIR is required}"

CHECKPOINT_LOCAL="${CHECKPOINT_LOCAL:-/work}"
BLAS_THREADS="${BLAS_THREADS:-1}"

# Pin BLAS threads for cross-machine reproducibility unless opted out.
if [ -n "$BLAS_THREADS" ]; then
    export OMP_NUM_THREADS="$BLAS_THREADS"
    export OPENBLAS_NUM_THREADS="$BLAS_THREADS"
    export MKL_NUM_THREADS="$BLAS_THREADS"
    export NUMEXPR_NUM_THREADS="$BLAS_THREADS"
    export VECLIB_MAXIMUM_THREADS="$BLAS_THREADS"
fi

RUN_PREFIX="s3://${BUCKET}/${RUNS_PREFIX}${RUN_ID}"

echo "=== open_cloud_run entrypoint ==="
echo "  mode           : ${MODE}"
echo "  run            : ${RUN_PREFIX}"
echo "  out_dir (root) : ${OUT_DIR}"
echo "  BLAS threads   : OMP=${OMP_NUM_THREADS:-?} OPENBLAS=${OPENBLAS_NUM_THREADS:-?} MKL=${MKL_NUM_THREADS:-?}"

case "${MODE}" in

  array)
    : "${AWS_BATCH_JOB_ARRAY_INDEX:?AWS_BATCH_JOB_ARRAY_INDEX must be set by Batch}"
    : "${DRIVER_CMD:?DRIVER_CMD is required}"

    SLICE_INDEX="${AWS_BATCH_JOB_ARRAY_INDEX}"
    SLICE_PREFIX="${RUN_PREFIX}/slices/${SLICE_INDEX}"
    SLICE_MANIFEST="/tmp/slice_manifest.txt"

    mkdir -p "${OUT_DIR}"

    # Pull prior outputs so resume after preemption skips completed
    # units if the driver's idempotency check looks at OUT_DIR.
    echo "--- syncing prior outputs (if any) ---"
    aws s3 sync "${RUN_PREFIX}/out/" "${OUT_DIR}/" --no-progress 2>&1 || true

    echo "--- fetching slice manifest from ${SLICE_PREFIX}/manifest.txt ---"
    aws s3 cp "${SLICE_PREFIX}/manifest.txt" "${SLICE_MANIFEST}" --no-progress
    N_UNITS=$(wc -l < "${SLICE_MANIFEST}" | tr -d ' ')
    echo "    ${N_UNITS} units for slice ${SLICE_INDEX}"

    FAILED=0
    SUCCEEDED=0
    SKIPPED=0

    # Save the root OUT_DIR before the loop overwrites it per-unit.
    ROOT_OUT_DIR="${OUT_DIR}"

    while IFS= read -r UNIT || [ -n "${UNIT}" ]; do
        [ -z "${UNIT}" ] && continue
        UNIT_OUT_DIR="${ROOT_OUT_DIR}/${UNIT}"
        mkdir -p "${UNIT_OUT_DIR}"

        echo ""
        echo "----- slice=${SLICE_INDEX} unit=${UNIT} -----"
        export UNIT OUT_DIR="${UNIT_OUT_DIR}" RUN_ID BUCKET SLICE_INDEX
        if eval "${DRIVER_CMD}"; then
            SUCCEEDED=$((SUCCEEDED + 1))
        else
            RC=$?
            if [ "${RC}" -eq 99 ]; then
                # Convention: drivers can exit 99 to explicitly indicate
                # "this unit was already done, skipped".
                SKIPPED=$((SKIPPED + 1))
            else
                echo "    unit ${UNIT} FAILED with exit ${RC}" >&2
                FAILED=$((FAILED + 1))
            fi
        fi
    done < "${SLICE_MANIFEST}"

    # Restore OUT_DIR for the slice-end sync.
    export OUT_DIR="${ROOT_OUT_DIR}"

    echo ""
    echo "--- slice complete: ${SUCCEEDED} ok, ${SKIPPED} skipped, ${FAILED} failed ---"
    echo "--- syncing ${OUT_DIR}/ → ${RUN_PREFIX}/out/ ---"
    aws s3 sync "${OUT_DIR}/" "${RUN_PREFIX}/out/" --no-progress

    if [ "${FAILED}" -gt 0 ]; then
        echo "ERROR: ${FAILED} unit(s) failed in this slice" >&2
        exit 1
    fi
    ;;

  merge)
    : "${MERGE_CMD:?MERGE_CMD is required}"

    INPUTS_DIR="${CHECKPOINT_LOCAL}/inputs"
    MERGE_OUT="${OUT_DIR}"
    mkdir -p "${INPUTS_DIR}" "${MERGE_OUT}"

    echo "--- syncing per-unit outputs from ${RUN_PREFIX}/out/ ---"
    aws s3 sync "${RUN_PREFIX}/out/" "${INPUTS_DIR}/" --no-progress

    echo "--- running MERGE_CMD ---"
    echo "    INPUTS_DIR=${INPUTS_DIR}"
    echo "    MERGE_OUT=${MERGE_OUT}"
    export INPUTS_DIR MERGE_OUT RUN_ID BUCKET
    eval "${MERGE_CMD}"

    echo "--- syncing merge output → ${RUN_PREFIX}/out_merged/ ---"
    aws s3 sync "${MERGE_OUT}/" "${RUN_PREFIX}/out_merged/" --no-progress
    ;;

  *)
    echo "Unknown MODE=${MODE}. Set MODE=array or MODE=merge." >&2
    exit 1 ;;
esac

echo "=== done ==="
