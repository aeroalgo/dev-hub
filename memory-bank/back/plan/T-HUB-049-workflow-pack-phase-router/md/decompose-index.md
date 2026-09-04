# [T-HUB-049 | workflow-pack-phase-router] DECOMPOSE INDEX

**Дата:** 2026-09-04
**Режим:** BACK DECOMPOSE
**Plan:** [plan.md](plan.md)
**Status:** pending → IMPLEMENT

---

## Requirements coverage

FR-идентификаторы соответствуют `plan.md §Functional Requirements` (строки 74–84).

| FR / US / SC | Requirement (из plan.md) | sNN |
|---|---|---|
| FR-001 / US-001 / SC-001 | `load_phase_registry(registry_path=None, *, pack_id=None, cwd=None)` — если pack_id set → resolve path via workflow registry; оба None → fail-closed ValueError | s01 |
| FR-002 | `get_command_prefixes(pack)` → `list[str]` из pack manifest, кэш per-pack | s02 |
| FR-003 / US-002 / SC-002 | `normalize_registry_phase(phase, pack)` — strip pack prefix из `pack.command_prefixes` перед lookup | s02 |
| FR-004 / US-001 / SC-001 | `gates_from_phase(phase, *, cwd)` — resolve active pack из cwd/env; load correct registry | s03 |
| FR-005 / US-003 / TM-004 | `arm_phase`, `get_verify_agent`, `get_dsh_preset` — thread pack context (optional cwd param) | s03 |
| FR-006 | `loop/workflow/command_router.py` — map `(pack, raw_command)` → `CommandRoute(normalized_phase, rules_mdc_rel)` | s04 |
| FR-007 / US-005 / TM-005 | `session_start_payload` — append pack id + command prefixes snippet в additionalContext | s05 |
| FR-008 / US-004 / SC-003 | Purge `epic_transition._ROLE_PREFIXES` static tuple; replace with pack-driven loader | s06 |
| FR-009 | `.cursor/rules/mainrule.mdc` §Workflow Pack doc pattern — **Deferred: appetite cut_list** (follow_up: T-HUB-052) | Deferred |
| FR-010 / SC-004 | pytest: software pack regression + mock alternate pack phase yaml (TM-001..005) | s07 |
| TM-001 | pack phase yaml missing → fail-closed ValueError | s01, s07 |
| TM-002 | unknown phase in pack registry → ValueError | s01, s07 |
| TM-003 | `SCRIPT IMPLEMENT` + video pack prefixes → normalize → `IMPLEMENT` | s02, s07 |
| TM-004 | arm_phase video pack dsh → dsh_preset из video registry | s03, s07 |
| TM-005 | EPIC_LOOP=1 → pack_id + prefix list in session_start_payload | s05, s07 |

**FR-009 deferred:** `generated mainrule stub` в appetite `cut_list` — hub-link 052 владеет генерацией stub; этот эпик только runtime routing.

---

## Stages coverage

| Этап (план «До DECOMPOSE») | sNN | Файл |
|---|---|---|
| s01 pack-aware load_phase_registry | s01 | s01-pack-aware-load-phase-registry.yaml |
| s02 dynamic normalize_registry_phase | s02 | s02-dynamic-normalize-registry-phase.yaml |
| s03 gates_from_phase + arm_phase thread pack | s03 | s03-gates-arm-phase-thread-pack.yaml |
| s04 command_router.py | s04 | s04-command-router.yaml |
| s05 session-start pack inject | s05 | s05-session-start-pack-inject.yaml |
| s06 purge _ROLE_PREFIXES + rg audit | s06 | s06-purge-role-prefixes-legacy.yaml |
| s07 pytest matrix + regression | s07 | s07-pytest-matrix-regression.yaml |

---

## Outcome map

| Outcome (plan AC+/SC) | sNN | Measurable verify |
|---|---|---|
| `gates_from_phase` читает pack phase_registry (SC-001) | s01, s03 | `bin/pytest loop/tests/test_workflow_pack_phase_router.py::test_gates_from_phase_video_pack -xq` |
| `normalize_registry_phase` pack-scoped prefixes (SC-002, TM-003) | s02 | `bin/pytest loop/tests/test_workflow_pack_phase_router.py::test_normalize_custom_prefix -xq` |
| `arm_phase` + `get_verify_agent` через pack registry (TM-004) | s03 | `bin/pytest loop/tests/test_workflow_pack_phase_router.py::test_arm_phase_dsh_video_pack -xq` |
| `command_router.route_command(pack, cmd)` → `CommandRoute(phase, rules_mdc_rel)` (FR-006) | s04 | `bin/pytest loop/tests/test_workflow_pack_phase_router.py::test_route_command_software -xq` |
| `session_start_payload` содержит pack_id + command_prefixes (TM-005) | s05 | `bin/pytest loop/tests/test_workflow_pack_phase_router.py::test_session_start_pack_inject -xq` |
| `_ROLE_PREFIXES` полностью удалён из codebase (SC-003) | s06 | `rg '_ROLE_PREFIXES' loop/ harness/ --include='*.py' \| grep -v test_ \| wc -l \| grep '^0$'` |
| Software default pack zero regression + TM-001..005 (SC-004, FR-010) | s07 | `bin/pytest loop/tests/test_workflow_pack_phase_router.py -q` exit 0 |
| AC−3: нет `if pack == video` веток в epic/core.py после эпика | s03 | `rg 'pack.*==.*video\|pack_id.*==.*video' harness/ loop/ --include='*.py'` → 0 |
| AC−4: нет дублирующих phase registry loaders разной семантики | s01, s06 | `rg 'load_phase_registry\|_PHASE_REGISTRY_CACHE' loop/ --include='*.py' \| wc -l` → только pack-aware API |
| FR-009 mainrule.mdc §Workflow Pack | Deferred → T-HUB-052 | n/a this epic |

---

## Replacement cleanup

| Symbol / Path | Тип | Owner shard | Action | Verify cp |
|---|---|---|---|---|
| `loop/epic_transition._ROLE_PREFIXES` frozenset | B (replace) | s02 drop usage → s06 delete | `deletes: [_ROLE_PREFIXES]` в s06 | `rg '_ROLE_PREFIXES' --include='*.py'` (non-test) → 0 |
| `loop/epic_transition._DEFAULT_REGISTRY_PATH` | B (replace) | s01 drop usage → s06 delete | `deletes: [_DEFAULT_REGISTRY_PATH]` в s06 | `rg '_DEFAULT_REGISTRY_PATH' --include='*.py'` → 0 |
| `registry_path` parameter в `get_verify_agent`, `get_dsh_preset`, `get_phase_config` (не в FR-001 `load_phase_registry`) | B (replace) | s03 migrate callers → s06 delete param | `deletes: [legacy registry_path param]` в s06 | `rg 'def get_verify_agent.*registry_path\|def get_dsh_preset.*registry_path\|def get_phase_config.*registry_path' loop/ --include='*.py'` → 0 |
| `gates_from_phase()` без cwd context (legacy bare call) | B (replace) | s03 | `delta: gates_from_phase(phase, *, cwd)` | `rg 'gates_from_phase(' harness/ loop/ --include='*.py' \| grep -v 'test_\|def gates_from_phase' \| grep -v 'cwd' \| wc -l \| grep '^0$'` |
| `arm_phase` / `get_phase_config(phase)` без pack_id | B (replace) | s03 | `delta: get_phase_config(phase, *, pack_id, cwd)` | pytest TM-004 |

Лестница: s01 (add pack-aware load) → s02 (drop _ROLE_PREFIXES callers, add pack prefixes) → s03 (wire gates/arm, migrate registry_path callers) → s04 (command_router) → s05 (session-start inject) → s06 (deletes purge: _ROLE_PREFIXES + _DEFAULT_REGISTRY_PATH + registry_path param) → s07 (regression suite).

## Очередь шагов

| step_id | title & files | next_phase | status |
| :--- | :--- | :--- | :--- |
| **s01** | pack-aware load_phase_registry(registry_path, *, pack_id) — path from pack manifest · [yaml](s01-pack-aware-load-phase-registry.yaml) | BACK IMPLEMENT | completed |
| **s02** | dynamic normalize_registry_phase uses pack.command_prefixes (drop _ROLE_PREFIXES) · [yaml](s02-dynamic-normalize-registry-phase.yaml) | BACK IMPLEMENT | completed |
| **s03** | gates_from_phase + arm_phase thread pack context via resolve_workflow_pack · [yaml](s03-gates-arm-phase-thread-pack.yaml) | BACK IMPLEMENT | completed |
| **s04** | loop/workflow/command_router.py — route_command(pack, cmd) → CommandRoute(phase, rules_mdc_rel) · [yaml](s04-command-router.yaml) | BACK IMPLEMENT | completed |
| **s05** | session-start injects pack command index into additionalContext payload · [yaml](s05-session-start-pack-inject.yaml) | BACK IMPLEMENT | completed |
| **s06** | purge _ROLE_PREFIXES hardcode + rg audit — replace with pack-scoped prefixes · [yaml](s06-purge-role-prefixes-legacy.yaml) | BACK IMPLEMENT | completed |
| **s07** | pytest matrix: TM-001..005 failure coverage + pack-router regression suite · [yaml](s07-pytest-matrix-regression.yaml) | BACK IMPLEMENT | pending |
