# Decompose Index — T-HUB-060-remove-reflect-phase

**plan_id:** T-HUB-060-remove-reflect-phase  
**Epic:** Remove REFLECT Phase  
**Level:** L3  
**Role:** BACK  
**Status canon:** `yaml/decompose-index.yaml`

---

## Requirements coverage

| ID | Requirement | Covered by | Measurable verify |
|----|-------------|------------|-------------------|
| AC+1 | `post_implement_phase()` при qa_pass → `("DONE", qa_path, None)` без reflection_path | s01 | `bin/pytest loop/tests/test_handoff_phase_gates.py -k done -q` |
| AC+2 | `epic_complete_allowed()` при qa_pass → `{"allowed": True}` | s01 | `bin/pytest loop/tests/test_handoff_phase_gates.py -k allowed -q` |
| AC+3 | `loop_phase_key("REFLECT")` → `None` | s02 | `python -c "from loop.context_loop import LOOP_PHASE_MODEL_ENV; assert 'REFLECT' not in LOOP_PHASE_MODEL_ENV"` |
| AC+4 | `bin/pytest loop/tests/` все тесты зелёные | s05 | `bin/pytest loop/tests/ -q --tb=short` |
| AC+5 | Cursor rules не содержат `BACK REFLECT → ARCHIVE` | s04 | `rg "BACK REFLECT" .cursor/rules/` (0 hits) |
| AC+6 | `POST_IMPLEMENT_CHAIN == "IMPLEMENT → AUDIT → QA → EPIC_DONE"` | s01 | `python -c "from harness.hooks.epic.core import POST_IMPLEMENT_CHAIN; assert 'REFLECT' not in POST_IMPLEMENT_CHAIN"` |
| AC−1 | Никакой код-путь не возвращает phase="REFLECT" при qa_pass | s01 | `bin/pytest loop/tests/test_handoff_phase_gates.py -q` |
| AC−2 | `epic_complete_allowed()` не возвращает allowed=False из-за REFLECT | s01 | `bin/pytest loop/tests/test_handoff_phase_gates.py -q` |
| AC−3 | Тест не ожидает `reflection_done` event или `phase=REFLECT` | s03 | `bin/pytest loop/tests/ -q --tb=short` |
| AC−4 | `"REFLECT"` не в `LOOP_PHASE_MODEL_ENV` или `_LOOP_PHASE_DETECT_ORDER` | s02 | `python -c "from loop.context_loop import LOOP_PHASE_MODEL_ENV; assert 'REFLECT' not in LOOP_PHASE_MODEL_ENV"` |
| AC−5 | Промпт loop не содержит «QA pass + REFLECT» как gate к DONE | s02 | `rg "REFLECT" loop/context_loop.py` — только в комментариях/CLI args |
| FR-01 | `reduce_epic_lifecycle`: qa_pass → phase=DONE напрямую (без REFLECT) | s01 | `bin/pytest loop/tests/test_reducer_qa_bugfix.py -q` |
| FR-02 | `_declared_artifacts` не собирает `reflection_done` события | s01 | `rg "reflection_done" harness/hooks/epic/core.py` — 0 live hits |
| FR-03 | `post_implement_phase` убрать `reflection_path` из сигнатуры возврата | s01 | `bin/pytest loop/tests/test_handoff_phase_gates.py -q` |
| FR-04 | `LOOP_PHASE_MODEL_ENV` и `_LOOP_PHASE_DETECT_ORDER` без REFLECT | s02 | assert import |
| FR-05 | `_reflect_finish_block` удалена, ветка `phase_kind == "reflect"` убрана | s02 | `rg "_reflect_finish_block" loop/context_loop.py` (0 hits) |
| FR-06 | `loop/schemas/event.py`: `reflection_done` в `LEGACY_DEAD_EVENT_KINDS` (уже есть); не в `EVENT_KINDS` (уже так) | s03 | `bin/pytest loop/tests/test_schemas_event.py -q` |
| FR-07 | `loop/schemas/active_context.py` REFLECT убран из regex и frozenset | s03 | `rg "REFLECT" loop/schemas/active_context.py` — только в parsing regex если нужно legace read |
| FR-08 | `phase_registry.yaml` не содержит REFLECT | s03 | `rg "REFLECT" loop/schemas/phase_registry.yaml` (0 hits) |
| FR-09 | `loop/epic_transition.py`: `_POST_IMPLEMENT_ARMED` без REFLECT | s03 | `rg "REFLECT" loop/epic_transition.py` (0 hits) |
| FR-10 | `loop/roadmap_queue.py`: QA+REFLECT gate текст → QA gate | s03 | `rg "REFLECT" loop/roadmap_queue.py` (0 hits) |
| FR-11 | Cursor rules mainrule-core/mainrule (BACK/FRONT/INTEG) — REFLECT убран | s04 | `rg "REFLECT" .cursor/rules/back_developer/mainrule.mdc` (0 hits) |
| FR-12 | Тесты REFLECT assertions переписаны под DONE после qa_pass | s05 | `bin/pytest loop/tests/ -q --tb=short` |
| NFR-01 | Архивные `reflection_done` events в event.log → игнорируются (dead events), не вызывают краш | s01 | `bin/pytest loop/tests/test_reducer_qa_bugfix.py::test_legacy_reflection_done_event_ignored -q` |
| NFR-02 | Старый `handoff_phase == "REFLECT"` из activeContext не блокирует `epic_complete_allowed` | s01 | `bin/pytest loop/tests/test_handoff_phase_gates.py -k reflect -q` |

---

## Stages coverage

| Этап | Артефакт-шаг | Outcome |
|------|-------------|---------|
| core.py lifecycle reducer: qa_pass → DONE напрямую | s01 | `phase="DONE"` при qa_pass без reflection check |
| core.py epic_complete_allowed + post_implement_phase: убрать reflection_path | s01 | allowed=True при qa_pass; reflection_path=None из post_implement_phase |
| context_loop.py: убрать REFLECT из phase model, prompts, finish block | s02 | REFLECT не в LOOP_PHASE_MODEL_ENV/_LOOP_PHASE_DETECT_ORDER; _reflect_finish_block удалена |
| schemas + epic_transition + roadmap_queue: убрать REFLECT | s03 | REFLECT не в active_context.py frozenset, phase_registry.yaml, epic_transition.py, roadmap_queue.py |
| Cursor rules mainrule-core + mainrule: убрать REFLECT | s04 | `rg "BACK REFLECT"` 0 hits в mainrule файлах |
| Тесты: переписать REFLECT assertions → DONE | s05 | `bin/pytest loop/tests/ -q` green |

---

## Outcome map

| Plan WHAT | Закрыт шагом | Поведение после |
|-----------|-------------|-----------------|
| `IMPLEMENT → AUDIT → QA → DONE` | s01 | lifecycle переходит qa_pass→DONE без REFLECT |
| `epic_complete_allowed()` allowed=True при qa_pass | s01 | gate проходит без проверки reflection |
| LOOP_PHASE_MODEL_ENV без REFLECT | s02 | loop_phase_key("REFLECT") == None |
| Cursor rules без BACK REFLECT → ARCHIVE | s04 | mainrule таблицы чистые |
| Тесты зелёные | s05 | bin/pytest loop/tests/ green |

---

## Replacement cleanup

| Тип | Что удаляем | Где | Шаг |
|-----|------------|-----|-----|
| **A** (code) | Функции `find_reflection_artifact`, `_reflection_stale_vs_qa_pass`, `_matching_reflection_artifacts`, `_reflection_ownership_ambiguous` | `harness/hooks/epic/core.py` | s01 |
| **A** (code) | Параметр `reflection_path` из `build_post_implement_active_context` и всех callers | `harness/hooks/epic/core.py` | s01 |
| **A** (code) | Ветки `phase=REFLECT` в `reduce_epic_lifecycle` (уже нет, но остались helper-функции) | `harness/hooks/epic/core.py` | s01 |
| **A** (code) | `_reflect_finish_block()` + ветка `phase_kind == "reflect"` | `loop/context_loop.py` | s02 |
| **A** (code) | `"REFLECT"` в `_POST_IMPLEMENT_PHASES` (если есть) | `loop/context_loop.py` | s02 |
| **A** (string) | `"QA+REFLECT gate"` → `"QA gate"` в roadmap_queue.py | `loop/roadmap_queue.py` | s03 |
| **A** (string) | `reflection` из doc-строки `_declared_artifacts` | `harness/hooks/epic/core.py` | s01 |
| **I** (Kind I — instructions) | REFLECT из regex в `active_context.py` `_HANDOFF_PHASE_HEADING_RE`, `_HANDOFF_MODE_LINE_RE`, `_HANDOFF_NEXT_PHASE_RE` | `loop/schemas/active_context.py` | s03 |
| **I** (Kind I — instructions) | REFLECT из `BACK/FRONT/INTEG mainrule.mdc` таблицы + doc | `.cursor/rules/` | s04 |
| **C** (comment/string) | REFLECT из `core.py` строк 958, 2424, 2533, 3401-3402 | `harness/hooks/epic/core.py` | s01 |

---

## Steps

| ID | Title | Status |
|----|-------|--------|
| s01 | core.py — lifecycle reducer, artifacts, epic_complete_allowed, reflection helpers | pending |
| s02 | context_loop.py — phase model, finish block, prompts | pending |
| s03 | schemas + epic_transition + roadmap_queue — убрать REFLECT | pending |
| s04 | Cursor rules — убрать REFLECT из mainrule-core и mainrule | pending |
| s05 | Тесты — переписать/удалить REFLECT assertions | pending |

## Очередь шагов

| step_id | title & files | next_phase | status |
| :--- | :--- | :--- | :--- |
| **s01** | core.py — lifecycle reducer, artifacts, epic_complete_allowed, reflection helpers · [yaml](s01-core-lifecycle-reflection-helpers.yaml) | BACK IMPLEMENT | completed |
| **s02** | context_loop.py — phase model, finish block, prompts · [yaml](s02-context-loop-phase-model.yaml) | BACK IMPLEMENT | completed |
| **s03** | schemas + epic_transition + roadmap_queue — убрать REFLECT · [yaml](s03-schemas-epic-transition-roadmap.yaml) | BACK IMPLEMENT | completed |
| **s04** | Cursor rules — убрать REFLECT из mainrule-core и mainrule · [yaml](s04-cursor-rules-mainrule.yaml) | BACK IMPLEMENT | completed |
| **s05** | Тесты — переписать/удалить REFLECT assertions · [yaml](s05-tests-rewrite-reflect-assertions.yaml) | BACK IMPLEMENT | completed |