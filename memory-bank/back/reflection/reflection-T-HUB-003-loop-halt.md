---
schema: epic-reflect/v1
epic_id: T-HUB-003-loop-halt
task_id: T-HUB-003
date: "2026-08-22"
author: claude
verdict: PASS
---

# Ретроспектива эпика T-HUB-003-loop-halt

## Итог

Эпик закрыл дорогие outer-retry на `NEED_HUMAN`/integrity после `check-after`: pure `decide_after_action` + wire в `loop.sh`, выравнивание `last_session_path` с `epic_dir()`, docs/architecture canon, `workers.md`.  
**AUDIT:** PASS, `not_implemented: []` (2 low deviations).  
**QA:** PASS, suite 42 passed, reviewer VERDICT PASS.  
AC+/AC− закрыты; leftover NEED_HUMAN outer retry+sleep снят.

| Шаг | Название | Результат |
|-----|----------|-----------|
| s01 | Pure `decide_after_action` helper + TDD (halt matrix) | completed |
| s02 | `loop.sh` halt-parity after check-after | completed |
| s03 | `last_session_path` → epic_dir alignment (TDD) | completed |
| s04 | Docs: epic-loop / WORKFLOW / architecture data-flow | completed |
| s05 | `workers.md` + projectbrief/index gaps | completed |
| s06 | Suite targeted + Cursor-hooks unwired note | completed |

## vs plan / decompose

| FR / AC | Покрытие | Статус |
|---------|----------|--------|
| FR-1…FR-4 halt / NEED_HUMAN / EPIC_DONE / continue | s01 + s02 | ✅ |
| FR-5 last_session_path ↔ epic_dir | s03 | ✅ |
| FR-6 тесты halt-parity + path | s01–s03, s06 suite | ✅ |
| FR-7 docs canon hub runtime | s04 | ✅ |
| FR-8 workers.md + orphan claims | s05 | ✅ |
| FR-9 projectbrief / architecture gaps | s05 (+ s06 note) | ✅ / ⚠️ gap#1 «нет .venv» остался (deferred) |
| AC+ halt / NEED_HUMAN / EPIC_DONE / path / docs / workers | QA + reviewer | ✅ |
| AC− no halt on continue / no product runtime delete / no Cursor stop-gate / extract_verdict untouched | QA | ✅ |
| NFR-1…5 prepare / repair_* / activeContext / TDD / DoNotTouch | s01–s02 + audit | ✅ |
| Replacement: NEED_HUMAN retry+sleep; hardcoded last_session; `.claude/runtime/epic/` primary-canon wording | s02 / s03 / s04 deletes | ✅ |

**Deviations (audit, low):**  
1. `architecture/index.md` gap#1 ещё упоминает «нет .venv» — docs follow-up.  
2. Optional `pyproject.toml` testpaths stub skipped — `.venv/bin/pytest` уже есть.

## Successes

- **Pure helper first (s01):** `loop/halt_logic.py::decide_after_action` дал тестируемую матрицу до shell-wire; red→green без ломки `prepare` fail-closed.
- **Sunset deletes в s02:** удаление outer `NEED_HUMAN`/`after_rc` retry+sleep — корневая цель эпика; static shell parity tests зафиксировали контракт.
- **Path alignment (s03):** `last_session_path` на том же root, что `epic_dir()` (`HUB_ROOT`/`DEV_HUB` + slug) — убрана рассинхронизация hub vs product.
- **Docs + workers как first-class shards (s04–s05):** не «потом»; AC проверяемы (`workers.md` exists, epic-loop wording).
- **AUDIT → QA без петли:** `not_implemented[]` пуст; suite 42; reviewer PASS; leftover retry снят.

## Problems

- **Stale architecture gap#1 («нет .venv»)** — s06 закрыл S-HOOKS-CUR / techContext §Тесты, но index gap не подчистили; low, deferred.
- **events.jsonl без `implement_done`:** только `audit_done` + `qa_pass` — timeline IMPLEMENT s01–s06 в event-log не виден (есть delivery log / implement yaml).
- **Runtime pollution после pytest:** `.claude/runtime/epic/last-session.json` указывает на `/tmp/pytest-of-aero/.../session.log`, `state.json` = idle + `halt_reason: API Error: terminated` + `state_rebuilt` — снимок не отражает живой эпик; ирония относительно цели s03.
- **T-HUB-002 reflection без Orchestration/Promote** — прецедент; этот артефакт восстанавливает обязательные секции workflow-reflect.

## Lessons

1. Halt-семантика shell безопаснее через **pure decide + thin wire**, чем разрастание `if` в `loop.sh`.
2. Replacement cleanup (deletes + rg/static tests) ловит leftover retry лучше, чем «поправить docs».
3. Hub runtime path helpers нужно **изолировать от pytest cwd/env**, иначе suite сам портит `.claude/runtime/epic/*`.
4. Deferred docs в s06 лучше закрывать в том же шаге или явным follow-up ID — иначе gap#1 живёт после QA pass.

## Improvements (process)

- На шагах с docs/architecture gaps — checklist «все gap-строки index закрыты или `Отложено:` с owner».
- QA ALLOW / suite уже ок; для path-эпиков добавить smoke: «после suite `last-session.json` не указывает в `/tmp/pytest-*`» (или reset fixture).
- Event emission: `finalize-step` / record-session → `implement_done` per sNN (или один `implement_batch_done`) для layer B.

## Orchestration signals

| Источник | Наблюдение | Аномалия? |
|----------|------------|-----------|
| `events.jsonl` | seq1 `audit_done` 17:46Z → seq2 `qa_pass` 17:53Z; **нет** implement_* | Да — пробел timeline IMPLEMENT |
| `last-session.json` | `status=completed`, `outcome=clean`, `retry_count=1`, `log_file` → pytest tmp, `plan_id=null` | Да — fixture overwrite / stale |
| `state.json` | `active=false`, `idle`, `halt_reason=API Error: terminated`, `state_rebuilt=true`, epic/phase null | Да (внешн.) — rebuild после terminate; не зацикливание эпика |
| `checkpoint.json` | отсутствует | Нет (ожидаемо post-idle) |
| session logs | полный dump не читался; path в last-session = pytest | Аномалия path, не abort-loop |
| Режимы | IMPLEMENT s01–s06 → AUDIT PASS → QA PASS → REFLECT; qa_fail/retries=0 | Нет зацикливания / role drift |
| Dirty чужих эпиков | `dirty: []` в last-session | Нет |

**Вывод layer B:** продуктовый путь эпика чистый (нет qa_fail / same-step retry). Оркестрационные артефакты runtime **зашумлены тестами и API terminate** — сигнал на изоляцию runtime I/O в suite и на полноту event-log, не на re-open AC эпика.

## Promote candidates

| Сигнал | → | Действие |
|--------|---|----------|
| Нет `implement_done` в `events.jsonl` | → loop/hooks | Emit event на `finalize-step` (per step или batch) |
| pytest пишет/`оставляет` `last-session.json` → `/tmp/pytest-*` | → loop/hooks | Фикстуры: tmp `HUB_ROOT`/`DEV_HUB` only; teardown не трогает канон runtime **или** post-suite assert path not under `/tmp/pytest` |
| `state_rebuilt` + `API Error: terminated` leftover | → skip | Ожидаемый idle после abort; не блокирует EPIC_DONE |
| `architecture/index.md` gap#1 «нет .venv» | → workflow | Docs follow-up (T-HUB-005 simplify-docs или inline при следующем touch index) |
| pyproject testpaths stub skipped | → skip | Не нужен при живом `.venv/bin/pytest` |
| Reflection без Orchestration/Promote (T-HUB-002) | → workflow | Шаблон/checklist REFLECT: две секции обязательны (уже в workflow-reflect — enforce на FINISH) |

## Метрики

- Шагов: 6 / 6 completed (100%)
- Audit: 0 not_implemented, 2 low deviations
- QA: 0 issues / 0 blockers; suite 42 passed
- Events: 2 (`audit_done`, `qa_pass`)
- code_changed (эта сессия REFLECT): no

## Next

- **EPIC_DONE** — ARCHIVE NOW только вручную вне loop (после stop runner / исчерпания queue).
- Promote-pass (отдельный чат, не смешивать с ARCHIVE): runtime test isolation + `implement_done` events.
- Отложено: architecture/index.md gap#1; pyproject stub.
