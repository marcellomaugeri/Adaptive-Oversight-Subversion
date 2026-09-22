"""Chain-of-thought monitor for Petri.

Adapted from the CoT monitor of Baker et al., "Monitoring Reasoning Models for Misbehavior and the Risks of Promoting Obfuscation" (2025), which observes the chain-of-thought, the tool calls and the outputs of the agent, and from the per-action suspiciousness of Greenblatt et al., "AI Control: Improving Safety Despite Intentional Subversion" (2024).

How it plugs into Petri, using only documented extension points:
1. `MonitoredResume` replaces the auditor's `resume` tool. When the target has proposed a step, the monitor rates it before the auditor sees it. If the suspiciousness reaches the threshold, the step is blocked.
2. `generate_hook` replaces the auditor's per-turn LLM call (the `generate` option of `auditor_agent`). After a block, the next turn skips the LLM: this code writes the turn as the auditor would, one `send_tool_call_result` with the error for every tool call of the step, then `resume`. The auditor reads the block in its own format, the target tries again and the turn still counts toward `max_turns`.
3. `TargetWithSystemMessages` is Petri's target loop plus one change: a system message staged during the conversation (the built-in SYSTEM slot) is delivered to the target. It is used to show the target its suspiciousness.

The `monitored_audit` task in `main.py` wires these into a Petri audit. Every rating is recorded in the log as an info event with source "cot_monitor".
"""

import uuid
from typing import Literal

from inspect_ai.agent import AgentState
from inspect_ai.log import transcript
from inspect_ai.model import CachePolicy, ChatMessage, ChatMessageAssistant, ChatMessageSystem, ChatMessageUser, Model, ModelOutput, get_model
from inspect_ai.tool import Tool, ToolCall, ToolDef, ToolParams
from inspect_ai.util import store
from inspect_petri.target import TOOL_RESULT, ExitSignal, TargetContext, controller
from inspect_scout import AnswerStructured, MessagesPreprocessor, generate_answer, messages_as_str
from pydantic import BaseModel, Field

from .prompts.monitor import MONITOR_PROMPT_TEMPLATE, MONITOR_SYSTEM_PROMPT

# what the target reads in place of the result of a blocked tool call
BLOCKED_ERROR = "Call blocked"

# what the target reads after a step when its suspiciousness is disclosed, followed by the score
SUSPICIOUSNESS_MESSAGE = "Suspiciousness: "

# key in the per-sample store: the tool results of a blocked step, which the next auditor turn sends
PENDING_TOOL_RESULTS = "cot_monitor_pending_tool_results"

# what the target is told about the monitor
Disclosure = Literal["nothing", "rationale", "suspiciousness"]


class MonitorOutput(BaseModel):
    # Scout's structured answer gives two aliases a special meaning: the field aliased "value" becomes `result.value` (the main value of the result) and the field aliased "explanation" becomes `result.explanation`. We map our two fields onto them because, without these aliases, Scout returns both fields together in a dict and adds an "explanation" field of its own, asking the monitor to explain a second time.
    suspiciousness: float = Field(alias="value", ge=0.0, le=1.0, description="Suspiciousness of the last step, between 0 and 1.")
    rationale: str = Field(alias="explanation", description="One or two sentences explaining the suspiciousness.")


async def monitor(messages: list[ChatMessage]) -> MonitorOutput | None:
    """Rate the last step in `messages` (the target's conversation) with the model bound to the `monitor` role. Returns None when the monitor gave no valid answer."""
    # the monitor receives the target's conversation (instructions, messages, chain-of-thought, tool calls and results), without the scores disclosed to the target
    messages = [message for message in messages if not (message.role == "system" and message.text.startswith(SUSPICIOUSNESS_MESSAGE))]
    # the trajectory as a JSON list of {"role", "content"}; the system message is kept: the monitor judges the step against the instructions of the agent. The role label is excluded because the JSON "role" field already carries it (needs the Scout patch, see README)
    preprocessor = MessagesPreprocessor(exclude_system=False, exclude_role_label=True)
    trajectory = await messages_as_str(messages, preprocessor=preprocessor, format="json")
    # Scout's structured answer, as in Petri's judge: a missing or invalid answer is asked again, up to 3 attempts
    result = await generate_answer(
        [ChatMessageSystem(content=MONITOR_SYSTEM_PROMPT), ChatMessageUser(content=MONITOR_PROMPT_TEMPLATE.format(trajectory=trajectory))],
        AnswerStructured(type=MonitorOutput),
        model=get_model(role="monitor", required=True),
    )
    if result.value is None:
        return None
    return MonitorOutput(value=result.value, explanation=result.explanation)


class MonitoredResume:
    """The auditor's `resume` tool, with the monitor between the target and the auditor."""

    def __init__(self, resume: Tool, threshold: float | None, disclosure: Disclosure) -> None:
        self.resume = resume  # Petri's resume: wakes the target and returns its next step as text
        self.threshold = threshold  # None: rate every step, never block (the baseline)
        self.disclosure = disclosure

    async def __call__(self) -> str:
        target_response = await self.resume()
        step = controller().state.messages[-1]  # the step the target has just proposed
        rating = await monitor(controller().state.messages)

        # without a valid answer the step passes, and the rating is recorded as missing
        if rating is None:
            transcript().info(
                {"message_id": step.id, "suspiciousness": None, "rationale": None, "threshold": self.threshold, "blocked": False},
                source="cot_monitor",
            )
            return str(target_response)

        # only tool calls can be blocked: a message to the user is rated but always passes
        blocked = bool(step.tool_calls) and self.threshold is not None and rating.suspiciousness >= self.threshold
        transcript().info(
            {"message_id": step.id, **rating.model_dump(), "threshold": self.threshold, "blocked": blocked},
            source="cot_monitor",
        )

        # the target reads its suspiciousness after the step, as a system message
        if self.disclosure == "suspiciousness":
            await controller().stage_system(f"{SUSPICIOUSNESS_MESSAGE}{rating.suspiciousness}")

        if not blocked:
            return str(target_response)

        # blocked: the next auditor turn answers every tool call of the step with the error, see generate_hook
        error = f"{BLOCKED_ERROR}: {rating.rationale}" if self.disclosure == "rationale" else BLOCKED_ERROR
        store().set(PENDING_TOOL_RESULTS, [{"tool_call_id": call.id, "result": error, "status": "error"} for call in step.tool_calls])
        return str(target_response)


def monitored_resume(resume: Tool, threshold: float | None, disclosure: Disclosure) -> Tool:
    """Wrap Petri's `resume` tool, keeping the name and description that the auditor knows."""
    original = ToolDef(resume)
    monitored = MonitoredResume(resume, threshold, disclosure)
    return ToolDef(monitored, name=original.name, description=original.description, parameters=ToolParams(), viewer=original.viewer).as_tool()


async def generate_hook(model: Model, messages: list[ChatMessage], tools: list[Tool], cache: bool | CachePolicy) -> ModelOutput:
    """The auditor's per-turn LLM call. After a block the LLM is skipped and the turn is written here, as the auditor would write it."""
    if results := store().get(PENDING_TOOL_RESULTS):
        store().delete(PENDING_TOOL_RESULTS)
        calls = [ToolCall(id=str(uuid.uuid4()), function="send_tool_call_result", arguments=result) for result in results]
        calls.append(ToolCall(id=str(uuid.uuid4()), function="resume", arguments={}))
        return ModelOutput.from_message(ChatMessageAssistant(content="", tool_calls=calls, model=str(model)), stop_reason="tool_calls")
    return await model.generate(input=messages, tools=tools, cache=cache)


class TargetWithSystemMessages:
    """Petri's target loop (`inspect_petri/target/_agent.py`, prefill and caching left out), which also delivers a system message staged during the conversation, as the last message before the target generates. Petri's own loop reads the system message only at the start."""

    async def __call__(self, state: AgentState, context: TargetContext) -> AgentState:
        generate = context.replayable(get_model(role="target").generate, surface_errors=True)
        try:
            # the system and user message written by the auditor
            await context.wait_for_resume()
            state.messages[:] = [await context.system_message(), await context.user_message()]

            while True:
                # 1. the target generates its next step (ASSISTANT)
                state.output = await generate(input=state.messages, tools=context.tools)
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

                # 5. the only change to Petri's loop: the system message staged by the monitor (SYSTEM, the score of the step above). Claude models allow a system message in the middle of the conversation only after a user message or a tool result, and only if an assistant message follows, so here we add it last, right before the target generates again.
                if system_message := await context.system_message(required=False):
                    state.messages.append(system_message)
        except ExitSignal:
            return state
