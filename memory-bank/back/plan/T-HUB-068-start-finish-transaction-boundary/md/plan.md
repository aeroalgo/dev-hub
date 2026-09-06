# [T-HUB-068 | start-finish-transaction-boundary] PLAN

**Дата:** 2026-09-05  
**Режим:** BACK PLAN  
**Уровень:** L3–L4  
**Статус:** active  
**Clarify:** `memory-bank/back/clarify/clarify-20260905-workflow-loop-audit.md`  
**Roadmap:** `memory-bank/back/roadmap/queue.yaml` · batch `workflow-loop-20260905`  
**Deps:** **hard T-HUB-066** (ownership/fence so finish only commits validated records). Soft T-HUB-040 (mb-finish). Soft T-HUB-067 (bundle ok — start half already stricter; 068 owns **finish** transaction + `finish_handoff` escape). **Не rewrite 040 plan.**  
**Skills:** writing-plans · architecture-patterns · python-testing-patterns  
**Источник:** audit `03` §7 crash window · §8 finish_handoff · §9 lost-update · `07` P2.2 TransitionService (Appetite: journal now, mega-service cut)

---

## Контекст

- **req:** Finish transition (activeContext + index/state + implement step) — **одна** recoverable транзакция. Публичный `finish_handoff` не перевооружает workflow в обход verify/finalize. Crash между write context и `finalize_step` не оставляет split-brain. Concurrent hook state saves не last-write-lose silently.
- **gap:**
  1. `finish_implement_step`: write activeContext then finalize_step; crash window = new Handoff, old index.
  2. `finish_handoff()` public escape: render+write context + mutate armed_step/phase without verify contract.
  3. `save_epic_state()` atomic replace without RMW lock (spawn-gate has lockfile; epic state does not).
  4. T-HUB-040 planned mb-finish quality; leftover **transaction/recovery** still open 2026-09-05.
  5. Full `TransitionService` class (audit P2.2) — **cut_list**; this epic = journal + close public hatch + lock.
- **refs:** `loop/mb_finish/impl.py` `finish_handoff` / `finish_implement_step`; `finalize_step`; `save_epic_state`; audit 03 §6–9.
- **Не:** REFLECT deletion (T-HUB-060 IMPLEMENT); duplicate hooks (065); pack doctor (067) except consume incomplete-bundle if already landed; Codex TOML (069).

### CREATIVE need

**нет**

---

## Technology axiom

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Finish commit | `finish_transaction/v1` journal prepared→committed | multi-file write without journal |
| Public CLI | phase-typed `mb-finish <phase>` only | public `finish_handoff` re-arm |
| Recovery hatch | `recovery_token` + journal log | undocumented escape |
| State RMW | one lock for epic state + sidecars in finish path | unlocked concurrent save_epic_state |
| Crash | prepare_session recovers/rolls back | split-brain accepted |

---

## Продуктовая спека (WHAT)

1. Journal record for every implement/qa/bugfix finish: `prepared`, `context_written`, `index_written`, `committed`, `rollback_required`.
2. `prepare_session` / next SessionStart detects incomplete journal → complete or rollback **before** agent work.
3. `finish_handoff` not on public CLI; internal only with `recovery_token`.
4. Two concurrent `save_epic_state` cannot drop fields (lock or retry).
5. Tests simulate crash-after-context-write.

### Product probe

| # | Question | Answer | Impact |
|---|----------|--------|--------|
| 1 | Reframe | Finish врёт атомарность | Journal + close hatch |
| 2 | Wedge | crash fixture + hide finish_handoff CLI | P0 |
| 3 | Pre-mortem | Journal written but recover never called | prepare_session must recover |
| 4 | Adoption | mb-finish implement path first | |
| 5 | Leverage | existing atomic file replace + backup | wrap, don't new DB |
| 6 | Appetite | 5 days | cut: full TransitionService OOP; MCP-only finish; cross-host lock |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как operator, я не хочу Handoff без index commit после crash. | P0 | crash fixture → recover aligns files |
| US-002 | Как CI, я хочу public finish_handoff fail or require token. | P0 | CLI without token → error `finish_handoff_forbidden` |
| US-003 | Как hook, я не теряю retry counter при concurrent save. | P1 | two writers fixture |
| US-004 | Как SessionStart, я доигрываю prepared journal. | P0 | leftover journal → recover before inject |

#### Acceptance Scenarios — US-001

- **Given:** staged finish; context file replaced; kill before index
- **When:** `prepare_session` / recover
- **Then:** either both new or both old; never mixed identity (epic/step mismatch)

#### Acceptance Scenarios — US-002

- **Given:** `mb-finish handoff` or Python `finish_handoff` from CLI dispatcher
- **When:** no `recovery_token`
- **Then:** reject; state not armed

### Functional Requirements

- **FR-001:** Schema `loop-finish-transaction/v1` (or `finish_transaction/v1`) in registry **or** sidecar-only documented; DECOMPOSE pick sidecar `.claude/runtime/epic/finish-tx.json` vs BOUNDARY_REGISTRY. Prefer sidecar journal first (less 066 coupling); if registered, extra=forbid.
- **FR-002:** States: `prepared` → `context_written` → `index_written` → `committed`. Failure → `rollback_required`.
- **FR-003:** Staged files in tx dir; commit = rename/replace all; fsync as existing atomic helper.
- **FR-004:** Identity check: staged Handoff epic_id/step_id == index target == state armed.
- **FR-005:** `prepare_session` calls `recover_finish_transaction()`.
- **FR-006:** Public dispatcher: only `mb-finish implement|qa|bugfix|…` typed. `handoff` subcommand removed or gated.
- **FR-007:** Internal `finish_handoff(..., recovery_token=)` validates token vs journal id; logs incident.
- **FR-008:** Kind I: finish-block.mdc / docs mentioning handoff CLI as normal path — rewrite.
- **FR-009:** `save_epic_state` lockfile same family as spawn-gate **or** document single-threaded hook assumption with test that fails if unlocked lost-update reproduced.
- **FR-010:** QA/bugfix finish functions share journal helper (not only implement) — minimum implement+qa; bugfix if same write pattern.
- **FR-011:** Do not require postgres; filesystem journal is SoT.
- **FR-012:** REFLECT finish path: **out** (060). If `finish_reflect` still exists, 068 must not reintroduce; journal helper ignores reflect.
- **FR-013:** Tests: crash after context; crash after index before committed marker; recover committed leftover (idempotent); token-less handoff.
- **FR-014:** halt_logic / check_after unchanged behaviorally except they must not call public handoff.
- **FR-015:** Appetite cut: unified TransitionService class / ContextBoundaryService — design note in HOW, **no** mandatory new module tree.

### Success Criteria

| ID | Result | Check | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | crash recover consistent | pytest | outcome |
| SC-002 | handoff without token rejected | CLI/unit | outcome |
| SC-003 | prepare_session recovers | unit | outcome |
| SC-004 | concurrent state no silent drop | pytest or skip+lock | outcome |
| SC-005 | docs no public handoff | rg | outcome |

### Assumptions

- Single machine / single project dir (hub). NFS locks N/A.
- 040 leftover wire is this epic; do not edit 040 plan file.

## AC

1. Journaled finish for implement (and qa if same writer).
2. Recover on prepare.
3. Public finish_handoff closed.
4. Crash tests.
5. State lock or proven single-writer.

### AC−

1. Нет mixed Handoff/index identity after recover.
2. Нет CLI re-arm without verify.
3. Нет journal left `prepared` ignored on next start.
4. Нет reintroduction finish_reflect.
5. Нет «backup restore only on exception» as sole crash strategy.

## HOW

- `loop/mb_finish/transaction.py` (thin journal) wrapping existing writers.
- Close dispatcher route; tests in `loop/tests/test_mb_finish_transaction.py`.
- Lock around `save_epic_state`.

## Eng review spine

### Data flow

```text
[mb-finish phase] -> [journal prepared]
                  -> [stage context+index+state]
                  -> [validate identity]
                  -> [commit marker + replace]
                  -> [committed]
[crash] -> [prepare_session recover] -> rollback or commit remainder
[finish_handoff CLI] -> forbidden unless recovery_token == journal id
```

### Failure matrix

| Component | Failure | Detection | Response | Test ID |
|-----------|---------|-----------|----------|---------|
| crash after context | split-brain | recover | align | TM-001 |
| crash after index pre-marker | ambiguous | recover policy documented | TM-002 |
| public handoff | skip verify | CLI | forbidden | TM-003 |
| stale journal ignored | start with mixed | prepare recover | TM-004 |
| lost-update state | counters | lock test | TM-005 |
| identity mismatch staged | wrong step | validate | abort tx | TM-006 |
| recover loops | journal corrupt | fail-closed NEED_HUMAN | TM-007 |
| 060 reflect finish | ImportError | ignore/out | TM-008 |

### Eng spine self-check

| Dimension | Score | Gap |
|-----------|-------|-----|
| Data flow complete | 5 | |
| Failure coverage | 5 | |
| Testability | 4 | crash sim via staged files not kill(2) |

## Replacement / sunset

### A

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| unjournaled dual write | journal helper | delete in-epic |
| public finish_handoff | typed mb-finish / token | delete in-epic |

### B

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| CLI `mb-finish handoff` | removed/gated | delete in-epic |

### C

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| exception-only restore | recover on prepare | delete in-epic |
| unlocked save_epic_state | lock | delete in-epic |

### I

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| docs «finish_handoff for operators» | recovery only | delete in-epic |
| finish-doc-router if it advertises handoff escape | typed phases | delete in-epic |

## QA consumes

<a id="qa-consumes"></a>

| ID | Priority | Scenario | Command | Expected | Maps |
|----|----------|----------|---------|----------|------|
| TM-001 | P0 | crash after context | pytest tx | recovered consistent | US-001 |
| TM-002 | P0 | handoff no token | CLI/unit | finish_handoff_forbidden | US-002 |
| TM-003 | P0 | prepare recovers journal | unit | committed or rolled back | US-004 |
| TM-004 | P1 | concurrent saves | pytest | no dropped field | US-003 |
| TM-005 | P1 | identity mismatch abort | pytest | rollback_required | FR-004 |
| TM-006 | P1 | rg public handoff docs | rg | 0 operator paths | FR-008 |

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| CLARIFY / Product probe | L3 | done | |
| Eng review spine | L2+ | done | |
| §0.11 | if new schema registered | draft sidecar-first | DECOMPOSE pick |
| CREATIVE | n/a | n/a | |
| qa_consumes | L2+ | done | |
| Plan review batch | L2+ | done | |

## Plan review batch log

| Phase | Auto-resolved | Deferred |
|-------|---------------|----------|
| Product | Journal+close hatch, not mega class | TransitionService OOP |
| Eng | Sidecar journal first | distributed lock |

## До DECOMPOSE

1. s01 — red: crash fixture + public handoff forbidden.
2. s02 — journal schema/sidecar + states.
3. s03 — wrap finish_implement (+ qa if same).
4. s04 — prepare_session recover.
5. s05 — lock save_epic_state.
6. s06 — Kind I + purge CLI/docs.
7. s07 — purge exception-only as sole strategy comments/tests.

## Appetite

| Поле | Значение | Описание |
| :--- | :--- | :--- |
| `timebox_days` | `5` | |
| `cut_list` | `['TransitionService class tree', 'ContextBoundaryService rewrite', 'MCP-only finish', 'cross-host locks']` | clarify deferred mega-service |

## Independent Test

- PASS: mixed files after simulated crash become aligned; CLI handoff without token fails.
- FAIL: «atomic replace of one file» without multi-file journal; «backup on Exception» without prepare recover.

## Decompose

Index (layout v2): [`md/decompose-index.md`](decompose-index.md) · machine [`../yaml/decompose-index.yaml`](../yaml/decompose-index.yaml) · shards `../yaml/steps/sNN-*.yaml`. Status SoT = yaml only.

**FR-001 pick:** sidecar-only `.claude/runtime/epic/finish-tx.json` (`loop-finish-transaction/v1`, extra=forbid) — **не** BOUNDARY_REGISTRY.

## Следующий режим

→ BACK ANALYZE T-HUB-068-start-finish-transaction-boundary (после DECOMPOSE FINISH).

**CREATIVE need:** нет.
