# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-024-validate-traceability  
**План:** [plan/T-HUB-024-validate-traceability/md/plan.md](../plan/T-HUB-024-validate-traceability/md/plan.md)  
**Machine index:** [index.yaml](index.yaml) — **канон status**  
**Дата:** 2026-08-31  
**Режим:** BACK DECOMPOSE  

Каждый шаг — атомарная задача (один продакшн-модуль или один test-file). Shard: `sNN-<slug>.yaml`.

> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `index.yaml`.** Этот файл в IMPLEMENT не грузить.  
> **status SoT = `index.yaml` only.**

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность (сессия DECOMPOSE) |
| `architecture-patterns` | fail-closed CLI, parser layering (сессия PLAN) |

**Per-step:** skills gate в каждом `sNN` (TDD · python-testing-patterns · modern-python).

---

## Requirements coverage (plan → steps)

| Req ID | Кратко | sNN | Notes |
| :--- | :--- | :--- | :--- |
| US-001 | Machine-enforced traceability: FR→decompose→implement→ac | s01, s02, s05 | parsers + checker + opt-in loop |
| FR-001 | parse_plan_requirements — FR/SC/US из plan.md | s01 | parse_plan_requirements() |
| FR-002 | parse_decompose_refs — sNN→plan_refs + out_of_scope | s01 | parse_decompose_refs() |
| FR-003 | parse_implement_evidence — sNN→files/tests/status | s01 | parse_implement_evidence() |
| FR-004 | run_checks — 4 check rules → Finding list | s02 | run_checks() checker layer |
| FR-005 | Reverse: sNN без plan_refs → HIGH (audit-* → MEDIUM) | s02 | check rule b |
| FR-006 | TraceReport dataclass + Finding stable IDs TR-001… | s01, s02 | dataclasses |
| FR-007 | format_report (json + human) | s02 | format_report() |
| FR-008 | Findings schema: severity CRITICAL/HIGH/MEDIUM/LOW | s01, s02 | Finding.severity |
| FR-009 | Exit 0 CRITICAL=0; exit 1 CRITICAL≥1; exit 2 missing dir | s02 | exit code logic |
| FR-010 | scan_ac_markers — @pytest.mark.ac grep | s03 | scan_ac_markers() |
| FR-011 | enrich_with_ac + --ac-strict | s03 | enrich_with_ac() |
| FR-012 | YAML-CONTRACT §Traceability fields | s04 | docs patch |
| SC-001 | T-HUB-021 decompose validates CRITICAL=0 (acceptance на hub fixture) | s05 | integration test |
| SC-002 | CLI exit 2 на missing plan.md | s02 | test_cli_exit2_missing_plan |
| SC-003 | --strict elevates HIGH→CRITICAL | s02, s03 | run_checks(strict=True) |
| SC-004 | YAML-CONTRACT + workflow decompose FINISH tip | s04 | docs |
| AC+ #1 | exit 0 когда CRITICAL=0 | s02 | exit code rule |
| AC+ #2 | exit 1 при CRITICAL≥1 | s02 | exit code rule |
| AC+ #3 | --strict доступен и работает | s02, s03 | CLI flag |
| AC+ #4 | YAML-CONTRACT обновлён | s04 | docs |
| AC+ #5 | EPIC_TRACEABILITY_CHECK opt-in в loop | s05 | env flag |
| AC− #1 | Не заменяет ANALYZE workflow | s04 | docs explicit |
| AC− #2 | opt-in scan_ac_markers — молчит без --tests-dir | s03 | soft opt-in |
| AC− #3 | exit 2 (не 0) при missing dir — fail-closed | s02 | check |
| AC− #4 | loop: exit 1 → warn only (не блокировать) | s05 | context_loop.py |

---

## Stages coverage (plan outline → steps)

| Этап плана | sNN покрывает |
| :--- | :--- |
| Data layer: parsers + dataclasses | s01 |
| CLI + checker rules + exit codes | s02 |
| AC marker scanner + --ac-strict | s03 |
| Docs: YAML-CONTRACT + workflow tip | s04 |
| Loop integration + pytest.mark.ac + integration tests | s05 |

---

## Outcome map

| Outcome (из plan §Outcome) | sNN | Verifiable |
| :--- | :--- | :--- |
| `epic_resolve validate-traceability` green on clean epic | s02, s05 | integration test exit 0 |
| CRITICAL finding on uncovered FR in plan | s02 | test_run_checks_critical_on_uncovered_req |
| HIGH finding on sNN without plan_refs | s02 | test_run_checks_high_on_shard_no_plan_refs |
| HIGH finding on completed impl without tests | s02 | test_run_checks_high_on_completed_without_tests |
| --strict elevates HIGH | s02, s03 | test_cli_strict + test_enrich_strict |
| Exit 2 on missing plan.md | s02 | test_cli_exit2_missing_plan |
| scan_ac_markers collects pytest.mark.ac | s03 | test_scan_ac_markers_finds_marks |
| YAML-CONTRACT documents traceability fields | s04 | rg 'Traceability fields' |
| opt-in EPIC_TRACEABILITY_CHECK in loop | s05 | context_loop.py + project.env |
| pytest.mark.ac registered | s05 | pytest.ini markers |

---

## Replacement cleanup

greenfield — новые файлы (traceability.py, test_traceability_*.py, fixtures). Коды-патчи в существующих:

| Файл | Тип изменения | sNN | deletes |
| :--- | :--- | :--- | :--- |
| `.claude/hooks/epic_resolve.py` | ADD subcommand | s02 | n/a |
| `loop/context_loop.py` | ADD opt-in call | s05 | n/a |
| `loop/YAML-CONTRACT.md` | ADD section | s04 | n/a |
| `.cursor/rules/back_developer/workflow-decompose.mdc` | ADD FINISH tip | s04 | n/a |
| `.claude/project.env` | ADD commented flag | s05 | n/a |
| `pytest.ini` | ADD markers | s05 | n/a |

Нет заменяемых / удаляемых модулей — greenfield дополнение существующего tooling.

## Очередь шагов

| step_id | title & files | next_phase | status |
| :--- | :--- | :--- | :--- |
| **s01** | Parsers + report schema — plan/decompose/implement readers + TraceReport dataclass · [yaml](s01-parsers-schema.yaml) | BACK IMPLEMENT | completed |
| **s02** | CLI validate-traceability — epic_resolve command + exit codes + JSON report · [yaml](s02-cli-validate-traceability.yaml) | BACK IMPLEMENT | completed |
| **s03** | AC marker scanner — pytest.mark.ac collector + --ac-strict flag · [yaml](s03-ac-marker-scanner.yaml) | BACK IMPLEMENT | completed |
| **s04** | YAML-CONTRACT + workflow decompose FINISH tip (docs-only) · [yaml](s04-yaml-contract-docs.yaml) | BACK IMPLEMENT | completed |
| **s05** | Loop prompt opt-in EPIC_TRACEABILITY_CHECK + integration test on hub fixture · [yaml](s05-loop-integration.yaml) | BACK IMPLEMENT | completed |