# css_env

Deterministic OpenEnv benchmark for iterative CSS refinement.

## Motivation

Modern AI systems generate CSS that is syntactically valid but visually poor. This environment benchmarks whether an agent can fix structured design defects (tokens, spacing, typography, contrast, responsiveness, cleanup) through constrained semantic actions.

## Environment Loop

1. reset() loads task HTML + token spec + clean CSS.
2. Flaw injector programmatically injects realistic defects.
3. Agent receives observation: html, css, tokens, violations (easy only).
4. Agent sends structured action.
5. step(action) applies mutation, runs deterministic graders, computes reward.
6. Episode ends on success (all grader scores >= 0.95) or max steps.

No LLM-based grading is used.

## Data Contracts

### Observation

- html: string
- css: string
- tokens: dict
- violations: optional list[dict[str, str]] (easy task only)

### Action

- action_type: one of
  - replace_color
  - fix_spacing
  - fix_typography
  - fix_contrast
  - add_breakpoint
  - remove_rule
- target: string
- value: string or null

### Grader Signature

All graders implement:

- grade(html: str, css: str, tokens: dict, state: dict | None = None) -> float

All scores are clamped to [0.0, 1.0].

## Reward

Per-step dense reward:

- 0.30 * color
- 0.20 * spacing
- 0.20 * typography
- 0.20 * contrast
- 0.10 * cleanliness
- -0.05 penalty for no-op/unnecessary actions

Terminal bonus:

- +0.50 when episode is done and all grader scores >= 0.95

## Tasks

Defined in:

- tasks/task1.py
- tasks/task2.py
- tasks/task3.py

Each task declares:

- HTML fixture
- clean CSS baseline
- design tokens
- flaw config
- grader weights metadata
- max steps
- success threshold
- optional violations (easy task)

## Graders

- graders/colors.py
- graders/spacing.py
- graders/typography.py
- graders/contrast.py
- graders/layout.py
- graders/cleanliness.py
- graders/design_quality.py

Unit tests:

- scripts/test_graders_unit.py

Verification harness:

- scripts/tasks_and_verification.py

## Run Locally

Create environment and install:

```bash
python -m venv .venv
. .venv/bin/activate
pip install .
```

Run server:

```bash
uvicorn server.app:app --host 0.0.0.0 --port 8000 --reload
```

Run verification:

```bash
python scripts/tasks_and_verification.py
python scripts/test_graders_unit.py
```

## Docker

Root Dockerfile is validator-compatible.

```bash
docker build -t css_env-env:latest .
docker run --rm -p 8000:8000 css_env-env:latest
```

## Inference Script Requirements

Submission script is:

- inference.py (root)

Required environment variables:

- API_BASE_URL
- MODEL_NAME
- HF_TOKEN

LLM calls use OpenAI Client with those variables.

The script prints strict structured logs:

- [START]
- [STEP]
- [END]

Example run:

```bash
API_BASE_URL=https://api.openai.com/v1 MODEL_NAME=gpt-4o-mini HF_TOKEN=... python inference.py
```

## HF Space and Validation

OpenEnv manifest:

- openenv.yaml

Run pre-validation before submission:

```bash
bash scripts/validate-submission.sh https://your-space.hf.space .
```

Validation checks:

1. Space responds to POST /reset with HTTP 200
2. Docker build succeeds
3. openenv validate passes
