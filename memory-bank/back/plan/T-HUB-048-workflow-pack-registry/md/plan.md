# [T-HUB-048 | workflow-pack-registry] PLAN

**Дата:** 2026-09-02  
**Режим:** BACK PLAN  
**Уровень:** L3–L4  
**Статус:** active  
**Roadmap:** [roadmap-workflow-pack-framework-epics.md](roadmap-workflow-pack-framework-epics.md)  
**Queue:** [roadmap-workflow-pack-framework-epics.queue.yaml](roadmap-workflow-pack-framework-epics.queue.yaml)  
**Deps:** **hard** T-HUB-029 (phase registry-driven transition). **Soft:** T-HUB-042 (registry loader pattern parity), T-HUB-041 (canonical harness paths).

**Skills:** writing-plans · architecture-patterns · python-testing-patterns · modern-python

→ [T-HUB-048-workflow-pack-registry/md/decompose-index.md](T-HUB-048-workflow-pack-registry/md/decompose-index.md) — **после DECOMPOSE**

---

## Контекст

- **req:** Harness orchestration (loop + epic hooks + stop-gate) уже domain-agnostic, но роли/фазы/paths захардкожены под software dev (BACK/FRONT/INTEG). Operator хочет подключать **любой производственный pipeline** (video, content, legal review) без fork loop. Нужен plug-in **Workflow Pack Registry** — зеркало `runtime_registry.yaml` (T-HUB-042), но для **домена**, не runtime shell.
- **gap (as-built):**
  - `mainrule.mdc` — только три префикса BACK/FRONT/INTEG.
  - `loop/schemas/phase_registry.yaml` — единственный канон; путь захардкожен в `load_phase_registry()`.
  - `epic_transition._ROLE_PREFIXES` — frozenset `BACK | FRONT | INTEG`.
  - Нет env/config для выбора pack; нет fail-closed на unknown pack.
  - IDEA PIPELINE знает только dev-цепочки (отдельный эпик T-HUB-052).
- **refs:** чат 2026-09-02 (Workflow Pack Gate); plan-T-HUB-042 (RuntimeAdapter pattern); plan-T-HUB-029 (phase_registry.yaml); roadmap-harness-universal-runtime §2 (orchestration не меняется).

**CREATIVE need:** нет.

---

## Technology axiom (replace-not-wrap)

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Pack selection | `workflow_pack_registry.yaml` + pydantic loader | prose «если video — другие rules» |
| Active pack | `WORKFLOW_PACK` env + optional `project.yaml` field | hardcoded default без registry row |
| Unknown pack | `invalid_workflow_pack` diagnostic → exit 2 | silent fallback to dev-hub-software |
| Default pack row | `dev-hub-software` mirrors current behavior | implicit «no pack = broken» |
| Pack manifest path | resolved relative to hub root or pack dir | ad-hoc glob per domain |

DECOMPOSE → purge-step: удалить implicit assumption «единственный software pack» из `_lib.py` / session-start без registry lookup.

---

## Продуктовая spека (WHAT)

### Product probe (Phase 0 skipped — taxonomy clear)

| # | Question | Answer / Probe | Decision / Impact |
|---|----------|----------------|---------------------------|
| 1 | **Reframe:** Какую проблему решаем? | Нельзя переиспользовать harness для non-software production без копирования loop/rules | Фокус = registry + resolve API, не новый orchestrator |
| 2 | **Narrowest wedge:** Минимальный slice? | Registry yaml + loader + default pack row + CLI `resolve` | Command router / mb paths → T-HUB-049/050 |
| 3 | **Pre-mortem:** Провал через месяц? | Pack registry drift vs phase_registry; dual path software+pack | Default pack = exact current paths; zero regression AC |
| 4 | **Distribution:** Кто вызывает? | loop runner, session-start, epic_resolve CLI, doctor (052) | Machine API first |
| 5 | **Technical leverage:** Что переиспользовать? | `loop/runtime/registry.py` pattern, pydantic schemas from mb_finish | `loop/workflow/` package |
| 6 | **Appetite:** L3–L4, ~5–7 sNN, 4–5 days | Foundation epic; blocks 049–052 | |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как operator, я хочу `WORKFLOW_PACK` из registry, чтобы добавлять domain без правки loop.sh. | P0 | `EPIC_WORKFLOW_PACK=foo` → exit 2 + JSON `invalid_workflow_pack` |
| US-002 | Как platform, я хочу default `dev-hub-software`, чтобы текущие проекты работали без изменений. | P0 | unset env → resolve returns software pack; existing pytest green |
| US-003 | Как maintainer, я хочу pydantic-validated pack manifest, чтобы misconfig fail-closed at load. | P0 | corrupt yaml → ValidationError → diagnostic code |
| US-004 | Как loop runner, я хочу pack id в prepare JSON, чтобы downstream hooks read one field. | P1 | prepare_session output includes `workflow_pack` key |
| US-005 | Как pack author, я хочу manifest schema documented, чтобы создать новый pack row. | P1 | `workflow-pack-manifest/v1` JSON schema + template in workflows/ |

#### Acceptance Scenarios — US-001

- **Given:** `workflow_pack_registry.yaml` without pack `foo`
- **When:** `python3 -m loop.workflow resolve --pack foo --cwd $PROJECT_ROOT`
- **Then:** exit 2, stdout JSON `{ok:false, diagnostic_codes:["invalid_workflow_pack"]}`

#### Acceptance Scenarios — US-002

- **Given:** fresh dev-hub checkout, `WORKFLOW_PACK` unset
- **When:** `python3 -m loop.workflow resolve --cwd $PROJECT_ROOT`
- **Then:** exit 0, `{ok:true, pack_id:"dev-hub-software", phase_registry:"loop/schemas/phase_registry.yaml", ...}`

### Functional Requirements

- **FR-001:** `loop/workflow_pack_registry.yaml` schema `workflow-pack-registry/v1` with `default` + `packs{}`.
- **FR-002:** Pack row fields: `id`, `roles[]`, `command_prefixes[]`, `phase_registry` (path), `memory_bank` (relative root), `rules_root`, `artifact_layout` enum.
- **FR-003:** `loop/workflow/schemas.py` — pydantic `WorkflowPack`, `WorkflowPackRegistry`, `PackResolveResult`.
- **FR-004:** `loop/workflow/registry.py` — `load_registry()`, `get_pack(id)`, `resolve_workflow_pack(cwd)` (env `WORKFLOW_PACK` → registry → default).
- **FR-005:** Optional `project.yaml` / `.dev-hub/project.yaml` field `workflow_pack` overrides env (document precedence: project > env > default).
- **FR-006:** CLI `python3 harness/hooks/epic_resolve.py workflow resolve [--pack] [--cwd] [--json]`.
- **FR-007:** `harness/hooks/_lib.py` — extend `RuntimeConfig` or sibling `WorkflowConfig` with resolved pack (no dual frozenset of pack ids).
- **FR-008:** `loop/context_loop.prepare_session` — emit `workflow_pack` + pack metadata in prepare dict.
- **FR-009:** Default pack `dev-hub-software` row pointing to current paths (phase_registry, memory-bank, .cursor/rules).
- **FR-010:** Unit tests: load registry, invalid pack, default pack, project.yaml override, corrupt yaml.

### Success Criteria

| ID | Результат | Проверка | Type |
|----|-----------|----------|------|
| SC-001 | Unknown pack → exit 2 | pytest TM-001 | outcome |
| SC-002 | Default pack = current behavior | pytest + smoke arm_phase | outcome |
| SC-003 | prepare_session includes workflow_pack | pytest context_loop | outcome |
| SC-004 | No hardcoded pack frozenset in _lib | rg audit | outcome |

### Assumptions

- Hub ships default registry; product repos may extend via `workflows/<pack-id>/` overlay (merge strategy → T-HUB-051).
- Pack registry lives in hub `loop/` (like runtime_registry), not per-product, unless product.yaml points to custom registry path (P2 defer).
- `EPIC_WORKFLOW_PACK` alias accepted alongside `WORKFLOW_PACK` for loop parity (document one canonical).

### Clarifications

- Session: чат 2026-09-02; taxonomy clear — orthogonal to RuntimeAdapter.
- Pack overlay merge (product extends hub registry) — defer explicit FR to T-HUB-051 reference pack.

### [НУЖНО УТОЧНИТЬ]

- n/a CRITICAL.

---

## AC+

1. `workflow_pack_registry.yaml` lists `dev-hub-software` with paths matching as-built.
2. `workflow resolve` CLI returns JSON ok:true for default; ok:false for unknown.
3. `prepare_session` JSON contains `workflow_pack` field.
4. `pytest loop/tests/test_workflow_pack_registry.py -q` green.
5. Zero regression: existing epic loop smoke with unset WORKFLOW_PACK.

### AC−

1. Hardcoded pack id frozenset in Python after epic.
2. Silent fallback unknown pack → dev-hub-software.
3. Dual resolver (regex + pydantic) for pack selection.
4. Pack-specific logic in loop.sh if/else branches.
5. Breaking rename of `memory-bank/` for default pack.

---

## Техника / архитектура (HOW)

### workflow_pack_registry.yaml (draft)

```yaml
schema: workflow-pack-registry/v1
default: dev-hub-software
packs:
  dev-hub-software:
    id: dev-hub-software
    roles: [back, front, integration]
    command_prefixes: [BACK, FRONT, INTEG]
    phase_registry: loop/schemas/phase_registry.yaml
    memory_bank: memory-bank
    rules_root: .cursor/rules
    artifact_layout: software-epic-v1
    description: Default software delivery (BACK/FRONT/INTEG)
```

### PackResolve flow

```text
[env WORKFLOW_PACK | project.yaml]
    -> [load_registry(hub_root)]
    -> [get_pack(id) | default]
    -> [validate paths exist relative to PROJECT_ROOT]
    -> [PackResolveResult JSON]
```

### Files

| Path | Action |
|------|--------|
| `loop/workflow_pack_registry.yaml` | new |
| `loop/workflow/__init__.py` | new package |
| `loop/workflow/schemas.py` | new pydantic |
| `loop/workflow/registry.py` | new loader |
| `loop/workflow/resolve.py` | new resolve + path validation |
| `harness/hooks/epic_resolve.py` | add `workflow resolve` subcommand |
| `harness/hooks/_lib.py` | WorkflowConfig integration |
| `loop/context_loop.py` | prepare_session field |
| `loop/tests/test_workflow_pack_registry.py` | new |
| `workflows/README.md` | pack authoring pointer |

---

## Eng review spine

### Data flow (ASCII)

```text
[Operator] -> [WORKFLOW_PACK env / project.yaml]
          -> [loop.workflow.registry.load_registry]
          -> [resolve_workflow_pack(cwd)] sync
          -> [validate phase_registry path exists]
          -> [PackResolveResult -> prepare_session / session-start hook]
          fail-closed on unknown/missing paths
```

### Failure matrix

| Component / link | Failure | Detection | User/system response | Test ID |
|------------------|---------|-----------|----------------------|---------|
| registry yaml | malformed | pydantic ValidationError | invalid_workflow_pack_registry | TM-001 |
| unknown pack id | not in registry | get_pack None | exit 2 JSON diagnostic | TM-002 |
| phase_registry path | missing file | path.is_file() false | exit 2 pack_path_missing | TM-003 |
| memory_bank root | missing dir | path.is_dir() false | exit 2 pack_path_missing | TM-004 |
| project.yaml override | invalid pack id | resolve fail | exit 2 before loop start | TM-005 |
| default pack regression | wrong paths | smoke arm_phase | block merge | TM-006 |

### Eng spine self-check

| Dimension | Score 1–5 | Gap / action |
|-----------|-----------|--------------|
| Data flow complete | 5 | — |
| Failure coverage | 5 | TM-001..006 |
| Testability | 5 | isolated registry fixtures |

---

## Replacement / sunset

### A. Code / modules

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| Implicit «single software domain» in session-start prose | `resolve_workflow_pack()` | delete in-epic |
| n/a greenfield paths | — | — |

### B. Entrypoints / deploy

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| n/a | `epic_resolve workflow resolve` | greenfield |

### C. Fallbacks / soft-fail

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| Any silent default when WORKFLOW_PACK invalid | fail-closed exit 2 | delete in-epic |

<a id="qa-consumes"></a>
## QA consumes (test plan)

### Scope under test

- Epic surfaces: registry yaml, pydantic loader, CLI resolve, prepare_session field, default pack regression.
- Out of scope: command router (049), mb-load paths (050), video pack (051).

### Test matrix

| ID | Priority | Scenario | Command / fixture | Expected | Maps FR/AC |
|----|----------|----------|-------------------|----------|------------|
| TM-001 | P0 | Unknown pack fail-closed | `pytest -k unknown_pack` | PASS | AC+1, FR-004 |
| TM-002 | P0 | Default pack paths | `pytest -k default_pack` | PASS | AC+2, FR-009 |
| TM-003 | P0 | Corrupt registry yaml | `pytest -k corrupt_registry` | PASS | FR-003 |
| TM-004 | P0 | prepare_session field | `pytest -k prepare_workflow_pack` | PASS | FR-008 |
| TM-005 | P1 | project.yaml override | `pytest -k project_override` | PASS | FR-005 |
| TM-006 | P0 | Zero regression smoke | existing epic transition tests | PASS | AC+5 |

### Regression notes

- Run after T-HUB-042 merge to ensure runtime + pack resolve coexist in prepare JSON.

---

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| CLARIFY / Product probe | L3: one of done | done | §Product probe 6/6 |
| Eng review spine | L2+ | done | §Eng review spine |
| §0.11 counterparts (draft) | if external refs | n/a | no new external APIs |
| CREATIVE | if flagged | n/a | CREATIVE need: нет |
| qa_consumes draft | L2+ | done | §QA consumes 6 TM |
| Plan review batch | L2+ | done | §Plan review batch log |

**FINISH PLAN allowed:** no pending Required rows.

---

## Plan review batch log

| Phase | Auto-resolved | Deferred (owner/next) | Taste / CRITICAL surfaced |
|-------|---------------|-------------------------|---------------------------|
| Product | Orthogonal pack vs runtime axes; default pack = zero migration | Pack overlay merge → T-HUB-051 | — |
| Eng | Mirror runtime/registry.py structure; single resolve API | project.yaml precedence documented in FR-005 | — |

---

## До DECOMPOSE (черновик нарезки)

1. s01 — `workflow_pack_registry.yaml` + schema doc  
2. s02 — pydantic schemas `workflow/schemas.py`  
3. s03 — `registry.py` loader + cache  
4. s04 — `resolve.py` + path validation  
5. s05 — CLI `workflow resolve` in epic_resolve  
6. s06 — `_lib` WorkflowConfig + context_loop prepare field  
7. s07 — pytest matrix + default pack regression  
8. s08 — purge implicit single-domain assumptions (rg + doc)  

---

## Appetite

| Поле | Значение |
|------|----------|
| `timebox_days` | 5 |
| `cut_list` | `['project.yaml custom registry path', 'MCP workflow resolve wrapper']` |

---

## Следующий режим

→ BACK DECOMPOSE T-HUB-048 (after roadmap merge)
