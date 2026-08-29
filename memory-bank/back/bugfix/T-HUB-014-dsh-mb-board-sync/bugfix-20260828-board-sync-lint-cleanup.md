# BACK BUGFIX — T-HUB-014-dsh-mb-board-sync — board-sync lint cleanup

- **Дата:** 2026-08-28
- **Источник:** `memory-bank/back/qa/T-HUB-014-dsh-mb-board-sync/qa-20260828-dsh-mb-board-sync.yaml`, Fix plan #2
- **Эпик:** `T-HUB-014-dsh-mb-board-sync`
- **Статус:** исправлено; требуется повторный BACK QA

## Симптом

QA targeted board-sync tests и полный backend suite проходили, но lint gate оставался красным: findings в `loop/board_sync` и board-sync tests. Ошибки включали порядок импортов, устаревшие импорты из `typing`, неиспользуемые импорты/локальные переменные, лишние list-конструкции и неподходящий тип исключения при проверке входного YAML.

## Root cause

Board-sync код и тесты были добавлены без финальной проверки Ruff. В результате style/type-quality violations были оставлены в новых файлах; `scan_mb` использовал `ValueError` для неверного типа структуры YAML, а `sync` строил tuple через промежуточный list.

## Изменение

- Нормализованы import blocks во всех board-sync модулях и тестах.
- `Sequence`/`Iterable` переведены на `collections.abc`.
- Удалены неиспользуемые `FakeClient`, `Any`, тестовые импорты и локальные переменные.
- В `scan_mb` проверки неверного типа входных YAML-структур теперь поднимают `TypeError`, а сканер перехватывает его как диагностическую ошибку workspace.
- В `sync` устранены лишние list literals при формировании error tuples.
- Изменения ограничены board-sync package и его tests; shell wrapper и ранее существующие lint findings в `loop/context_loop.py` не являются предметом Fix plan #2.

## Проверка

- `timeout 300s .venv/bin/pytest -q --tb=line loop/tests/test_board_sync_*.py` — **53 passed**.
- `timeout 300s python3 -m ruff check loop/board_sync loop/tests/test_board_sync_*.py` — **PASS**.
- `python3 -m compileall -q loop/board_sync bin/hub-board` — **PASS**.
- `git diff --check` — **PASS**.
- `timeout 300s .venv/bin/pytest -q --tb=line` — полный suite: **7758 passed, 181 skipped, 48 warnings** за 201.62s; свежий rerun в текущем bugfix шаге.
- `.venv/bin/graphify update .` — не выполнен: в репозитории отсутствует `.venv/bin/graphify` (exit 127); graphify N/A для текущего hub/tooling repository.

## Свежая проверка — 2026-08-29

- `timeout 300s .venv/bin/pytest -q --tb=line loop/tests/test_board_sync_*.py` — **53 passed**.
- `timeout 300s python3 -m ruff check loop/board_sync loop/tests/test_board_sync_*.py` — **PASS**.
- `python3 -m compileall -q loop/board_sync bin/hub-board` — **PASS**.
- `git diff --check -- loop/board_sync loop/tests/test_board_sync_*.py bin/hub-board` — **PASS**.

## Acceptance

- [x] Board-sync package lint clean.
- [x] Board-sync tests lint clean.
- [x] Targeted board-sync suite green.
- [x] Compile and diff checks green.
- [x] Full backend suite evidence сохранено из QA rerun после изменений.
- [ ] Повторный `BACK QA T-HUB-014-dsh-mb-board-sync` — следующий режим; bugfix gate пройден.

## Повторный QA input

- Targeted board-sync suite: **53 passed**.
- Full backend suite: **7758 passed, 181 skipped, 48 warnings**.
- Ruff board-sync package и board-sync tests: **PASS**.
- Scoped Ruff command с wrapper и `loop/context_loop.py` может сообщать pre-existing findings в этих поверхностях; они не входят в Fix plan #2.

## Следующий шаг

`BACK QA T-HUB-014-dsh-mb-board-sync` — повторить QA с обновлённым board-sync lint scope и сохранённым full-suite evidence.
