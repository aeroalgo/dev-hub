# BACK BUGFIX — T-HUB-092-roadmap-cadence-foundation

- **Дата:** 2026-09-12
- **Источник:** `memory-bank/back/qa/T-HUB-092-roadmap-cadence-foundation/qa-20260912-roadmap-cadence-foundation.yaml`
- **Предмет:** Устранение silent fallback / optional bypass при загрузке cadence SoT в `mark_queue_epic_done` и `roadmap_advance`.

## Причина

В `loop/roadmap_queue.py` вызовы `on_feature_done`/`on_non_feature_done` и `load_cadence` были обёрнуты в проверку `if cad_file.is_file():`. При отсутствии файла `cadence.yaml` функции `mark_queue_epic_done` и `roadmap_advance` silently пропускали проверку cadence и продолжали выполнение в обход обязательного cadence gate, что нарушало требование fail-closed и контракт T-HUB-092 (запрет optional cadence).

## Исправление

- В `loop/roadmap_queue.py` удалена проверка `if cad_file.is_file():` из `mark_queue_epic_done`. Теперь `on_feature_done`/`on_non_feature_done` вызываются напрямую и при отсутствии/повреждении `cadence.yaml` завершаются fail-closed.
- В `loop/roadmap_queue.py` удалена проверка `if cad_file.is_file():` из `roadmap_advance`. Загрузка `load_cadence` выполняется напрямую и fail-closed.
- В `loop/tests/test_roadmap_queue.py` фикстура `_write_queue` дополнена созданием дефолтного `cadence.yaml` для тестовых сред.
- Добавлены регрессионные тесты `test_mark_queue_epic_done_missing_cadence_fail_closed` и `test_roadmap_advance_missing_cadence_fail_closed`.

## Проверка

- `bin/pytest loop/tests/test_roadmap_cadence.py loop/tests/test_roadmap_queue.py -q --tb=line` — PASS.
- `bin/pytest -q --tb=line` — 2853 passed, 4 skipped.

## Область изменений

- `loop/roadmap_queue.py`
- `loop/tests/test_roadmap_queue.py`
- `memory-bank/back/bugfix/T-HUB-092-roadmap-cadence-foundation/bugfix-queue.yaml`
- `memory-bank/back/bugfix/T-HUB-092-roadmap-cadence-foundation/bugfix-20260912-roadmap-cadence-foundation.md`
