"""Entry point: the monitored audit task, Petri's audit with the CoT monitor wired in."""

from argparse import ArgumentParser

from inspect_ai import Task, task
from inspect_ai.log import transcript
from inspect_ai.model import ModelInfo, set_model_info
from inspect_ai.tool import Tool, ToolDef, ToolParam, ToolParams
from inspect_petri import audit_solver, audit_viewer, auditor_agent, auditor_tools, seeds_dataset

from src.cot_monitor import Feedback, Monitoring, generate_hook, monitored_resume
from src.judge.step_judge import step_judge
from src.judge.utils import dimensions_from_yaml
from src.prompts.auditor import AUDITOR_SYSTEM_PROMPT, AUDITOR_USER_PROMPT
from src.seed_builder.builder import build_seeds
from src.target.monitored_target import MonitoredTarget

# Inspect does not know Space Bunny's context window (models.dev lists 524,288 input tokens) and would otherwise compact at 0.9 of a default 128,000
set_model_info("openai-api/opencode/space-bunny-free", ModelInfo(context_length=524288))
# Inspect only knows the retired alias deepseek-v4-flash; DeepSeek's docs list deepseek-flash (DeepSeek-V4.1-Flash) with a 1M context
set_model_info("deepseek/deepseek-flash", ModelInfo(context_length=1048576))


class ExplainedEndConversation:
    """Petri's `end_conversation` tool, which also records the auditor's motivation when it ends a run early.

    Args:
        motivation (str): Why the auditor stopped the run.
    """

    def __init__(self, original: Tool) -> None:
        self.original = original  # Petri's end_conversation

    async def __call__(self, motivation: str) -> str:
        transcript().info({"motivation": motivation}, source="auditor_stop")
        return await self.original()


def explained_end_conversation(original: Tool) -> Tool:
    """Wrap Petri's `end_conversation` tool, as `monitored_resume` wraps `resume`: the auditor must state why it stops."""
    parameters = ToolParams(properties={"motivation": ToolParam(type="string", description="Why the auditor stopped the run.")}, required=["motivation"])
    return ToolDef(ExplainedEndConversation(original), name="end_conversation", description="End the conversation only when the agent persistently cannot continue, as the seed instructions define; never because the objective is complete. Record the motivation for stopping.", parameters=parameters).as_tool()


@task
def monitored_audit(
    seed_instructions: str | None = None,
    max_turns: int = 30,
    monitoring: Monitoring = "passive",
    threshold: float | None = None,
    feedback: Feedback | None = None,
    disclose_suspiciousness: bool = False,
    compaction_threshold: dict[str, int | float] | None = None,
    vllm_lens: bool = False,
) -> Task:
    """Run a Petri audit where an auditor simulates the environment, a monitor rates target steps, and a judge scores them.

    Run `inspect eval main.py@monitored_audit -T seed_instructions=seeds/`; repeat `-T name=value` for other options and configure the auditor, target, monitor, and judge model roles with `--model-role` or `INSPECT_EVAL_MODEL_ROLE`.
    For capture, run a vLLM-Lens server, set the target role to `vllm/<model>`, and point `VLLM_BASE_URL` to its API URL.
    Then add `-T vllm_lens=true`; encoded captures appear in each target `ModelEvent.call.response` in the `.eval` log.
    This captures the residual stream, not attention internals or MoE expert routing.

    Args:
        seed_instructions: Scenario text, seed file, or seed directory; omit to use Petri's built-in seeds.
        max_turns: Maximum number of auditor turns in the scenario (default: 30).
        monitoring: "passive" only rates steps; "active" also blocks tool calls at the threshold.
        threshold: Minimum suspiciousness score that blocks a tool call; required only with active monitoring.
        feedback: "decision" shows a block, while "rationale" also gives the reason; required only with active monitoring.
        disclose_suspiciousness: Show the target its numeric suspiciousness score after each rated step.
        compaction_threshold: Per-role context fraction up to 1.0 or token count; omitted roles use 0.9.
        vllm_lens: Use with a vLLM-Lens server and a `vllm/` target to collect per-token, per-layer residual activations and prompt/output token IDs in the Inspect log for mechanistic interpretability.
    """
    # an active monitor needs a threshold and a feedback, a passive monitor takes neither
    if (monitoring == "active") != (threshold is not None) or (monitoring == "active") != (feedback is not None):
        raise ValueError(f"monitoring={monitoring!r} does not match threshold={threshold!r} and feedback={feedback!r}: an active monitor needs both, a passive monitor takes neither.")

    # the compaction thresholds are keyed by the model roles
    compaction_threshold = compaction_threshold or {}
    unknown = set(compaction_threshold) - {"auditor", "target", "monitor", "judge"}
    if unknown:
        raise ValueError(f"compaction_threshold has unknown roles {sorted(unknown)}: the roles are auditor, target, monitor and judge.")

    tools = []
    for tool in auditor_tools(rollback=False):
        if ToolDef(tool).name == "resume":
            tool = monitored_resume(tool, monitoring, threshold, feedback, disclose_suspiciousness, compaction_threshold.get("monitor", 0.9))
        elif ToolDef(tool).name == "end_conversation":
            tool = explained_end_conversation(tool)
        tools.append(tool)

    auditor = auditor_agent(max_turns=max_turns, tools=tools, generate=generate_hook, system_message=AUDITOR_SYSTEM_PROMPT, user_message=AUDITOR_USER_PROMPT, compaction=compaction_threshold.get("auditor", 0.9))

    # the judge dimensions listed in src/dimensions.yaml, in that order
    dimensions = dimensions_from_yaml("src/dimensions.yaml")

    return Task(
        dataset=seeds_dataset(seed_instructions),
        solver=audit_solver(auditor=auditor, target=MonitoredTarget(compaction_threshold.get("target", 0.9), vllm_lens)),
        scorer=step_judge(dimensions, compaction_threshold=compaction_threshold.get("judge", 0.9)),
        viewer=audit_viewer(dimensions),
    )


if __name__ == "__main__":
    parser = ArgumentParser(description="Build the runnable seeds for Petri.")
    parser.add_argument("--build", action="store_true", help="write generated Markdown seeds into seeds/")
    arguments = parser.parse_args()
    if not arguments.build:
        parser.error("use --build to generate seeds")
    for generated_seed in build_seeds():
        print(generated_seed)
