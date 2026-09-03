# Реестр шагов — T-HUB-034-harness-janitor-gc

**Plan ID:** T-HUB-034-harness-janitor-gc  
**План:** [plan/T-HUB-034-harness-janitor-gc/md/plan.md](../plan/T-HUB-034-harness-janitor-gc/md/plan.md)  
**Machine index:** [index.yaml](index.yaml)  
**Дата:** 2026-08-31  
**Режим:** BACK DECOMPOSE

> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `index.yaml`.** Этот файл в IMPLEMENT не грузить.
> **status SoT = `index.yaml` only.**

---

## Requirements coverage (plan → steps)

| Req ID | Кратко | sNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | Module `loop/janitor/` — `scan(cwd) -> JanitorReport`, schema `janitor-report/v1` | s01 | Pydantic model + scan entry point |
| FR-002 | Finding categories: orphan_implement_yaml, stale_index_status, dead_plan_ref, duplicate_epic_id, orphan_events_dir, episode_retention_exceeded | s02, s03 | s02 = orphan/stale/dead/duplicate; s03 = events/episode |
| FR-003 | Reuse reconcile + traceability + index mirror checks | s02 | calls epic.traceability, epic.reconcile internals |
| FR-004 | CLI `epic_resolve.py janitor-scan` + `janitor-gc --dry-run\|--apply` | s04 | subcommands wired in epic_resolve.py |
| FR-005 | Workflow `.cursor/rules/back_developer/workflow-janitor.mdc` + lean gate (READ-ONLY scan path) | s05 | mdc file |
| FR-006 | Register `BACK JANITOR` in mainrule (optional P1 if CLI sufficient v1) | s05 | P1, deferred if CLI covers v1 |
| FR-007 | Document weekly cron example in loop/README.md | s05 | README patch |
| FR-008 | Tests per finding category; gc apply dry-run | s04 | pytest fixtures |
| AC-1 | janitor-scan CLI + report schema | s01, s04 | |
| AC-2 | janitor-gc dry-run/apply with whitelist | s03, s04 | |
| AC-3 | Reuses reconcile parsers | s02 | |
| AC-4 | README cron doc | s05 | |
| AC-5 | Optional BACK JANITOR workflow | s05 | P1 |
| SC-001 | Stale artifact detected (pytest fixture) | s04 | |
| SC-002 | gc apply refuses non-whitelist (pytest) | s04 | |
| SC-003 | janitor-report schema valid (pydantic test) | s01 | |
| NFR-01 | janitor-scan read-only — zero writes | s02, s03 | enforced by whitelist; cp: rg for open() calls in scan path |
| NFR-02 | janitor-gc apply restricted to whitelist paths only | s03 | fail-closed if path not in whitelist |
| NFR-03 | No duplication of reconcile/traceability logic | s02 | reuse imports, cp: rg for clone patterns |
| US-001 | Weekly operator: janitor report stale decompose indexes | s02, s04 | |
| US-002 | Platform: gc only whitelist paths (tier0) | s03, s04 | |
| US-003 | Operator: BACK JANITOR mode in router | s05 | P1 |

---

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| Janitor module scaffold + schema | plan §FR-001, §AC-1 | s01 |
| Orphan/stale/dead/duplicate detectors | plan §FR-002, §FR-003 | s02 |
| Episode/events retention detectors + janitor-gc whitelist engine | plan §FR-002, §AC-2 | s03 |
| CLI wiring + full pytest suite | plan §FR-004, §FR-008 | s04 |
| Workflow mdc + README cron + mainrule wire | plan §FR-005, §FR-006, §FR-007 | s05 |

---

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Operator получает читаемый отчёт по entropy без запуска AUDIT | s01 (schema+scan), s02 (detectors), s04 (CLI/tests) |
| Platform может сделать bounded repair без ручного вмешательства (tier-0 style) | s03 (gc whitelist), s04 (CLI+dry-run tests) |
| Повторное использование reconcile/traceability — нет дублирования логики | s02 (import-reuse detectors) |
| Janitor-scan 100% read-only, ни один файл не изменяется | s02, s03 (read-only scan path; gc path separately gated) |
| Weekly cron поддерживается документацией | s05 (README cron example) |
| Guided BACK JANITOR режим (P1) | s05 (workflow mdc) |
| Out of scope: full AUDIT / reconcile-spec rewrites / new reconcile logic | — / T-HUB-026 |
| Out of scope: UI / frontend для janitor | — / future epic |

---

## Replacement cleanup (plan → steps)

n/a — нет замен. Эпик greenfield: новый модуль `loop/janitor/`, новые CLI subcommands, новый workflow mdc. Существующие модули (`epic.reconcile`, `epic.traceability`) не заменяются, а переиспользуются.

---

## Очередь шагов (BACK)

| step_id | title & files | needs_creative | tdd | next_phase | status |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-janitor-schema.yaml](s01-janitor-schema.yaml) — JanitorReport schema + scan entry point | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-janitor-detectors-orphan-stale.yaml](s02-janitor-detectors-orphan-stale.yaml) — Orphan/stale/dead/duplicate detectors (reuse reconcile+traceability) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-janitor-events-retention-gc.yaml](s03-janitor-events-retention-gc.yaml) — Events/episode retention detector + janitor-gc whitelist engine | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-janitor-cli-tests.yaml](s04-janitor-cli-tests.yaml) — CLI subcommands (janitor-scan / janitor-gc) + full pytest suite | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-janitor-workflow-docs.yaml](s05-janitor-workflow-docs.yaml) — workflow-janitor.mdc + mainrule wire + README cron | no | no | BACK IMPLEMENT | completed |