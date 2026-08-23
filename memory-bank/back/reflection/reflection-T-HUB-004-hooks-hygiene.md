---
schema: epic-reflect/v1
epic_id: T-HUB-004-hooks-hygiene
task_id: T-HUB-004
date: "2026-08-22"
author: claude
verdict: PASS
---

# Ретроспектива эпика T-HUB-004-hooks-hygiene

## Итог

Эпик закрыл hygiene hooks: `extract_verdict` last-match wins, `NEED_HUMAN: verify_no_verdict` messaging, единый `_discover_registry` (file-wins), `ALIAS["explore"]="explorer"`, delete 6 dead epic re-exports, posttool mirror без bare `except: pass`, `save_state` lock+atomic.  
**AUDIT:** PASS, `not_implemented: []` (2 low deviations — ambient env isolation).  
**QA:** PASS, AC-suite 39 passed / 0 failed; leftover sunset чист; reviewer VERDICT PASS.  
AC+/AC− закрыты; sunset deletes выполнены.

| Шаг | Название | Результат |
|-----|----------|-----------|
| s01 | extract_verdict: remove short-circuit, last-match wins, TDD | completed |
| s02 | NEED_HUMAN messaging: pretool BLOCKED→NEED_HUMAN, spawn-hard sync | completed |
| s03 | Unified registry discovery: `_discover_registry` file-wins | completed |
| s04 | ALIAS explore → explorer + normalization tests | completed |
| s05 | Delete 6 dead epic re-exports + unused import | completed |
| s06 | Posttool mirror + save_state lock/atomic | completed |
| s07 | Targeted suite + import smoke | completed |

## vs plan / decompose

| FR / AC | Покрытие | Статус |
|---------|----------|--------|
| FR-1…FR-3 extract_verdict last-wins + TDD | s01 | ✅ |
| FR-4…FR-5 NEED_HUMAN + spawn-hard/stop-gate sync | s02 | ✅ |
| FR-6 unified `_discover_registry` | s03 | ✅ |
| FR-7 ALIAS explore | s04 | ✅ |
| FR-8 delete 6 stubs; facade intact | s05 | ✅ |
| FR-9…FR-10 mirror visible + save_state lock | s06 | ✅ |
| AC+1…7 targeted pytest / rg leftover | s07 + QA | ✅ |
| AC− core.py+epic_lib / loop.sh halt / vendor archive / no monolith | QA | ✅ |
| NFR-1…4 settings/hooks/TDD/DoNotTouch | audit + QA | ✅ |
| Replacement: short-circuit · BLOCKED msg · stubs · dual discover · bare except | s01–s06 deletes | ✅ |

**Deviations (audit, low):**  
1. s05/s07 — ambient `finish_integrity` / часть `agent_hooks` без `-u DEV_HUB/HUB_ROOT/PROJECT_ROOT` падают на active epic identity — known env isolation, не regression stubs.  
2. Broader full-file run 6 test-файлов без `-k` → 9 failed / 107 passed; fails out-of-scope (session_resilience / gate_bypass / model registry ambient) — AC− Do Not Touch / follow-up вне эпика.

## Successes

- **Last-match wins first (s01):** TDD на PASS→FAIL / contract-blob / BLOCKED до wire messaging — убрал PASS short-circuit как корневой баг verdict.
- **Messaging sync (s02):** единый `NEED_HUMAN: verify_no_verdict` в pretool + spawn-hard + stop-gate — stop-маркер совпал с gate allowlist.
- **One discover helper (s03):** file-wins во всех entry hooks; тест registry_file_wins закрыл dual-path drift.
- **Sunset stubs (s05):** 6 re-export modules удалены; facade `epic`/`epic_lib` живы; `from epic.X` = 0.
- **Concurrency hygiene (s06):** fcntl lock + atomic replace на `save_state`; mirror ошибки видимы.
- **AUDIT → QA без петли:** `not_implemented[]` пуст; AC-suite 39; reviewer PASS.

## Problems

- **Ambient env isolation:** suite slice требует `env -u DEV_HUB -u HUB_ROOT -u PROJECT_ROOT`, иначе finish_integrity/agent_hooks цепляются к живому epic T-HUB-004 — known, задокументировано как Deferred (не gap AC).
- **events.jsonl без `implement_done`:** только `audit_done` + `qa_pass` — timeline IMPLEMENT s01–s07 в event-log не виден (есть implement yaml).
- **Runtime pollution после pytest:** `last-session.json` → `/tmp/pytest-of-aero/.../session.log`, `state.json` = idle + `halt_reason: API Error: terminated` + `state_rebuilt` — снимок не отражает живой эпик (повтор сигнала T-HUB-003).
- **Out-of-scope full-file fails (9):** session_resilience / gate_bypass / model registry — не трогали по AC−; follow-up вне эпика.

## Lessons

1. Verdict-парсер безопаснее через **last-match + явные contract fixtures**, чем short-circuit на первое PASS.
2. Messaging stop-маркеров (`NEED_HUMAN` vs `BLOCKED`) нужно синхронизировать сразу с spawn-hard **и** stop-gate allowlist — иначе gate drift.
3. Delete dead re-exports требует **import smoke + rg=0** в том же шаге; ambient suite isolation — отдельный promote, не blocker sunset.
4. Targeted `-k` + `env -u …` — канон AC-suite для hub hooks, пока runtime I/O не изолирован от pytest.

## Improvements (process)

- QA/ALLOW: фиксировать `env -u DEV_HUB/HUB_ROOT/PROJECT_ROOT` в suite recipe для finish_integrity/agent_hooks (уже в qa yaml — закрепить в workflow QA template).
- Event emission: `finalize-step` → `implement_done` per sNN (или batch) — повтор promote из T-HUB-003.
- Post-suite smoke: `last-session.json` не указывает в `/tmp/pytest-*` (или teardown reset) — повтор promote из T-HUB-003.
- Out-of-scope 9 fails — отдельный mini-epic / TASK на ambient model registry + gate_bypass isolation (не смешивать с ARCHIVE).

## Orchestration signals

| Источник | Наблюдение | Аномалия? |
|----------|------------|-----------|
| `events.jsonl` | seq1 `audit_done` 19:11Z → seq2 `qa_pass` 19:16Z; **нет** implement_* | Да — пробел timeline IMPLEMENT |
| `last-session.json` | `status=completed`, `outcome=clean`, `retry_count=1`, `log_file` → pytest tmp, `plan_id=null` | Да — fixture overwrite / stale |
| `state.json` | `active=false`, `idle`, `halt_reason=API Error: terminated`, `state_rebuilt=true`, epic/phase null | Да (внешн.) — rebuild после terminate; не зацикливание эпика |
| `checkpoint.json` | отсутствует | Нет (ожидаемо post-idle) |
| session logs | полный dump не читался; path в last-session = pytest | Аномалия path, не abort-loop |
| Режимы | IMPLEMENT s01–s07 → AUDIT PASS → QA PASS → REFLECT; qa_fail/retries=0 | Нет зацикливания / role drift |
| Dirty чужих эпиков | `dirty: []` в last-session | Нет |

**Вывод layer B:** продуктовый путь эпика чистый (нет qa_fail / same-step retry). Оркестрационные артефакты runtime **зашумлены тестами и API terminate** — сигнал на изоляцию runtime I/O в suite и на полноту event-log, не на re-open AC эпика.

## Promote candidates

| Сигнал | → | Действие |
|--------|---|----------|
| Нет `implement_done` в `events.jsonl` | → loop/hooks | Emit event на `finalize-step` (per step или batch) — уже в promote T-HUB-003 |
| pytest пишет/`оставляет` `last-session.json` → `/tmp/pytest-*` | → loop/hooks | Фикстуры: tmp `HUB_ROOT`/`DEV_HUB` only; teardown не трогает канон runtime **или** post-suite assert |
| Ambient finish_integrity без `-u DEV_HUB/…` | → loop/hooks | Изоляция active-epic identity в tests; закрепить `env -u` в QA recipe |
| `state_rebuilt` + `API Error: terminated` leftover | → skip | Ожидаемый idle после abort; не блокирует EPIC_DONE |
| 9 out-of-scope full-file fails | → workflow | Follow-up TASK/epic: session_resilience / gate_bypass / model registry ambient |
| QA suite recipe с `-u` уже в yaml | → skip | Закреплено в артефакте QA; template promote опционален |

## Метрики

- Шагов: 7 / 7 completed (100%)
- Audit: 0 not_implemented, 2 low deviations
- QA: 0 issues / 0 blockers; AC-suite 39 passed
- Events: 2 (`audit_done`, `qa_pass`)
- code_changed (эта сессия REFLECT): no

## Next

- **EPIC_DONE** — ARCHIVE NOW только вручную вне loop (после stop runner / исчерпания queue).
- Promote-pass (отдельный чат, не смешивать с ARCHIVE): runtime test isolation + `implement_done` events (+ ambient finish_integrity).
- Отложено: ambient env isolation finish_integrity; 9 out-of-scope full-file fails.
