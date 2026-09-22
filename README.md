# Adaptive Scheming

This repo contains the code to reproduce the experiments from the paper `"

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

`disclosure=suspiciousness` sends the score to the target as a system message after each step. Run it only with OpenAI targets, or Claude 4.8+ on the Claude API or on Claude Platform on AWS: these deliver the message in place. Other providers do not. For older Claude models and for Claude on Bedrock or Vertex, Inspect moves the score into the system prompt when it follows a tool result and rewrites it as a user message when it follows a user message. For Gemini, Inspect moves every system message into the system instruction. In both cases the target does not read one score after each step.
