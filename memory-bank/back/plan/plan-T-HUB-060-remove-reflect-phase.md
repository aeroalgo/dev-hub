# T-HUB-060 — Remove REFLECT Phase

**Epic ID:** T-HUB-060-remove-reflect-phase  
**Level:** L3  
**Role:** BACK  
**Date:** 2026-09-03  
**Skills:** python-testing-patterns

---

## Goal

Убрать фазу REFLECT полностью из workflow и из loop. После успешного QA эпик должен переходить в DONE и запускать следующий эпик из очереди — без промежуточного шага reflection.

---

## WHAT (аксиомы)

- `IMPLEMENT → AUDIT → QA → DONE` — новая цепочка (REFLECT вырезан).
- После `qa_pass` lifecycle-фаза = `DONE` без требования `reflection_done`.
- `epic_complete_allowed()` возвращает `allowed=True` при наличии QA pass (без проверки reflection).
- `POST_IMPLEMENT_CHAIN` = `"IMPLEMENT → AUDIT → QA → EPIC_DONE"`.
- `LOOP_PHASE_MODEL_ENV` не содержит ключ `"REFLECT"`.
- `_LOOP_PHASE_DETECT_ORDER` не содержит `"REFLECT"`.
- `phase_registry.yaml` не содержит REFLECT в terminal_phases.
- `schemas/active_context.py` не ссылается на REFLECT в regex.
- `schemas/event.py` не содержит `"reflection_done"` в EVENT_KINDS.
- `_declared_artifacts()` в core.py не собирает `reflection_done` события.
- `reduce_epic_lifecycle()` не эмитит phase=REFLECT, переходит напрямую qa_pass → DONE.
- cursor rules (back/front/integ mainrule-core, mainrule, workflow-reflect) — REFLECT убран из цепочки переходов.
- Тесты, проверявшие REFLECT-поведение — переписаны под новую цепочку (DONE после qa_pass).
- Артефакты `reflection-*.md` в `memory-bank/*/reflection/` — **не удаляются** (архивные), но больше не требуются для gate.

---

## AC+ (pass)

1. `post_implement_phase()` при qa_pass возвращает `("DONE", qa_path, None)` — без reflection_path проверки.
2. `epic_complete_allowed()` при qa_pass возвращает `{"allowed": True}`.
3. `loop_phase_key("REFLECT")` возвращает `None` (ключ не в dict).
4. `bin/pytest loop/tests/` — все тесты зелёные (в т.ч. переписанные под новую логику).
5. Cursor rules не содержат `BACK REFLECT → ARCHIVE` в цепочке переходов.
6. `POST_IMPLEMENT_CHAIN == "IMPLEMENT → AUDIT → QA → EPIC_DONE"`.

## AC− (fail)

1. Любой код-путь, возвращающий phase="REFLECT" при qa_pass — FAIL.
2. `epic_complete_allowed()` возвращает `allowed=False` ссылаясь на отсутствие reflection — FAIL.
3. Тест ожидает `reflection_done` event или `phase=REFLECT` — FAIL.
4. `"REFLECT"` в `LOOP_PHASE_MODEL_ENV` или `_LOOP_PHASE_DETECT_ORDER` — FAIL.
5. Промпт loop содержит текст вида «QA pass + REFLECT» как gate к DONE — FAIL.

---

## Architecture

### Затронутые файлы

| Файл | Что меняется |
|------|-------------|
| `harness/hooks/epic/core.py` | `reduce_epic_lifecycle`: убрать ветки `phase=REFLECT`; qa_pass → DONE напрямую. `_declared_artifacts`: убрать сбор `reflection_done`. `post_implement_phase`: убрать `phase==REFLECT` ветку. `epic_complete_allowed`: убрать REFLECT из `handoff_phase` guard. `POST_IMPLEMENT_CHAIN`. `_POST_IMPLEMENT_NEED`. `post_implement_phase_need`. Фразы в ошибках. |
| `loop/context_loop.py` | `LOOP_PHASE_MODEL_ENV`: убрать `"REFLECT"`. `_LOOP_PHASE_DETECT_ORDER`: убрать `"REFLECT"`. `_epic_done_stop_result`: убрать упоминание REFLECT. `_reflect_finish_block`: удалить функцию. Ветка `phase_kind == "reflect"` → убрать. `_POST_IMPLEMENT_PHASES`: убрать `"REFLECT"`. Все промпт-строки «QA pass + REFLECT» → «QA pass». |
| `loop/schemas/event.py` | Убрать `"reflection_done"` из EVENT_KINDS. |
| `loop/schemas/active_context.py` | Убрать REFLECT из regex и frozenset. |
| `loop/schemas/phase_registry.yaml` | Убрать `REFLECT` из terminal_phases и блок `REFLECT:`. |
| `loop/roadmap_queue.py` | Убрать `reflection_path` из smart_entry; убрать поиск reflection-*.md. |
| `loop/epic_transition.py` | Убрать `"REFLECT"` из `_POST_IMPLEMENT_ARMED`. |
| **Cursor rules** | `back_developer/mainrule-core.mdc`: убрать REFLECT из transitions. Аналогично front/integ. `back_developer/mainrule.mdc`, `front_developer/mainrule.mdc`, `integ/.../mainrule.mdc`: убрать row `BACK REFLECT`. Workflow-reflect files: оставить (не удалять — архив), но не линковать из mainrule. |
| **Тесты** | `loop/tests/test_handoff_phase_gates.py`: переписать тесты REFLECT → ожидать DONE. `loop/tests/test_epic_transition.py`: убрать REFLECT из terminal_phases assert. `loop/tests/test_epic_lib.py` (если есть): обновить. Другие тесты — удалить/переписать REFLECT assertions. |

### Логика reduce_epic_lifecycle (новая)

```
qa_pass (latest) → phase=DONE  (было: → phase=REFLECT, потом reflection_done → DONE)
```

Конкретно в `reduce_epic_lifecycle` (~line 3480–3519):
- Блок `if last_reflection is not None:` — удалить целиком (reflection-check).
- `reason_code = "qa_passed"` → напрямую `phase = "DONE"`.
- Убрать все ветки `reason_code in {"qa_passed_stale_reflection", "reflection_completed"}`.

---

## Decompose plan (шаги)

| sNN | Название | Файлы |
|-----|----------|-------|
| s01 | core.py — убрать REFLECT из lifecycle reducer и artifacts | `harness/hooks/epic/core.py` |
| s02 | core.py — убрать REFLECT из epic_complete_allowed и phase_need | `harness/hooks/epic/core.py` |
| s03 | context_loop.py — убрать REFLECT из phase model, prompts, finish block | `loop/context_loop.py` |
| s04 | schemas + epic_transition — убрать REFLECT из event/registry/active_context | `loop/schemas/event.py`, `loop/schemas/active_context.py`, `loop/schemas/phase_registry.yaml`, `loop/epic_transition.py`, `loop/roadmap_queue.py` |
| s05 | Тесты — переписать/удалить REFLECT assertions | `loop/tests/test_handoff_phase_gates.py`, `loop/tests/test_epic_transition.py`, другие |
| s06 | Cursor rules — убрать REFLECT из mainrule-core и mainrule (BACK/FRONT/INTEG) | `.cursor/rules/back_developer/mainrule-core.mdc`, `.cursor/rules/back_developer/mainrule.mdc`, `.cursor/rules/front_developer/mainrule-core.mdc` (аналог), `.cursor/rules/integration_developer/mainrule.mdc` (аналог) |

---

## Independent Tests (наблюдаемое поведение)

1. `bin/pytest loop/tests/test_handoff_phase_gates.py -k "reflect or done"` → тесты зелёные без REFLECT.
2. `bin/pytest loop/tests/test_epic_transition.py` → `"REFLECT"` не в `terminal_phases`.
3. `bin/pytest loop/tests/ -q --tb=short` → suite green.
4. `python -c "from loop.context_loop import LOOP_PHASE_MODEL_ENV; assert 'REFLECT' not in LOOP_PHASE_MODEL_ENV"` → exit 0.
5. `python -c "from harness.hooks.epic.core import POST_IMPLEMENT_CHAIN; assert 'REFLECT' not in POST_IMPLEMENT_CHAIN"` → exit 0.

---

## Risks

- `reflection_done` events в существующих event.log (архивные эпики) — reducer должен **игнорировать** (не краш, не влиять на phase) → при чтении event.log старые `reflection_done` events просто не меняют phase (убираем ветку их обработки, они остаются как dead events).
- Тесты, опирающиеся на `phase=REFLECT` fixture — придётся переписать под `phase=DONE`.
- `handoff_phase == "REFLECT"` в activeContext существующих эпиков → `handoff_post_implement_phase()` вернёт "REFLECT", но `epic_complete_allowed` должен обрабатывать это как не-блокирующее (или игнорировать). **Решение:** в `epic_complete_allowed` убрать REFLECT из guard-set — если Handoff содержит REFLECT, это уже устаревший формат, рассматривать как "можем проверить через lifecycle".

---

## Review readiness

| Item | Status |
|------|--------|
| Scope ясен | Required — OK |
| Independent Tests определены | Required — OK |
| REFLECT в архивных event.log — обработка | Required — OK (игнорируем как dead events) |
| Sunset inventory (что удаляем vs архивируем) | Required — OK: workflow-reflect.mdc оставляем как архив, не линкуем; reflection-*.md артефакты не удаляем |
| Cursor rules scope | Required — OK: только mainrule-core + mainrule таблицы; workflow-reflect.mdc не трогаем |
