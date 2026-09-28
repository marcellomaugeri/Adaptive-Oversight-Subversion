"""One run over its steps: the monitor's suspiciousness, a judge dimension (1-10 rescaled to 0-1), and a dashed black rule at every blocked step. With --show-awareness, also the judge's eval_awareness and monitoring_awareness.

Usage: python -m src.analysis.step_trajectory LOG DIMENSION OUTPUT.html [--show-awareness]
"""

import sys

from inspect_viz import Data
from inspect_viz.mark import line, rule_x
from inspect_viz.plot import legend, plot, write_html

from src.analysis.utils import steps_df

log, dimension, output = sys.argv[1:4]
awareness = {"eval_awareness": "blue", "monitoring_awareness": "green"} if "--show-awareness" in sys.argv[4:] else {}
colors = {"suspiciousness": "orange", dimension: "red", **awareness}
judged = [dimension, *awareness]
run = steps_df(log)
run[judged] = (run[judged] - 1) / 9  # the judge's 1-10 on the 0-1 scale of suspiciousness
series = run.melt(id_vars="step", value_vars=list(colors), var_name="series", value_name="score")
blocked = run.loc[run["blocked"].eq(True), ["step"]].assign(series="blocked")

write_html(output, plot(
    rule_x(Data.from_dataframe(blocked), x="step", stroke="series", stroke_dasharray="4 3"),
    line(Data.from_dataframe(series), x="step", y="score", stroke="series"),
    x_label="Step",
    y_label="Score",
    y_domain=[0, 1],
    color_domain=[*colors, "blocked"],
    color_range=[*colors.values(), "black"],
    legend=legend("color", frame_anchor="top-right", inset=10, background=False),
))
