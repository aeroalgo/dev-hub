"""Self-contained HTML and JSON rendering for DashboardReport."""

from __future__ import annotations

from html import escape
import json

from loop.dashboard.schema import DashboardReport


def render_json(report: DashboardReport) -> str:
    """Render DashboardReport to formatted JSON string."""
    return report.model_dump_json(indent=2, by_alias=True)


def render_html(report: DashboardReport) -> str:
    """Render DashboardReport to a self-contained HTML page with inline CSS."""
    # Metrics rates and counters table
    m = report.metrics
    counters_rows = "".join(
        f"<tr><td>{escape(k)}</td><td>{v}</td></tr>"
        for k, v in sorted(m.counters.items())
    )
    rates_rows = "".join(
        f"<tr><td>{escape(k)}</td><td>{v:.2%}</td></tr>"
        for k, v in sorted(m.rates.items())
    )

    metrics_section = f"""
    <h3>Counters</h3>
    <table>
      <thead><tr><th>Counter</th><th>Value</th></tr></thead>
      <tbody>{counters_rows}</tbody>
    </table>
    <h3>Rates</h3>
    <table>
      <thead><tr><th>Rate</th><th>Value</th></tr></thead>
      <tbody>{rates_rows}</tbody>
    </table>
    """

    # Open Incidents table
    if report.open_incidents:
        inc_rows_list = []
        for inc in report.open_incidents:
            inc_rows_list.append(
                f"<tr><td>{escape(inc.incident_id[:8])}</td>"
                f"<td>{escape(inc.epic_id)}</td><td>{escape(inc.step_id)}</td>"
                f"<td>{escape(inc.phase)}</td><td>{escape(inc.opened_at)}</td></tr>"
            )
        inc_table = f"""
        <table>
          <thead><tr><th>ID</th><th>Epic</th><th>Step</th><th>Phase</th><th>Opened At</th></tr></thead>
          <tbody>{''.join(inc_rows_list)}</tbody>
        </table>
        """
    else:
        inc_table = "<p>No open incidents.</p>"

    # Episodes table (up to 20)
    episodes_slice = report.last_episodes[:20]
    if episodes_slice:
        ep_rows_list = []
        for ep in episodes_slice:
            halt = escape(ep.halt_reason or "-")
            decide = escape(ep.decide or "-")
            ep_rows_list.append(
                f"<tr><td>{escape(ep.episode_id)}</td><td>{escape(ep.started_at)}</td>"
                f"<td>{escape(ep.epic_id)}</td><td>{escape(ep.role)}</td>"
                f"<td>{escape(ep.armed_step)}</td><td>{decide}</td><td>{halt}</td>"
                f"<td>{ep.incident_count}</td></tr>"
            )
        ep_table = f"""
        <table>
          <thead><tr><th>ID</th><th>Started At</th><th>Epic</th><th>Role</th><th>Step</th><th>Decide</th><th>Halt Reason</th><th>Incidents</th></tr></thead>
          <tbody>{''.join(ep_rows_list)}</tbody>
        </table>
        """
    else:
        ep_table = "<p>No episodes recorded.</p>"

    # Events by kind table
    if report.events_by_kind:
        ev_rows_list = []
        for kind, count in sorted(report.events_by_kind.items()):
            ev_rows_list.append(f"<tr><td>{escape(kind)}</td><td>{count}</td></tr>")
        ev_table = f"""
        <table>
          <thead><tr><th>Event Kind</th><th>Count</th></tr></thead>
          <tbody>{''.join(ev_rows_list)}</tbody>
        </table>
        """
    else:
        ev_table = "<p>No events recorded.</p>"

    # Epic progress table
    if report.epic_progress:
        prog_rows_list = []
        for task in report.epic_progress:
            prog_rows_list.append(
                f"<tr><td>{escape(task.epic_id)}</td><td>{escape(task.role)}</td>"
                f"<td>{escape(task.phase)}</td><td>{escape(task.step)}</td>"
                f"<td>{escape(task.title)}</td></tr>"
            )
        prog_table = f"""
        <table>
          <thead><tr><th>Epic ID</th><th>Role</th><th>Phase</th><th>Step</th><th>Title</th></tr></thead>
          <tbody>{''.join(prog_rows_list)}</tbody>
        </table>
        """
    else:
        prog_table = "<p>No active epics in tasks.md.</p>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Loop Dashboard — {escape(report.cwd)}</title>
  <style>
    body {{ font-family: monospace, sans-serif; margin: 20px; max-width: 1200px; color: #222; background: #fff; }}
    h1, h2, h3 {{ border-bottom: 1px solid #ccc; padding-bottom: 4px; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
    th, td {{ border: 1px solid #ddd; padding: 6px 10px; text-align: left; }}
    th {{ background: #f4f4f4; }}
    .meta {{ font-size: 0.9em; color: #555; margin-bottom: 20px; }}
  </style>
</head>
<body>
  <h1>Loop Dashboard</h1>
  <div class="meta">
    <strong>CWD:</strong> {escape(report.cwd)} |
    <strong>Generated At:</strong> {escape(report.generated_at)} |
    <strong>Window:</strong> {report.days_window} days
  </div>

  <h2>Metrics</h2>
  {metrics_section}

  <h2>Open Incidents ({len(report.open_incidents)})</h2>
  {inc_table}

  <h2>Last Episodes ({len(episodes_slice)})</h2>
  {ep_table}

  <h2>Events by Kind</h2>
  {ev_table}

  <h2>Epic Progress ({len(report.epic_progress)})</h2>
  {prog_table}
</body>
</html>
"""
