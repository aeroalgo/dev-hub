# [T-HUB-074 | qa-bugfix-lifecycle-rearm] PLAN

**Дата:** 2026-09-06  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** active  
**Clarify:** `memory-bank/back/clarify/clarify-20260906-loop-session-architecture.md`  
**Roadmap:** `memory-bank/back/roadmap/queue.yaml` · batch `loop-session-architecture-20260906`  
**Deps:** **hard T-HUB-070** (next(QA) ≠ REFLECT; overlay must not re-arm REFLECT while finish_qa arms BUGFIX/DONE). Soft T-HUB-060 (REFLECT removed; leftover `finish_reflect` ImportError in T-HUB-060 qa yaml). Soft T-HUB-068 (finish journal / finish_handoff lock — complementary, not re-QA yaml).  
**Skills:** writing-plans · python-testing-patterns · architecture-patterns  
**Источник:** architecture §6 QA tx + §8 QA/BUGFIX; session audit stale QA; `loop/mb_finish/impl.py` `finish_qa` / `finish_bugfix`; T-HUB-060 qa yaml `verdict: fail`

→ decompose-index — **после DECOMPOSE**

---

## Контекст

- **req:** QA/BUGFIX lifecycle fail-closed:
  1. `finish_qa` with `verdict: fail|blocked` **cannot** mark epic DONE / dequeue / leave queue as success.
  2. After `finish_bugfix`, next QA **requires** new session + **new** `qa-*.yaml` (`qa_after_bugfix` already partially coded).
  3. Epic cannot advance past QA while latest qa yaml is fail **and** no newer pass exists.
  4. Leftover `finish_reflect` / `find_reflection_artifact` ImportError (T-HUB-060 ISS-001/ISS-002) **purged** — no live import of deleted REFLECT finish.
  5. Kind I: overlay QA→REFLECT is **070**; this epic **consumes** that 070 is merged (hard dep) and purges remaining finish_reflect symbols + stale-yaml gate.
- **gap:**
  1. Session audit: T-HUB-060 qa yaml `verdict: fail`, bugfix-doc claimed «1942 passed», queue already moved to T-HUB-062. Machine did not require re-QA pass before leaving 060.
  2. `finish_qa` as-built: fail → next_mode BUGFIX (good); pass → DONE. **Missing:** cannot `roadmap-advance` / mark epic done while latest qa fail if someone uses finish_handoff escape (068 owns closing escape; **this** epic: finish_qa + queue leave + tests that fail yaml blocks DONE).
  3. `qa_after_bugfix` / `qa_new_session_required` / `qa_new_artifact_required` exist in `finish_qa` (L140–160). Independent Test: they **cannot** be skipped via finish_handoff or by reusing old fail yaml as «the» artifact.
  4. T-HUB-060 qa ISS-001 `find_reflection_artifact` ImportError; ISS-002 tests still calling `finish_reflect`.
- **refs:** `loop/mb_finish/impl.py` `finish_qa`, `finish_bugfix`, `finish_handoff`; `loop/schemas/state.py` `QaAfterBugfix`; `harness/hooks/epic/core.py` `parse_qa_verdict`, `validate_qa_finish_handoff`; T-HUB-060 qa yaml; architecture §8.
- **Не:** overlay string REFLECT (070 deletes it); identity COMMAND (071); load_session ok (072); abort 401 (073); finish journal schema (068).

**CREATIVE need:** нет.

---

## Technology axiom (replace-not-wrap)

> **HARD.** Stale fail yaml is **not** a pass. `finish_reflect` is **deleted phase**, not shim.

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| QA verdict | `parse_qa_verdict(qa-*.yaml)` enum pass/fail/blocked | prose «1942 passed» in bugfix.md as SoT |
| Re-QA after bugfix | new yaml path ∉ `existing_artifacts` + new session | reuse fail yaml to close |
| Epic leave | latest qa pass **or** explicit BUGFIX armed | queue advance on fail yaml |
| REFLECT finish | gone | `from … import finish_reflect` / `find_reflection_artifact` live |
| next after QA fail | BUGFIX | REFLECT (070) / DONE |

---

## Продуктовая спека (WHAT)

1. `finish_qa` with fail/blocked → `ok=true` only as **transition to BUGFIX**, never DONE, never `EPIC_DONE` hint.
2. Attempt to finish_qa pass while latest artifact is the **same** fail yaml after bugfix → `qa_new_artifact_required` (already) — keep + test.
3. `finish_handoff` cannot write mode=DONE/IMPLEMENT/QA success while `armed_step=QA` and latest qa verdict fail (068 may lock generic escape; **this** epic adds QA-specific: if latest qa fail, handoff modes allowed = BUGFIX only). Overlap with 068: if 068 already blocks all finish_handoff — this epic still tests QA fail cannot DONE.
4. `roadmap-advance` / queue leave: if called after QA fail without BUGFIX — `ok=false` diagnostic `qa_fail_blocks_advance` (or reuse existing code). If no such function yet, gate in `finish_qa` is enough **plus** test that DONE handoff rejected.
5. Purge live `finish_reflect` / `find_reflection_artifact` imports and tests. Rewrite tests to `finish_qa` next BUGFIX/DONE.
6. T-HUB-060 leftover: do **not** rewrite 060 IMPLEMENT; do **purge hub code** that still imports reflect finish. Historical qa yaml on disk may stay fail (archive) — **machine** must not treat it as current pass.

### Product probe

| # | Question | Answer / Probe | Decision / Impact on PLAN |
|---|----------|----------------|---------------------------|
| 1 | **Reframe** | Эпик уехал из QA с fail yaml | Gate leave + re-QA |
| 2 | **Narrowest wedge** | finish_qa fail≠DONE; re-QA new yaml; purge finish_reflect | P0 |
| 3 | **Pre-mortem** | Tests green via finish_handoff escape | FR: escape cannot DONE on fail yaml |
| 4 | **Adoption** | mb-finish qa/bugfix all roles | |
| 5 | **Leverage** | qa_after_bugfix already in impl | tighten + tests + purge reflect |
| 6 | **Appetite** | 3 дня | cut: rewrite all historical qa yaml; auto-reopen 060 in queue |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как QA fail, я иду в BUGFIX, не DONE. | P0 | finish_qa fail → next_mode BUGFIX, not DONE |
| US-002 | Как BUGFIX done, я не закрываю QA старым fail yaml. | P0 | finish_qa after bugfix with same yaml → qa_new_artifact_required |
| US-003 | Как operator, finish_handoff не DONE при fail yaml. | P0 | finish_handoff mode DONE → ok false |
| US-004 | Как CI, нет import finish_reflect. | P0 | rg finish_reflect loop/ harness/ = 0 production |
| US-005 | Как reviewer, new QA after bugfix needs own reviewer PASS (already partial). | P1 | keep qa_reviewer_required test |

#### Acceptance Scenarios — US-001

- **Given:** qa-*.yaml `verdict: fail`, armed QA
- **When:** `finish_qa`
- **Then:** result ok for transition; rendered AC mode BUGFIX; hint not EPIC_DONE; state not phase DONE

#### Acceptance Scenarios — US-002

- **Given:** QaAfterBugfix recorded with existing_artifacts including `qa-20260905-….yaml` fail
- **When:** `finish_qa` pointing at that same file
- **Then:** `ok=False`, `qa_new_artifact_required`

#### Acceptance Scenarios — US-004

- **Given:** hub tree after epic
- **When:** `rg -n 'finish_reflect|find_reflection_artifact' loop/ harness/ --glob '!**/T-HUB-060/**'`
- **Then:** 0 in production modules; tests that imported it rewritten or deleted

### Functional Requirements

- **FR-001:** `finish_qa` fail/blocked → `next_mode="BUGFIX"` only. Never `"DONE"`, never `"REFLECT"`.
- **FR-002:** Keep `qa_new_session_required` and `qa_new_artifact_required`. Add tests that fail if those branches deleted.
- **FR-003:** `finish_handoff`: if latest qa for armed epic is fail/blocked and requested meta.mode in `{DONE, IMPLEMENT, ANALYZE, DECOMPOSE, PLAN, QA}` except BUGFIX — `ok=False` `qa_fail_blocks_handoff`. BUGFIX allowed (already bugfix_finish_required inverse).
- **FR-004:** `finish_bugfix` must set `QaAfterBugfix` so subsequent QA cannot skip (already). Test: after finish_bugfix, finish_qa without new yaml fails.
- **FR-005:** Purge `finish_reflect` function if still present; purge imports; rewrite `harness/hooks/tests/test_mb_finish_*.py` ISS-002 class.
- **FR-006:** Purge `find_reflection_artifact` or make it raise unused — **delete**.
- **FR-007:** Kind I: workflow comments next QA = REFLECT **in mb_finish / epic core** — delete. Rules mdc leftovers outside hooks — only if rg in loop/harness; `.cursor/rules` only if one-line and blocks tests (prefer 070 for overlay; this epic for Python finish_*).
- **FR-008:** Do not auto-requeue T-HUB-060 (Appetite cut). Machine gate is forward-looking.
- **FR-009:** parse_qa_verdict fail-closed: missing verdict ≠ pass.
- **FR-010:** Tests under `loop/tests/` and/or `harness/hooks/tests/` with tmp mb layout.
- **FR-011:** Independent Test = cannot leave with fail yaml; not «QaAfterBugfix field exists».
- **FR-012:** If `finish_qa` pass path requires reviewer (L183–197) — keep; do not weaken.
- **FR-013:** Queue/roadmap-advance: if a Python entrypoint advances queue on epic DONE, it must check latest qa pass. Locate in DECOMPOSE (`roadmap_queue.py` / `epic_transition`). If no such call — FR-003 handoff gate is the wedge.
- **FR-014:** No feature flag `ALLOW_QA_FAIL_DONE`.
- **FR-015:** FRONT/INTEG finish_qa same functions — one fix.

### Success Criteria

| ID | Измеримый результат | Проверка | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | fail qa → BUGFIX not DONE | pytest | outcome |
| SC-002 | reuse yaml after bugfix rejected | pytest | outcome |
| SC-003 | finish_handoff DONE blocked on fail yaml | pytest | outcome |
| SC-004 | no finish_reflect import | rg | outcome |
| SC-005 | qa_reviewer_required still on re-QA | pytest | outcome |

### Assumptions

- 070 merged so overlay won't inject REFLECT during QA FINISH (hard dep).
- 068 may further lock finish_handoff; 074 tests still required (behavior-first: two epics, one outcome).
- Historical T-HUB-060 fail yaml remains on disk as archive evidence.

### Clarifications

- clarify-20260906; 074 ≠ 060 rewrite.

### [НУЖНО УТОЧНИТЬ]

- нет CRITICAL.

## AC

1. QA fail cannot DONE.
2. Re-QA after bugfix requires new yaml + session.
3. finish_reflect purged from production.
4. Escape hatch cannot skip fail yaml.
5. Tests encode 060-shaped leftover (fail yaml + bugfix prose).

### AC−

1. Нет DONE после fail yaml.
2. Нет REFLECT next from finish_qa.
3. Нет shim `finish_reflect = finish_qa`.
4. Нет reuse fail artifact as pass.
5. Нет «bugfix.md 1942 passed» as verdict SoT.
6. Нет dual path finish_handoff that writes DONE anyway.

---

## Техника / архитектура (HOW)

- **Модули:** `loop/mb_finish/impl.py`; `harness/hooks/epic/core.py` qa helpers; tests; rg purge reflect.
- **Паттерн:** State machine QA ↔ BUGFIX already; tighten guards; delete dead REFLECT finish.
- **Sunset:** finish_reflect, find_reflection_artifact, tests importing them, DONE on fail.

---

## Eng review spine

### Data flow (ASCII)

```text
[mb-finish qa]
    -> [parse_qa_verdict]
    -> [qa_after_bugfix: new session + new yaml]
    -> [fail → BUGFIX | pass+reviewer → DONE]
    -> [render AC]
[mb-finish handoff]
    -> [if latest qa fail and mode≠BUGFIX → ok false]
[imports]
    -> [no finish_reflect]
```

### Failure matrix

| Component / link | Failure | Detection | User/system response | Test ID |
|------------------|---------|-----------|----------------------|---------|
| fail → DONE | epic leave dirty | pytest US-001 | FAIL | TM-001 |
| reuse fail yaml | false pass | pytest US-002 | FAIL | TM-002 |
| finish_handoff escape | skip gate | pytest US-003 | FAIL | TM-003 |
| finish_reflect import | 060 ISS-001 | rg | FAIL | TM-004 |
| missing new session | same session close | pytest | FAIL | TM-005 |
| reviewer skipped on re-QA | false green | pytest | FAIL | TM-006 |
| overlay REFLECT | wrong next | 070 dep | n/a here | TM-007 note |
| parse missing verdict as pass | false green | pytest | FAIL | TM-008 |

### Eng spine self-check

| Dimension | Score 1–5 | Gap / action |
|-----------|-----------|--------------|
| Data flow complete | 5 | finish_qa + handoff + purge |
| Failure coverage | 5 | fail DONE, reuse yaml, escape, reflect |
| Testability | 5 | tmp mb |

---

## Replacement / sunset (brownfield)

### A. Code / modules

| Устаревает (path / symbol) | Замена | Policy |
| :--- | :--- | :--- |
| `finish_reflect` | gone; use finish_qa | delete in-epic |
| `find_reflection_artifact` | gone | delete in-epic |
| tests importing finish_reflect | finish_qa tests | delete in-epic |
| DONE on qa fail | BUGFIX | delete in-epic |

### B. Entrypoints / deploy

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| mb-finish reflect subcommand if still registered | removed | delete in-epic |

### C. Fallbacks / soft-fail

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| finish_handoff DONE despite fail yaml | qa_fail_blocks_handoff | delete in-epic |
| ImportError catch continue | purge symbol | delete in-epic |

### I. Instruction surfaces

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| QA FINISH → REFLECT in Python comments | BUGFIX/DONE | delete in-epic (070 overlay) |

---

## NFR

| ID | Requirement |
|----|-------------|
| NFR-1 | Fail-closed epic leave |
| NFR-2 | No dead REFLECT imports |
| NFR-3 | Re-QA cost = new session (explicit), not hidden |

---

## QA consumes (test plan)

<a id="qa-consumes"></a>

### Scope under test

- finish_qa, finish_bugfix, finish_handoff QA fail, reflect purge.
- Out: overlay strings (070), abort (073), bundle (072).

### Test matrix

| ID | Priority | Scenario | Command / fixture | Expected | Maps FR/AC |
|----|----------|----------|-------------------|----------|------------|
| TM-001 | P0 | fail yaml → BUGFIX | pytest finish_qa | mode BUGFIX | US-001 FR-001 |
| TM-002 | P0 | reuse yaml after bugfix | pytest | qa_new_artifact_required | US-002 FR-002 |
| TM-003 | P0 | handoff DONE on fail | pytest | ok false | US-003 FR-003 |
| TM-004 | P0 | rg finish_reflect | rg | 0 production | US-004 FR-005 |
| TM-005 | P0 | qa_new_session_required | pytest | ok false | FR-002 |
| TM-006 | P1 | qa_reviewer_required re-QA | pytest | ok false without PASS | FR-012 |
| TM-007 | P1 | missing verdict ≠ pass | pytest | fail-closed | FR-009 |
| TM-008 | P1 | finish_bugfix sets QaAfterBugfix | pytest | subsequent QA gated | FR-004 |

### Regression notes

- 060 historical yaml not rewritten.
- 068 finish_handoff close — tests here still valid if 068 lands first or later.

---

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| CLARIFY / Product probe | L3 | done | clarify + probe |
| Eng review spine | L2+ | done | |
| §0.11 counterparts | if external | done | finish_qa ↔ state QaAfterBugfix ↔ AC render |
| CREATIVE | if flagged | n/a | |
| qa_consumes draft | L2+ | done | ≥3 P0 TM |
| Plan review batch | L2+ | done | |

## Plan review batch log

| Phase | Auto-resolved | Deferred (owner/next) | Taste / CRITICAL surfaced |
|-------|---------------|-------------------------|---------------------------|
| Product | fail≠DONE; purge reflect; no requeue 060 | rewrite historical yaml | none |
| Eng | tighten existing qa_after_bugfix | 068 journal duplicate | none |

---

## До DECOMPOSE (черновик нарезки)

1. s01 — red tests fail≠DONE, reuse yaml, handoff escape.
2. s02 — finish_qa next_mode lock + parse fail-closed.
3. s03 — finish_handoff qa_fail_blocks_handoff.
4. s04 — purge finish_reflect / find_reflection_artifact + tests.
5. s05 — Kind I rg + mb-finish reflect subcommand if any.
6. s06 — purge leftover comments.

Advisory band 5–8.

---

## Appetite

| Поле | Значение | Описание |
| :--- | :--- | :--- |
| `timebox_days` | `3` | |
| `cut_list` | `['requeue T-HUB-060', 'rewrite historical qa yaml bodies', 'auto-open BUGFIX from audit docs']` | |

## Independent Test

- PASS: fail yaml cannot DONE; re-QA needs new yaml; rg finish_reflect 0.
- FAIL: «qa_after_bugfix field already exists» without tests that escape hatch is closed.

## Следующий режим

→ BACK DECOMPOSE T-HUB-074 after 070.

**CREATIVE need:** нет.
