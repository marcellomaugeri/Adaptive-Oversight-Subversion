"""Entry point: the monitored audit task, Petri's audit with the CoT monitor wired in."""

from inspect_ai import Task, task
from inspect_ai.tool import ToolDef
from inspect_petri import audit_judge, audit_solver, audit_viewer, auditor_agent, auditor_tools, seeds_dataset

from src.cot_monitor import Disclosure, TargetWithSystemMessages, generate_hook, monitored_resume


@task
def monitored_audit(
    seed_instructions: str | None = None,
    max_turns: int = 30,
    threshold: float | None = None,
    disclosure: Disclosure = "nothing",
) -> Task:
    """Petri's audit with rollback disabled and the monitor. With `threshold=None` the monitor rates every step and never blocks."""
    tools = []
    for tool in auditor_tools(rollback=False):
        if ToolDef(tool).name == "resume":
            tool = monitored_resume(tool, threshold, disclosure)
        tools.append(tool)

    return Task(
        dataset=seeds_dataset(seed_instructions),
        solver=audit_solver(
            auditor=auditor_agent(max_turns=max_turns, tools=tools, generate=generate_hook),
            target=TargetWithSystemMessages(),
        ),
        scorer=audit_judge(),
        viewer=audit_viewer(),
    )
