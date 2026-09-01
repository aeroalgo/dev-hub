# DECOMPOSE T-HUB-040 | harness-workflow-finish-api

**Plan:** [plan-T-HUB-040-harness-workflow-finish-api.md](../plan-T-HUB-040-harness-workflow-finish-api.md)  
**Role:** BACK  
**Next phase:** BACK IMPLEMENT  
**Steps:** s01–s11 (s10 P2 cut optional)

---

## Steps

| sNN | Slug | Title | Priority |
|-----|------|-------|----------|
| s01 | schemas-render | `loop/mb_finish/` schemas + render + shape tests | P0 |
| s02 | finish-implement | `finish_implement_step` + CLI `mb-finish implement` + rollback | P0 |
| s03 | stop-gate-fingerprint | Stop-gate `last_finish_tool` fingerprint + epic state wire | P0 |
| s04 | finish-handoff | `finish_handoff` low-level + doctor render reuse | P1 |
| s05 | finish-qa-bugfix | `finish_qa` + `finish_bugfix` | P1 |
| s06 | finish-decompose-plan | `finish_decompose` + `finish_plan` + transition engine delegate | P1 |
| s07 | finish-analyze-audit | `finish_analyze` + `finish_audit` | P1 |
| s08 | finish-creative-reflect | `finish_creative` + `finish_reflect` | P2 |
| s09 | rules-purge-prose | workflow rules + context_loop FINISH blocks purge prose → call tool | P0 |
| s10 | mcp-wrapper | (P2) MCP thin server + parity tests | P2 |
| s11 | legacy-purge | Legacy purge: prose FINISH instructions, dual handoff write paths | P0 |

---

## Requirements coverage

| Requirement | Kind | Covered by | Verify |
|-------------|------|------------|--------|
| US-001 — один CLI вызов finish implement | AC+ | s02 | `pytest harness/hooks/tests/test_mb_finish_implement.py -q` |
| US-002 — fail-closed без verify PASS | AC+ | s02 | `pytest -k test_finish_implement_no_verify -q` |
| US-003 — typed render activeContext, 0 shape errors | AC+ | s01 s02 | `pytest -k test_mb_finish_shape -q` |
| US-004 — finish_qa qa yaml + REFLECT handoff | AC+ | s05 | `pytest -k test_finish_qa_handoff -q` |
| US-005 — phase finish tools, uniform JSON contract | AC+ | s05 s06 s07 s08 | `.venv/bin/pytest harness/hooks/tests/ -q --tb=line -k "test_mb_finish_"` |
| US-006 — MCP server (P2) | AC+ | s10 | `pytest -k test_mcp_parity -q` |
| US-007 — doctor repair reuses render API | AC+ | s04 | `rg "render_active_context" loop/context_loop.py harness/hooks/epic/core.py` |
| US-008 — stop-gate без last_finish_tool fingerprint | AC+ | s03 | `pytest -k test_stop_gate_fingerprint -q` |
| FR-001 — модуль `loop/mb_finish/` pydantic models | FR | s01 | `python -c "from loop.mb_finish.schemas import MbFinishRequest"` |
| FR-002 — `render_active_context(...)` единственный writer | FR | s01 s09 s11 | `rg "write.*activeContext\|Write.*activeContext\|_implement_finish_block\|_qa_finish_block" loop/context_loop.py harness/hooks/epic/core.py loop/mb_finish/` — 0 ad-hoc writes |
| FR-003 — CLI subcommands (implement, qa, decompose …) | FR | s02 s05 s06 s07 s08 | `python harness/hooks/epic_resolve.py mb-finish --help` |
| FR-004 — finish_implement atomic: validate+verify+render+finalize | FR | s02 | `pytest -k test_finish_implement_happy -q` |
| FR-005 — finish_qa = qa yaml + sync_tasks_index | FR | s05 | `pytest -k test_finish_qa -q` |
| FR-006 — finish_decompose arms ANALYZE via Transition Engine | FR | s06 | `pytest -k test_finish_decompose_arm -q` |
| FR-007 — `last_finish_tool` stop-gate read | FR | s03 | `pytest -k test_stop_gate_no_fingerprint -q` |
| FR-008 — workflow rules + context_loop FINISH blocks → mb-finish call instructions | FR | s09 | `.venv/bin/pytest harness/hooks/tests/test_mb_finish_rules_purge.py -q --tb=line` |
| FR-009 — doctor repair reuses render | FR | s04 | `.venv/bin/pytest harness/hooks/tests/test_mb_finish_handoff.py -q --tb=line -k test_doctor_repair_uses_render` |
| FR-010 — MCP parity test | FR | s10 | `.venv/bin/pytest harness/hooks/tests/test_mcp_parity.py -q --tb=line -k test_mcp_parity` |
| FR-011 — extra=forbid pydantic, JSON stdout, stderr human, exit 0 only on ok:true | FR | s01 s02 | `.venv/bin/pytest harness/hooks/tests/test_mb_finish_implement.py -q --tb=line -k test_exit_code_policy` |
| FR-012 — hub/product PROJECT_ROOT cwd guard | FR | s02 s03 | `.venv/bin/pytest harness/hooks/tests/test_mb_finish_implement.py -q --tb=line -k test_finish_implement_bad_cwd` |
| AC-1 — ok:true + completed + shape valid на happy path | AC+ | s02 | `.venv/bin/pytest harness/hooks/tests/test_mb_finish_implement.py -q --tb=line -k test_finish_implement_happy` |
| AC-2 (US-002) — ok:false + in_progress без verify | AC− | s02 | `.venv/bin/pytest harness/hooks/tests/test_mb_finish_implement.py -q --tb=line -k test_finish_implement_no_verify` |
| SC-001 — 0 mutations on verify FAIL (ни implement, ни index не меняются) | AC− | s02 | `.venv/bin/pytest harness/hooks/tests/test_mb_finish_implement.py -q --tb=line -k test_finish_implement_no_verify` — assert both implement AND index status unchanged |
| SC-002 — 0 shape errors, 20 FINISH scenarios | AC+ | s01 s02 | `.venv/bin/pytest harness/hooks/tests/test_mb_finish_shape.py -q` |
| SC-003 — stop-gate blocks IMPLEMENT stop без finish tool fingerprint | AC− | s03 | `.venv/bin/pytest harness/hooks/tests/test_stop_gate_fingerprint.py -q --tb=line -k test_stop_gate_no_fingerprint` |
| SC-004 — doctor repair uses shared render | AC+ | s04 | `.venv/bin/pytest harness/hooks/tests/test_mb_finish_handoff.py -q --tb=line -k test_doctor_repair_uses_render` |
| TM-001 finish_implement happy | test matrix | s02 | `.venv/bin/pytest harness/hooks/tests/test_mb_finish_implement.py -q -k test_finish_implement_happy` |
| TM-002 verify missing → no mutation | test matrix | s02 | `.venv/bin/pytest harness/hooks/tests/test_mb_finish_implement.py -q -k test_finish_implement_no_verify` |
| TM-003 shape validator rejects bad load_now | test matrix | s01 | `.venv/bin/pytest harness/hooks/tests/test_mb_finish_shape.py -q -k test_render_invalid` |
| TM-004 finalize rollback restores activeContext | test matrix | s02 | `.venv/bin/pytest harness/hooks/tests/test_mb_finish_implement.py -q -k test_finish_implement_rollback` |
| TM-005 stop-gate without fingerprint | test matrix | s03 | `.venv/bin/pytest harness/hooks/tests/test_stop_gate_fingerprint.py -q -k test_stop_gate_no_fingerprint` |
| TM-006 finish_qa → REFLECT handoff | test matrix | s05 | `.venv/bin/pytest harness/hooks/tests/test_mb_finish_qa.py -q -k test_finish_qa_handoff` |
| TM-007 finish_decompose arms ANALYZE | test matrix | s06 | `.venv/bin/pytest harness/hooks/tests/test_mb_finish_decompose.py -q -k test_finish_decompose_armed_step` |
| TM-008 doctor repair uses render | test matrix | s04 | `.venv/bin/pytest harness/hooks/tests/test_mb_finish_handoff.py -q -k test_doctor_repair_uses_render` |
| TM-009 MCP parity | test matrix | s10 | `.venv/bin/pytest harness/hooks/tests/test_mcp_parity.py -q -k test_mcp_parity` |
| NFR: fail-closed on misconfig | AC− | s02 s03 | `.venv/bin/pytest harness/hooks/tests/test_mb_finish_implement.py -q -k test_finish_implement_bad_cwd` |
| NFR: rollback on finalize failure | AC− | s02 | `.venv/bin/pytest harness/hooks/tests/test_mb_finish_implement.py -q -k test_finish_implement_rollback` |

---

## Stages coverage

| Plan stage | sNN | Outcome |
|------------|-----|---------|
| `loop/mb_finish/schemas.py` + `render.py` + shape tests | s01 | module + tests green |
| `finish_implement_step` + CLI + rollback | s02 | CLI `mb-finish implement` works; TM-001..004 green |
| stop-gate `last_finish_tool` fingerprint | s03 | stop-gate blocks FINISH without fingerprint; TM-005 green |
| `finish_handoff` + doctor delegate | s04 | doctor uses `render_active_context`; TM-008 green |
| `finish_qa` + `finish_bugfix` | s05 | qa tool works; TM-006 green |
| `finish_decompose` + `finish_plan` + Transition Engine | s06 | decompose arms ANALYZE; TM-007 green |
| `finish_analyze` + `finish_audit` | s07 | both phase tools functional; matrix test green |
| `finish_creative` + `finish_reflect` | s08 | P2 phase tools functional |
| workflow rules purge prose FINISH blocks | s09 | context_loop FINISH prose → call tool; `rg` audit clean |
| MCP thin server + parity tests (P2) | s10 | MCP tool schema parity; TM-009 green |
| legacy purge: prose instructions + dual handoff paths | s11 | rg for removed patterns → 0 matches |

---

## Outcome map

| Outcome (plan) | sNN | Measurable verify |
|----------------|-----|-------------------|
| Harness FINISH не требует LLM прозы для activeContext | s01 s02 s09 | `rg '_implement_finish_block\s*(' loop/context_loop.py \| grep -v 'def _implement_finish_block'; test $? -ne 0` + аналог для `_qa_finish_block` |
| shape errors = 0 на FINISH | s01 s02 | `pytest -k test_mb_finish_shape -q` |
| Ложные PASS до finalize исключены | s02 s03 | `.venv/bin/pytest harness/hooks/tests/test_mb_finish_implement.py -q -k test_finish_implement_no_verify` + `.venv/bin/pytest harness/hooks/tests/test_stop_gate_fingerprint.py -q -k test_stop_gate_no_fingerprint` |
| doctor/incident reuses render API | s04 | `rg "render_active_context" loop/context_loop.py harness/hooks/epic/core.py` |
| Все фазы (qa, bugfix, decompose, plan, analyze, audit) — одинаковый JSON contract | s05 s06 s07 | `pytest -k "test_mb_finish_" -q` |
| Prose FINISH instructions в rules заменены на `mb-finish …` | s09 s11 | `rg "_implement_finish_block\|_qa_finish_block" loop/context_loop.py; test $? -ne 0` + `.venv/bin/pytest harness/hooks/tests/test_mb_finish_rules_purge.py -q --tb=line` |
| finish_creative + finish_reflect (P2) | s08 | `.venv/bin/pytest harness/hooks/tests/test_mb_finish_creative.py -q --tb=line` |
| MCP parity (P2) | s10 | `.venv/bin/pytest harness/hooks/tests/test_mcp_parity.py -q --tb=line -k test_mcp_parity` |

---

## Replacement cleanup

| Symbol / path | Kind | Replaced by | Cutover sNN | Fallback? |
|---------------|------|-------------|-------------|-----------|
| `_implement_finish_block()` in `loop/context_loop.py` | A — prose FINISH block | `mb-finish implement` call in rules | s09 | no |
| `_qa_finish_block()` in `loop/context_loop.py` | A — prose FINISH block | `mb-finish qa` call in rules | s09 | no |
| `_try_advance_active_context` ad-hoc strings in `epic/core.py` (partial) | A — ad-hoc concat | `mb_finish.render` | s04 | no |
| LLM regex Handoff mode extract as primary path | A — regex primary | `loop-handoff/v1` frontmatter via render_active_context | s11 | no |
| Dual-path handoff writes (direct Write + yaml) | A — dual write | single `finish_handoff` | s11 | no |
| Ручной `Write activeContext` на FINISH (rules/cheatsheets) | B — prose instruction | `epic_resolve.py mb-finish` | s09 | no |
| «напиши Handoff своими словами» (free-form done_summary prose) | C — free-form | typed `done_summary` field in MbFinishRequest + template | s09 | no |
| silent skip verify before completed | C — soft-fail | fail-closed `_verify_pass_ready_for_step` check in finish_implement_step | s02 | no |
| doctor ad-hoc activeContext patch strings | C — ad-hoc patch | `render_active_context` | s04 | no |

All rows non-`n/a` → `s11-legacy-purge` closes remaining deletes after cutover (sunset_inventory present in shard).
grep_control (anti-fallback): `rg "_implement_finish_block\|_qa_finish_block\|_try_advance_active_context" loop/context_loop.py harness/hooks/epic/core.py` → 0 after s11.

---

## Appetite mirror

`timebox_days: 5` · `cut_list: [s10 MCP server, s08 finish_reflect polish, janitor patch_index, extra phases if T-HUB-029 unstable]`

## Очередь шагов

| step_id | title & files | next_phase | status |
| :--- | :--- | :--- | :--- |
| **s01** | loop/mb_finish/ schemas + render + shape tests · [yaml](s01-schemas-render.yaml) |  | completed |
| **s02** | finish_implement_step + CLI mb-finish implement + rollback · [yaml](s02-finish-implement.yaml) |  | completed |
| **s03** | stop-gate last_finish_tool fingerprint + epic state wire · [yaml](s03-stop-gate-fingerprint.yaml) |  | pending |
| **s04** | finish_handoff low-level + doctor render reuse · [yaml](s04-finish-handoff.yaml) |  | pending |
| **s05** | finish_qa + finish_bugfix · [yaml](s05-finish-qa-bugfix.yaml) |  | pending |
| **s06** | finish_decompose + finish_plan + transition engine delegate · [yaml](s06-finish-decompose-plan.yaml) |  | pending |
| **s07** | finish_analyze + finish_audit · [yaml](s07-finish-analyze-audit.yaml) |  | pending |
| **s08** | finish_creative + finish_reflect (P2) · [yaml](s08-finish-creative-reflect.yaml) |  | pending |
| **s09** | workflow rules + context_loop FINISH blocks purge prose · [yaml](s09-rules-purge-prose.yaml) |  | pending |
| **s10** | MCP thin server + parity tests (P2) · [yaml](s10-mcp-wrapper.yaml) |  | pending |
| **s11** | legacy purge: prose FINISH instructions + dual handoff paths · [yaml](s11-legacy-purge.yaml) |  | pending |
