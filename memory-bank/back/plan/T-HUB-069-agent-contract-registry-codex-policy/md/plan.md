# [T-HUB-069 | agent-contract-registry-codex-policy] PLAN

**Дата:** 2026-09-05  
**Режим:** BACK PLAN  
**Уровень:** L3–L4  
**Статус:** active  
**Clarify:** `memory-bank/back/clarify/clarify-20260905-workflow-loop-audit.md`  
**Roadmap:** `memory-bank/back/roadmap/queue.yaml` · batch `workflow-loop-20260905`  
**Deps:** **hard T-HUB-064** (video agents must exist in manifest before registry/parity includes them). Soft T-HUB-053 (hooks parity), T-HUB-039 (verify agents). P2 «один Contract Registry generating all docs» = **Appetite cut** — this epic = **policy fingerprint + Codex mapping + drift fail**, not generated README encyclopedia.  
**Skills:** writing-plans · architecture-patterns · python-testing-patterns  
**Источник:** audit `01` Codex TOML drops tools/disallowedTools · `_lib.CONTRACTS` vs prompt · `07` P0 Codex + P2.1 registry

---

## Контекст

- **req:** Materialized Codex agent либо **эквивалентен** source frontmatter policy (`tools`, `disallowedTools`, `maxTurns`, managed/verdict flags), либо **явно** `unsupported_runtime_policy` fail-closed. Injected `_lib.CONTRACTS` hash-совпадает с prompt SoT. Нет silent «TOML есть = parity green» при потерянных deny tools.
- **gap:**
  1. `codex_agent_toml.py` writes only name/description/developer_instructions.
  2. Parity checks file presence, not policy matrix.
  3. `_ALWAYS_INJECT` / CONTRACTS diverge from prompts and omit video/sunset (064/063 leftover; 069 consumes after they exist).
  4. Six behavior sources (audit 01 §1) not generated from one typed model — **full generate-all = cut**; minimum = typed **PolicyRecord** + fingerprint + tests.
- **refs:** `harness/agents/*.md`; `loop/runtime_materializers/codex_agent_toml.py`; `harness/hooks/_lib.py` CONTRACTS; `.codex/agents/*.toml`; audit 01 §3 P0/P1.
- **Не:** duplicate Claude hooks (065); finish journal (068); skill FS (062); doctor graph (067) except fingerprint may be consumed later.

**CREATIVE need:** нет (Codex capability matrix is engineering mapping, not visual).

---

## Technology axiom

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Source policy | parse agent markdown frontmatter → PolicyRecord | TOML-only as SoT |
| Codex emit | mapped fields **or** unsupported fail | silent drop disallowedTools |
| Injected contract | `contract_id` + `source_sha256` match prompt | drift start allowed |
| Parity | source prompt set ∪ mapping matrix | presence-only TOML |
| Docs matrix | optional generated later | blocking on generated README (P2.4 cut) |

---

## Продуктовая спека (WHAT)

1. For each managed agent in `harness/agents/*.md` (after 064: 11 files): PolicyRecord extracted.
2. Codex materialize writes fingerprint + mapped native fields Codex supports; unsupported required fields → **do not** emit usable agent without `unsupported_runtime_policy` (fail materialize or emit + doctor fail).
3. Hook inject includes contract fingerprint; mismatch → `agent_contract_drift` block spawn.
4. Parity test: verify-implement (and video after 064) disallowed Write/Edit still enforced via hook if TOML cannot native-deny.
5. Equivalence matrix documented in-repo as yaml/json **checked in tests**, not only markdown.

### Product probe

| # | Question | Answer | Impact |
|---|----------|--------|--------|
| 1 | Reframe | Codex agent выглядит materialized, deny — prose | Fail-closed mapping |
| 2 | Wedge | fingerprint + disallowedTools mapping test on verify-implement | P0 |
| 3 | Pre-mortem | Put policy in developer_instructions only, parity still presence | FR matrix ≠ presence |
| 4 | Adoption | runtime-sync / materialize | |
| 5 | Leverage | existing frontmatter; hook already deny tools for Claude | |
| 6 | Appetite | 4 days | cut: generate README/schema tables; generate all CONTRACTS from AST |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как Codex parent, я не хочу verify-implement с native Write если source forbids. | P0 | mapping: unsupported → hook policy still deny **and** fingerprint; or TOML field if exists |
| US-002 | Как CI, я хочу fail если TOML silent-dropped required deny. | P0 | fixture frontmatter disallowedTools not in mapping → fail `unsupported_runtime_policy` |
| US-003 | Как SubagentStart, я хочу drift CONTRACTS vs prompt hash block. | P0 | mutate CONTRACTS string → `agent_contract_drift` |
| US-004 | Как operator, я хочу video verify in inject set after 064. | P1 | `_ALWAYS_INJECT` contains verify-edit |

#### Acceptance Scenarios — US-002

- **Given:** agent md with `disallowedTools: ["Write","Edit","Agent"]`
- **When:** materialize Codex
- **Then:** either TOML encodes deny **or** materialize/parity fails with `unsupported_runtime_policy` unless hook-enforcement row exists in matrix with test proving stop/start still blocks those tools

### Functional Requirements

- **FR-001:** `PolicyRecord` pydantic: name, tools, disallowedTools, maxTurns, overlay, managed, mode, verdict, allow_worktree, requires_model, default_loop, default_chat, color (color may map n/a).
- **FR-002:** Parser from harness/agents frontmatter; extra unknown keys listed not silently ignored if `managed: true`.
- **FR-003:** Codex mapping table yaml: field → `native` | `hook` | `unsupported`. Required deny (Write/Edit/Agent on verify-*) cannot be `unsupported` without hook row.
- **FR-004:** Generated TOML includes `policy_fingerprint` and `source_prompt_sha256` (as TOML comments or `[metadata]` if Codex allows; if parser strips unknown — still write sidecar `.codex/agents/<id>.policy.json`).
- **FR-005:** Parity: for each prompt file, mapping applied; fail codes `codex_policy_dropped`, `unsupported_runtime_policy`, `agent_contract_drift`.
- **FR-006:** `_lib.CONTRACTS` keyed by agent; build or checksum vs prompt section; SubagentStart compares.
- **FR-007:** `_ALWAYS_INJECT` derived from PolicyRecord.managed/verdict **or** phase registry ∪ manifest — not hardcoded software-only set (consume 064 ids).
- **FR-008:** sunset-inventory: inject contract after 063; 069 must include if managed.
- **FR-009:** Kind I: agent md may keep human tools list; runtime must not be weaker than md.
- **FR-010:** Explorer Write deny: same mapping (already Claude native); Codex path must not grant Write.
- **FR-011:** Do not invent Codex CLI flags that do not exist; prefer hook enforcement documented.
- **FR-012:** runtime-sync --check includes fingerprint mismatch.
- **FR-013:** Tests mutation: remove disallowedTools from TOML/sidecar → fail parity.
- **FR-014:** Generic `@verify` in machine commands (audit P2.3) — **out of this epic** unless one-line Kind I if we touch spawn docs; cut.
- **FR-015:** Generated loop/schemas/README from registry — **cut** (P2.4).

### Success Criteria

| ID | Result | Check | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | silent drop deny fails CI | pytest | outcome |
| SC-002 | fingerprint in sidecar/TOML | files | outcome |
| SC-003 | CONTRACTS drift blocks start | hook test | outcome |
| SC-004 | video agents in inject after 064 | set membership | outcome |
| SC-005 | verify-implement Codex not weaker than md | matrix test | outcome |

### Assumptions

- Codex TOML schema may never grow tools[] — then hook is the native enforcement (must be tested, not hoped).
- Claude continues to read markdown frontmatter natively.

## AC

1. PolicyRecord for all managed agents.
2. Materialize/parity fail-closed on undroppable policy.
3. Fingerprint + drift spawn block.
4. Inject set includes all finish/managed agents (software+video+repair+sunset).
5. Mapping yaml tested.

### AC−

1. Нет presence-only Codex parity.
2. Нет silent drop disallowedTools.
3. Нет CONTRACTS text ≠ prompt without fail.
4. Нет hardcoded software-only ALWAYS_INJECT after 064.
5. Нет «policy in developer_instructions only» as sufficient Independent Test.

## HOW

- `loop/runtime_materializers/agent_policy.py` + mapping yaml + extend `codex_agent_toml.py` + `_lib.py` fingerprint + tests `loop/tests/test_codex_agent_policy.py`, hook start drift.

## Eng review spine

### Data flow

```text
[harness/agents/*.md] -> [PolicyRecord]
                      -> [mapping yaml] -> [TOML + sidecar fingerprint]
                      -> [parity]
[SubagentStart] -> [CONTRACTS + sha] vs PolicyRecord.source_sha
                      mismatch -> agent_contract_drift (no spawn)
[tools deny] -> [Codex native OR hook]
```

### Failure matrix

| Component | Failure | Detection | Response | Test ID |
|-----------|---------|-----------|----------|---------|
| drop disallowedTools | Write on verify | parity | unsupported/fail | TM-001 |
| stale CONTRACTS | two HARD texts | sha | drift block | TM-002 |
| missing video inject | no contract | set | include | TM-003 |
| presence-only parity | false green | mutation TOML | fail | TM-004 |
| unknown frontmatter | lost field | extra list | fail managed | TM-005 |
| sidecar stripped | fingerprint gone | runtime-sync | fail | TM-006 |
| explorer Write on Codex | weaker | mapping | deny hook | TM-007 |
| generate README required | scope creep | cut | n/a | — |

### Eng spine self-check

| Dimension | Score | Gap |
|-----------|-------|-----|
| Data flow complete | 5 | |
| Failure coverage | 5 | |
| Testability | 5 | no live Codex needed |

## Replacement / sunset

### A

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| TOML name/desc/instructions only as complete | mapped+fingerprint | delete in-epic (the incompleteness) |
| hardcoded ALWAYS_INJECT software set | derived set | delete in-epic |
| presence-only REQUIRED_CODEX_AGENTS exclusivity | policy matrix (064 already source glob) | delete leftover in-epic |

### B

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| runtime-sync green on truncated TOML | fingerprint check | delete in-epic |

### C

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| silent materialize weaker agent | fail-closed | delete in-epic |
| prose deny only as SoT | hook+matrix | delete in-epic as sufficient |

### I

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| docs «Codex TOML = full agent» | mapping honesty | delete in-epic |
| P2 generate all docs | cut | keep manual rationale |

## QA consumes

<a id="qa-consumes"></a>

| ID | Priority | Scenario | Command | Expected | Maps |
|----|----------|----------|---------|----------|------|
| TM-001 | P0 | drop deny fixture | pytest policy | unsupported_runtime_policy or equivalent hook row + fail if neither | US-002 |
| TM-002 | P0 | CONTRACTS sha mismatch | hook start | agent_contract_drift | US-003 |
| TM-003 | P0 | verify-implement mapping | pytest | not weaker | US-001 |
| TM-004 | P0 | fingerprint written | sidecar/TOML | present | FR-004 |
| TM-005 | P1 | ALWAYS_INJECT has verify-edit | unit | in set | US-004 |
| TM-006 | P1 | explorer Codex Write | mapping | denied | FR-010 |

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| CLARIFY / Product probe | L3 | done | |
| Eng review spine | L2+ | done | |
| §0.11 | mapping yaml | in HOW | |
| CREATIVE | n/a | n/a | |
| qa_consumes | L2+ | done | |
| Plan review batch | L2+ | done | |

## Plan review batch log

| Phase | Auto-resolved | Deferred |
|-------|---------------|----------|
| Product | Fail-closed mapping, not generate-all | P2.4 README gen |
| Eng | Sidecar fingerprint if TOML unknown keys stripped | generate CONTRACTS from AST |

## До DECOMPOSE

1. s01 — PolicyRecord + red tests silent drop.
2. s02 — mapping yaml + materialize fingerprint/sidecar.
3. s03 — parity mutation.
4. s04 — SubagentStart drift.
5. s05 — ALWAYS_INJECT derived (video+sunset).
6. s06 — Kind I + runtime-sync check.
7. s07 — purge presence-only assertions.

## Appetite

| Поле | Значение | Описание |
| :--- | :--- | :--- |
| `timebox_days` | `4` | |
| `cut_list` | `['generate schemas README', 'generate CONTRACTS AST', 'generic @verify purge', 'Cursor Codex IDE']` | P2.1 full registry later |

## Independent Test

- PASS: dropping deny from artifact fails CI; drift blocks start; fingerprint exists.
- FAIL: «TOML file exists for each md»; «deny mentioned in developer_instructions».

## Следующий режим

→ BACK DECOMPOSE T-HUB-069 after 064 (and after 063 if sunset inject asserted in same shard — queue places 069 last).

**CREATIVE need:** нет.
