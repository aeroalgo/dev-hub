# [T-HUB-036 | harness-decompose-formulas] PLAN

**Дата:** 2026-08-31  
**Режим:** BACK PLAN  
**Уровень:** L2–L3  
**Статус:** active  
**Roadmap:** [roadmap-harness-maturity-borrowings-epics.md](roadmap-harness-maturity-borrowings-epics.md)  
**Queue:** [roadmap-harness-maturity-borrowings-epics.queue.yaml](roadmap-harness-maturity-borrowings-epics.queue.yaml)  
**Deps:** none.

**Skills:** writing-plans · architecture-patterns · python-testing-patterns

→ [decompose-T-HUB-036-harness-decompose-formulas/index.md](decompose-T-HUB-036-harness-decompose-formulas/index.md) — **после DECOMPOSE**

---

## Контекст

- **req:** Gas Town **formula / protomolecule** pattern: reusable decompose skeletons for recurring epic types (hooks epic, loop epic, CLI tool epic, docs epic) — repeatability of planning structure.
- **gap:** Each DECOMPOSE starts from generic template; no typed formulas with pre-filled sNN patterns.
- **refs:** Gas Town formulas TOML; `.cursor/templates/decompose/`; completed hub epics T-HUB-017, 023, 024 as exemplars.

**CREATIVE need:** нет.

---

## Цель

Catalog **`loop/formulas/`** with schema `decompose-formula/v1` + CLI **`formula-render`** that materializes draft `decompose-<id>/sNN-*.yaml` from formula + epic metadata — operator edits before commit.

---

## Продуктовая spека (WHAT)

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как planner нового loop epic, я хочу formula `loop-tooling`, чтобы DECOMPOSE начинался с проверенной структуры. | P0 | render → 5+ sNN yaml files |
| US-002 | Как platform, я хочу formula validation, чтобы broken template fail at render. | P0 | invalid formula → exit 2 |

### Functional Requirements (FR-###)

- **FR-001:** Schema `loop/schemas/formula.py` — formula id, description, default_level, steps[] with title, goal template, typical files pattern, verify hints.
- **FR-002:** Ship ≥3 formulas: `hooks-epic`, `loop-runtime-epic`, `cli-validate-epic` derived from T-HUB-023/017/024 decompose patterns.
- **FR-003:** CLI `formula-list`, `formula-render --formula <id> --epic-id T-xxx --slug <slug> --dry-run|--out dir`.
- **FR-004:** Render produces index.yaml skeleton + sNN yaml from `.cursor/templates/decompose/epic-step.yaml` merge.
- **FR-005:** Document in DECOMPOSE workflow: optional `--formula` hint in plan header.
- **FR-006:** Tests: render dry-run; schema validation; no overwrite without `--force`.

### Success Criteria

| SC-001 | 3 formulas render valid yaml | pytest |
| SC-002 | Rendered steps pass validate-decompose-tree after manual fill | manual smoke doc |

---

## AC

1. decompose-formula/v1 schema.
2. 3 bundled formulas.
3. formula-list + formula-render CLI.
4. DECOMPOSE workflow note.
5. Tests ≥ 10.

---

## До DECOMPOSE

| sNN | Slice |
|-----|-------|
| s01 | formula schema |
| s02 | 3 formula yaml files |
| s03 | formula-render CLI |
| s04 | tests + DECOMPOSE doc |

---

## Следующий режим

→ BACK DECOMPOSE
