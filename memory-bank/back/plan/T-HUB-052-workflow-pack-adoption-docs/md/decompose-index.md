# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-052-workflow-pack-adoption-docs  
**План:** [plan.md](plan.md)  
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**  
**Дата:** 2026-09-05  
**Режим:** BACK DECOMPOSE

> **Path (layout v2 HARD):** этот файл = `plan/T-HUB-052-workflow-pack-adoption-docs/md/decompose-index.md`. Machine = `yaml/decompose-index.yaml`. Shards = `yaml/steps/`.

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность |
| `modern-python` | doctor/loader реализация |
| `python-testing-patterns` | pytest fixtures |
| `architecture-patterns` | intent routing schema |

---

## Requirements coverage (plan → steps)

| Req ID | Plan FR text (verbatim) | sNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | `loop/workflow/intent_routing.yaml` — maps intent types → default pack + phase chain templates | s01 | |
| FR-002 | Extend `workflow-idea-pipeline.mdc` intent table with `video_production`, `content_factory` rows referencing pack ids | s07 | |
| FR-003 | Doctor subcommand `doctor workflow-pack [--cwd]` — checks: resolve ok, phase_registry exists, rules_root exists, mb_root writable | s02 | |
| FR-004 | `docs/runbooks/workflow-pack-authoring.md` — step-by-step from template | s04 | |
| FR-005 | `docs/runbooks/workflow-pack-operator.md` — env vars, loop flags, troubleshooting | s03 | |
| FR-006 | hub-link extension `--pack <id>` (046 integration or standalone patch markers) | s06 | |
| FR-007 | `loop/context_loop.py` — `--workflow-pack` CLI flag sets env for session (document parity with WORKFLOW_PACK) | s05 | |
| FR-008 | AGENTS.md + CLAUDE.md section «Workflow Packs» with concise table | s07 | |
| FR-009 | pytest doctor workflow-pack matrix (ok pack, missing rules, invalid pack) | s08 | |
| FR-010 | Update roadmap-harness-universal-runtime §2 table with Workflow Pack layer row | s08 | |
| AC+ #1 | doctor workflow-pack operational with ≥4 checks | s02 | |
| AC+ #2 | intent_routing.yaml loaded by IDEA PIPELINE workflow doc reference | s01, s07 | |
| AC+ #3 | Operator runbook + author runbook committed | s03, s04 | |
| AC+ #4 | hub-link --pack documented (implement or defer — prefer implement P1) | s06 | implement P1 |
| AC+ #5 | pytest doctor pack matrix green | s08 | |
| US-001 | missing pack → non-zero + diagnostic | s02 | |
| US-002 | IDEA PIPELINE video intent → video pack chain | s07 | |
| US-003 | runbook steps match template 051 | s04 | |
| US-004 | alongside mode copies .cursor/rules/video | s06 | |
| US-005 | context_loop --help shows flag | s05 | |
| SC-001 | doctor workflow-pack green on dev-hub default | s02, s08 | |
| SC-002 | doctor fails on invalid pack | s02, s08 | |
| SC-003 | IDEA intent video maps to pack | s01 | |
| SC-004 | Runbook paths exist and link from README | s03, s04 | |
| TM-001 | doctor default ok → exit 0 | s02, s08 | |
| TM-002 | doctor invalid pack → exit 1 | s02, s08 | |
| TM-003 | intent load → pytest intent → PASS | s01 | |
| TM-004 | hub-link pack dry-run → ok | s06 | |
| TM-005 | loop --workflow-pack → pytest → PASS | s05 | |
| AC− #1 | IDEA PIPELINE prose-only pack routing — FORBIDDEN | s07 | deletes prose rows |
| AC− #2 | Doctor warnings-only on invalid pack — FORBIDDEN | s02 | fail-closed |
| AC− #3 | Duplicate pack docs without single runbook SoT — FORBIDDEN | s03, s04 | single SoT each |

---

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| intent→pack machine table | plan §FR-001 + Technology axiom | s01 |
| doctor preflight checks (≥4) | plan §FR-003 + Failure matrix TM-001..TM-004 | s02 |
| operator runbook (env/flags/troubleshooting) | plan §FR-005 + US-001 | s03 |
| author runbook (scaffold in 30 min) | plan §FR-004 + US-003 | s04 |
| --workflow-pack CLI flag | plan §FR-007 + US-005 | s05 |
| hub-link --pack alongside install | plan §FR-006 + US-004 | s06 |
| AGENTS/CLAUDE/idea-pipeline docs | plan §FR-002 + §FR-008 | s07 |
| pytest full matrix + roadmap row | plan §FR-009 + §FR-010 + SC-001..SC-004 | s08 |

---

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Framework without adoption path = dead code → operator can adopt pack in <30 min | s03, s04 (runbooks) |
| IDEA PIPELINE routes video intent to video pack (not prose-only) | s01 (yaml table), s07 (doc reference) |
| Doctor preflight catches missing pack before loop start (fail-closed, not warnings) | s02 |
| loop --workflow-pack flag: parity with env var, documented in --help | s05 |
| hub-link alongside install covers pack rules tree | s06 |
| Living docs: doctor encodes checks = docs don't rot | s02 (diagnostic codes), s03 (troubleshooting by code) |
| pytest matrix green on default dev-hub pack | s08 |
| Roadmap universal-runtime §2 updated with Workflow Pack layer | s08 |

---

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| Prose-only IDEA video routing sentences in workflow-idea-pipeline.mdc | I | video_production row in Матрица table + intent_routing.yaml ref | s07 | no | rg audit cp3 |
| n/a — всё остальное greenfield | — | — | — | — | новые файлы без замены |

---

## Очередь шагов (BACK)

| step_id | title & files | needs_creative | tdd | next_phase | status |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-intent-routing-yaml.yaml](../yaml/steps/s01-intent-routing-yaml.yaml) — intent_routing.yaml + loader | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-doctor-workflow-pack.yaml](../yaml/steps/s02-doctor-workflow-pack.yaml) — doctor checks | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-operator-runbook.yaml](../yaml/steps/s03-operator-runbook.yaml) — operator runbook | no | no | BACK IMPLEMENT | completed |
| **s04** | [s04-author-runbook.yaml](../yaml/steps/s04-author-runbook.yaml) — author runbook | no | no | BACK IMPLEMENT | completed |
| **s05** | [s05-context-loop-workflow-pack-flag.yaml](../yaml/steps/s05-context-loop-workflow-pack-flag.yaml) — --workflow-pack flag | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-hub-link-pack-flag.yaml](../yaml/steps/s06-hub-link-pack-flag.yaml) — hub-link --pack | no | no | BACK IMPLEMENT | completed |
| **s07** | [s07-agents-claude-idea-pipeline-docs.yaml](../yaml/steps/s07-agents-claude-idea-pipeline-docs.yaml) — AGENTS/CLAUDE/idea-pipeline | no | no | BACK IMPLEMENT | completed |
| **s08** | [s08-pytest-roadmap-update.yaml](../yaml/steps/s08-pytest-roadmap-update.yaml) — pytest matrix + roadmap | no | yes | BACK IMPLEMENT | completed |