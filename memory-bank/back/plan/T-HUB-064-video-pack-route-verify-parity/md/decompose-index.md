# Реестр шагов (Decompose index)

**Plan ID:** T-HUB-064-video-pack-route-verify-parity  
**План:** [plan.md](plan.md)  
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**  
**Дата:** 2026-09-06  
**Режим:** BACK DECOMPOSE  
**Уровень:** L3–L4  
**Granularity:** 6 sNN (band 5–8; advisory floor плана = 7; inventory+route SoT слиты в s01 — один operator outcome `Path.exists`; Kind I+software regression слиты в s05; не micro-ladder schema→CLI→wire)

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml` — `.cursor/templates/decompose/epic-step.yaml`.

> **Path (layout v2 HARD):** этот файл = `plan/T-HUB-064-video-pack-route-verify-parity/md/decompose-index.md`. Machine = `yaml/decompose-index.yaml`. Shards = `yaml/steps/`.  
> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `yaml/decompose-index.yaml`.** Этот файл в IMPLEMENT не грузить.  
> **status SoT = `decompose-index.yaml` only.**  
> **Ladder:** s01 add+enforce route (existing path / `pack_route_missing`) → s02 add agents (manifest+materialize) → s03 wire stop/start + `no_gate_reason` → s04 enforce source-driven parity (orphan DENY) → s05 Kind I + software regression → s06 purge.

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
| FR-001 | Inventory всех video intent commands vs FS. | s01 | pytest: каждый command из `intent_routing.yaml` `video_production`/`content_factory` → `Path.exists(hub_root / rules_mdc_rel)` |
| FR-002 | Либо создать missing `workflow-*.mdc` under video role dirs, либо `route_map` на реальные shared files — **один** SoT, не оба. | s01 | as-built README = flat `.cursor/rules/video/` (не `script_developer/`); SoT = route_map/flat resolver на существующие files + create missing STORYBOARD/DECOMPOSE; `rg` 0 hits ghost `script_developer/workflow-` for video pack |
| FR-003 | Manifest entries `verify-script`, `verify-edit`, `verify-publish` с claude copy_to + codex materialize. | s02 | yaml keys + `.claude/agents/verify-edit.md` + `.codex/agents/verify-edit.toml` after `runtime-sync` |
| FR-004 | Parity source = `harness/agents/*.md` set, not `REQUIRED_CODEX_AGENTS` hardcoded allowlist-only. | s04 | fixture undeclared `harness/agents/orphan-probe.md` → parity fail; green only when glob ⊆ declared ∪ explicit excluded |
| FR-005 | Stop/start contracts include three ids (VERIFY_FINISH or phase-aware map). | s03 | `verify-edit` ∈ stop validate set; pytest mapping TM-005 |
| FR-006 | BRIEF/STORYBOARD/SHOOT: `no_gate_reason` in phase_registry. | s03 | yaml field present; SHOOT `need_verify` не true при `verify_agent: null` |
| FR-007 | pytest: each intent command path exists; broken fixture `pack_route_missing`. | s01 | TM-001 + TM-002 |
| FR-008 | `bin/runtime-sync --check` includes new TOML or documents generate step. | s02 | `bin/runtime-sync --check` exit 0 after materialize three toml |
| FR-009 | Kind I: pack README не утверждает «fully wired» пока FR-007 red. | s05 | README honest after tests; no «fully wired» / «pack works» without Path.exists |
| FR-010 | Не reuse verify-implement contract verbatim (051 axiom) — keep distinct prompts, wire same **pipeline**. | s02, s03 | prompts remain `verify-script.md` etc.; stop uses `loop-gate-verdict/v1`; not copy implement body; not map video agent → software `mb-finish implement` blindly |
| FR-011 | JANITOR no-gate (audit 02 §7) **не** в этом эпике кроме если video janitor — skip. | — | Appetite/OOS; не video janitor |
| US-001 | Как operator SCRIPT PLAN, я хочу route на существующий workflow. | s01 | `Path.exists(route_command result)` |
| US-002 | Как Codex, я хочу TOML для verify-edit. | s02 | `.codex/agents/verify-edit.toml` after materialize |
| US-003 | Как parent EDIT, я хочу SubagentStop принять gate JSON verify-edit. | s03 | agent in VERIFY/stop set; fence validates |
| US-004 | Как CI, я хочу parity fail если agents/*.md не в manifest. | s04 | orphan prompt fixture |
| SC-001 | 0 missing video routes | s01 | pytest e2e |
| SC-002 | 3 video agents in manifest+toml | s02 | files |
| SC-003 | orphan prompt fails parity | s04 | pytest |
| SC-004 | no_gate_reason on ungated phases | s03 | yaml+test |
| AC+1 | route_command video commands → existing files. | s01 | Path.exists |
| AC+2 | Three agents materialized both runtimes. | s02 | claude md + codex toml |
| AC+3 | Parity fails on undeclared prompt file. | s04 | TM-004 plan QA |
| AC+4 | Stop validates video verify JSON like software. | s03 | same validate_boundary gate schema |
| AC−1 | Нет ok=true + missing path. | s01, s06 | fail-closed `pack_route_missing` |
| AC−2 | Нет parity green на subset manifest. | s04, s06 | source = glob agents/*.md |
| AC−3 | Нет silent skip video verify. | s03, s06 | ids in stop set; no skip-not-in-hardcoded |
| AC−4 | Нет dual route_map + ghost role-subdir без delete. | s01, s06 | one SoT; purge concat ghost |
| AC−5 | Нет copy verify-implement as video SoT. | s02, s03 | distinct prompt files |
| TM-001 | SCRIPT PLAN path exists | s01 | `bin/pytest loop/tests/test_workflow_pack_video_e2e.py -q --tb=line -k script_plan_path` |
| TM-002 | missing route fixture → pack_route_missing | s01 | pytest fail-closed |
| TM-003 | manifest has 3 video agents | s02 | yaml+pytest |
| TM-004 | orphan md fails parity | s04 | pytest fail (plan QA TM-004 = US-004; Failure matrix TM-002 same outcome) |
| TM-005 | stop mapping verify-edit | s03 | unit in set |
| TM-006 | software pack still routes | s05 | pytest software `BACK IMPLEMENT` path exists |
| TM-007 | dual ghost dirs | s01, s06 | rg role-subdir builder for video → 0 live concat |
| Failure matrix TM-001 | missing workflow file → pack_route_missing | s01 | |
| Failure matrix TM-002 | orphan agent md → parity fail | s04 | |
| Failure matrix TM-003 | video verify not in stop set | s03 | |
| Failure matrix TM-004 | BRIEF has fake verify → no_gate_reason | s03 | |
| Failure matrix TM-005 | Codex toml missing → materialize | s02 | |
| Failure matrix TM-006 | software route regression | s05 | |
| Failure matrix TM-007 | dual ghost dirs | s01, s06 | |
| Independent Test PASS | SCRIPT PLAN path exists; verify-edit.toml exists; orphan md fails. | s01, s02, s04 | named pytest |
| Independent Test FAIL | «manifest yaml has keys» without files; «prompt files exist» without manifest. | s01–s06 | dilution = FAIL ANALYZE |
| Technology axiom | Route = existing path or explicit route_map; every `harness/agents/*.md` declared or advisory/unmaterialized with reason; video verify same stop/validate pipeline; phases without verify = `no_gate_reason` | s01–s06 | ladder add→wire→enforce→purge |
| Out of scope | ffmpeg live gate | — | Appetite `cut_list`; follow_up leftover T-HUB-051 tool-gate CREATIVE |
| Out of scope | full video rules prose | — | Appetite `cut_list` |
| Out of scope | template pack authoring | — | Appetite `cut_list` |
| Out of scope | JANITOR no-gate (audit 02 §7) | — | FR-011 skip |
| Out of scope | software verify rewrite; 067 full doctor | — | plan Не; 067 consumes this |
| Out of scope | T-HUB-051 ffmpeg real render / CREATIVE tool-gate | — | soft dep; не блокирует 064 |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| Inventory commands vs FS (red tests) | plan §До DECOMPOSE #1 · FR-001/007 · US-001 | s01 (слито с route SoT — один Path.exists outcome) |
| fix route_command / add workflow files XOR route_map; purge ghost builder | plan §До DECOMPOSE #2 · FR-002 · AC−4 · TM-007 | s01 |
| manifest + materialize 3 agents | plan §До DECOMPOSE #3 · FR-003/008 · US-002 · SC-002 | s02 |
| stop/start mapping + no_gate_reason | plan §До DECOMPOSE #4 · FR-005/006 · US-003 · SC-004 | s03 |
| source-driven parity (orphan fail) | plan §До DECOMPOSE #5 · FR-004 · US-004 · SC-003 | s04 |
| Kind I + software regression | plan §До DECOMPOSE #6 · FR-009 · TM-006 | s05 |
| purge leftover hardcoded REQUIRED_CODEX_AGENTS exclusivity | plan §До DECOMPOSE #7 · Replacement A | s06 |
| Add → Wire → Enforce → Purge | workflow-behavior-first §3 | s01 add+route-enforce · s02 add agents · s03 wire stop · s04 enforce parity · s05 Kind I · s06 purge |
| Data flow: SCRIPT PLAN → pack resolve → route_command Path.exists; spawn verify-edit → manifest → toml/md → SubagentStop VERIFY set → gate schema | plan §Eng review spine | s01, s02, s03 |
| Failure matrix TM-001…007 | plan §Failure matrix · §QA consumes | s01–s06 |
| Intent pipeline video_production / content_factory | `loop/workflow/intent_routing.yaml` | s01 |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Operator `WORKFLOW_PACK=video-production` + `SCRIPT PLAN` получает **существующий** workflow file | s01 |
| Missing dir/file → `ok` false `pack_route_missing`, не 404-декорация | s01 |
| Один SoT маршрутов: нет dual `route_map` + ghost `script_developer/` concat | s01, s06 |
| Codex/Claude: три video verify агента materialized (toml+md) | s02 |
| `bin/runtime-sync --check` зелёный с новыми TOML | s02 |
| Parent EDIT: SubagentStop принимает gate JSON `verify-edit` как software verify | s03 |
| BRIEF/STORYBOARD/SHOOT не притворяются verify без агента — `no_gate_reason` | s03 |
| CI: orphan `harness/agents/*.md` валит parity (не subset manifest) | s04 |
| README/CLAUDE pack table не врёт «fully wired» до зелёного FR-007 | s05 |
| Software pack `BACK IMPLEMENT` path exists (нет регрессии) | s05 |
| `REQUIRED_CODEX_AGENTS` не единственный parity source; leftover exclusivity purged | s04, s06 |
| Independent Test PASS: SCRIPT PLAN path exists; verify-edit.toml exists; orphan md fails | s01 + s02 + s04 |
| Independent Test FAIL dilution: «manifest yaml has keys» without files | s01–s06 (не done) |
| ffmpeg live / full video rules / template authoring / JANITOR / 067 doctor | — Appetite / follow_up 051, 067 |

## Replacement cleanup (plan → steps)

> Brownfield leftover **executable routes + manifest agents**. Completeness: **add → wire → enforce → purge**. Kind A\|B\|C\|I. Финальный `s06-legacy-fallback-purge` с явными блоками `sunset_inventory:` и `grep_control:`.

| Устаревает (path / symbol) | Kind | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `REQUIRED_CODEX_AGENTS` as sole parity source | A | agents dir glob ∪ manifest declare | s04 (source), s06 (leftover exclusive tests) | no | hardcoded exclusive set |
| `route_command` builder to nonexistent role-subdir (`script_developer/workflow-plan.mdc`) | A | existing files / explicit `route_map` (один SoT) | s01, s06 | no | as-built: `_resolve_role_subdir("script")` → `script_developer` под `.cursor/rules/video/` — файла нет |
| parity skip video (`harness/agents/verify-*.md` orphan while checker green) | A | include three agents + glob source | s02, s04, s06 | no | |
| tests asserting `rules_mdc_rel == packs/video/rules/script_developer/workflow-plan.mdc` without Path.exists | A | e2e exists check + rewrite custom-prefix if it encodes ghost | s01, s06 | no | `test_route_command_custom_prefix` |
| Codex without video toml | B | generated `.codex/agents/verify-{script,edit,publish}.toml` via manifest materialize | s02, s06 | no | |
| `ok=true` on missing route (`CommandRoute` всегда отдаёт rel path без exists) | C | fail-closed `pack_route_missing` | s01, s06 | yes | FORBIDDEN silent ok |
| «Claude symlink enough» (`.claude/agents/verify-edit.md` есть, manifest нет) | C | manifest declare + materialize both runtimes | s02, s06 | yes | |
| docs «video pack works» / fully wired | I | honest after FR-007 green | s05, s06 | no | `workflows/video/README.md`, CLAUDE pack table |
| CLAUDE.md pack table if claims full video execute | I | match reality (prefixes exist; routes exist after s01) | s05, s06 | no | table currently lists prefixes only — keep honest |

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-video-route-exists-fail-closed.yaml](../yaml/steps/s01-video-route-exists-fail-closed.yaml) | [s01…](../../implement/T-HUB-064-video-pack-route-verify-parity/s01-video-route-exists-fail-closed.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-manifest-materialize-video-verify.yaml](../yaml/steps/s02-manifest-materialize-video-verify.yaml) | [s02…](../../implement/T-HUB-064-video-pack-route-verify-parity/s02-manifest-materialize-video-verify.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-stop-mapping-no-gate-reason.yaml](../yaml/steps/s03-stop-mapping-no-gate-reason.yaml) | [s03…](../../implement/T-HUB-064-video-pack-route-verify-parity/s03-stop-mapping-no-gate-reason.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-source-driven-agent-parity.yaml](../yaml/steps/s04-source-driven-agent-parity.yaml) | [s04…](../../implement/T-HUB-064-video-pack-route-verify-parity/s04-source-driven-agent-parity.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-kind-i-software-regression.yaml](../yaml/steps/s05-kind-i-software-regression.yaml) | [s05…](../../implement/T-HUB-064-video-pack-route-verify-parity/s05-kind-i-software-regression.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-legacy-fallback-purge.yaml](../yaml/steps/s06-legacy-fallback-purge.yaml) | [s06…](../../implement/T-HUB-064-video-pack-route-verify-parity/s06-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | completed |
**needs_creative:** все `no` (plan: CREATIVE need нет; 051 owns tool-gate CREATIVE).

**Justification (6 sNN, не 7):** plan §До DECOMPOSE #1 inventory — red tests того же Path.exists, что #2 route SoT; слиты в s01 (behavior-first §3a core+CLI / schema+paths). Purge остаётся отдельным s06 (apply ≠ purge).
