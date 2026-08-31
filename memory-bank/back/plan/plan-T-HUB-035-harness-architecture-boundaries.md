# [T-HUB-035 | harness-architecture-boundaries] PLAN

**Дата:** 2026-08-31  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** active  
**Roadmap:** [roadmap-harness-maturity-borrowings-epics.md](roadmap-harness-maturity-borrowings-epics.md)  
**Queue:** [roadmap-harness-maturity-borrowings-epics.queue.yaml](roadmap-harness-maturity-borrowings-epics.queue.yaml)  
**Deps:** **soft** T-HUB-025 (constitution paths).

**Skills:** writing-plans · architecture-patterns · python-testing-patterns

→ [decompose-T-HUB-035-harness-architecture-boundaries/index.md](decompose-T-HUB-035-harness-architecture-boundaries/index.md) — **после DECOMPOSE**

---

## Контекст

- **req:** OpenAI harness **architecture boundary tests** with ratchet: enforce layer imports (loop ↔ hooks ↔ memory-bank ↔ product) via import-linter or equivalent; violations fail CI with remediation hints.
- **gap:** Ad-hoc dependency direction documented in architecture/ but not mechanically enforced.
- **refs:** OpenAI harness LAYERS.md + import rules; `memory-bank/architecture/`; harness-init pattern.

**CREATIVE need:** нет.

---

## Цель

CI-runnable **`validate-boundaries`** command: declarative rules in `loop/boundaries.yaml`; ratchet file tracks allowed legacy violations count (must not increase).

---

## Продуктовая spека (WHAT)

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как platform, я хочу CI fail on new cross-layer import, чтобы harness layers не смешивались. | P0 | test adds forbidden import → exit 1 |
| US-002 | Как developer, я хочу ratchet для legacy violations, чтобы постепенно ужесточать. | P1 | ratchet count unchanged → pass; increased → fail |

### Functional Requirements (FR-###)

- **FR-001:** `loop/boundaries.yaml` — contracts: `loop` must not import product app; hooks may import loop schemas; etc.
- **FR-002:** Implement checker using `import-linter` **or** lightweight AST grep (prefer existing deps; add import-linter to dev deps if needed).
- **FR-003:** CLI `python -m loop.boundaries check` + `--update-ratchet` (explicit, not in CI).
- **FR-004:** Ratchet file `loop/boundaries-ratchet.json` committed; CI compares violation count.
- **FR-005:** Document layers in `memory-bank/architecture/overview.md` § Boundaries (short pointer).
- **FR-006:** pytest wrapper test invoking checker on hub repo snapshot.
- **FR-007:** Optional: integrate into `loop doctor` checklist as warn.

### Success Criteria

| SC-001 | Known clean hub passes | pytest |
| SC-002 | Synthetic violation fails | pytest tmp |
| SC-003 | Ratchet blocks increase | pytest |

---

## AC

1. boundaries.yaml with ≥5 contracts for hub layers.
2. check CLI works in CI.
3. Ratchet mechanism tested.
4. architecture overview updated.

---

## До DECOMPOSE

| sNN | Slice |
|-----|-------|
| s01 | boundaries.yaml + checker module |
| s02 | ratchet json + CI test |
| s03 | doctor integration warn |
| s04 | architecture doc pointer |

---

## Следующий режим

→ BACK DECOMPOSE
