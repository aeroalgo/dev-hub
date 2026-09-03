# [T-HUB-050 | workflow-pack-memory-bank-paths] PLAN

**Дата:** 2026-09-02  
**Режим:** BACK PLAN  
**Уровень:** L3–L4  
**Статус:** active  
**Roadmap:** [roadmap-workflow-pack-framework-epics.md](roadmap-workflow-pack-framework-epics.md)  
**Queue:** [roadmap-workflow-pack-framework-epics.queue.yaml](roadmap-workflow-pack-framework-epics.queue.yaml)  
**Deps:** **hard** T-HUB-048 (pack manifest memory_bank root). **Soft:** T-HUB-045 (mb-load), T-HUB-040 (mb-finish), T-HUB-047 (epic layout v2 resolver).

**Skills:** writing-plans · architecture-patterns · python-testing-patterns · modern-python

→ [T-HUB-050-workflow-pack-memory-bank-paths/md/decompose-index.md](T-HUB-050-workflow-pack-memory-bank-paths/md/decompose-index.md) — **после DECOMPOSE**

---

## Контекст

- **req:** Pack manifest declares `memory_bank` root (e.g. `memory-bank` vs `memory-bank/video`), but all path resolution today assumes software layout (`memory-bank/back/plan/…`). mb-load, mb-finish, epic_resolve, activeContext validation, and epic path helpers must resolve artifacts **relative to pack root** without breaking default software pack.
- **gap (as-built):**
  - `read_active_context`, `extract_load_now` — hardcoded `memory-bank/activeContext.md`.
  - `mb_load` / `mb_finish` (T-HUB-040/045) — paths relative to fixed memory-bank tree.
  - `epic_paths.py` / reconcile — `plan/decompose-{id}/` under `back/plan/`.
  - Forbidden load policy (no full plan in IMPLEMENT) — not parameterized per pack artifact_layout.
  - T-HUB-047 epic layout v2 resolver — no pack dimension yet.
- **refs:** plan-T-HUB-048; plan-T-HUB-045; plan-T-HUB-047; `.cursor/rules/shared/epic-scoped-paths.mdc`.

**CREATIVE need:** нет.

---

## Technology axiom (replace-not-wrap)

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| MB root | `resolve_mb_root(cwd)` from pack | string concat `memory-bank/` in hooks |
| activeContext path | `{mb_root}/activeContext.md` | hardcoded path in epic/core |
| Forbidden policy | pack.artifact_layout → policy module | one-size software denylist only |
| Epic path kinds | `resolve_epic_path(kind, epic_id, pack)` | parallel glob helpers per domain |
| Hub vs product cwd | same guard as mb-finish | pack resolve on wrong cwd silent pass |

---

## Продуктовая spека (WHAT)

### Product probe

| # | Question | Answer | Impact |
|---|----------|--------|--------|
| 1 | Reframe | Non-software packs cannot store artifacts in harness | Unified mb root resolver |
| 2 | Wedge | resolve_mb_root + mb-load/mb-finish thread pack | layout v2 pack-aware in s05 |
| 3 | Pre-mortem | T-HUB-047 migrates paths; pack resolver drifts | Single `loop/paths/pack_layout.py` API |
| 4 | Adoption | Video epic under memory-bank/video/script/plan/ | artifact_layout enum |
| 5 | Leverage | mb_finish schemas, extract_load_now | extend not rewrite |
| 6 | Appetite | ~8–10 sNN, 6 days | |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как operator IMPLEMENT, я хочу mb-load session читал activeContext из pack root. | P0 | pack video → memory-bank/video/activeContext.md loaded |
| US-002 | Как platform, я хочу mb-finish писал Handoff в pack activeContext. | P0 | FINISH on video pack → correct path written |
| US-003 | Как planner, я хочу plan/decompose paths under pack role subdirs. | P0 | resolve_epic_path(plan) → pack-relative |
| US-004 | Как auditor, я хочу forbidden policy per artifact_layout. | P1 | software-epic-v1 vs production-epic-v1 matrix |
| US-005 | Как operator, я хочу software pack zero path change. | P0 | default pack paths identical to as-built |

#### Acceptance Scenarios — US-001

- **Given:** WORKFLOW_PACK=video-production, activeContext at `memory-bank/video/activeContext.md`
- **When:** `epic_resolve.py mb-load session --cwd $PROJECT_ROOT`
- **Then:** JSON ok:true, meta reflects video pack, files from video load_now

### Functional Requirements

- **FR-001:** `loop/paths/pack_layout.py` — `resolve_mb_root(cwd)`, `resolve_active_context(cwd)`, `resolve_role_root(pack, role)`.
- **FR-002:** `artifact_layout` enum handlers: `software-epic-v1` (current), `production-epic-v1` (flat role dirs under pack root).
- **FR-003:** Refactor `harness/hooks/epic/core.py` — activeContext/read/handoff use pack_layout (no hardcoded memory-bank).
- **FR-004:** `loop/mb_load/load_session` — thread pack; forbidden policy from layout handler.
- **FR-005:** `loop/mb_finish/*` — write paths via pack_layout.
- **FR-006:** Integrate T-HUB-047 `resolve_epic_path` — pack parameter (soft compat if 047 not merged: shim reads software paths only).
- **FR-007:** `validate_active_context_shape` — pack-aware load_now path validation.
- **FR-008:** CLI diagnostics include `mb_root` + `workflow_pack` in mb-load/mb-finish JSON.
- **FR-009:** pytest matrix: software default + video fixture tree + forbidden policy cases.
- **FR-010:** Purge rg targets: literal `memory-bank/activeContext` in epic hooks (allow docs/tests with comment exemption list).

### Success Criteria

| ID | Результат | Проверка |
|----|-----------|----------|
| SC-001 | mb-load pack-aware | pytest |
| SC-002 | mb-finish pack-aware | pytest |
| SC-003 | Default pack path parity | diff paths vs as-built |
| SC-004 | rg purge memory-bank hardcode in hooks | audit |

### Assumptions

- Single activeContext per project (under pack mb root); multi-pack concurrent epics out of scope v1.
- T-HUB-047 layout v2 may land before or after; resolver API designed with optional layout version field.

### [НУЖНО УТОЧНИТЬ]

- n/a CRITICAL.

---

## AC+

1. `resolve_mb_root` returns pack manifest path; default = `memory-bank`.
2. mb-load/mb-finish succeed on video fixture tree.
3. Software pack byte-equivalent paths for existing epics.
4. Forbidden load policy tested for both layout enums.
5. `pytest loop/tests/test_workflow_pack_mb_paths.py loop/tests/test_mb_load.py -q` green.

### AC−

1. Literal `memory-bank/` concat in epic/core after epic (exempt tests/docs).
2. Silent fallback to software root when pack mb missing.
3. Dual path resolver (legacy glob + pack_layout) without purge step.
4. Breaking move of existing software epics without migrate tool.

---

## Техника / архитектура (HOW)

### production-epic-v1 layout (draft)

```text
memory-bank/video/
  activeContext.md
  script/plan/…
  script/plan/decompose-<epic_id>/…
  visual/…
  post/…
```

### Files

| Path | Action |
|------|--------|
| `loop/paths/pack_layout.py` | new |
| `loop/paths/artifact_layouts/*.py` | layout handlers |
| `harness/hooks/epic/core.py` | refactor paths |
| `loop/mb_load/*.py` | pack thread |
| `loop/mb_finish/*.py` | pack thread |
| `loop/paths/epic_layout.py` | pack param (047 integration) |
| `loop/tests/test_workflow_pack_mb_paths.py` | new |

---

## Eng review spine

### Data flow

```text
[mb-load session] -> [resolve_workflow_pack]
                  -> [resolve_mb_root]
                  -> [read activeContext at mb_root]
                  -> [extract_load_now with pack-relative paths]
                  -> [forbidden policy via artifact_layout handler]
                  fail-closed if activeContext missing
```

### Failure matrix

| Component | Failure | Detection | Response | Test ID |
|-----------|---------|-----------|----------|---------|
| mb_root missing | no dir | is_dir false | ok:false mb_root_missing | TM-001 |
| activeContext missing | no file | read fail | shape invalid diagnostic | TM-002 |
| load_now path escape | outside mb_root | path guard | forbidden_skipped | TM-003 |
| layout handler unknown | bad enum | pydantic | invalid_artifact_layout | TM-004 |
| software regression | wrong path | parity test | block merge | TM-005 |
| finish write wrong file | handoff drift | fingerprint test | block merge | TM-006 |

---

## Replacement / sunset

### A. Code

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| Hardcoded memory-bank paths in epic/core | pack_layout | delete in-epic |
| Ad-hoc path joins in mb_load | resolve_mb_root | delete in-epic |

### C. Fallbacks

| Silent default mb root | fail-closed | delete in-epic |

<a id="qa-consumes"></a>
## QA consumes

| ID | P | Scenario | Command | Expected | Maps |
|----|---|----------|---------|----------|------|
| TM-001 | P0 | Video mb-load | pytest video_load | PASS | FR-004 |
| TM-002 | P0 | Software parity | pytest software_parity | PASS | US-005 |
| TM-003 | P0 | mb-finish pack | pytest video_finish | PASS | FR-005 |
| TM-004 | P1 | Forbidden policy | pytest forbidden_layout | PASS | FR-004 |
| TM-005 | P0 | Path escape guard | pytest path_escape | PASS | FR-004 |
| TM-006 | P0 | rg hardcode purge | rg audit | PASS | FR-010 |

---

## Review readiness

| Gate | Status | Evidence |
|------|--------|----------|
| Product probe | done | §Product probe |
| Eng spine | done | filled |
| §0.11 | n/a | internal paths only |
| CREATIVE | n/a | — |
| qa_consumes | done | 6 TM |
| Plan review batch | done | below |

---

## Plan review batch log

| Phase | Auto-resolved | Deferred |
|-------|---------------|----------|
| Product | production-epic-v1 role subdirs | 047 integration shim if 047 delayed |
| Eng | Single pack_layout module | — |

---

## До DECOMPOSE

1. s01 — pack_layout.py + software handler  
2. s02 — production-epic-v1 handler  
3. s03 — epic/core activeContext refactor  
4. s04 — mb_load pack thread  
5. s05 — mb_finish pack thread  
6. s06 — epic_layout pack param (047)  
7. s07 — validate_active_context_shape  
8. s08 — pytest matrix + rg purge  
9. s09 — legacy path purge step  

---

## Appetite

| timebox_days | 6 |
| cut_list | `['047 full integration if 047 not merged', 'mb-scaffold pack paths']` |

---

## Следующий режим

→ BACK DECOMPOSE T-HUB-050
