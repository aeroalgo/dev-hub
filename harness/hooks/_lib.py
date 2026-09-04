#!/usr/bin/env python3
"""Shared spawn-gate state for Claude Code hooks."""
from __future__ import annotations

import json
import os
import re
import shlex
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None  # type: ignore[assignment]

_HUB_ROOT = Path(__file__).resolve().parents[2]
if str(_HUB_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUB_ROOT))

from agent_policy import AgentContext, resolve_agent_policy
from agent_registry import AGENT_ALIASES, discover_registry
from loop.workflow.resolve import full_resolve
from loop.workflow.schemas import PackResolveResult

# Known gate/search ids used by spawn-map finish text (verify/reviewer lines).
CUSTOM_OVERLAY = frozenset(
    {
        "verify",
        "verify-implement",
        "verify-bugfix",
        "verify-qa",
        "reviewer",
        "explorer",
        "sunset-inventory",
        "gate-repair",
    }
)
GATE_AGENTS = frozenset(
    {
        "verify",
        "verify-implement",
        "verify-bugfix",
        "verify-qa",
        "verify-decompose",
        "analyze-verify",
        "reviewer",
    }
)
ALLOWED = CUSTOM_OVERLAY

ALIAS: dict[str, str] = {"explore": "explorer", **AGENT_ALIASES}
ALIAS_REVERSE: dict[str, str] = {v: k for k, v in ALIAS.items()}

HARD_RULE = (
    "HARD RULE: ты subagent. НЕ запускай frontend-тесты "
    "(vitest/playwright/npm test/e2e). Отчёт parent — на русском."
)

_GATE_JSON_HARD = (
    "HARD: финальный ответ содержит fenced ```json``` блок "
    '({"schema":"loop-gate-verdict/v1","agent_id":"<id>","verdict":"PASS|FAIL|BLOCKED",'
    '"recorded_at":"<iso8601>"}). '
    "Fence language = только `json` (FORBIDDEN info-string `json loop-gate-verdict/v1`). "
    "Schema id — поле `schema` внутри JSON. "
    "Перед emit (последний Bash): "
    "`python harness/hooks/epic_resolve.py validate-boundary "
    "--schema-id loop-gate-verdict/v1 --raw-json '…'` → `valid:true`; "
    "иначе правь по diagnostic_codes и повтори. "
    "Строка VERDICT: — optional human summary, не machine input. "
    "После ≤6 Read (+ validate-boundary) — только финальный отчёт, ноль tool. "
    "Ответ без valid JSON fence = протокольный FAIL."
)

CONTRACTS = {
    "verify": (
        "CONTRACT verify: нужен AC+ · AC− · §0.11 · VERIFY · ALLOW. "
        + _GATE_JSON_HARD
        + " Не edit. Без isolation=worktree. "
        "Канон: activeContext + decompose index.yaml + implement step."
    ),
    "verify-implement": (
        "CONTRACT verify-implement: нужен AC+ · AC− · §0.11 · VERIFY · ALLOW. "
        + _GATE_JSON_HARD
        + " Не edit. Без isolation=worktree. "
        "Канон: activeContext + decompose index.yaml + implement step."
    ),
    "verify-bugfix": (
        "CONTRACT verify-bugfix: нужен AC+ · AC− · §0.11 · VERIFY · BUGFIX ARTIFACT · ALLOW. "
        + _GATE_JSON_HARD
        + " Не edit. Без isolation=worktree."
    ),
    "verify-qa": (
        "CONTRACT verify-qa: нужен Suite results · AC+ · AC− · §0.11 · ALLOW. "
        + _GATE_JSON_HARD
        + " Не pytest. Не Plan Mode / plan-файлы. Без isolation=worktree."
    ),
    "verify-decompose": (
        "CONTRACT verify-decompose: нужен Requirements coverage · Stages coverage · "
        "Outcome map · Replacement cleanup · PLAN EXCERPT · ALLOW. "
        + _GATE_JSON_HARD
        + " FORBIDDEN pytest. Без isolation=worktree."
    ),
    "reviewer": (
        "CONTRACT reviewer: нужен Suite results · AC+ · AC− · §0.11 · ALLOW. "
        + _GATE_JSON_HARD
        + " Не pytest. Не Plan Mode / plan-файлы. Без isolation=worktree."
    ),
    "explorer": (
        "CONTRACT explorer: graphify first, затем узкий Grep/rg только внутри ALLOW из prompt. "
        "Budget: ≤12 Read · ≤6 Bash · re-read >1× FORBIDDEN. "
        "FORBIDDEN: repo-wide rg/find/ls; Read/search вне ALLOW без явной ссылки in Цель/shard/plan. "
        "Не edit. Не Plan Mode — только file:line отчёт на русском. "
        "Без isolation=worktree."
    ),
    "sunset-inventory": (
        "CONTRACT sunset-inventory: только чтение и as-built инвентаризация устаревшего кода в scope/ALLOW. "
        "HARD: финальный ответ содержит fenced ```json``` блок "
        '({"schema":"loop-sunset-inventory/v1",...items...}). '
        "Fence language = только `json`; schema id внутри JSON. "
        "Перед emit: validate-boundary --schema-id loop-sunset-inventory/v1. "
        "Правила: mark=REPLACE, excerpt≤40 строк. "
        "FORBIDDEN: design/HOW предложения, dual-path, edit/write, Plan Mode. Без isolation=worktree."
    ),
    "gate-repair": (
        "CONTRACT gate-repair: нужен BLOCKERS · ALLOW WRITE · VERIFY. "
        "HARD: финальный ответ содержит fenced ```json``` блок "
        '({"schema":"loop-repair-result/v1","status":"done|partial|fail",...}). '
        "Fence language = только `json`. "
        "Перед emit: `python harness/hooks/epic_resolve.py validate-boundary "
        "--schema-id loop-repair-result/v1 --raw-json '…'` → `valid:true`. "
        "Write/Edit только ALLOW WRITE. После fix — pytest из VERIFY. "
        "FORBIDDEN: spawn Agent/verify, FINISH, finalize-step, правки вне ALLOW WRITE. "
        "Ответ без JSON fence = status fail."
    ),
}

VERDICT_FIRST_LINE = (
    "HARD: финальный ответ содержит fenced ```json``` блок "
    '({"schema":"loop-gate-verdict/v1",...}). '
    "Fence language = только `json` (FORBIDDEN `json loop-gate-verdict/v1` info-string). "
    "Перед emit: validate-boundary --schema-id loop-gate-verdict/v1 → valid:true. "
    "После ≤6 Read (+ validate-boundary) — сразу JSON fence + optional summary, без tool. "
    "VERDICT: prose — не machine input."
)

# Optional ATX heading prefix: agents often write `# AC+` / `## VERIFY`.
_HD = r"(?im)^\s*#{0,6}\s*"

_SECTION_PATTERNS: dict[str, list[tuple[str, re.Pattern[str]]]] = {
    "reviewer": [
        ("Suite results", re.compile(_HD + r"Suite results\b")),
        ("AC+", re.compile(_HD + r"AC\+\s*[:：]?")),
        ("AC−", re.compile(_HD + r"AC[−\-]\s*[:：]?")),
        ("§0.11", re.compile(_HD + r"§?\s*0\.11\s*[:：]?")),
        ("ALLOW READ", re.compile(_HD + r"ALLOW READ\s*[:：]?")),
    ],
    "verify-qa": [
        ("Suite results", re.compile(_HD + r"Suite results\b")),
        ("AC+", re.compile(_HD + r"AC\+\s*[:：]?")),
        ("AC−", re.compile(_HD + r"AC[−\-]\s*[:：]?")),
        ("§0.11", re.compile(_HD + r"§?\s*0\.11\s*[:：]?")),
        ("ALLOW READ", re.compile(_HD + r"ALLOW READ\s*[:：]?")),
    ],
    "verify": [
        ("AC+", re.compile(_HD + r"AC\+\s*[:：]?")),
        ("AC−", re.compile(_HD + r"AC[−\-]\s*[:：]?")),
        ("§0.11", re.compile(_HD + r"§?\s*0\.11\s*[:：]?")),
        ("VERIFY", re.compile(_HD + r"VERIFY\s*[:：]?")),
        ("ALLOW READ", re.compile(_HD + r"ALLOW READ\s*[:：]?")),
    ],
    "verify-implement": [
        ("AC+", re.compile(_HD + r"AC\+\s*[:：]?")),
        ("AC−", re.compile(_HD + r"AC[−\-]\s*[:：]?")),
        ("§0.11", re.compile(_HD + r"§?\s*0\.11\s*[:：]?")),
        ("VERIFY", re.compile(_HD + r"VERIFY\s*[:：]?")),
        ("ALLOW READ", re.compile(_HD + r"ALLOW READ\s*[:：]?")),
    ],
    "verify-bugfix": [
        ("AC+", re.compile(_HD + r"AC\+\s*[:：]?")),
        ("AC−", re.compile(_HD + r"AC[−\-]\s*[:：]?")),
        ("§0.11", re.compile(_HD + r"§?\s*0\.11\s*[:：]?")),
        ("VERIFY", re.compile(_HD + r"VERIFY\s*[:：]?")),
        ("BUGFIX ARTIFACT", re.compile(_HD + r"BUGFIX ARTIFACT\s*[:：]?")),
        ("ALLOW READ", re.compile(_HD + r"ALLOW READ\s*[:：]?")),
    ],
    "verify-decompose": [
        ("Requirements coverage", re.compile(_HD + r"Requirements coverage\b")),
        ("Stages coverage", re.compile(_HD + r"Stages coverage\b")),
        ("Outcome map", re.compile(_HD + r"Outcome map\b")),
        ("Replacement cleanup", re.compile(_HD + r"Replacement cleanup\b")),
        ("PLAN EXCERPT", re.compile(_HD + r"PLAN EXCERPT\s*[:：]?")),
        ("ALLOW READ", re.compile(_HD + r"ALLOW READ\s*[:：]?")),
    ],
    "gate-repair": [
        ("BLOCKERS", re.compile(_HD + r"BLOCKERS\s*[:：]?")),
        ("ALLOW WRITE", re.compile(_HD + r"ALLOW WRITE\s*[:：]?")),
        ("VERIFY", re.compile(_HD + r"VERIFY\s*[:：]?")),
    ],
}

_NEXT_SECTION = re.compile(
    _HD
    + r"(?:Suite results|AC\+|AC[−\-]|§?\s*0\.11|VERIFY|RESULT|ALLOW READ|ALLOW WRITE|BLOCKERS|"
    r"Requirements coverage|Stages coverage|Outcome map|Replacement cleanup|"
    r"PLAN EXCERPT|COVERAGE|"
    r"FORBID|CREATE/EDIT|GRAPHIFY|Цель|Цель:|Budget|Отчёт|HARD RULE|"
    r"CONTRACT|Scope:)\b"
)

# Любой project-relative файл (scope = cwd репо). Без whitelist top-level папок.
_ALLOW_PATH = re.compile(
    r"(?:^|[\s,;`])("
    r"(?!(?:/|~|\.\.(?:/|$)))"
    r"(?:\.?[\w+-]+/)*\.?[\w+-]+\.[\w.+-]+"
    r"|(?:Dockerfile|Makefile|LICENSE)"
    r")"
)

def env_bool(value: str | None, default: bool = False) -> bool:
    """Parse the project's documented boolean values."""
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off", ""}:
        return False
    return default


def workflow_policy(project_dir: str | Path | None = None) -> str:
    """Return loop/always/off; invalid values fail closed to off."""
    raw = (merged_project_env_map(project_dir).get("PROJECT_WORKFLOW_HOOKS") or "loop")
    policy = raw.strip().lower()
    return policy if policy in WORKFLOW_POLICIES else "off"


def workflow_hooks_enabled(
    project_dir: str | Path | None = None, *, role_prompt: bool = False
) -> bool:
    """Enable workflow hooks only for loop or an explicit manual role prompt."""
    policy = workflow_policy(project_dir)
    if policy == "off":
        return False
    if policy == "loop":
        return is_epic_loop_env()
    return role_prompt


def _managed_policy(
    definition: Any,
    context: AgentContext,
    project_dir: str | Path | None = None,
) -> Any:
    """Resolve a discovered definition through the shared policy contract."""
    metadata = {
        "enabled_loop": "1" if definition.loop_enabled else "0",
        "enabled_chat": "1" if definition.chat_enabled else "0",
        "model": definition.model or "inherit",
    }
    values = merged_project_env_map(project_dir)
    return resolve_agent_policy(
        definition.id,
        context,
        env={},
        project_env=values,
        metadata=metadata,
    )


def _discover_registry(project_dir: str | Path | None = None) -> Any:
    """Discover agents with project files retaining legacy file-wins semantics."""
    process_env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("PROJECT_AGENT_")
    }
    return discover_registry(project_dir, process_env=process_env)


def _managed_definition(
    norm: str | None, project_dir: str | Path | None
) -> Any | None:
    if not norm:
        return None
    definition = _discover_registry(project_dir).get(norm)
    if definition is None or not definition.managed:
        return None
    return definition


def registry_active_agents(
    context: AgentContext | str, project_dir: str | Path | None = None
) -> dict[str, str | None]:
    """Return runnable managed agents enabled for one registry context."""
    try:
        resolved_context = (
            context
            if isinstance(context, AgentContext)
            else AgentContext(str(context).strip().lower())
        )
    except ValueError:
        return {}
    active: dict[str, str | None] = {}
    for definition in _discover_registry(project_dir).definitions:
        if not definition.managed or not definition.runnable:
            continue
        policy = _managed_policy(definition, resolved_context, project_dir)
        if policy.error is None and policy.enabled:
            active[definition.id] = definition.model
    return active


def agent_enabled(norm: str | None, project_dir: str | Path | None = None) -> bool:
    """True when a managed registry agent is runnable and enabled for context."""
    definition = _managed_definition(norm, project_dir)
    if definition is None:
        return False
    context = AgentContext.LOOP if is_epic_loop_env() else AgentContext.CHAT
    policy = _managed_policy(definition, context, project_dir)
    return definition.runnable and policy.error is None and policy.enabled


def explorer_enabled(project_dir: str | Path | None = None) -> bool:
    """True when search agent explorer is active for the current context."""
    return agent_enabled("explorer", project_dir)


def explorer_loop_enabled(project_dir: str | Path | None = None) -> bool:
    """True when explorer is runnable and enabled for loop (epic next-prompt)."""
    definition = _managed_definition("explorer", project_dir)
    if definition is None or not definition.runnable:
        return False
    return bool(definition.loop_enabled)


def workflow_state_active(
    state: dict[str, Any], project_dir: str | Path | None = None
) -> bool:
    """Whether persisted spawn state may affect this process."""
    source = state.get("workflow_source")
    if source == "loop":
        return is_epic_loop_env() and workflow_policy(project_dir) == "loop"
    if source == "manual":
        return workflow_policy(project_dir) == "always"
    if not state.get("workflow_source"):
        env_root = claude_dir(project_dir)
        if not (env_root / "project.env").is_file():
            return True
    return workflow_hooks_enabled(project_dir)


def neutralize_state(state: dict[str, Any]) -> dict[str, Any]:
    """Drop gate requirements while retaining a valid runtime-state shape."""
    state.update(
        {
            "mode": None,
            "workflow_source": None,
            "need_verify": False,
            "need_reviewer": False,
            "verify_done": False,
            "reviewer_done": False,
            "verify_verdict": None,
            "reviewer_verdict": None,
            "verify_incomplete": None,
            "verify_no_verdict_retries": None,
            "verify_evidence": None,
            "reviewer_evidence": None,
            "gate_identity": None,
            "gate_diagnostic": None,
            "session_id": None,
            "epic_id": None,
            "role": None,
            "step": None,
            "projection_hash": None,
            "phase_epoch": None,
            "event_digest": None,
            "spawns": [],
            "in_flight": [],
            "spawn_denied_inflight": 0,
        }
    )
    return state


def active_overlay(project_dir: str | Path | None = None) -> frozenset[str]:
    """Enabled managed agents for the current chat or loop context."""
    context = AgentContext.LOOP if is_epic_loop_env() else AgentContext.CHAT
    return frozenset(registry_active_agents(context, project_dir))


def build_spawn_map(project_dir: str | Path | None = None) -> str:
    """Build a context-aware spawn map from active managed registry agents."""
    context = AgentContext.LOOP if is_epic_loop_env() else AgentContext.CHAT
    active_ids = registry_active_agents(context, project_dir)
    definitions = {
        definition.id: definition
        for definition in _discover_registry(project_dir).definitions
        if definition.id in active_ids
    }
    active = [definitions[agent_id] for agent_id in sorted(definitions)]
    gate_agents = [agent for agent in active if agent.mode == "gate"]
    search_agents = [agent for agent in active if agent.mode == "search"]
    repair_agents = [agent for agent in active if agent.mode == "repair"]
    optional_agents = [agent for agent in active if agent.mode == "optional"]

    overlay_agents = [
        agent_id
        for agent_id in ("explorer", "verify", "reviewer", "gate-repair")
        if agent_id in definitions
    ]
    overlay_agents.extend(
        agent.id for agent in optional_agents if agent.id not in overlay_agents
    )
    overlay = " · ".join(f"@{agent_id}" for agent_id in overlay_agents)
    if not overlay:
        overlay = "(нет managed agents)"

    search_lines: list[str] = []
    if any(agent.id == "explorer" for agent in search_agents):
        search_lines.extend(
            [
                "| Поиск «где X» | @explorer ОБЯЗАТЕЛЬНО (если нет delta_paths_exist/scoped: yes) |",
                "| delta_paths_exist: yes | @explorer SKIP — Read listed paths + shard |",
                "| delta_paths_scoped: yes | @explorer SKIP — greenfield; shard + consumes + targets |",
                "| После @explorer | только file:line из отчёта; FORBIDDEN rediscovery frontend|apps |",
            ]
        )
    elif search_agents:
        search_lines.extend(
            f"| Поиск «где X» | @{agent.id} доступен для поиска по вызову parent |"
            for agent in search_agents
        )
    else:
        search_lines.append(
            "| Поиск «где X» | graphify → узкий rg/Grep с path= сам parent "
            "(managed search agent недоступен) |"
        )

    agent_lines = [
        f"| Gate agent | @{agent.id} активен; completion требует его verdict |"
        for agent in gate_agents
        if agent.id not in GATE_AGENTS
    ]
    agent_lines.extend(
        f"| Repair agent | @{agent.id} после verify FAIL — чинит BLOCKERS in-scope |"
        for agent in repair_agents
    )
    agent_lines.extend(
        f"| Optional agent | @{agent.id} доступен по вызову parent, не блокирует completion |"
        for agent in optional_agents
    )
    return "\n".join(
        [
            "## spawn-gate (Claude Code)",
            "Делегирование — как обычно у Claude Code (Agent / built-in). Не запрещай spawn.",
            f"Overlay: {overlay} (model строго из `.claude/project.env`).",
            "| Ситуация | Agent |",
            *search_lines,
            *agent_lines,
            "| Agent running | FORBIDDEN TaskOutput mid-poll — жди completion (VERDICT / repair JSON) |",
            "| verify FAIL | @gate-repair с BLOCKERS + ALLOW WRITE + VERIFY → retry @verify; "
            "FORBIDDEN: «ожидаю verify», FINISH, новый @verify/repair пока in_flight |",
            "| Parallel spawn | DENY: второй managed пока in_flight; DENY: та же model busy |",
            "| Pre-FINISH code_changed | seed-implement → flush cp → suite → "
            "evidence (in_progress) → validate-step → Handoff → "
            "`@verify` packed → PASS → finalize-step/stop |",
            "| BACK QA после suite | @reviewer ОБЯЗАТЕЛЬНО (Suite+AC+§0.11/ALLOW ≤10) |",
            "DENY @verify: нет секций · ALLOW пуст/дерево · step нет в ALLOW · step path нет "
            "на диске · уже PASS · no-VERDICT retry исчерпан.",
            "no-VERDICT exhausted → Handoff `NEED_HUMAN: verify_no_verdict` + stop "
            "(stop-gate allow; не 3-й @verify).",
            "FAIL: @verify после VERDICT: PASS. FAIL: FINISH до PASS. "
            "FAIL: второй @verify пока предыдущий running. "
            "FAIL: parallel managed / same-model spawn.",
            "QA FINISH: qa-*.yaml (verdict) + Handoff → REFLECT обязательны.",
            "Канон: `.claude/instructions/spawn-hard.md`",
        ]
    )


def is_epic_loop_env() -> bool:
    """True only inside ./loop/loop.sh (export EPIC_LOOP=1).

    Armed epic state on disk must NOT activate EPIC MODE / fingerprint gates
    in IDE extension chats — those share .claude/settings.json hooks.
    """
    return str(os.environ.get("EPIC_LOOP", "")).lower() in {"1", "true", "yes"}


_OUTPUT_SUMMARY_ENV_LOADED = False
_PROJECT_ENV_LOADED = False

PROJECT_ENV_BASENAMES = ("project",)

AGENT_MODEL_ENV_KEYS: dict[str, str] = {
    "explorer": "PROJECT_AGENT_EXPLORER_MODEL",
    "verify": "PROJECT_AGENT_VERIFY_MODEL",
    "verify-implement": "PROJECT_AGENT_VERIFY_MODEL",
    "verify-bugfix": "PROJECT_AGENT_VERIFY_BUGFIX_MODEL",
    "verify-qa": "PROJECT_AGENT_REVIEWER_MODEL",
    "verify-decompose": "PROJECT_AGENT_VERIFY_DECOMPOSE_MODEL",
    "reviewer": "PROJECT_AGENT_REVIEWER_MODEL",
    "gate-repair": "PROJECT_AGENT_GATE_REPAIR_MODEL",
}
_AGENT_MODEL_KEY_RE = re.compile(r"^PROJECT_AGENT_[A-Z][A-Z0-9_-]*_MODEL$")
_LOOP_PHASE_MODEL_KEY_RE = re.compile(r"^PROJECT_LOOP_[A-Z][A-Z0-9_]*_MODEL$")
WORKFLOW_POLICIES = frozenset({"loop", "always", "off"})


def agent_model_env_key(norm: str | None) -> str:
    if not norm:
        return ""
    return AGENT_MODEL_ENV_KEYS.get(
        norm, f"PROJECT_AGENT_{norm.upper().replace('-', '_')}_MODEL"
    )


# Tests may load hooks repeatedly from temporary repositories. Do not retain a
# prior repository's agent-model settings across those isolated loads.
def _project_env_root(project_dir: str | Path | None = None) -> Path:
    return Path(project_dir or os.getcwd()).resolve()


def is_agent_model_file_wins_key(key: str) -> bool:
    return bool(
        _AGENT_MODEL_KEY_RE.fullmatch(key) or _LOOP_PHASE_MODEL_KEY_RE.fullmatch(key)
    )


@dataclass(frozen=True)
class RuntimeConfig:
    session_timeout_sec: int
    session_kill_grace_sec: int
    transient_retry_max: int
    degraded_max: int
    status_heartbeat_sec: int | None
    stream_idle_timeout_sec: int | None
    permission_mode: str
    sources: dict[str, str]
    epic_runtime: str = "claude"


@dataclass(frozen=True)
class WorkflowConfig:
    pack: PackResolveResult

    @classmethod
    def resolve(cls, cwd: str | Path | None = None, hub_root: str | Path | None = None) -> WorkflowConfig:
        return cls(pack=full_resolve(cwd=cwd, hub_root=hub_root))


class RuntimeConfigError(ValueError):
    def __init__(self, diagnostics: list[dict[str, str]]) -> None:
        self.diagnostics = diagnostics
        super().__init__("invalid runtime configuration")


@dataclass(frozen=True)
class RunnerOwner:
    pid: int
    host: str
    started_at: str
    session_id: str
    selected_identity: str
    mode: str
    model: str
    timeout_config: dict[str, int | None]

    def as_dict(self) -> dict[str, Any]:
        return {
            "pid": self.pid,
            "host": self.host,
            "started_at": self.started_at,
            "session_id": self.session_id,
            "selected_identity": self.selected_identity,
            "mode": self.mode,
            "model": self.model,
            "timeout_config": dict(self.timeout_config),
        }


def write_runner_owner(path: str | Path, owner: RunnerOwner) -> None:
    """Publish runner ownership through a same-directory atomic replacement."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f"{target.name}.tmp.{os.getpid()}")
    try:
        temporary.write_text(
            json.dumps(owner.as_dict(), ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, target)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def load_runner_owner(path: str | Path) -> RunnerOwner | None:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return RunnerOwner(
            pid=int(data["pid"]),
            host=str(data.get("host", "unknown")),
            started_at=str(data.get("started_at", "")),
            session_id=str(data.get("session_id", "unknown")),
            selected_identity=str(data.get("selected_identity", "unknown")),
            mode=str(data.get("mode", "unknown")),
            model=str(data.get("model", "")),
            timeout_config=dict(data.get("timeout_config", {})),
        )
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return None


def runner_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def remove_runner_owner_if_owned(path: str | Path, pid: int, session_id: str) -> bool:
    target = Path(path)
    owner = load_runner_owner(target)
    if owner is None or owner.pid != pid or owner.session_id != session_id:
        return False
    try:
        target.unlink()
    except FileNotFoundError:
        return False
    return True


def runner_owner_status(state_dir: str | Path) -> dict[str, Any]:
    root = Path(state_dir)
    owner_path = root / "runner.json"
    lock_path = root / "runner.lock"
    owner = load_runner_owner(owner_path)
    lock_age_sec = None
    try:
        lock_age_sec = max(0.0, __import__("time").time() - lock_path.stat().st_mtime)
    except OSError:
        pass
    return {
        "runner_active": bool(owner and runner_pid_alive(owner.pid)),
        "owner_alive": bool(owner and runner_pid_alive(owner.pid)),
        "lock_age_sec": lock_age_sec,
        "owner": owner.as_dict() if owner else None,
    }


_RUNTIME_CONFIG_DEFAULTS: dict[str, int | None] = {
    "EPIC_SESSION_TIMEOUT_SEC": 3600,
    "EPIC_SESSION_KILL_GRACE_SEC": 30,
    "EPIC_TRANSIENT_RETRY_MAX": 3,
    "EPIC_DEGRADED_MAX": 3,
    "EPIC_STATUS_HEARTBEAT_SEC": 30,
    "EPIC_STREAM_IDLE_TIMEOUT_SEC": 300,
}
_PERMISSION_MODE_DEFAULT = "dontAsk"
_PERMISSION_MODES = frozenset({"dontAsk", "acceptEdits", "bypassPermissions", "default", "plan"})
_RUNTIME_DEFAULT = "claude"

def _get_supported_runtimes() -> set[str] | frozenset[str] | list[str]:
    try:
        from loop.runtime.registry import list_ids
        return list_ids()
    except Exception:
        return frozenset({"claude", "dsh"})

def _runtime_config_source(key: str, project: dict[str, str]) -> tuple[str | None, str]:
    if key in os.environ:
        return os.environ[key], "process"
    if key in project:
        return project[key], "project"
    return None, "default"
_RUNTIME_CONFIG_BOUNDS: dict[str, tuple[int, int]] = {
    "EPIC_SESSION_TIMEOUT_SEC": (1, 86400),
    "EPIC_SESSION_KILL_GRACE_SEC": (1, 600),
    "EPIC_TRANSIENT_RETRY_MAX": (0, 100),
    "EPIC_DEGRADED_MAX": (1, 100),
    "EPIC_STATUS_HEARTBEAT_SEC": (1, 3600),
    "EPIC_STREAM_IDLE_TIMEOUT_SEC": (30, 86400),
}


def resolve_runtime_config(project_dir: str | Path | None = None) -> RuntimeConfig:
    """Resolve bounded runner values once, preserving the source of each value."""
    project = merged_project_env_map(project_dir)
    values: dict[str, int | str | None] = {}
    sources: dict[str, str] = {}
    diagnostics: list[dict[str, str]] = []
    for key, default in _RUNTIME_CONFIG_DEFAULTS.items():
        raw, source = _runtime_config_source(key, project)
        if raw is None:
            values[key] = default
            sources[key] = "default"
            continue
        if (
            key in {"EPIC_STATUS_HEARTBEAT_SEC", "EPIC_STREAM_IDLE_TIMEOUT_SEC"}
            and raw.strip() == ""
        ):
            values[key] = None
            sources[key] = source
            continue
        try:
            value = int(raw, 10)
        except (TypeError, ValueError):
            diagnostics.append({"code": "invalid_runtime_config", "key": key, "reason": "not_integer"})
            continue
        low, high = _RUNTIME_CONFIG_BOUNDS[key]
        if value < low or value > high:
            diagnostics.append({"code": "invalid_runtime_config", "key": key, "reason": "out_of_bounds"})
            continue
        values[key] = value
        sources[key] = source
    raw, source = _runtime_config_source("EPIC_PERMISSION_MODE", project)
    permission_mode = raw if raw else _PERMISSION_MODE_DEFAULT
    if permission_mode not in _PERMISSION_MODES:
        diagnostics.append(
            {
                "code": "invalid_runtime_config",
                "key": "EPIC_PERMISSION_MODE",
                "reason": "unsupported_permission_mode",
            }
        )
    else:
        values["EPIC_PERMISSION_MODE"] = permission_mode
        sources["EPIC_PERMISSION_MODE"] = source
    raw, source = _runtime_config_source("EPIC_RUNTIME", project)
    epic_runtime = raw if raw else _RUNTIME_DEFAULT
    if raw is None:
        source = "default"
    if epic_runtime not in _get_supported_runtimes():
        diagnostics.append(
            {
                "code": "invalid_runtime_config",
                "key": "EPIC_RUNTIME",
                "reason": "unsupported_runtime",
            }
        )
    else:
        sources["EPIC_RUNTIME"] = source
    if diagnostics:
        raise RuntimeConfigError(diagnostics)
    return RuntimeConfig(
        session_timeout_sec=values["EPIC_SESSION_TIMEOUT_SEC"],
        session_kill_grace_sec=values["EPIC_SESSION_KILL_GRACE_SEC"],
        transient_retry_max=values["EPIC_TRANSIENT_RETRY_MAX"],
        degraded_max=values["EPIC_DEGRADED_MAX"],
        status_heartbeat_sec=values["EPIC_STATUS_HEARTBEAT_SEC"],
        stream_idle_timeout_sec=values["EPIC_STREAM_IDLE_TIMEOUT_SEC"],
        permission_mode=values["EPIC_PERMISSION_MODE"],
        sources=sources,
        epic_runtime=epic_runtime,
    )


def runtime_config_status(config: RuntimeConfig) -> dict[str, Any]:
    return {
        "effective": {
            "EPIC_SESSION_TIMEOUT_SEC": config.session_timeout_sec,
            "EPIC_SESSION_KILL_GRACE_SEC": config.session_kill_grace_sec,
            "EPIC_TRANSIENT_RETRY_MAX": config.transient_retry_max,
            "EPIC_DEGRADED_MAX": config.degraded_max,
            "EPIC_STATUS_HEARTBEAT_SEC": config.status_heartbeat_sec,
            "EPIC_STREAM_IDLE_TIMEOUT_SEC": config.stream_idle_timeout_sec,
            "EPIC_PERMISSION_MODE": config.permission_mode,
            "EPIC_RUNTIME": config.epic_runtime,
        },
        "sources": dict(config.sources),
    }




def extract_json_fence(text: str) -> dict[str, Any] | None:
    if not isinstance(text, str):
        return None
    last: dict[str, Any] | None = None
    # Allow optional CommonMark info-string after `json`
    # (models sometimes emit ```json loop-gate-verdict/v1).
    for match in re.finditer(
        r"```\s*json[^\n`]*\n(.*?)\n\s*```",
        text,
        re.DOTALL | re.IGNORECASE,
    ):
        try:
            data = json.loads(match.group(1))
        except Exception:
            continue
        if isinstance(data, dict):
            last = data
    return last


def parse_gate_verdict_message(
    text: str,
    cwd: str | Path,
    agent_id: str,
    *,
    recorded_at: str,
    step_id: str | None = None,
    session_id: str | None = None,
    epic_id: str | None = None,
) -> Any | None:
    data = extract_json_fence(text)
    if not data or not isinstance(data, dict):
        return None

    try:
        from loop.gate_verdict_store import write_gate_verdict
        from loop.schemas.gate_verdict import GateVerdictRecord, SCHEMA_LOOP_GATE_VERDICT

        verdict_val = data.get("verdict")
        if not verdict_val:
            return None

        schema = str(data.get("schema") or data.get("schema_version") or "").strip()
        if schema == SCHEMA_LOOP_GATE_VERDICT:
            payload = dict(data)
            payload.setdefault("agent_id", agent_id)
            payload.setdefault("recorded_at", recorded_at)
            record = GateVerdictRecord.model_validate(payload)
            return write_gate_verdict(
                cwd,
                record.agent_id,
                record.verdict,
                step_id=record.step_id or step_id,
                session_id=record.session_id or session_id,
                epic_id=record.epic_id or epic_id,
                recorded_at=record.recorded_at or recorded_at,
                evidence_sha256=record.evidence_sha256,
            )

        rec_step = data.get("step_id") or step_id
        rec_epic = data.get("epic_id") or epic_id
        allowed_keys = {
            "verdict",
            "step_id",
            "session_id",
            "epic_id",
            "evidence_sha256",
        }
        if not set(data.keys()).issubset(allowed_keys):
            return None
        return write_gate_verdict(
            cwd,
            agent_id,
            verdict_val,
            step_id=rec_step,
            session_id=data.get("session_id") or session_id,
            epic_id=rec_epic,
            recorded_at=recorded_at,
            evidence_sha256=data.get("evidence_sha256"),
        )
    except Exception:
        return None


def hub_root() -> Path:
    env = (os.environ.get("DEV_HUB") or os.environ.get("HUB_ROOT") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    # hooks live at <hub>/harness/hooks → parents[2] = hub when file is _lib.py
    return Path(__file__).resolve().parents[2]


def product_cwd(fallback: str | Path | None = None) -> Path:
    """Resolve hook payload cwd, redirecting only the hub to PROJECT_ROOT."""
    hub = hub_root().resolve()
    proj = (os.environ.get("PROJECT_ROOT") or "").strip()
    product = Path(proj).expanduser().resolve() if proj else None
    if fallback is not None and str(fallback).strip():
        fallback_path = Path(fallback).expanduser().resolve()
        if product is not None and product != hub and fallback_path == hub:
            return product
        return fallback_path
    if product is not None and product != hub and Path.cwd().resolve() == hub:
        return product
    return Path.cwd().resolve()


# Hooks receive the target repository in their payload; use it as the source of truth.
_original_product_cwd = product_cwd


def resolve_cli_cwd(cli_cwd: str | Path | None = None) -> Path:
    """Resolve product root for epic_resolve CLI.

    When Claude session cwd is the hub but PROJECT_ROOT points at a product,
    never write memory-bank into the hub. Explicit non-hub --cwd (tests) kept.
    """
    hub = hub_root().resolve()
    proj = (os.environ.get("PROJECT_ROOT") or "").strip()
    prod = Path(proj).expanduser().resolve() if proj else None

    if cli_cwd is None or not str(cli_cwd).strip():
        if prod is not None and Path.cwd().resolve() == hub:
            return prod
        return Path.cwd().resolve()

    cwd_p = Path(str(cli_cwd)).expanduser().resolve()
    if prod is not None and prod != hub and cwd_p == hub:
        return prod
    return cwd_p


def claude_dir(project_dir: str | Path | None = None) -> Path:
    """Resolve explicit project config before the session-level tooling root."""
    if project_dir is not None:
        return Path(project_dir).expanduser().resolve() / ".claude"
    env_claude = os.environ.get("CLAUDE_PROJECT_DIR")

    if env_claude:
        p = Path(env_claude).expanduser().resolve()
        if (p / ".claude").is_dir():
            return p / ".claude"
        if p.name == ".claude" or (p / "hooks").is_dir():
            return p if p.name == ".claude" else p
        return p / ".claude"
    return hub_root() / ".claude"


def _parse_env_assignments(path: Path) -> list[tuple[str, str]]:
    if not path.is_file():
        return []
    out: list[tuple[str, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if not key:
            continue
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in {'"', "'"}:
            val = val[1:-1]
        out.append((key, val))
    return out


def project_env_files(project_dir: str | Path | None = None) -> list[Path]:
    claude = claude_dir(project_dir)
    files: list[Path] = []
    for base in PROJECT_ENV_BASENAMES:
        files.append(claude / f"{base}.env")
        files.append(claude / f"{base}.env.local")
    # optional per-product overrides: <hub>/projects/<slug>/project.env*
    slug_root: Path | None = None
    if project_dir is not None:
        slug_root = hub_root() / "projects" / Path(project_dir).resolve().name
    else:
        proj = (os.environ.get("PROJECT_ROOT") or "").strip()
        if proj:
            slug_root = hub_root() / "projects" / Path(proj).resolve().name
    if slug_root is not None:
        for base in PROJECT_ENV_BASENAMES:
            files.append(slug_root / f"{base}.env")
            files.append(slug_root / f"{base}.env.local")
    return files


def output_summary_env_files(project_dir: str | Path | None = None) -> list[Path]:
    return project_env_files(project_dir)


def merged_project_env_map(
    project_dir: str | Path | None = None,
) -> dict[str, str]:
    """Merge project.env then .local (later wins)."""
    merged: dict[str, str] = {}
    for path in project_env_files(project_dir):
        for key, val in _parse_env_assignments(path):
            merged[key] = val
    return merged


_HOOKS_LLM_DOMAINS = frozenset({"fallback", "verdict", "handoff", "abort"})


def load_hooks_llm_env(
    project_dir: str | Path | None = None,
) -> dict[str, str]:
    """Return PROJECT_HOOKS_LLM_* values (process env overrides project.env)."""
    merged = dict(merged_project_env_map(project_dir))
    out: dict[str, str] = {}
    for key, val in merged.items():
        if key.startswith("PROJECT_HOOKS_LLM_"):
            out[key] = val
    for key, val in os.environ.items():
        if key.startswith("PROJECT_HOOKS_LLM_"):
            out[key] = val
    return out


def hooks_llm_flag(
    domain: str,
    *,
    project_dir: str | Path | None = None,
) -> bool:
    """True when PROJECT_HOOKS_LLM_<DOMAIN> is enabled (1/true/yes/on)."""
    token = str(domain or "").strip().lower()
    if token not in _HOOKS_LLM_DOMAINS:
        return False
    values = load_hooks_llm_env(project_dir=project_dir)
    raw = (values.get(f"PROJECT_HOOKS_LLM_{token.upper()}") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def iter_project_env(
    project_dir: str | Path | None = None,
) -> list[tuple[str, str]]:
    """KEY=VAL from project.env*. FILE_WINS keys always from file; others only if unset."""
    applied: list[tuple[str, str]] = []
    for key, val in merged_project_env_map(project_dir).items():
        if is_agent_model_file_wins_key(key):
            applied.append((key, val))
            continue
        if key in os.environ:
            continue
        applied.append((key, val))
    return applied


def iter_output_summary_env(
    project_dir: str | Path | None = None,
) -> list[tuple[str, str]]:
    return [
        (k, v)
        for k, v in iter_project_env(project_dir)
        if k.startswith("PROJECT_OUTPUT_SUMMARY")
    ]


def load_project_env(project_dir: str | Path | None = None) -> list[str]:
    """Apply .claude/project.env* into os.environ. Returns applied keys."""
    global _PROJECT_ENV_LOADED, _OUTPUT_SUMMARY_ENV_LOADED
    keys: list[str] = []
    for key, val in iter_project_env(project_dir):
        os.environ[key] = val
        keys.append(key)
    _PROJECT_ENV_LOADED = True
    _OUTPUT_SUMMARY_ENV_LOADED = True
    return keys


def load_output_summary_env(project_dir: str | Path | None = None) -> list[str]:
    return load_project_env(project_dir)


def bash_exports_project_env(project_dir: str | Path | None = None) -> str:
    """Shell snippet: export KEY=... from .claude/project.env*."""
    lines = [
        f"export {key}={shlex.quote(val)}"
        for key, val in iter_project_env(project_dir)
    ]
    return "\n".join(lines)


def bash_exports_output_summary_env(project_dir: str | Path | None = None) -> str:
    return bash_exports_project_env(project_dir)


def agent_model_from_project_env(
    norm: str | None, project_dir: str | Path | None = None
) -> str | None:
    """Resolve a managed model from registry, else PROJECT_AGENT_<NAME>_MODEL."""
    if not norm:
        return None
    values = merged_project_env_map(project_dir)
    raw = (values.get(agent_model_env_key(norm)) or "").strip()
    if raw:
        return raw
    definition = _managed_definition(norm, project_dir)
    return definition.model if definition is not None else None


def agent_model_pin(norm: str | None, project_dir: str | Path | None = None) -> str | None:
    return agent_model_from_project_env(norm, project_dir)


TOOL_NAME_ALIASES: dict[str, str] = {
    "bash": "Bash",
    "shell": "Bash",
    "bash_20241022": "Bash",
    "bash_20250124": "Bash",
    "bash_tool": "Bash",
    "agent": "Agent",
    "task": "Task",
    "taskcreate": "TaskCreate",
    "todowrite": "TodoWrite",
    "todoread": "TodoRead",
    "read": "Read",
    "write": "Write",
    "edit": "Edit",
    "multiedit": "MultiEdit",
    "notebookedit": "NotebookEdit",
    "glob": "Glob",
    "grep": "Grep",
    "skill": "Skill",
    "webfetch": "WebFetch",
    "websearch": "WebSearch",
    "askquestion": "AskQuestion",
    "enterplanmode": "EnterPlanMode",
    "exitplanmode": "ExitPlanMode",
}

_KNOWN_CANONICAL_TOOLS: frozenset[str] = frozenset(
    set(TOOL_NAME_ALIASES.values())
    | {
        "Bash",
        "Agent",
        "Task",
        "TaskCreate",
        "TodoWrite",
        "TodoRead",
        "Read",
        "Write",
        "Edit",
        "MultiEdit",
        "NotebookEdit",
        "Glob",
        "Grep",
        "Skill",
        "WebFetch",
        "WebSearch",
        "AskQuestion",
        "EnterPlanMode",
        "ExitPlanMode",
        "EnterWorktree",
        "ExitWorktree",
        "ScheduleWakeup",
        "SendMessage",
        "TaskOutput",
        "TaskStop",
        "CronCreate",
        "CronDelete",
        "CronList",
        "Workflow",
    }
)


def normalize_tool_name(raw: str | None) -> str:
    """Normalize tool_name casing and aliases fail-closed."""
    if not raw or not str(raw).strip():
        return ""
    stripped = str(raw).strip()
    # Check exact canonical match
    if stripped in _KNOWN_CANONICAL_TOOLS:
        return stripped
    # Check alias / lowercase map
    lower = stripped.lower()
    if lower in TOOL_NAME_ALIASES:
        return TOOL_NAME_ALIASES[lower]
    # Check case-insensitive against canonical tools
    for canon in _KNOWN_CANONICAL_TOOLS:
        if canon.lower() == lower:
            return canon
    import logging
    logging.getLogger("harness.hooks").warning("unknown tool_name: %s", raw)
    return stripped


def read_stdin() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    data = json.loads(raw)
    if isinstance(data, dict) and "tool_name" in data and isinstance(data["tool_name"], str):
        data["tool_name"] = normalize_tool_name(data["tool_name"])
    return data


def emit(obj: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False))


def state_path(session_id: str, cwd: str) -> Path:
    root = product_cwd(cwd)
    hub = (os.environ.get("DEV_HUB") or os.environ.get("HUB_ROOT") or "").strip()
    hub_path = Path(hub).expanduser().resolve() if hub else None
    project = (os.environ.get("PROJECT_ROOT") or "").strip()
    project_path = Path(project).expanduser().resolve() if project else None
    use_hub_runtime = bool(
        hub_path
        and not (
            project_path == hub_path
            and root != hub_path
        )
    )
    if use_hub_runtime:
        d = hub_path / "runtime" / root.name / "spawn-gate"
    else:
        d = root / ".claude" / "runtime" / "spawn-gate"
    d.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", session_id or "nosession")[:80]
    return d / f"{safe}.json"


def load_state(session_id: str, cwd: str) -> dict[str, Any]:
    p = state_path(session_id, cwd)
    default = {
        "mode": None,
        "need_verify": False,
        "need_reviewer": False,
        "verify_done": False,
        "reviewer_done": False,
        "verify_verdict": None,
        "reviewer_verdict": None,
        "verify_evidence": None,
        "reviewer_evidence": None,
        "gate_identity": None,
        "gate_diagnostic": None,
        "session_id": None,
        "epic_id": None,
        "role": None,
        "step": None,
        "projection_hash": None,
        "phase_epoch": None,
        "event_digest": None,
        "spawns": [],
        "spawn_allowed": 0,
        "spawn_denied_scope": 0,
        "spawn_denied_config": 0,
        "spawn_denied_inflight": 0,
        "in_flight": [],
        "verdict_recorded_agents": [],
    }
    if not p.is_file():
        return dict(default)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        for k, v in default.items():
            data.setdefault(k, v)
        return data
    except Exception:
        return dict(default)


def _spawn_state_lock(path: Path):
    """Exclusive lockfile sibling for spawn-gate JSON (fcntl when available)."""
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+", encoding="utf-8")
    if fcntl is not None:
        deadline = time.monotonic() + 2.0
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                    break
                time.sleep(0.01)
    return handle


def _spawn_state_unlock(handle: Any) -> None:
    if fcntl is not None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    handle.close()


def save_state(session_id: str, cwd: str, state: dict[str, Any]) -> None:
    """Atomic write + lockfile to avoid lost-update / truncated JSON."""
    p = state_path(session_id, cwd)
    text = json.dumps(state, ensure_ascii=False, indent=2)
    lock = _spawn_state_lock(p)
    try:
        temporary = p.with_name(f"{p.name}.tmp.{os.getpid()}")
        try:
            temporary.write_text(text, encoding="utf-8")
            with temporary.open("r+") as handle:
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, p)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
    finally:
        _spawn_state_unlock(lock)


IN_FLIGHT_TTL_SEC = 1800


def resolved_spawn_model(
    tool_input: dict[str, Any],
    definition: Any | None,
) -> str:
    raw = tool_input.get("model")
    if raw not in (None, "", "inherit"):
        return str(raw)
    if definition is not None:
        model = getattr(definition, "model", None)
        if model not in (None, "", "inherit"):
            return str(model)
    return "inherit"


def prune_in_flight(
    state: dict[str, Any],
    *,
    now: datetime | None = None,
    ttl_sec: int = IN_FLIGHT_TTL_SEC,
) -> list[dict[str, Any]]:
    """Drop stale in_flight entries; mutate state; return active list."""
    now = now or datetime.now(timezone.utc)
    active: list[dict[str, Any]] = []
    for entry in state.get("in_flight") or []:
        if not isinstance(entry, dict):
            continue
        started = entry.get("started_at")
        if isinstance(started, str) and started:
            try:
                started_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                if (now - started_dt).total_seconds() > ttl_sec:
                    continue
            except ValueError:
                pass
        active.append(entry)
    state["in_flight"] = active
    return active


def in_flight_deny_reasons(
    state: dict[str, Any],
    *,
    agent: str,
    model: str,
    managed: bool,
) -> list[str]:
    """Deny parallel managed spawn and same concrete model in_flight."""
    active = prune_in_flight(state)
    if not active:
        return []
    reasons: list[str] = []
    for entry in active:
        other = str(entry.get("agent") or "?")
        other_model = str(entry.get("model") or "inherit")
        other_managed = bool(entry.get("managed"))
        if managed and other_managed:
            reasons.append(
                f"managed_in_flight: @{other} still running — "
                "дождись SubagentStop, потом spawn (не parallel managed)"
            )
        if (
            model not in (None, "", "inherit")
            and other_model == model
        ):
            reasons.append(
                f"model_in_flight: model={model} busy with @{other} — "
                "один запрос на модель; дождись completion"
            )
    # de-dupe while preserving order
    seen: set[str] = set()
    uniq: list[str] = []
    for reason in reasons:
        if reason in seen:
            continue
        seen.add(reason)
        uniq.append(reason)
    return uniq


def mark_in_flight(
    state: dict[str, Any],
    *,
    agent: str,
    model: str,
    managed: bool,
    tool_use_id: str | None = None,
) -> None:
    prune_in_flight(state)
    entry: dict[str, Any] = {
        "agent": agent,
        "model": model,
        "managed": managed,
        "started_at": utc_now(),
    }
    if tool_use_id:
        entry["tool_use_id"] = tool_use_id
    state["in_flight"] = list(state.get("in_flight") or []) + [entry]


def clear_in_flight(
    state: dict[str, Any],
    *,
    agent: str | None = None,
    tool_use_id: str | None = None,
) -> int:
    """Remove matching in_flight entries. Returns removed count."""
    active = prune_in_flight(state)
    if not active:
        return 0
    by_id = [
        e
        for e in active
        if tool_use_id and e.get("tool_use_id") == tool_use_id
    ]
    if by_id:
        drop_ids = {id(e) for e in by_id}
        state["in_flight"] = [e for e in active if id(e) not in drop_ids]
        return len(by_id)
    if not agent:
        return 0
    kept = [e for e in active if e.get("agent") != agent]
    removed = len(active) - len(kept)
    state["in_flight"] = kept
    return removed


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def gate_identity(epic: dict[str, Any], session_id: str) -> dict[str, Any]:
    projection = epic.get("projection")
    projection = projection if isinstance(projection, dict) else {}
    return {
        "session_id": session_id or None,
        "epic_id": projection.get("epic_id") or epic.get("armed_epic"),
        "role": projection.get("role") or epic.get("role"),
        "step": (
            projection.get("next_step")
            or projection.get("step")
            or epic.get("armed_step")
        ),
        "projection_hash": projection.get("projection_hash") or epic.get("projection_hash"),
        "phase_epoch": projection.get("phase_epoch") or epic.get("phase_epoch"),
        "event_digest": projection.get("event_digest") or epic.get("event_digest"),
        "authority": (
            "autonomous"
            if projection.get("projection_hash") and projection.get("phase_epoch")
            else "manual"
        ),
    }


def set_gate_identity(state: dict[str, Any], identity: dict[str, Any]) -> None:
    state["gate_identity"] = dict(identity)
    for key in (
        "session_id",
        "epic_id",
        "role",
        "step",
        "projection_hash",
        "phase_epoch",
        "event_digest",
    ):
        state[key] = identity.get(key)


def match_gate_evidence(
    evidence: object, current: dict[str, Any]
) -> tuple[bool, str]:
    """Match verify evidence to the current projection.

    Binding keys are step + projection_hash + phase_epoch (+ epic/role/digest).
    ``session_id`` is audit-only: Claude retries mint new invoke ids, and
    aborted loop sessions often clear epic ``session_id`` while PASS evidence
    remains valid for the same armed step. Requiring session equality caused
    finalize-step to fail and the loop to re-arm the same step forever.
    """
    if not isinstance(evidence, dict):
        return False, "verdict_evidence_missing"
    if evidence.get("authority") == "manual":
        return True, "manual_fallback_non_authoritative"
    required = ("step", "projection_hash", "phase_epoch")
    if any(not evidence.get(key) for key in required):
        return False, "verdict_identity_missing"
    if any(not current.get(key) for key in required):
        return False, "projection_identity_missing"
    for key in required + ("epic_id", "role", "event_digest"):
        expected = current.get(key)
        observed = evidence.get(key)
        if expected is not None and observed != expected:
            return False, "verdict_stale"
    return True, "matched"


def normalize_type(name: str | None) -> str | None:
    if not name:
        return None
    if name in ALIAS:
        return ALIAS[name]
    return name


def current_gate_identity(cwd: str, session_id: str) -> dict[str, Any]:
    """Read the runner-owned projection identity without reconstructing it.

    Prefer epic runner ``session_id`` (state, then ``EPIC_RUNNER_SESSION_ID``)
    over the Claude Code invoke id so verify evidence still matches
    ``finalize-step`` after transient Claude retries / session aborts.
    """
    try:
        from epic_lib import gate_identity as projection_identity, load_epic_state

        state = load_epic_state(cwd)
        runner_session = (
            str(state.get("session_id") or "").strip()
            or str(os.environ.get("EPIC_RUNNER_SESSION_ID") or "").strip()
            or session_id
        )
        return projection_identity(state, runner_session)
    except (ImportError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return {
            "session_id": (
                str(os.environ.get("EPIC_RUNNER_SESSION_ID") or "").strip()
                or session_id
                or None
            ),
            "authority": "manual",
        }


def verdict_evidence(
    identity: dict[str, Any],
    verdict: str,
    *,
    diagnostic: str | None = None,
) -> dict[str, Any]:
    """Create bounded, typed evidence for one gate verdict."""
    evidence = {
        "schema_version": "hook-verdict/v1",
        "verdict": str(verdict).upper(),
        "observed_at": utc_now(),
        **{key: identity.get(key) for key in (
            "session_id", "epic_id", "role", "step", "projection_hash",
            "phase_epoch", "event_digest", "authority",
        )},
    }
    if diagnostic:
        evidence["diagnostic"] = str(diagnostic)[:240]
    return evidence


def sync_gate_identity(state: dict[str, Any], identity: dict[str, Any]) -> bool:
    """Bind state to the current projection and clear old gate results on change."""
    previous = state.get("gate_identity")
    changed = isinstance(previous, dict) and any(
        previous.get(key) != identity.get(key)
        for key in ("session_id", "step", "projection_hash", "phase_epoch")
    )
    set_gate_identity(state, identity)
    if changed:
        for agent in ("verify", "reviewer"):
            state[f"{agent}_done"] = False
            state[f"{agent}_verdict"] = None
            state[f"{agent}_evidence"] = None
        state["gate_diagnostic"] = "projection_identity_changed"
    return changed


def verdict_dedupe_key(
    session_id: str,
    agent_type: str,
    *,
    tool_use_id: str | None = None,
    verdict: str | None = None,
) -> str:
    """Dedupe key for one Agent/Task completion.

    Prefer ``tool_use_id`` (one record per spawn). Fallback includes ``verdict``
    so FAIL→PASS retry in the same session is not swallowed by a coarse
    ``session:agent`` key.
    """
    sid = (session_id or "").strip() or "nosession"
    agent = (agent_type or "").strip() or "agent"
    tool = (tool_use_id or "").strip()
    if tool:
        return f"{sid}:{agent}:{tool}"
    ver = (verdict or "").strip().upper() or "NONE"
    return f"{sid}:{agent}:{ver}"


def should_skip_verdict_record(
    state: dict[str, Any],
    dedupe_key: str,
) -> bool:
    """True when this completion was already persisted under ``dedupe_key``."""
    seen = state.get("verdict_recorded_agents") or []
    return bool(dedupe_key) and dedupe_key in seen


def mark_verdict_recorded(state: dict[str, Any], dedupe_key: str) -> None:
    seen = state.setdefault("verdict_recorded_agents", [])
    if dedupe_key and dedupe_key not in seen:
        seen.append(dedupe_key)
    state["verdict_recorded_agents"] = seen[-30:]


def record_verdict(
    state: dict[str, Any],
    agent_type: str,
    verdict: str,
    evidence: dict[str, Any],
) -> tuple[bool, str]:
    """Persist a verdict only when its identity matches the current gate."""
    current = state.get("gate_identity") or {}
    matched, diagnostic = match_gate_evidence(evidence, current)
    evidence = dict(evidence)
    evidence["diagnostic"] = diagnostic
    evidence["valid"] = matched
    evidence["observed_at"] = evidence.get("observed_at") or utc_now()
    state[f"{agent_type}_evidence"] = evidence
    state["gate_diagnostic"] = diagnostic
    if matched:
        state[f"{agent_type}_done"] = True
        state[f"{agent_type}_verdict"] = evidence.get("verdict")
        if agent_type == "verify-implement":
            state["verify_done"] = True
            state["verify_verdict"] = evidence.get("verdict")
            state["verify_evidence"] = evidence
        elif agent_type == "verify-qa":
            state["reviewer_done"] = True
            state["reviewer_verdict"] = evidence.get("verdict")
            state["reviewer_evidence"] = evidence
        elif agent_type == "verify-decompose":
            state["verify_decompose_done"] = True
            state["verify_decompose_verdict"] = evidence.get("verdict")
            state["verify_decompose_evidence"] = evidence
    else:
        state[f"{agent_type}_done"] = False
        state[f"{agent_type}_verdict"] = None
        if agent_type == "verify-implement":
            state["verify_done"] = False
            state["verify_verdict"] = None
        elif agent_type == "verify-qa":
            state["reviewer_done"] = False
            state["reviewer_verdict"] = None
        elif agent_type == "verify-decompose":
            state["verify_decompose_done"] = False
            state["verify_decompose_verdict"] = None
    return matched, diagnostic


def extract_verdict(
    text: str | None,
    *,
    cwd: str | None = None,
    agent_id: str = "verify",
) -> str | None:
    """Read gate verdict from JSON fence (machine SoT), then optional sidecar."""
    if text:
        data = extract_json_fence(text)
        if isinstance(data, dict):
            schema = data.get("schema")
            if schema in (None, "loop-gate-verdict/v1"):
                verdict_val = data.get("verdict")
                if isinstance(verdict_val, str):
                    candidate = verdict_val.strip().upper()
                    if candidate in {"PASS", "FAIL", "BLOCKED"}:
                        return candidate
    if cwd:
        try:
            import sys
            from pathlib import Path

            loop_root = Path(__file__).resolve().parents[2]
            if loop_root.is_dir() and str(loop_root) not in sys.path:
                sys.path.insert(0, str(loop_root))
            from loop.gate_verdict_store import read_gate_verdict

            record = read_gate_verdict(cwd, agent_id)
            if record is not None:
                return record.verdict
        except Exception:
            pass
    return None


# compat: принимает BLOCKED и NEED_HUMAN; deprecate BLOCKED в 004 (канон = NEED_HUMAN)
BLOCKED_VERIFY_NO_VERDICT_RE = re.compile(
    r"(?i)(?:BLOCKED|NEED_HUMAN):\s*verify_no_verdict\b"
)


def verify_no_verdict_exhausted(st: dict[str, Any]) -> bool:
    return int(st.get("verify_incomplete") or 0) >= 1 and int(
        st.get("verify_no_verdict_retries") or 0
    ) >= 1


def has_blocked_verify_no_verdict(msg: str | None, cwd: str | None = None) -> bool:
    if BLOCKED_VERIFY_NO_VERDICT_RE.search(msg or ""):
        return True
    if not cwd:
        return False
    ac = Path(cwd) / "memory-bank" / "activeContext.md"
    if not ac.is_file():
        return False
    try:
        return bool(
            BLOCKED_VERIFY_NO_VERDICT_RE.search(
                ac.read_text(encoding="utf-8", errors="replace")
            )
        )
    except OSError:
        return False


def missing_contract_sections(agent: str | None, prompt: str) -> list[str]:
    if not agent or agent not in _SECTION_PATTERNS:
        return []
    missing: list[str] = []
    for label, pat in _SECTION_PATTERNS[agent]:
        if not pat.search(prompt or ""):
            missing.append(label)
    return missing


def _allow_section_body(prompt: str) -> str | None:
    m = re.search(_HD + r"ALLOW READ[ \t]*[:：]?[ \t]*(.*)$", prompt or "")
    if not m:
        m = re.search(_HD + r"ALLOW[ \t]*[:：][ \t]*(.*)$", prompt or "")
    if not m:
        return None
    start = m.end()
    first = (m.group(1) or "").strip()
    lines = [first] if first else []
    for line in (prompt or "")[start:].splitlines():
        if _NEXT_SECTION.match(line) and not re.match(
            _HD + r"ALLOW READ\b", line
        ):
            break
        lines.append(line)
    return "\n".join(lines)


ALLOW_READ_MAX = 10


def allow_read_files(prompt: str) -> list[str]:
    """Concrete file paths listed under ALLOW READ (best-effort)."""
    body = _allow_section_body(prompt)
    if body is None:
        return []
    paths: list[str] = []
    seen: set[str] = set()
    for m in _ALLOW_PATH.finditer(body):
        t = m.group(1).strip().strip("`").rstrip(",;")
        if not t or t in seen:
            continue
        seen.add(t)
        paths.append(t)
    return paths


def allow_read_violations(prompt: str) -> list[str]:
    """Return human-readable violations for ALLOW READ (≤ALLOW_READ_MAX files, no dirs)."""
    body = _allow_section_body(prompt)
    if body is None:
        return []

    paths = allow_read_files(prompt)

    viol: list[str] = []
    trees: list[str] = []
    files: list[str] = []
    for line in body.splitlines():
        candidate = line.strip().lstrip("-* ").strip("`").rstrip(",;")
        if candidate.endswith("/") or re.fullmatch(r"(?:[\\w.+-]+/)+", candidate):
            if candidate not in trees:
                trees.append(candidate)

    paths = [path for path in paths if path not in trees]

    for p in paths:
        name = Path(p.rstrip("/")).name
        is_file = (
            not p.endswith("/")
            and (
                "." in name
                or name in {"Dockerfile", "Makefile", "LICENSE"}
            )
        )
        if p.endswith("/") or not is_file:
            trees.append(p)
        else:
            files.append(p)

    if trees:
        viol.append(
            f"ALLOW READ содержит деревья/каталоги (нужны ≤{ALLOW_READ_MAX} файлов): "
            + ", ".join(trees[:8])
        )
    if len(files) > ALLOW_READ_MAX:
        viol.append(
            f"ALLOW READ: {len(files)} файлов > {ALLOW_READ_MAX} — урежь список"
        )
    if not files and not trees:
        viol.append(
            f"ALLOW READ пуст — укажи ≤{ALLOW_READ_MAX} конкретных файлов"
        )
    return viol


ALLOW_WRITE_MAX = 10


def _allow_write_section_body(prompt: str) -> str | None:
    m = re.search(_HD + r"ALLOW WRITE[ \t]*[:：]?[ \t]*(.*)$", prompt or "")
    if not m:
        return None
    start = m.end()
    first = (m.group(1) or "").strip()
    lines = [first] if first else []
    for line in (prompt or "")[start:].splitlines():
        if _NEXT_SECTION.match(line) and not re.match(
            _HD + r"ALLOW WRITE\b", line
        ):
            break
        lines.append(line)
    return "\n".join(lines)


def allow_write_files(prompt: str) -> list[str]:
    body = _allow_write_section_body(prompt)
    if body is None:
        return []
    paths: list[str] = []
    seen: set[str] = set()
    for m in _ALLOW_PATH.finditer(body):
        t = m.group(1).strip().strip("`").rstrip(",;")
        if not t or t in seen:
            continue
        seen.add(t)
        paths.append(t)
    return paths


def allow_write_violations(prompt: str) -> list[str]:
    body = _allow_write_section_body(prompt)
    if body is None:
        return ["ALLOW WRITE отсутствует — укажи ≤10 конкретных файлов для правки"]

    paths = allow_write_files(prompt)
    viol: list[str] = []
    trees: list[str] = []
    files: list[str] = []
    for line in body.splitlines():
        candidate = line.strip().lstrip("-* ").strip("`").rstrip(",;")
        if candidate.endswith("/") or re.fullmatch(r"(?:[\\w.+-]+/)+", candidate):
            if candidate not in trees:
                trees.append(candidate)

    paths = [path for path in paths if path not in trees]

    for p in paths:
        name = Path(p.rstrip("/")).name
        is_file = (
            not p.endswith("/")
            and (
                "." in name
                or name in {"Dockerfile", "Makefile", "LICENSE"}
            )
        )
        if p.endswith("/") or not is_file:
            trees.append(p)
        else:
            files.append(p)

    if trees:
        viol.append(
            f"ALLOW WRITE содержит деревья/каталоги (нужны ≤{ALLOW_WRITE_MAX} файлов): "
            + ", ".join(trees[:8])
        )
    if len(files) > ALLOW_WRITE_MAX:
        viol.append(
            f"ALLOW WRITE: {len(files)} файлов > {ALLOW_WRITE_MAX} — урежь список"
        )
    if not files and not trees:
        viol.append(
            f"ALLOW WRITE пуст — укажи ≤{ALLOW_WRITE_MAX} конкретных файлов"
        )
    return viol


_REPAIR_JSON_FENCE = re.compile(
    r"```json\s*(\{[\s\S]*?\})\s*```",
    re.MULTILINE,
)


def extract_repair_result(text: str | None) -> dict[str, Any] | None:
    if not text:
        return None
    for match in reversed(list(_REPAIR_JSON_FENCE.finditer(text))):
        raw = match.group(1)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        schema = payload.get("schema") or payload.get("schema_version")
        if schema != "loop-repair-result/v1":
            continue
        try:
            import sys
            from pathlib import Path

            loop_root = Path(__file__).resolve().parents[2]
            if loop_root.is_dir() and str(loop_root) not in sys.path:
                sys.path.insert(0, str(loop_root))
            from loop.schemas.repair_result import RepairResultRecord

            record = RepairResultRecord.model_validate(payload)
            return record.model_dump(by_alias=True)
        except Exception:
            status = str(payload.get("status") or "").lower()
            if status in {"done", "partial", "fail"}:
                return payload
    repair_match = re.search(
        r"(?m)^REPAIR:\s*(done|partial|fail)\b", text, re.I
    )
    if repair_match:
        return {
            "schema": "loop-repair-result/v1",
            "agent_id": "gate-repair",
            "status": repair_match.group(1).lower(),
            "fixed_blockers": [],
            "remaining_blockers": [],
            "recorded_at": utc_now(),
        }
    return None


def is_schema_error(codes: list[str] | None) -> bool:
    """True if any error code belongs to the schema error taxonomy (prefix schema_)."""
    if not codes:
        return False
    return any(isinstance(c, str) and c.startswith("schema_") for c in codes)


def is_semantic_error(codes: list[str] | None) -> bool:
    """True if any error code belongs to the semantic error taxonomy (prefix semantic_)."""
    if not codes:
        return False
    return any(isinstance(c, str) and c.startswith("semantic_") for c in codes)


def last_verdict_was_fail(cwd: str | Path | None = None, session_id: str | None = None) -> bool:
    """Return True if the last recorded gate verdict in spawn state or sidecar was FAIL."""
    if session_id and cwd:
        st = load_state(session_id, str(cwd))
        verdict = str(st.get("verify_verdict") or "").upper()
        if st.get("verify_done") and verdict == "FAIL":
            return True
    if cwd:
        try:
            import sys
            from pathlib import Path

            loop_root = Path(__file__).resolve().parents[2]
            if loop_root.is_dir() and str(loop_root) not in sys.path:
                sys.path.insert(0, str(loop_root))
            from loop.gate_verdict_store import read_gate_verdict

            record = read_gate_verdict(cwd, "verify")
            if record is not None and str(record.verdict).upper() == "FAIL":
                return True
        except Exception:
            pass
    return False


def _schema_retry_key(tool_use_id: str, session_id: str | None = None) -> str:
    tid = str(tool_use_id or "").strip()
    sid = str(session_id or "").strip()
    if tid and sid and not tid.startswith(f"{sid}:"):
        return f"{sid}:{tid}"
    return tid or sid or "default"


def get_schema_retry_count(
    cwd: str | Path, tool_use_id: str, session_id: str | None = None
) -> int:
    """Get same-agent schema-retry count for tool_use_id + session_id from epic state."""
    from epic.core import load_epic_state

    st = load_epic_state(cwd)
    counters = st.get("schema_retry_counts") or {}
    key = _schema_retry_key(tool_use_id, session_id)
    val = counters.get(key)
    if val is None:
        val = counters.get(tool_use_id, 0)
    return int(val)


def clear_schema_retry_count(
    cwd: str | Path, tool_use_id: str, session_id: str | None = None
) -> None:
    """Clear same-agent schema-retry count for tool_use_id + session_id in epic state."""
    from epic.core import load_epic_state, save_epic_state

    st = load_epic_state(cwd)
    counters = dict(st.get("schema_retry_counts") or {})
    key = _schema_retry_key(tool_use_id, session_id)
    counters.pop(key, None)
    counters.pop(tool_use_id, None)
    st["schema_retry_counts"] = counters
    save_epic_state(cwd, st)


def increment_schema_retry_count(
    cwd: str | Path, tool_use_id: str, session_id: str | None = None
) -> int:
    """Increment and save same-agent schema-retry count for tool_use_id + session_id in epic state."""
    from epic.core import load_epic_state, save_epic_state

    st = load_epic_state(cwd)
    counters = dict(st.get("schema_retry_counts") or {})
    key = _schema_retry_key(tool_use_id, session_id)
    prev = counters.get(key)
    if prev is None:
        prev = counters.get(tool_use_id, 0)
    count = int(prev) + 1
    counters[key] = count
    counters[tool_use_id] = count
    st["schema_retry_counts"] = counters
    save_epic_state(cwd, st)
    return count


# implement step: implement/<id>/(e|s)NN-*.yaml | leftover yaml/steps | v1 implement-<id>/
_IMPLEMENT_STEP_RE = re.compile(
    r"(memory-bank/(?:back|front|integration)/implement/"
    r"(?:implement-[^\s`/]+|[^\s`/]+(?:/yaml/steps)?)/"
    r"(?:e|s)\d{2}-[^\s`]+\.ya?ml)"
)


def implement_steps_in_prompt(prompt: str) -> list[str]:
    """Unique implement step paths mentioned in prompt (ALLOW + body)."""
    seen: set[str] = set()
    out: list[str] = []
    for m in _IMPLEMENT_STEP_RE.finditer(prompt or ""):
        p = m.group(1).strip().strip("`").rstrip(",;")
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def verify_step_path_violations(cwd: str | Path, prompt: str) -> list[str]:
    """DENY reasons: implement step must be in prompt and exist on disk."""
    steps = implement_steps_in_prompt(prompt)
    if not steps:
        return [
            "step_not_in_allow: в prompt/ALLOW READ нужен путь "
            "`memory-bank/**/implement/.../eNN|sNN-*.yaml` "
            "(сначала Write step на диск, потом @verify)"
        ]
    root = Path(cwd) if cwd else None
    if root is None:
        return []
    missing: list[str] = []
    for rel in steps:
        if not (root / rel).is_file():
            missing.append(rel)
    if missing:
        return [
            "step_missing: implement step нет на диске — "
            + ", ".join(missing)
            + ". seed-implement → validate-step → затем @verify"
        ]
    return []


def normalize_agent_tool_input(
    tool_input: dict[str, Any],
    norm: str | None,
    project_dir: str | Path | None = None,
) -> list[str]:
    """Mutate tool_input: strip worktree; model строго из project.env. Return notes."""
    notes: list[str] = []
    definition = _managed_definition(norm, project_dir)
    if definition is None:
        return notes

    iso = tool_input.get("isolation")
    if not definition.overlay.allow_worktree and iso and str(iso).lower() == "worktree":
        tool_input.pop("isolation", None)
        notes.append("stripped isolation=worktree (shared parent cwd; uncommitted diff)")

    if norm in active_overlay(project_dir):
        model = agent_model_from_project_env(norm, project_dir)
        env_key = agent_model_env_key(norm)
        if not model:
            tool_input.pop("model", None)
            notes.append(
                f"model_missing: задай {env_key} в .claude/project.env"
            )
        elif model == "inherit":
            tool_input.pop("model", None)
            notes.append("model=inherit (наследуется из родительской сессии)")
        else:
            prev = tool_input.get("model")
            tool_input["model"] = model
            if prev and str(prev) != model:
                notes.append(
                    f"model {prev!r} → {model} (строго .claude/project.env)"
                )
            else:
                notes.append(f"model={model} из .claude/project.env")

    return notes


FINISH_RE = re.compile(
    r"(?i)\b(FINISH|Handoff|step-файл|qa-\d{8}|activeContext|doc-router)\b"
)
_ROLE_RE = r"\b(?:BACK|FRONT|INTEG)\s+"
_STEP_RE = r"\b(?:s|e)\d{2}\b"
IMPL_RE = re.compile(
    rf"(?i){_ROLE_RE}IMPLEMENT\b|\bIMPLEMENT\b.*{_STEP_RE}"
)
QA_RE = re.compile(rf"(?i){_ROLE_RE}QA\b")
AUDIT_RE = re.compile(rf"(?i){_ROLE_RE}AUDIT\b")
BUGFIX_RE = re.compile(
    rf"(?i){_ROLE_RE}BUGFIX\b|\bBUGFIX\b.*{_STEP_RE}"
)

# Runner-only epic/program CLI — agent must not call these inside a session
# (loop.sh owns after/resolve). Allowed: validate-step, flush-checkpoint,
# seed-implement, mark-index-status, sync-index-yaml, status.
_RUNNER_ONLY_SUBCMDS = (
    "after",
    "resolve",
    "resolve-arm",
    "arm",
    "halt",
    "complete",
    "prepare-repair",
    "record-session",
)
_RUNNER_CLI_RE = re.compile(
    r"(?:^|[\n;|&]|\b(?:then|do)\s+|(?:&&|\|\|)\s*)"
    r"(?:(?:env|command)\s+)?"
    r"(?:python3?\s+)?"
    r"(?:(?:\./)?\.claude/hooks/)?"
    r"(?:epic|program)_resolve\.py\s+"
    r"(" + "|".join(_RUNNER_ONLY_SUBCMDS) + r")\b",
    re.IGNORECASE,
)

# Bulk rewrite of decompose index status — e13 sed marked e14–e30 completed.
_INDEX_PATH_RE = re.compile(
    r"(?i)(?:decompose[^;\n\"']*index\.(?:md|ya?ml)|index\.(?:md|ya?ml)[^;\n\"']*decompose)"
)
_INDEX_MUTATOR_RE = re.compile(
    r"(?is)(?:\bsed\b.*(?:-i|--in-place)|\bperl\b.*-i|\bcat\s*>|\btee\b)"
)
_STATE_PATH_RE = re.compile(
    r"(?i)(?:^|[\s'\"])(?:\.\.?/)?\.claude/runtime/epic/state\.json"
)


def state_projection_deny_reason(command: str | None) -> str | None:
    """Deny agent-side writes to the runner-derived epic projection."""
    if not command or not _STATE_PATH_RE.search(str(command)):
        return None
    cmd = str(command)
    if not re.search(r"(?is)(?:>|tee|sed\s+-i|perl\s+-i|mv|cp|rm|truncate)", cmd):
        return None
    return (
        "state_projection_forbidden: `.claude/runtime/epic/state.json` — "
        "runner-owned derived cache; не редактируй его вручную. "
        "Измени source artifacts, activeContext или index через canonical CLI."
    )


def index_bulk_status_deny_reason(command: str | None) -> str | None:
    """Deny sed/cat>/perl -i that rewrites decompose index.md/yaml status in bulk."""
    if not command or not str(command).strip():
        return None
    cmd = str(command)
    if not _INDEX_PATH_RE.search(cmd):
        return None
    if not _INDEX_MUTATOR_RE.search(cmd):
        return None
    if "mark-index-status" in cmd or "sync-index-yaml" in cmd:
        return None
    return (
        "index_bulk_status_forbidden: не правь decompose index.md/yaml через "
        "sed/perl -i/cat>/tee. Канон status = index.yaml; одна точка записи: "
        "`python3 .claude/hooks/epic_resolve.py mark-index-status "
        "--decompose <index|id> --step eNN --status completed` "
        "(зеркалит в index.md). Рассинхрон: repair-index-mirror. "
        "Структура: sync-index-yaml."
    )


def runner_cli_deny_reason(command: str | None) -> str | None:
    """If Bash cmd is a runner-owned epic/program_resolve subcommand, return deny reason."""
    if not command or not str(command).strip():
        return None
    projection = state_projection_deny_reason(command)
    if projection:
        return projection
    bulk = index_bulk_status_deny_reason(command)
    if bulk:
        return bulk
    m = _RUNNER_CLI_RE.search(str(command))
    if not m:
        return None
    sub = m.group(1).lower()
    return (
        f"runner_cli_forbidden: `{sub}` — legacy IPC; context-first loop "
        f"не использует epic_resolve/program_resolve {sub}. "
        "Агенту: validate-step · finalize-step · sync-index-yaml. "
        "FINISH IMPLEMENT → finalize-step (index + tasks/log + load_now); "
        "не пиши tasks.md на sNN. Следующий шаг = Handoff «Следующий»."
    )
