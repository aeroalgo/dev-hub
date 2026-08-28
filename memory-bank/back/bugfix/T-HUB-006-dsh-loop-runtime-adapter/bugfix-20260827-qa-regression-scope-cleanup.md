# BACK BUGFIX — T-HUB-006-dsh-loop-runtime-adapter

- **Дата:** 2026-08-27
- **Источник:** `memory-bank/back/qa/T-HUB-006-dsh-loop-runtime-adapter/qa-20260827-dsh-loop-runtime-adapter.yaml`
- **Предмет:** регрессия общего loop lifecycle и scope leakage в diff DSH-эпика.

## Причина

QA обнаружил, что в рабочем diff одновременно присутствовали два независимых изменения:

1. `.claude/hooks/epic/core.py` менял checkpoint resume-контракт и блокировал committed checkpoint при несовпадении `step`, включая разрешённый переход `resume_policy=next_step`.
2. `sanitize_stale_armed_decompose` и его импорты/вызовы, а также `loop/tests/test_stale_arm_sanitize.py`, относились к отдельному stale-arm направлению и не имели покрытия T-HUB-006.

Из-за этого общий lifecycle suite был красным, а DSH-эпик содержал посторонний API и тест.

## Исправление

- Удалена дополнительная блокировка `step` для committed `resume_policy=next_step`; переход шага снова разрешён, тогда как committed `same_step` по-прежнему fail-closed.
- Удалены `sanitize_stale_armed_decompose` из `.claude/hooks/epic/core.py`, его facade-экспорты из `.claude/hooks/epic/__init__.py` и `.claude/hooks/epic_lib.py`, а также вызовы и импорт из `loop/context_loop.py`.
- Удалён несвязанный `loop/tests/test_stale_arm_sanitize.py`.

## Проверка

- `bash -n loop/loop.sh` — PASS.
- `env -u PROJECT_ROOT -u DEV_HUB -u HUB_ROOT -u CLAUDE_PROJECT_DIR -u EPIC_LOOP -u PROJECT_WORKFLOW_HOOKS timeout 300s .venv/bin/pytest loop/tests/test_dsh_runtime_adapter.py loop/tests/test_loop_dsh_dispatch.py loop/tests/test_checkpoint_next_step_advance.py loop/tests/test_identity_resolution.py -q --tb=line` — 34 passed.
- `env -u PROJECT_ROOT -u DEV_HUB -u HUB_ROOT -u CLAUDE_PROJECT_DIR -u EPIC_LOOP -u PROJECT_WORKFLOW_HOOKS timeout 300s .venv/bin/pytest loop/tests/ -q --tb=short` — 541 passed.

## Область изменений

Изменения в runtime config, DSH adapter, DSH dispatch и session resilience сохранены как предмет T-HUB-006. Stale-arm API и его тест удалены из этого эпика; дальнейшее stale-arm поведение остаётся за owning epic T-HUB-011.
