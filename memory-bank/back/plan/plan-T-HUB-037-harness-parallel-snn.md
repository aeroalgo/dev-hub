# [T-HUB-037 | harness-parallel-snn] PLAN

**Дата:** 2026-08-31  
**Режим:** BACK PLAN  
**Уровень:** L4  
**Статус:** active  
**Roadmap:** [roadmap-harness-maturity-borrowings-epics.md](roadmap-harness-maturity-borrowings-epics.md)  
**Queue:** [roadmap-harness-maturity-borrowings-epics.queue.yaml](roadmap-harness-maturity-borrowings-epics.queue.yaml)  
**Deps:** **hard** T-HUB-029 (unified arm_phase + cursor sync).

**Skills:** writing-plans · architecture-patterns · python-testing-patterns · diagnosing-bugs

→ [decompose-T-HUB-037-harness-parallel-snn/index.md](decompose-T-HUB-037-harness-parallel-snn/index.md) — **после DECOMPOSE**

---

## Контекст

- **req:** Bernstein/GSD **wave parallelism**: independent sNN steps (no deps in decompose index) execute in parallel git worktrees with separate agent sessions; parent merges results via index status only.
- **gap:** Strictly sequential loop; decompose may mark parallel hints but runner ignores.
- **refs:** GSD dependency waves; Omnigent/Bernstein worktree orchestrators; decompose index `parallel:` markers if any.

**CREATIVE need:** optional — merge conflict policy if two sNN touch same files (default: forbid parallel if file overlap detected at plan time).

---

## Цель

Opt-in **`EPIC_PARALLEL_SNN=1`**: loop identifies ready wave from decompose index → spawns N bounded worktree sessions → each completes one sNN → parent validates all → advances cursor when wave complete.

---

## Продуктовая spека (WHAT)

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как operator IMPLEMENT epic с independent s02+s03, я хочу parallel run, чтобы сократить wall time. | P0 | fixture 2 steps no deps → 2 worktrees spawned |
| US-002 | Как platform, я хочу fail-closed if file overlap, чтобы parallel не corrupt repo. | P0 | overlapping files → sequential fallback |
| US-003 | Как operator, я хочу default sequential, чтобы opt-in only. | P0 | EPIC_PARALLEL_SNN=0 unchanged behavior |

### Functional Requirements (FR-###)

- **FR-001:** Module `loop/parallel/` — `compute_ready_wave(index_yaml) -> list[sNN]` using deps graph from decompose index (extend index schema optional `depends_on: []` per step).
- **FR-002:** `file_overlap_check(step_a, step_b) -> bool` from shard Files sections.
- **FR-003:** Worktree pool: `create_worktree(epic, sNN)`, `destroy_worktree`; base branch current HEAD.
- **FR-004:** Orchestrator in loop.sh or Python: spawn parallel sessions max `EPIC_PARALLEL_MAX` default 2.
- **FR-005:** Each child runs standard prepare→agent→check_after for single sNN; parent waits; merge git via standard commit per T-HUB-033 or manual merge policy doc.
- **FR-006:** Index status updates serialized via existing flock.
- **FR-007:** Transition Engine: parallel mode only when `armed_step=IMPLEMENT` and registry allows.
- **FR-008:** Tests: wave computation; overlap detection; mock spawn count; sequential fallback.

### Success Criteria

| SC-001 | Wave of 2 independent steps identified | pytest |
| SC-002 | Overlap blocks parallel | pytest |
| SC-003 | EPIC_PARALLEL_SNN=0 no parallel spawn | integration mock |

### Assumptions

- v1 hub-only opt-in; product repos may disable.
- No cross-vendor agent mix in v1 — same runtime.

### Anti-scope

- Full Bernstein task graph planner; portal DAG rewrite; automatic git merge conflict resolution.

---

## AC

1. depends_on in decompose index schema (optional, backward compatible).
2. compute_ready_wave + overlap check.
3. Worktree spawn/mock integration test.
4. Env gates documented.
5. Requires T-HUB-029 arm_phase integration point documented.

---

## До DECOMPOSE

| sNN | Slice |
|-----|-------|
| s01 | index depends_on schema + wave compute |
| s02 | file overlap checker |
| s03 | worktree pool module |
| s04 | loop orchestrator opt-in |
| s05 | transition engine hook + tests |

---

## Следующий режим

→ BACK DECOMPOSE
