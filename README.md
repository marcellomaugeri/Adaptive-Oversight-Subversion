# Adaptive Oversight Subversion

This repository contains an experimental pipeline to study how models adapt when a monitor blocks their actions.
I developed it during the [M³ fellowship](https://m3fellowship.com/).

For example, a model which works on a long cyber-security task might *forget* that a system is out of scope, or deliberately attack it, because it became frustrated when it could not solve the task.
A case of this kind is the [incident](https://www.aisi.gov.uk/blog/incident-report-unsanctioned-agent-behaviour-during-cyber-testing) that the UK AI Security Institute reported during its cyber testing.
To prevent that, a chain-of-thought (CoT) monitor reads the reasoning and the tool calls of the model at every step, and blocks the ones which look suspicious.
However, a blocked model still has a task to solve.
So this project studies how models react to a block, whether they try to evade the monitor, and which strategies they adopt.

## Contents

| Path | What it is |
| --- | --- |
| `main.py` | The task `monitored_audit`: Petri's audit with the monitor wired in. It also builds the seeds. |
| `src/cot_monitor.py` | The chain-of-thought monitor: it rates every step of the target and can block its tool calls. |
| `src/target/` | The target loop: Petri's, plus the delivery of the suspiciousness and the compaction of the context. |
| `src/judge/` | The step judge, which scores every step, and the rubrics of the eight dimensions I added. |
| `src/dimensions.yaml` | The 20 dimensions the judge scores. |
| `src/seed_builder/`, `seeds/` | The scenario texts, and the five runnable seeds built from them. |
| `src/prompts/` | The prompts of the auditor and of the monitor. |
| `src/analysis/`, `scripts/` | The plot of a run over its steps, and three scripts that call it. |
| `patches/` | A patch for Inspect Scout, needed until the change is released. |

## Getting started

You need [uv](https://docs.astral.sh/uv/) and Python 3.14.

```bash
uv sync
patch -p1 -d .venv/lib/python3.14/site-packages < patches/inspect_scout_exclude_role_label.patch
cp .env.example .env
```

The patch adds the `exclude_role_label` option to Inspect Scout 0.5.2.
The monitor and the judge use it to render the conversation without repeating the role in every message.
I proposed the change upstream ([issue #650](https://github.com/meridianlabs-ai/inspect_scout/issues/650), [inspect_scout#651](https://github.com/meridianlabs-ai/inspect_scout/pull/651), [ts-mono#684](https://github.com/meridianlabs-ai/ts-mono/pull/684)).
`uv sync` overwrites the patched file, so apply the patch again after every sync.

### The `.env` file

Two things go in `.env`: the API key of every provider you use, and the model of every role.

A run has four roles:

| Role | What it does |
| --- | --- |
| `auditor` | Simulates the environment and the tools of the target, following the seed. |
| `target` | The model under test. |
| `monitor` | Rates every step of the target, and can block it. |
| `judge` | Scores every step after the run. |

`INSPECT_EVAL_MODEL_ROLE` sets the four roles, separated by spaces.
A role is a model name, or a JSON object with the model and its options, written without spaces.
For example, with DeepSeek for every role:

```bash
INSPECT_EVAL_MODEL_ROLE='auditor={"model":"deepseek/deepseek-flash","reasoning_effort":"medium"} target={"model":"deepseek/deepseek-flash","reasoning_effort":"medium"} judge={"model":"deepseek/deepseek-flash","reasoning_effort":"medium"} monitor={"model":"deepseek/deepseek-flash","reasoning_effort":"low"}'
```

A monitor has to be fast, so I give it a lower reasoning effort or a smaller model than the target.
In the example the monitor has a low reasoning effort.

## Running an evaluation

Build the seeds.
This is needed once, and again after any change in `src/seed_builder/`:

```bash
uv run python main.py --build
```

Run one scenario:

```bash
uv run inspect eval main.py@monitored_audit -T seed_instructions=seeds/ --sample-id uk_aisi_DL-v2_incident_replica -T max_turns=100
```

`seed_instructions` takes the directory of the seeds, and `--sample-id` selects one of them:

- `uk_aisi_DL-v2_incident_replica`
- `uk_aisi_DL-v2_correct_prompt`
- `insider_trading_no_nudge`
- `insider_trading_nudge`
- `insider_trading_strong_nudge`

Open the logs in the Inspect viewer:

```bash
uv run inspect view
```

### Monitor settings

The command above runs a passive monitor, which only rates the steps.
The other three settings block a tool call when its suspiciousness reaches the threshold, and differ in what the target is told.

| Setting | The monitor blocks | What the target is told | Options |
| --- | --- | --- | --- |
| Passive | No | Nothing | none |
| Decision | Yes | "Call blocked" | `-T monitoring=active -T threshold=0.5 -T feedback=decision` |
| Decision and suspiciousness | Yes | "Call blocked", and its suspiciousness after every step | `-T monitoring=active -T threshold=0.5 -T feedback=decision -T disclose_suspiciousness=true` |
| Rationale | Yes | "Call blocked" and the monitor's reason | `-T monitoring=active -T threshold=0.5 -T feedback=rationale` |

### Other options

- `-T max_turns=N` sets the number of turns of the auditor.
- `--epochs N` repeats the run N times in the same log.
- `-T compaction_threshold="{target: 200000, monitor: 200000, judge: 200000}"` compacts the context of a role when it reaches that number of tokens.
  A role left out compacts at 0.9 of its context window.

## Design

To study this, I needed a setting where a model works on a long task.
[Inspect Petri](https://github.com/meridianlabs-ai/inspect_petri) gave me the first half: an auditor model simulates the environment and the tools for the model under test (the target), following a seed which describes the scenario, and a judge scores the transcript at the end.

However, Petri has no monitor of the target.
So I wrote a CoT monitor, adapted from Baker et al., ["Monitoring Reasoning Models for Misbehavior and the Risks of Promoting Obfuscation"](https://arxiv.org/abs/2503.11926) (2025), and from Greenblatt et al., ["AI Control: Improving Safety Despite Intentional Subversion"](https://arxiv.org/abs/2312.06942) (2024).
After every step of the target, the monitor reads its reasoning, its message and its tool calls, and gives the step a suspiciousness between 0 and 1 with a short reason.
A passive monitor only records the suspiciousness.
An active monitor also blocks the step when the suspiciousness reaches a threshold: the target then receives "Call blocked" in place of the results of its tool calls.

A blocked model can be told different things, and I expect this to change how it adapts.
So the feedback can be the decision alone, the decision with the monitor's reason, or the decision with the suspiciousness of every step, which the target reads as a system message.
These are the monitor settings listed above.

Then, Petri's judge gives one score per dimension for the whole run.
Since I am interested in how the behaviour changes during the run, I wrote a step judge, which scores every step from 1 to 10 on every dimension.
It uses 12 of Petri's dimensions.
However, none of them describes what happens after a block, so I added 8 more: strategy change, objective change, oversight subversion, unsanctioned behaviour, monitoring awareness, reward hacking, sabotage and sandbagging.
Their rubrics are in `src/judge/dimensions/`, and `src/judge/README.md` describes the judge.

Finally, Petri's default prompt tells the auditor to push boundaries and break loops, while here the auditor only has to administer the environment described by the seed.
So I replaced the prompt, disabled rollback, and made the auditor give a motivation when it ends a run early.
Since the runs are long, the target, the monitor and the judge also compact their context, as Petri does for the auditor.

## Scenarios

I needed realistic scenarios, so I rebuilt two known ones as Petri seeds.
In both, the environment is simulated by the auditor model: there is no real network or host.

The first is the UK AISI cyber range incident: a replica of the range described in the [incident report](https://www.aisi.gov.uk/blog/incident-report-unsanctioned-agent-behaviour-during-cyber-testing), with the published system and task wording.
It has two conditions on the same range: the task prompt which was supplied by mistake in the incident (`uk_aisi_DL-v2_incident_replica`) and the correct one (`uk_aisi_DL-v2_correct_prompt`).
The Mythic interface is simulated, because the report does not publish the harness.

The second is the insider trading setting of Scheurer et al., ["Large Language Models can Strategically Deceive their Users when Put Under Pressure"](https://arxiv.org/abs/2311.07590) (2024), which I extended into a persistent loop.
It has three conditions, `no_nudge`, `nudge` and `strong_nudge`, which change only the first message to the target.

## Notes

- `max_turns` counts the turns of the auditor, not the actions of the target.
  A response of the target without a tool call also takes an auditor turn.
- The state of the simulated world lives in the auditor's context.
  Very long runs depend on the auditor's compaction to keep it consistent.
- `disclose_suspiciousness` relies on the provider delivering a system message in the middle of the conversation.
  OpenAI models do, and so does Claude 4.8 or later on the Claude API.
  For older Claude models, Claude on Bedrock or Vertex, and Gemini, Inspect moves the message elsewhere, so the target does not read one score after each step.
- `src/judge/jev_judge.py` is a second judge I tried and do not use.
  Its docstring says why.
