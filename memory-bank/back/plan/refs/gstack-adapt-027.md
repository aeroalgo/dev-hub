# Ref-notes: gstack adaptation in dev-hub (T-HUB-027)

**Date:** 2026-08-31  
**Status:** active reference  
**Epic:** T-HUB-027-back-plan-gstack-adapt  
**Scope:** Adopted vs rejected practices from gstack (Gary Tan workflow & skills) into hub BACK PLAN & workflow.

---

## Borrowings summary

| Practice / Feature | Status | Hub adaptation & placement |
|---|---|---|
| Product probe (office-hours lite) | **Adopted** | Structured 6 forcing questions (`WHAT/HOW`, edge cases, scale, kill-switch, rollbacks) in `.cursor/rules/shared/workflow-clarify-core.mdc` |
| Eng review spine | **Adopted** | L3+ PLAN template mandatory sections: ASCII `Data flow`, `Failure matrix`, `Test matrix (plan-level)` |
| `qa_consumes` test plan | **Adopted** | Executable standalone `#qa-consumes` section in `plan-*.md` read directly by BACK QA without loading full plan |
| Plan review batch | **Adopted** | Compact inline review batch (security, edge cases, failure modes, scale) within a single PLAN session |
| Review readiness dashboard | **Adopted** | Explicit `Review readiness` table pre-DECOMPOSE gate (checking AC+, NFR, risk matrix, test plan) |
| gstack slash installation | **Rejected** | AC− #1: No external gstack CLI/slash package installation |
| Interactive 0–10 rating | **Rejected** | Replaced by deterministic eng spine self-check (3 lines) |
| GSD `.planning/` layout | **Rejected** | Preserved hub canonical `memory-bank/` layout |
| Browser Playwright in QA | **Rejected** | Browser QA stays strictly in FRONT; BACK QA uses backend suite & integration tests |
| "Plan = prompt" / DECOMPOSE replacement | **Rejected** | AC− #2: Preserved DECOMPOSE index & atomic shards (`sNN|eNN`) |

---

## Exemplar Fragment: Review readiness table (CLEARED)

```markdown
## Review readiness

| Metric / Aspect | Target | Current | Status |
|---|---|---|---|
| AC+ / AC− coverage | 100% mapped to test plan | All 8 ACs mapped | CLEARED |
| Data-flow & Failure matrix | Included (ASCII + table) | Present with 4 scenarios | CLEARED |
| QA Consumes section | Standalone `#qa-consumes` block | Defined with 5 tests | CLEARED |
| Risk & Rollback plan | Non-empty mitigation | 2 risks mitigated | CLEARED |
| Unresolved items / PII | 0 pending questions | 0 pending | CLEARED |
```
