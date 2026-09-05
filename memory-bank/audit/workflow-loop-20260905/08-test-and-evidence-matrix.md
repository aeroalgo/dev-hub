# 08. Test и evidence matrix для закрытия аудита

Цель этого файла — не добавить ещё prose в workflow, а превратить findings в проверяемые invariants.

## 1. Static repository checks

| Check | Сейчас | Требуемый результат |
|---|---|---|
| `@` literal refs | есть missing skill/archive/template refs | zero missing canonical refs; templates помечены и исключены корректно |
| agents vs manifest | 11 prompt files / 8 manifest entries | каждый prompt declared или explicit `advisory/unmaterialized` |
| phase verify agents | video agents referenced but omitted | every `verify_agent` resolves through manifest + runtime |
| route paths | video route paths missing | every intent command returns existing workflow |
| gates | janitor exception не описан | every workflow has Gate или machine-readable `no_gate_reason` |
| hooks | duplicate Claude realpaths | one registered hook per target/matcher |
| runtime sync | Claude hash mismatch | all runtime targets green or intentional generated diff |

## 2. Boundary schema tests

### Positive

- gate PASS/FAIL/BLOCKED with required `schema`, agent, context, timestamp;
- repair done/partial/fail with parent identity;
- sunset report with zero and non-zero items;
- `validate-result` for each registered schema;
- `mb-load-result` complete bundle.

### Negative

- missing `schema`;
- wrong schema id;
- extra fields;
- invalid enum/case/empty identifiers;
- missing `recorded_at`;
- malformed JSON fence/info-string;
- no fence with `data.verdict`;
- unknown sunset schema;
- stale step/session/epic;
- duplicate/overlapping repair blockers;
- `status=done` with remaining blockers.

## 3. Hook integration matrix

| Agent | Start inject | Stop parse | Schema | Retry | Sidecar/state | Finish mapping |
|---|---|---|---|---|---|---|
| verify-implement | yes | yes | gate | 2 | yes | implement |
| verify-bugfix | yes | yes | gate | 2 | yes | bugfix |
| verify-qa | yes | yes | gate | 2 | yes | qa / BLOCKED→bugfix |
| verify-decompose | yes | yes | gate | 2 | yes | decompose |
| analyze-verify | yes | yes | gate | 2 | yes | analyze |
| gate-repair | yes | yes | repair | 1 | state | no finish |
| explorer | workflow-dependent | no verdict | none | n/a | in-flight only | none |
| sunset-inventory | currently partial | currently no | sunset | n/a | currently no | none |
| verify-script | not declared | not wired | gate | n/a | no | no |
| verify-edit | not declared | not wired | gate | n/a | no | no |
| verify-publish | not declared | not wired | gate | n/a | no | no |

## 4. Property/invariant tests

1. `PASS` cannot finalize without current gate evidence.
2. `FAIL` cannot mutate index to completed.
3. `BLOCKED` QA cannot produce DONE.
4. Old session verdict cannot satisfy new gate identity.
5. Duplicate stop hook is idempotent.
6. Late stop hook cannot clear a newer in-flight entry.
7. Missing required `load_now` cannot return successful complete bundle.
8. Atomic crash at every finish stage recovers to one consistent state.
9. Route resolution never returns `ok` with nonexistent workflow.
10. Every generated runtime artifact has source hash.

## 5. Mutation targets

Особенно полезны mutation tests для:

- `if fence_data is not None or not data.get("verdict")`;
- `ok_status = True` после чтения load bundle;
- default schema fields;
- `extra="ignore"` в Codex collab model;
- broad `except Exception: pass` в pack/registry and mirror paths;
- `finish_handoff()` state mutation;
- hardcoded `REQUIRED_CODEX_AGENTS`.

## 6. Required test commands

Запускать из корня репозитория:

```bash
bin/pytest loop/tests/test_boundary_registry.py \
  loop/tests/test_validate_boundary.py \
  loop/tests/test_codex_collab_verdict.py \
  harness/hooks/tests/test_gate_repair.py \
  harness/hooks/tests/test_mcp_load_parity.py

bin/pytest loop/tests/test_workflow_pack_video_e2e.py \
  loop/tests/test_workflow_pack_phase_router.py \
  loop/tests/test_codex_hooks_parity_matrix.py

bin/pytest -q
```

Пока `REFLECT` migration не завершена, полный suite остаётся красным, поэтому результат нужно фиксировать как baseline, а не маскировать deselect-ом старых tests.

## 7. Evidence format

Каждое закрытие finding должно иметь:

```text
finding_id
source_paths + line references
before behavior
after invariant
test command
test result
runtime matrix
migration/deprecation status
```

Не считать finding закрытым по изменению prompt или зелёному unit test, если не проверен hook/CLI/runtime end-to-end path.
