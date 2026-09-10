# Bugfix: QA verify-qa anti-ratchet (style blockers ineligible)
**Epic ID:** T-HUB-080-workflow-capability-instruction-parity  
**Date:** 2026-09-10  
**Author:** BACK BUGFIX  
**Source:** memory-bank/back/qa/T-HUB-080-workflow-capability-instruction-parity/qa-20260910-style-variable-naming-gap.yaml  

---

## 1. QA Root Cause Analysis
`qa-20260910-style-variable-naming-gap.yaml` armed BUGFIX on ineligible findings:
1. B1 — unrequested comments in template/test (style/doc annotation).
2. B2 — one-letter locals `p`/`f` (naming taste).
3. B3 — validate-boundary prompt hygiene attributed as product §0.11.

Root cause of the endless QA↔BUGFIX loop: `verify-qa` / parent treated style and «stricter than plan» as eligible blockers, raising the AC bar every re-QA.

## 2. Changes Implemented
- `harness/agents/verify-qa.md`: blocker eligibility + anti-ratchet HARD (eligible vs ineligible; PASS when only ineligible residuals).
- `loop/context_loop.py`, `loop/runtime_adapters/collaboration.py`, `loop/qa_outcome.py`, `loop/mb_finish/verify_hint.py`: parent QA path copies **eligible** B* only; FORBIDDEN style/naming/comments/«строже plan» → BUGFIX.
- `harness/cursor/rules/back_developer/isolation_rules/_lean/qa.mdc` + `workflow-qa.mdc`: anti-ratchet gates.
- Contract tests: `loop/tests/test_verify_qa_exhaustive_contract.py`, `loop/tests/test_mb_finish_verify_hint.py`.

## 3. Blocker closure
| ID | Disposition |
|----|-------------|
| B1 | **ineligible** (comments) — closed by anti-ratchet; no product delete of contract annotations |
| B2 | **ineligible** (naming) — closed by anti-ratchet |
| B3 | **ineligible** as product BUGFIX — validate-boundary remains prompt contract in verify-qa; clarified in agent text |

## 4. Verification
- `bin/pytest loop/tests/test_verify_qa_exhaustive_contract.py loop/tests/test_mb_finish_verify_hint.py loop/tests/test_next_prompt.py -q --tb=line`
- `python3 -m loop.cli.runtime_sync --check` (after apply for Codex materialize)
