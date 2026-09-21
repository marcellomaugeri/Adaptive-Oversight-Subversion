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

### Run one scenario

```bash
uv run inspect eval inspect_petri/audit -T seed_instructions=id:clinical_oversight_subversion -T enable_rollback=false -T max_turns=10
```

