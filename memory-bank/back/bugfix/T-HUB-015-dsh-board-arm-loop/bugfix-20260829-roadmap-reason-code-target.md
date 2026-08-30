# BACK BUGFIX — T-HUB-015-dsh-board-arm-loop — roadmap-reason-code-target

- **Дата:** 2026-08-29
- **Источник:** `memory-bank/back/qa/T-HUB-015-dsh-board-arm-loop/qa-20260829-board-arm-loop.yaml`, Fix plan #1
- **Эпик:** `T-HUB-015-dsh-board-arm-loop`
- **Статус:** исправление подтверждено targeted, scoped и полным suite; требуется повторный BACK QA

## Свежая проверка

- `timeout 300s .venv/bin/pytest loop/tests/test_board_launch_arm.py -q --tb=line` — `9 passed in 3.53s`.
- `timeout 300s .venv/bin/pytest loop/tests/test_board_launch_*.py loop/tests/test_board_sync_*.py -q --tb=line` — `144 passed in 0.57s`.
- `timeout 300s .venv/bin/pytest -q --tb=line` — `7849 passed, 181 skipped, 48 warnings in 254.73s`.

## Симптом

QA подтвердил, что ROADMAP-карточка с `allowRoadmapAdvance=true`, включённым bridge и только `reason_code="needs_review"` проходила arm вместо отказа. Значение диагностической причины ошибочно использовалось как epic target.

## Root cause

`_explicit_roadmap_target()` в `loop/board_launch/arm.py` включал `reason_code` в список ключей, считающихся явной авторизацией цели ROADMAP. Поэтому `_has_explicit_epic()` принимал диагностическое поле за explicit epic metadata, а `arm_from_card()` передавал `needs_review` в `arm_session()`.

## Исправление

Из списка явных ROADMAP target keys удалён `reason_code`. Авторизацией остаются только `explicit_epic`, `epic_id` и `next_epic_id`; при отсутствии одного из них сохраняется `RoadmapAdvanceDeniedError` до вызова `arm_session()`.

Добавлен regression test `test_gate_roadmap_reason_code_is_not_explicit_target` в `loop/tests/test_board_launch_arm.py`: reason-code-only карточка при разрешённом config должна быть отклонена, а arm не вызывается.

## Проверка исправления

- `timeout 300s .venv/bin/pytest loop/tests/test_board_launch_arm.py -q --tb=line` — `9 passed`.

## Delta

- **Изменённые product/code-файлы:** `loop/board_launch/arm.py`, `loop/tests/test_board_launch_arm.py`.
- **Добавлен артефакт:** этот bugfix-документ.
- **Не изменено:** исходный QA artifact; его `fail` сохраняется как evidence дефекта до повторного BACK QA.

## Acceptance

- [x] `reason_code` больше не считается явной ROADMAP epic authorization.
- [x] reason-code-only ROADMAP card отклоняется до `arm_session()`.
- [x] Targeted regression test зелёный.
- [ ] Повторный BACK QA с scoped и полным suite.

## Следующий шаг

`BACK QA T-HUB-015-dsh-board-arm-loop` — повторить эпический QA после обновления code/test evidence. До QA pass переход к REFLECT запрещён.
