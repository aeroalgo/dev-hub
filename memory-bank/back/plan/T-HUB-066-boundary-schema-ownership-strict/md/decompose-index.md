# Реестр шагов (Decompose index)

**Plan ID:** T-HUB-066-boundary-schema-ownership-strict  
**План:** [plan.md](plan.md)  
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**  
**Дата:** 2026-09-06  
**Режим:** BACK DECOMPOSE  
**Уровень:** L3–L4  
**Granularity:** 6 sNN (band 5–8; L3/L4 ≤9; advisory floor плана = 7; red-tests + Wire required schema + collab extra=forbid слиты в s01 как один contract boundary; apply≠purge — fence/ownership/repair отдельно; Kind I + README в s05; leftover → s06)

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml` — `.cursor/templates/decompose/epic-step.yaml`.

> **Path (layout v2 HARD):** этот файл = `plan/T-HUB-066-boundary-schema-ownership-strict/md/decompose-index.md`. Machine = `yaml/decompose-index.yaml`. Shards = `yaml/steps/`.  
> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `yaml/decompose-index.yaml`.** Этот файл в IMPLEMENT не грузить.  
> **status SoT = `decompose-index.yaml` only.**  
> **Ladder:** s01 add (Wire schema required + extra=forbid + one parse function) → s02 wire+enforce (SubagentStop fence-only; mutation on bypass) → s03 enforce ownership vs in-flight (no schema-retry) → s04 repair parent FAIL invariants → s05 Kind I README/prompts → s06 purge leftover A+B+C+I.

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность (сессия DECOMPOSE, не `impl:`) |
| `tdd` / `python-testing-patterns` / `modern-python` / `python-anti-patterns` | Core(4) в каждом code sNN |
| `python-type-safety` | Wire* vs Internal* / required discriminator / extra=forbid |
| `python-error-handling` | protocol fail, ownership mismatch, repair invalid, fail-closed |

**Per-step:** skills gate в каждом `sNN` (`workflow-decompose.mdc`). **FORBIDDEN в `impl:`:** writing-plans · brainstorming · executing-plans · breakdown-plan.

## Requirements coverage (plan → steps)

> **HARD:** каждый AC+ / AC− / FR / NFR (или UI AC) → ≥1 шаг, иначе явный `out_of_scope` + `follow_up: T-…` **уже в** `roadmap/queue.yaml`.  
> **FR verbatim (HARD):** колонка **Plan FR text** = дословный текст / nouns из `plan.md`. Remap FR = FAIL ANALYZE (`layout_dilution`).  
> Notes `deferred`/`partial` без `follow_up: T-…` = FAIL (`validate-decompose-tree`).

| Req ID | Plan FR text (verbatim) | sNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | Split Wire* vs Internal* or `require_discriminator=True` on validate_boundary external. | s01, s06 | Wire schema required; Internal may keep defaults |
| FR-002 | Replace bypass condition with `fence_data is not None` (and documented trusted adapter envelope **only if** signed — default none). | s02, s06 | signed envelope = Appetite cut |
| FR-003 | Ownership fields required for loop finish gates: `agent_id`, `epic_id`, `step_id`, `session_id`, `recorded_at` ISO, optional `evidence_sha256` format. | s03 | ISO junk → TM-008 |
| FR-004 | Compare record identity to in-flight spawn state; mismatch → `semantic_ownership_mismatch`. | s03 | QA TM-003 |
| FR-005 | BLOCKED allowed only for agents/phases that declare it (verify-qa). | s03 | Failure matrix TM-007 / QA TM-006 |
| FR-006 | Repair: parent_evidence_id; remaining/fixed disjoint; done ⇒ remaining empty; fail ⇒ remaining or diagnostic; agent_id=gate-repair. | s04 | `bin/pytest loop/tests/test_repair_result.py harness/hooks/tests/test_gate_repair.py -q --tb=line -k 'remaining or leftover or parent or disjoint'` — done+remaining invalid; parent_evidence_id required (QA TM-004 / SC-004) |
| FR-007 | Schema errors retry; ownership **no** retry (audit 01). | s02, s03 | schema retry stays; ownership escalate |
| FR-008 | Codex collab extra=forbid; same parse function. | s01, s02 | `_CollabGateVerdictFence` → canonical parser |
| FR-009 | Mutation tests on bypass condition (08 §5). | s02 | invert `or not data.get("verdict")` |
| FR-010 | Kind I: agent prompts «no fence = FAIL» remains true in runtime. | s02, s05 | prompts already say fence; runtime must match |
| FR-011 | sunset records (after 063) get same fence+schema rules. | s02, s06 | hard dep 063 done; QA TM-007 |
| FR-012 | `loop/schemas/README.md` stale verdict.py — rewrite in-epic Kind I (audit 04/06). | s05, s06 | SKIP → PASS/FAIL/BLOCKED |
| US-001 | Как stop-gate, я не принимаю PASS из payload без fence. | s02 | Independent Test mutation |
| US-002 | Как validator, я отвергаю missing schema on wire. | s01 | pytest extra/missing |
| US-003 | Как loop, я отвергаю verdict другого step_id. | s03 | `semantic_ownership_mismatch` |
| US-004 | Как parent, я вижу repair привязанный к FAIL blockers. | s04 | repair fixture |
| US-005 | Как Codex, я не принимаю extra fields. | s01 | collab extra=forbid |
| US-001 Given/When/Then | Given: SubagentStop data.verdict=PASS, message without fence. When: hook runs. Then: validation path executed; not record_verdict PASS; retry or protocol fail | s02 | |
| SC-001 | no-fence + payload verdict ≠ PASS | s02 | hook test |
| SC-002 | missing schema invalid | s01 | pytest |
| SC-003 | stale step mismatch code | s03 | pytest |
| SC-004 | repair done with remaining invalid | s04 | pytest |
| SC-005 | collab extra field invalid | s01 | pytest |
| AC+1 | Fence required for verify/repair/sunset machine agents. | s02, s06 | |
| AC+2 | schema required on wire. | s01 | |
| AC+3 | Ownership mismatch fail-closed without schema-retry. | s03 | |
| AC+4 | Repair linked to parent FAIL. | s04 | |
| AC+5 | Codex parser parity extra=forbid. | s01 | |
| AC−1 | Нет bypass `or not data.get("verdict")`. | s02, s06 | |
| AC−2 | Нет extra=ignore on collab. | s01, s06 | |
| AC−3 | Нет schema default on external payload. | s01, s06 | |
| AC−4 | Нет retry on ownership. | s03, s06 | |
| AC−5 | Нет repair done with leftover blockers. | s04, s06 | |
| Product spec 1 | No-fence verify completion cannot record PASS. | s02 | |
| Product spec 2 | Missing schema field on wire → invalid. | s01 | |
| Product spec 3 | Stale session/step/epic/agent ≠ current in-flight → ownership fail, no retry-as-schema. | s03 | |
| Product spec 4 | Repair `done` requires empty remaining; fixed ⊆ parent FAIL. | s04 | |
| Product spec 5 | One parser function for gate/repair/sunset fences. | s01, s02 | |
| Technology axiom Wire model | `schema` required, extra=forbid; FORBIDDEN default schema on external payload | s01, s06 | |
| Technology axiom Verdict SoT | JSON fence body; FORBIDDEN hook `data.verdict` without fence | s02, s06 | |
| Technology axiom Ownership fail | `semantic_ownership_mismatch`; FORBIDDEN schema-retry on wrong step_id | s03 | |
| Technology axiom Repair | parent FAIL id + blocker subset; FORBIDDEN done with leftover blockers | s04 | |
| Technology axiom Codex parser | same canonical parser; FORBIDDEN extra=ignore collab model | s01 | |
| Failure matrix TM-001 | no fence + payload PASS / bypass / mutation test / fail | s02 | |
| Failure matrix TM-002 | missing schema / default accept / wire test / invalid | s01 | |
| Failure matrix TM-003 | extra field / ignore collab / extra=forbid / fail | s01 | **не** QA TM-003 |
| Failure matrix TM-004 | stale session / wrong PASS / ownership / mismatch | s03 | |
| Failure matrix TM-005 | repair done+remaining / inconsistent / validator / invalid | s04 | |
| Failure matrix TM-006 | schema fail retried as repair / wrong agent / taxonomy / schema retry only | s02, s04 | |
| Failure matrix TM-007 | BLOCKED on verify-implement / illegal / enum/phase / fail | s03 | QA table TM-006 |
| Failure matrix TM-008 | ISO timestamp junk / parse / validator / fail | s03 | recorded_at ISO |
| QA TM-001 | no-fence payload PASS / hook test / not PASS / US-001 | s02 | |
| QA TM-002 | missing schema / test_validate_boundary / invalid / US-002 | s01 | |
| QA TM-003 | stale step_id / pytest / semantic_ownership_mismatch / US-003 | s03 | **не** Failure matrix TM-003 |
| QA TM-004 | repair done leftover / pytest / invalid / US-004 | s04 | |
| QA TM-005 | extra collab / test_codex_collab / invalid / US-005 | s01 | |
| QA TM-006 | BLOCKED implement / pytest / invalid / FR-005 | s03 | |
| QA TM-007 | sunset no fence after 063 / hook / fail / FR-011 | s02, s06 | |
| Independent Test PASS | no-fence not PASS; stale step mismatch code; repair invariant. | s02, s03, s04 | |
| Independent Test FAIL | «GateVerdictRecord extra=forbid unit» without stop hook path. | s01–s06 | dilution = FAIL ANALYZE |
| Appetite cut signed envelope | Trusted adapter envelope out of scope (cut). | — | `cut_list`; Assumptions |
| Appetite cut retry_policy/v1 | full retry_policy/v1 productization | — | `cut_list`; retry counters stay, classification stub OK |
| Out of scope explorer | Explorer remains no-verdict. | — | Assumptions |
| Out of scope 063 | register sunset (063) | — | hard dep already done; this epic applies ownership to sunset fences |
| Out of scope 065 | duplicate hooks (065) | — | follow_up: T-HUB-065-duplicate-hooks-runtime-entrypoint |
| Out of scope 068 | finish transaction (068) | — | follow_up: T-HUB-068-start-finish-transaction-boundary |
| Out of scope 069 | full retry_policy registry / agent contract | — | follow_up: T-HUB-069-agent-contract-registry-codex-policy (cut_list retry_policy) |

## Stages coverage (plan/canon → steps)

> Каждый этап/фаза плана и канон-дока → sNN. Не растворять в layout.

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| Wire vs Internal / required discriminator | plan §FR-001 · §Technology axiom Wire model · gap 1 | s01 |
| Codex collab extra=forbid + same parse | plan §FR-008 · gap 3 · Failure matrix TM-003 | s01 |
| Data flow: extract fence missing → protocol fail/retry schema | plan §Data flow | s02 |
| Data flow: validate_boundary schema required | plan §Data flow · §HOW | s01, s02 |
| Data flow: ownership vs in-flight → NEED_HUMAN/block | plan §Data flow | s03 |
| Data flow: record_verdict / repair store | plan §Data flow | s02, s04 |
| Stop condition rewrite + mutation | plan §До DECOMPOSE #3 · FR-002/009 · gap 2 | s02 |
| Ownership vs in-flight | plan §До DECOMPOSE #4 · FR-003/004/005/007 | s03 |
| Repair parent constraints | plan §До DECOMPOSE #5 · FR-006 · gap 4 | s04 |
| Kind I README + prompts | plan §До DECOMPOSE #6 · FR-010/012 | s05 |
| Purge bypass leftover + SKIP docs | plan §До DECOMPOSE #7 · Replacement A/C/I | s06 |
| Add → wire → enforce → purge | behavior-first §3 | s01 add; s02–s04 wire/enforce; s05 Kind I; s06 purge |
| QA consumes TM-001…007 | plan §QA consumes | s01–s04, s06 |
| Independent Test | plan §Independent Test | s02, s03, s04 |
| Sunset fence+schema after 063 | plan FR-011 · hard dep T-HUB-063 | s02, s06 |
| retry counters stay; add classification schema vs semantic | plan §HOW | s02, s03 |

## Outcome map (plan → steps)

> **HARD:** не ужимать Goal/NFR плана до infra-slug. Map ≠ замена шагов.

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| No-fence + payload PASS не записывает PASS (SoT = fence) | s02, s06 |
| Missing `schema` on wire → invalid (не internal default) | s01, s06 |
| Stale step/epic/session/agent → `semantic_ownership_mismatch`, без schema-retry | s03 |
| Repair `done` с leftover remaining — invalid; fixed ⊆ parent FAIL | s04 |
| Codex extra field → invalid; same canonical parser | s01 |
| BLOCKED только у агентов/фаз, что декларируют (verify-qa); verify-implement — fail | s03 |
| Sunset fence+schema те же правила, что gate/repair | s02, s06 |
| README не врёт `verdict.py` / SKIP; prompts «no fence = FAIL» = runtime | s05, s06 |
| Independent Test PASS: no-fence not PASS; stale mismatch code; repair invariant | s02 + s03 + s04 |
| Independent Test FAIL dilution: unit extra=forbid без stop hook path | s01–s06 (не done) |
| Appetite cut: signed envelope / full retry_policy product | — (`cut_list`) |
| Out of scope: 065 dual hooks, 068 finish txn, explorer no-verdict | queue / Assumptions |

## Replacement cleanup (plan → steps)

> **HARD (brownfield replace):** каждая поверхность plan sunset **A/B/C/I** → ≥1 `sNN` с непустым `deletes:` (или out_of_scope + follow-up epic **уже в** `roadmap/queue.yaml`).  
> Completeness ladder: **add → wire → enforce → purge**. Add-only на sole-path FR = FAIL (`optional_sot`).  
> Kind B CLI = `n/a` keep (same validate-boundary) — не отдельный cutover.  
> Финальный `s06-legacy-fallback-purge` с `sunset_inventory` + `grep_control` по каждой строке ≠ n/a.

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `if fence_data is not None or not data.get("verdict")` (`harness/hooks/subagent-stop.py`) | A | `fence_data is not None` only | s02, s06 | no | plan A `if fence or not verdict` |
| `_CollabGateVerdictFence` `extra="ignore"` (`loop/codex_collab_verdict.py`) | A | extra=forbid + canonical parse | s01, s06 | no | |
| `schema_version: str = Field(alias="schema", default=SCHEMA_…)` on **wire** validate (`gate_verdict.py` / `repair_result.py` / sunset via registry) | A | Wire* required / `require_discriminator=True` on external | s01, s06 | no | Internal defaults OK |
| tests/comments that treat missing schema as valid on wire | A | rewrite asserts invalid | s01, s06 | no | |
| tests that treat payload `data.verdict` as SoT without fence | A | rewrite: protocol fail / not PASS | s02, s06 | no | |
| CLI validate-boundary | B | same validate-boundary | — | no | plan B **n/a keep** |
| payload verdict as SoT (`data.get("verdict")` path in VERIFY_FINISH) | C | fence only | s02, s06 | yes | fail-closed |
| ownership retried as schema | C | escalate NEED_HUMAN / block, no increment_schema_retry | s03, s06 | yes | |
| repair done with leftover remaining accepted | C | validator invalid | s04, s06 | yes | |
| prompts already say fence required while runtime bypasses | I | runtime match prompts | s02, s05, s06 | no | enforce, keep prompt |
| `loop/schemas/README.md` `LoopGateVerdict` / `verdict.py` / SKIP | I | `GateVerdictRecord` PASS/FAIL/BLOCKED | s05, s06 | no | delete in-epic |

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-wire-schema-required-collab-forbid.yaml](../yaml/steps/s01-wire-schema-required-collab-forbid.yaml) | [s01…](../../implement/T-HUB-066-boundary-schema-ownership-strict/s01-wire-schema-required-collab-forbid.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-fence-required-stop-mutation.yaml](../yaml/steps/s02-fence-required-stop-mutation.yaml) | [s02…](../../implement/T-HUB-066-boundary-schema-ownership-strict/s02-fence-required-stop-mutation.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-semantic-ownership-mismatch.yaml](../yaml/steps/s03-semantic-ownership-mismatch.yaml) | [s03…](../../implement/T-HUB-066-boundary-schema-ownership-strict/s03-semantic-ownership-mismatch.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-repair-parent-fail-invariants.yaml](../yaml/steps/s04-repair-parent-fail-invariants.yaml) | [s04…](../../implement/T-HUB-066-boundary-schema-ownership-strict/s04-repair-parent-fail-invariants.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-kind-i-readme-prompts.yaml](../yaml/steps/s05-kind-i-readme-prompts.yaml) | [s05…](../../implement/T-HUB-066-boundary-schema-ownership-strict/s05-kind-i-readme-prompts.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-legacy-fallback-purge.yaml](../yaml/steps/s06-legacy-fallback-purge.yaml) | [s06…](../../implement/T-HUB-066-boundary-schema-ownership-strict/s06-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | completed |
**needs_creative:** все `no` (plan CREATIVE need: нет).

**Ladder justification (6 sNN, не 7):** plan §До DECOMPOSE #1+#2 = один contract boundary (Wire required schema + extra=forbid + red tests + same parse) → s01; #3 stop fence+mutation → s02 (wire+enforce, apply≠schema-only); #4 ownership → s03; #5 repair → s04; #6 Kind I → s05; #7 purge leftover → s06. Не micro-ladder schema→CLI→hook как отдельные sNN без outcome.
