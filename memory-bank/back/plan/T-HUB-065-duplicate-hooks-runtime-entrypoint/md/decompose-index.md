# Реестр шагов (Decompose index)

**Plan ID:** T-HUB-065-duplicate-hooks-runtime-entrypoint  
**План:** [plan.md](plan.md)  
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**  
**Дата:** 2026-09-06  
**Режим:** BACK DECOMPOSE  
**Уровень:** L3  
**Granularity:** 5 sNN (band 5–8; advisory floor плана = 6; red-test+generator unique realpath слиты в s01; leftover dual-all-events → s05 purge; не micro-ladder schema→CLI)

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml` — `.cursor/templates/decompose/epic-step.yaml`.

> **Path (layout v2 HARD):** этот файл = `plan/T-HUB-065-duplicate-hooks-runtime-entrypoint/md/decompose-index.md`. Machine = `yaml/decompose-index.yaml`. Shards = `yaml/steps/`.  
> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `yaml/decompose-index.yaml`.** Этот файл в IMPLEMENT не грузить.  
> **status SoT = `decompose-index.yaml` only.**  
> **Ladder:** s01 add+wire+enforce unique realpath (dedup + generator + committed settings + dual fixture) → s02 wire inject `EPIC_RUNTIME` → s03 Kind I instructions → s04 hash_mismatch fail-closed → s05 purge leftover A+B+C+I.

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность (сессия DECOMPOSE, не `impl:`) |
| `tdd` / `python-testing-patterns` / `modern-python` / `python-anti-patterns` | Core(4) в каждом code sNN |
| `python-error-handling` | fail-closed duplicate / unknown runtime / hash_mismatch |
| `python-configuration` | settings.json merge, EPIC_RUNTIME, runtime-sync check |

**Per-step:** skills gate в каждом `sNN` (`workflow-decompose.mdc`). `impl:` без session skills (`writing-plans` / `brainstorming` / `executing-plans` / `breakdown-plan`).

## Requirements coverage (plan → steps)

> **HARD:** каждый AC+ / AC− / FR / NFR (или UI AC) → ≥1 шаг, иначе явный `out_of_scope` + `follow_up: T-…` **уже в** `roadmap-*.queue.yaml`.  
> **FR verbatim (HARD):** колонка **Plan FR text** = дословный текст / nouns из `plan.md`. Remap FR = FAIL ANALYZE (`layout_dilution`).  
> Notes `deferred`/`partial` без `follow_up: T-…` = FAIL (`validate-decompose-tree`).  
> NFR в плане нет как ID — покрыты Independent Test / Appetite / Technology axiom строками ниже.

| Req ID | Plan FR text (verbatim) | sNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | Dedup function: canonicalize command path via realpath relative to project dir. | s01 | noun: realpath canonicalize |
| FR-002 | Generator/installer emits unique commands; pytest on committed settings.json. | s01 | `merge_hooks` + committed `.claude/settings.json` |
| FR-003 | If `.claude/hooks/*.py` symlink to harness — register **only harness** or **only .claude**, not both (choose harness SoT — matches manifest). | s01, s05 | SoT = `harness/hooks/*.py`; leftover dual → s05 |
| FR-004 | `session_start_payload` passes runtime from `EPIC_RUNTIME` / payload into `build_prompt_scope`. | s02 | wire, not default claude-code |
| FR-005 | Tests both runtimes. | s02 | TM-003 Codex AGENTS.md · TM-004 Claude CLAUDE.md |
| FR-006 | Rewrite `.cursor/rules/mainrule.mdc` chain step 0 / HARD RULE: current entrypoint only (Kind I). role-command SKILL same if it forces CLAUDE.md for Codex. | s03, s05 | SoT copies: `.claude/skills` + `harness/claude/skills` |
| FR-007 | runtime-sync: CLAUDE.md either regenerated from `harness/instructions/main.md` or documented generated header; hash_mismatch = fail CI unless allow. | s04, s05 | warning-only delete in-epic |
| FR-008 | Pre/Post tool duplicate same treatment as SessionStart. | s01, s05 | all events unique realpath |
| FR-009 | Cursor `.cursor/hooks.json` failClosed false = **out of scope** unless one-line note in Appetite cut. | — | follow_up: appetite cut; **not** a queue epic — cut_list only |
| FR-010 | Do not change hook Python semantics except idempotency if double-fire still possible mid-migrate (guard). | s01, s05 | guard only if dual still possible mid-step; purge dual so guard not eternal shim |
| US-001 | Как Claude runtime, я хочу SessionStart один раз. | s01 | unique realpath test on settings.json |
| US-002 | Как Codex loop, я хочу inject AGENTS.md. | s02 | unit session_start_payload monkeypatch env |
| US-003 | Как parent Codex, я не хочу rule «читай CLAUDE.md». | s03 | rg mainrule after rewrite |
| US-004 | Как CI, я хочу duplicate registration fail. | s01 | fixture dual commands → fail `hook_duplicate_realpath` |
| SC-001 | 0 duplicate realpaths | s01, s05 | pytest |
| SC-002 | Codex inject AGENTS.md | s02 | unit |
| SC-003 | mainrule no unconditional CLAUDE.md for Codex | s03 | rg + review |
| SC-004 | generator regression fixture | s01 | pytest |
| AC+ #1 | Unique hook realpaths in generated Claude settings. | s01 | |
| AC+ #2 | Runtime passed to prompt scope. | s02 | |
| AC+ #3 | Instruction chain runtime-specific. | s03 | |
| AC+ #4 | Tests prevent reintroduction. | s01, s02, s04, s05 | |
| AC− #1 | Нет dual SessionStart same script. | s01, s05 | |
| AC− #2 | Нет default claude entrypoint on Codex inject. | s02 | |
| AC− #3 | Нет «Read CLAUDE.md» as universal HARD for Codex. | s03, s05 | |
| AC− #4 | Нет hand-maintained second settings copy that re-adds dual. | s01, s05 | generator is SoT |
| AC− #5 | Нет warning-only on hash_mismatch. | s04, s05 | |
| TM-001 | unique realpath settings | s01 | pytest hooks parity |
| TM-002 | dual fixture fails | s01 | `hook_duplicate_realpath` |
| TM-003 | EPIC_RUNTIME=codex entrypoint | s02 | AGENTS.md |
| TM-004 | EPIC_RUNTIME=claude | s02 | CLAUDE.md |
| TM-005 (failure matrix) | hash_mismatch ignored / runtime-sync --check fail | s04 | plan Failure matrix TM-005; QA table TM-005 = all events (mapped s01) |
| TM-005 (QA consumes) | all hook events unique | s01, s05 | scan 0 dup; QA table row TM-005 |
| TM-006 (failure matrix) | only SessionStart deduped / other events dual | s01, s05 | FR-008 |
| TM-006 (QA consumes) | mainrule rg CLAUDE unconditional | s03 | 0 bad hits; QA table row TM-006 |
| TM-007 | generator skip / manual JSON regress | s01 | CI on settings |
| Independent Test PASS | settings unique; Codex inject AGENTS.md; dual fixture red. | s01, s02 | named pytest |
| Independent Test FAIL | «symlinks exist» without unique registration. | s01–s05 | dilution = FAIL ANALYZE |
| Technology axiom: Hook registration | one realpath per event/matcher | s01, s05 | dual symlink entries FORBIDDEN |
| Technology axiom: Prompt scope entrypoint | `EPIC_RUNTIME` → AGENTS.md / CLAUDE.md / DSH.md | s02 | default claude when Codex FORBIDDEN |
| Technology axiom: Instruction chain | current runtime entrypoint only | s03 | «always Read CLAUDE.md» in Codex FORBIDDEN |
| Technology axiom: settings.json | generated from manifest | s01 | hand-edit dual keep FORBIDDEN |
| Product WHAT #1 | Claude settings after generate: 0 duplicate realpath commands. | s01 | |
| Product WHAT #2 | Codex session start additionalContext entrypoint = AGENTS.md. | s02 | |
| Product WHAT #3 | Claude session start entrypoint = CLAUDE.md. | s02 | |
| Product WHAT #4 | mainrule / role-command: «читай current runtime entrypoint», не hardcoded CLAUDE для всех. | s03 | |
| Product WHAT #5 | runtime-sync claude either green or intentional generated marker — no silent stale copy. | s04 | |
| Appetite cut: Cursor hooks.json failClosed | out of scope | — | `cut_list`; FR-009; one-line note in plan Appetite only |
| Appetite cut: DSH full inject matrix polish | out of scope | — | `cut_list`; Assumptions: DSH.md handle or explicit n/a → s02 documents n/a or fail-closed unknown |
| catch Exception continue on preflight as success | typed warning vs fail | s02, s05 | sunset C **partial**; swallow → follow_up: T-HUB-067 / T-HUB-068 |
| full Codex event matrix | out of scope | — | follow_up: T-HUB-053-codex-claude-hooks-parity (queue) |
| transactional finish | out of scope | — | follow_up: T-HUB-068-start-finish-transaction-boundary (queue) |
| schema fence | out of scope | — | follow_up: T-HUB-066-boundary-schema-ownership-strict (queue) |

## Stages coverage (plan/canon → steps)

> Каждый этап/фаза плана и канон-дока → sNN. Не растворять в layout.

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| s01 — red test duplicate realpath + Codex entrypoint | plan §До DECOMPOSE #1 (Codex entrypoint → s02) | s01 (red unique+dual); s02 (Codex inject) |
| s02 — generator/settings unique; choose SoT path | plan §До DECOMPOSE #2 | s01 (схлоп с red-test: same outcome unique registration) |
| s03 — pass runtime into build_prompt_scope + tests | plan §До DECOMPOSE #3 | s02 |
| s04 — Kind I mainrule/role-command | plan §До DECOMPOSE #4 | s03 |
| s05 — runtime-sync hash policy | plan §До DECOMPOSE #5 | s04 |
| s06 — purge dual entries leftover all events | plan §До DECOMPOSE #6 | s05 |
| Technology axiom lock | plan §Technology axiom | s01–s05 |
| Data flow: manifest → generator → unique settings | plan §Data flow | s01 |
| Data flow: SessionStart → payload → build_prompt_scope(runtime) | plan §Data flow | s02 |
| Failure matrix dual realpath / generator skip | plan §Failure matrix TM-001, TM-007 | s01 |
| Failure matrix missing runtime / unknown EPIC_RUNTIME | plan §Failure matrix TM-002, TM-003 | s02 |
| Failure matrix mainrule stale | plan §Failure matrix TM-004 | s03 |
| Failure matrix hash_mismatch ignored | plan §Failure matrix TM-005 | s04 |
| Failure matrix only SessionStart deduped | plan §Failure matrix TM-006 | s01, s05 |
| Replacement A second settings command | plan §Replacement A | s01, s05 |
| Replacement A default build_prompt_scope for Codex | plan §Replacement A | s02, s05 |
| Replacement B installer appends both paths | plan §Replacement B | s01, s05 |
| Replacement C swallow preflight / warning-only hash | plan §Replacement C | s04, s05; swallow partial → 067/068 |
| Replacement I mainrule / role-command | plan §Replacement I | s03, s05 |
| QA consumes TM-001…006 | plan §QA consumes | s01–s04 |
| Independent Test | plan §Independent Test | s01, s02 |
| Add → wire → enforce → purge | behavior-first §3 | s01 add/wire/enforce unique; s02 wire inject; s03 Kind I; s04 enforce hash; s05 purge |

## Outcome map (plan → steps)

> **HARD:** не ужимать Goal/NFR плана до infra-slug. Map ≠ замена шагов.

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Один hook command на (event, matcher, realpath); SessionStart не ×2 | s01, s05 |
| Codex inject AGENTS.md, не CLAUDE.md | s02 |
| Claude inject CLAUDE.md | s02 |
| mainrule / role-command читает current runtime entrypoint | s03 |
| runtime-sync claude: hash_mismatch = fail, не warning-only | s04 |
| Generator не эмитит duplicates; committed settings уникальны | s01 |
| Dual fixture `hook_duplicate_realpath` fail | s01 |
| All events (Pre/Post/Stop/…) unique, не только SessionStart | s01, s05 |
| Fail-closed unknown EPIC_RUNTIME (или documented default) | s02 |
| Independent Test PASS: unique + AGENTS.md + dual red | s01 + s02 |
| Independent Test FAIL dilution: «symlinks exist» without unique registration | s01–s05 (не done) |
| Appetite cut Cursor failClosed / DSH polish | — (cut_list) |
| Soft leftover swallow preflight Exception | follow_up T-HUB-067 / T-HUB-068 (не eternal shim) |
| Out of scope: full 053 event matrix, 066 schema, 068 transactional finish | queue follow_up |

## Replacement cleanup (plan → steps)

> Brownfield leftover **dual registration + default runtime + Kind I**. Completeness: **add → wire → enforce → purge**. Kind A\|B\|C\|I. Финальный `s05-legacy-fallback-purge` с `sunset_inventory:` + `grep_control:` по каждой строке.

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| second settings command same realpath (`.claude/hooks/*.py` + `harness/hooks/*.py` на одном event/matcher) | A | single harness SoT command | s01 (apply unique), s05 (leftover all events) | no | plan A row 1 |
| `build_prompt_scope()` default used for Codex (`session_start_payload` без `runtime=`) | A | explicit `EPIC_RUNTIME` / payload runtime | s02, s05 | no | plan A row 2 |
| installer/`merge_hooks` that appends both `.claude` and harness when realpath equal | B | one path (harness SoT) | s01, s05 | no | plan B |
| catch Exception continue on preflight as success | C | typed warning vs fail | s02 (inject path only), s05 scan | yes | **partial** this epic; swallow → follow_up: T-HUB-067-pack-doctor-executable-graph / T-HUB-068-start-finish-transaction-boundary |
| hash_mismatch warning-only | C | fail check (`bin/runtime-sync --runtime claude --check` non-zero) | s04, s05 | yes | delete in-epic for claude target |
| mainrule «Read CLAUDE.md» always | I | current entrypoint only | s03, s05 | no | `.cursor/rules/mainrule.mdc` |
| role-command same (forces CLAUDE.md for Codex) | I | runtime entrypoint | s03, s05 | no | `.claude/skills/role-command/SKILL.md` + `harness/claude/skills/role-command/SKILL.md` |
| tests asserting dual-path OK / string-equal merge without realpath | A | rewrite to unique-realpath + dual fixture fail | s01, s05 | no | obsolete merge tests |
| Cursor `.cursor/hooks.json` failClosed false | — | n/a this epic | — | — | Appetite cut FR-009 |

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-unique-hook-realpath.yaml](../yaml/steps/s01-unique-hook-realpath.yaml) | [s01…](../../implement/T-HUB-065-duplicate-hooks-runtime-entrypoint/s01-unique-hook-realpath.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-session-start-runtime-inject.yaml](../yaml/steps/s02-session-start-runtime-inject.yaml) | [s02…](../../implement/T-HUB-065-duplicate-hooks-runtime-entrypoint/s02-session-start-runtime-inject.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-kind-i-runtime-entrypoint.yaml](../yaml/steps/s03-kind-i-runtime-entrypoint.yaml) | [s03…](../../implement/T-HUB-065-duplicate-hooks-runtime-entrypoint/s03-kind-i-runtime-entrypoint.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-runtime-sync-hash-fail-closed.yaml](../yaml/steps/s04-runtime-sync-hash-fail-closed.yaml) | [s04…](../../implement/T-HUB-065-duplicate-hooks-runtime-entrypoint/s04-runtime-sync-hash-fail-closed.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-legacy-fallback-purge.yaml](../yaml/steps/s05-legacy-fallback-purge.yaml) | [s05…](../../implement/T-HUB-065-duplicate-hooks-runtime-entrypoint/s05-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | completed |
**needs_creative:** все `no` (plan CREATIVE need: нет).

**Ladder justification (5 sNN, не 6):** plan §До DECOMPOSE #1+#2 = один outcome «unique registration» (red dual fixture + generator/settings SoT harness) → s01; #3 inject runtime → s02; #4 Kind I → s03; #5 hash policy → s04; #6 leftover dual-all-events + inventory scan → s05. Apply unique ≠ leftover purge (behavior-first apply≠purge).
