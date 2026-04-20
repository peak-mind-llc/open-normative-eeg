#!/usr/bin/env bash
# One-command "do the whole thing": submit LEMON + Dortmund recomputes on
# AWS Batch, wait for both to finish, download outputs, and run the full
# validation suite (internal split-half + literature + cross-dataset +
# source plausibility) ending in a per-dataset markdown report.
#
# Usage:
#   scripts/pipeline/run_everything.sh [RESULTS_DIR]
#
# Expected wall time:  ~75-100 min end to end
# Expected AWS cost:   ~$6-8 at the current m-family / 28 GB config
#
# See scripts/pipeline/recompute_all.sh and scripts/pipeline/validate_all.sh
# for the individual stages and their configuration knobs.

set -euo pipefail

RESULTS_DIR="${1:-./results}"
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "=== Stage 1: AWS Batch recomputes (LEMON + Dortmund) ==="
"$HERE/recompute_all.sh" "$RESULTS_DIR"

echo
echo "=== Stage 2: Validation suite ==="
"$HERE/validate_all.sh" "$RESULTS_DIR"

echo
echo "=== Done. ==="
echo "Merged norms:    $RESULTS_DIR/<dataset>/out/norms.json"
echo "Validation JSON: $RESULTS_DIR/validation/"
echo "Reports:         $RESULTS_DIR/validation/*_report.md"
