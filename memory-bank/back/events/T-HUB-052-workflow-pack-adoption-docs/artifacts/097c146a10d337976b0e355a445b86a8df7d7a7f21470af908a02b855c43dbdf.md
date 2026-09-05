# BACK BUGFIX — T-HUB-052-workflow-pack-adoption-docs — fix-test-flag-env-isolation

- **Дата:** 2026-09-05
- **Источник:** `memory-bank/back/qa/T-HUB-052-workflow-pack-adoption-docs/qa-20260905-workflow-pack-adoption-docs.yaml`, Issues ISS-001, ISS-002
- **Эпик:** `T-HUB-052-workflow-pack-adoption-docs`
- **Статус:** исправление подтверждено полным прогоном suite; 0 failures

## Симптом

QA зафиксировал blockers ISS-001 и ISS-002: при общем прогоне test suite падали тесты `loop/tests/test_workflow_pack_phase_router.py::test_tm_005_session_start_pack_inject` и `loop/tests/test_workflow_pack_registry.py::test_zero_regression_existing_smoke`.

## Root cause

В `loop/tests/test_workflow_pack_flag.py::test_workflow_pack_flag_sets_env` вызывался `main(["--cwd", ..., "prepare", "--workflow-pack", "video-production"])`, который мутировал глобальный словарь `os.environ["WORKFLOW_PACK"] = "video-production"`. Тест использовал `monkeypatch.delenv(...)` в начале, но не изолировал последующую прямую мутацию `os.environ` внутри `main`, из-за чего значение `WORKFLOW_PACK=video-production` протекало в последующие тесты, ломая резолв дефолтного пака `dev-hub-software`.

## Исправление

В `loop/tests/test_workflow_pack_flag.py::test_workflow_pack_flag_sets_env` применили `monkeypatch.setattr(os, "environ", os.environ.copy())`, гарантирующий автоматическое восстановление всего окружения `os.environ` после завершения теста без утечки переменных.

## Проверка исправления

- `bin/pytest loop/tests/test_workflow_pack_flag.py loop/tests/test_workflow_pack_phase_router.py loop/tests/test_workflow_pack_registry.py -q --tb=line` — 33 passed
- `bin/pytest -q --tb=line` — 1881 passed, 3 skipped, 75 warnings

## Delta

- `loop/tests/test_workflow_pack_flag.py`
- `memory-bank/back/bugfix/T-HUB-052-workflow-pack-adoption-docs/bugfix-20260905-fix-test-flag-env-isolation.md`

## Acceptance

- [x] AC+: Тест `test_workflow_pack_flag_sets_env` изолирован через monkeypatch и не загрязняет `os.environ`.
- [x] AC-: Отсутствуют падения `test_tm_005_session_start_pack_inject` и `test_zero_regression_existing_smoke` при последовательном запуске тестов.
- [x] §0.11: Полный pytest suite зелёный (1881 passed, 0 failures).

## Следующий шаг

Повторный `BACK QA` эпика T-HUB-052-workflow-pack-adoption-docs.
