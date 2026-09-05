# [T-HUB-066 | boundary-schema-ownership-strict] PLAN

**Дата:** 2026-09-05  
**Режим:** BACK PLAN  
**Уровень:** L3–L4  
**Статус:** active  
**Clarify:** `memory-bank/back/clarify/clarify-20260905-workflow-loop-audit.md`  
**Roadmap:** `memory-bank/back/roadmap/queue.yaml` · batch `workflow-loop-20260905`  
**Deps:** **hard T-HUB-063** (sunset in registry — ownership applies to all managed schemas including sunset). Soft T-HUB-057 (JSON session).  
**Skills:** writing-plans · architecture-patterns · python-testing-patterns  
**Источник:** audit `04` P1 schema optional + payload verdict bypass · `05` repair unlinked to FAIL · `08` mutation targets

---

## Контекст

- **req:** Wire JSON на границе: `schema` **required**; fence обязателен; `data.verdict` без fence ≠ SoT; semantic ownership (epic/step/session/agent/phase) mismatch → block, не schema-retry; repair связан с parent FAIL blockers.
- **gap:**
  1. Unified validator принимает gate/repair без явного `schema` (internal default).
  2. SubagentStop: `if fence_data is not None or not data.get("verdict")` — payload verdict bypasses validate.
  3. Codex collab model `extra=ignore`.
  4. Repair result не содержит parent identity / blocker subset checks.
  5. Hardcoded agent sets vs phase/manifest SoT (partially 064).
- **refs:** `harness/hooks/subagent-stop.py`; `loop/schemas/gate_verdict.py`; `repair_result.py`; `loop/tests/test_codex_collab_verdict.py`; audit 04 §4–6, 05 §4.
- **Не:** register sunset (063); duplicate hooks (065); finish transaction (068); full retry_policy registry (can stub in this epic as module).

**CREATIVE need:** нет.

---

## Technology axiom

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Wire model | `schema` required, extra=forbid | default schema on external payload |
| Verdict SoT | JSON fence body | hook `data.verdict` without fence |
| Ownership fail | `semantic_ownership_mismatch` | schema-retry on wrong step_id |
| Repair | parent FAIL id + blocker subset | done with leftover blockers |
| Codex parser | same canonical parser | extra=ignore collab model |

---

## Продуктовая спека (WHAT)

1. No-fence verify completion cannot record PASS.
2. Missing schema field on wire → invalid.
3. Stale session/step/epic/agent ≠ current in-flight → ownership fail, no retry-as-schema.
4. Repair `done` requires empty remaining; fixed ⊆ parent FAIL.
5. One parser function for gate/repair/sunset fences.

### Product probe

| # | Question | Answer | Impact |
|---|----------|--------|--------|
| 1 | Reframe | Можно провести PASS без JSON | Close bypass |
| 2 | Wedge | invert stop condition + required schema + 1 ownership test | P0 |
| 3 | Pre-mortem | Internal models still default schema leaked to wire | Wire vs Internal split |
| 4 | Adoption | SubagentStop only | |
| 5 | Leverage | pydantic extra=forbid already on records | |
| 6 | Appetite | 4 days | cut: signed envelopes; retry_policy/v1 full product |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как stop-gate, я не принимаю PASS из payload без fence. | P0 | mutation of `or not data.get("verdict")` covered |
| US-002 | Как validator, я отвергаю missing schema on wire. | P0 | pytest extra/missing |
| US-003 | Как loop, я отвергаю verdict другого step_id. | P0 | semantic_ownership_mismatch |
| US-004 | Как parent, я вижу repair привязанный к FAIL blockers. | P0 | repair fixture |
| US-005 | Как Codex, я не принимаю extra fields. | P1 | collab extra=forbid |

#### Acceptance Scenarios — US-001

- **Given:** SubagentStop data.verdict=PASS, message without fence
- **When:** hook runs
- **Then:** validation path executed; not record_verdict PASS; retry or protocol fail

### Functional Requirements

- **FR-001:** Split Wire* vs Internal* or `require_discriminator=True` on validate_boundary external.
- **FR-002:** Replace bypass condition with `fence_data is not None` (and documented trusted adapter envelope **only if** signed — default none).
- **FR-003:** Ownership fields required for loop finish gates: `agent_id`, `epic_id`, `step_id`, `session_id`, `recorded_at` ISO, optional `evidence_sha256` format.
- **FR-004:** Compare record identity to in-flight spawn state; mismatch → `semantic_ownership_mismatch`.
- **FR-005:** BLOCKED allowed only for agents/phases that declare it (verify-qa).
- **FR-006:** Repair: parent_evidence_id; remaining/fixed disjoint; done ⇒ remaining empty; fail ⇒ remaining or diagnostic; agent_id=gate-repair.
- **FR-007:** Schema errors retry; ownership **no** retry (audit 01).
- **FR-008:** Codex collab extra=forbid; same parse function.
- **FR-009:** Mutation tests on bypass condition (08 §5).
- **FR-010:** Kind I: agent prompts «no fence = FAIL» remains true in runtime.
- **FR-011:** sunset records (after 063) get same fence+schema rules.
- **FR-012:** `loop/schemas/README.md` stale verdict.py — rewrite in-epic Kind I (audit 04/06).

### Success Criteria

| ID | Result | Check | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | no-fence + payload verdict ≠ PASS | hook test | outcome |
| SC-002 | missing schema invalid | pytest | outcome |
| SC-003 | stale step mismatch code | pytest | outcome |
| SC-004 | repair done with remaining invalid | pytest | outcome |
| SC-005 | collab extra field invalid | pytest | outcome |

### Assumptions

- Trusted adapter envelope out of scope (cut).
- Explorer remains no-verdict.

## AC

1. Fence required for verify/repair/sunset machine agents.
2. schema required on wire.
3. Ownership mismatch fail-closed without schema-retry.
4. Repair linked to parent FAIL.
5. Codex parser parity extra=forbid.

### AC−

1. Нет bypass `or not data.get("verdict")`.
2. Нет extra=ignore on collab.
3. Нет schema default on external payload.
4. Нет retry on ownership.
5. Нет repair done with leftover blockers.

## HOW

- `subagent-stop.py` condition rewrite; `validate_boundary`; models; `repair_result.py` validators; spawn state identity; tests listed in audit 08.
- retry counters stay; add classification schema vs semantic.

## Eng review spine

### Data flow

```text
[agent message] -> [extract fence] --missing--> [protocol fail/retry schema]
                         | present
                         v
                  [validate_boundary schema required]
                         | shape fail -> schema retry
                         | ok
                         v
                  [ownership vs in-flight] --mismatch--> NEED_HUMAN/block
                         | ok
                         v
                  [record_verdict / repair store]
```

### Failure matrix

| Component | Failure | Detection | Response | Test ID |
|-----------|---------|-----------|----------|---------|
| no fence + payload PASS | bypass | mutation test | fail | TM-001 |
| missing schema | default accept | wire test | invalid | TM-002 |
| extra field | ignore collab | extra=forbid | fail | TM-003 |
| stale session | wrong PASS | ownership | mismatch | TM-004 |
| repair done+remaining | inconsistent | validator | invalid | TM-005 |
| schema fail retried as repair | wrong agent | taxonomy | schema retry only | TM-006 |
| BLOCKED on verify-implement | illegal | enum/phase | fail | TM-007 |
| ISO timestamp junk | parse | validator | fail | TM-008 |

### Eng spine self-check

| Dimension | Score | Gap |
|-----------|-------|-----|
| Data flow complete | 5 | |
| Failure coverage | 5 | 8 rows |
| Testability | 5 | |

## Replacement / sunset

### A

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| `if fence or not verdict` | fence required | delete in-epic |
| extra=ignore collab | extra=forbid | delete in-epic |
| schema optional wire | required | delete in-epic |
| README verdict.py / SKIP | gate_verdict PASS/FAIL/BLOCKED | delete in-epic |

### B

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| n/a CLI | same validate-boundary | keep |

### C

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| payload verdict as SoT | fence only | delete in-epic |
| ownership retried | escalate | delete in-epic |

### I

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| prompts already say fence required | make runtime match | enforce |
| schemas README lie | rewrite | delete in-epic |

## QA consumes

<a id="qa-consumes"></a>

| ID | Priority | Scenario | Command | Expected | Maps |
|----|----------|----------|---------|----------|------|
| TM-001 | P0 | no-fence payload PASS | hook test | not PASS | US-001 |
| TM-002 | P0 | missing schema | test_validate_boundary | invalid | US-002 |
| TM-003 | P0 | stale step_id | pytest | semantic_ownership_mismatch | US-003 |
| TM-004 | P0 | repair done leftover | pytest | invalid | US-004 |
| TM-005 | P0 | extra collab | test_codex_collab | invalid | US-005 |
| TM-006 | P1 | BLOCKED implement | pytest | invalid | FR-005 |
| TM-007 | P1 | sunset no fence after 063 | hook | fail | FR-011 |

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| CLARIFY / Product probe | L3 | done | |
| Eng review spine | L2+ | done | |
| §0.11 | n/a | n/a | |
| CREATIVE | n/a | n/a | |
| qa_consumes | L2+ | done | |
| Plan review batch | L2+ | done | |

## Plan review batch log

| Phase | Auto-resolved | Deferred |
|-------|---------------|----------|
| Product | Close bypass before retry_policy product | signed envelope |
| Eng | Wire vs Internal models | retry_policy/v1 registry |

## До DECOMPOSE

1. s01 — red tests bypass + missing schema.
2. s02 — Wire required schema + extra=forbid collab.
3. s03 — stop condition + mutation test.
4. s04 — ownership vs in-flight.
5. s05 — repair parent constraints.
6. s06 — Kind I README + prompts.
7. s07 — purge bypass leftover + SKIP docs.

## Appetite

| Поле | Значение | Описание |
| :--- | :--- | :--- |
| `timebox_days` | `4` | |
| `cut_list` | `['signed runtime envelope', 'full retry_policy/v1 productization']` | |

## Independent Test

- PASS: no-fence not PASS; stale step mismatch code; repair invariant.
- FAIL: «GateVerdictRecord extra=forbid unit» without stop hook path.

## Следующий режим

→ BACK DECOMPOSE T-HUB-066 after 063 (hard).

**CREATIVE need:** нет.
