#!/usr/bin/env python3
"""Canonical, fail-closed deployment runner for all dev-hub projects.

The runner owns the invocation contract. A project supplies only a declarative
manifest and one trusted adapter entrypoint; agents do not get to invent SSH,
Docker, or deployment commands at runtime.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


HUB_ROOT = Path(__file__).resolve().parents[1]
CONFIG_ROOT = HUB_ROOT / "projects"
DEFAULT_TIMEOUT = 20
MAX_OUTPUT = 12000
SAFE_ENV = {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"}
REMOTE_PROBE = r"""set -eu
kind="$1"
shift
case "$kind" in
  target)
    hostname
    ;;
  units)
    for unit in "$@"; do
      systemctl is-active --quiet "$unit"
    done
    ;;
  containers)
    command -v docker >/dev/null 2>&1
    for container in "$@"; do
      test "$(docker inspect -f '{{.State.Running}}' "$container" 2>/dev/null)" = true
      health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container" 2>/dev/null)"
      case "$health" in healthy|none) ;; *) exit 1 ;; esac
    done
    ;;
  listeners)
    for listener in "$@"; do
      protocol="${listener%%:*}"
      port="${listener##*:}"
      case "$protocol" in
        tcp) ss -H -lnt | awk -v p=":$port" '$4 ~ p"$" {found=1} END {exit !found}' ;;
        udp) ss -H -lun | awk -v p=":$port" '$4 ~ p"$" {found=1} END {exit !found}' ;;
        *) exit 2 ;;
      esac
    done
    ;;
  tcp)
    for endpoint in "$@"; do
      host="${endpoint%:*}"
      port="${endpoint##*:}"
      timeout 8 bash -c "cat < /dev/null > /dev/tcp/$host/$port"
    done
    ;;
  *) exit 2 ;;
esac
"""


class DeployError(RuntimeError):
    pass


def fail(message: str) -> None:
    raise DeployError(message)


def trim_output(value: str) -> str:
    redacted: list[str] = []
    for line in value.splitlines():
        if re.search(r"private.?key|preshared|password|secret|token|authorization", line, re.I):
            redacted.append("[redacted deployment output]")
        else:
            redacted.append(line)
    text = "\n".join(redacted)
    return text if len(text) <= MAX_OUTPUT else text[-MAX_OUTPUT:]


def run_command(
    args: list[str],
    *,
    cwd: Path | None = None,
    input_text: str | None = None,
    env: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            cwd=cwd,
            input=input_text,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        return subprocess.CompletedProcess(args, 124, trim_output(output + "\ntimeout"))


def project_root(value: str | None) -> Path:
    root = Path(value or os.getcwd()).expanduser().resolve()
    if not root.is_dir():
        fail(f"каталог проекта не найден: {root}")
    git = run_command(["git", "-C", str(root), "rev-parse", "--show-toplevel"])
    if git.returncode != 0:
        fail(f"проект не является Git-репозиторием: {root}")
    actual = Path(git.stdout.strip()).resolve()
    if actual != root:
        fail(f"--project должен указывать на корень Git-репозитория: {actual}")
    return actual


def config_path(root: Path) -> Path:
    path = CONFIG_ROOT / root.name / "deploy.json"
    if not path.is_file():
        fail(
            f"для проекта {root.name!r} нет манифеста {path}; "
            "создайте его по harness/templates/devops-deploy.json"
        )
    return path


def load_manifest(root: Path) -> dict[str, Any]:
    path = config_path(root)
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"манифест не читается: {exc}")
    if manifest.get("schema") != "dev-hub-deploy/v1":
        fail("неподдерживаемая схема dev-hub deploy manifest")
    if manifest.get("project_id") != root.name:
        fail("project_id манифеста не совпадает с именем проекта")
    adapter = manifest.get("adapter")
    if not isinstance(adapter, dict) or adapter.get("kind") != "python":
        fail("разрешён только adapter.kind=python")
    if adapter.get("interpreter") != "python3":
        fail("разрешён только interpreter=python3")
    entrypoint = adapter.get("entrypoint")
    if not isinstance(entrypoint, str) or not entrypoint or Path(entrypoint).is_absolute():
        fail("adapter.entrypoint должен быть относительным путём")
    raw_entry = root / entrypoint
    entry = raw_entry.resolve()
    if raw_entry.is_symlink() or root not in entry.parents or not entry.is_file():
        fail("adapter.entrypoint должен быть обычным файлом внутри проекта")
    actions = adapter.get("actions", {})
    if actions != {key: key for key in ("check", "status", "apply", "rollback")}:
        fail("adapter.actions обязан точно содержать check/status/apply/rollback")
    json_actions = adapter.get("json_actions", [])
    if not isinstance(json_actions, list) or any(item not in actions for item in json_actions):
        fail("adapter.json_actions содержит неизвестную команду")
    targets = manifest.get("targets", [])
    if not isinstance(targets, list):
        fail("targets должен быть списком")
    for target in targets:
        validate_target(target)
    for endpoint in manifest.get("tcp_endpoints", []):
        validate_endpoint(endpoint, "tcp")
    for endpoint in manifest.get("http_endpoints", []):
        validate_endpoint(endpoint, "http")
    return manifest


def validate_target(target: Any) -> None:
    if not isinstance(target, dict) or not isinstance(target.get("name"), str):
        fail("каждый target обязан иметь name")
    if not isinstance(target.get("ssh_host"), str) or not target["ssh_host"]:
        fail(f"target {target.get('name')!r} не имеет ssh_host")
    address = target.get("address")
    try:
        socket.inet_aton(address)
    except (OSError, TypeError):
        fail(f"target {target.get('name')!r} имеет неверный IPv4 address")
    proxy = target.get("proxy_jump")
    if proxy is not None and (not isinstance(proxy, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", proxy)):
        fail(f"target {target.get('name')!r} имеет неверный proxy_jump")
    for unit in target.get("units", []):
        if not isinstance(unit, str) or not re.fullmatch(r"[A-Za-z0-9_.@-]+", unit):
            fail(f"target {target.get('name')!r} содержит неверное имя unit")
    for container in target.get("containers", []):
        if not isinstance(container, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", container):
            fail(f"target {target.get('name')!r} содержит неверное имя контейнера")
    for listener in target.get("listeners", []):
        if not isinstance(listener, dict) or listener.get("protocol") not in {"tcp", "udp"}:
            fail(f"target {target.get('name')!r} содержит неверный listener")
        if not isinstance(listener.get("port"), int) or not 1 <= listener["port"] <= 65535:
            fail(f"target {target.get('name')!r} содержит неверный порт")


def validate_endpoint(endpoint: Any, kind: str) -> None:
    if not isinstance(endpoint, dict) or not isinstance(endpoint.get("name"), str):
        fail(f"{kind} endpoint обязан иметь name")
    if kind == "tcp":
        if not isinstance(endpoint.get("host"), str) or not isinstance(endpoint.get("port"), int):
            fail(f"tcp endpoint {endpoint.get('name')!r} имеет неверные host/port")
        if not 1 <= endpoint["port"] <= 65535:
            fail(f"tcp endpoint {endpoint['name']!r} имеет неверный порт")
        via_target = endpoint.get("via_target")
        if via_target is not None and (not isinstance(via_target, str) or not via_target):
            fail(f"tcp endpoint {endpoint['name']!r} имеет неверный via_target")
    else:
        url = endpoint.get("url")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")) or "@" in url:
            fail(f"http endpoint {endpoint.get('name')!r} имеет неверный URL")


def safe_env() -> dict[str, str]:
    env = dict(SAFE_ENV)
    for key in ("HOME", "SSH_AUTH_SOCK", "LANG", "LC_ALL"):
        if os.environ.get(key):
            env[key] = os.environ[key]
    env["DEV_HUB"] = str(HUB_ROOT)
    return env


def ssh_args(target: dict[str, Any]) -> list[str]:
    args = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=12"]
    if target.get("proxy_jump"):
        args.extend(["-o", f"ProxyJump={target['proxy_jump']}"])
    args.append(target["ssh_host"])
    return args


def remote_probe(target: dict[str, Any], kind: str, values: list[str]) -> dict[str, Any]:
    command = ssh_args(target) + ["bash", "-s", "--", kind, *values]
    result = run_command(command, input_text=REMOTE_PROBE, env=safe_env(), timeout=30)
    return {
        "name": target["name"],
        "kind": kind,
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "evidence": trim_output(result.stdout),
    }


def declared_checks(manifest: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    targets_by_name = {target["name"]: target for target in manifest.get("targets", [])}
    for target in manifest.get("targets", []):
        ssh_config = run_command(
            ssh_args(target)[:-1] + ["-G", target["ssh_host"]],
            env=safe_env(),
            timeout=20,
        )
        configured_host = next(
            (line.split(maxsplit=1)[1] for line in ssh_config.stdout.splitlines() if line.startswith("hostname ")),
            "",
        )
        checks.append(
            {
                "id": f"ssh-address:{target['name']}",
                "ok": ssh_config.returncode == 0 and configured_host == target["address"],
                "evidence": f"configured_host={configured_host} expected={target['address']}",
            }
        )
        target_probe = remote_probe(target, "target", [])
        checks.append({"id": f"ssh-reachable:{target['name']}", **target_probe})
        for kind, values in (
            ("units", target.get("units", [])),
            ("containers", target.get("containers", [])),
            ("listeners", [f"{item['protocol']}:{item['port']}" for item in target.get("listeners", [])]),
        ):
            if values:
                probe = remote_probe(target, kind, list(values))
                checks.append({"id": f"{kind}:{target['name']}", **probe})
    for endpoint in manifest.get("tcp_endpoints", []):
        via_target = endpoint.get("via_target")
        if via_target:
            target = targets_by_name.get(via_target)
            if target is None:
                checks.append({"id": f"tcp:{endpoint['name']}", "ok": False, "evidence": "unknown via_target"})
            else:
                probe = remote_probe(target, "tcp", [f"{endpoint['host']}:{endpoint['port']}"])
                checks.append({"id": f"tcp:{endpoint['name']}", **probe})
            continue
        try:
            with socket.create_connection((endpoint["host"], endpoint["port"]), timeout=endpoint.get("timeout", 8)):
                ok = True
                evidence = "connected"
        except OSError as exc:
            ok = False
            evidence = str(exc)
        checks.append({"id": f"tcp:{endpoint['name']}", "ok": ok, "evidence": evidence})
    for endpoint in manifest.get("http_endpoints", []):
        request = urllib.request.Request(
            endpoint["url"],
            headers={"User-Agent": "dev-hub-deploy-check/1"},
        )
        try:
            with urllib.request.urlopen(request, timeout=endpoint.get("timeout", 10)) as response:
                status = response.status
            allowed = endpoint.get("statuses", [200])
            ok = status in allowed
            evidence = f"status={status} expected={allowed}"
        except (OSError, urllib.error.URLError) as exc:
            ok = False
            evidence = str(exc)
        checks.append({"id": f"http:{endpoint['name']}", "ok": ok, "evidence": evidence})
    return {"ok": all(item["ok"] for item in checks), "checks": checks}


def adapter_command(root: Path, manifest: dict[str, Any], action: str) -> list[str]:
    adapter = manifest["adapter"]
    return [adapter["interpreter"], str((root / adapter["entrypoint"]).resolve()), action]


def run_adapter(root: Path, manifest: dict[str, Any], action: str, *, timeout: int = 900) -> dict[str, Any]:
    args = adapter_command(root, manifest, action)
    report_temp: Path | None = None
    if action in manifest["adapter"].get("json_actions", []):
        handle = tempfile.NamedTemporaryFile(prefix="devhub-adapter-", suffix=".json", delete=False)
        report_temp = Path(handle.name)
        handle.close()
        args.extend(["--json", "--report", str(report_temp)])
    result = run_command(args, cwd=root, env=safe_env(), timeout=timeout)
    structured: Any = None
    if action in manifest["adapter"].get("json_actions", []):
        try:
            structured = json.loads(result.stdout)
        except json.JSONDecodeError:
            structured = None
        if report_temp:
            report_temp.unlink(missing_ok=True)
    return {
        "action": action,
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "output": trim_output(result.stdout),
        "structured": structured,
    }


def report_path(root: Path, requested: str | None) -> Path:
    path = Path(requested).expanduser() if requested else HUB_ROOT / "runtime" / root.name / "deploy" / "last-report.json"
    if not path.is_absolute():
        path = (root / path).resolve()
    else:
        path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def execute(root: Path, manifest: dict[str, Any], action: str, output_path: Path) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema": "dev-hub-deploy-report/v1",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "project": manifest["project_id"],
        "project_root": str(root),
        "action": action,
        "adapter": manifest["adapter"]["entrypoint"],
        "phases": {},
        "errors": [],
    }
    if action == "apply":
        report["phases"]["preflight_adapter"] = run_adapter(root, manifest, "check", timeout=300)
        report["phases"]["preflight_checks"] = declared_checks(manifest)
        if not report["phases"]["preflight_adapter"]["ok"] or not report["phases"]["preflight_checks"]["ok"]:
            report["errors"].append("preflight failed; apply was not started")
        else:
            report["phases"]["apply"] = run_adapter(root, manifest, "apply")
            if not report["phases"]["apply"]["ok"]:
                report["errors"].append("adapter apply failed")
            report["phases"]["postflight_adapter"] = run_adapter(root, manifest, "check", timeout=300)
            report["phases"]["postflight_checks"] = declared_checks(manifest)
    else:
        report["phases"]["adapter"] = run_adapter(root, manifest, action, timeout=300)
        report["phases"]["checks"] = declared_checks(manifest)
        if not report["phases"]["adapter"]["ok"]:
            report["errors"].append("adapter command failed")
    if action == "rollback" and report["phases"].get("adapter", {}).get("ok"):
        report["phases"]["postflight_adapter"] = run_adapter(root, manifest, "check", timeout=300)
        report["phases"]["postflight_checks"] = declared_checks(manifest)
    for phase in report["phases"].values():
        if isinstance(phase, dict) and phase.get("ok") is False:
            report["errors"].append(f"phase failed: {phase.get('action') or phase.get('id') or 'checks'}")
    report["verdict"] = "PASS" if not report["errors"] else "FAIL"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(output_path, 0o600)
    return report


def print_result(report: dict[str, Any], json_mode: bool) -> None:
    if json_mode:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print(f"project={report['project']}")
    print(f"action={report['action']}")
    print(f"report={report.get('report_path', '')}")
    print(f"verdict={report['verdict']}")
    if report["errors"]:
        for error in report["errors"]:
            print(f"ERROR: {error}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(prog="devops-deploy")
    parser.add_argument("action", choices=("check", "status", "apply", "rollback"))
    parser.add_argument("--project", default=None, help="корень проекта; по умолчанию текущий каталог")
    parser.add_argument("--report", default=None, help="путь к JSON-отчёту")
    parser.add_argument("--json", action="store_true", help="выводить только JSON")
    args = parser.parse_args()
    try:
        root = project_root(args.project)
        manifest = load_manifest(root)
        destination = report_path(root, args.report)
        report = execute(root, manifest, args.action, destination)
        report["report_path"] = str(destination)
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.chmod(destination, 0o600)
        print_result(report, args.json)
        return 0 if report["verdict"] == "PASS" else 1
    except DeployError as exc:
        if args.json:
            print(json.dumps({"schema": "dev-hub-deploy-report/v1", "verdict": "FAIL", "errors": [str(exc)]}, ensure_ascii=False))
        else:
            print(f"devops-deploy: BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
