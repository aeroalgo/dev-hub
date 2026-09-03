# [T-HUB-032 | harness-analyze-convergence] PLAN

**Дата:** 2026-08-31  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** active  
**Roadmap:** [roadmap-harness-maturity-borrowings-epics.md](roadmap-harness-maturity-borrowings-epics.md)  
**Queue:** [roadmap-harness-maturity-borrowings-epics.queue.yaml](roadmap-harness-maturity-borrowings-epics.queue.yaml)  
**Deps:** **soft** T-HUB-024 (traceability parsers reuse).

**Skills:** writing-plans · python-testing-patterns · architecture-patterns

→ [T-HUB-032-harness-analyze-convergence/md/decompose-index.md](T-HUB-032-harness-analyze-convergence/md/decompose-index.md) — **после DECOMPOSE**

---

## Контекст

- **req:** Spec-kit-style **`analyze-convergence`**: read-only cross-artifact consistency report across plan + decompose + implement + optional git diff — beyond single-purpose `validate-traceability`.
- **gap:** `validate-traceability` checks refs/AC markers; нет unified «convergence» report (gaps, conflicts, orphan tasks, spec↔code drift summary).
- **refs:** GitHub spec-kit `/speckit.analyze`; T-HUB-024 traceability.py; T-HUB-026 reconcile.py (overlap — convergence = analyze, reconcile = as_built vs repo).

**CREATIVE need:** нет.

---

## Цель

Operator запускает `epic_resolve.py analyze-convergence --plan-id T-xxx` (или active sweep) и получает **`convergence-report/v1`** с categorized findings — read-only, suitable for pre-IMPLEMENT gate and post-hotfix review.

---

## Продуктовая speka (WHAT)

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как tech lead перед IMPLEMENT, я хочу convergence report, чтобы увидеть orphan FR и conflicting AC. | P0 | fixture orphan task → finding CV-003 |
| US-002 | Как operator, я хочу active sweep по tasks.md, как reconcile-spec. | P0 | same selector SoT as reconcile |
| US-003 | Как parent, я хочу optional `--include-git-diff`, чтобы видеть uncommitted delta vs plan. | P1 | git diff summary in report metadata |

### Functional Requirements (FR-###)

- **FR-001:** CLI `analyze-convergence` in `epic_resolve.py`: `--cwd`, `--plan-id` optional, `--format text|json`, `--strict`, `--include-git-diff`.
- **FR-002:** Report schema `convergence-report/v1`: findings `CV-001`… with categories: orphan_requirement, orphan_task, ac_conflict, traceability_gap, reconcile_overlap, stale_handoff.
- **FR-003:** Reuse `traceability.run_checks` + `reconcile.run_reconcile_spec` internally; dedupe findings by fingerprint.
- **FR-004:** Read-only: no file mutations; exit 0 with findings; `--strict` fail on HIGH+.
- **FR-005:** Optional loop integration: `EPIC_CONVERGENCE_CHECK=1` on IMPLEMENT arm (warn-only v1; block in v2 epic).
- **FR-006:** Tests: fixtures for each finding category; active sweep; strict exit codes.

### Success Criteria

| SC-001 | Cross-artifact orphan detected | pytest |
| SC-002 | Active sweep matches reconcile selector | pytest |
| SC-003 | Strict mode exit 1 on HIGH | pytest |

---

## AC

1. analyze-convergence CLI with text/json output.
2. convergence-report/v1 schema documented in loop/YAML-CONTRACT.md or schemas/README.
3. Reuses T-HUB-024/026 parsers without duplication explosion.
4. pytest coverage ≥ 15 tests.
5. Document in workflow-analyze or new cheatsheet when to run vs validate-traceability vs reconcile-spec.

---

## Техника / архитектура (HOW)

| Module | Role |
|--------|------|
| `.claude/hooks/epic/convergence.py` | orchestrator: run_checks + reconcile + git diff summary |
| `.claude/hooks/epic_resolve.py` | CLI subcommand |
| `loop/tests/test_convergence.py` | fixtures |

**Distinction matrix (document):**

| Command | Focus |
|---------|-------|
| validate-traceability | plan↔decompose↔implement refs + AC markers |
| reconcile-spec | as_built claims vs repo files |
| analyze-convergence | union + conflicts + orphan detection |

---

## До DECOMPOSE

| sNN | Slice |
|-----|-------|
| s01 | convergence.py + schema |
| s02 | CLI + text formatter |
| s03 | git diff optional + strict mode |
| s04 | loop opt-in env + integration test |
| s05 | docs distinction matrix |

---

## Следующий режим

→ BACK DECOMPOSE
