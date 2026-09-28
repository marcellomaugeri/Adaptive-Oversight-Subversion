"""One run over its steps: the monitor's suspiciousness, a judge dimension (1-10 rescaled to 0-1), and a red rule at every blocked step.

Usage: python -m src.analysis.step_trajectory LOG DIMENSION OUTPUT.html
"""

import sys

from inspect_viz import Data
from inspect_viz.mark import line, rule_x
from inspect_viz.plot import legend, plot, write_html

from src.analysis.utils import steps_df

log, dimension, output = sys.argv[1:4]
run = steps_df(log)
run[dimension] = (run[dimension] - 1) / 9  # the judge's 1-10 on the 0-1 scale of suspiciousness
series = run.melt(id_vars="step", value_vars=["suspiciousness", dimension], var_name="series", value_name="score")
blocked_steps = run.loc[run["blocked"].eq(True), "step"].tolist()

write_html(output, plot(
    rule_x(x=blocked_steps, stroke="red", stroke_dasharray="4 3"),
    line(Data.from_dataframe(series), x="step", y="score", stroke="series"),
    x_label="Step",
    y_label="Score",
    y_domain=[0, 1],
    color_domain=["suspiciousness", dimension],
    color_range=["orange", "red"],
    legend=legend("color", frame_anchor="top-right", inset=10, background=False),
))
