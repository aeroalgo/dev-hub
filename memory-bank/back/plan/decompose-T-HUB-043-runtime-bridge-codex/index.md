# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-043-runtime-bridge-codex
**План:** [plan-T-HUB-043-runtime-bridge-codex.md](../plan-T-HUB-043-runtime-bridge-codex.md)
**Machine index:** [index.yaml](index.yaml) — **канон status**
**Дата:** 2026-09-02
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml`.

> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `index.yaml`.** Этот файл в IMPLEMENT не грузить.
> **status SoT = `index.yaml` only.**

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность (сессионный) |
| `python-testing-patterns` | Core — TDD + fixtures |

Per-step skills gate: Core (tdd · python-testing-patterns · modern-python · python-anti-patterns) + situational из skills-gate-situational.mdc; канон в каждом sNN.

---

## Requirements coverage (plan → steps)

| Req ID | Кратко | sNN | Notes |
| :--- | :--- | :--- | :--- |
| AC+ #1 | `EPIC_RUNTIME=codex` + mock → loop invokes codex | s06, s07 | CodexAdapter build_command + dispatch wiring |
| AC+ #2 | manifest.yaml exists; runtime-sync generates .codex/hooks.json | s01, s02, s04 | schema + sync core + hooks generator |
| AC+ #3 | runtime-sync --check non-zero on stale | s03 | CLI --check mode |
| AC+ #4 | Missing codex binary → exit 127, no fallback | s06 | CodexAdapter resolve_binary |
| AC+ #5 | codex log fixture → SessionAnalysis completed vs aborted | s08 | analyze_log + fixtures |
| AC+ #6 | .codex/agents/verify-implement.md materialized | s05 | agent materializer |
| AC− #1 | Hand-edited .codex/hooks.json as SoT | s04 | generated header + manifest hash |
| AC− #2 | Separate spawn policy for codex | s07 | dispatch uses same spawn-hard |
| AC− #3 | Silent fallback codex → claude | s06, s07 | fail-closed assert in adapter + registry |
| AC− #4 | Dual dispatch run_codex_session in loop.sh | s07, s11 | no if/else in loop.sh; purge if any |
| FR-001 | harness/manifest.yaml schema harness-manifest/v1 | s01 | |
| FR-002 | runtime_materializers/sync.py — read manifest, emit targets | s02 | |
| FR-003 | bin/runtime-sync CLI --runtime --check --apply | s03 | |
| FR-004 | Generate .codex/hooks.json from manifest | s04 | |
| FR-005 | Materialize .codex/agents/ from harness/agents/ | s05 | |
| FR-006 | CodexAdapter implements RuntimeAdapter | s06 | |
| FR-007 | Register codex in runtime_registry.yaml | s07 | |
| FR-008 | analyze_log for codex output fixtures | s08 | |
| FR-009 | codex/bin/which-codex.sh resolve PATH/env | s06 | bundled with adapter |
| FR-010 | session_resilience / adapter tests with codex fixtures | s08, s09 | |
| FR-011 | Optional: manifest hook rows for dsh bridge (doc) | s10 | docs-only step |
| FR-012 | Preflight hook soft warn on drift (v1) | s03 | session-start integration |
| US-001 | EPIC_RUNTIME=codex → loop headless | s06, s07 | |
| US-002 | Manifest-driven sync: one fix → all runtimes | s01, s02, s04 | |
| US-003 | Stop-gate / spawn-gate semantics unchanged for codex | s09 | integration test |
| US-004 | runtime-sync --check fail on drift (CI) | s03 | |
| SC-001 | mock codex + loop invokes | s07 | test_codex_runtime_adapter |
| SC-002 | runtime-sync --check detects drift | s03 | test_runtime_sync |
| SC-003 | codex in registry; foo fail-closed | s07 | test_runtime_registry |
| SC-004 | stop-gate integration smoke | s09 | test_codex_hooks_bridge |
| NFR: fail-closed | missing binary → exit 127 (TM-006) | s06 | |
| NFR: no fallback | codex fail → exit 127 not claude (TM-002/C-fallback) | s06, s07 | |
| NFR: generated SoT | hooks.json always regenerated, not hand-maintained | s04, s11 | purge ensures no stale |
| §0.11 | external codex CLI argv contract | s06 | codex exec args in build_command |
| TM-001..TM-006 | failure matrix test IDs | s06–s09 | mapped per shard |
| Out of scope | interactive codex loop | — | follow-up / v2 |
| Out of scope | full DSH preset auto-regen | — | cut_list; optional s10 doc only |
| Out of scope | loop preflight hard fail v2 | — | cut_list; s03 soft warn only |

---

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| manifest schema + validation | plan §manifest.yaml / FR-001 | s01 |
| sync core (read manifest → emit targets) | plan §runtime_materializers / FR-002 | s02 |
| CLI entrypoint runtime-sync | plan §Sync CLI / FR-003 / US-004 | s03 |
| hooks.json generator + hash guard | plan §Hooks bridge / FR-004 / AC− #1 | s04 |
| agent materializer (.codex/agents/) | plan §Agent materialize / FR-005 / AC+ #6 | s05 |
| CodexAdapter + which-codex.sh + binary resolve | plan §Codex invoke / FR-006 / FR-009 | s06 |
| registry entry + dispatch wiring | plan FR-007 / AC+ #1 / SC-001 / SC-003 | s07 |
| analyze_log fixtures + tests | plan FR-008 / AC+ #5 / TM-001 TM-002 | s08 |
| stop-gate / spawn-gate bridge integration test | plan AC- #2 / US-003 / SC-004 / TM-004 | s09 |
| dsh manifest rows doc + optional dsh preset note | plan FR-011 / cut_list footnote | s10 |
| legacy purge — no run_codex if/else | plan AC− #4 / Replacement cleanup A/C | s11 |

---

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| **Codex как первоклассный runtime** — `EPIC_RUNTIME=codex` → loop headless без ручного fork | s06 (adapter), s07 (dispatch), s08 (log analysis) |
| **Manifest-SoT**: один yaml → синхронизирует hooks + agents для любого runtime | s01 (schema), s02 (sync core), s04 (hooks generator), s05 (agent mat.) |
| **--check drift detection** (CI gate, US-004) | s03 (CLI + hash check) |
| **Fail-closed semantics**: нет fallback, нет двойного dispatch | s06 (exit 127 on missing binary), s07 (registry fail-closed), s11 (purge loop.sh if/else) |
| **Stop-gate / spawn-gate semantics unchanged** — codex сессия = те же gate-вердикты | s09 (hooks bridge integration test) |
| **Agent materialization** — harness/agents/ как SoT, .codex/agents/ как output | s05 |
| **DSH bridge doc** — optional regen documented (cut from automation) | s10 |
| Out of scope: interactive codex, full DSH preset automation, preflight hard fail v2 | — / follow-up |

---

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| любой `run_codex_session` if/else в loop.sh (если появится) | A | CodexAdapter dispatch | s11 | no | AC− #4; s11 сканирует и удаляет если присутствует |
| `.codex/hooks.json` hand-maintained (нет GENERATED header) | C | generated файл с manifest hash | s04 | yes | s04 добавляет header; s11 grep-контроль |
| `README` раздел "loop не запускает Codex" | A | codex runtime section | s10 | no | docs-only; update in-epic |
| shim dsh preset drift (hand-maintained .prompt.md) | A | manifest preset row (optional) | s10 | no | cut_list; doc step; full automation = follow-up |

Финальный purge: **s11-legacy-purge** — sunset_inventory + grep_control по всем строкам выше.

---

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-manifest-schema.yaml](s01-manifest-schema.yaml) | s01-manifest-schema.yaml | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-sync-core.yaml](s02-sync-core.yaml) | s02-sync-core.yaml | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-runtime-sync-cli.yaml](s03-runtime-sync-cli.yaml) | s03-runtime-sync-cli.yaml | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-hooks-json-generator.yaml](s04-hooks-json-generator.yaml) | s04-hooks-json-generator.yaml | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-agent-materializer.yaml](s05-agent-materializer.yaml) | s05-agent-materializer.yaml | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-codex-adapter.yaml](s06-codex-adapter.yaml) | s06-codex-adapter.yaml | no | yes | BACK IMPLEMENT | pending |
| **s07** | [s07-registry-dispatch-wiring.yaml](s07-registry-dispatch-wiring.yaml) | s07-registry-dispatch-wiring.yaml | no | yes | BACK IMPLEMENT | completed |
| **s08** | [s08-analyze-log-fixtures.yaml](s08-analyze-log-fixtures.yaml) | s08-analyze-log-fixtures.yaml | no | yes | BACK IMPLEMENT | completed |
| **s09** | [s09-stop-gate-bridge-test.yaml](s09-stop-gate-bridge-test.yaml) | s09-stop-gate-bridge-test.yaml | no | yes | BACK IMPLEMENT | completed |
| **s10** | [s10-dsh-manifest-doc.yaml](s10-dsh-manifest-doc.yaml) | s10-dsh-manifest-doc.yaml | no | no | BACK IMPLEMENT | completed |
| **s11** | [s11-legacy-purge.yaml](s11-legacy-purge.yaml) | s11-legacy-purge.yaml | no | yes | BACK IMPLEMENT | pending |

**needs_creative:** `no` | `yes (CR-…)` | `yes (CR-…) ✅`
