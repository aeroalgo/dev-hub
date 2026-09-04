# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-048-workflow-pack-registry  
**План:** [plan.md](plan.md)  
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**  
**Дата:** 2026-09-04  
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml`.

> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `index.yaml`.** Этот файл в IMPLEMENT не грузить.
> **status SoT = `decompose-index.yaml` only.**

---

## Requirements coverage (plan → steps)

| Req ID | Plan FR text (verbatim) | sNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | `loop/workflow_pack_registry.yaml` schema `workflow-pack-registry/v1` with `default` + `packs{}` | s01 | |
| FR-002 | Pack row fields: `id`, `roles[]`, `command_prefixes[]`, `phase_registry` (path), `memory_bank` (relative root), `rules_root`, `artifact_layout` enum | s01 | |
| FR-003 | `loop/workflow/schemas.py` — pydantic `WorkflowPack`, `WorkflowPackRegistry`, `PackResolveResult` | s02 | |
| FR-004 | `loop/workflow/registry.py` — `load_registry()`, `get_pack(id)`, `resolve_workflow_pack(cwd)` (env `WORKFLOW_PACK` → registry → default) | s03 | |
| FR-005 | Optional `project.yaml` / `.dev-hub/project.yaml` field `workflow_pack` overrides env (document precedence: project > env > default) | s03 | resolve logic; s07 test |
| FR-006 | CLI `python3 harness/hooks/epic_resolve.py workflow resolve [--pack] [--cwd] [--json]` | s05 | |
| FR-007 | `harness/hooks/_lib.py` — extend `RuntimeConfig` or sibling `WorkflowConfig` with resolved pack (no dual frozenset of pack ids) | s06 | |
| FR-008 | `loop/context_loop.prepare_session` — emit `workflow_pack` + pack metadata in prepare dict | s06 | |
| FR-009 | Default pack `dev-hub-software` row pointing to current paths (phase_registry, memory-bank, .cursor/rules) | s01 | |
| FR-010 | Unit tests: load registry, invalid pack, default pack, project.yaml override, corrupt yaml | s07 | |
| US-001 | Как operator, я хочу `WORKFLOW_PACK` из registry, чтобы добавлять domain без правки loop.sh | s03, s05 | resolve + CLI |
| US-002 | Как platform, я хочу default `dev-hub-software`, чтобы текущие проекты работали без изменений | s01, s03, s07 | |
| US-003 | Как maintainer, я хочу pydantic-validated pack manifest, чтобы misconfig fail-closed at load | s02 | |
| US-004 | Как loop runner, я хочу pack id в prepare JSON, чтобы downstream hooks read one field | s06 | |
| US-005 | Как pack author, я хочу manifest schema documented, чтобы создать новый pack row | s01 | JSON Schema + README |
| AC+ 1 | `workflow_pack_registry.yaml` lists `dev-hub-software` with paths matching as-built | s01 | |
| AC+ 2 | `workflow resolve` CLI returns JSON ok:true for default; ok:false for unknown | s05 | |
| AC+ 3 | `prepare_session` JSON contains `workflow_pack` field | s06 | |
| AC+ 4 | `pytest loop/tests/test_workflow_pack_registry.py -q` green | s07 | |
| AC+ 5 | Zero regression: existing epic loop smoke with unset WORKFLOW_PACK | s07 | |
| AC− 1 | Hardcoded pack id frozenset in Python after epic | s06, s08 | rg audit |
| AC− 2 | Silent fallback unknown pack → dev-hub-software | s03, s04 | fail-closed |
| AC− 3 | Dual resolver (regex + pydantic) for pack selection | s02, s03 | pydantic only |
| AC− 4 | Pack-specific logic in loop.sh if/else branches | s08 | rg audit |
| AC− 5 | Breaking rename of `memory-bank/` for default pack | s01 | paths matching as-built |
| SC-001 | Unknown pack → exit 2 | s03, s04, s05 | |
| SC-002 | Default pack = current behavior | s01, s03, s07 | |
| SC-003 | prepare_session includes workflow_pack | s06, s07 | |
| SC-004 | No hardcoded pack frozenset in _lib | s06, s08 | |
| NFR: fail-closed | Unknown/corrupt pack → ValidationError / exit 2; no silent default | s02, s03, s04 | |
| NFR: zero regression | existing arm_phase / epic transition tests green | s07 | |
| cut_list | `project.yaml custom registry path` | — | Deferred: T-HUB-051 |
| cut_list | `MCP workflow resolve wrapper` | — | Deferred: T-HUB-051 |

---

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| Registry YAML + schema | plan §workflow_pack_registry.yaml draft, FR-001/002/009 | s01 |
| Pydantic models (fail-closed load) | plan FR-003, US-003, TM-001/003 | s02 |
| Resolver logic (env → project.yaml → default) | plan FR-004/005, US-001/002, PackResolve flow | s03 |
| Path validation (phase_registry / memory_bank exists) | plan Failure matrix TM-003/004, data flow | s04 |
| CLI subcommand workflow resolve | plan FR-006, US-001 Acceptance Scenario | s05 |
| _lib + prepare_session wire | plan FR-007/008, SC-003/004 | s06 |
| pytest matrix TM-001..006 | plan §QA consumes, FR-010, AC+4/5 | s07 |
| Purge implicit single-domain assumptions | plan §Replacement/sunset A+C, SC-004, AC−4 | s08 |

---

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Operator подключает любой pipeline без fork loop (US-001) | s01 (registry yaml), s03 (resolver), s05 (CLI), s08 (purge) |
| Default pack = zero migration (existing projects unchanged, US-002) | s01 (dev-hub-software row), s03 (default fallback), s07 (regression TM-006) |
| Fail-closed: unknown/corrupt pack → exit 2, no silent default (SC-001, AC−2) | s02 (pydantic validate), s03 (get_pack None), s04 (path guard), s05 (exit 2) |
| prepare_session JSON includes workflow_pack (SC-003, FR-008) | s06 (context_loop edit), s07 (TM-004) |
| No hardcoded pack frozenset in _lib / no if/else in loop.sh (SC-004, AC−1/4) | s06 (WorkflowConfig without frozenset), s08 (rg audit + instruction rewrites) |
| Pack manifest documented for authors (US-005) | s01 (JSON Schema + workflows/README.md) |
| Full TM-001..006 matrix green (AC+4) | s07 |
| Instruction surface (Kind I) updated — no stale single-domain prose | s08 |
| Out of scope: pack overlay merge product→hub | — Deferred: T-HUB-051 |
| Out of scope: IDEA PIPELINE domain chains | — Deferred: T-HUB-052 |
| Out of scope: command router mainrule.mdc prefix update | — Deferred: T-HUB-049 |

---

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| Implicit «single software domain» session-start prose | I | instruction rewrite → «configurable via Workflow Pack» | s08 | no | rg audit in s08 |
| Silent default unknown pack (no-op fallback behavior) | C | fail-closed exit 2 via `validate_pack_paths` | s04, s08 | yes | delete in-epic per plan §C |
| n/a — код greenfield (loop/workflow/ пакет новый) | — | — | — | — | greenfield |
| n/a — entrypoints greenfield (`epic_resolve workflow resolve` новый) | — | — | — | — | greenfield |

---

## Очередь шагов

| step_id | title & files | needs_creative | tdd | next_phase | status |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-registry-yaml-schema.yaml](../yaml/steps/s01-registry-yaml-schema.yaml) — workflow_pack_registry.yaml + JSON Schema + workflows/README.md | no | no | BACK IMPLEMENT | completed |
| **s02** | [s02-pydantic-schemas.yaml](../yaml/steps/s02-pydantic-schemas.yaml) — loop/workflow/schemas.py (WorkflowPack, WorkflowPackRegistry, PackResolveResult) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-registry-loader.yaml](../yaml/steps/s03-registry-loader.yaml) — loop/workflow/registry.py (load_registry, get_pack, resolve_workflow_pack) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-resolve-path-validation.yaml](../yaml/steps/s04-resolve-path-validation.yaml) — loop/workflow/resolve.py (validate_pack_paths, full_resolve) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-cli-workflow-resolve.yaml](../yaml/steps/s05-cli-workflow-resolve.yaml) — epic_resolve.py workflow resolve CLI | no | no | BACK IMPLEMENT | completed |
| **s06** | [s06-lib-prepare-session.yaml](../yaml/steps/s06-lib-prepare-session.yaml) — _lib.py WorkflowConfig + context_loop.prepare_session | no | yes | BACK IMPLEMENT | completed |
| **s07** | [s07-pytest-suite.yaml](../yaml/steps/s07-pytest-suite.yaml) — loop/tests/test_workflow_pack_registry.py (TM-001..006) | no | yes | BACK IMPLEMENT | completed |
| **s08** | [s08-purge-hardcoded-domain-assumptions.yaml](../yaml/steps/s08-purge-hardcoded-domain-assumptions.yaml) — rg audit + instruction rewrites (Kind A/I) | no | no | BACK IMPLEMENT | completed |