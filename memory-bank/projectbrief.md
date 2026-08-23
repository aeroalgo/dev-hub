# Project brief — dev-hub

## Продукт

Хаб разработки (tooling): Cursor/Claude workflow rules, skills, hooks, автоцикл `loop/`, линковка в продуктовые репозитории.

## Границы

**In scope (этот репозиторий):**
- `.cursor/rules`, `.cursor/templates` — команды ролей (BACK/FRONT/INTEG/…)
- `.claude/` — hooks, agents (`verify`/`reviewer`/`explorer`), settings, `project.env`
- `.agents/skills/` — общие skills
- `loop/` — context-first runner (`loop.sh`, `context_loop.py`, DAG)
- `bin/` — `loop`, `hub-link`, `hub-unlink`
- `make/product.mk` — Make-цели для продуктов
- `runtime/<slug>/` — runtime state loop **в хабе** (не product memory-bank)
- `loop/tests/` — тесты хаба

**Out of scope (не код этого репо):**
- Продуктовый application-код и product `memory-bank/` (живут в отдельных репозиториях)
- Содержимое прикреплённых продуктов при VAN хаба не инвентаризируется

## Runtime

- Python 3 + bash
- Loop: `bin/loop <PROJECT_ROOT> …` → cwd Claude = hub, продукт через `--add-dir`
- Cursor: plugin / `hub-link` / multi-root stub в `workspaces/` (файлы-заготовки; не source of truth архитектуры продукта)

## Цель VAN 2026-08-16

Первичная as-built карта **хаба** → `memory-bank/architecture/`.
