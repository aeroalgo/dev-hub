# BACK BUGFIX — T-HUB-102-agents-instruction-corpus — roadmap-queue-parses-finished-state

- **Дата:** 2026-09-16
- **Источник:** `memory-bank/back/qa/T-HUB-102-agents-instruction-corpus/qa-20260916-agents-instruction-corpus.yaml`, Item `BF-001`
- **Эпик:** `T-HUB-102-agents-instruction-corpus`
- **Статус:** исправление подтверждено полным прогоном suite; 0 failures

## Симптом

QA зафиксировал blocker `BF-001`: `loop/tests/test_roadmap_queue.py::test_repo_roadmap_queue_parses` падал с ошибкой `assert len(out['queue']) >= 1 failed (0 >= 1)` из-за того, что все запланированные эпики дорожной карты в `memory-bank/back/roadmap/queue.yaml` были завершены (`queue: []`, элементы в `done:`).

## Root cause

Тест `test_repo_roadmap_queue_parses` жестко требовал непустой список `queue:`, что не учитывало валидное терминальное состояние дорожной карты (`queue: []`, `done: [...]`).

## Исправление

В `loop/tests/test_roadmap_queue.py::test_repo_roadmap_queue_parses` скорректировано утверждение: проверяется, что `out["queue"]` является списком с валидными `id` и `plan` для всех записей (если они есть), а также наличие завершенных записей `assert len(out["done"]) >= 1`.

## Проверка исправления

- Targeted: `bin/pytest loop/tests/test_roadmap_queue.py -o addopts="-v"` — 50 passed
- Full suite: `bin/pytest -q --tb=line` — 2955 passed, 4 skipped in 130.34s

## Delta

- `loop/tests/test_roadmap_queue.py`
- `memory-bank/back/bugfix/T-HUB-102-agents-instruction-corpus/bugfix-queue.yaml`
- `memory-bank/back/bugfix/T-HUB-102-agents-instruction-corpus/bugfix-20260916-roadmap-queue-parses-finished-state.md`

## Acceptance

- [x] AC+: `test_repo_roadmap_queue_parses` корректно валидирует парсинг `memory-bank/back/roadmap/queue.yaml` в состоянии, когда активная очередь пуста, а все эпики перемещены в `done`.
- [x] AC-: Отсутствуют регрессии в `loop/tests/test_roadmap_queue.py`.
- [x] §0.11: Полный pytest suite зелёный (2955 passed, 4 skipped, 0 failures).

## Следующий шаг

Повторный `BACK QA` эпика T-HUB-102-agents-instruction-corpus.
