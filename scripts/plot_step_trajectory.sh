#!/usr/bin/env bash
# One run over its steps: the monitor's suspiciousness, a judge dimension, and the blocked steps in red, written as HTML next to the log.
# Usage: scripts/plot_step_trajectory.sh [LOG] [DIMENSION]
#   LOG        an .eval file (default: the most recent log in logs/)
#   DIMENSION  a judge dimension (default: unsanctioned_behaviour)
set -euo pipefail

log="${1:-$(ls -t logs/*.eval | head -1)}"
dimension="${2:-unsanctioned_behaviour}"
output="${log%.eval}_step_trajectory_${dimension}.html"

uv run python -m src.analysis.step_trajectory "$log" "$dimension" "$output"
echo "file://$(realpath "$output")"
open "$output"
