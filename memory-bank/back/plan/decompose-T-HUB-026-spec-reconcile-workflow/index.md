# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-026-spec-reconcile-workflow
**План:** [plan-T-HUB-026-spec-reconcile-workflow.md](../plan-T-HUB-026-spec-reconcile-workflow.md)
**Machine index:** [index.yaml](index.yaml) — **канон status**
**Дата:** 2026-08-31
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача (один модуль или один test-file). Shard: `sNN-<slug>.yaml`.

> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `index.yaml`.** Этот файл в IMPLEMENT не грузить.
> **status SoT = `index.yaml` only.**

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, workflow docs (s03, s04) |
| `tdd` | TDD red→green fixtures (s01, s05) |
| `python-testing-patterns` | pytest tmp_path fixture pattern |
| `modern-python` | dataclass, typing, Path |

**Per-step:** skills gate в каждом `sNN`.

---

## Requirements coverage (plan → steps)

| ID | Requirement | Steps | Rationale |
|:---|:---|:---|:---|
| FR-001 | workflow-reconcile.mdc STRICTLY READ-ONLY | s03 | workflow create |
| FR-002 | BACK RECONCILE в mainrule.mdc | s03 | mainrule edit |
| FR-003 | CLI reconcile-spec (--cwd, --plan-id, --format, --strict) | s02 | CLI subparser |
| FR-003a | SoT = tasks.md Status=active | s01, s02 | list_active_epic_ids |
| FR-004 | Checks: as_built (a), delta (b), plan layout (c), constitution (d) | s01 | core checks |
| FR-005 | Reuse traceability parsers (T-HUB-024) | s01 | epic_yaml/epic_portfolio |
| FR-006 | Report schema reconcile-report/v1; RC-001…RC-003 | s01 | core schema |
| FR-007 | Reconcile artifact template | s03 | workflow FINISH contract |
| FR-008 | Appetite: plan.md + decompose index optional | s04 | template edits |
| FR-009 | FINISH writes reconcile yaml; does not mutate plan/decompose | s03 | workflow constraint |
| FR-010 | Reconcile-report/v1: findings with severity HIGH/MEDIUM/LOW | s01 | Finding dataclass |
| FR-011 | Категории: stale_as_built, missing_delta, missing_plan_path, constitution_missing | s01 | core checks |
| FR-012 | Exit: 0 default / 1 strict+HIGH / 2 unknown plan-id | s01, s02 | exit code logic |

## AC coverage

| AC | Criterion | Steps | Done signal |
|:---|:---|:---|:---|
| AC+ #1 | BACK RECONCILE in mainrule index | s03 | grep mainrule.mdc |
| AC+ #2 | workflow-reconcile.mdc + lean gate exist | s03 | file check |
| AC+ #3 | reconcile-spec CLI: active sweep + --plan-id | s02 | CLI smoke |
| AC+ #4 | Stale as_built + active sweep fixture tests pass | s05 | pytest green |
| AC+ #5 | plan.md Appetite section added | s04 | rg timebox_days |
| AC+ #6 | Reconcile artifact template exists | s03 | file check |
| AC+ #7 | Read-only enforced (workflow + test) | s03, s05 | rg + pytest |
| AC− #1 | Не мутировать plan/decompose/implement при reconcile | s01, s03 | read-only design |
| AC− #2 | Не заменять AUDIT converge | s03 | workflow scope |
| AC− #3 | Не auto-cut scope in v1 | s04 | advisory only |
| AC− #4 | Не scan entire repo — bounded | s01 | _PATH_PREFIXES |
| AC− #5 | unknown plan_id → exit 2 | s01, s02 | exit code |
| AC− #6 | Default sweep — не требует знать epic_id | s01, s02 | list_active_epic_ids |

## Stages coverage (план канон → shards)

| Этап плана | Шаги | sNN |
|:---|:---|:---|
| reconcile.py движок + report schema | core checks, list_active, resolve_bundle | s01 |
| CLI subcommand wire | reconcile-spec argparse + handler | s02 |
| Workflow + mainrule + lean gate | BACK RECONCILE mode docs | s03 |
| Template: plan Appetite + decompose index mirror | timebox/cut_list fields | s04 |
| pytest suite | stale fixture, sweep, read-only, CLI | s05 |

## Outcome map (goal → sNN deliverable)

| User outcome | Step | Deliverable |
|:---|:---|:---|
| Drift detected after hotfix | s01 | RC-001 HIGH finding в reconcile_epic |
| Default sweep без знания epic_id | s01, s02 | list_active_epic_ids + CLI default |
| BACK RECONCILE как mode в router | s03 | mainrule row + workflow-reconcile.mdc |
| PM видит timebox/cut в plan | s04 | ## Appetite в plan.md template |
| Все тесты зелёные | s05 | pytest suite pass |

## Replacement cleanup

n/a — greenfield workflow + CLI. Нет замены существующих модулей. Spike-код в reconcile.py (`as_built` section s01) дополняется, не заменяет существующий файл; deletes = [] у всех shards.

---

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-reconcile-core.yaml](s01-reconcile-core.yaml) | pending | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-reconcile-cli.yaml](s02-reconcile-cli.yaml) | pending | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-workflow-mainrule.yaml](s03-workflow-mainrule.yaml) | pending | no | no | BACK IMPLEMENT | completed |
| **s04** | [s04-appetite-template.yaml](s04-appetite-template.yaml) | pending | no | no | BACK IMPLEMENT | completed |
| **s05** | [s05-tests-readonly.yaml](s05-tests-readonly.yaml) | pending | no | yes | BACK IMPLEMENT | completed |