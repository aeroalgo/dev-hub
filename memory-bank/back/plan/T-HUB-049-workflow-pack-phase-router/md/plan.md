# [T-HUB-049 | workflow-pack-phase-router] PLAN

**Дата:** 2026-09-02  
**Режим:** BACK PLAN  
**Уровень:** L3–L4  
**Статус:** active  
**Roadmap:** [roadmap-workflow-pack-framework-epics.md](roadmap-workflow-pack-framework-epics.md)  
**Queue:** [roadmap-workflow-pack-framework-epics.queue.yaml](roadmap-workflow-pack-framework-epics.queue.yaml)  
**Deps:** **hard** T-HUB-048 (pack registry + resolve). **Soft:** T-HUB-039 (verify agents runtime), T-HUB-008 (DSH preset mapping).

**Skills:** writing-plans · architecture-patterns · python-testing-patterns · modern-python

→ [T-HUB-049-workflow-pack-phase-router/md/decompose-index.md](T-HUB-049-workflow-pack-phase-router/md/decompose-index.md) — **после DECOMPOSE**

---

## Контекст

- **req:** После T-HUB-048 pack manifest указывает `phase_registry` path и `command_prefixes`, но harness всё ещё использует hardcoded `_ROLE_PREFIXES` и default `phase_registry.yaml`. Нужен **pack-scoped phase router**: `load_phase_registry(pack)`, dynamic prefix normalization, gates_from_phase и arm_phase читают active pack.
- **gap (as-built):**
  - `epic_transition._ROLE_PREFIXES = ("BACK ", "FRONT ", "INTEG ", …)` — static.
  - `load_phase_registry(registry_path=None)` defaults to `loop/schemas/phase_registry.yaml` only.
  - `gates_from_phase()` in epic/core.py calls `load_phase_registry()` without pack context.
  - `mainrule.mdc` — static table BACK/FRONT/INTEG; no pack indirection.
  - DSH `dsh_preset` per phase lives in phase_registry — pack switch must load alternate yaml.
- **refs:** plan-T-HUB-048; plan-T-HUB-029 (phase registry schema); `loop/epic_transition.py`; `harness/hooks/epic/core.py:gates_from_phase`.

**CREATIVE need:** нет (spike only if Cursor cannot @-ref dynamic rules path — defer to IMPLEMENT s01).

---

## Technology axiom (replace-not-wrap)

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Phase registry path | from `resolve_workflow_pack().phase_registry` | hardcoded `loop/schemas/phase_registry.yaml` in hooks |
| Role prefix normalization | from pack `command_prefixes[]` | `_ROLE_PREFIXES` frozenset |
| Command → rules routing | pack manifest `rules_root` + role subdir map | prose «read video rules» |
| Unknown phase in pack registry | fail-closed ValueError | fallback to software phases |

---

## Продуктовая spека (WHAT)

### Product probe (Phase 0 skipped — taxonomy clear)

| # | Question | Answer | Decision / Impact |
|---|----------|--------|-------------------|
| 1 | Reframe | Software phases forced on non-software packs | Dynamic registry path from pack |
| 2 | Wedge | pack-aware load_phase_registry + prefix normalize | mainrule harness router in s04 |
| 3 | Pre-mortem | Cursor rules @-refs break for new prefixes | Document pack rules install (046/052); session-start inject pack rules index |
| 4 | Adoption | Parent types `SCRIPT PLAN` instead of BACK PLAN | normalize_registry_phase uses pack prefixes |
| 5 | Leverage | Existing phase_registry schema unchanged | Only path + prefix list parameterized |
| 6 | Appetite | ~6–8 sNN, 5 days | |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как loop, я хочу gates_from_phase читать pack phase_registry, чтобы video EDIT имел implement gate. | P0 | mock pack registry → gates differ from software IMPLEMENT |
| US-002 | Как operator, я хочу `SCRIPT IMPLEMENT` нормализовался в phase IMPLEMENT для pack verify agent lookup. | P0 | normalize with pack prefixes → IMPLEMENT |
| US-003 | Как platform, я хочу arm_phase использовать pack verify_agent names. | P0 | arm_phase video pack → verify-edit agent id |
| US-004 | Как maintainer, я хочу purge `_ROLE_PREFIXES` hardcode. | P0 | rg `_ROLE_PREFIXES` → only pack loader |
| US-005 | Как session-start hook, я хочу inject pack command index в additionalContext. | P1 | EPIC_LOOP=1 → prefix list in payload |

#### Acceptance Scenarios — US-001

- **Given:** pack `video-production` with phase `EDIT` having `need_verify: true`
- **When:** `gates_from_phase("EDIT", pack=video_pack)`
- **Then:** `{mode: implement, need_verify: true, need_reviewer: false}`

### Functional Requirements

- **FR-001:** `load_phase_registry(registry_path, *, pack_id=None)` — if pack_id set, resolve path via workflow registry.
- **FR-002:** `get_command_prefixes(pack)` → list from pack manifest; cached per pack.
- **FR-003:** Refactor `normalize_registry_phase(phase, pack)` — strip any pack prefix before lookup.
- **FR-004:** `gates_from_phase(phase, *, cwd)` — resolve active pack from cwd/env; load correct registry.
- **FR-005:** `arm_phase`, `get_verify_agent`, `get_dsh_preset` — thread pack context (optional cwd param).
- **FR-006:** `loop/workflow/command_router.py` — map `(pack, prefix, mode)` → rules mdc relative path.
- **FR-007:** Harness `session_start_payload` — append pack id + command table snippet.
- **FR-008:** Purge `epic_transition._ROLE_PREFIXES` static tuple; replace with pack-driven loader.
- **FR-009:** `.cursor/rules/mainrule.mdc` — add §Workflow Pack: resolve pack before role index (document pattern; optional thin generated stub via hub-link 052).
- **FR-010:** pytest: software pack regression + mock alternate pack phase yaml.

### Success Criteria

| ID | Результат | Проверка |
|----|-----------|----------|
| SC-001 | gates_from_phase pack-aware | pytest |
| SC-002 | normalize dynamic prefixes | pytest |
| SC-003 | No `_ROLE_PREFIXES` hardcode | rg audit |
| SC-004 | Software pack unchanged behavior | test_epic_transition regression |

### Assumptions

- Phase registry schema `phase-registry/v1` unchanged; packs supply compatible yaml.
- Cursor rules for new packs ship as optional tree (T-HUB-051); this epic wires runtime routing only.

### Clarifications

- n/a

### [НУЖНО УТОЧНИТЬ]

- n/a CRITICAL.

---

## AC+

1. Active pack phase_registry drives gates_from_phase.
2. Dynamic command prefix normalization works for ≥3 prefixes from pack manifest.
3. `_ROLE_PREFIXES` removed from epic_transition.
4. Software default pack zero regression on arm_phase smoke.
5. `pytest loop/tests/test_workflow_pack_phase_router.py -q` green.

### AC−

1. Hardcoded BACK/FRONT/INTEG-only normalize after epic.
2. Fallback to software phase_registry when pack yaml missing (must fail-closed).
3. if pack == video branches in epic/core.py.
4. Duplicate phase registry loaders with different semantics.

---

## Техника / архитектура (HOW)

### Command router

```python
def resolve_command(pack: WorkflowPack, raw_command: str) -> CommandRoute:
    """SCRIPT PLAN -> rules_root/video/script/workflow-plan.mdc"""
```

### Data flow

```text
[User: SCRIPT IMPLEMENT]
    -> [resolve_workflow_pack(cwd)]
    -> [normalize_registry_phase("SCRIPT IMPLEMENT", pack)]
    -> [get_phase_config("IMPLEMENT", pack.phase_registry_path)]
    -> [gates_from_phase -> stop-gate / spawn-hard]
```

### Files

| Path | Action |
|------|--------|
| `loop/epic_transition.py` | pack-aware registry + purge _ROLE_PREFIXES |
| `harness/hooks/epic/core.py` | gates_from_phase cwd/pack thread |
| `loop/workflow/command_router.py` | new |
| `harness/hooks/session-start.py` | pack command index inject |
| `loop/tests/test_workflow_pack_phase_router.py` | new |

---

## Eng review spine

### Failure matrix

| Component | Failure | Detection | Response | Test ID |
|-----------|---------|-----------|----------|---------|
| pack phase yaml | missing | resolve path | fail-closed start | TM-001 |
| unknown phase in pack | bad phase id | get_phase_config | ValueError | TM-002 |
| prefix strip | ambiguous double prefix | unit test | deterministic longest match | TM-003 |
| verify_agent missing file | arm_phase | preflight | diagnostic verify_agent_missing | TM-004 |
| software regression | gate drift | test_epic_transition | block merge | TM-005 |

### Eng spine self-check

| Dimension | Score | Gap |
|-----------|-------|-----|
| Data flow complete | 5 | — |
| Failure coverage | 5 | TM-001..005 |
| Testability | 5 | mock pack fixtures |

---

## Replacement / sunset

### A. Code

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| `_ROLE_PREFIXES` tuple | pack.command_prefixes | delete in-epic |
| `load_phase_registry()` default-only | resolve pack path first | delete in-epic |

### B/C

| n/a greenfield | — | — |

<a id="qa-consumes"></a>
## QA consumes

| ID | Priority | Scenario | Command | Expected | Maps |
|----|----------|----------|---------|----------|------|
| TM-001 | P0 | Pack phase gates | pytest pack_gates | PASS | FR-004 |
| TM-002 | P0 | Prefix normalize | pytest normalize | PASS | FR-003 |
| TM-003 | P0 | Purge _ROLE_PREFIXES | rg + pytest | PASS | FR-008 |
| TM-004 | P0 | Software regression | test_epic_transition | PASS | SC-004 |
| TM-005 | P1 | session-start inject | pytest session_start | PASS | FR-007 |

---

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| Product probe | L3 | done | §Product probe |
| Eng spine | L2+ | done | filled |
| §0.11 | external | n/a | — |
| CREATIVE | — | n/a | — |
| qa_consumes | L2+ | done | 5 TM |
| Plan review batch | L2+ | done | below |

---

## Plan review batch log

| Phase | Auto-resolved | Deferred | CRITICAL |
|-------|---------------|----------|----------|
| Product | Same phase schema across packs | Cursor rules install → 051/052 | — |
| Eng | Thread cwd through gates_from_phase | mainrule doc-only in 049; generated stub 052 | — |

---

## До DECOMPOSE (черновик)

1. s01 — pack-aware load_phase_registry  
2. s02 — dynamic normalize_registry_phase  
3. s03 — gates_from_phase + arm_phase thread pack  
4. s04 — command_router.py  
5. s05 — session-start pack inject  
6. s06 — purge _ROLE_PREFIXES + rg audit  
7. s07 — pytest matrix + regression  

---

## Appetite

| timebox_days | 5 |
| cut_list | `['generated mainrule stub', 'MCP command resolve']` |

---

## Следующий режим

→ BACK DECOMPOSE T-HUB-049
