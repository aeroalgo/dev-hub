# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-050-workflow-pack-memory-bank-paths
**План:** [plan.md](plan.md)
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**
**Дата:** 2026-09-04
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml` — [.cursor/templates/decompose/epic-step.yaml](epic-step.yaml).

> **Path (layout v2 HARD):** этот файл = `plan/T-HUB-050-workflow-pack-memory-bank-paths/md/decompose-index.md`. Machine = `plan/T-HUB-050-workflow-pack-memory-bank-paths/yaml/decompose-index.yaml`. Shards = `yaml/steps/`. **FORBIDDEN** `decompose-<id>/` · `yaml/index.md` · `yaml/index.yaml` · дубль имён.

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность |
| `python-testing-patterns` | pytest матрица, параметризация |
| `architecture-patterns` | pack resolver, enum dispatch |
| `modern-python` | dataclass/enum, Path-native API |

---

## Requirements coverage (plan → steps)

| Req ID | Plan FR text (verbatim) | sNN | Notes |
| :--- | :--- | :--- | :--- |
| US-001 | mb-load session читал activeContext из pack root | s03, s04 | |
| US-002 | mb-finish писал Handoff в pack activeContext | s05 | |
| US-003 | plan/decompose paths under pack role subdirs | s01, s06 | |
| US-004 | forbidden policy per artifact_layout | s02 | |
| US-005 | software pack zero path change | s01, s08 | regression tests |
| FR-001 | resolve_mb_root(cwd) from pack — no string concat `memory-bank/` in hooks | s01 | |
| FR-002 | {mb_root}/activeContext.md — hardcoded path → parameterized | s03 | |
| FR-003 | pack.artifact_layout → policy module (forbidden load) | s02 | |
| FR-004 | resolve_epic_path(kind, epic_id, pack) — parallel glob helpers removed | s06 | |
| FR-005 | same guard as mb-finish on hub vs product cwd | s01, s05 | |
| FR-006 | software pack paths identical to as-built after refactor | s08, s09 | |
| AC+ US-001 | pack video → memory-bank/video/activeContext.md loaded | s04 | |
| AC+ US-002 | FINISH on video pack → correct path written | s05 | |
| AC+ US-003 | resolve_epic_path(plan) → pack-relative | s06 | |
| AC+ US-004 | software-epic-v1 vs production-epic-v1 matrix | s02 | |
| AC+ US-005 | default pack paths identical to as-built | s01, s08 | |
| AC− US-001 | missing pack config → fail-closed (shape invalid diagnostic) | s07 | |
| AC− US-002 | wrong cwd → fail-closed | s01 | |
| TM-001 | video epic integration smoke | s08 | |
| TM-002 | activeContext missing → shape invalid diagnostic | s07 | |
| NFR-001 | software pack: zero regression on existing paths | s08 | |
| NFR-002 | no silent default mb root (fail-closed) | s01, s07 | |
| NFR-003 | delete-in-epic all hardcoded `memory-bank/` string concats in hooks | s09 | |

---

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| pack_layout.py + software handler | plan §До DECOMPOSE s01 | s01 |
| production-epic-v1 handler (forbidden policy) | plan §До DECOMPOSE s02 | s02 |
| epic/core activeContext refactor | plan §До DECOMPOSE s03 | s03 |
| mb_load pack thread | plan §До DECOMPOSE s04 | s04 |
| mb_finish pack thread | plan §До DECOMPOSE s05 | s05 |
| epic_layout pack param (T-HUB-047) | plan §До DECOMPOSE s06 | s06 |
| validate_active_context_shape | plan §До DECOMPOSE s07 | s07 |
| pytest matrix + rg purge verify | plan §До DECOMPOSE s08 | s08 |
| legacy path purge step (deletes) | plan §До DECOMPOSE s09 | s09 |
| Failure matrix (TM-001, TM-002) | plan §Failure matrix | s07, s08 |

---

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| mb-load/mb-finish читают/пишут из pack root без хардкода | s01, s04, s05 |
| forbidden policy зависит от artifact_layout пака, а не hardcoded software-only | s02 |
| activeContext path параметризован через pack resolver | s03 |
| resolve_epic_path(kind, epic_id, pack) → единственная точка разрешения путей | s06 |
| validate_active_context_shape → fail-closed при отсутствии / некорректном файле | s07 |
| Zero regression: software pack paths идентичны as-built | s08 |
| Удаление всех hardcoded `memory-bank/` string concat из hooks/core | s09 |
| video pack integration smoke: memory-bank/video/activeContext.md работает | s08 |

---

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| hardcoded `"memory-bank/activeContext.md"` в `loop/context_loop.py`, `loop/epic_transition.py` | A | `resolve_mb_root(cwd) / "activeContext.md"` | s03, s09 | yes | delete in-epic |
| hardcoded `"memory-bank/"` concat в `harness/hooks/epic/core.py` | A | `resolve_mb_root(cwd)` | s03, s09 | yes | delete in-epic |
| `plan/decompose-{id}/` glob в epic_paths | A | `resolve_epic_path(kind, epic_id, pack)` | s06, s09 | no | |
| software-only forbidden load denylist в `mb_load` | A | `policy_for_layout(artifact_layout)` | s02, s09 | no | |
| параллельные glob-хелперы per-domain в `loop/` | A | единый `resolve_epic_path` | s06, s09 | no | |
| инструкция `memory-bank/` как фиксированный prefix в agent rules | I | `{mb_root}/` с resolver | s09-legacy-purge | no | Kind I purge |

---

## Очередь шагов (BACK)

| step_id | title & files | needs_creative | tdd | next_phase | status |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-pack-layout-resolver.yaml](../yaml/steps/s01-pack-layout-resolver.yaml) — `loop/paths/pack_layout.py` + software handler | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-production-epic-policy.yaml](../yaml/steps/s02-production-epic-policy.yaml) — `loop/paths/forbidden_policy.py` | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-epic-core-activecontext-refactor.yaml](../yaml/steps/s03-epic-core-activecontext-refactor.yaml) — `harness/hooks/epic/core.py` + `loop/context_loop.py` | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-mb-load-pack-thread.yaml](../yaml/steps/s04-mb-load-pack-thread.yaml) — `loop/mb_load/` pack-aware | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-mb-finish-pack-thread.yaml](../yaml/steps/s05-mb-finish-pack-thread.yaml) — `loop/mb_finish/impl.py` pack-aware | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-epic-layout-pack-param.yaml](../yaml/steps/s06-epic-layout-pack-param.yaml) — `loop/paths/epic_paths.py` + T-HUB-047 param | no | yes | BACK IMPLEMENT | completed |
| **s07** | [s07-validate-active-context-shape.yaml](../yaml/steps/s07-validate-active-context-shape.yaml) — `loop/incidents/doctor.py` shape validator | no | yes | BACK IMPLEMENT | completed |
| **s08** | [s08-pytest-matrix-smoke.yaml](../yaml/steps/s08-pytest-matrix-smoke.yaml) — pytest matrix + video integration smoke | no | yes | BACK IMPLEMENT | completed |
| **s09** | [s09-legacy-path-purge.yaml](../yaml/steps/s09-legacy-path-purge.yaml) — delete hardcoded paths + Kind I instruction purge | no | no | BACK IMPLEMENT | completed |