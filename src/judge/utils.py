"""Helpers for the judges."""

from inspect_petri import JudgeDimension, judge_dimensions
from yaml import safe_load


def dimensions_from_yaml(path: str) -> list[JudgeDimension]:
    """The dimensions named in the YAML list at `path`, in its order: ours (the `.md` files in `src/judge/dimensions`) by name, the others Petri's defaults. Petri's own YAML loader looks names up only among its defaults, so ours are passed to it as loaded dimensions."""
    ours = {dimension.name: dimension for dimension in judge_dimensions("src/judge/dimensions")}
    with open(path) as file:
        return judge_dimensions([ours.get(name, name) for name in safe_load(file)])
