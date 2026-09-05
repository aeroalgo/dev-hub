# Реестр шагов (Decompose index)

**Plan ID:** T-HUB-063-sunset-boundary-stop-pipeline  
**План:** [plan.md](plan.md)  
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**  
**Дата:** 2026-09-06  
**Режим:** BACK DECOMPOSE  
**Уровень:** L3  
**Granularity:** 5 sNN (band 5–8; advisory floor плана = 6; schema+CLI слиты в s01; Kind I+matrix в s04; не micro-ladder)

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml` — `.cursor/templates/decompose/epic-step.yaml`.

> **Path (layout v2 HARD):** этот файл = `plan/T-HUB-063-sunset-boundary-stop-pipeline/md/decompose-index.md`. Machine = `yaml/decompose-index.yaml`. Shards = `yaml/steps/`.  
> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `yaml/decompose-index.yaml`.** Этот файл в IMPLEMENT не грузить.  
> **status SoT = `decompose-index.yaml` only.**  
> **Ladder:** s01 add (registry+CLI fixtures) → s02 wire+enforce (SubagentStop branch + no-fence DENY) → s03 persist (sidecar parent-readable) → s04 Kind I (prompt+matrix) → s05 purge.

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность (сессия DECOMPOSE, не `impl:`) |
| `tdd` / `python-testing-patterns` / `modern-python` / `python-anti-patterns` | Core(4) в каждом code sNN |

**Per-step:** skills gate в каждом `sNN` (`skills-gate-situational.mdc`). Session skills (`writing-plans`, `brainstorming`) **FORBIDDEN** в `impl:`.

## Requirements coverage (plan → steps)

> **HARD:** каждый AC+ / AC− / FR / NFR / US / SC → ≥1 шаг, иначе `out_of_scope` + `follow_up:` уже в `memory-bank/back/roadmap/queue.yaml`.  
> Колонка **Plan FR text** = дословно из `plan.md`. Covered row ⇒ measurable `verify` (не map-only).

| Req ID | Plan FR text (verbatim) | sNN | Notes / measurable verify |
| :--- | :--- | :--- | :--- |
| FR-001 | `BOUNDARY_REGISTRY[SCHEMA_LOOP_SUNSET_INVENTORY] = SunsetReport` (или WireSunsetReport с required schema). | s01 | `bin/pytest loop/tests/test_boundary_registry.py -q --tb=line -k sunset` |
| FR-002 | Export schema id constant used by agent prompt **and** registry (one string). | s01, s04 | registry export + `rg` prompt `loop-sunset-inventory/v1`; s04 Kind I drift |
| FR-003 | `validate_boundary` positive/negative tests in `loop/tests/test_boundary_registry.py` / `test_validate_boundary.py`. | s01 | pos/neg pytest + CLI `--schema-id loop-sunset-inventory/v1` |
| FR-004 | SubagentStop: agent id `sunset-inventory` → extract fence → validate_boundary sunset schema. | s02 | hook test: valid fence → not skip; wrong agent id не мапится на gate schema (TM-006) |
| FR-005 | Persist result (sidecar path convention same family as gate, documented) **or** explicit typed in-memory + parent-readable file; not log-only. | s03 | sidecar file exists; parent helper reads schema_id |
| FR-006 | Malformed → schema retry count documented (0 or 1; sunset is search — prefer 1 retry then NEED_HUMAN). Semantic empty inventory is **valid** (zero items). | s01, s02 | s01: zero items `valid: true`; s02: retry 1 then NEED_HUMAN |
| FR-007 | Prompt `harness/agents/sunset-inventory.md` schema_id совпадает с registry (Kind I if drift). | s04 | `rg` schema string in prompt == `SCHEMA_LOOP_SUNSET_INVENTORY` |
| FR-008 | 08 matrix row sunset: Start inject yes, Stop parse yes, Schema sunset, sidecar yes. | s02, s03, s04 | living test encodes row; historical audit 08 keep (plan I keep) |
| FR-009 | Codex collab parser, если отдельный — same schema id (soft: если 066 owns collab, минимум registry shared). | s01 | registry shared; collab extra=ignore → `follow_up: T-HUB-066-boundary-schema-ownership-strict` |
| FR-010 | Не удалять sunset machine contract; «удалить schema из prompt» = только если registry path rejected — **не** выбран (audit preferred include). | s04, s05 | prompt retains `loop-sunset-inventory/v1`; no delete-schema path |
| US-001 | Как parent, я хочу `validate_boundary` принять корректный SunsetReport. | s01 | CLI/pytest `valid: true` |
| US-002 | Как hook, я хочу SubagentStop отвергнуть sunset без fence. | s02 | fixture transcript no fence → retry/block, не persist |
| US-003 | Как parent, я хочу sidecar/result после valid sunset, чтобы строить deletes. | s03 | file or state key exists with schema_id |
| US-004 | Как CI, я хочу unknown schema_id больше не быть единственным ответом на valid sunset. | s01, s05 | before/after pytest; purge `len==4` / expected-unknown |
| SC-001 | registry contains sunset id | s01 | pytest |
| SC-002 | valid payload CLI valid true | s01 | CLI |
| SC-003 | stop without fence ≠ success | s02 | hook test |
| SC-004 | 08-style matrix row green | s02, s03, s04 | test or doc+test |
| AC+1 | `loop-sunset-inventory/v1` in BOUNDARY_REGISTRY. | s01 | registry pytest |
| AC+2 | CLI validate success on fixture report (zero and non-zero items). | s01 | CLI TM-002/TM-006 |
| AC+3 | SubagentStop validates sunset; no-fence fails. | s02 | TM-004 |
| AC+4 | Parent-readable persisted result. | s03 | TM-005 |
| AC−1 | Нет dual path unit-only validate vs hook skip. | s02, s05 | stop branch exists; skip-path purged |
| AC−2 | Нет silent `schema_unknown` на каноническом id. | s01, s05 | CLI known id; leftover tests rewritten |
| AC−3 | Misconfig (wrong schema id in prompt) → fail validate, не prose accept. | s04 | prompt drift test / wrong-id fixture |
| AC−4 | Нет optional SoT «модель есть, hook нет». | s02 | sunset-inventory ∈ stop path; not VERIFY_MB_FINISH skip |
| AC−5 | Нет extra=ignore на sunset wire. | s01 | extra field → valid false (TM-002 plan QA TM-003) |
| TM-001 | registry has sunset | s01 | `bin/pytest loop/tests/test_boundary_registry.py -q --tb=line -k sunset` |
| TM-002 | valid zero items | s01 | validate-boundary CLI `valid true` |
| TM-003 | extra field | s01 | CLI `valid false` |
| TM-004 | stop no fence | s02 | hook test not success |
| TM-005 | valid stop persist | s03 | sidecar exists |
| TM-006 | non-zero items | s01 | fixture `valid true` |
| TM-006-map | wrong agent id mapped to gate schema | s02 | mapping test — sunset branch only (plan Failure matrix TM-006) |
| TM-007 | Codex collab extra=ignore | — | `follow_up: T-HUB-066-boundary-schema-ownership-strict` (plan Eng review deferred) |
| Independent Test PASS | CLI valid true; stop no-fence fails; sidecar present. | s01, s02, s03 | named pytest + CLI |
| Independent Test FAIL | «SunsetReport.model_validate in unit» only. | s01–s05 | dilution = FAIL ANALYZE |
| Technology axiom | fenced JSON `schema: loop-sunset-inventory/v1` → registry model; Stop same parser as gate; missing fence protocol FAIL; optional sunset **нет** | s01–s05 | ladder add→wire→enforce→purge |
| Out of scope | auto-fill plan sunset tables; MCP sunset tool | — | Appetite `cut_list` |
| Out of scope | skill FS (062); video agents (064); ownership v2 для gate (066, но sunset должен получить **минимум** schema+agent_id+scope); transactional finish (068) | — | 062 done; 064/066/068 в queue; 066 = collab extra=ignore |
| Out of scope | Codex collab parser extra=ignore / ownership v2 | — | follow_up: `T-HUB-066-boundary-schema-ownership-strict` |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| registry + red tests unknown→known | plan §До DECOMPOSE #1 · FR-001/002 · US-001 · AC+1 | s01 |
| validate_boundary pos/neg fixtures (zero/non-zero/extra/unknown) | plan §До DECOMPOSE #2 · FR-003/006 empty · AC+2 · AC−2/5 | s01 (слито: один contract boundary schema+CLI) |
| SubagentStop branch + no-fence | plan §До DECOMPOSE #3 · FR-004/006 retry · US-002 · AC+3 · AC−1/4 | s02 |
| persist sidecar + parent read helper if missing | plan §До DECOMPOSE #4 · FR-005 · US-003 · AC+4 | s03 |
| Kind I prompt schema_id + 08 matrix row | plan §До DECOMPOSE #5 · FR-007/008/010 · AC−3 | s04 |
| purge leftover comments/tests that encode unknown id as expected for canonical sunset | plan §До DECOMPOSE #6 · Replacement A/C · AC−1/2 | s05 |
| Add → Wire → Enforce → Purge | workflow-behavior-first §3 | s01 add · s02 wire+enforce · s03 persist (parent consume) · s04 Kind I · s05 purge |
| Failure matrix TM-001…006 (TM-007 → 066) | plan §Failure matrix · §QA consumes | s01–s03; TM-007 OOS |
| Data flow: agent → fence → Stop → validate_boundary → sidecar → parent deletes | plan §Eng review spine | s01–s03 |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Valid sunset JSON проходит CLI `validate-boundary --schema-id loop-sunset-inventory/v1` → `valid: true` | s01 |
| Malformed / extra / unknown id → fail-closed diagnostic, не silent | s01 |
| SubagentStop для `sunset-inventory` парсит fence, валидирует; no-fence ≠ success | s02 |
| Parent читает sidecar/result после valid sunset (не log-only) | s03 |
| Prompt schema_id = registry; misconfig → fail validate, не prose | s04 |
| Нет пути «модель зелёная, hook не знает schema» / optional SoT | s02, s05 |
| 08 matrix living: Start inject yes, Stop parse yes, Schema sunset, sidecar yes | s02, s03, s04 |
| CI: canonical sunset больше не отвечает только `schema_unknown_schema_id` | s01, s05 |
| Independent Test PASS: CLI valid true; stop no-fence fails; sidecar present | s01 + s02 + s03 |
| Independent Test FAIL dilution: unit `SunsetReport.model_validate` only | s01–s05 (не done) |
| Codex collab extra=ignore / ownership v2 | — follow_up T-HUB-066 |
| MCP sunset tool / auto-fill plan sunset tables | — Appetite cut_list |
| Skill FS / video agents / transactional finish | — 062 / 064 / 068 |

## Replacement cleanup (plan → steps)

> Brownfield leftover **wire** (модель есть, pipeline нет). Completeness: **add → wire → enforce → purge**. Kind A\|B\|C\|I. Финальный `s05-legacy-fallback-purge` с явными блоками `sunset_inventory:` и `grep_control:` (`inv-a-01`…`inv-i-02`: no canonical `schema_unknown`, no skip-path, persist fail-closed, prompt schema lock).

| Устаревает (path / symbol) | Kind | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `BOUNDARY_REGISTRY` without sunset (`len==4`, no `SCHEMA_LOOP_SUNSET_INVENTORY`) | A | `BOUNDARY_REGISTRY[SCHEMA_LOOP_SUNSET_INVENTORY] = SunsetReport` | s01 (add), s05 (leftover tests) | no | gap, not wrap |
| Stop path that ignores sunset agent (`harness/hooks/subagent-stop.py` falls through after gate/repair) | A | dedicated `sunset-inventory` / alias `sunset` branch → `validate_boundary` sunset schema | s02, s05 | no | not VERIFY_MB_FINISH |
| tests only `SunsetReport.model_validate` / `test_boundary_registry_contains_all_four_schemas` | A | e2e `validate_boundary` + stop + rewrite `len==4` | s01, s05 | no | obsolete exact-4 |
| `validate-boundary` unknown for sunset (`schema_unknown_schema_id` on canonical id) | B | known id in CLI `--schema-id loop-sunset-inventory/v1` | s01, s05 | no | |
| skip sunset because not verify / search agent | C | validate anyway | s02, s05 | yes | FORBIDDEN skip |
| swallow persist exception | C | raise / NEED_HUMAN | s03, s05 | yes | fail-closed |
| prompt «schema validated» while registry missing | I | truthful pipeline: fence → registry → stop | s04, s05 | no | keep schema in prompt (FR-010) |
| audit 08 matrix «currently no» | I | living test encodes yes-row; keep audit historical | s04 | no | plan policy **keep** historical audit |
| comments/tests that encode unknown id as expected for canonical sunset | A | rewrite asserts to known-id / valid:true | s05 | no | |

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-register-sunset-boundary.yaml](../yaml/steps/s01-register-sunset-boundary.yaml) | [s01…](../../implement/T-HUB-063-sunset-boundary-stop-pipeline/s01-register-sunset-boundary.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-subagentstop-sunset-branch.yaml](../yaml/steps/s02-subagentstop-sunset-branch.yaml) | [s02…](../../implement/T-HUB-063-sunset-boundary-stop-pipeline/s02-subagentstop-sunset-branch.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s03** | [s03-persist-sunset-sidecar.yaml](../yaml/steps/s03-persist-sunset-sidecar.yaml) | [s03…](../../implement/T-HUB-063-sunset-boundary-stop-pipeline/s03-persist-sunset-sidecar.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s04** | [s04-kind-i-sunset-prompt-matrix.yaml](../yaml/steps/s04-kind-i-sunset-prompt-matrix.yaml) | [s04…](../../implement/T-HUB-063-sunset-boundary-stop-pipeline/s04-kind-i-sunset-prompt-matrix.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s05** | [s05-legacy-fallback-purge.yaml](../yaml/steps/s05-legacy-fallback-purge.yaml) | [s05…](../../implement/T-HUB-063-sunset-boundary-stop-pipeline/s05-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | pending |

**needs_creative:** все `no` (plan CREATIVE need: нет).

**Ladder justification (5 sNN, не 6):** plan §До DECOMPOSE #1+#2 = один contract boundary (registry+CLI+fixtures) → s01; #3 wire+enforce stop → s02; persist отдельно (apply≠только validate) → s03; Kind I+matrix → s04; purge leftover → s05.
