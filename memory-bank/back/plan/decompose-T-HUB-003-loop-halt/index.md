# [T-HUB-003 | loop-halt] DECOMPOSE index

**Plan:** [plan-T-HUB-003-loop-halt.md](../plan-T-HUB-003-loop-halt.md)  
**Status canon:** index.yaml  
**Created:** 2026-08-22  

---

## Requirements coverage

| FR/NFR/AC | sNN |
|-----------|-----|
| FR-1 (loop.sh halt=1 → exit 1) | s02 |
| FR-2 (loop.sh NEED_HUMAN → exit 1) | s01, s02 |
| FR-3 (EPIC_DONE → complete/chain без регрессии) | s01, s02 |
| FR-4 (ok continue без регрессии) | s01, s02 |
| FR-5 (last_session_path → epic_dir root) | s03 |
| FR-6 (тесты halt-parity + last_session unit) | s01, s03 |
| FR-7 (docs epic-loop / WORKFLOW / data-flow) | s04 |
| FR-8 (workers.md create + orphan claims cleanup) | s05 |
| FR-9 (projectbrief/architecture gaps согласованы) | s05 |
| NFR-1 (prepare halt fail-closed не сломан) | s02 |
| NFR-2 (repair_* в check_after не трогать) | s01, s02 |
| NFR-3 (contract activeContext не менять) | n/a — нет пересечений |
| NFR-4 (TDD red→green) | s01, s03 |
| NFR-5 (flock/model_substitution/phase models DoNotTouch) | s02 |
| AC+ 1 (mock check-after halt=true → exit≠0) | s01, s02 |
| AC+ 2 (stop=NEED_HUMAN → exit≠0) | s01, s02 |
| AC+ 3 (EPIC_DONE → exit 0/chain) | s01, s02 |
| AC+ 4 (last_session_path unit HUB_ROOT+slug) | s03 |
| AC+ 5 (rg epic-loop.md удалено/legacy-only) | s04 |
| AC+ 6 (test -f workers.md) | s05 |
| AC+ 7 (architecture index gaps закрыты) | s05 |
| AC− 1 (не HALT на continue) | s01, s02 |
| AC− 2 (не удалять product runtime dirs) | s04 |
| AC− 3 (нет Cursor epic stop-gate) | n/a |
| AC− 4 (не менять extract_verdict) | n/a |

## Stages coverage

| Этап плана | sNN |
|-----------|-----|
| Phase 1: halt matrix + pure decide helper (TDD) | s01 |
| Phase 2: wire loop.sh | s02 |
| Phase 3: last_session_path → epic_dir (TDD) | s03 |
| Phase 4: docs epic-loop/WORKFLOW/architecture data-flow | s04 |
| Phase 5: workers.md + projectbrief/index gaps | s05 |
| Phase 6: suite targeted + arch note Cursor hooks unwired | s06 |

## Outcome map

| Outcome | sNN |
|---------|-----|
| Outer retry на NEED_HUMAN исчезает | s01 + s02 |
| last-session.json рядом со state.json в hub epic_dir | s03 |
| Docs не врут о runtime root | s04 |
| architecture/workers.md создан | s05 |
| Orphan test_ports_browser claim удалён | s05 |
| Pytest entry для hub в techContext/architecture | s06 |
| Cursor hooks N/A wired — зафиксировано в architecture | s06 |

## Replacement cleanup

| Устаревает | sNN | deletes |
|-----------|-----|---------|
| Outer retry на NEED_HUMAN в `loop.sh` (check-after) | s02 | код ветки `else continue` после NEED_HUMAN |
| `last_session_path` → product `.claude/runtime/...` | s03 | hardcoded product path в `session_resilience.py` |
| Docs канон `.claude/runtime/epic/` как primary | s04 | строки в `epic-loop.md` / WORKFLOW где указан product path |
| Orphaned `tests/unit/test_ports_browser` claims | s05 | строки в `architecture/index.md` и `projectbrief.md` |

---

## Steps

- **s01** — Pure `decide_after_action` helper + TDD (red→green halt matrix)
- **s02** — `loop.sh` halt-parity wiring (потребляет s01 helper)
- **s03** — `last_session_path` → `epic_dir`-aligned implementation + TDD
- **s04** — Docs: `epic-loop.md`, `WORKFLOW.md`, `architecture/data-flow.md` — runtime canon
- **s05** — `workers.md` create; `projectbrief.md` + `architecture/index.md` gaps
- **s06** — Suite targeted run evidence + architecture note: Cursor hooks unwired / N/A

## Очередь шагов

| step_id | title & files | next_phase | status |
| :--- | :--- | :--- | :--- |
| **s01** | Pure decide_after_action helper + TDD (halt matrix) · [yaml](s01-decide-helper-tdd.yaml) | BACK IMPLEMENT | completed |
| **s02** | loop.sh halt-parity branches after check-after · [yaml](s02-loop-sh-wire.yaml) | BACK IMPLEMENT | completed |
| **s03** | last_session_path → epic_dir alignment (TDD) · [yaml](s03-last-session-path-tdd.yaml) | BACK IMPLEMENT | completed |
| **s04** | Docs: epic-loop.md / WORKFLOW.md / architecture data-flow canon · [yaml](s04-docs-epic-loop-workflow.yaml) | BACK IMPLEMENT | completed |
| **s05** | workers.md create + projectbrief/index gaps cleanup · [yaml](s05-workers-projectbrief-gaps.yaml) | BACK IMPLEMENT | completed |
| **s06** | Suite targeted run + architecture Cursor-hooks unwired note · [yaml](s06-suite-arch-hooks-note.yaml) | BACK IMPLEMENT | completed |