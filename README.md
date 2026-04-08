---
title: BitWise CSS Env
emoji: 🐠
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
short_description: Design System Alignment RL Environment
---

# BitWise CSS: Design System Alignment Environment

## Space Metadata Summary

| Field | Value |
| --- | --- |
| **SDK** | Docker |
| **Port** | 7860 |
| **Topic** | Design System Alignment RL |

## Overview
BitWise CSS is a Reinforcement Learning (RL) environment designed to fix a core problem in AI-assisted coding: **visually poor CSS**. While LLMs generate syntactically correct code, they often ignore design tokens, break accessibility, and create redundant rules.

This environment challenges agents to iteratively transform "flawed" CSS into code that perfectly aligns with a provided **Design Token Specification**. All grading is deterministic and based on mathematical compliance, not subjective LLM judgment.

---

## Architecture Summary
The environment follows a standard RL loop:
1. **`reset()`**: Loads an HTML fixture and Design Tokens. A **Flaw Injector** programmatically creates realistic CSS errors. Returns the initial **Observation**.
2. **`step(action)`**: The agent applies a **Structured Action** (e.g., `replace_color`, `fix_spacing`).
3. **Reward**: The environment computes a dense reward based on the delta of compliance scores across five categories: Color, Spacing, Typography, Contrast, and Cleanliness.
4. **Termination**: Ends when all scores exceed **0.95** or `max_steps` is reached.

---

## Tasks & Difficulty
| Task | Level | Focus | Difficulty Drivers |
| :--- | :--- | :--- | :--- |
| **Task 1** | **Easy** | Token Alignment | Explicit violation hints provided. |
| **Task 2** | **Medium** | Accessibility & Typography | Hints absent; requires diagnostic reasoning. |
| **Task 3** | **Hard** | Layout & Code Cleanup | Requires media query logic and pruning. |

---

## Data Models

### Observation
- **HTML**: Component structure (string).
- **CSS**: Current stylesheet (string).
- **Design Tokens**: Allowed colors, spacing grid (4px/8px), font-scale, and breakpoints.
- **Violations**: Explicit list of errors (Easy task only).

### Action (Structured Edits)
*Raw CSS string editing is prohibited.* Agents must use:
- `replace_color`: Target selector/property to match tokens.
- `fix_spacing`: Snap values to the 4px/8px grid.
- `fix_typography`: Align font-size/line-height to type scales.
- `fix_contrast`: Adjust foreground/background pairs for WCAG AA.
- `add_breakpoint`: Inject media queries with fluid layout rules.
- `remove_rule`: Clean up unused selectors.

### Reward Function
Dense rewards are computed as a weighted sum:
$$Reward = 0.30(Color) + 0.20(Spacing) + 0.20(Typography) + 0.20(Contrast) + 0.10(Clean)$$
- **Penalty**: $-0.05$ for unnecessary or no-op actions.
- **Bonus**: $+0.50$ for reaching the $0.95$ success threshold.

---

## Quick Start for Testing
```bash
# Set required variables
export ENV_BASE_URL="[https://ar-srivas-bitwise-css-env.hf.space](https://ar-srivas-bitwise-css-env.hf.space)"
export API_BASE_URL="[https://router.huggingface.co/v1](https://router.huggingface.co/v1)"
export MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"
export HF_TOKEN="your_token_here"

# Run smoke tests
curl -i $ENV_BASE_URL/health
curl -i -X POST $ENV_BASE_URL/reset -H "Content-Type: application/json" -d '{}'

# Run baseline inference
python inference.py