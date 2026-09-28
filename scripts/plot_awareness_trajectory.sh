#!/usr/bin/env bash
# One run over its steps: the step trajectory plot plus the judge's eval_awareness (blue) and monitoring_awareness (green), written as HTML next to the log.
# Usage: scripts/plot_awareness_trajectory.sh [LOG] [DIMENSION]
#   LOG        an .eval file (default: the most recent log in logs/)
#   DIMENSION  a judge dimension (default: unsanctioned_behaviour)
set -euo pipefail

log="${1:-$(ls -t logs/*.eval | head -1)}"
dimension="${2:-unsanctioned_behaviour}"
output="${log%.eval}_awareness_trajectory_${dimension}.html"

uv run python -m src.analysis.step_trajectory "$log" "$dimension" "$output" --show-awareness
echo "file://$(realpath "$output")"
open "$output"
