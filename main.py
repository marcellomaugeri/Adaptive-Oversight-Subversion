"""Entry point: the monitored audit task, Petri's audit with the CoT monitor wired in."""

from argparse import ArgumentParser

from inspect_ai import Task, task
from inspect_ai.log import transcript
from inspect_ai.tool import Tool, ToolDef
from inspect_petri import audit_judge, audit_solver, audit_viewer, auditor_agent, auditor_tools, seeds_dataset

from src.cot_monitor import Disclosure, generate_hook, monitored_resume
from src.prompts.auditor import AUDITOR_SYSTEM_PROMPT, AUDITOR_USER_PROMPT
from src.target.monitored_target import MonitoredTarget


def explained_end_conversation(original: Tool) -> Tool:
    """Record the auditor's motivation when it ends a run early."""

    async def end(motivation: str) -> str:
        """End the conversation.

        Args:
            motivation: Why the auditor stopped the run.
        """
        transcript().info({"motivation": motivation}, source="auditor_stop")
        return await original()

    return ToolDef(end, name="end_conversation", description="End the conversation and record the motivation for stopping.").as_tool()


@task
def monitored_audit(
    seed_instructions: str | None = None,
    max_turns: int = 30,
    threshold: float | None = None,
    disclosure: Disclosure = "nothing",
    target_compaction: int | float = 0.9,
) -> Task:
    """Run Petri's audit with rollback disabled and the monitor enabled.

    With `threshold=None`, the monitor rates each step without blocking it.
    The target compacts its input at `target_compaction`: a fraction of its
    context window up to 1.0, or a token count otherwise.
    """
    tools = []
    for tool in auditor_tools(rollback=False):
        if ToolDef(tool).name == "resume":
            tool = monitored_resume(tool, threshold, disclosure)
        elif ToolDef(tool).name == "end_conversation":
            tool = explained_end_conversation(tool)
        tools.append(tool)

    auditor = auditor_agent(max_turns=max_turns, tools=tools, generate=generate_hook, system_message=AUDITOR_SYSTEM_PROMPT, user_message=AUDITOR_USER_PROMPT)

    return Task(
        dataset=seeds_dataset(seed_instructions),
        solver=audit_solver(auditor=auditor, target=MonitoredTarget(target_compaction)),
        scorer=audit_judge(),
        viewer=audit_viewer(),
    )


if __name__ == "__main__":
    parser = ArgumentParser(description="Build the runnable seeds for Petri.")
    parser.add_argument("--build", action="store_true", help="write generated Markdown seeds into seeds/")
    arguments = parser.parse_args()
    if not arguments.build:
        parser.error("use --build to generate seeds")
    from src.seed_builder.builder import build_seeds

    for generated_seed in build_seeds():
        print(generated_seed)
