# [T-HUB-025 | product-constitution-bootstrap] PLAN

**Дата:** 2026-08-30  
**Режим:** BACK PLAN  
**Уровень:** L2–L3  
**Статус:** active  
**Roadmap:** [roadmap-spec-maturity-epics.md](roadmap-spec-maturity-epics.md)  
**Queue:** [roadmap-spec-maturity-epics.queue.yaml](roadmap-spec-maturity-epics.queue.yaml)  
**Deps:** нет hard. Soft: T-HUB-013 (template + hub starter done).

**Skills:** writing-plans · architecture-patterns · python-testing-patterns

→ [T-HUB-025-product-constitution-bootstrap/md/decompose-index.md](T-HUB-025-product-constitution-bootstrap/md/decompose-index.md) — **DECOMPOSE done 2026-08-31**

---

## Контекст

- **req:** каждый product `$PROJECT_ROOT` может получить `memory-bank/constitution.md` одной командой из hub template; VAN gate напоминает об адаптации; ANALYZE constitution pass не skip когда файл есть.
- **gap (as-built):** hub имеет `memory-bank/constitution.md` + `.cursor/templates/constitution.md`; ai-server и другие продукты — **нет** product constitution → ANALYZE pass 6 skipped; governance размазана по `.cursor/rules/`.
- **refs:** T-HUB-013 reflection; `.cursor/templates/constitution.md`; `memory-bank/constitution.md` (hub); `.cursor/rules/shared/workflow-analyze-core.mdc` §Constitution pass; `.cursor/rules/shared/workflow-van-brownfield.mdc`.

**CREATIVE need:** нет.

---

## Цель

Product repo получает адаптируемый constitution за одну fail-closed команду; workflow явно требует его для L2+ epics без silent skip ANALYZE authority check.

---

## Продуктовая спека (WHAT)

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как разработчик продукта, я хочу `seed-constitution` при первом BACK VAN, чтобы ANALYZE/AUDIT имели MUST authority. | P0 | Empty product → command → `memory-bank/constitution.md` exists with placeholders filled |
| US-002 | Как loop, я хочу fail-closed если constitution уже exists без `--force`, чтобы не затереть адаптацию. | P0 | Second run without `--force` → exit 2 |
| US-003 | Как PM, я хочу VAN checklist «constitution adapted?» для L2+ задач. | P1 | VAN template mentions constitution path |

#### Acceptance Scenarios — US-001

- **Given:** product repo without `memory-bank/constitution.md`, `$PROJECT_ROOT` set
- **When:** `python3 .claude/hooks/epic_resolve.py --cwd "$PROJECT_ROOT" seed-constitution`
- **Then:** file created from template; version/date/scope filled from product folder name + today; MUST-1..9 sections present

#### Acceptance Scenarios — US-002

- **Given:** existing adapted constitution
- **When:** seed without `--force`
- **Then:** exit 2; stderr names existing path; file unchanged

### Functional Requirements (FR-###)

- **FR-001:** Subcommand `seed-constitution` in `epic_resolve.py`: `--cwd`, optional `--force`, optional `--product-name`.
- **FR-002:** Source template: `.cursor/templates/constitution.md` from hub (resolve via dev-hub root when invoked from product).
- **FR-003:** Target: `$PROJECT_ROOT/memory-bank/constitution.md` only (never hub memory-bank when cwd=product).
- **FR-004:** Fill placeholders: version `1.0`, date ISO, scope from product name or directory basename.
- **FR-005:** Pre-fill MUST-1..9 from hub starter **wording** as sensible defaults (TDD, no silent fallback, FRONT parent-only, lean load, fail-closed, markers, ONE Handoff, integration parity, phase authority) — product may edit after.
- **FR-006:** Fail-closed: missing template → exit 2; missing memory-bank dir → create `memory-bank/` first.
- **FR-007:** VAN brownfield workflow: add gate bullet «L2+ epic: confirm `memory-bank/constitution.md` exists or run seed-constitution».
- **FR-008:** `workflow-analyze-core.mdc`: clarify pass runs when product file exists (already spec); add note in VAN doc only.
- **FR-009:** Unit tests `loop/tests/test_seed_constitution.py` with tmp_path product layout.
- **FR-010:** `memory-bank/techContext.md` (hub): document seed command for products.
- **FR-011:** Anti-mix: command refuses `--cwd` pointing at dev-hub root unless `DEV_HUB_CONSTITUTION_SEED=1` (prevent overwriting hub canonical).

### Success Criteria (SC-###)

| ID | Измеримый результат | Проверка | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | Seed creates valid file on empty product fixture | pytest | outcome |
| SC-002 | `--force` required to overwrite | pytest | outcome |
| SC-003 | Hub root protected by default | pytest | outcome |
| SC-004 | loop/tests green | pytest loop/tests/ -q | outcome |

### Assumptions

- Products symlink `.cursor/rules` from hub — template path resolvable.
- Constitution adaptation content remains human/AI edit after seed — not auto-customized per stack in v1.

### Clarifications

- Session: 2026-08-30 chat gap «constitution in product repo».
- Does not duplicate T-HUB-013 hub starter — only product bootstrap path.

### [НУЖНО УТОЧНИТЬ]

- n/a CRITICAL.

---

## AC

### AC+

1. `seed-constitution --help` documented
2. Product fixture gets constitution with ≥9 MUST sections
3. Existing file protected without `--force`
4. Hub root blocked by default
5. VAN workflow updated with one checklist item
6. techContext documents command

### AC−

1. Не перезаписывать hub `memory-bank/constitution.md` accidentally
2. Не auto-translate MUST rules per product stack in v1
3. Не require constitution for L1 TASK/BUGFIX
4. Не блокировать loop if constitution missing — warn in VAN only until product opts in strict mode (future)
5. Не дублировать T-HUB-013 template content changes — reuse existing template

---

## Техника / архитектура (HOW)

### Layout

| Path | Action |
|------|--------|
| `.claude/hooks/epic/constitution_seed.py` | Create |
| `.claude/hooks/epic_resolve.py` | Modify — subcommand |
| `loop/tests/test_seed_constitution.py` | Create |
| `.cursor/rules/shared/workflow-van-brownfield.mdc` | Modify — checklist bullet |
| `memory-bank/techContext.md` | Modify — product onboarding |

### Default MUST mapping (seed)

Copy hub starter MUST-1..9 verbatim into product file with scope line replaced — product edits MUST-1 commands/paths later.

### TDD plan

1. Red: seed empty tmp product
2. Red: refuse overwrite
3. Red: hub root guard
4. Green: implement
5. Green: VAN doc patch

---

## Replacement / sunset (brownfield)

n/a — greenfield tooling.

---

## До DECOMPOSE (черновик нарезки)

| Step | Суть |
|------|------|
| s01 | `constitution_seed.py` + CLI |
| s02 | hub root guard + `--force` semantics |
| s03 | VAN checklist + techContext |
| s04 | pytest suite + fixture products |

---

## Следующий режим

→ BACK DECOMPOSE
