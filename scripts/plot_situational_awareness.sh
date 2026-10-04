#!/usr/bin/env bash
# One run over its steps: the judge's eval_awareness, monitoring_awareness and scenario_realism against unsanctioned_behaviour, and the blocked steps as dashed black lines, written as HTML next to the log.
# Usage: scripts/plot_situational_awareness.sh [LOG] [EPOCH]
#   LOG    an .eval file (default: the most recent log in logs/)
#   EPOCH  the run within the log (default: 1)
set -euo pipefail

log="${1:-$(ls -t logs/*.eval | head -1)}"
epoch="${2:-1}"
output="${log%.eval}_epoch_${epoch}_situational_awareness.html"

uv run python -m src.analysis.step_trajectory "$log" "$epoch" "$output" eval_awareness monitoring_awareness scenario_realism unsanctioned_behaviour --show-blocks
echo "file://$(realpath "$output")"
open "$output"
