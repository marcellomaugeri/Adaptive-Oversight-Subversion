"""One run over its steps: the chosen dimensions, each either the monitor's suspiciousness or a judge dimension (1-10 rescaled to 0-1). With --show-blocks, also a dashed black rule at every blocked step.

Usage: python -m src.analysis.step_trajectory LOG EPOCH OUTPUT.html DIMENSION [DIMENSION ...] [--show-blocks]
"""

import argparse
import zlib

from inspect_viz import Data
from inspect_viz.mark import line, rule_x
from inspect_viz.plot import legend, plot, write_html

from src.analysis import COLOURS_MAP
from src.analysis.utils import steps_df

parser = argparse.ArgumentParser()
parser.add_argument("log")
parser.add_argument("epoch", type=int)
parser.add_argument("output")
parser.add_argument("dimensions", nargs="+")
parser.add_argument("--show-blocks", action="store_true")
args = parser.parse_args()

judged = [dimension for dimension in args.dimensions if dimension != "suspiciousness"]
run = steps_df(args.log)
run[judged] = (run[judged] - 1) / 9  # the judge's 1-10 on the 0-1 scale of suspiciousness
run = run[run["epoch"].eq(args.epoch)]
series = run.melt(id_vars="step", value_vars=args.dimensions, var_name="series", value_name="score")
marks = [line(Data.from_dataframe(series), x="step", y="score", stroke="series")]
names = args.dimensions
if args.show_blocks:
    blocked = run.loc[run["blocked"].eq(True), ["step"]].assign(series="blocked")
    marks = [rule_x(Data.from_dataframe(blocked), x="step", stroke="series", stroke_dasharray="4 3"), *marks]
    names = [*args.dimensions, "blocked"]

write_html(args.output, plot(
    *marks,
    x_label="Step",
    y_label="Score",
    y_domain=[0, 1],
    color_domain=names,
    color_range=[COLOURS_MAP.get(name, f"hsl({zlib.crc32(name.encode()) % 360}, 70%, 45%)") for name in names],  # a name outside the map gets a hue computed from the name, so it is the same in every chart; 70% saturation keeps it vivid, 45% lightness keeps it dark enough to read on white
    legend=legend("color", frame_anchor="top-right", inset=10, background=False),
))
