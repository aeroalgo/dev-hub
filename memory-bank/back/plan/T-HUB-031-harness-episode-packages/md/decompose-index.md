# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-031-harness-episode-packages  
**План:** [plan/T-HUB-031-harness-episode-packages/md/plan.md](../plan/T-HUB-031-harness-episode-packages/md/plan.md)  
**Machine index:** [index.yaml](index.yaml) — **канон status**  
**Дата:** 2026-08-31  
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml`.

> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `index.yaml`.** Этот файл в IMPLEMENT не грузить.
> **status SoT = `index.yaml` only.** `index.md` status — best-effort зеркало.

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность |
| `python-testing-patterns` | TDD, pytest patterns |
| `python-type-safety` | Pydantic schema design |

**Per-step:** Core (tdd · python-testing-patterns · modern-python · python-anti-patterns) + situational по таблице allowlist.

## Requirements coverage (plan → steps)

> **HARD:** каждый AC+ / AC− / FR / NFR → ≥1 шаг, иначе явный out_of_scope.

| Req ID | Кратко | sNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | EpisodeManifest schema fields | s01 | episode_id, started_at, fingerprint_before/after и др. |
| FR-002 | loop/episodes/ module API: begin/finalize/episode_dir | s01 | публичный API |
| FR-003 | prepare_session calls begin_episode; check_after calls finalize | s02 | wire в context_loop.py |
| FR-004 | Bundle artifact copies (check_after.json, checkpoint, gate_verdict, trace_tail) | s03 | immutable copies |
| FR-005 | append_trace includes episode_id field | s04 | backward-compat keyword-only |
| FR-006 | Incidents store episode_id in metadata | s04 | metadata dict flexible |
| FR-007 | CLI episode-list [--last N] + episode-show <id> | s05 | argparse subcommands |
| FR-008 | prune_episodes + EPIC_EPISODE_RETENTION_DAYS | s06 | retention policy |
| FR-009 | Tests: manifest schema, finalize on continue/halt, episode_id correlation, retention prune | s01–s06 | distributed по шардам |
| AC-1 | loop-episode/v1 schema + pydantic model | s01 | |
| AC-2 | begin/finalize wired in prepare/check_after | s02, s03 | s03 добавляет artifacts |
| AC-3 | episode_id in trace + incidents | s04 | |
| AC-4 | episode-list / episode-show CLI | s05 | |
| AC-5 | Retention documented + prune function tested | s06 | |
| AC-6 | README § Episodes | s06 | |
| US-001 | Episode folder contains full context after halt | s01–s03 | manifest + artifacts |
| US-002 | episode_id correlates incident ↔ session | s04 | |
| US-003 | pytest log / gate_verdict in bundle | s03 | gate_verdict.json copy |
| US-004 | Retention policy prunes old dirs | s06 | |
| SC-001 | Episode created every loop iteration | s02, s06 | wire + canary test |
| SC-002 | manifest validates against pydantic schema | s01, s06 | unit + canary |
| SC-003 | incident carries episode_id | s04, s06 | unit + canary |
| SC-004 | episode-list CLI works | s05, s06 | unit + canary |
| NFR: no secrets | No secrets in bundle (EPIC_EPISODE_INCLUDE_PROMPT guard) | s03 | env guard |
| NFR: bundle size bounded | Trace tail = last N lines; no full chat log by default | s03 | |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| Schema + module skeleton | plan §Техника / FR-001, FR-002 | s01 |
| Lifecycle wire (prepare → begin, check_after → finalize) | plan §FR-003, AC-2 | s02 |
| Artifact copy into bundle | plan §FR-004, §Bundle structure | s03 |
| Correlation: trace + incidents | plan §FR-005, FR-006, AC-3 | s04 |
| CLI operator inspection | plan §FR-007, AC-4 | s05 |
| Retention + tests + README | plan §FR-008, FR-009, AC-5, AC-6 | s06 |

## Outcome map (plan → steps)

> **HARD:** не ужимать Goal/NFR до infra-slug. Каждый критичный outcome → sNN.

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| После каждой итерации в `runtime/<slug>/episodes/<episode_id>/` — versioned bundle с детерминированным manifest | s01, s02, s03 |
| Operator после halt открывает episode folder и видит полный контекст без raw chat log | s01, s03, s05 |
| Auditor correlates incident ↔ session через episode_id в incidents.jsonl и trace | s04 |
| Developer воспроизводит gate failure через gate_verdict.json в bundle | s03 |
| Disk не растёт бесконечно — retention policy с EPIC_EPISODE_RETENTION_DAYS | s06 |
| Episode ID sortable (UTC prefix) — diff между runs и postmortem хронология | s01 |
| Manifest pydantic schema validates — SC-002 | s01, s06 |
| CLI episode-list / episode-show — SC-004 | s05 |
| No secrets в bundle (EPIC_EPISODE_INCLUDE_PROMPT guard) | s03 |
| README §Episodes — operator onboarding | s06 |

## Replacement cleanup (plan → steps)

> Greenfield — нет замен.

| Устаревает | Kind | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| n/a — нет замен | — | — | — | — | greenfield additive (plan §Replacement/sunset: n/a) |

## Очередь шагов (BACK)

| step_id | title & файл | needs_creative | tdd | next_phase | status |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-episode-schema-model.yaml](s01-episode-schema-model.yaml) — EpisodeManifest schema + loop/episodes module skeleton | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-wire-prepare-check-after.yaml](s02-wire-prepare-check-after.yaml) — Wire begin_episode/finalize_episode into lifecycle | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-artifact-copies-bundle.yaml](s03-artifact-copies-bundle.yaml) — Artifact copies into episode bundle | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-incident-trace-correlation.yaml](s04-incident-trace-correlation.yaml) — episode_id propagation trace + incidents | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-cli-episode-list-show.yaml](s05-cli-episode-list-show.yaml) — CLI episode-list + episode-show | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-retention-prune-tests-readme.yaml](s06-retention-prune-tests-readme.yaml) — Retention prune + integration tests + README | no | yes | BACK IMPLEMENT | completed |
**needs_creative:** все `no` — архитектура greenfield additive, нет неразрешённых design decisions.
