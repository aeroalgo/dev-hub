# Реестр шагов (Decompose index)

**Plan ID:** T-HUB-017-loop-observability-foundation  
**План:** [plan/T-HUB-017-loop-observability-foundation/md/plan.md](../plan/T-HUB-017-loop-observability-foundation/md/plan.md)  
**Machine index:** [index.yaml](index.yaml) — **канон status**  
**Дата:** 2026-08-30  
**Режим:** BACK DECOMPOSE  
**Эпик:** T-HUB-017  
**Уровень:** L3  
**Deps:** нет hard; soft T-HUB-014 (board_sync_stale в doctor)

> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `index.yaml`.** Этот файл в IMPLEMENT не грузить.  
> **status SoT = `index.yaml` only.**

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность (сессия DECOMPOSE) |
| `brainstorming` | batch decisions уже в plan (CREATIVE не нужен) |

**Per-step:** skills gate (Core + situational из `skills-gate-situational.mdc`) в каждом `sNN`; канон в shard `skills.impl`.

---

## Requirements coverage (plan → steps)

| Req ID | Кратко | sNN | Notes |
| :--- | :--- | :--- | :--- |
| AC+ #1 | loop-incident/v1 round-trip | s01 | |
| AC+ #2 | tier0 mark_index_missing → resolved | s02 | integration s03 |
| AC+ #3 | unknown code → no repair | s02 | |
| AC+ #4 | metrics increment + rolling prune | s05 | |
| AC+ #5 | trace append + tail in status | s04, s06 | |
| AC+ #6 | doctor stale_owner + exit codes | s07 | |
| AC+ #7 | check_after wires tier0 before halt | s03 | |
| AC+ #8 | repair_applied in events.jsonl | s08 | |
| AC+ #9 | loop README observability | s09 | |
| AC+ #10 | regression test_decide_after_action, test_status_* | s03, s06 | |
| AC− #1 | не spawn agent sessions | — | out_of_scope → T-HUB-018 |
| AC− #2 | не webhooks/Telegram | — | out_of_scope → T-HUB-018 |
| AC− #3 | не чинить product pytest | — | out_of_scope all sNN |
| AC− #4 | не edit loop/*.py из registry dynamically | s02 | |
| AC− #5 | не требовать DSH/board для ship | s07 | optional check only |
| AC− #6 | fail-closed corrupt incidents | s01, s06, s07 | |
| AC− #7 | не дублировать repair logic | s02 | epic.core wrappers only |
| FR-001 | schema loop-incident/v1 | s01 | |
| FR-002 | store append/resolve/list | s01 | |
| FR-003 | registry.yaml 7 codes | s02 | |
| FR-004 | tier0.py runner | s02 | |
| FR-005 | wire tier0 in check_after | s03 | |
| FR-006 | trace.py + loop.sh | s04 | |
| FR-007 | metrics.py counters | s05 | |
| FR-008 | status incidents/metrics/trace_tail | s06 | |
| FR-009 | doctor CLI | s07 | |
| FR-010 | event emission | s08 | |
| FR-011 | runbooks + registry links | s09 | |
| FR-012 | EPIC_INCIDENT_TRACE/METRICS env | s04, s05 | |
| FR-013 | idempotency fingerprint+session | s01 | |
| FR-014 | loop README + incidents README | s09 | |
| US-001 | open incidents visible | s01, s06 | |
| US-002 | auto tier0 desync repair | s02, s03 | |
| US-003 | session trace chain | s04 | |
| US-004 | loop doctor preflight | s07 | |
| US-005 | repair success rate metrics | s05, s06 | |
| US-006 | repair events in events.jsonl | s08 | |
| SC-001 | registry ≥6 codes | s02 | |
| SC-002 | desync auto-continue | s03 | |
| SC-003 | status no prompt leak | s06 | |
| SC-004 | doctor stale_owner | s07 | |
| SC-005 | trace per loop iteration | s04 | |
| SC-006 | repair_applied event | s08 | |

---

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| Incident schema + JSONL store | plan §Модули schema.py, store.py | s01 |
| Tier-0 registry + runner | plan §Registry, tier0.py | s02 |
| check_after integration (dual-path inline + tier0) | plan §Tier-0 integration | s03 |
| Session trace writer + shell hooks | plan §Session trace, loop.sh | s04 |
| Rolling metrics counters | plan §Metrics schema | s05 |
| status() payload extensions | plan FR-008 | s06 |
| Doctor preflight CLI | plan §Doctor checks | s07 |
| Epic event emission (build_event) | plan FR-010, epic_events.py | s08 |
| Runbooks + operational docs | plan FR-011, FR-014 | s09 |
| Package layout loop/incidents/ | plan §Модули | s01 (init), s02–s08 |
| Test fixtures incidents/** | plan §loop/tests/fixtures | s01, s02, s07 |
| Test suite test_incidents_* | plan §loop/tests | s01–s08 |

---

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Orchestration-инциденты видимы без stdout (incident log) | s01, s06 |
| Known desync auto-repair Tier-0 до эскалации человеку | s02, s03 |
| Session lifecycle trace prepare→decide для stall debug | s04, s06 |
| Измеримый autopilot (success rate, auto-continue) | s05, s06 |
| Preflight doctor перед автозапуском | s07 |
| Lifecycle projection в epic events.jsonl | s08 |
| Операционная документация + runbooks для Tier-1 (018) | s09 |
| Out of scope: agent spawn, webhooks, product pytest fix | — → T-HUB-018 |
| Out of scope: legacy inline repair dedup (optional) | — → follow-up после 017 ship |

---

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind (A\|B\|C) | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| n/a — нет замен | — | — | — | — | greenfield extension; inline repairs в check_after остаются (dual-path per plan) |

---

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-incident-schema-store.yaml](s01-incident-schema-store.yaml) — schema + store | [s01…](../../implement/T-HUB-017-loop-observability-foundation/s01-incident-schema-store.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-registry-yaml-tier0.yaml](s02-registry-yaml-tier0.yaml) — registry + tier0 | [s02…](../../implement/T-HUB-017-loop-observability-foundation/s02-registry-yaml-tier0.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-check-after-wire-tier0.yaml](s03-check-after-wire-tier0.yaml) — check_after wire | [s03…](../../implement/T-HUB-017-loop-observability-foundation/s03-check-after-wire-tier0.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-session-trace-jsonl.yaml](s04-session-trace-jsonl.yaml) — trace + loop.sh | [s04…](../../implement/T-HUB-017-loop-observability-foundation/s04-session-trace-jsonl.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-metrics-rolling.yaml](s05-metrics-rolling.yaml) — metrics.json | [s05…](../../implement/T-HUB-017-loop-observability-foundation/s05-metrics-rolling.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-status-incidents-metrics.yaml](s06-status-incidents-metrics.yaml) — status payload | [s06…](../../implement/T-HUB-017-loop-observability-foundation/s06-status-incidents-metrics.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s07** | [s07-doctor-cli-preflight.yaml](s07-doctor-cli-preflight.yaml) — doctor CLI | [s07…](../../implement/T-HUB-017-loop-observability-foundation/s07-doctor-cli-preflight.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s08** | [s08-event-emission-repair.yaml](s08-event-emission-repair.yaml) — events.jsonl | [s08…](../../implement/T-HUB-017-loop-observability-foundation/s08-event-emission-repair.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s09** | [s09-runbooks-docs-readme.yaml](s09-runbooks-docs-readme.yaml) — docs only | [s09…](../../implement/T-HUB-017-loop-observability-foundation/s09-runbooks-docs-readme.yaml) | no | no | BACK IMPLEMENT | completed |
**Следующий режим:** BACK IMPLEMENT s01 (новый чат). Рекомендуется BACK ANALYZE T-HUB-017 перед первым IMPLEMENT.
