# Decompose Formulas

Reusable decompose formulas (`decompose-formula/v1`) for loop planner and epic generation.

## Available Formulas

| ID | Title / Description | When to use | Exemplar Epic |
|---|---|---|---|
| `hooks-epic` | Formula for hooks and LLM fallbacks | For creating or modifying `.claude/hooks` logic, fallbacks, and prompt inventories | T-HUB-023 |
| `loop-runtime-epic` | Formula for loop runtime lifecycle changes | For core `loop/` runtime engine, state management, or component wiring | T-HUB-017 |
| `cli-validate-epic` | Formula for CLI validation & audit tools | For CLI utilities, schema checkers, and traceability verification scripts | T-HUB-024 |

## How to Use

Render a formula draft into a decompose plan:
```bash
python -m loop.cli.formula_render --formula hooks-epic --epic T-HUB-XXX
```
