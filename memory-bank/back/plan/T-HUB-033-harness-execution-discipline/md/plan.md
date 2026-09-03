# [T-HUB-033 | harness-execution-discipline] PLAN

**Дата:** 2026-08-31  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** active  
**Roadmap:** [roadmap-harness-maturity-borrowings-epics.md](roadmap-harness-maturity-borrowings-epics.md)  
**Queue:** [roadmap-harness-maturity-borrowings-epics.queue.yaml](roadmap-harness-maturity-borrowings-epics.queue.yaml)  
**Deps:** **hard** T-HUB-029 (finalize_step / transition API stable).

**Skills:** writing-plans · python-testing-patterns · architecture-patterns

→ [T-HUB-033-harness-execution-discipline/md/decompose-index.md](T-HUB-033-harness-execution-discipline/md/decompose-index.md) — **трекер шагов**

---

## Контекст

- **req:** GSD-style **execution discipline**: one implement shard = one fresh agent session = one atomic git commit (optional but default-on in hub); prevents context rot and enables `git bisect` on epic progress.
- **gap:** Multiple sNN in one session allowed; commits ad-hoc; no enforced session boundary at finalize_step.
- **refs:** GSD get-shit-done; chat P1-10; `finalize_step` in epic/core.py; token-economy one-shard load.

**CREATIVE need:** нет.

---

## Цель

После `finalize_step` для sNN loop может (when enabled) создать **canonical git commit** с message `{epic_id} sNN: {title}` и enforce **session boundary** — next prepare must be new session, not continue same chat.

---

## Продуктовая спека (WHAT)

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как operator, я хочу atomic commit per completed sNN, чтобы git log = epic timeline. | P0 | finalize → commit with sNN in message |
| US-002 | Как platform, я хочу opt-out via env, чтобы ad-hoc mode без commits остаётся. | P0 | EPIC_ATOMIC_COMMIT=0 skips |
| US-003 | Как parent, я хочу checkpoint flag session_boundary after finalize, чтобы loop не reuse chat. | P1 | checkpoint.session_boundary=true after sNN done |

### Functional Requirements (FR-###)

- **FR-001:** Env `EPIC_ATOMIC_COMMIT` default `0` in hub (document `1` for product repos); never commit without explicit env + clean git state check.
- **FR-002:** Module `loop/git_discipline.py`: `maybe_atomic_commit(cwd, epic_id, step_id, title) -> CommitResult`; fail-closed on dirty unrelated files (configurable allowlist).
- **FR-003:** Hook from `finalize_step` after mark-index-status success.
- **FR-004:** Commit message template: `{epic_id} {step_id}: {title}`; no AI-generated body.
- **FR-005:** `session_boundary` field on checkpoint record when atomic commit or always on finalize (DECOMPOSE: schema extend loop-checkpoint/v1 minor).
- **FR-006:** loop.sh respects session_boundary → forces new agent invocation marker.
- **FR-007:** Document one-shard-one-session in back-implement cheatsheet (align with GSD).
- **FR-008:** Tests: mock git; commit on success; skip when env=0; fail on dirty tree.

### Success Criteria

| SC-001 | Atomic commit on finalize when enabled | pytest mock git |
| SC-002 | No commit when EPIC_ATOMIC_COMMIT=0 | pytest |
| SC-003 | session_boundary set | pytest checkpoint |

### Assumptions

- Git operations only when user env enables; hub dev-hub repo may keep default 0.
- No auto-push; commit local only.

---

## AC

1. git_discipline module + finalize hook.
2. Env gate EPIC_ATOMIC_COMMIT documented.
3. session_boundary checkpoint field + loop respect.
4. Cheatsheet update one-shard-one-session.
5. Tests with git mock/fixture repo.

---

## Техника / HOW

| File | Change |
|------|--------|
| `loop/git_discipline.py` | new |
| `.claude/hooks/epic/core.py` | finalize_step hook |
| `loop/schemas/checkpoint.py` | session_boundary optional field |
| `loop/loop.sh` | read session_boundary |
| `.cursor/rules/shared/cheatsheets/back-implement.mdc` | discipline note |

---

## До DECOMPOSE

| sNN | Slice |
|-----|-------|
| s01 | git_discipline + tests mock |
| s02 | finalize_step hook |
| s03 | session_boundary schema + loop.sh |
| s04 | docs cheatsheet + project.env |

---

## Следующий режим

→ BACK DECOMPOSE
