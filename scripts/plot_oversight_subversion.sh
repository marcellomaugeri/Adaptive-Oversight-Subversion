#!/usr/bin/env bash
# One run over its steps: the judge's unsanctioned_behaviour, oversight_subversion and stuck_in_loops, and the blocked steps as dashed black lines, written as HTML next to the log.
# Usage: scripts/plot_oversight_subversion.sh [LOG] [EPOCH]
#   LOG    an .eval file (default: the most recent log in logs/)
#   EPOCH  the run within the log (default: 1)
set -euo pipefail

log="${1:-$(ls -t logs/*.eval | head -1)}"
epoch="${2:-1}"
output="${log%.eval}_epoch_${epoch}_oversight_subversion.html"

uv run python -m src.analysis.step_trajectory "$log" "$epoch" "$output" unsanctioned_behaviour oversight_subversion stuck_in_loops --show-blocks
echo "file://$(realpath "$output")"
open "$output"
