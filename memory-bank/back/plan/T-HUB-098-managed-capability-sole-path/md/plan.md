# [T-HUB-098-managed-capability-sole-path] PLAN

**Дата:** 2026-09-14  
**Режим:** BACK PLAN (REPLAN spawn)  
**Уровень:** L2  
**Статус:** active  
**iteration:** 2  
**Replan-of:** `T-HUB-076-stack-profile-capability-execution`  
**Parent-prompt:** [memory-bank/back/plan/T-HUB-076-stack-profile-capability-execution/md/prompt.md](../../T-HUB-076-stack-profile-capability-execution/md/prompt.md) — immutable prior Epic SoT  
**Parent-replan:** [memory-bank/back/plan/T-HUB-076-stack-profile-capability-execution/md/replan-i2.yaml](../../T-HUB-076-stack-profile-capability-execution/md/replan-i2.yaml)  
**Parent I1 QA:** [memory-bank/back/qa/T-HUB-076-stack-profile-capability-execution/qa-20260907-stack-profile-capability-execution.yaml](../../../qa/T-HUB-076-stack-profile-capability-execution/qa-20260907-stack-profile-capability-execution.yaml)  
**Prompt (this epic):** [md/prompt.md](prompt.md)  
**Deps:** hard `T-HUB-076` (parent I1 in done; outcome continuity via Parent-prompt)  
**Batch:** replan-spawn-075-080-20260914  

→ После DECOMPOSE единственный трекер — `yaml/decompose-index.yaml`.

## Provenance

- Spawned by REPLAN of `T-HUB-076-stack-profile-capability-execution` on 2026-09-14.
- Prior Epic outcome SoT: `memory-bank/back/plan/T-HUB-076-stack-profile-capability-execution/md/prompt.md` (do not rewrite parent prompt).
- Parent remains in roadmap `done:`; this epic is the sole I2 delivery vehicle.
- I1 plan/decompose/QA under parent are historical; not overwritten.

## Outcome (verbatim summary из prompt.md Epic)

Workflow verification for a managed project becomes an executable, auditable capability boundary rather than an instruction to guess a test command. A declared verification intent either runs through the selected project target and produces a typed outcome, or the workflow stops with a diagnostic.

**Done when (кратко):**

1. An explicit verification check for each named target either succeeds with evidence or prevents a green workflow continuation.
2. A raw command string, stale proof or failed resolution cannot stand in for that evidence.
3. The hub remains able to test itself without being treated as a managed profile.

**Forbidden after (кратко):** No shell reconstruction, arbitrary execution input, implicit target, optional phase execution, cross-target proof reuse, prose-as-proof or **fallback from managed verification to a hub command**.

## Gap classification (только critical work I2)

| ID | Class | Описание | Surfaces |
|---|---|---|---|
| G076-1 | `legacy_removal` + `outcome_gap` | Workspace содержит strict `dev-hub.project.yaml` (managed root), но armed step / finish shard **не** объявляет `capability_checks`. Сегодня finish и check-after всё равно зеленят через hub-style `tests:` (`bin/pytest`). Это прямой managed→hub fallback, запрещённый prompt Forbidden after. | `harness/hooks/epic_yaml.py` (~721–761, ~1813–1848); `loop/context_loop.py` `_enforce_capability_checks_for_armed_step` / check_after (~2820–3111) |
| G076-2 | `hardening` | Finish/read принимает capability evidence, если совпадают fingerprint и status, даже когда JSON мог быть записан агентом (Write), а не executor/check-after path. Fingerprint + status недостаточны для Done when §2. Нужен executor-only write **или** validated provenance field на read/finish. | `loop/stack_profiles/evidence.py`; `loop/stack_profiles/execution.py`; `harness/hooks/epic_yaml.py` (finish branch); `loop/context_loop.py` (evidence writer) |

**Anti-carry (не входит в I2):** clear_open_on_start (079), TestFingerprintCache wiring (078), harness/agents instruction corpus (080), neighbor-epic write-deny primary ownership (077).

## backlog_candidates (NOT shards)

| ID | Описание | Почему backlog |
|---|---|---|
| BC-076-1 | Cross-check richer provenance (execution receipt id, subprocess pid metadata) beyond minimal `provenance_source` если Done when §2 уже закрыт минимальным полем | Не требуется prompt Done when при успешном executor-only + finish reject |
| BC-076-2 | Instruction wording в harness/agents для managed vs hub branch | OWNED BY T-HUB-080 |

## Technology axiom

| Выбор | Machine boundary | FORBIDDEN после I2 |
|---|---|---|
| Managed root detection | strict `dev-hub.project.yaml` at project root (existing T-HUB-075 containment) | infer managed from cwd heuristics без manifest |
| Verification in managed context | `capability_checks` + executor-produced evidence | hub `tests:` / `bin/pytest` as sole proof when managed manifest present |
| Evidence authority | sidecar с `provenance_source=executor` (или эквивалент) set only executor path | agent-written JSON with matching fingerprint accepted at finish |
| Hub self-test | no manifest → existing hub `tests:` canon | treating dev-hub repo root as managed profile |

## User Stories + Independent Test

| # | Story | P | Independent Test |
|---|---|---|---|
| US-I2-001 | Как QA owner managed monorepo, я не могу завершить step только hub pytest, если в root лежит `dev-hub.project.yaml`, даже когда shard «забыл» capability_checks. | P0 | Temp workspace: strict manifest + implement shard with only `tests: bin/pytest …` → finish/check-after HALT `managed_verification_requires_capability_checks`; zero green continuation. |
| US-I2-002 | Как оператор loop, я вижу check-after HALT на managed armed step без declaration до любого hub test run. | P0 | Armed step in managed fixture without `capability_checks` → check_after returns halt diagnostic; hub pytest subprocess not invoked as proof. |
| US-I2-003 | Как maintainer integrity boundary, я отвергаю capability sidecar, записанный агентом вручную, даже при valid fingerprint и status succeeded. | P0 | Agent Write fixture drops JSON at canonical path → finish/read returns `capability_evidence_non_authoritative`; legitimate executor-written sidecar still passes. |
| US-I2-004 | Как maintainer hub, я сохраняю hub self-test без manifest — существующие hub shards с `bin/pytest` остаются valid. | P1 | Hub-only fixture (no manifest) regression: finish green with hub tests; managed classifier not invoked. |

**Independent Test (epic):** Поднять temporary managed root с minimal manifest и fake target. Scenario A: shard declares `capability_checks` → executor writes evidence with provenance → finish green. Scenario B: same root, shard has only hub `tests:` → finish and check-after both HALT without subprocess proof. Scenario C: agent pre-writes forged sidecar with succeeded status → finish HALT non-authoritative. Scenario D: hub repo path without manifest → existing hub test finish still green.

## Acceptance Scenarios

### US-I2-001 — managed root forbids hub-only proof

- **Given:** project root contains valid strict `dev-hub.project.yaml` with at least one named target; decompose shard for armed step has `tests:` with `bin/pytest -q` but empty/missing `capability_checks`.
- **When:** operator runs check-after for armed step or attempts mb-finish on implement artifact.
- **Then:** workflow HALTs with typed diagnostic `managed_verification_requires_capability_checks` (or stable equivalent); finish validator does **not** treat hub `tests:` as sufficient verification; no green continuation.

### US-I2-002 — check-after does not skip managed classification

- **Given:** same managed root; `_enforce_capability_checks_for_armed_step` loads shard without `capability_checks`.
- **When:** check_after executes after phase transition.
- **Then:** function returns halt payload (not `None` silent pass); context loop blocks continuation before unrelated hub test execution is accepted as proof.

### US-I2-003 — forged agent-written evidence rejected

- **Given:** shard declares `capability_checks`; executor has **not** run; agent Write creates `memory-bank/<role>/execution/<epic>/<step>/capability-<fp>.json` with `status=succeeded` and matching fingerprint but missing/wrong `provenance_source`.
- **When:** finish validation or `read_capability_evidence` loads sidecar.
- **Then:** evidence treated as non-authoritative; finish error `capability_evidence_non_authoritative`; check-after would not have written this file in production path.

### US-I2-004 — hub boundary preserved

- **Given:** dev-hub self-test context (no `dev-hub.project.yaml` at resolved project root); implement shard uses canonical hub `tests:`.
- **When:** finish validation runs.
- **Then:** existing hub test canon applies; no requirement for `capability_checks`; managed classifier returns hub mode.

## Functional requirements

- **FR-001:** Add pure `classify_project_verification_context(project_root) -> hub|managed` using strict manifest presence (T-HUB-075 loader); fail-closed on ambiguous/unreadable manifest for managed claim.
- **FR-002:** When context is `managed`, finish validation (`epic_yaml.py` finish branches ~721–761 and step validator ~1813–1848) **requires** non-empty `capability_checks` on decompose shard for the finishing step; hub `tests:` alone MUST NOT satisfy verification; emit stable diagnostic `managed_verification_requires_capability_checks`.
- **FR-003:** Extend `_enforce_capability_checks_for_armed_step` / check_after path: if managed context and armed shard lacks `capability_checks`, return halt (not `None`); forbid treating absence as hub pass.
- **FR-004:** Extend `CapabilityExecutionEvidence` (or companion schema field) with mandatory `provenance_source: Literal["executor"]` (or enum) set **only** by `write_capability_evidence` / executor integration in `loop/stack_profiles/execution.py` and context_loop writer; schema rejects agent-supplied values on read if not executor-issued.
- **FR-005:** `read_capability_evidence` and finish gate MUST reject sidecars missing valid provenance even when fingerprint, status and exit_code match declaration; diagnostic `capability_evidence_non_authoritative`.
- **FR-006:** Preserve hub-only branch: when context is `hub`, existing `tests:` validation unchanged; no mandatory `capability_checks`; no regression to T-HUB-098 I1 positive paths covered by QA TM-001…TM-006.

## NFR

| ID | Requirement |
|---|---|
| NFR-001 | Managed vs hub classification MUST be deterministic from filesystem manifest only; no environment flag bypass. |
| NFR-002 | New diagnostics MUST be stable strings suitable for loop HALT and mb-finish error surfaces. |
| NFR-003 | Provenance enforcement MUST NOT break operator CLI `python -m loop.stack_profiles execute` diagnostic flows (CLI is not finish proof unless wired through check-after). |
| NFR-004 | Changes remain argv-only / no shell reconstruction; align with T-HUB-075 executor boundary. |
| NFR-005 | I2 diff stays within gap surfaces; no expansion into agents corpus or TestFingerprintCache. |

## Target layout (paths)

| Path | Responsibility I2 |
|---|---|
| `loop/stack_profiles/schemas.py` | Add/extend `provenance_source` on evidence model; strict validation on load |
| `loop/stack_profiles/evidence.py` | Executor-only stamp on write; read rejects non-authoritative |
| `loop/stack_profiles/execution.py` | Ensure execution result → evidence write is sole production mutator |
| `loop/context_loop.py` | Managed halt when shard lacks checks; provenance on check-after write |
| `harness/hooks/epic_yaml.py` | Managed finish branch; dual-path removal in ~721–761, ~1813–1848 |
| `loop/tests/test_stack_profile_execution*.py` | Extend with managed/hub classifier + forged evidence negatives |
| `harness/hooks/tests/test_epic_yaml*.py` (if present) | Finish managed-without-checks regression |

**Soft dependency (077):** tool Write deny on `memory-bank/{role}/execution/**/capability-*.json` — implement in 077; 076 MUST still fail-closed at read/finish if deny absent.

## Sunset A / B / C / I

### A. Code / modules

| Устаревает | Замена | Policy |
|---|---|---|
| `else:` branch in finish validators that runs `validate_tests_entries(..., finish=True)` whenever `has_capability_checks` is false **without** checking managed root | managed classifier → require capability_checks or HALT | delete in-epic |
| `_enforce_capability_checks_for_armed_step` returning `None` when `capability_checks` absent in managed workspace | explicit managed halt diagnostic | delete in-epic |
| `read_capability_evidence` accepting any JSON matching fingerprint/status | provenance-validated authoritative read | delete in-epic |

### B. Entrypoints

| Устаревает | Замена | Policy |
|---|---|---|
| check-after green path on managed project without declaration execution | managed halt before continuation | delete in-epic |
| mb-finish accepting agent-written capability sidecar | provenance gate | delete in-epic |

### C. Fallbacks / soft-fail

| Устаревает | Замена | Policy |
|---|---|---|
| managed project + missing `capability_checks` → hub pytest proof | `managed_verification_requires_capability_checks` HALT | delete in-epic |
| fingerprint match without executor provenance → PASS | `capability_evidence_non_authoritative` | delete in-epic |

### I. Instruction surfaces (minimal I2)

| Устаревает | Замена | Policy |
|---|---|---|
| Any finish-block prose implying hub pytest suffices inside managed repo | explicit «managed root requires capability_checks» in finish diagnostic only | note-only I2 — full agents corpus OWNED BY 080 |

## AC−

1. No managed→hub fallback: presence of `dev-hub.project.yaml` MUST NOT allow hub `tests:` as sole verification.
2. No silent pass when `_enforce_capability_checks_for_armed_step` sees managed shard without checks.
3. No finish PASS on agent-written capability JSON regardless of fingerprint/status match.
4. No new optional flag default-off that re-enables hub fallback for managed roots.
5. No breaking hub self-test path when manifest absent.
6. No scope creep into 077 write-deny implementation, 078 test cache, 080 agents inventory.

## QA consumes (#qa-consumes)

| ID | P | Scenario | Command / fixture | Expected | Maps |
|---|---|---|---|---|---|
| TM-I2-076-01 | P0 | Managed root + shard only hub `tests:` → finish denied | targeted pytest epic_yaml/finish fixture | HALT `managed_verification_requires_capability_checks` | FR-001,2 |
| TM-I2-076-02 | P0 | Managed armed step no capability_checks → check_after halt | context_loop integration fixture | halt payload; no green continuation | FR-003 |
| TM-I2-076-03 | P0 | Agent-forged sidecar with succeeded status → finish denied | write fake JSON + finish validator | `capability_evidence_non_authoritative` | FR-004,5 |
| TM-I2-076-04 | P1 | Hub root without manifest + hub tests → finish still valid | regression existing hub fixture | green; no capability requirement | FR-006 |
| TM-I2-076-05 | P1 | Executor-written sidecar with provenance → finish accepts | check-after integration path | green with matching declaration | FR-004,5,6 |

## Review readiness

| Gate | Required | Status | Evidence |
|---|---|---|---|
| I1 QA PASS | yes | done | qa-20260907-stack-profile-capability-execution.yaml |
| Gap scope locked to G076-1/G076-2 | yes | done | Gap classification table |
| Outcome verbatim from prompt Epic | yes | done | Outcome section |
| Anti-carry neighbor epics | yes | done | backlog + AC− |
| qa_consumes ≥3 TM | yes | done | TM-I2-076-01…05 |
| Eng failure matrix for I2 gaps | L2 | done | Acceptance Scenarios |
| §0.11 counterparts | yes | done | epic_yaml ↔ context_loop ↔ evidence.py mapped |
| Pending Required | none | done | — |

## Delivery closure

| Outcome slice | Class | Production entrypoint | Enforcement | Independent test |
|---|---|---|---|---|
| Managed root cannot hub-fallback | legacy_removal | `epic_yaml.py` finish + `context_loop.check_after` | managed classifier HALT | TM-I2-076-01, TM-I2-076-02 |
| Executor-only evidence authority | hardening | `evidence.py` write/read + finish gate | provenance field validate | TM-I2-076-03, TM-I2-076-05 |
| Hub self-test preserved | regression guard | hub branch unchanged | no manifest → hub canon | TM-I2-076-04 |

## Следующий режим

→ `BACK DECOMPOSE T-HUB-098-managed-capability-sole-path` (iteration 2).
