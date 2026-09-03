# Decompose: T-HUB-038-harness-metrics-dashboard

**Plan:** [plan/T-HUB-038-harness-metrics-dashboard/md/plan.md](../plan/T-HUB-038-harness-metrics-dashboard/md/plan.md)  
**Status canon:** [index.yaml](index.yaml)  
**Epic:** T-HUB-038 | harness-metrics-dashboard  
**Role:** BACK  
**Tracker:** index.yaml (единственный трекер шагов)

---

## Steps

| id  | Title | Status |
|-----|-------|--------|
| s01 | Dashboard collect + dashboard-report/v1 schema — aggregate metrics/incidents/episodes/events | pending |
| s02 | Self-contained HTML render — sections: Metrics, Incidents, Episodes, Events, Epic progress | pending |
| s03 | CLI dashboard-render + bin/loop alias — operator entry point with --days / --format | pending |
| s04 | Doctor halt-rate warn — optional check EPIC_DASHBOARD_HALT_WARN_RATE over 7d window | pending |
| s05 | Fixture-based tests + README §Dashboard — pytest suite + schema validation + doctor threshold | pending |

---

## Requirements coverage (plan → steps)

| Requirement | Kind | Covered by | Verify |
|---|---|---|---|
| FR-001: schema `dashboard-report/v1` — computed fields from metrics.compute_rates + event aggregates + episode summaries | FR | s01 | `rg 'dashboard-report/v1' loop/dashboard/schema.py` |
| FR-002: Module `loop/dashboard/` — `collect(cwd)`, `render_html(report)`, `render_json(report)` | FR | s01, s02 | `rg 'def collect' loop/dashboard/collect.py && rg 'def render_html' loop/dashboard/render.py` |
| FR-003: CLI `context_loop.py dashboard-render [--days 7] [--format html\|json\|both]` | FR | s03 | `rg 'dashboard-render' loop/context_loop.py` |
| FR-004: HTML self-contained minimal CSS inline; sections: Metrics, Incidents open, Episodes last 20, Events by kind, Epic progress | FR | s02 | `pytest tests/test_dashboard_render.py::test_html_structure -q` |
| FR-005: Optional `bin/loop dashboard` alias | FR | s03 | `grep -q dashboard bin/loop && echo ok` |
| FR-006: Doctor warn if halt rate > EPIC_DASHBOARD_HALT_WARN_RATE default 0.5 over 7d | FR | s04 | `pytest tests/test_dashboard_doctor.py -q` |
| FR-007: Tests: fixture runtime dir → render; schema validation; doctor warn threshold | FR | s05 | `pytest tests/test_dashboard_collect.py tests/test_dashboard_render.py tests/test_dashboard_cli.py tests/test_dashboard_doctor.py -q` |
| AC-1: dashboard-render CLI html+json | AC+ | s03 | `python loop/context_loop.py dashboard-render --help` |
| AC-2: dashboard-report/v1 schema | AC+ | s01 | `rg 'dashboard-report/v1' loop/dashboard/schema.py` |
| AC-3: Self-contained HTML | AC+ | s02 | `pytest tests/test_dashboard_render.py::test_html_no_external_cdn -q` |
| AC-4: doctor optional halt rate warn | AC+ | s04 | `pytest tests/test_dashboard_doctor.py::test_halt_rate_warn -q` |
| AC-5: README §Dashboard | AC+ | s05 | `rg '## Dashboard' README.md` |
| SC-001: HTML renders without network | AC+ | s02, s05 | `pytest tests/test_dashboard_render.py::test_html_no_external_cdn -q` (no 'https://' in rendered output) |
| SC-002: JSON schema valid | AC+ | s02, s05 | `pytest tests/test_dashboard_render.py::test_json_schema_valid -q` |
| SC-003: Rates match metrics.compute_rates | AC+ | s01, s05 | `pytest tests/test_dashboard_collect.py::test_collect_rates_match -q` |
| US-001: HTML dashboard с halt/tier0 rates | US | s01, s02, s03 | end-to-end: `pytest tests/test_dashboard_cli.py::test_cli_creates_html_file -q` |
| US-002: JSON export для scripting | US | s03 | `pytest tests/test_dashboard_cli.py -k json -q` |
| US-003: dashboard in doctor warn | US | s04 | `pytest tests/test_dashboard_doctor.py::test_halt_rate_warn -q` |
| NFR: offline/no SaaS — нет внешних зависимостей | NFR | s02 | `rg 'https://' loop/dashboard/render.py` → 0 matches (negative test) |
| NFR: operator UX — single command, no jq | NFR | s03 | `rg 'reports' loop/context_loop.py` + stdout message "Dashboard written to" |

---

## Stages coverage (plan → steps)

| Plan stage | Step(s) | Delta | Files | Verify |
|---|---|---|---|---|
| s01 collect + report schema | s01 | create loop/dashboard/{__init__.py,collect.py,schema.py} | loop/dashboard/collect.py, loop/dashboard/schema.py | pytest test_dashboard_collect.py -q |
| s02 render_html | s02 | create loop/dashboard/render.py с render_html + render_json | loop/dashboard/render.py | pytest test_dashboard_render.py -q |
| s03 CLI dashboard-render | s03 | edit loop/context_loop.py + bin/loop | loop/context_loop.py, bin/loop | pytest test_dashboard_cli.py -q |
| s04 doctor warn integration | s04 | edit loop/incidents/doctor.py (+_check_halt_rate) | loop/incidents/doctor.py | pytest test_dashboard_doctor.py -q |
| s05 tests + README | s05 | complete all test_dashboard_*.py + edit README.md | tests/test_dashboard_*.py, README.md | pytest test_dashboard_collect.py test_dashboard_render.py test_dashboard_cli.py test_dashboard_doctor.py -q + rg '## Dashboard' README.md |

---

## Outcome map (plan → steps)

| Outcome | Steps |
|---|---|
| Operator запускает `loop dashboard` и получает HTML/JSON файл без jq — единственная команда | s01, s02, s03 |
| Dashboard содержит halt/tier0 rates, открытые инциденты, последние эпизоды, события — полный снимок | s01, s02 |
| HTML работает offline (no CDN, inline CSS) — безопасен в air-gapped окружении | s02 |
| Doctor автоматически предупреждает при высоком halt rate (> 0.5 за 7d) — оператор видит сигнал без анализа | s04 |
| Полный pytest suite на fixture-данных — CI-зелёный; schema validation через pydantic | s05 |
| README §Dashboard — документированный entry point + env var | s05 |

---

## Replacement cleanup

n/a — greenfield модуль `loop/dashboard/`. Нет замены существующих модулей.  
`loop/incidents/doctor.py` расширяется (additive), не заменяется.  
`loop/context_loop.py` расширяется новым subcommand (additive).

## Очередь шагов

| step_id | title & files | next_phase | status |
| :--- | :--- | :--- | :--- |
| **s01** | Dashboard collect + dashboard-report/v1 schema — aggregate metrics/incidents/episodes/events · [yaml](s01-collect-report-schema.yaml) | BACK IMPLEMENT | completed |
| **s02** | Self-contained HTML render — sections: Metrics, Incidents, Episodes, Events, Epic progress · [yaml](s02-render-html.yaml) | BACK IMPLEMENT | completed |
| **s03** | CLI dashboard-render + bin/loop alias — operator entry point with --days / --format · [yaml](s03-cli-dashboard-render.yaml) | BACK IMPLEMENT | completed |
| **s04** | Doctor halt-rate warn — optional check EPIC_DASHBOARD_HALT_WARN_RATE over 7d window · [yaml](s04-doctor-halt-rate-warn.yaml) | BACK IMPLEMENT | completed |
| **s05** | Fixture-based tests + README §Dashboard — pytest suite + schema validation + doctor threshold · [yaml](s05-tests-readme.yaml) | BACK IMPLEMENT | completed |