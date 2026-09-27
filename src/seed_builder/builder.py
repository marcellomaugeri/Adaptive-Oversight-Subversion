"""Render the explicitly selected seed configurations into ``seeds/``."""

import re
import tomllib
from pathlib import Path


SOURCE_DIR = Path(__file__).resolve().parent
SEEDS_DIR = SOURCE_DIR.parents[1] / "seeds"

# output filename -> (scenario, condition); each scenario is rendered from one base file
CONFIGURATIONS = {
    "uk_aisi_DL-v2_incident_replica.md": ("1_aisi_range.md", "2_aisi_range_dl_v1_task.toml"),
    "uk_aisi_DL-v2_correct_prompt.md": ("1_aisi_range.md", "2_aisi_range_dl_v2_task.toml"),
    "insider_trading_no_nudge.md": ("1_insider_trading.md", "2_insider_trading_no_nudge.toml"),
    "insider_trading_nudge.md": ("1_insider_trading.md", "2_insider_trading_nudge.toml"),
    "insider_trading_strong_nudge.md": ("1_insider_trading.md", "2_insider_trading_strong_nudge.toml"),
}

PLACEHOLDER = re.compile(r"\{([A-Z][A-Z0-9_]*)\}")


def render(scenario: str, condition: dict[str, str], auditor: str) -> str:
    values = {"AUDITOR": auditor, **condition}
    placeholders = set(PLACEHOLDER.findall(scenario))
    if placeholders != values.keys():
        raise ValueError(f"Placeholder mismatch: missing={placeholders - values.keys()}, unused={values.keys() - placeholders}")
    for name, value in values.items():
        if not isinstance(value, str):
            raise ValueError(f"{name} must be a string")
        scenario = scenario.replace("{" + name + "}", value)
    return scenario.rstrip() + "\n"


def build_seeds() -> list[Path]:
    """Create the output directory and overwrite only the listed generated seeds."""
    auditor = (SOURCE_DIR / "0_auditor.md").read_text().strip()
    rendered = {}
    for output, (base_name, condition_name) in CONFIGURATIONS.items():
        scenario = (SOURCE_DIR / base_name).read_text()
        with (SOURCE_DIR / condition_name).open("rb") as file:
            condition = tomllib.load(file)
        rendered[output] = render(scenario, condition, auditor)

    SEEDS_DIR.mkdir(parents=True, exist_ok=True)
    for output, text in rendered.items():
        (SEEDS_DIR / output).write_text(text)
    return [SEEDS_DIR / output for output in rendered]
