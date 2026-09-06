# [T-HUB-057 | loop-session-json-contract] PLAN

**Дата:** 2026-09-02  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** active  
**Prompt:** [md/prompt.md](prompt.md) — `## Epic` + `## Covering`  
**Clarify:** Phase 0 skipped — taxonomy clear (chat 2026-09-02 + refine: schema-retry / error taxonomy / post-finish next≠current arm)  
**Roadmap:** [roadmap-loop-session-contract-epics.md](roadmap-loop-session-contract-epics.md) · queue sibling  
**Deps:** **hard** T-HUB-056 (suite green / loop identity). **Soft:** T-HUB-040 / T-HUB-045 (mb-finish / mb-load modules — в canon skip/done; reuse, не re-invent). **Unlocks:** T-HUB-053 (Codex parity после канона session path).

**Skills:** writing-plans · architecture-patterns · python-testing-patterns · grill-me (Phase 0 skip → mini grill в §Product probe)

→ [T-HUB-057-loop-session-json-contract/md/decompose-index.md](T-HUB-057-loop-session-json-contract/md/decompose-index.md) — **после DECOMPOSE**

---

## Контекст

- **req:** Один machine path сессии: mb-load start → JSON на границах с **runtime pydantic validate-before-emit** → schema-retry тем же агентом при invalid → semantic FAIL → repair → PASS → mb-finish → **arm next ≠ finished** (anti-loop). Сейчас: dual prose path, слабый no-verdict retry, finish без жёсткого next≠current.
- **gap (as-built):**
  - `loop/mb_load` / SessionStart — есть, не обязателен как SoT; prepare = prose paths.
  - Gate JSON fence + sidecar — есть; schema-retry универсальный (diagnostic → re-emit) — нет; смешение schema vs semantic ошибок — нет.
  - `mb-finish` + hint — есть; stop `last_finish_tool` — частичный; **assert next_step ≠ step_just_finished** — нет.
  - LLM «сам валидирует в голове» — anti-pattern; нужна runtime validation.
- **refs:** чат 2026-09-02 (схема + refine); `plan-T-HUB-040/045`; `loop/mb_load/**`, `loop/mb_finish/**`, hooks `session-start` / `subagent-stop` / `agent-pretool` / `stop-gate`; `loop/schemas/gate_verdict.py`; `verify_hint.py`.

**CREATIVE need:** нет.

---

## Technology axiom (replace-not-wrap)

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Session START | `mb-load session` → `mb-load-result/v1` | multi-Read `load_now` как primary SoT |
| Session FINISH | `mb-finish <phase>` → `mb-finish-result/v1` (+ typed `next_*`) | ручной Write AC / `status: completed` |
| Boundary emit | fenced JSON + **registry schema_id → pydantic model** | prose `VERDICT:` / free-text machine SoT |
| Schema invalid | runtime validate → **same agent re-emit** (≤N) → NEED_HUMAN | regex salvage; silent accept; «я проверил» без tool |
| Semantic FAIL | `@gate-repair` / parent fix → re-gate | schema-retry вместо repair; repair без prior FAIL |
| Post-finish cursor | arm/seed **только** `next ≠ finished_step` из finish result | re-arm того же sNN; Write AC next вручную |
| Validator | hook/CLI/tool (код) — агент **вызывает** validate-функцию с JSON | «в голове ок» без runtime ok |
| Pre-emit self-check | тот же pydantic helper, что у boundary hook (`validate-boundary` CLI/MCP) | отдельный «мягкий» checker с иной семантикой |

As-built optional load / prose FINISH / no-verdict-only retry — **sunset inventory**.

---

## Продуктовая спека (WHAT)

Оператор и loop получают сессию, где:

1. Старт = typed bundle.  
2. Любой выход на machine-границе валидируется **кодом** до приёма.  
3. Битый schema-output чинит **тот же** агент (счётчик).  
4. Semantic blockers чинит repair/parent, не schema-retry.  
5. После успешного finish статусы и next cursor обновляются tool’ом; следующий шаг **обязан отличаться** от только что закрытого — иначе fail-closed (петля одного sNN запрещена).  
6. Для каждой границы — один канон (schema), «выглядит только так».

### Product probe (office-hours lite)

| # | Question | Answer / Probe | Decision / Impact on PLAN |
|---|----------|----------------|---------------------------|
| 1 | **Reframe:** | Prose START/FINISH + mixed errors + step loops | Enforce boundaries + taxonomy + anti-loop arm |
| 2 | **Narrowest wedge:** | IMPLEMENT: load → verify JSON schema-retry → PASS → mb-finish → next≠sNN | P0 IMPLEMENT; phases P1 |
| 3 | **Pre-mortem:** | Schema-retry зовут repair; или arm того же шага | Taxonomy HARD + next≠current AC |
| 4 | **Adoption:** | EPIC_LOOP Claude; 053 копирует | Canon Claude first |
| 5 | **Leverage:** | mb_load/mb_finish + SubagentStop | Wire + registry + counters |
| 6 | **Appetite:** | 4–6 дней | cut: mid-turn JSON; MCP polish; DSH |

### Canon: machine boundaries (единственные JSON SoT)

Mid-turn Read/Edit/Bash **не** обязаны JSON. Machine boundaries:

| Boundary ID | Кто эмитит | Schema (канон) | Validator (runtime) | При успехе | При schema fail | При semantic fail |
|-------------|------------|----------------|---------------------|------------|-----------------|-------------------|
| `B-START` | SessionStart / `mb-load session` | `mb-load-result/v1` | `load_session` pydantic | parent работает по bundle | prepare/start HALT или ok:false → не стартовать work | shape/missing → halt |
| `B-SPAWN` | parent → Task prompt | секции контракта (AC+/…); не полный OutputModel | `agent-pretool` / `spawn_validate` | child стартует | DENY spawn + diagnostic | — |
| `B-GATE` | verify-* / reviewer / analyze-verify | `loop-gate-verdict/v1` | SubagentStop + `GateVerdictRecord` + sidecar | record verdict; hint | **schema-retry** same agent ≤N | verdict FAIL → repair path |
| `B-REPAIR` | gate-repair | `loop-repair-result/v1` | SubagentStop extract repair | parent re-verify | schema-retry ≤N | status fail/partial → parent/NEED_HUMAN |
| `B-FINISH-REQ` | parent CLI args/stdin | `mb-finish-request/v1` | CLI pydantic | run finish | ok:false, no mutate | verify_pass_required и т.п. |
| `B-FINISH-RES` | mb-finish | `mb-finish-result/v1` **обязан** содержать `finished_step` + `next_step` \| `next_phase` \| `epic_done` | response model | parent arm next | — (tool bug) | ok:false |
| `B-ARM` | parent после finish | arm/seed API result (typed) | arm_phase / seed-implement | cursor = next | fail-closed | **next == finished → diagnostic `step_loop_forbidden`** |

**Registry SoT:** `agent_id | boundary_id → schema_id → pydantic model` (код; prompt только ссылается на schema_id). DECOMPOSE: таблица в implement + тесты registry completeness для managed gates.

### Canon: validate-before-emit protocol

Агент **не** валидирует JSON «в голове». Он **кладёт candidate в функцию** (CLI/MCP) → тот же pydantic, что и boundary hook.

#### Preferred agent path (pre-emit)

```text
1. Agent builds candidate JSON for boundary B (schema_id from registry)
2. Agent CALLS validate tool/CLI:
     epic_resolve.py validate-boundary --schema <schema_id> --json '<candidate>'
     (или MCP validate_boundary; stdin JSON ok)
3. Tool returns typed result:
     { "schema": "loop-validate-result/v1", "ok": true|false,
       "schema_id": "...", "diagnostic_codes": [], "errors": [] }
4. ok=false → agent fixes candidate using diagnostic_codes (same turn) → goto 2
              (agent-local attempts; not yet boundary accept)
5. ok=true  → agent EMITS final fence / calls finish CLI with that JSON
6. Boundary hook/CLI (SubagentStop / mb-finish) RE-VALIDATES same schema
     → defense in depth: skip pre-emit ≠ skip gate; gate always runs
```

**Один helper SoT:** `validate_boundary(schema_id, payload) -> ValidateResult` в `loop/` (или shared).  
Pre-emit CLI и SubagentStop/mb-finish **импортируют одну функцию** — FORBIDDEN второй checker с иной семантикой.

#### Boundary accept path (hook / finish — всегда)

```text
1. Candidate arrives at boundary B (fence / CLI body)
2. Same validate_boundary(B.schema_id, candidate)
3. ok=true  → accept, persist sidecar/state, continue protocol for B
4. ok=false → diagnostic_codes[] to SAME agent
              → MUST re-emit fixed JSON (not prose apology)
              → retry_count[B, spawn_id] += 1
5. retry_count > N (default N=2 gates; N=1 repair)
              → NEED_HUMAN: schema_retry_exhausted:<boundary>
              → stop-gate allow stop only with that marker (no fake PASS)
```

**HARD:**  
- «Провалидировал» = `ValidateResult.ok=true` от runtime tool/hook.  
- Pre-emit call **рекомендуется** (prompt contract managed agents); boundary re-validate **обязателен**.  
- Pre-emit ok не отменяет hook validate.

### Canon: error taxonomy (не смешивать)

| Класс | Код-префикс | Примеры | Действие |
|-------|-------------|---------|----------|
| **schema** | `schema_*` | no fence, bad JSON, missing field, wrong enum, wrong schema id | same-agent schema-retry |
| **spawn** | `spawn_*` | missing AC+ section, agent_file_missing, inflight | DENY spawn; parent fixes prompt |
| **semantic** | `semantic_*` / verdict FAIL blockers | AC not evidenced, cp pending, gaps.blocked | gate-repair or parent fix → re-gate |
| **finish** | `finish_*` | verify_pass_required, shape, finalize fail | no status change; parent fixes preconditions |
| **loop** | `loop_*` | `step_loop_forbidden` (next==finished) | fail-closed; не seed того же шага |
| **human** | `NEED_HUMAN:*` | schema_retry_exhausted, verify_no_verdict | outer HALT |

### Canon: post-finish anti-loop arm

```text
mb-finish ok
  → result.finished_step = S_done
  → result.next_step | next_phase | epic_done
  → if epic_done: no arm step; Handoff terminal phase / EPIC_DONE path
  → else:
       assert next_identity != S_done   # step id or phase key
       parent calls arm/seed ONLY for next_identity
       if arm would target S_done → ok:false loop_* ; FORBIDDEN silent re-run
```

**Кто пишет next:** только `mb-finish` (SoT). Parent не выбирает «ещё раз s03». Outer `prepare` следующей сессии читает уже обновлённый AC/index — согласовано с finish, не второй конкурирующий arm.

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как parent, я хочу typed mb-load bundle на старте. | P0 | load/SessionStart → ok + shard; pytest |
| US-002 | Как platform, я хочу halt при invalid AC shape на start. | P0 | ok:false / prepare HALT |
| US-003 | Как gate agent, я хочу перед финалом вызвать `validate-boundary` с JSON и править по `diagnostic_codes`, пока ok. | P0 | CLI/MCP validate-boundary: invalid→ok:false codes; valid→ok:true; agent re-calls; pytest |
| US-003b | Как platform, я хочу что SubagentStop всё равно re-validate (даже после pre-emit ok). | P0 | fixture: pre-emit ok + tampered emit → stop still schema fail / no PASS |
| US-004 | Как parent, я хочу schema-exhausted на boundary → NEED_HUMAN, не бесконечный spawn. | P0 | N+1 invalid at stop → marker; stop allowed only with marker |
| US-005 | Как parent, я хочу semantic FAIL → repair path, не schema-retry. | P0 | FAIL verdict → repair allow; schema path не вызывается |
| US-006 | Как parent, я хочу PASS → mb-finish hint + stop block без finish tool. | P0 | hint CLI; stop-gate block |
| US-007 | Как parent, я хочу mb-finish атомарно закрыть step и вернуть next ≠ finished. | P0 | result.next_step != finished_step; statuses completed |
| US-008 | Как platform, я хочу fail-closed если arm/next указывает на только что закрытый step. | P0 | `step_loop_forbidden`; index не active на S_done |
| US-009 | Как prepare, я хочу prompt = mb-load/mb-finish канон, не path-list SoT. | P1 | context_loop assert |
| US-010 | Как auditor, я хочу registry boundary→schema покрывает все managed gates. | P1 | pytest registry completeness |

#### Acceptance Scenarios — US-003

- **Given:** candidate JSON без поля `verdict` для `loop-gate-verdict/v1`
- **When:** `validate-boundary --schema loop-gate-verdict/v1 --json '…'`
- **Then:** `ok:false`, `diagnostic_codes` non-empty; агент чинит и вызывает снова → `ok:true` перед emit fence

#### Acceptance Scenarios — US-003b

- **Given:** agent получил pre-emit `ok:true`, но в финальном fence сломал JSON
- **When:** SubagentStop
- **Then:** boundary validate fail; no PASS sidecar; schema-retry / NEED_HUMAN — pre-emit ok не bypass

#### Acceptance Scenarios — US-004

- **Given:** тот же spawn исчерпал N schema-retries
- **When:** ещё один invalid emit
- **Then:** `NEED_HUMAN: schema_retry_exhausted:B-GATE`; stop-gate не требует PASS; FORBIDDEN silent continue work as PASS

#### Acceptance Scenarios — US-005

- **Given:** valid JSON `verdict: FAIL` + blockers
- **When:** SubagentStop
- **Then:** schema path не ретраится; hint gate-repair / fix; PreToolUse allow repair; FINISH DENY

#### Acceptance Scenarios — US-007 / US-008

- **Given:** mb-finish implement --step s03 ok
- **When:** result inspected / arm next
- **Then:** `finished_step=s03`, `next_step` in {s04, QA, …} and `next_step != s03`; попытка seed s03 → `loop_step_forbidden` / equivalent

### Functional Requirements (FR-###)

- **FR-001:** Session start → `MbLoadResult`; fail-closed при shape invalid.
- **FR-002:** prepare/build_prompt: primary = mb-load; path list не SoT.
- **FR-003:** Boundary registry: каждый managed gate/repair → schema_id + pydantic model; SubagentStop validate-before-accept.
- **FR-003a:** Единый `validate_boundary(schema_id, payload) -> ValidateResult` (`loop-validate-result/v1`); CLI `epic_resolve.py validate-boundary` (+ optional MCP); managed agent prompts: **перед emit вызови validate-boundary**.
- **FR-003b:** Pre-emit и boundary hook используют **один** helper; dual checker FORBIDDEN.
- **FR-004:** Schema-retry на **boundary** accept (счётчик tool_use_id/spawn); default N=2 gate / N=1 repair; escalate NEED_HUMAN. Agent-local pre-emit retries не считаются boundary N (пока не emit).
- **FR-005:** Error taxonomy schema vs semantic vs finish vs loop; hooks ветвят по классу (не один generic retry).
- **FR-006:** Semantic FAIL → repair/self-fix → re-verify; PreToolUse DENY repair без FAIL.
- **FR-007:** PASS → mb-finish hint; stop-gate требует `last_finish_tool` fingerprint.
- **FR-008:** `mb-finish-result/v1` включает `finished_step` + (`next_step` | `next_phase` | `epic_done`); единственный writer statuses+AC на FINISH.
- **FR-009:** Post-finish: arm/seed only for next; **HARD** `next_identity != finished_step`; diagnostic `loop_*` otherwise.
- **FR-010:** extract_verdict / stop-gate: JSON+sidecar only; prose VERDICT не machine.
- **FR-011:** Epic state: load fingerprint, schema_retry counters, last_finish_tool, last_finished_step, armed_after_finish.
- **FR-012:** Phase matrix IMPLEMENT P0; QA/ANALYZE/DECOMPOSE P1 same protocols.
- **FR-013:** Purge dual prose START/FINISH instructions in loop prompts.
- **FR-014:** Pytest: TM matrix ниже (schema-retry, taxonomy branch, anti-loop arm, load, finish).
- **FR-015:** Out of scope: Codex (053), pack (050), board (055), mid-turn JSON every message.

### Success Criteria

| ID | Измеримый результат | Проверка | Type |
|----|---------------------|----------|------|
| SC-001 | mb-load primary START | pytest + rg | outcome |
| SC-002 | schema-invalid ≠ PASS; retry then NEED_HUMAN | SubagentStop tests | outcome |
| SC-003 | semantic FAIL → repair, not schema-retry | pretool + stop tests | outcome |
| SC-004 | PASS → mb-finish required | stop-gate | outcome |
| SC-005 | finish next ≠ finished | mb_finish + arm tests | outcome |
| SC-006 | re-arm same step fail-closed | pytest loop_* | outcome |
| SC-007 | no prose VERDICT machine path | rg + purge tests | outcome |

### Assumptions

- mb_load/mb_finish modules exist; 057 = enforce + protocol + anti-loop.
- Mid-turn = prose tools; boundaries only = JSON.
- N schema-retries настраиваем env позже; default в FR-004.
- Outer check-after fingerprint stall остаётся; anti-loop step **дополняет**.

### Clarifications

- Chat 2026-09-02 + refine schema-retry / arm next≠current.
- Queue: after 056, before 053.

### AC−

1. Нет dual START multi-Read = SoT рядом с mb-load.  
2. Нет silent PASS / regex salvage на schema fail.  
3. Нет schema-retry на semantic FAIL (и наоборот).  
4. Нет FINISH completed без mb-finish.  
5. Нет re-arm / active того же step сразу после его finish.  
6. Нет «LLM validated pydantic» без `ValidateResult.ok` от tool/hook.  
7. Нет второго validate-checker с иной семантикой, чем boundary.  
8. Нет mid-turn JSON obligation на каждый tool call (кроме machine boundaries).  
9. Нет scope creep в 053/055/050.

---

## Техника / архитектура (HOW)

- **Стек:** Python 3.12, pydantic v2, `loop/mb_load`, `loop/mb_finish`, harness hooks, `epic_resolve.py`.
- **Стратегия:**  
  1) `validate_boundary` + CLI `validate-boundary` + registry.  
  2) Agent prompts: pre-emit call validate; SubagentStop always re-validate + schema/semantic branch + counters.  
  3) mb-finish result fields next_* + arm guard.  
  4) stop-gate last_finish_tool + loop marker.  
  5) prepare/SessionStart mb-load SoT.  
  6) purge prose; pytest.
- **Модули:**  
  - new: `loop/validate_boundary.py` (или `loop/schemas/validate.py`) + `loop-validate-result/v1`;  
  - CLI wire в `epic_resolve.py validate-boundary`;  
  - `loop/boundary_registry.py` (agent→schema_id);  
  - `harness/hooks/subagent-stop.py`, `_lib.py` (import same helper; retry counters, taxonomy);  
  - `loop/mb_finish/schemas.py` + `impl.py` (next_*);  
  - `epic/core.py` / transition arm guard;  
  - `stop-gate.py`, `agent-pretool.py`, `session-start.py`, `context_loop.py` / agent presets (pre-emit instruction).
- **Наблюдаемость:** diagnostic_codes from validate tool + boundary; retry counters; finished/next in finish result.

## Eng review spine

### Data flow (ASCII)

```text
[prepare] -> [B-START mb-load] --schema fail--> HALT
                    |
                    v
              [parent work]
                    |
                    v
         [B-SPAWN validate sections] --spawn fail--> DENY
                    |
                    v
         [child] candidate JSON
                    |
                    v
         [validate-boundary CLI/MCP] <-- same helper
              | ok=false: fix, recall
              v ok=true
         [emit fence] -> [B-GATE SubagentStop = same helper again]
              |                |
         schema fail      semantic FAIL
              |                |
         re-emit <=N      [B-REPAIR] -> re-gate
              |                |
         exhausted           PASS
              |                |
         NEED_HUMAN            v
                         [B-FINISH-REQ/RES]
                               |
                         next != finished?
                          |           |
                         yes         no -> loop_* fail-closed
                          v
                      [B-ARM next]
                          v
                   [stop-gate allow]
                          v
                   [check-after / next session]
```

### Failure matrix

| Component / link | Failure | Detection | User/system response | Test ID |
|------------------|---------|-----------|----------------------|---------|
| AC shape | load ok:false | B-START | HALT | TM-001 |
| missing shard | diagnostic | B-START | fail-closed | TM-002 |
| validate-boundary invalid | schema_* | CLI tool | ok:false codes; agent fix | TM-003 |
| pre-emit ok + bad emit | schema_* | B-GATE re-validate | no PASS; retry | TM-003b |
| schema exhausted | counter > N | B-GATE | NEED_HUMAN | TM-004 |
| dual checker drift | AC− | unit | same helper only | TM-003c |
| verdict FAIL | semantic | B-GATE | repair, no FINISH | TM-005 |
| repair without FAIL | spawn | pretool | DENY | TM-006 |
| stop w/o mb-finish | finish_* | stop-gate | block | TM-007 |
| mb-finish w/o PASS | finish_* | CLI | ok:false | TM-008 |
| next == finished | loop_* | finish/arm | fail-closed | TM-009 |
| prose VERDICT accept | AC− | extract | purge | TM-010 |
| prepare path-SoT | dual path | rg/prompt | purge | TM-011 |

### Eng spine self-check

| Dimension | Score 1–5 | Gap / action |
|-----------|-----------|--------------|
| Data flow complete | 5 | — |
| Failure coverage | 5 | taxonomy + loop |
| Testability | 5 | TM-001…011 |

## Replacement / sunset (brownfield)

### A. Code / modules

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| prepare path-list as SoT | mb-load instruction + bundle | delete in-epic |
| FINISH «Write activeContext» | mb-finish only | delete in-epic |
| Optional SessionStart skip load | always load EPIC_LOOP | delete in-epic |
| prose VERDICT machine path | JSON+sidecar | delete in-epic |
| single no-verdict retry without taxonomy | schema-retry + semantic branch | delete in-epic |
| ad-hoc / duplicate JSON checkers | one `validate_boundary` | delete in-epic |
| «self-check without tool» as gate | validate-boundary CLI + hook | delete in-epic |
| finish without next_* / no loop check | typed next + next≠finished | delete in-epic |
| stop FINISH без last_finish_tool | require fingerprint | delete in-epic |

### B. Entrypoints / deploy

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| START = only Read | mb-load / SessionStart | delete in-epic |
| FINISH = Write AC | mb-finish CLI | delete in-epic |
| next step = agent guesses | finish result next_* + arm guard | delete in-epic |

### C. Fallbacks / soft-fail

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| invalid JSON → regex salvage | schema-retry / NEED_HUMAN | delete in-epic |
| invalid → accept prose | fail-closed | delete in-epic |
| re-run same sNN after finish | loop_* | delete in-epic |
| silent degraded load | halt or explicit counter | delete in-epic silent |
| mb-finish fail → manual AC | JSON error only | delete in-epic |

<a id="qa-consumes"></a>
## QA consumes (test plan)

### Scope under test

- B-START load, B-GATE schema-retry/taxonomy, B-REPAIR pretool, B-FINISH next≠finished, B-ARM loop guard, stop-gate, prepare prompt
- Out: Codex (053), board (055), full suite green (056)

### Test matrix

| ID | Priority | Scenario | Command / fixture | Expected | Maps FR/AC |
|----|----------|----------|-------------------|----------|------------|
| TM-001 | P0 | shape invalid start | pytest mb_load/session_start | ok:false/halt | FR-001 US-002 |
| TM-002 | P0 | bundle has work shard | pytest load_session | files ⊇ sNN | FR-001 US-001 |
| TM-003 | P0 | validate-boundary CLI invalid/valid | pytest validate_boundary | ok:false→ok:true | FR-003a US-003 |
| TM-003b | P0 | pre-emit ok + bad emit | pytest subagent-stop | no PASS; re-validate | FR-003b US-003b |
| TM-003c | P0 | stop uses same helper as CLI | pytest import/identity | one function | FR-003b AC− |
| TM-004 | P0 | schema exhausted at boundary | pytest counter | NEED_HUMAN marker | FR-004 US-004 |
| TM-005 | P0 | FAIL semantic → repair | pytest pretool+stop | repair allow; no schema-retry | FR-005/006 US-005 |
| TM-006 | P0 | repair without FAIL DENY | pytest agent-pretool | DENY | FR-006 |
| TM-007 | P0 | stop without finish | pytest stop-gate | block | FR-007 US-006 |
| TM-008 | P0 | mb-finish ok + next | pytest mb_finish | next≠finished; completed | FR-008 US-007 |
| TM-009 | P0 | arm same step | pytest arm/finish guard | loop_* fail | FR-009 US-008 |
| TM-010 | P0 | no prose VERDICT SoT | rg + extract tests | fail-closed | FR-010 |
| TM-011 | P1 | prepare mb-load SoT | pytest context_loop | instruction; no path-SoT | FR-002 US-009 |

### Regression notes

- Не ослаблять 054 JSON purge.  
- Fingerprint stall check-after сохраняется.  
- Не требовать JSON на mid-turn tools.

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| CLARIFY / Product probe | L3 | skip+reason | taxonomy clear + refine in §Product probe / Canon |
| Technology axiom | Required | done | expanded table |
| Eng review spine | Required | done | data flow + failure matrix |
| QA consumes ≥3 TM | Required | done | TM-001…011 |
| Sunset A+B+C | Required | done | Replacement |
| CREATIVE | Optional | n/a | — |
| Independent Test behavior | Required | done | US tests observable |

## Plan review batch log

| Pass | Item | Resolution |
|------|------|------------|
| Product | Schema-retry vs repair | taxonomy HARD in plan |
| Product | Anti-loop arm | FR-009 + US-008 P0 |
| Product | Agent calls validate fn | FR-003a pre-emit + boundary re-validate |
| Eng | LLM pydantic in head | FORBIDDEN; tool/hook only |
| Eng | Mid-turn JSON | cut / AC− |
| Eng | Dual arm | finish SoT next; prepare reads result |

## Risks / cut_list

| Risk | Mitigation |
|------|------------|
| Token SessionStart | size cap; fingerprint+paths |
| stop-gate breaks chat | EPIC_LOOP + epic active only |
| Counter state loss across spawns | key by tool_use_id + session |
| next_phase vs next_step ambiguity | finish result discriminant epic_done \| next_step \| next_phase |

**cut_list:** MCP polish; every mid-turn JSON; DSH bridge; optional agents beyond managed gates (P1 registry completeness only for managed).

## Decompose input map (черновик)

| Slice | Covers | Notes |
|-------|--------|-------|
| s01 | inventory gaps vs FR + registry draft | read-only |
| s02 | B-START SessionStart + prepare mb-load | FR-001/002 |
| s03 | validate_boundary + CLI + registry; SubagentStop same helper + schema-retry | FR-003/003a/003b/004/005 |
| s04 | semantic FAIL → repair + PASS hint | FR-006/007 |
| s05 | mb-finish next_* + arm loop guard | FR-008/009 |
| s06 | stop-gate last_finish_tool + NEED_HUMAN schema exhausted | FR-007/004 |
| s07 | pytest TM-001…011 | FR-014 |
| s08 | legacy-fallback-purge | AC− |

→ DECOMPOSE уточнит ids/AC mapping.

## Next

**BACK DECOMPOSE** `T-HUB-057-loop-session-json-contract` (после 054–056 в loop order).
