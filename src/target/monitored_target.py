"""The target of the monitored audit: Petri's target loop, with the system messages staged by the CoT monitor (`src/cot_monitor.py`) and input compaction."""

from inspect_ai.agent import AgentState
from inspect_ai.model import CompactionAuto, compaction, get_model
from inspect_petri.target import TOOL_RESULT, ExitSignal, TargetContext


class MonitoredTarget:
    """Petri's target loop (`inspect_petri/target/_agent.py`, prefill and caching left out), which also delivers a system message staged during the conversation, as the last message before the target generates. Petri's own loop reads the system message only at the start. Like Petri's auditor, the target compacts its input when it reaches `compaction_threshold`; `state.messages` keeps the full conversation."""

    def __init__(self, compaction_threshold: int | float) -> None:
        self.compaction_threshold = compaction_threshold  # as in Inspect's CompactionAuto: a fraction of the context window up to 1.0, otherwise a token count

    async def __call__(self, state: AgentState, context: TargetContext) -> AgentState:
        generate = context.replayable(get_model(role="target").generate, surface_errors=True)
        try:
            # the system and user message written by the auditor
            await context.wait_for_resume()
            state.messages[:] = [await context.system_message(), await context.user_message()]
            # the system and user message are always kept, the rest is compacted when the input reaches the threshold
            compact = compaction(CompactionAuto(threshold=self.compaction_threshold), prefix=state.messages, tools=context.tools, model=get_model(role="target"))

            while True:
                # 1. the target generates its next step (ASSISTANT) from its input, compacted if needed; the summary of a compaction is kept in the conversation
                input, summary = await compact.compact_input(state.messages)
                if summary is not None:
                    state.messages.append(summary)
                state.output = await generate(input=input, tools=context.tools)
                await compact.record_output(input, state.output)
                state.messages.append(state.output.message)

                if tool_calls := state.output.message.tool_calls:
                    # 2. the step goes to the auditor's resume, where the monitor rates it and, if disclosed, stages its score
                    context.expect({TOOL_RESULT: {call.id for call in tool_calls}})
                    await context.send_output(state.output)
                    # 3. the tool results (TOOL) from the auditor, or from the turn written after a block: the APIs require them right after the tool calls
                    state.messages.extend(await context.tool_results(tool_calls))
                    # 4. the user message (USER), if the auditor wrote one: Petri's order
                    if user_message := await context.user_message(required=False):
                        state.messages.append(user_message)
                else:
                    # 2. the step (a message to the user) goes to the auditor's resume, where the monitor rates it
                    context.expect({TOOL_RESULT: set()})
                    await context.send_output(state.output)
                    # 4. the auditor must answer as the user (USER)
                    state.messages.append(await context.user_message())

                # 5. the change to Petri's loop: the system message staged by the monitor (SYSTEM, the score of the step above). Claude models allow a system message in the middle of the conversation only after a user message or a tool result, and only if an assistant message follows, so here we add it last, right before the target generates again.
                if system_message := await context.system_message(required=False):
                    state.messages.append(system_message)
        except ExitSignal:
            return state
