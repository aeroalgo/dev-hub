# Реестр шагов (Decompose index)

**Plan ID:** T-HUB-018-loop-incident-autopilot  
**План:** [plan-T-HUB-018-loop-incident-autopilot.md](../plan-T-HUB-018-loop-incident-autopilot.md)  
**Machine index:** [index.yaml](index.yaml) — **канон status**  
**Дата:** 2026-08-30  
**Режим:** BACK DECOMPOSE  
**Эпик:** T-HUB-018  
**Уровень:** L4  
**Deps:** hard T-HUB-017 (incident schema, store, events, metrics, registry, runbooks). Soft T-HUB-015 (board failed-status).

> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `index.yaml`.** Этот файл в IMPLEMENT не грузить.  
> **status SoT = `index.yaml` only.**

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность (сессия DECOMPOSE) |
| `python-testing-patterns` | TDD структура, fixture design |
| `architecture-patterns` | tier0→tier1 flow, scope guard, alert channels |
| `brainstorming` | batch decisions уже в plan (CREATIVE не нужен, опционален для board soft) |

**Per-step:** skills gate (Core + situational из `skills-gate-situational.mdc`) в каждом `sNN`; канон в shard `skills.impl`.

---

## Requirements coverage

| Requirement | sNN | Примечание |
|-------------|-----|------------|
| FR-001: eligibility check orchestration-only whitelist | s01 | |
| FR-002: prompt template + runbook injection | s02 | |
| FR-003: scope hard limit + pretool hook | s03 | |
| FR-004: loop.sh branch — spawn → re-check_after → decide | s04 | |
| FR-005: tier1_runner max_attempts (default 3) | s04 | в tier1_runner.py |
| FR-006: verify gate post-tier1 orchestration-only | s05 | |
| FR-007: alert payload loop-alert/v1; fail-closed webhook | s06 | |
| FR-008: NEED_HUMAN flag file + stderr banner | s06 | |
| FR-009: CLI subcommands incident-status + incident-retry | s07 | |
| FR-010: metrics tier1_attempts_total / resolved / escalated | s08 | |
| FR-011: soft board execution failed (feature-detect 015) | s09 | |
| US-001: автоматический tier1 для orchestration-only | s01, s02, s04, s05 | AC scenario covered s10 |
| US-002: лимит попыток tier1 → NEED_HUMAN | s04, s06 | AC scenario covered s10 |
| US-003: webhook alert при эскалации | s06 | |
| US-004: loop incident-retry для ручного повтора | s07 | |
| US-005: board failed incident (soft 015) | s09 | P2, feature-detect |
| NFR: EPIC_INCIDENT_TIER1=0 → immediate escalate | s04 | env var |
| NFR: product test failures NOT tier1 eligible | s01 | fail-closed |
| NFR: no secrets in alert payload / prompt | s02, s06 | |
| NFR: tier1 metrics via existing metrics.json rolling | s08 | |

---

## Stages coverage

| Этап канона | sNN | Заметка |
|-------------|-----|---------|
| Eligibility gate (classifier) | s01 | tier1_eligibility.yaml + is_tier1_eligible |
| Prompt build + runbook inject | s02 | tier1_prompt.py deterministic |
| Scope guard + pretool hook | s03 | scope.py + .claude/hooks/tier1-pretool-guard.py |
| loop.sh branch + spawn session | s04 | tier1_runner.py + loop.sh modification |
| Post-tier1 verify AC slice | s05 | tier1_verify.py orchestration-only |
| Escalation + alert (NEED_HUMAN + webhook) | s06 | alert.py + alert_schema.py |
| CLI (incident-status / retry) | s07 | context_loop.py subcommands |
| Observability (events.jsonl + metrics) | s08 | emit_event tier1_* + metrics.json counters |
| Docs + board soft stub | s09 | WORKFLOW.md + runbooks + board_soft.py |
| Regression suite (integration E2E) | s10 | fixtures + integration tests + polish |

---

## Outcome map

| Outcome | AC | sNN |
|---------|-----|-----|
| tier1 spawned only for orchestration-only incidents | AC+ #1 | s01, s03, s04 |
| escalation → NEED_HUMAN + alert | AC+ #2 | s06 |
| EPIC_INCIDENT_TIER1=0 → immediate escalate, no spawn | AC+ #3 (NFR) | s04 |
| product test failure → not eligible → no tier1 | AC− #3 | s01 |
| product code / git OOB write → blocked by pretool | AC− #4 | s03 |
| product tests not run in verify slice | AC− #5 | s05 |
| alert payload without secrets (no env vars/tokens) | AC− #7 | s06, s02 |
| tier1 fail max 3× → escalate, not spawn again | AC− #8 (US-002) | s04, s10 |

---

## Replacement cleanup

n/a — greenfield extension. Существующий `loop.sh` получает новую ветку (s04), но без удаления существующего кода. `.claude/hooks/` получает новый файл (s03 tier1-pretool-guard.py) без замены существующих. Shim или параллельный путь не создаётся.

---

## Очередь шагов (BACK)

| step_id | title & files | needs_creative | tdd | next_phase | status |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-tier1-eligibility-yaml.yaml](s01-tier1-eligibility-yaml.yaml) — whitelist + classifier | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-tier1-prompt-template.yaml](s02-tier1-prompt-template.yaml) — prompt + runbook inject | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-scope-pretool-guard.yaml](s03-scope-pretool-guard.yaml) — scope.py + pretool hook | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-loop-sh-incident-branch.yaml](s04-loop-sh-incident-branch.yaml) — loop.sh branch + runner | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-tier1-verify-orchestration.yaml](s05-tier1-verify-orchestration.yaml) — verify AC slice | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-alert-webhook-need-human.yaml](s06-alert-webhook-need-human.yaml) — alert.py + NEED_HUMAN | no | yes | BACK IMPLEMENT | completed |
| **s07** | [s07-cli-incident-retry-status.yaml](s07-cli-incident-retry-status.yaml) — CLI subcommands | no | yes | BACK IMPLEMENT | completed |
| **s08** | [s08-metrics-events-tier1.yaml](s08-metrics-events-tier1.yaml) — tier1 events + metrics | no | yes | BACK IMPLEMENT | completed |
| **s09** | [s09-docs-workflow-board-soft.yaml](s09-docs-workflow-board-soft.yaml) — docs + board soft | no | partial | BACK IMPLEMENT | completed |
| **s10** | [s10-regression-suite-polish.yaml](s10-regression-suite-polish.yaml) — regression E2E | no | yes | BACK IMPLEMENT | completed |
**Следующий режим:** BACK IMPLEMENT s01 (новый чат). Рекомендуется BACK ANALYZE T-HUB-018 перед первым IMPLEMENT.
