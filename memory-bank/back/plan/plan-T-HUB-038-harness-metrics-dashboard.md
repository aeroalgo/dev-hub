# [T-HUB-038 | harness-metrics-dashboard] PLAN

**Дата:** 2026-08-31  
**Режим:** BACK PLAN  
**Уровень:** L2–L3  
**Статус:** active  
**Roadmap:** [roadmap-harness-maturity-borrowings-epics.md](roadmap-harness-maturity-borrowings-epics.md)  
**Queue:** [roadmap-harness-maturity-borrowings-epics.queue.yaml](roadmap-harness-maturity-borrowings-epics.queue.yaml)  
**Deps:** **hard** T-HUB-031 (episode packages for rich dashboard data).

**Skills:** writing-plans · python-testing-patterns · architecture-patterns

→ [decompose-T-HUB-038-harness-metrics-dashboard/index.md](decompose-T-HUB-038-harness-metrics-dashboard/index.md) — **после DECOMPOSE**

---

## Контекст

- **req:** Local-first **observability dashboard**: aggregate `metrics.json`, `events.jsonl`, `incidents.jsonl`, episode summaries into static HTML + JSON report — no SaaS required.
- **gap:** `loop status` JSON only; operator must jq manually; no trend view (tier0 success rate, halt rate, sessions per sNN).
- **refs:** T-HUB-017 metrics; T-HUB-031 episodes; chat P2-15.

**CREATIVE need:** нет.

---

## Цель

CLI **`dashboard-render`** produces `runtime/<slug>/reports/dashboard-<date>.html` + sibling `.json` with computed rates, open incidents, last N episodes, event timeline chart (simple tables, no external JS CDN required).

---

## Продуктовая spека (WHAT)

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как operator после week autopilot, я хочу HTML dashboard, чтобы видеть halt/tier0 rates. | P0 | render → html contains metrics tables |
| US-002 | Как operator, я хочу JSON export для scripting. | P0 | `--format json` valid schema |
| US-003 | Как developer, я хочу dashboard in doctor warn if halt rate high. | P1 | doctor optional check |

### Functional Requirements (FR-###)

- **FR-001:** Schema `dashboard-report/v1` — computed fields from `loop/incidents/metrics.compute_rates` + event aggregates + episode summaries.
- **FR-002:** Module `loop/dashboard/` — `collect(cwd)`, `render_html(report)`, `render_json(report)`.
- **FR-003:** CLI `context_loop.py dashboard-render [--days 7] [--format html|json|both]`.
- **FR-004:** HTML: self-contained minimal CSS inline; sections: Metrics, Incidents open, Episodes last 20, Events by kind, Epic progress from tasks.md active rows.
- **FR-005:** Optional `bin/loop dashboard` alias.
- **FR-006:** Doctor warn if `check_after_halt / sessions_total > EPIC_DASHBOARD_HALT_WARN_RATE` default 0.5 over 7d window.
- **FR-007:** Tests: fixture runtime dir → render; schema validation; doctor warn threshold.

### Success Criteria

| SC-001 | HTML renders without network | pytest html parse |
| SC-002 | JSON schema valid | pydantic |
| SC-003 | Rates match metrics.compute_rates | pytest |

---

## AC

1. dashboard-render CLI html+json.
2. dashboard-report/v1 schema.
3. Self-contained HTML.
4. doctor optional halt rate warn.
5. README § Dashboard.

---

## До DECOMPOSE

| sNN | Slice |
|-----|-------|
| s01 | collect + report schema |
| s02 | render_html |
| s03 | CLI dashboard-render |
| s04 | doctor warn integration |
| s05 | tests + README |

---

## Следующий режим

→ BACK DECOMPOSE
