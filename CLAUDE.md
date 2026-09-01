# dev-hub / product workflow

> **Hub:** tooling в `/home/aero/PyProject/dev-hub`. **Продукт:** `PROJECT_ROOT` — код + `memory-bank/`. Cursor: открывай папку продукта. Loop: `dev-hub/bin/loop $PROJECT_ROOT …`
>
> **Anti-mix (HARD):** product-артефакты только в `$PROJECT_ROOT/memory-bank`. Hub-эпики `T-HUB-*` — в `dev-hub/memory-bank` при `PROJECT_ROOT=dev-hub`. CLI: `epic_resolve.py --cwd "$PROJECT_ROOT" …`

**Cursor, Claude Code, Codex — один workflow.** Канон: `.cursor/rules/` + `memory-bank/`.

| Layer | File |
|-------|------|
| Router | @.cursor/rules/mainrule.mdc |
| Economy stub (always) | @.cursor/rules/token-economy-stub.mdc |
| **Spec-first replace (always HARD)** | @.cursor/rules/spec-first-replace-hard.mdc |
| **Behavior-first / anti-dilution** | @.cursor/rules/shared/workflow-behavior-first.mdc |
| Economy full | @.cursor/rules/token-economy-core.mdc — **Read on role command**; PLAN/DECOMPOSE → §0.0 + §0.0.1 before write |
| Session / FINISH | @.cursor/rules/shared/context-session-economy.mdc · @.cursor/rules/shared/finish-block.mdc |
| PLAN artifact | @.claude/rules/plan-artifact.md |

## Parity (Claude Code)

1. `.claude/skills/role-command/SKILL.md` — цепочка **до** основной работы
2. graphify: @.cursor/rules/graphify.mdc + `.venv/bin/graphify` из корня репо
3. Только файлы из `.cursor/rules/` — не импровизировать процесс
4. Slash: `.claude/commands/` — PLAN → `/integ-plan` `/back-plan` `/front-plan`

## Stack

Python 3.12 · FastAPI · Next.js `frontend/` · `.venv/bin/pytest` · PostgreSQL 16 · Redis 7. Детали: `memory-bank/techContext.md`

## Conventions

Русский в чате · silent tools (@.cursor/rules/silent-tools.mdc) · spec-first replace HARD (@.cursor/rules/spec-first-replace-hard.mdc) · behavior-first (@.cursor/rules/shared/workflow-behavior-first.mdc) · `implement this` gate (§0.9) · FRONT tests parent-only (@.cursor/rules/front-tests-parent-only.mdc) · коммиты/PR по запросу · не править linter без запроса

PM, TL, CONTENT, MARKETING, SEO → `_archive/cursor-rules/`

@.cursor/rules/mainrule.mdc
