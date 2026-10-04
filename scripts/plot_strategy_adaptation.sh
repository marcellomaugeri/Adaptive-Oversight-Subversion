#!/usr/bin/env bash
# One run over its steps: the judge's strategy_change, objective_change and monitoring_awareness against the monitor's suspiciousness, and the blocked steps as dashed black lines, written as HTML next to the log.
# Usage: scripts/plot_strategy_adaptation.sh [LOG] [EPOCH]
#   LOG    an .eval file (default: the most recent log in logs/)
#   EPOCH  the run within the log (default: 1)
set -euo pipefail

log="${1:-$(ls -t logs/*.eval | head -1)}"
epoch="${2:-1}"
output="${log%.eval}_epoch_${epoch}_strategy_adaptation.html"

uv run python -m src.analysis.step_trajectory "$log" "$epoch" "$output" strategy_change objective_change monitoring_awareness suspiciousness --show-blocks
echo "file://$(realpath "$output")"
open "$output"
