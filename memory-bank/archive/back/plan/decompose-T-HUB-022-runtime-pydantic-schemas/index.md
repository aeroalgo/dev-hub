# Decompose — T-HUB-022 runtime-pydantic-schemas
**Plan:** [plan-T-HUB-022-runtime-pydantic-schemas.md](../plan-T-HUB-022-runtime-pydantic-schemas.md)  
**Дата:** 2026-08-31  
**Статус очереди:** index.yaml  
**Режим:** BACK DECOMPOSE  

---

## Цель эпика

Единый Pydantic слой для всех machine-readable границ loop — runtime persistence + transition contracts.
Validate-on-read (fail-soft с diagnostic) / validate-before-write (strict).
Sunset `repair_*` auto-rewrite как hot path; drift counters вместо молчаливых правок.
Markdown/prose — только view layer.

**Target flow:** `typed artifact ──validate──► event ──reduce──► projection ──render──► markdown`.

---

## Шаги очереди

| step | file | outcome-first title | status |
|------|------|---------------------|--------|
| s01 | s01-inventory-fields.yaml | Inventory all state/checkpoint/event/handoff/gate fields from code + tests | pending |
| s02 | s02-epic-state-drift-counters.yaml | EpicState + DriftCounters Pydantic model + golden fixtures | pending |
| s03 | s03-wire-state-io.yaml | Wire load_epic_state / save_epic_state + drift counter increment helper | pending |
| s04 | s04-checkpoint-record.yaml | CheckpointRecord Pydantic model + validate_checkpoint typed | pending |
| s05 | s05-loop-event.yaml | LoopEvent model + epic_events typed append | pending |
| s06 | s06-board-card-metadata.yaml | BoardCardMetadata model + card_model integration | pending |
| s07 | s07-handoff-frontmatter-consolidate.yaml | Consolidate HandoffFrontmatter spike — tests + schemas/README | pending |
| s08 | s08-gate-verdict-strict.yaml | Consolidate GateVerdictRecord + store strict validate | pending |
| s09 | s09-handoff-strict-flag.yaml | PROJECT_LOOP_HANDOFF_STRICT + stop-gate FINISH gate + project.env | pending |
| s10 | s10-qa-finish-handoff.yaml | validate_qa_finish_handoff via frontmatter mode + epic_yaml verdict | pending |
| s11 | s11-index-yaml-only.yaml | index yaml-only writes; md mirror runner-only; agent prompt touch | pending |
| s12 | s12-repair-counters.yaml | PROJECT_LOOP_REPAIR_LEGACY — wire drift counters on all repair_* paths | pending |
| s13 | s13-integration-tests.yaml | Integration tests + full loop suite (pytest -q) | pending |
| s14 | s14-readme-drift-display.yaml | README + §0.11 integration grep + loop status drift display | pending |
| s15 | s15-audit-repair-purge.yaml | AUDIT: repair_* caller purge / regex fallback metrics near zero | pending |
| s16 | s16-legacy-purge.yaml | Legacy dict-validation + repair auto-rewrite purge (final sunset) | pending |

---

## Requirements coverage

| Requirement | Step(s) | Coverage |
|-------------|---------|---------|
| US-001 — fail-closed diagnostic corrupt state.json | s02, s03, s13 | EpicState + load wire + integration |
| US-002 — typed CheckpointRecord, validate_checkpoint | s04, s13 | CheckpointRecord + integration |
| US-003 — BoardCardMetadata validate before upsert | s06, s13 | BoardCardMetadata + integration |
| US-004 — schema_version on every artifact | s02, s05, s13 | EpicState, LoopEvent + integration |
| US-005 — phase from reducer, not regex | s10, s13 | validate_qa_finish_handoff + integration |
| US-006 — typed verdict sidecar, sidecar-first | s08, s13 | GateVerdictRecord strict write + integration |
| US-007 — STRICT=1 blocks FINISH without frontmatter | s09, s13 | stop-gate STRICT flag + integration |
| US-008 — drift_counters in state/status on repair/fallback | s03, s12, s14 | increment_drift_counter wire + display |
| US-009 — agent writes status only in index.yaml | s11, s13 | yaml-only guard + integration |
| FR-001 — EpicState Pydantic | s02, s03 | model + wire |
| FR-002 — CheckpointRecord Pydantic | s04 | model |
| FR-003 — DriftCounters, increment_drift_counter | s02, s03, s12 | model + helper + wire |
| FR-004 — HandoffFrontmatter, GateVerdictRecord strict | s07, s08, s09 | tests + strict write + flag |
| FR-005 — LoopEvent Pydantic | s05 | model + wire |
| FR-006 — BoardCardMetadata Pydantic | s06 | model + wire |
| FR-007 — loop status drift display, README §0.11 | s11, s14, s15 | guard + display + audit |
| AC+1 — fail-soft read: invalid → diagnostic + safe default | s03, s13 | load_epic_state wire |
| AC+2 — validate_checkpoint structured error | s04 | CheckpointRecord-based validate |
| AC+3 — save_epic_state strict via EpicState | s03 | save wire |
| AC+4 — Pydantic models all boundaries | s02–s08 | all 6 schema models |
| AC+5 — board metadata parse raises clear error | s06 | BoardCardMetadata |
| AC+6 — sidecar PASS overrides transcript FAIL | s08 | strict write + extract_verdict |
| AC+7 — legacy AC STRICT=0 auto-project | s09 | stop-gate flag |
| AC+8 — QA FINISH: qa-*.yaml verdict required | s10 | validate_qa_finish_handoff |
| AC−1 — no new HALT from schema read | s03, s13 | fail-soft pattern |
| AC−2 — backward compat: model_validator coerce | s02, s04 | EpicState extra=allow; CheckpointRecord |
| AC−3 — no duplicate schema definitions | s01 (inventory) + s02–s08 (single SoT per type) | loop/schemas/ only |

---

## Stages coverage

| Stage (plan outline) | Covered by | Gap |
|----------------------|-----------|-----|
| Inventory fields from code + tests + spike | s01 | нет |
| EpicState + DriftCounters model | s02 | нет |
| Wire load/save + counter helper | s03 | нет |
| CheckpointRecord + validate | s04 | нет |
| LoopEvent + append | s05 | нет |
| BoardCardMetadata + card_model | s06 | нет |
| HandoffFrontmatter consolidate | s07 | нет |
| GateVerdictRecord strict | s08 | нет |
| STRICT flag + stop-gate | s09 | нет |
| validate_qa_finish_handoff | s10 | нет |
| index yaml-only | s11 | нет |
| repair_* counters | s12 | нет |
| Integration tests + suite | s13 | нет |
| README + §0.11 + drift display | s14 | нет |
| AUDIT repair caller | s15 | нет |
| Legacy purge final | s16 | нет |

---

## Outcome map

| Outcome | Шаги | Test evidence |
|---------|------|---------------|
| Corrupt state.json → diagnostic, no crash | s03 | test_state_io.py::test_load_corrupt_json |
| All schema files in loop/schemas/ | s02,s04,s05,s06 | rg class.*Model loop/schemas/ |
| drift_counters in state after repair | s12 | test_repair_counters.py |
| Sidecar PASS overrides FAIL transcript | s08 | test_schemas_gate_verdict.py::test_sidecar_pass |
| STRICT=1 blocks legacy FINISH | s09 | test_handoff_strict_flag.py |
| index.yaml is single status SoT | s11 | test_index_yaml_only.py |
| Full loop suite green | s13, s16 | pytest loop/tests/ -q |
| repair_* auto-rewrite removed | s15, s16 | rg audit → 0 stale callers |

---

## Replacement cleanup

Brownfield replace — repair_* auto-rewrite:

| Старый код | Замена | Шаг удаления |
|-----------|--------|-------------|
| `repair_index_mirror()` auto md-write блок | log + `increment_drift_counter` counter only | s16 |
| `repair_fingerprint_stall()` auto-clear | log + counter only | s16 |
| `repair_finish_desync()` auto Handoff rewrite | log + counter only | s16 |
| `EVENT_SCHEMA` dict в epic_events.py | `LoopEvent.model_fields` alias или удаление | s16 |
| frozenset-validation в validate_checkpoint (дублирует CheckpointRecord Literals) | CheckpointRecord-based validate | s04 / s16 |

Import-audit cp в s16: `rg 'repair_index_mirror|repair_fingerprint_stall|repair_finish_desync|EVENT_SCHEMA'` → 0 unexpected callers.

## Очередь шагов

| step_id | title & files | next_phase | status |
| :--- | :--- | :--- | :--- |
| **s01** | Inventory all state/checkpoint/event/handoff/gate fields from code + tests · [yaml](s01-inventory-fields.yaml) | BACK IMPLEMENT | completed |
| **s02** | EpicState + DriftCounters Pydantic model + golden fixtures · [yaml](s02-epic-state-drift-counters.yaml) | BACK IMPLEMENT | completed |
| **s03** | Wire load_epic_state / save_epic_state + drift counter increment helper · [yaml](s03-wire-state-io.yaml) | BACK IMPLEMENT | completed |
| **s04** | CheckpointRecord Pydantic model + validate_checkpoint typed · [yaml](s04-checkpoint-record.yaml) | BACK IMPLEMENT | completed |
| **s05** | LoopEvent model + epic_events typed append · [yaml](s05-loop-event.yaml) | BACK IMPLEMENT | completed |
| **s06** | BoardCardMetadata model + card_model integration · [yaml](s06-board-card-metadata.yaml) | BACK IMPLEMENT | completed |
| **s07** | Consolidate HandoffFrontmatter spike — tests + schemas/README · [yaml](s07-handoff-frontmatter-consolidate.yaml) | BACK IMPLEMENT | completed |
| **s08** | Consolidate GateVerdictRecord + store strict validate · [yaml](s08-gate-verdict-strict.yaml) | BACK IMPLEMENT | completed |
| **s09** | PROJECT_LOOP_HANDOFF_STRICT + stop-gate FINISH gate + project.env · [yaml](s09-handoff-strict-flag.yaml) | BACK IMPLEMENT | completed |
| **s10** | validate_qa_finish_handoff via frontmatter mode + epic_yaml verdict · [yaml](s10-qa-finish-handoff.yaml) | BACK IMPLEMENT | completed |
| **s11** | index yaml-only writes; md mirror runner-only; agent prompt touch · [yaml](s11-index-yaml-only.yaml) | BACK IMPLEMENT | completed |
| **s12** | PROJECT_LOOP_REPAIR_LEGACY — wire drift counters on all repair_* paths · [yaml](s12-repair-counters.yaml) | BACK IMPLEMENT | completed |
| **s13** | Integration tests + full loop suite (pytest -q) · [yaml](s13-integration-tests.yaml) | BACK IMPLEMENT | completed |
| **s14** | README + §0.11 integration grep + loop status drift display · [yaml](s14-readme-drift-display.yaml) | BACK IMPLEMENT | completed |
| **s15** | AUDIT: repair_* caller purge / regex fallback metrics near zero · [yaml](s15-audit-repair-purge.yaml) | BACK IMPLEMENT | completed |
| **s16** | Legacy dict-validation + repair auto-rewrite purge (final sunset) · [yaml](s16-legacy-purge.yaml) | BACK IMPLEMENT | completed |