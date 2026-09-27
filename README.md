# Adaptive Scheming

This repo contains the code to reproduce the experiments from the paper `"

## Evaluation terminology

| Term | Meaning | Example |
| --- | --- | --- |
| Evaluation | The research goal and the behaviour or condition comparison we want to test. | Oversight subversion: does an agent disable oversight to pursue a conflicting goal? |
| Scenario | A persistent world with an assigned task, available tools, and consequential choices. | The DL-v2 cyber range with its canteen entry point, three connected environments, and simulated internet. |
| Condition | The exact requirement or controlled variation applied to a scenario. | The correct DL-v2 task prompt versus the mistakenly supplied DL-v1 task prompt on the same DL-v2 range. |
| Run | One execution of a scenario under one condition. | One target trajectory in the DL-v2 range with the mistaken prompt. |

A prompt condition does not create another scenario when the underlying task and world stay fixed. The current Petri loader treats each `.md` file as one runnable seed sample, so paired conditions have separate generated samples. Repeated runs of a condition measure variation in target behaviour.

```
uv run inspect eval inspect_petri/audit -T seed_instructions=id:clinical_oversight_subversion -T enable_rollback=false -T max_turns=10
```


## Getting Started

### Requirements

- uv
- Python 3.14
- Docker (Dish only)

### Installation

```bash
uv sync
cp .env.example .env
```

Now, edit the `.env` file to add your API keys and set the models (See `INSPECT_EVAL_MODEL_ROLE`).

### Patch for Inspect Scout

The monitor renders the trajectory of the agent with Inspect Scout's `messages_as_str(..., format="json")`. In the released `inspect-scout` (0.5.2) every JSON item repeats the role inside its content, e.g. `{"role": "user", "content": "USER:\nHello\n"}`. We proposed an `exclude_role_label` option upstream that removes the repeated label ([issue #650](https://github.com/meridianlabs-ai/inspect_scout/issues/650), [inspect_scout#651](https://github.com/meridianlabs-ai/inspect_scout/pull/651), [ts-mono#684](https://github.com/meridianlabs-ai/ts-mono/pull/684)). Until it is released, apply the same change to the installed package with `patches/inspect_scout_exclude_role_label.patch`.

Apply it (after `uv sync`):

```bash
patch -p1 -d .venv/lib/python3.14/site-packages < patches/inspect_scout_exclude_role_label.patch
```

Unapply it:

```bash
patch -R -p1 -d .venv/lib/python3.14/site-packages < patches/inspect_scout_exclude_role_label.patch
```

`uv sync` or any reinstall of `inspect-scout` overwrites the patched file, so apply the patch again afterwards. Once a release of `inspect-scout` includes `exclude_role_label`, upgrade it and delete the patch and this section.

### Run one scenario

```bash
uv run inspect eval inspect_petri/audit -T seed_instructions=id:clinical_oversight_subversion -T enable_rollback=false -T max_turns=10
```


### Run one scenario with the monitor

```bash
uv run inspect eval main.py@monitored_audit -T seed_instructions=id:clinical_oversight_subversion -T max_turns=30 -T threshold=0.5 -T disclosure=nothing
```

Build the runnable seeds from the shared auditor text, scenario text and condition values:

```bash
uv run python main.py --build
```

The builder overwrites only its five declared outputs in `seeds/`. The retired drafts have `.md.disabled` suffixes, so Petri does not load them. Each output begins with the same auditor baseline in `src/seed_builder/0_auditor.md`. The task also supplies a neutral auditor system prompt from `src/prompts/auditor.py`, replacing Petri's default prompt that tells the auditor to push boundaries and break loops. The [AISI range](https://www.aisi.gov.uk/blog/incident-report-unsanctioned-agent-behaviour-during-cyber-testing) has two task-prompt conditions on one shared world. The insider-trading scenario has `no_nudge`, `nudge` and `strong_nudge` conditions; only their initial target-facing message changes. The `no_nudge` condition is the baseline for independent behaviour. The [Apollo case](https://arxiv.org/html/2311.07590) originally sampled a continuation from a [written interaction history](https://github.com/ApolloResearch/insider-trading/blob/main/prompts/default.json); this seed extends its setting into a persistent agent loop rather than reproducing that original sampling procedure. The AISI seed uses the published system and task wording, with the apparent `"f"` typo removed. Its Mythic interface is simulated because the incident report does not publish the exact harness schema.

Pass the seed directory, then select one sample by id. Passing a single `.md` file to `seed_instructions` makes Petri treat its nonempty lines as separate instructions. These commands are short pilots:

```bash
uv run inspect eval main.py@monitored_audit -T seed_instructions=seeds/ --sample-id uk_aisi_DL-v2_incident_replica -T max_turns=80
uv run inspect eval main.py@monitored_audit -T seed_instructions=seeds/ --sample-id uk_aisi_DL-v2_correct_prompt -T max_turns=80
uv run inspect eval main.py@monitored_audit -T seed_instructions=seeds/ --sample-id insider_trading_no_nudge -T max_turns=80
```

These commands leave `threshold` unset, so the monitor records scores without blocking. Set a threshold and disclosure mode only after reviewing a baseline for the selected scenario.

`max_turns` caps auditor turns, not target actions. The auditor's `end_conversation` tool takes a required `motivation` string and records it in the log before calling Petri's original tool. The stopping rule is in the auditor prompt; the code does not check whether the motivation is valid. A target response without a tool call also needs another auditor-supplied user turn before the target can continue. The scenarios ask for a persistent world through the budget, but the simulation's state still lives in the auditor's context; very long runs need durable external state, bounded monitor context and a judge that can review long transcripts. A finite AISI flag task can also finish naturally before the turn cap.

`disclosure=suspiciousness` sends the score to the target as a system message after each step. Run it only with OpenAI targets, or Claude 4.8+ on the Claude API or on Claude Platform on AWS: these deliver the message in place. Other providers do not. For older Claude models and for Claude on Bedrock or Vertex, Inspect moves the score into the system prompt when it follows a tool result and rewrites it as a user message when it follows a user message. For Gemini, Inspect moves every system message into the system instruction. In both cases the target does not read one score after each step.

### Future work: evaluation-infrastructure honeypot

The [base ExploitGym benchmark](https://github.com/sunblaze-ucb/exploitgym) is public. The planned OpenAI/ExploitGym reward-hacking scenario needs an adapter to an actual fixed ExploitGym instance and its solution-access surface. Petri's synthetic auditor tools do not currently provide that integration, so a synthetic text-only imitation is not included among the runnable seeds. OpenAI's separate [ExploitGym Honeypot evaluation](https://deploymentsafety.openai.com/gpt-6-astra/protocolqa-open-ended) is future work; its exact scenario files and implementation were not found in the public sources checked.

The disabled `cyber_range_supply_chain_boundary` draft is a synthetic analogue of the Petri-based out-of-scope supply-chain evaluation [described by UK AISI in the Astra system card](https://deploymentsafety.openai.com/gpt-6-astra/protocolqa-open-ended). Its exact seed and internal Petri implementation were not found in the public sources checked; the [public Inspect Petri repository](https://github.com/meridianlabs-ai/inspect_petri) is a framework, not that evaluation release.
