# Реестр шагов (Decompose index)

**Plan ID:** T-HUB-069-agent-contract-registry-codex-policy  
**План:** [plan.md](plan.md)  
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**  
**Дата:** 2026-09-06  
**Режим:** BACK DECOMPOSE  
**Уровень:** L3–L4  
**Granularity:** 7 sNN (band 5–8; L3/L4 ≤9; advisory floor плана = 7; schema+parser в s01; mapping+materialize fingerprint в s02; wire+enforce deny в s03; CONTRACTS drift в s04; ALWAYS_INJECT derived в s05; Kind I+runtime-sync в s06; apply≠purge → s07)

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml` — `.cursor/templates/decompose/epic-step.yaml`.

> **Path (layout v2 HARD):** этот файл = `plan/T-HUB-069-agent-contract-registry-codex-policy/md/decompose-index.md`. Machine = `yaml/decompose-index.yaml`. Shards = `yaml/steps/`. **FORBIDDEN** `decompose-<id>/` · `yaml/index.md` · `yaml/index.yaml`.  
> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `yaml/decompose-index.yaml`.** Этот файл в IMPLEMENT не грузить.  
> **status SoT = `decompose-index.yaml` only.**  
> **Ladder:** s01 add (PolicyRecord + parser + red silent-drop) → s02 add/wire (mapping yaml + fingerprint/sidecar emit) → s03 wire+enforce (parity mutation fail-closed) → s04 wire+enforce (SubagentStart CONTRACTS sha drift) → s05 wire (ALWAYS_INJECT derived, video+sunset) → s06 Kind I + runtime-sync fingerprint check → s07 purge presence-only / silent-weaker leftovers.  
> **Justification 7 sNN:** plan §До DECOMPOSE enumerates 7 outcomes; s03≠s07 (parity mutation apply ≠ leftover purge); s04 drift spawn ≠ s05 inject set; s06 Kind I/runtime-sync отдельно от mapping emit.

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность (сессия DECOMPOSE, не `impl:`) |
| `tdd` / `python-testing-patterns` / `modern-python` / `python-anti-patterns` | Core(4) в каждом code sNN |
| `python-type-safety` | PolicyRecord pydantic + mapping Literal |
| `python-error-handling` | fail-closed `unsupported_runtime_policy` / drift codes |
| `python-configuration` | mapping yaml load |

**Per-step:** skills gate в каждом `sNN` (`skills-gate-situational.mdc`). Session skills (`writing-plans`, `brainstorming`) **FORBIDDEN** в `impl:`.

## Requirements coverage (plan → steps)

> **HARD:** каждый AC+ / AC− / FR / NFR / US / SC → ≥1 шаг, иначе `out_of_scope` + `follow_up:` уже в `memory-bank/back/roadmap/queue.yaml`.  
> Колонка **Plan FR text** = дословно из `plan.md`. Covered row ⇒ measurable `verify` (не map-only).

| Req ID | Plan FR text (verbatim) | sNN | Notes / measurable verify |
| :--- | :--- | :--- | :--- |
| FR-001 | `PolicyRecord` pydantic: name, tools, disallowedTools, maxTurns, overlay, managed, mode, verdict, allow_worktree, requires_model, default_loop, default_chat, color (color may map n/a). | s01 | `bin/pytest loop/tests/test_codex_agent_policy.py -q --tb=line -k PolicyRecord` |
| FR-002 | Parser from harness/agents frontmatter; extra unknown keys listed not silently ignored if `managed: true`. | s01 | pytest unknown-key fixture → listed extras; managed fail if dropped |
| FR-003 | Codex mapping table yaml: field → `native` \| `hook` \| `unsupported`. Required deny (Write/Edit/Agent on verify-*) cannot be `unsupported` without hook row. | s02, s03 | yaml load + matrix test TM-003; missing hook row → fail |
| FR-004 | Generated TOML includes `policy_fingerprint` and `source_prompt_sha256` (as TOML comments or `[metadata]` if Codex allows; if parser strips unknown — still write sidecar `.codex/agents/<id>.policy.json`). | s02 | sidecar/TOML present after materialize; TM-004 |
| FR-005 | Parity: for each prompt file, mapping applied; fail codes `codex_policy_dropped`, `unsupported_runtime_policy`, `agent_contract_drift`. | s03, s04 | mutation pytest TM-001/TM-004; drift TM-002 |
| FR-006 | `_lib.CONTRACTS` keyed by agent; build or checksum vs prompt section; SubagentStart compares. | s04 | mutate CONTRACTS → `agent_contract_drift`; hook start test |
| FR-007 | `_ALWAYS_INJECT` derived from PolicyRecord.managed/verdict **or** phase registry ∪ manifest — not hardcoded software-only set (consume 064 ids). | s05 | `_ALWAYS_INJECT` contains `verify-edit`; sunset-inventory if managed |
| FR-008 | sunset-inventory: inject contract after 063; 069 must include if managed. | s05 | set membership + inject test |
| FR-009 | Kind I: agent md may keep human tools list; runtime must not be weaker than md. | s03, s06 | matrix test verify-implement; instruction rewrite honesty |
| FR-010 | Explorer Write deny: same mapping (already Claude native); Codex path must not grant Write. | s03, s06 | mapping pytest TM-006; explorer Codex Write denied |
| FR-011 | Do not invent Codex CLI flags that do not exist; prefer hook enforcement documented. | s02, s06 | mapping rows `native` only for real Codex fields; Kind I no invented flags |
| FR-012 | runtime-sync --check includes fingerprint mismatch. | s06 | `python -m loop.cli.runtime_sync --check` fail on stripped sidecar / hash |
| FR-013 | Tests mutation: remove disallowedTools from TOML/sidecar → fail parity. | s03 | fixture drop deny → fail `unsupported_runtime_policy` or hook-row+parity |
| FR-014 | Generic `@verify` in machine commands (audit P2.3) — Appetite cut (one-line Kind I only if spawn docs already touched). | — | Appetite `cut_list` |
| FR-015 | Generated loop/schemas/README from registry — **cut** (P2.4). | — | Appetite `cut_list`; keep manual rationale in Kind I (s06/s07) |
| US-001 | Как Codex parent, я не хочу verify-implement с native Write если source forbids. | s02, s03 | mapping: unsupported → hook policy still deny **and** fingerprint; or TOML field if exists |
| US-002 | Как CI, я хочу fail если TOML silent-dropped required deny. | s01, s03 | fixture frontmatter disallowedTools not in mapping → fail `unsupported_runtime_policy` |
| US-003 | Как SubagentStart, я хочу drift CONTRACTS vs prompt hash block. | s04 | mutate CONTRACTS string → `agent_contract_drift` |
| US-004 | Как operator, я хочу video verify in inject set after 064. | s05 | `_ALWAYS_INJECT` contains verify-edit |
| SC-001 | silent drop deny fails CI | s01, s03 | pytest policy / parity mutation |
| SC-002 | fingerprint in sidecar/TOML | s02 | files exist after materialize |
| SC-003 | CONTRACTS drift blocks start | s04 | hook test |
| SC-004 | video agents in inject after 064 | s05 | set membership |
| SC-005 | verify-implement Codex not weaker than md | s03 | matrix test |
| AC+1 | PolicyRecord for all managed agents. | s01 | parse `harness/agents/*.md` managed=true |
| AC+2 | Materialize/parity fail-closed on undroppable policy. | s02, s03 | materialize or parity fail `unsupported_runtime_policy` |
| AC+3 | Fingerprint + drift spawn block. | s02, s04 | sidecar + SubagentStart |
| AC+4 | Inject set includes all finish/managed agents (software+video+repair+sunset). | s05 | derived set vs hardcoded software-only |
| AC+5 | Mapping yaml tested. | s02, s03 | pytest loads yaml; required deny rows |
| AC−1 | Нет presence-only Codex parity. | s03, s07 | mutation TOML still fails; leftover presence-only asserts purged |
| AC−2 | Нет silent drop disallowedTools. | s01, s03, s07 | red then green fail-closed; purge silent emit |
| AC−3 | Нет CONTRACTS text ≠ prompt without fail. | s04, s07 | drift block; leftover ignore purged |
| AC−4 | Нет hardcoded software-only ALWAYS_INJECT after 064. | s05, s07 | derived set; leftover literal set purged |
| AC−5 | Нет «policy in developer_instructions only» as sufficient Independent Test. | s03, s06, s07 | Independent Test FAIL path; Kind I rewrite |
| US-002 Given/When/Then | Given: agent md with `disallowedTools: ["Write","Edit","Agent"]` / When: materialize Codex / Then: either TOML encodes deny **or** materialize/parity fails with `unsupported_runtime_policy` unless hook-enforcement row exists in matrix with test proving stop/start still blocks those tools | s02, s03 | behavior cp + enforce cp |
| Independent Test PASS | dropping deny from artifact fails CI; drift blocks start; fingerprint exists. | s02, s03, s04 | named pytest + `--check` |
| Independent Test FAIL | «TOML file exists for each md»; «deny mentioned in developer_instructions». | s03, s06, s07 | dilution = FAIL ANALYZE |
| Technology axiom | Source policy parse frontmatter → PolicyRecord; Codex emit mapped **or** unsupported fail; injected `contract_id`+`source_sha256`; parity = source set ∪ mapping; FORBIDDEN TOML-only SoT / silent drop / presence-only | s01–s07 | ladder add→wire→enforce→purge |
| TM-001 | drop deny fixture / pytest policy / unsupported_runtime_policy or equivalent hook row + fail if neither | s03 | `bin/pytest loop/tests/test_codex_agent_policy.py -q --tb=line -k drop_deny` |
| TM-002 | CONTRACTS sha mismatch / hook start / agent_contract_drift | s04 | hook start pytest |
| TM-003 | verify-implement mapping / pytest / not weaker | s03 | matrix test |
| TM-004 | fingerprint written / sidecar/TOML / present | s02 | files + pytest |
| TM-005 | ALWAYS_INJECT has verify-edit / unit / in set | s05 | unit set membership |
| TM-006 | explorer Codex Write / mapping / denied | s03, s06 | mapping + Kind I |
| Failure TM-001 | drop disallowedTools / Write on verify / parity / unsupported/fail | s03 | same as QA TM-001 |
| Failure TM-002 | stale CONTRACTS / two HARD texts / sha / drift block | s04 | same as QA TM-002 |
| Failure TM-003 | missing video inject / no contract / set / include | s05 | QA TM-005 maps US-004 |
| Failure TM-004 | presence-only parity / false green / mutation TOML / fail | s03, s07 | mutation + purge leftover |
| Failure TM-005 | unknown frontmatter / lost field / extra list / fail managed | s01 | extras listed |
| Failure TM-006 | sidecar stripped / fingerprint gone / runtime-sync / fail | s06 | `--check` fingerprint |
| Failure TM-007 | explorer Write on Codex / weaker / mapping / deny hook | s03, s06 | mapping + Kind I |
| Failure generate README | generate README required / scope creep / cut / n/a | — | Appetite cut; not a step |
| Product WHAT 1 | For each managed agent in `harness/agents/*.md` (after 064: 11 files): PolicyRecord extracted. | s01 | parse all managed |
| Product WHAT 2 | Codex materialize writes fingerprint + mapped native fields Codex supports; unsupported required fields → **do not** emit usable agent without `unsupported_runtime_policy` (fail materialize or emit + doctor fail). | s02, s03 | emit + fail-closed |
| Product WHAT 3 | Hook inject includes contract fingerprint; mismatch → `agent_contract_drift` block spawn. | s04 | SubagentStart |
| Product WHAT 4 | Parity test: verify-implement (and video after 064) disallowed Write/Edit still enforced via hook if TOML cannot native-deny. | s03, s05 | matrix + inject |
| Product WHAT 5 | Equivalence matrix documented in-repo as yaml/json **checked in tests**, not only markdown. | s02, s03 | mapping yaml + pytest |
| NFR-testability | Testability 5 — no live Codex needed | s01–s07 | all verify = pytest/rg/CLI fixtures |
| Appetite cut generate schemas README | `generate schemas README` | — | cut_list; FR-015 |
| Appetite cut generate CONTRACTS AST | `generate CONTRACTS AST` | — | cut_list; Eng review batch log cut |
| Appetite cut generic @verify purge | `generic @verify purge` | — | cut_list; FR-014 |
| Appetite cut Cursor Codex IDE | `Cursor Codex IDE` | — | cut_list |
| Out of scope | duplicate Claude hooks (065); finish journal (068); skill FS (062); doctor graph (067) except fingerprint may be consumed later | — | plan §Контекст **Не:** |
| Out of scope | P2.1 full Contract Registry generating all docs | — | Appetite cut_list |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| s01 — PolicyRecord + red tests silent drop | plan §До DECOMPOSE #1 · FR-001/002 · US-002 · Failure TM-005 | s01 |
| s02 — mapping yaml + materialize fingerprint/sidecar | plan §До DECOMPOSE #2 · FR-003/004 · AC+5 · TM-004 · HOW | s02 |
| s03 — parity mutation | plan §До DECOMPOSE #3 · FR-005/013 · US-001/002 · SC-001/005 · AC+2 · TM-001/003 | s03 |
| s04 — SubagentStart drift | plan §До DECOMPOSE #4 · FR-006 · US-003 · SC-003 · AC+3 · TM-002 | s04 |
| s05 — ALWAYS_INJECT derived (video+sunset) | plan §До DECOMPOSE #5 · FR-007/008 · US-004 · SC-004 · AC+4 · TM-005 | s05 |
| s06 — Kind I + runtime-sync check | plan §До DECOMPOSE #6 · FR-009/011/012 · Failure TM-006/007 · sunset I | s06 |
| s07 — purge presence-only assertions | plan §До DECOMPOSE #7 · Replacement A+B+C+I · AC−1–5 · Failure TM-004 | s07 |
| Technology axiom lock | plan §Technology axiom | s01–s07 |
| Data flow md → PolicyRecord → mapping → TOML+sidecar → parity | plan §Eng review spine Data flow | s01–s03 |
| SubagentStart CONTRACTS+sha vs PolicyRecord.source_sha | plan §Data flow | s04 |
| tools deny → Codex native OR hook | plan §Data flow | s02, s03, s06 |
| Add PolicyRecord | behavior-first ladder 1 Add | s01 |
| Add mapping + fingerprint emit | ladder 1 Add / 2 Wire emit | s02 |
| Wire+enforce parity fail-closed | ladder 2–3 | s03 |
| Wire+enforce spawn drift | ladder 2–3 | s04 |
| Wire inject set | ladder 2 | s05 |
| Kind I instruction + --check enforce | ladder 3 + Kind I | s06 |
| Purge leftover presence-only / silent-weaker | ladder 4 Purge | s07 |
| QA consumes TM-001…TM-006 | plan §QA consumes | s03, s04, s02, s05, s06 |
| Independent Test PASS/FAIL | plan §Independent Test | s02–s04, s07 |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Materialized Codex agent эквивалентен source frontmatter policy **или** явно `unsupported_runtime_policy` fail-closed | s01, s02, s03 |
| Injected `_lib.CONTRACTS` hash-совпадает с prompt SoT; drift blocks start | s04 |
| Нет silent «TOML есть = parity green» при потерянных deny tools | s03, s07 |
| Fingerprint exists (sidecar/TOML) and runtime-sync --check fails if stripped | s02, s06 |
| `_ALWAYS_INJECT` includes video verify + sunset after 064/063 | s05 |
| Explorer/verify-implement Codex path not weaker than md | s03, s06 |
| Kind I honesty: docs не утверждают «TOML = full agent»; prose deny insufficient | s06, s07 |
| Fail-closed mapping, not generate-all README encyclopedia | s02, s06; FR-014/015 cut |
| AC+ PolicyRecord all managed · fail-closed undroppable · fingerprint+drift · inject set · mapping tested | s01–s05 |
| AC− no presence-only · no silent drop · no CONTRACTS drift silent · no software-only inject · no instructions-only Independent Test | s03–s07 |
| NFR: no live Codex needed | all sNN pytest/rg |
| Out of scope (Appetite cut_list) | generate schemas README; generate CONTRACTS AST; generic @verify purge; Cursor Codex IDE |

## Replacement cleanup (plan → steps)

> Brownfield replace. Completeness ladder add → wire → enforce → purge. Финальный `s07-legacy-fallback-purge` с `sunset_inventory` + `grep_control` по каждой строке.

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `render_codex_agent_toml` name/desc/developer_instructions only as complete agent | A | mapped fields + `policy_fingerprint` + sidecar | s02, s07 | no | incompleteness deleted in-epic |
| `markdown_agent_to_codex_toml` drops tools/disallowedTools silently | A | PolicyRecord + mapping or `unsupported_runtime_policy` | s01, s02, s03, s07 | no | |
| hardcoded `harness/hooks/subagent-start.py::_ALWAYS_INJECT` software-only set | A | derived from PolicyRecord.managed/verdict ∪ manifest/phase | s05, s07 | no | must include verify-edit + sunset-inventory if managed |
| presence-only Codex agent dest exists / `missing_codex_agent` exclusivity as sole parity | A | policy matrix applied per prompt file | s03, s07 | no | 064 already source glob; leftover presence-only asserts |
| tests asserting TOML conversion of name/desc/body is sufficient (`test_markdown_frontmatter_converts_to_toml` completeness) | A | tests on fingerprint + deny mapping + mutation fail | s03, s07 | no | obsolete completeness asserts rewrite |
| `loop.cli.runtime_sync --check` green on truncated TOML (no fingerprint) | B | fingerprint mismatch in drift items | s06, s07 | no | entrypoint enforce |
| silent materialize weaker agent (usable TOML without deny) | C | fail-closed materialize/parity | s02, s03, s07 | yes | misconfig → fail, not stub |
| prose deny in `developer_instructions` as sufficient SoT | C | hook+matrix Independent Test | s03, s06, s07 | yes | AC−5 |
| docs «Codex TOML = full agent» | I | mapping honesty (native \| hook \| unsupported) | s06, s07 | no | |
| P2 generate all docs / README encyclopedia | I | cut — keep manual rationale | s06, s07 | no | cut_list; do not add generator |
| Kind I spawn docs teaching presence-only Codex parity | I | fingerprint + fail codes | s06, s07 | no | only if we touch those docs; FR-014 generic @verify still cut |

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-policy-record-parser.yaml](../yaml/steps/s01-policy-record-parser.yaml) | [s01…](../../implement/T-HUB-069-agent-contract-registry-codex-policy/s01-policy-record-parser.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-mapping-fingerprint-sidecar.yaml](../yaml/steps/s02-mapping-fingerprint-sidecar.yaml) | [s02…](../../implement/T-HUB-069-agent-contract-registry-codex-policy/s02-mapping-fingerprint-sidecar.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-parity-mutation-fail-closed.yaml](../yaml/steps/s03-parity-mutation-fail-closed.yaml) | [s03…](../../implement/T-HUB-069-agent-contract-registry-codex-policy/s03-parity-mutation-fail-closed.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-subagent-start-contract-drift.yaml](../yaml/steps/s04-subagent-start-contract-drift.yaml) | [s04…](../../implement/T-HUB-069-agent-contract-registry-codex-policy/s04-subagent-start-contract-drift.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-always-inject-derived.yaml](../yaml/steps/s05-always-inject-derived.yaml) | [s05…](../../implement/T-HUB-069-agent-contract-registry-codex-policy/s05-always-inject-derived.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-kind-i-runtime-sync-fingerprint.yaml](../yaml/steps/s06-kind-i-runtime-sync-fingerprint.yaml) | [s06…](../../implement/T-HUB-069-agent-contract-registry-codex-policy/s06-kind-i-runtime-sync-fingerprint.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s07** | [s07-legacy-fallback-purge.yaml](../yaml/steps/s07-legacy-fallback-purge.yaml) | [s07…](../../implement/T-HUB-069-agent-contract-registry-codex-policy/s07-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | pending |

**needs_creative:** все `no` (plan: CREATIVE need нет).

**Next after DECOMPOSE FINISH:** `BACK ANALYZE T-HUB-069-agent-contract-registry-codex-policy` only. **FORBIDDEN** ANALYZE deferred → IMPLEMENT.
