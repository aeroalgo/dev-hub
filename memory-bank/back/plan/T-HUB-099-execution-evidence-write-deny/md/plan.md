# [T-HUB-099-execution-evidence-write-deny] PLAN

**Дата:** 2026-09-14  
**Режим:** BACK PLAN (REPLAN spawn)  
**Уровень:** L2  
**Статус:** active  
**iteration:** 2  
**Replan-of:** `T-HUB-077-gate-evidence-integrity`  
**Parent-prompt:** [memory-bank/back/plan/T-HUB-077-gate-evidence-integrity/md/prompt.md](../../T-HUB-077-gate-evidence-integrity/md/prompt.md) — immutable prior Epic SoT  
**Parent-replan:** [memory-bank/back/plan/T-HUB-077-gate-evidence-integrity/md/replan-i2.yaml](../../T-HUB-077-gate-evidence-integrity/md/replan-i2.yaml)  
**Parent I1 QA:** [memory-bank/back/qa/T-HUB-077-gate-evidence-integrity/qa-20260907-gate-evidence-integrity-pass.yaml](../../../qa/T-HUB-077-gate-evidence-integrity/qa-20260907-gate-evidence-integrity-pass.yaml)  
**Prompt (this epic):** [md/prompt.md](prompt.md)  
**Deps:** hard `T-HUB-077` (parent I1 in done; outcome continuity via Parent-prompt)  
**Batch:** replan-spawn-075-080-20260914  

→ После DECOMPOSE единственный трекер — `yaml/decompose-index.yaml`.

## Provenance

- Spawned by REPLAN of `T-HUB-077-gate-evidence-integrity` on 2026-09-14.
- Prior Epic outcome SoT: `memory-bank/back/plan/T-HUB-077-gate-evidence-integrity/md/prompt.md` (do not rewrite parent prompt).
- Parent remains in roadmap `done:`; this epic is the sole I2 delivery vehicle.
- I1 plan/decompose/QA under parent are historical; not overwritten.

## Outcome (verbatim summary из prompt.md Epic)

Workflow completion becomes trustworthy: a successful verification is an independently produced fact, not a mutable claim made by the agent that wants to continue.

**Done when (кратко):**

1. A worker cannot turn its own work into a passing verification.
2. Interrupted verification stops with an actionable typed failure.

**Forbidden after (кратко):** Manual pass markers, **mutable evidence as authority**, or silent gate cleanup.

## Gap classification (только critical work I2)

| ID | Class | Описание | Surfaces |
|---|---|---|---|
| G077-1 | `hardening` + `outcome_gap` | Worker может Write/Edit `memory-bank/{role}/execution/**/capability-*.json`. Mutable JSON стоит как verification proof — прямое нарушение Done when §1 и Forbidden «mutable evidence as authority». Нужно расширить `recorded_artifact_write_deny_reason` / pretool Write deny на execution evidence paths (или эквивалентный sole deny). | `harness/hooks/_lib.py` `recorded_artifact_write_deny_reason` (~3062–3089); `harness/hooks/pretool_policy.py` `WritePolicyAdapter` (~492–533) |
| G077-2 | `hardening` | Finish/read MUST treat agent-written capability evidence without executor provenance as non-authoritative (align с T-HUB-076 `provenance_source`); 077 owns enforcement at tool boundary + read-path reject hook integration, not executor stamp logic. | `harness/hooks/pretool_policy.py`; finish validators consuming `read_capability_evidence`; optional shared helper in `harness/hooks/_lib.py` |

**Anti-carry (не входит в I2):** managed→hub tests fallback (076), agents corpus (080), TestFingerprintCache (078), clear_open_on_start (079), foreign_dirty FAIL→PASS promote in subagent-stop (~170–184) unless proven forge path.

## backlog_candidates (NOT shards)

| ID | Описание | Почему backlog |
|---|---|---|
| BC-077-1 | foreign_dirty FAIL→PASS promote heuristic in `harness/hooks/subagent-stop.py` (~170–184) | Designed scope; not I2 unless proven worker forges PASS via that path |
| BC-077-2 | clear_open_on_start | OWNED BY T-HUB-079 |
| BC-077-3 | verification_results prose normalization for INTEG | Out of 077 outcome scope |

## Technology axiom

| Выбор | Machine boundary | FORBIDDEN после I2 |
|---|---|---|
| Tool Write deny | pretool policy before Write/Edit executes | agent mutating `memory-bank/*/execution/**/capability-*.json` |
| Evidence authority | executor provenance validated at read/finish (076 field) + deny at write | mutable sidecar as PASS proof |
| Verifier receipt (I1) | unchanged immutable gate receipt path | regress I1 TM-077-01…05 |

## User Stories + Independent Test

| # | Story | P | Independent Test |
|---|---|---|---|
| US-I2-001 | Как security boundary, я блокирую agent Write/Edit capability sidecar до записи на диск. | P0 | Pretool fixture: Write to `memory-bank/back/execution/<epic>/<step>/capability-deadbeef.json` → DENY with stable reason; executor/runtime write path still allowed. |
| US-I2-002 | Как finish gate, я не принимаю capability JSON, появившийся минуя executor, даже если deny обошли через shell heredoc. | P0 | Pre-seeded forged sidecar without provenance → finish/read non-authoritative (pairs with 076 FR-005). |
| US-I2-003 | Как operator, я сохраняю I1 verifier receipt integrity — новый deny не ломает runtime gate JSON paths. | P1 | Regression TM-077-01…05 remain green. |

**Independent Test (epic):** Attempt agent Write to execution evidence path → pretool DENY. Attempt Edit of existing executor-written sidecar → DENY. Legitimate check-after write (simulated executor hook) → allowed. Finish with forged file created before deny deployed → read rejects non-authoritative. Re-run I1 verifier receipt positive path → unchanged PASS.

## Acceptance Scenarios

### US-I2-001 — Write deny on execution evidence

- **Given:** active IMPLEMENT session; target path matches `memory-bank/<role>/execution/<epic_id>/<step_id>/capability-<fingerprint>.json`.
- **When:** agent invokes Write or Edit on that path.
- **Then:** `WritePolicyAdapter` returns DENY before tool execution; reason code stable (`execution_evidence_write_denied` or equivalent); event observable in hook telemetry.

### US-I2-002 — deny covers role variants

- **Given:** paths under `memory-bank/back/execution/`, `memory-bank/front/execution/`, `memory-bank/integration/execution/`.
- **When:** Write attempted on any matching capability sidecar name pattern.
- **Then:** deny applies uniformly; no role-specific bypass.

### US-I2-003 — finish read rejects non-authoritative capability evidence

- **Given:** forged sidecar on disk (e.g. created in test setup bypassing pretool) lacking executor `provenance_source`.
- **When:** mb-finish / epic_yaml finish validation loads evidence via `read_capability_evidence`.
- **Then:** validation fails `capability_evidence_non_authoritative`; finish non-zero; aligns with T-HUB-076 provenance contract.

### US-I2-004 — I1 gate receipts unaffected

- **Given:** valid verifier receipt from I1 path.
- **When:** finish/stop-gate validation runs.
- **Then:** existing receipt integrity checks pass; new execution deny patterns do not match runtime gate JSON paths incorrectly.

## Functional requirements

- **FR-001:** Extend `recorded_artifact_write_deny_reason` (or dedicated sibling `execution_evidence_write_deny_reason`) to match `memory-bank/{back,front,integration}/execution/{epic_id}/{step_id}/capability-*.json` using path-safe glob/regex; return stable deny string.
- **FR-002:** Wire new deny into `WritePolicyAdapter.evaluate` in `pretool_policy.py` before other allows; Write and Edit aliases covered.
- **FR-003:** Deny MUST apply to agent tool boundary for all roles; executor/check-after write path MUST remain allowed via allowlist (hook identity, subprocess writer, or temp-file atomic replace from trusted caller — exact mechanism in DECOMPOSE, but outcome is sole mutator).
- **FR-004:** Integrate finish/read non-authoritative rejection for capability sidecars missing valid executor provenance (delegate to `read_capability_evidence` from 076; 077 adds hook-level tests proving agent cannot establish authority via Write).
- **FR-005:** Preserve I1 verifier receipt enforcement (FR-001…I1 FR-005); no regression on TM-077-01…05; no new manual PASS paths.

## NFR

| ID | Requirement |
|---|---|
| NFR-001 | Deny reason strings MUST be machine-stable for pretool telemetry and agent additionalContext. |
| NFR-002 | Path matching MUST use resolved relative path under project root; no directory traversal bypass. |
| NFR-003 | Performance: deny check is O(1) regex on path, no full events.jsonl scan for execution paths. |
| NFR-004 | Provider parity: Claude pretool and Codex bridge route through same `WritePolicyAdapter`. |

## Target layout (paths)

| Path | Responsibility I2 |
|---|---|
| `harness/hooks/_lib.py` | `execution_evidence_write_deny_reason` or extended `recorded_artifact_write_deny_reason` |
| `harness/hooks/pretool_policy.py` | Wire deny in `WritePolicyAdapter` |
| `harness/hooks/agent-pretool.py` (if registration) | Ensure adapter order unchanged except new deny |
| `loop/stack_profiles/evidence.py` | Consumer of provenance read (076); 077 tests integration only |
| `harness/hooks/tests/test_pretool_policy*.py` | New negatives for execution path Write |
| `harness/hooks/tests/test_gate_evidence*.py` | Forged sidecar finish reject |

**Not in 077 files list:** managed classifier (076), TestFingerprintCache (078), agents prompts (080).

## Sunset A / B / C / I

### A. Code / modules

| Устаревает | Замена | Policy |
|---|---|---|
| Absence of write deny on `memory-bank/*/execution/**/capability-*.json` | pretool DENY | delete in-epic |
| Finish accepting any readable JSON at evidence path | provenance-aware read (076) + deny at source | delete in-epic |

### B. Entrypoints

| Устаревает | Замена | Policy |
|---|---|---|
| Agent Write as capability proof transport | executor-only + deny | delete in-epic |

### C. Fallbacks

| Устаревает | Замена | Policy |
|---|---|---|
| «File exists ⇒ evidence OK» for capability sidecars | non-authoritative without provenance | delete in-epic |

### I. Instruction surfaces

| Устаревает | Замена | Policy |
|---|---|---|
| Prompts suggesting manual creation of capability JSON | deny + wait for check-after (minimal) | note-only; full agents OWNED BY 080 |

## AC−

1. No agent Write/Edit success on capability execution sidecar paths in pretool fixtures.
2. No finish PASS solely because forged sidecar exists with succeeded status.
3. No regression of I1 verifier receipt deny paths (runtime gate JSON still governed by I1 rules).
4. No implementation of managed→hub fallback fix (076 scope).
5. No scope into TestFingerprintCache or clear_open_on_start.

## QA consumes (#qa-consumes)

| ID | P | Scenario | Command / fixture | Expected | Maps |
|---|---|---|---|---|---|
| TM-I2-077-01 | P0 | Agent Write capability sidecar denied | pretool policy pytest | DENY `execution_evidence_write_denied` | FR-001,2 |
| TM-I2-077-02 | P0 | Agent Edit existing capability sidecar denied | pretool policy pytest | DENY | FR-002 |
| TM-I2-077-03 | P0 | Forged sidecar without provenance → finish fail | finish integrity pytest | non-authoritative error | FR-004 |
| TM-I2-077-04 | P1 | I1 verifier receipt positive path regression | existing TM-077-05 fixture | PASS unchanged | FR-005 |
| TM-I2-077-05 | P1 | Executor/check-after write path still permitted | integration fixture with trusted writer | file persisted | FR-003 |

## Review readiness

| Gate | Required | Status | Evidence |
|---|---|---|---|
| I1 QA PASS | yes | done | qa-20260907-gate-evidence-integrity-pass.yaml |
| Gap scope G077-1/G077-2 only | yes | done | Gap table |
| 076 provenance alignment noted | yes | done | Technology axiom + FR-004 |
| qa_consumes ≥3 TM | yes | done | TM-I2-077-01…05 |
| Anti-carry | yes | done | backlog + AC− |
| Pending Required | none | done | — |

## Delivery closure

| Outcome slice | Class | Production entrypoint | Enforcement | Independent test |
|---|---|---|---|---|
| Agent cannot Write capability proof | hardening | `pretool_policy.WritePolicyAdapter` | path deny before Write | TM-I2-077-01, TM-I2-077-02 |
| Non-authoritative read at finish | hardening | `read_capability_evidence` + finish | provenance validate | TM-I2-077-03 |
| I1 receipt path preserved | regression | existing subagent-stop/stop-gate | no dual authority | TM-I2-077-04 |

### CREATIVE need
**нет**

## Следующий режим

→ `BACK DECOMPOSE T-HUB-099-execution-evidence-write-deny` (iteration 2).
