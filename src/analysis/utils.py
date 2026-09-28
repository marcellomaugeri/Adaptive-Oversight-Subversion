"""Shared helpers for the analysis scripts."""

import json

import pandas as pd
from inspect_ai.analysis import SampleScores, SampleSummary, samples_df


def steps_df(logs: str | list[str]) -> pd.DataFrame:
    """One row per step of every run: the run (`log`, `eval_id`, `sample_id`) and the step judge's record of the step."""
    samples = samples_df(logs, columns=SampleSummary + SampleScores)
    rows = []
    for log, eval_id, sample_id, metadata in samples[["log", "eval_id", "sample_id", "score_audit_judge_metadata"]].itertuples(index=False):
        for step in json.loads(metadata)["steps"]:
            rows.append({"log": log, "eval_id": eval_id, "sample_id": sample_id, **step})
    return pd.DataFrame(rows)
