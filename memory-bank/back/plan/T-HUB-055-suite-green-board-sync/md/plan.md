# [T-HUB-055 | suite-green-board-sync] PLAN

**Дата:** 2026-09-02  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** done  
**Clarify:** Phase 0 skipped — taxonomy clear (axiom из T-HUB-020 s06: epic cards only)  
**Roadmap:** [roadmap-suite-hygiene-epics.md](roadmap-suite-hygiene-epics.md)  
**Deps hard:** T-HUB-054  
**Baseline nodeids (fresh):**

- `loop/tests/test_board_sync_epic_regression.py::test_e2e_pending_steps_emit_single_epic_card_pending_to_epic`
- `…::test_e2e_sync_roadmap_rank_column_running_backlog_roadmap_column`
- `…::test_e2e_step_era_cards_archived_on_sync`
- `loop/tests/test_board_sync_sync.py::test_sync_generation_increment`

→ decompose после DECOMPOSE

## Контекст

- req: board sync снова соответствует sunset step→epic (T-HUB-020); e2e regression green
- deps: T-HUB-054 (runner); soft T-HUB-014/019/020 implement
- refs: `implement-T-HUB-020-…/s06-scan-epics-sunset-step-cards.yaml` (deletes: step card upsert pipeline); `s09-integration-tests-docs.yaml`

## Technology axiom

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Board projection unit | **epic** card (`card_kind: epic`, stable id `…-epic`) | upsert новых step-era cards как desired SoT |
| Step-era leftover on board | archive via `archive_all_task_ids(..., step_era_archive=True)` | оставлять step cards «для совместимости» |
| Tests | assert epic ids / archived step ids | assert `…-s01` как единственный upsert target |

## Продуктовая спека (WHAT)

Оператор Task Board видит **одну карточку на эпик**, а не рой step-карточек. Старые step-era карточки при sync **архивируются**. Регрессионные тесты закрепляют этот контракт и не требуют возврата step-upsert pipeline.

## Product probe

| # | Question | Answer | Impact |
|---|----------|--------|--------|
| 1 | Reframe | Incomplete sunset: `run_sync` всё ещё кормит `compute_ops([*epics, *steps])` | PROD fix desired set |
| 2 | Wedge | Убрать steps из desired upsert; оставить archive step-era; green 4 tests | s01 prod + s02 tests |
| 3 | Pre-mortem | Tests ослабят archive assert | AC− archive must fire |
| 4 | Adoption | board sync CLI / loop board | e2e PASS |
| 5 | Leverage | Не трогать gate JSON | out → 054 |
| 6 | Appetite | 1–2 дня | cut CLI polish |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как оператор доски, я хочу sync создавал epic-card и архивировал step-era, чтобы доска не плодила sNN карточки. | P0 | Fixture: существующая step card + pending epic → после `run_sync` step id ∈ `client.archived`, epic id в `client.tasks`, status running/backlog по rank. |
| US-002 | Как BACK QA, я хочу board regression suite зелёный без правки AC на step-upsert. | P0 | `bin/pytest loop/tests/test_board_sync_epic_regression.py loop/tests/test_board_sync_sync.py -q` → 0 failed. |

#### Acceptance Scenarios — US-001

- **Given:** FakeClient с `card_kind: step` и decompose pending
- **When:** `run_sync([ref], client)`
- **Then:** step id archived; epic card upserted; errors empty

### Functional Requirements

- **FR-001:** `run_sync` передаёт в `compute_ops` desired = epics (+ gates path as today), **без** step WorkItems как upsert SoT (доделать deletes T-HUB-020 s06).
- **FR-002:** `archive_all_task_ids(..., step_era_archive=True)` применяется и `retire_board_task`/`client.archive` вызывается для step-era ids.
- **FR-003:** `test_sync_generation_increment` и e2e regression согласованы с epic-only desired.
- **FR-004:** Method lock: каждый FAIL → implement T-HUB-020 s06/s09 → fix prod or rewrite test; **FORBIDDEN** restore step upsert «чтобы green».
- **FR-005:** CLI dry-run/status (если снова красные после 054) — rewrite под epic stable-id (`…-epic`), не `…-s01`.

### Success Criteria

| ID | Результат | Проверка | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | 4 board nodeids green | targeted pytest | outcome |
| SC-002 | Full suite без board F из baseline | `bin/pytest -q --tb=no` | outcome |
| SC-003 | rg: нет желания «вернуть step upsert» в sync desired | code review / test | outcome |

### Assumptions

- `scan_steps` может остаться для gates/scan_gates input, но не для board upsert desired.
- Gate cards path не ломаем.

## AC

1. Четыре baseline board FAIL → PASS.
2. `run_sync` не upsert’ит новые step-era cards из pending steps.
3. Step-era existing → archive.
4. Sunset A закрыт в purge step.

### AC−

1. Нет dual desired: epic+step upsert SoT.
2. Нет soft-skip archive.
3. Нет тестов, требующих step-card как единственный SoT после эпика.
4. Misconfig queue → fail-closed (уже); не ослаблять.

## Техника / HOW

- Модули: `loop/board_sync/sync.py`, `diff.py`, `scan_epics.py`, `client.py` FakeClient, tests `test_board_sync_*`
- Корневая гипотеза бага: `compute_ops([*epics, *steps], …)` → step card update вместо archive; либо archive затем перебивается upsert (`archived.discard` в FakeClient)

## Eng review spine

### Data flow

```text
[scan_epics] -> [desired epic cards] -> [compute_ops]
[existing board] -> [archive_all_task_ids step_era] -> [BoardOp archive] -> [FakeClient.archive]
[scan_steps] -> [gates only / no upsert]   sync; fail-closed on queue errors
```

### Failure matrix

| Component | Failure | Detection | Response | Test ID |
|-----------|---------|-----------|----------|---------|
| desired includes steps | step not archived | e2e assert | remove steps from compute_ops | TM-001 |
| archive not applied | archived empty | e2e | fix apply order / ops merge | TM-002 |
| generation assert stale | sync_generation fail | unit | rewrite expect | TM-003 |
| CLI expects s01 | dry_run fail | CLI test | rewrite epic id | TM-004 |
| restore step upsert | dual SoT | review | FAIL AC− | TM-005 |

### Eng spine self-check

| Dimension | Score | Gap |
|-----------|-------|-----|
| Data flow | 5 | — |
| Failure coverage | 5 | — |
| Testability | 5 | — |

## Replacement / sunset

### A. Code / modules

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| `sync.run_sync` desired `*steps` upsert pipeline | epic-only desired | delete in-epic |
| Test asserts requiring only `…-s01` upsert (если ещё есть) | `…-epic` | delete in-epic / rewrite |
| Dual path «if steps else epics» | single epic path | delete in-epic |

### B. Entrypoints

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| n/a (same CLI) | — | n/a |

### C. Fallbacks

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| keep step cards if archive fails silently | raise/error in result.errors or hard archive | delete in-epic |

## QA consumes

### Scope

- board_sync epic regression + sync generation (+ CLI if red)

### Test matrix

| ID | Priority | Scenario | Command | Expected | Maps |
|----|----------|----------|---------|----------|------|
| TM-001 | P0 | step archived | `bin/pytest loop/tests/test_board_sync_epic_regression.py::test_e2e_step_era_cards_archived_on_sync -q` | PASS | FR-002 |
| TM-002 | P0 | rank columns | `…::test_e2e_sync_roadmap_rank_column_running_backlog_roadmap_column` | PASS | FR-001 |
| TM-003 | P0 | pending→epic | `…::test_e2e_pending_steps_emit_single_epic_card_pending_to_epic` | PASS | FR-001 |
| TM-004 | P0 | generation | `bin/pytest loop/tests/test_board_sync_sync.py::test_sync_generation_increment -q` | PASS | FR-003 |
| TM-005 | P0 | board cluster | `bin/pytest loop/tests/test_board_sync_epic_regression.py loop/tests/test_board_sync_sync.py -q` | 0 failed | SC-001 |

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| CLARIFY / Product probe | L3 | done | §Product probe |
| Eng review spine | L2+ | done | filled |
| §0.11 | draft | done | sync↔diff↔scan_epics |
| CREATIVE | n/a | n/a | — |
| qa_consumes | L2+ | done | ≥5 TM |
| Plan review batch | L2+ | done | below |

## Plan review batch log

| Phase | Auto-resolved | Deferred | CRITICAL |
|-------|---------------|----------|----------|
| Product | epic-only SoT from T-HUB-020 s06 | — | none |
| Eng | root cause = desired `*steps` leftover | CLI only if red after fix | none |

## До DECOMPOSE

1. **s01** — изменить `run_sync` desired (epic-only upsert); сохранить step_era archive  
2. **s02** — TDD green regression + sync_generation  
3. **s03** — CLI asserts rewrite if needed  
4. **s04-legacy-fallback-purge** — rg/tests: нет step upsert SoT; sunset inventory s06 closes

## Appetite

| Поле | Значение |
| :--- | :--- |
| `timebox_days` | `2` |
| `cut_list` | `['CLI UX copy', 'extra board docs']` |

## Следующий режим

→ BACK DECOMPOSE после T-HUB-054 (queue deps)
