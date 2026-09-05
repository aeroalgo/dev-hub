# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-061-boundary-cli-doctor-hygiene
**План:** [plan.md](plan.md)
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**
**Дата:** 2026-09-04
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача. Shard: `sNN-<slug>.yaml`.

> **status SoT = `decompose-index.yaml` only.** `decompose-index.md` status — best-effort зеркало.

| Step | Title | Status |
| :--- | :--- | :--- |
| s01 | Fix doctor boundary kwargs TypeError (call-site + tests) | pending |
| s02 | Fix harness SoT CLI flag: --raw-json → --json в agent/hook/preset sources | pending |
| s03 | Rematerialize .claude/.codex/dsh surfaces после harness SoT fix | pending |
| s04 | Purge prose REPAIR: fallback из extract_repair_result | pending |

---

## Requirements coverage (plan → steps)

| Req ID | Plan FR text (verbatim) | sNN | Notes |
| :--- | :--- | :--- | :--- |
| US-001 | Как loop/hooks, я хочу чтобы `validate-boundary --schema-id … --raw-json '…'` работал без argparse error (SoT: `--json`), чтобы machine-path gate не падал на unrecognized arg | s02, s03 | |
| US-002 | Как operator `doctor --json`, я хочу честный `boundary_violations` pass/warn/skip без TypeError kwargs, чтобы видеть architecture violations | s01 | |
| US-003 | Как loop/hooks, я хочу чтобы `extract_repair_result` принимал только валидный JSON fence, чтобы prose `REPAIR:` не был machine SoT | s04 | |
| US-004 | Как Codex/Claude operator, я хочу чтобы materialized agents не содержали `--raw-json` после sync | s03 | |
| FR-001 | CLI `validate-boundary` принимает `--json` (SoT-флаг) + alias `--payload`; `--raw-json` → argparse error (unrecognized) | s02 | |
| FR-002 | Harness SoT (agent .md, hook CONTRACT strings, preset .prompt.md) использует только `--json`; `--raw-json` absent rg-audit | s02, s03 | |
| FR-003 | Materialized surfaces (.claude/agents/*.md, .codex/agents/*.toml, dsh/presets/*.prompt.md) синхронны harness SoT (без `--raw-json` drift) | s03 | |
| FR-004 | `loop/incidents/doctor.py` вызывает `check_boundaries(root_dir=…, boundaries_yaml_path=…)` (без `yaml_file=`) | s01 | |
| FR-005 | doctor `--json` → checklist `boundary_violations` detail не содержит `TypeError: unexpected keyword argument 'yaml_file'` | s01 | |
| FR-006 | Из `extract_repair_result` удалены: (a) prose `REPAIR:` regex success path; (b) soft-return invalid payload после pydantic `Exception` без `model_validate` success | s04 | |
| FR-007 | `harness/hooks/tests/test_gate_repair.py::test_extract_repair_result_from_repair_line_fallback` удалён или переписан на assert `is None` / schema miss | s04 | |
| FR-008 | Enforce scan в implement/QA: `rg -n -- '--raw-json' harness/agents harness/hooks/_lib.py .claude/agents .codex/agents dsh/presets` → 0 matches | s02, s03 | |
| FR-009 | Документировать в implement done: команда rematerialize (`bin/runtime-sync` / `python -m loop… materialize`) фактически прогнанная в эпике | s03 | |
| NFR-001 | Fail-closed: mis-taught CLI / broken doctor check → явная ошибка или честный warn, не silent skip как «всё ок» | s01, s04 | |
| NFR-002 | Не расширять scope на mid-turn JSON, MCP Cursor live, SessionEnd/PreCompact | s01, s02, s03, s04 | |
| NFR-003 | Rematerialize идемпотентен; alongside layout не ломается | s03 | |
| SC-001 | `rg -n -- '--raw-json' harness/ .claude/agents .codex/agents dsh/presets → empty` | s02, s03 | |
| SC-002 | `validate-boundary --raw-json '{}'` → non-zero exit / argparse error | s02, s04 | |
| SC-003 | `doctor --json` + unit tests: boundary_violations без `yaml_file` TypeError | s01 | |
| SC-004 | prose-only REPAIR не extract-success (`test_gate_repair` + optional subagent-stop semantic) | s04 | |
| SC-005 | Targeted suite green (`bin/pytest` paths) | s01, s02, s03, s04 | |
| TM-001 | Agent учит `--raw-json` | s02, s03 | |
| TM-002 | Doctor `yaml_file=` | s01 | |
| TM-003 | Prose REPAIR: soft-accept | s04 | |

---

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| Doctor boundary call-site fix + tests | plan §Этапы / gap #2 / US-002 | s01 |
| Harness SoT CLI flag fix (–raw-json → –json) | plan §Этапы / gap #1 / US-001 | s02 |
| Rematerialize materialized surfaces | plan §Этапы / FR-003 / SC-001 | s03 |
| Purge prose REPAIR: fallback из extract_repair_result | plan §Этапы / gap #3 / US-003 | s04 |

---

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Doctor `boundary_violations` возвращает честный pass/warn/skip (не exception-string TypeError) | s01 |
| rg `--raw-json` в harness + materialized surfaces → empty (CLI drift устранён) | s02, s03 |
| `extract_repair_result` refuse prose REPAIR: input (machine SoT = JSON fence only) | s04 |
| NFR-001: fail-closed — ошибки видимы, не swallowed | s01, s04 |
| Все runtime surfaces синхронны после re-materialize | s03 |

---

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `harness/agents/{gate-repair,verify-*,analyze-verify}.md` — строки `--raw-json` | I | `--json` SoT | s02 | no | |
| `harness/hooks/_lib.py` CONTRACT strings `--raw-json` | I | `--json` | s02 | no | |
| `.claude/agents/*.md` — materialized с `--raw-json` drift | A | re-materialize | s03 | no | |
| `.codex/agents/*.toml` — materialized с `--raw-json` drift | A | re-materialize | s03 | no | |
| `dsh/presets/*.prompt.md` — materialized с `--raw-json` drift | A | re-materialize | s03 | no | |
| `harness/hooks/_lib.py`: prose `REPAIR:` regex branch (^REPAIR:\s*) → synthetic dict | C | удалить; JSON fence only | s04 | yes | |
| `harness/hooks/_lib.py`: soft `except Exception: return payload` в extract_repair_result | C | re-raise или return None | s04 | yes | |
| `harness/hooks/tests/test_gate_repair.py`: `test_extract_repair_result_from_repair_line_fallback` | A | deny-test (prose → None) | s04 | no | |

## Очередь шагов

| step_id | title & files | next_phase | status |
| :--- | :--- | :--- | :--- |
| **s01** | Fix doctor boundary kwargs TypeError (call-site + tests) · [yaml](s01-doctor-boundary-kwargs-fix.yaml) | BACK IMPLEMENT | completed |
| **s02** | Fix harness SoT CLI flag: --raw-json → --json в agent/hook/preset sources · [yaml](s02-harness-sot-cli-flag-fix.yaml) | BACK IMPLEMENT | completed |
| **s03** | Rematerialize .claude/.codex/dsh surfaces после harness SoT fix · [yaml](s03-materialize-rematerialize-surfaces.yaml) | BACK IMPLEMENT | completed |
| **s04** | Purge prose REPAIR: fallback из extract_repair_result · [yaml](s04-repair-extract-prose-fallback-purge.yaml) | BACK IMPLEMENT | completed |