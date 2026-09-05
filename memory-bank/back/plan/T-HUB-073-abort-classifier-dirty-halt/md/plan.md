# [T-HUB-073 | abort-classifier-dirty-halt] PLAN

**Дата:** 2026-09-06  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** active  
**Clarify:** `memory-bank/back/clarify/clarify-20260906-loop-session-architecture.md`  
**Roadmap:** `memory-bank/back/roadmap/queue.yaml` · batch `loop-session-architecture-20260906`  
**Deps:** нет hard. Soft T-HUB-003 (loop halt already exists). Soft T-HUB-068 (finish journal / last-session lock — complementary). Independent of overlay 070.  
**Skills:** writing-plans · python-testing-patterns · architecture-patterns  
**Источник:** architecture §P1 abort + dirty_files; session audit §11 401×8 empty DECOMPOSE; as-built `harness/hooks/session_resilience.py`

→ decompose-index — **после DECOMPOSE**

---

## Контекст

- **req:** Abort classifier **не** ретраит auth/policy bans как TRANSIENT. `401` / `All connections banned` / org-banned API keys → `NEED_HUMAN` / `PERMANENT_FAILURE` / halt, **не** 8 пустых DECOMPOSE-циклов. Catch-all `API Error:[^\n]*` **удалить** или сузить так, чтобы он не перекрывал permanent. `dirty_files` на abort/resume включает yaml tree / steps / index, не только `plan.md`.
- **gap (as-built 2026-09-06):**
  1. `harness/hooks/session_resilience.py` `_TRANSIENT_ABORT_PATTERNS` содержит **последним** `r"(?i)API Error:[^\n]*"` (L110). Comment L32: «Match order: specific → broad». Specific transient (`terminated`, `overloaded`, `rate limit`) exist, **then** catch-all swallows `API Error: 401 … banned`.
  2. `_PERMANENT_FAILURE_PATTERNS` has `auth_failed`, `Authentication failed`, `Invalid API key` (DSH), **не** `401` / `banned` / `All connections banned`.
  3. `DEFAULT_TRANSIENT_RETRY_MAX = 3` (as-built). Session audit described 8 empty DECOMPOSE — loop/context_loop may retry beyond this via another path; this epic must **audit both** classifier **and** any outer retry that ignores `retryable=False`. Independent Test = 401 text → `retryable=False` **and** loop does not spawn next session.
  4. dirty_files (architecture): abort marker lists only `plan.md` while yaml/steps dirty → resume misses work. Locate `dirty_files` collector in session_resilience / context_loop / last-session.json writer — **sunset incomplete list**.
- **refs:** `harness/hooks/session_resilience.py`; `loop/context_loop.py` retry; `last-session.json`; architecture abort P1; session audit §11.
- **Не:** overlay REFLECT (070); identity COMMAND (071); mb-load ok (072); finish_qa yaml (074); model substitution (already permanent, keep).

**CREATIVE need:** нет.

---

## Technology axiom (replace-not-wrap)

> **HARD.** Catch-all `API Error:` — sunset, не «добавить 401 рядом и оставить catch-all».

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Permanent abort | typed patterns: 401, banned, allowlist, auth | catch-all `API Error:[^\n]*` as TRANSIENT |
| Transient abort | explicit list: timeout, overloaded, rate-limit, stream idle, connection reset | «any API Error is retryable» |
| Retry | `SessionAnalysis.retryable` honored by loop | outer loop retry when `retryable=False` |
| dirty_files | git/status glob of epic dirty set (md+yaml+index+steps) | only `**/md/plan.md` |
| Halt | NEED_HUMAN / PERMANENT_FAILURE in last-session | silent next DECOMPOSE spawn |

**Classifier order (locked):**

1. FATAL (KeyboardInterrupt, signal)
2. PERMANENT (401 banned, All connections banned, auth_failed, model substitution, invalid config)
3. MALFORMED
4. TRANSIENT (explicit only — **no** catch-all API Error)
5. UNKNOWN (not retryable by default)

If unknown API Error remains after purge: classify **UNKNOWN_FAILURE retryable=False**, not TRANSIENT. Better miss a retry than storm 401.

---

## Продуктовая спека (WHAT)

1. Input containing `API Error: 401` and/or `banned` → `SessionAnalysis.retryable is False`, `abort_kind` permanent/need_human, **not** `transient_abort`.
2. Input `All connections banned` (with or without API Error prefix) → same.
3. Catch-all `API Error:[^\n]*` **gone** from `_TRANSIENT_ABORT_PATTERNS`.
4. Transient still matches: timeout, overloaded, rate limit, stream idle, connection reset, incomplete response.
5. Loop/context_loop: when analysis.retryable is False → **does not** increment transient retry / spawn another agent session; writes NEED_HUMAN / last-session permanent.
6. dirty_files on abort includes at least: `plan.md` if dirty, `yaml/**/*.yaml` under epic plan, `decompose-index.yaml`, implement/qa yaml if dirty. Independent Test: dirty step yaml without dirty plan.md still listed.
7. Tests table-driven: 401, banned, overloaded, timeout, KeyboardInterrupt.

### Product probe

| # | Question | Answer / Probe | Decision / Impact on PLAN |
|---|----------|----------------|---------------------------|
| 1 | **Reframe** | Loop штормит banned 401 как «сеть моргнула» | Permanent halt |
| 2 | **Narrowest wedge** | Delete catch-all; add 401/banned to permanent; honor retryable in loop | P0 |
| 3 | **Pre-mortem** | Добавят 401 pattern **после** catch-all (order) или оставят catch-all «на всякий» | FR: catch-all **deleted**; tests fail if reintroduced |
| 4 | **Adoption** | All loop run_session paths | |
| 5 | **Leverage** | classify_abort already exists; don't new framework | |
| 6 | **Appetite** | 2–3 дня | cut: ML classifier; rewrite all retry UX; Variant B event log |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как operator, 401 banned не ретраится. | P0 | `classify_abort("API Error: 401 … banned")` → retryable False |
| US-002 | Как DECOMPOSE session, All connections banned → NEED_HUMAN, не 8 пустых прогонов. | P0 | loop fixture: one spawn then halt |
| US-003 | Как implementer, timeout всё ещё retryable. | P0 | timeout text → retryable True |
| US-004 | Как resume, dirty yaml step виден без dirty plan.md. | P0 | dirty_files contains `s03-*.yaml` |
| US-005 | Как CI, catch-all API Error отсутствует в source. | P0 | `rg 'API Error:\[\\^\\n\]\\*' session_resilience.py` = 0 |

#### Acceptance Scenarios — US-001

- **Given:** stderr/stdout blob `API Error: 401 {"error":{"message":"All connections banned"}}`
- **When:** `classify_abort` / `analyze_session`
- **Then:** `retryable is False`; outcome in `{permanent_failure, unknown_failure}` **not** `transient_abort`; reason includes banned or 401

#### Acceptance Scenarios — US-004

- **Given:** git/workdir dirty `memory-bank/back/plan/T-HUB-070-…/yaml/steps/s01-*.yaml`, plan.md clean
- **When:** abort/resume dirty collector
- **Then:** `dirty_files` includes that yaml path; not empty; not only plan.md

### Functional Requirements

- **FR-001:** Remove `re.compile(r"(?i)API Error:[^\n]*")` from `_TRANSIENT_ABORT_PATTERNS`. Kind I: tests that relied on catch-all for generic API Error → rewrite to UNKNOWN or specific pattern.
- **FR-002:** Add to `_PERMANENT_FAILURE_PATTERNS` (or dedicated NEED_HUMAN set consumed as non-retryable):
  - `(?i)API Error:\s*401\b`
  - `(?i)\b401\b[^\n]*banned`
  - `(?i)All connections banned`
  - `(?i)connections? banned`
  - existing auth_failed kept
- **FR-003:** `classify_abort` / `analyze_session` order: permanent **before** transient. Unit test: string matching both `API Error:` and `401` is permanent.
- **FR-004:** Audit `context_loop.py` / `run_session` retry: if `analysis.retryable` is False, **no** sleep+retry. If a second retry path ignores analysis — delete in-epic.
- **FR-005:** last-session.json records `abort_kind`, `retryable: false`, `need_human: true` (field names as-built schema; extra=forbid → use existing keys). Do not invent parallel marker file.
- **FR-006:** dirty_files collector: include globs under armed epic dir: `**/*.md`, `**/*.yaml`, `**/*.yml` relative to plan epic and implement/qa/bugfix dirs for epic_id. Exclude `__pycache__`, `.venv`. If collector currently hardcodes `md/plan.md` — delete that special case.
- **FR-007:** Tests in `harness/hooks/tests/` (session_resilience already has tests — extend, don't parallel module).
- **FR-008:** Kind I comments «API Error always transient» — delete.
- **FR-009:** DSH `_DSH_TRANSIENT_PATTERNS` must not reintroduce catch-all API Error. DSH permanent already has terminated/overloaded — keep; add 401/banned there too **or** share one pattern tuple (prefer shared constant `_AUTH_BANNED_PATTERNS` used by both).
- **FR-010:** UNKNOWN API Error (e.g. `API Error: weird`) after catch-all removal → retryable False (safe default). Optional: log metric `abort_unknown`. Not TRANSIENT.
- **FR-011:** Do not change `DEFAULT_TRANSIENT_RETRY_MAX` as the fix for 401 (that's treating symptom). If audit finds a **second** retry max of 8/30 that ignores classifier — sunset that constant in-epic.
- **FR-012:** KeyboardInterrupt remains FATAL, not retried.
- **FR-013:** Model substitution remains permanent (already). Regression test stays.
- **FR-014:** Independent Test is behavior of classify + loop halt, not «pattern exists in tuple».
- **FR-015:** FRONT/INTEG loops share session_resilience — one fix.

### Success Criteria

| ID | Измеримый результат | Проверка | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | 401 banned not retryable | pytest | outcome |
| SC-002 | catch-all gone | rg + pytest | outcome |
| SC-003 | timeout still retryable | pytest | outcome |
| SC-004 | dirty yaml listed | pytest tmp dirty | outcome |
| SC-005 | loop does not retry permanent | pytest/loop fixture | outcome |

### Assumptions

- Session audit «8 retries» may be outer loop or human re-invoke; classifier still must not mark 401 retryable.
- dirty_files may live next to last-session writer; DECOMPOSE locates exact symbol.

### Clarifications

- Session: clarify-20260906; independent of 070.

### [НУЖНО УТОЧНИТЬ]

- нет CRITICAL. Exact last-session schema field names — DECOMPOSE reads as-built.

## AC

1. 401/banned → not TRANSIENT.
2. Catch-all API Error deleted.
3. Transient list still covers timeouts/overload.
4. dirty_files includes yaml steps.
5. Loop honors retryable=False.

### AC−

1. Нет catch-all `API Error:` в transient.
2. Нет «401 pattern after catch-all» dual.
3. Нет retry when retryable False.
4. Нет dirty_files = [plan.md] only.
5. Нет feature flag `RETRY_401` default on.
6. Нет второго classifier copy in context_loop that still catch-alls.

---

## Техника / архитектура (HOW)

- **Модули:** `harness/hooks/session_resilience.py` (classifier + dirty); `loop/context_loop.py` retry consumer; tests under `harness/hooks/tests/`.
- **Паттерн:** Chain of responsibility ordered pattern lists; Strategy already SessionOutcome enum — extend usage, don't add Outcome v2.
- **Sunset:** L110 catch-all; incomplete dirty_files allowlist.

---

## Eng review spine

### Data flow (ASCII)

```text
[run_session stderr/stdout]
    -> [classify_abort: FATAL → PERMANENT → MALFORMED → TRANSIENT → UNKNOWN]
    -> [SessionAnalysis.retryable]
    -> [context_loop: if retryable: backoff+retry else halt NEED_HUMAN]
    -> [collect dirty_files epic glob]
    -> [last-session.json]
```

Hops: stream → classify → loop decision → dirty → marker (≥3, fail-closed permanent).

### Failure matrix

| Component / link | Failure | Detection | User/system response | Test ID |
|------------------|---------|-----------|----------------------|---------|
| Catch-all leftover | 401 retried | pytest + rg | FAIL | TM-001 |
| 401 not in permanent | UNKNOWN retried if someone adds catch-all later | pytest US-001 | FAIL | TM-002 |
| Loop ignores retryable | 8 empty sessions | loop fixture | FAIL | TM-003 |
| dirty only plan.md | yaml lost | pytest | FAIL | TM-004 |
| timeout classified permanent | lost retries | pytest | FAIL | TM-005 |
| DSH copy catch-all | 401 on DSH retried | pytest DSH | FAIL | TM-006 |
| unknown API Error transient | storm | FR-010 | FAIL | TM-007 |
| KeyboardInterrupt retried | bad UX | pytest | FAIL | TM-008 |

### Eng spine self-check

| Dimension | Score 1–5 | Gap / action |
|-----------|-----------|--------------|
| Data flow complete | 5 | classify → loop → dirty |
| Failure coverage | 5 | 401, catch-all, loop, dirty, timeout, DSH |
| Testability | 5 | table-driven strings |

---

## Replacement / sunset (brownfield)

### A. Code / modules

| Устаревает (path / symbol) | Замена | Policy |
| :--- | :--- | :--- |
| `_TRANSIENT_ABORT_PATTERNS` catch-all `API Error:[^\n]*` | explicit transient only | delete in-epic |
| missing 401/banned in permanent | `_AUTH_BANNED_PATTERNS` shared | add + consume |
| dirty_files plan.md-only | epic glob md+yaml | delete in-epic |
| any second retry ignoring analysis | honor retryable | delete in-epic |

### B. Entrypoints / deploy

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| n/a (same run_session) | — | n/a |

### C. Fallbacks / soft-fail

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| «retry unknown API Error» | UNKNOWN retryable False | delete in-epic |

### I. Instruction surfaces

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| comments API Error always transient | permanent 401 | delete in-epic |

---

## NFR

| ID | Requirement |
|----|-------------|
| NFR-1 | Halt 401 in one session, not N |
| NFR-2 | Classifier O(patterns × log size) unchanged order of magnitude |
| NFR-3 | Kind I rg catch-all = 0 |

---

## QA consumes (test plan)

<a id="qa-consumes"></a>

### Scope under test

- classify_abort / analyze_session; context_loop retry; dirty_files.
- Out: overlay (070), identity (071), load_session (072), finish_qa (074).

### Test matrix

| ID | Priority | Scenario | Command / fixture | Expected | Maps FR/AC |
|----|----------|----------|-------------------|----------|------------|
| TM-001 | P0 | 401 banned not retryable | pytest classify | retryable False | US-001 FR-002 |
| TM-002 | P0 | catch-all absent | rg + pytest | 0 hits | US-005 FR-001 |
| TM-003 | P0 | timeout retryable | pytest | True | US-003 FR-010 inverse |
| TM-004 | P0 | dirty yaml listed | pytest tmp | path in list | US-004 FR-006 |
| TM-005 | P0 | loop no retry permanent | pytest loop | one attempt | US-002 FR-004 |
| TM-006 | P1 | All connections banned no API prefix | pytest | permanent | FR-002 |
| TM-007 | P1 | unknown API Error not transient | pytest | retryable False | FR-010 |
| TM-008 | P1 | DSH 401 permanent | pytest | retryable False | FR-009 |

### Regression notes

- Model substitution tests must stay green.
- Overloaded / rate-limit still transient.

---

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| CLARIFY / Product probe | L3 | done | clarify + probe |
| Eng review spine | L2+ | done | |
| §0.11 counterparts | if external | done | classify ↔ loop retry ↔ last-session |
| CREATIVE | if flagged | n/a | |
| qa_consumes draft | L2+ | done | ≥3 P0 TM |
| Plan review batch | L2+ | done | |

## Plan review batch log

| Phase | Auto-resolved | Deferred (owner/next) | Taste / CRITICAL surfaced |
|-------|---------------|-------------------------|---------------------------|
| Product | Halt 401; delete catch-all | ML abort class | none |
| Eng | Ordered lists + shared banned patterns | rewrite retry UX | none |

---

## До DECOMPOSE (черновик нарезки)

1. s01 — table-driven red tests 401/banned/timeout/catch-all presence.
2. s02 — delete catch-all; add permanent patterns; shared tuple.
3. s03 — loop honor retryable=False (find second retry max if any).
4. s04 — dirty_files glob epic yaml+md.
5. s05 — DSH parity + Kind I rg.
6. s06 — purge leftover tests expecting catch-all.

Advisory band 5–8.

---

## Appetite

| Поле | Значение | Описание |
| :--- | :--- | :--- |
| `timebox_days` | `3` | |
| `cut_list` | `['ML classifier', 'rewrite all retry UX copy', 'Variant B event log']` | |

## Independent Test

- PASS: 401 text → no retry; catch-all rg 0; dirty yaml listed; timeout still retries.
- FAIL: «добавили 401 рядом с catch-all».

## Следующий режим

→ BACK DECOMPOSE T-HUB-073 (deps none; can parallel 070). Queue order after 062–069.

**CREATIVE need:** нет.
