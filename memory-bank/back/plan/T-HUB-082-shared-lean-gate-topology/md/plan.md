# T-HUB-082 — Shared lean gate topology

**Дата:** 2026-09-07 · **Режим:** BACK PLAN · **Уровень:** L3 · **Статус:** draft
**Clarify:** Phase 0 skipped — exact duplicates/deltas enumerated by audit. **Prompt:** [md/prompt.md](prompt.md)

## WHAT

`roadmap-merge.mdc` is an exact three-role duplicate; `security.mdc` is common body plus a one-line delta; BACK/INTEG VAN are equivalent. Extract only evidence-proven common contracts into shared owner files, retaining explicit role patches and all role semantics.

## FR / AC

- **FR-001:** one shared roadmap-merge lean contract serves BACK/FRONT/INTEG.
- **FR-002:** security has shared body plus named role patches only for real deltas.
- **FR-003:** BACK/INTEG VAN common contract is extracted only after fresh equivalence inventory; FRONT remains separate when UI semantics differ.
- **FR-004:** active callers use canonical path; topology test reports duplicate, missing patch and dangling old path.

1. Shared update is visible to all intended callers.
2. Role patch preserves artifact path/ownership/next semantics.
3. Recreated local copy or absent patch fails test.

### AC−

- No symlink or local fallback copy; no mass merge of unrelated `_lean` files; no change to security permissions or VAN requirements.

## HOW / Eng spine

```text
role workflow -> shared/_lean/common-contract -> optional role-patch -> artifact transition
```

| Failure | Detection | TM |
|---|---|---|
| old local link | graph inventory | TM-082-01 |
| lost role delta | semantic fixture | TM-082-02 |
| false VAN merge | FRONT/BACK fixtures | TM-082-03 |

## Replacement / sunset

| Kind | Legacy | Replacement | Policy |
|---|---|---|---|
| A | copied roadmap/security/VAN gates | shared contract + role patch | delete in-epic |
| C | local fallback on missing shared source | validation failure | delete in-epic |
| I | old workflow/gates references | canonical shared link | delete in-epic |
| B | n/a | n/a | n/a |

## QA consumes

TM-082-01 roadmap three-role owner; TM-082-02 security common/delta; TM-082-03 VAN parity; TM-082-04 no local fallback; TM-082-05 `bin/pytest -q --tb=line`.

## Review readiness

Product probe (one owner), Eng spine (source→patch→caller), delivery closure and QA matrix: **done**.

## Draft stages

1. Inventory/red tests; 2. roadmap merge extract; 3. security and evidence-approved VAN extract; 4. purge copies + regression/sunset scan.

## Следующий режим

→ **BACK DECOMPOSE T-HUB-082-shared-lean-gate-topology**
