# Реестр шагов — T-HUB-045 | harness-workflow-session-load-api
**Plan ID:** T-HUB-045-harness-workflow-session-load-api  
**План:** [plan/T-HUB-045-harness-workflow-session-load-api/md/plan.md](../plan/T-HUB-045-harness-workflow-session-load-api/md/plan.md)  
**Machine index:** [index.yaml](index.yaml) — **канон status**  
**Дата:** 2026-09-02  
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml`.

> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `index.yaml`.** Этот файл в IMPLEMENT не грузить.
> **status SoT = `index.yaml` only.**

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность |
| `python-testing-patterns` | TDD matrix |
| `python-type-safety` | Pydantic v2 schemas |

---

## Requirements coverage (plan → steps)

| Req ID | Кратко | sNN | Notes |
| :--- | :--- | :--- | :--- |
| US-001 | parent IMPLEMENT — один CLI-вызов | s01, s02 | s01 core + s02 CLI |
| US-002 | fail-closed при invalid shape | s01 | TM-002 pytest |
| US-003 | denylist forbidden paths | s01, s03 | policy в session.py + resolver |
| US-004 | QA/BUGFIX mode bundle | s03 | mode matrix resolver |
| US-005 | plan_section jump | s04 | load_plan_section |
| US-006 | session-start inject EPIC_LOOP | s05 | fingerprint в additionalContext |
| US-007 | MCP load_session parity | s07 | P2 |
| US-008 | fingerprint stable | s01 | TM-006 pytest |
| FR-011 | Hub vs product cwd guard | s02 | CLI path guard |
| FR-012 | pytest matrix IMPLEMENT/QA/BUGFIX/shape_invalid/forbidden/plan_section | s01 | test_mb_load_session.py |
| SC-001 | Session start без prose «прочитай load_now» в workflow-implement | s06 | rg check cp1 |
| SC-002 | 0 false loads of full plan in IMPLEMENT matrix | s01 | pytest forbidden policy |
| SC-003 | Bundle fingerprint stable | s01 | pytest same cwd twice |
| SC-004 | session-start inject when EPIC_LOOP | s05 | pytest session_start |
| AC+ US-001 | ok:true, files ≥2, fingerprint non-empty | s01 cp2 | |
| AC+ US-002 | ok:false, diagnostic_codes non-empty | s01 cp3 | |
| AC+ US-003 | forbidden_skipped[], not in files[] | s01 cp4 / s03 cp2 | |
| FR-001 | mb-load-request/v1, mb-load-result/v1 schemas | s01 | |
| FR-002 | load_session(cwd, plan_section) | s01 | |
| FR-003 | forbidden policy engine | s01, s03 | |
| FR-004 | CLI epic_resolve.py mb-load session | s02 | |
| FR-005 | response fields meta/handoff/files/fingerprint/forbidden_skipped/diagnostic_codes | s01 | |
| FR-006 | load_plan_section(cwd, section) | s04 | |
| FR-007 | mode matrix auto-resolve implement yaml | s03 | |
| FR-008 | session_start_payload EPIC_LOOP inject | s05 | |
| FR-009 | workflow rules purge prose START | s06 | |
| FR-010 | (P2) MCP thin wrapper | s07 | |
| NFR-001 | per-file size cap (default 512 KiB) | s01 | session.py size cap |
| NFR-002 | fingerprint deterministic | s01 | TM-006 |
| NFR-003 | fail-closed misconfig (bad cwd, missing activeContext) | s02 | CLI exit 2 |
| NFR-004 | no import of mb_finish phase handlers (read-only shared schemas) | s01 | regression note |
| AC− silent-skip shape errors | fail-closed mb-load | s01 | verify TM-002 |
| AC− silent full plan IMPLEMENT | skip with diagnostic | s01, s03 | FR-003 |
| AC− partial bundle misconfig | JSON error, not partial | s02 | FR-004 cwd guard |
| TM-001 | happy path load_session | s01 cp2, s02 cp2 | |
| TM-002 | shape invalid → fail | s01 cp3 | |
| TM-003 | forbidden full plan IMPLEMENT | s01 cp4 / s03 | |
| TM-004 | QA mode bundle | s03 cp2 | |
| TM-005 | plan_section extract | s04 cp1 | |
| TM-006 | fingerprint stable | s01 cp1 (basis) | |
| TM-007 | session-start inject EPIC_LOOP | s05 cp1 | |
| TM-008 | implement yaml auto-resolve | s03 cp1 | |
| TM-009 | MCP parity CLI | s07 cp1 | |

---

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| Core package + schemas | plan §FR-001, FR-002 | s01 |
| Session load + forbidden policy | plan §FR-002, FR-003, NFR | s01 |
| CLI subcommand + cwd guard | plan §FR-004 | s02 |
| Mode matrix resolver | plan §FR-007 | s03 |
| plan_section extractor | plan §FR-006 | s04 |
| session-start hook extension | plan §FR-008, US-006 | s05 |
| workflow rules purge | plan §FR-009, §Replacement A+B+C | s06 |
| MCP thin wrapper (P2) | plan §FR-010 | s07 |
| Legacy purge + sunset_inventory_scan | plan §Replacement cleanup + §Technology axiom | s08 |

---

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Агент вместо 3–6 ручных Read вызывает один mb-load session → JSON bundle | s01, s02 |
| Fail-closed при bitом activeContext — агент не работает на invalid cursor | s01 (shape validate) |
| Forbidden path policy — агент не тянет done или полный plan в IMPLEMENT | s01, s03 |
| Mode matrix: IMPLEMENT/QA/BUGFIX/DECOMPOSE получают правильный bundle | s03 |
| plan_section jump — агент загружает только нужный §N плана | s04 |
| Loop runner (EPIC_LOOP=1) — first turn warm без дополнительных вызовов | s05 |
| Prose «читай load_now вручную» исчезает из workflow rules → LLM следует API | s06, s08 |
| MCP parity — Cursor user получает тот же JSON через MCP tool | s07 |
| Fingerprint bundle для аудита / stop-gate / episode package | s01 (fingerprint field) |
| Нет silent load full plan в IMPLEMENT — fail-closed или skip с diagnostic | s01 (NFR), s03 |
| Misconfig bad cwd / missing activeContext → JSON error, не partial bundle | s02 |
| Out of scope: episode package wire (T-HUB-031) | — / follow-up epic |
| Out of scope: subagent auto-inject | — / beyond FR |
| Out of scope: analyze-convergence detect «session without mb-load» | — / T-HUB-032 |

---

## Replacement cleanup (plan → steps)

> Brownfield replace: 3 строки sunset (A+B+C) из plan §Replacement / sunset.

| Устаревает (path / symbol) | Kind | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| Prose-only session start в .mdc rules | A | `mb-load session` one-liner | s06, s08 | no | delete in-epic |
| Manual Read load_now chain (context_loop.py prompts) | A | mb-load bundle | s06, s08 | no | delete in-epic; fallback mb_paths_for_prompt остаётся |
| «если неясно — прочитай весь plan» prose | C | `load_plan_section N` + дейнилист | s06, s08 | no | delete in-epic |

**Финальный purge:** s08-legacy-purge-manual-read-instructions — sunset_inventory_scan по .cursor/rules/ + loop/ + harness/ + rg grep_control на все 3 строки.

---

## Очередь шагов (BACK)

| step_id | title & файл | needs_creative | tdd | next_phase | status |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-mb-load-schemas-core.yaml](s01-mb-load-schemas-core.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-mb-load-cli-cwd-guard.yaml](s02-mb-load-cli-cwd-guard.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-mb-load-resolver-mode-matrix.yaml](s03-mb-load-resolver-mode-matrix.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-load-plan-section.yaml](s04-load-plan-section.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-session-start-inject-epic-loop.yaml](s05-session-start-inject-epic-loop.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-rules-purge-prose-start.yaml](s06-rules-purge-prose-start.yaml) | no | no | BACK IMPLEMENT | completed |
| **s07** | [s07-mcp-wrapper-parity.yaml](s07-mcp-wrapper-parity.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s08** | [s08-legacy-purge-manual-read-instructions.yaml](s08-legacy-purge-manual-read-instructions.yaml) | no | no | BACK IMPLEMENT | completed |
**needs_creative:** `no` для всех шагов — CREATIVE need: нет (подтверждено в plan).
