#!/usr/bin/env python3
"""Context-first loop — activeContext is the cursor; runner only spins sessions.

Канон переходов и next mode: memory-bank/activeContext.md + decompose index.
Next mode/step — решение модели по context, не отдельный FSM-парсер runner.
Если load_now/shape парсятся плохо — всё равно стартуем сессию: агент сам
читает activeContext + decompose index и выбирает шаг (и чинит activeContext).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]  # hub root (DEV_HUB)
HUB_ROOT = ROOT
HOOKS = HUB_ROOT / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))
LOOP_DIR = HUB_ROOT / "loop"
if str(LOOP_DIR) not in sys.path:
    sys.path.insert(0, str(LOOP_DIR))

from _lib import (  # noqa: E402
    explorer_loop_enabled,
    is_epic_loop_env,
    merged_project_env_map,
    resolve_runtime_config,
    runner_owner_status,
    runtime_config_status,
    workflow_policy,
)
from agent_policy import AgentContext, resolve_agent_policy  # noqa: E402
from agent_registry import discover_registry  # noqa: E402
from epic import (  # noqa: E402
    arm_active_context_from_decompose,
    arm_epic,
    checkpoint_lifecycle,
    checkpoint_resume,
    clear_reserved_role_arm,
    clear_runner_checkpoint,
    complete_archived_armed_epic,
    epic_complete_allowed,
    extract_handoff_block,
    extract_load_now,
    handoff_post_implement_phase,
    fingerprint_context,
    load_checkpoint,
    load_decompose_steps_fail_closed,
    load_epic_state,
    read_active_context,
    rebuild_epic_projection,
    repair_index_mirror,
    repair_fingerprint_stall,
    sync_cursor_from_index,
    save_epic_state,
    validate_active_context_shape,
    reconcile_current_epic_events,
    resolve_armed_decompose_for_integrity,
    validate_finish_integrity,
    validate_finish_integrity_with_repair,
    verify_pass_step_blockers,
    gates_from_phase,
    discover_epic_for_pipeline,
    post_implement_phase,
    _event_log_path,
    utc_now,
)
from loop.episodes import begin_episode, finalize_episode
from session_resilience import (  # noqa: E402
    analyze_session_log,
    classify_abort,
    dirty_resume_prompt_lines,
    git_dirty_paths,
    load_last_session,
    transient_backoff_sec,
    write_last_session,
)

RUNTIME_REL = Path("epic")
PROMPT_NAME = "next-prompt.txt"

# Phase → Claude --model override from .claude/project.env (file wins).
# Absent override → CLI MODEL from loop.sh. Alias or OmniRoute id OK.
LOOP_PHASE_MODEL_ENV: dict[str, str] = {
    "DECOMPOSE": "PROJECT_LOOP_DECOMPOSE_MODEL",
    "PLAN": "PROJECT_LOOP_PLAN_MODEL",
    "CLARIFY": "PROJECT_LOOP_CLARIFY_MODEL",
    "ANALYZE": "PROJECT_LOOP_ANALYZE_MODEL",
    "CREATIVE": "PROJECT_LOOP_CREATIVE_MODEL",
    "IMPLEMENT": "PROJECT_LOOP_IMPLEMENT_MODEL",
    "AUDIT": "PROJECT_LOOP_AUDIT_MODEL",
    "QA": "PROJECT_LOOP_QA_MODEL",
    "BUGFIX": "PROJECT_LOOP_BUGFIX_MODEL",
    "REFLECT": "PROJECT_LOOP_REFLECT_MODEL",
}
_LOOP_PHASE_DETECT_ORDER = (
    "DECOMPOSE",
    "CLARIFY",
    "ANALYZE",
    "CREATIVE",
    "IMPLEMENT",
    "BUGFIX",
    "AUDIT",
    "QA",
    "REFLECT",
    "PLAN",
)


def loop_phase_key(
    phase: str | None, armed_step: str | None = None
) -> str | None:
    """Normalize armed_step / projection.phase → LOOP_PHASE_MODEL_ENV key."""
    ph = str(phase or "").strip().upper()
    # Terminal DONE must win over stale armed_step (AUDIT/QA/REFLECT left after REFLECT).
    if ph == "DONE" or re.search(r"\bDONE\b", ph):
        return None
    step = str(armed_step or "").strip().upper()
    if step in LOOP_PHASE_MODEL_ENV:
        return step
    if not ph:
        return None
    for key in _LOOP_PHASE_DETECT_ORDER:
        if re.search(rf"\b{re.escape(key)}\b", ph):
            return key
    return None


def resolve_loop_phase_model(
    *,
    phase: str | None,
    armed_step: str | None = None,
    cli_model: str | None = None,
    project_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Pick --model for this session: PROJECT_LOOP_<PHASE>_MODEL > CLI > None."""
    key = loop_phase_key(phase, armed_step)
    env_name = LOOP_PHASE_MODEL_ENV.get(key) if key else None
    override = ""
    if env_name:
        # Prefer live os.environ (loop.sh already exported project.env);
        # fall back to merged file map for direct prepare() calls.
        override = (os.environ.get(env_name) or "").strip()
        if not override:
            override = (merged_project_env_map(project_dir).get(env_name) or "").strip()
    if override:
        return {
            "model": override,
            "loop_phase": key,
            "model_source": "phase_env",
            "model_env": env_name,
        }
    cli = (cli_model or "").strip() or None
    if cli:
        return {
            "model": cli,
            "loop_phase": key,
            "model_source": "cli",
            "model_env": env_name,
        }
    return {
        "model": None,
        "loop_phase": key,
        "model_source": "default",
        "model_env": env_name,
    }


def hub_root() -> Path:
    env = (os.environ.get("DEV_HUB") or os.environ.get("HUB_ROOT") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return HUB_ROOT


def runtime_dir(cwd: str | Path) -> Path:
    slug = Path(cwd).resolve().name
    d = hub_root() / "runtime" / slug / RUNTIME_REL
    d.mkdir(parents=True, exist_ok=True)
    return d


def prompt_path(cwd: str | Path) -> Path:
    return runtime_dir(cwd) / PROMPT_NAME


# GAPS is NOT a stop marker: agents misuse `**GAPS:**` for deferred sNN/eNN scope notes.
# Human halt = BLOCKED: | NEED_HUMAN: only (+ EPIC_DONE standalone / labeled Стоп).
STOP_LINE_RE = re.compile(
    r"(?m)^\s*(?:[-*]\s*)?(?:\*\*)?(EPIC_DONE|BLOCKED|NEED_HUMAN)(?:\*\*)?\s*:"
)
STOP_EPIC_DONE_RE = re.compile(
    r"(?m)^\s*(?:[-*]\s*)?(?:\*\*)?`?EPIC_DONE`?(?:\*\*)?\s*$"
)
# Agents often write `- **Стоп:** `EPIC_DONE`.` (bold label includes colon).
STOP_EPIC_DONE_LABELED_RE = re.compile(
    r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?(?:Стоп|Stop|Статус|Status)(?::\*\*|\*\*:|:)\s*"
    r"(?:\*\*)?`?EPIC_DONE`?(?:\*\*)?\s*\.?\s*$"
)


def detect_stop_marker(text: str) -> str | None:
    handoff = extract_handoff_block(text) or text
    if STOP_EPIC_DONE_RE.search(handoff):
        return "EPIC_DONE"
    if STOP_EPIC_DONE_LABELED_RE.search(handoff):
        return "EPIC_DONE"
    m = STOP_LINE_RE.search(handoff)
    if m:
        kind = m.group(1).upper()
        line = m.group(0).strip()
        return f"{kind}: {line}" if kind != "EPIC_DONE" else "EPIC_DONE"
    return None


def handoff_indicates_epic_finished(text: str) -> bool:
    """True when Handoff already closed the epic (labeled/bare EPIC_DONE or ARCHIVE NOW)."""
    if detect_stop_marker(text) == "EPIC_DONE":
        return True
    handoff = extract_handoff_block(text) or ""
    if not handoff:
        return False
    heading = handoff.splitlines()[0] if handoff.splitlines() else ""
    # Only ARCHIVE NOW heading — not REFLECT template line «ARCHIVE: вручную после EPIC_DONE».
    return bool(re.search(r"(?i)\bARCHIVE\s+NOW\b", heading))


def handoff_indicates_epic_archived(text: str) -> bool:
    """True when Handoff reports ARCHIVE NOW completed (body or heading)."""
    handoff = extract_handoff_block(text) or ""
    if not handoff:
        return False
    if re.search(
        r"(?i)(?:BACK|FRONT|INTEG)\s+ARCHIVE\s+NOW|ARCHIVE\s+NOW\s+(?:completed|заверш)",
        handoff,
    ):
        return True
    if re.search(r"(?i)ЗАВЕРШЕНА\s+И\s+АРХИВИРОВАНА", handoff):
        return True
    return False


def _is_tier0_eligible(diagnostic_code: str, registry_path: str | Path | None = None) -> bool:
    """Check if diagnostic code has a registered Tier-0 repair chain in registry.yaml."""
    from loop.incidents.registry import get_chain

    chain = get_chain(diagnostic_code, registry_path=registry_path)
    return bool(chain)


def _epic_done_stop_result(cwd: str | Path) -> dict[str, Any]:
    """Complete only when QA+REFLECT exist; otherwise halt (never silent DONE)."""
    gate = epic_complete_allowed(cwd)
    if gate.get("allowed"):
        return {
            "ok": False,
            "complete": True,
            "reason": "EPIC_DONE",
            "stop": "EPIC_DONE",
        }
    return {
        "ok": False,
        "complete": False,
        "halt": True,
        "reject_epic_done": True,
        "phase": gate.get("phase"),
        "reason": gate.get("reason")
        or "EPIC_DONE запрещён: нет AUDIT/QA pass и/или REFLECT",
    }


def mb_paths_for_prompt(cwd: str | Path, load_now: list[str]) -> list[str]:
    root = Path(cwd).resolve()
    out = [str(root / "memory-bank" / "activeContext.md")]
    seen = {out[0]}
    for raw in load_now:
        p = raw.strip()
        if not p.startswith("memory-bank/"):
            if p.startswith(("back/", "front/", "integration/")):
                p = f"memory-bank/{p}"
            else:
                continue
        abs_path = str((root / p).resolve())
        if abs_path in seen:
            continue
        rel = root / p
        if rel.is_file() or rel.is_dir():
            out.append(abs_path)
            seen.add(abs_path)
    return out


def discover_decompose_indexes(cwd: str | Path, *, limit: int = 5) -> list[str]:
    """Best-effort hint paths when load_now empty — not a next-step parser."""
    root = Path(cwd) / "memory-bank"
    if not root.is_dir():
        return []
    found: list[str] = []
    for p in sorted(root.glob("**/plan/decompose-*/index.md")):
        rel = p.relative_to(cwd).as_posix()
        found.append(rel)
        if len(found) >= limit:
            break
    return found


_WORK_SHARD_RE = re.compile(
    r"memory-bank/.+/(?:plan/decompose-|implement/implement-)[^/]+/"
    r"(?:e|s)\d{2}-[^/\s`]+\.ya?ml$"
)
_SCOPED_PATH_PREFIXES = (
    "frontend/",
    "apps/",
    "tests/",
    "dsh/",
    "loop/",
    ".claude/",
    "scripts/",
    "bin/",
)
_CODE_PATH_RE = re.compile(
    r"(?:^|[\s\"'`])"
    r"((?:frontend|apps|tests|dsh|loop|\.claude)/[A-Za-z0-9_./-]+\."
    r"(?:ts|tsx|js|jsx|py|json|ya?ml|md|sh))"
)
_BARE_FILE_RE = re.compile(r"`([A-Za-z0-9_-]+\.(?:ts|tsx|js|jsx|py))`")
_FILES_BLOCK_RE = re.compile(r"(?ms)^files:\s*\n((?:[ \t]*-[ \t]*.+\n)*)")
_CONTEXT_LIST_RE = re.compile(
    r"(?ms)^[ \t]*(?:consumes|produces):\s*\n((?:[ \t]*-[ \t]*.+\n)*)"
)
_DELTA_LINE_PATH_RE = re.compile(
    r"^\s*-\s*['\"]?((?:frontend|apps|tests|dsh|loop|\.claude|memory-bank)/"
    r"[^\s:'\"`]+)"
)


def _work_shard_path(cwd: Path, load_now: list[str]) -> Path | None:
    for raw in load_now:
        p = raw.strip()
        if not p.startswith("memory-bank/"):
            continue
        if _WORK_SHARD_RE.search(p) and (cwd / p).is_file():
            return cwd / p
    return None


def _resolve_bare_code_file(cwd: Path, name: str) -> str | None:
    """Unique basename under frontend/src or apps → repo-relative path."""
    hits: list[Path] = []
    for base in (cwd / "frontend" / "src", cwd / "apps"):
        if not base.is_dir():
            continue
        for p in base.rglob(name):
            if p.is_file():
                hits.append(p)
                if len(hits) > 1:
                    return None
    if len(hits) == 1:
        return hits[0].relative_to(cwd).as_posix()
    return None


def _normalize_shard_path_item(item: str) -> str:
    item = item.strip().strip("'\"`").rstrip(",;")
    if not item:
        return ""
    if "#" in item:
        item = item.split("#", 1)[0].strip()
    if ":" in item and not item.startswith("http"):
        left = item.split(":", 1)[0].strip()
        if "/" in left and not left.endswith(":"):
            item = left
    return item


def _is_scoped_repo_path(rel: str) -> bool:
    return rel.startswith(_SCOPED_PATH_PREFIXES) and ".." not in rel


def extract_shard_code_paths(cwd: str | Path, shard_text: str) -> list[str]:
    """Explicit repo paths from work shard (files/consumes/produces/delta + path-like)."""
    root = Path(cwd)
    seen: set[str] = set()
    out: list[str] = []

    def add(rel: str) -> None:
        rel = _normalize_shard_path_item(rel)
        if not rel or rel in seen:
            return
        if not _is_scoped_repo_path(rel):
            return
        seen.add(rel)
        out.append(rel)

    m = _FILES_BLOCK_RE.search(shard_text or "")
    if m:
        for line in m.group(1).splitlines():
            item = line.strip()
            if item.startswith("-"):
                item = item[1:].strip()
            add(item)

    for ctx in _CONTEXT_LIST_RE.finditer(shard_text or ""):
        for line in ctx.group(1).splitlines():
            item = line.strip()
            if item.startswith("-"):
                item = item[1:].strip()
            add(item)

    for line in (shard_text or "").splitlines():
        dm = _DELTA_LINE_PATH_RE.match(line)
        if dm:
            add(dm.group(1))

    for m in _CODE_PATH_RE.finditer(shard_text or ""):
        add(m.group(1))

    for m in _BARE_FILE_RE.finditer(shard_text or ""):
        name = m.group(1)
        if "/" in name:
            continue
        resolved = _resolve_bare_code_file(root, name)
        if resolved:
            add(resolved)

    return out


def detect_delta_paths(
    cwd: str | Path, load_now: list[str]
) -> tuple[str, list[str]]:
    """Return (scope, paths). scope: exist | scoped | open."""
    root = Path(cwd)
    shard = _work_shard_path(root, load_now)
    if shard is None:
        return "open", []
    try:
        text = shard.read_text(encoding="utf-8")
    except OSError:
        return "open", []
    paths = extract_shard_code_paths(root, text)
    if len(paths) < 2:
        return "open", paths
    if all((root / p).is_file() for p in paths):
        return "exist", paths
    return "scoped", paths


def _scope_parent_dirs(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in paths:
        parent = Path(raw).parent.as_posix()
        if parent in ("", "."):
            continue
        if parent not in seen:
            seen.add(parent)
            out.append(parent)
    return out


def _search_scope_block(delta_paths: list[str]) -> str:
    if not delta_paths:
        return ""
    path_lines = "\n".join(f"- `{p}`" for p in delta_paths)
    dirs = _scope_parent_dirs(delta_paths)
    dir_lines = "\n".join(f"- `{d}/`" for d in dirs) if dirs else "- _(нет — только файлы)_"
    return f"""
## search_scope (HARD)
ALLOW (default): work shard + paths ниже + их родительские каталоги.
paths:
{path_lines}
dirs:
{dir_lines}
Вне ALLOW — **только** если путь явно в shard (`context.consumes` / `files:` / `produces:` / checkpoint verify) или `plan §N` из Consumes. Иначе FORBIDDEN «на всякий случай».
Runtime verify: max 3 retry одной команды из shard → stderr / fix / `BLOCKED:`.
"""


def _explorer_block(
    *, delta_scope: str, delta_paths: list[str], explorer_on: bool
) -> str:
    if not explorer_on:
        return """## explorer
managed: off
Перед широким codebase search — graphify → узкий rg/Grep с path= внутри ALLOW (parent; @explorer выключен).
"""
    if delta_scope == "exist":
        path_lines = "\n".join(f"- `{p}`" for p in delta_paths)
        return (
            f"""## explorer
delta_paths_exist: yes
paths:
{path_lines}
SKIP `@explorer`. Работай только в ALLOW (shard + paths + parent dirs).
"""
            + _search_scope_block(delta_paths)
        )
    if delta_scope == "scoped":
        path_lines = "\n".join(f"- `{p}`" for p in delta_paths)
        return (
            f"""## explorer
delta_paths_scoped: yes
paths:
{path_lines}
SKIP `@explorer`. Greenfield OK — targets из shard, файлы могут ещё не существовать.
Read shard + `context.consumes` + listed targets; пиши `files:` / `produces:`.
Работай только в ALLOW; другие каталоги — только по явной ссылке в shard/plan.
"""
            + _search_scope_block(delta_paths)
        )
    return """## explorer
delta_paths_exist: no
Перед широким codebase search — 1× `@explorer` (packed ALLOW ≤10 paths).
"""


def _decompose_role_rule_dir(role: str) -> str:
    key = str(role or "back").lower()
    return {
        "back": "back_developer",
        "front": "front_developer",
        "integration": "integration_developer",
        "integ": "integration_developer",
    }.get(key, f"{key}_developer")


def _decompose_work_block(role: str, epic_id: str) -> str:
    rule_dir = _decompose_role_rule_dir(role)
    return f"""## DECOMPOSE canon (HARD)
1. Read `.cursor/templates/decompose/epic-step.yaml` + `index.md` + `.cursor/rules/{rule_dir}/workflow-decompose.mdc` (§Maximal detail).
2. Output dir: `memory-bank/{role}/plan/decompose-<plan_id>/` with **index.md** + **index.yaml** + `sNN-<slug>.yaml` (FORBIDDEN bare `sNN.yaml`).
3. index.md MUST contain: `## Requirements coverage`, `## Stages coverage`, `## Outcome map`, `## Replacement cleanup` (greenfield → `n/a`).
4. Each shard: `schema: epic-decompose/v1`, `role`, `as_built`/`delta` lists, 2–4 checkpoints with runnable verify.
5. FINISH: `validate-decompose-tree` (stop-gate) blocks promote if tree incomplete.
Epic queue id: `{epic_id}`.
"""


def _decompose_finish_block() -> str:
    return """## DECOMPOSE FINISH
1. Создай/обнови decompose dir: index.md + index.yaml + все sNN-<slug>.yaml по плану.
2. Self-check: `.venv/bin/python .claude/hooks/epic_resolve.py validate-decompose-tree --cwd "$PROJECT_ROOT" --decompose <path/to/index.yaml>`
3. Перепиши activeContext: следующий режим (IMPLEMENT s01 или ANALYZE если gate), `## load_now` → work shard + index.yaml, 1× `## Handoff`, ≤1× `## done`.
FORBIDDEN: FINISH без index.md; FORBIDDEN bare sNN.yaml; FORBIDDEN skip coverage tables in index.md.
"""


def _phase_kind(phase: object) -> str:
    value = str(phase or "").upper()
    if value == "DONE" or re.search(r"\bDONE\b", value):
        return "done"
    if re.search(r"\bCREATIVE\b", value):
        return "creative"
    if re.search(r"\bANALYZE\b", value):
        return "analyze"
    if re.search(r"\bCLARIFY\b", value):
        return "clarify"
    if re.search(r"\bDECOMPOSE\b", value):
        return "decompose"
    if re.search(r"\bPLAN\b", value):
        return "plan"
    if re.search(r"\bIMPLEMENT\b", value):
        return "implement"
    if re.search(r"\bQA\b", value):
        return "qa"
    if re.search(r"\bREFLECT\b", value):
        return "reflect"
    if re.search(r"\bAUDIT\b", value):
        return "audit"
    return "generic"


def _projection_step_id(projection: dict[str, Any], cwd_p: Path) -> str:
    for key in ("step", "next_step"):
        value = projection.get(key)
        if value:
            return str(value)
    st = load_epic_state(cwd_p) or {}
    armed = str(st.get("armed_step") or "").strip()
    if armed:
        return armed
    return "unknown"


_GATE_PHASES = frozenset(
    {
        "ANALYZE",
        "CLARIFY",
        "DECOMPOSE",
        "PLAN",
        "CREATIVE",
        "AUDIT",
        "QA",
        "BUGFIX",
        "REFLECT",
    }
)
_SHARD_STEP_RE = re.compile(r"^[sera]\d+", re.I)


def _prompt_projection(
    state: dict[str, Any],
    projection_state: dict[str, Any],
) -> dict[str, Any]:
    """Merge rebuilt projection + epic state for build_prompt (phase/epic/step)."""
    proj = dict(projection_state.get("projection") or {})
    for key in ("phase", "epic", "epic_id", "next_step", "step", "role"):
        outer = projection_state.get(key)
        if outer and not proj.get(key):
            proj[key] = outer
    armed = str(state.get("armed_step") or "").strip()
    armed_u = armed.upper()
    epic = state.get("armed_epic") or proj.get("epic") or proj.get("epic_id")
    if epic and not proj.get("epic"):
        proj["epic"] = epic
    if armed_u in _GATE_PHASES:
        role_t = str(state.get("role") or proj.get("role") or "BACK").upper()
        if role_t == "INTEGRATION":
            role_t = "INTEG"
        return {
            **proj,
            "phase": f"{role_t} {armed_u}",
            "next_step": armed_u,
            "step": armed_u,
            "epic": epic,
            "role": role_t,
        }
    if armed and _SHARD_STEP_RE.match(armed):
        proj.setdefault("next_step", armed)
        proj.setdefault("step", armed)
    elif not proj.get("next_step") and not proj.get("step"):
        top_next = projection_state.get("next_step")
        if top_next:
            proj["next_step"] = top_next
            proj.setdefault("step", top_next)
    if not proj.get("phase"):
        proj["phase"] = projection_state.get("phase") or state.get("phase")
    return proj


def _projection_for_gate_armed_step(
    state: dict[str, Any],
    projection: dict[str, Any],
) -> dict[str, Any]:
    return _prompt_projection(state, projection)


def _done_finish_block(*, chain_on: bool) -> str:
    chain_line = (
        "Runner при `EPIC_CHAIN_ROADMAP=1` сам возьмёт следующий эпик из roadmap Queue "
        "(smart entry: DECOMPOSE / IMPLEMENT / …).\n"
        if chain_on
        else "Без chain — stop; следующий эпик армит человек / `roadmap-advance`.\n"
    )
    return (
        "## DONE FINISH\n"
        "Эпик уже закрыт (projection.phase=DONE: QA pass + REFLECT).\n"
        "1. Перепиши `activeContext.md`: `## load_now` пуст → 1× `## Handoff` со "
        "строкой `EPIC_DONE` (без префикса Стоп:) → stop.\n"
        "2. FORBIDDEN: `BACK|FRONT|INTEG ARCHIVE NOW`, skill `*-archive`, VAN, "
        "выбор другого decompose/эпика, IMPLEMENT/QA/AUDIT заново.\n"
        "3. ARCHIVE — только вручную вне loop, после того как runner остановился "
        "или очередь roadmap исчерпана.\n"
        f"4. {chain_line}"
    )


def _implement_finish_block() -> str:
    return """## IMPLEMENT FINISH (по порядку)
HARD: все `memory-bank/**` и `--cwd` = `$PROJECT_ROOT` (продукт). Claude session cwd=hub — **не** пиши артефакты в `dev-hub/memory-bank`.
0. `python3 .claude/hooks/epic_resolve.py --cwd "$PROJECT_ROOT" seed-implement --decompose <decompose-shard.yaml>`
1. После каждого зелёного cp.verify:
   `python3 .claude/hooks/epic_resolve.py --cwd "$PROJECT_ROOT" flush-checkpoint --path <implement.yaml> --cp <cp_id>`
2. Suite: `timeout 300s …` (frontend-тесты — только parent).
3. Допиши evidence в implement yaml (`done`/`files`/`tests`/…); **status оставь `in_progress`**.
4. `python3 .claude/hooks/epic_resolve.py --cwd "$PROJECT_ROOT" validate-step --path <step>` → exit 0.
5. Перепиши `$PROJECT_ROOT/memory-bank/activeContext.md` (`## load_now` → 1× `## Handoff` → ≤1× `## done`).
6. `@verify` один раз (`.claude/instructions/spawn-hard.md`).
7. `VERDICT: PASS` → `finalize-step --cwd "$PROJECT_ROOT"` (он атомарно ставит implement+index `completed`) → JSON `ok: true` → stop.
   FAIL/DENY → **исправь причину в этом же эпике** (pending cp, gaps, неполный harness/parity, seed) → снова 6.
   без `VERDICT:` → макс. 1 retry шага 6; иначе Handoff `NEED_HUMAN: verify_no_verdict`.

HARD incomplete (обязательно):
- Шаг не закрыт, пока все `checkpoints[].status=done` и `gaps` не `blocked`.
- `@verify` PASS при pending cp / `gaps.status=blocked` = ложный PASS; hooks demote → FAIL. Считай это FAIL и чини.
- Gate шага (parity PASS, seed coverage, missing samples) не выполнен → добей в этом эпике (в т.ч. правкой prior sNN harness/docs), затем re-verify. Не «отдельный bugfix».
- FORBIDDEN: `BLOCKED:` / «consistent blocked-state PASS» / «нужен BACK BUGFIX» из‑за incomplete AC текущего эпика.
- `BLOCKED:` / `NEED_HUMAN:` — только внешний стоп (секреты, prod access, policy, ручное решение человека).

FORBIDDEN: писать `status: completed` руками (только `finalize-step`); `finalize-step` до `VERDICT: PASS`; писать product-эпики в `dev-hub/memory-bank` или hub `T-HUB-*` в product `memory-bank`.
"""


def _creative_finish_block() -> str:
    return """## CREATIVE FINISH
1. Запиши creative artifact и закрой gate в work shard:
   `needs_creative: yes (CR-…) — **closed**`; index колонка `yes (CR-…) ✅`;
   `next_phase` этого же sNN/eNN → `* IMPLEMENT`.
2. Перепиши `memory-bank/activeContext.md` (`## load_now` → 1× `## Handoff` → ≤1× `## done`).
   Handoff: тот же шаг, следующий режим IMPLEMENT (не следующий sNN и не `completed`).
3. FORBIDDEN: `mark-index-status --status completed` на CREATIVE —
   шаг остаётся `pending`/`active`. Index `completed` пишет только `finalize-step` после IMPLEMENT.
4. stop.

FORBIDDEN: `@verify` для CREATIVE.
"""


def _qa_finish_block() -> str:
    return """## QA FINISH
1. Parent suite зелёный (`timeout 300s …`).
2. `@reviewer` packed (Suite results · AC+ · AC− · §0.11 · ALLOW ≤10).
3. **HARD:** запиши `memory-bank/<role>/qa/<epic_id>/qa-YYYYMMDD-<slug>.yaml`
   (`schema: epic-qa/v1`, `verdict: pass|fail|blocked`). Без файла фаза QA не закрывается.
4. Перепиши `activeContext.md` (Handoff → REFLECT при pass; не EPIC_DONE).
5. stop. FORBIDDEN: pytest внутри reviewer.
"""


def _reflect_finish_block() -> str:
    return """## REFLECT FINISH
1. Write `memory-bank/**/reflection/reflection-<epic>.md`.
2. Handoff в activeContext; после PASS — отдельная строка `EPIC_DONE` и stop.
3. FORBIDDEN в этой сессии: ARCHIVE NOW / VAN / следующий эпик.
4. ARCHIVE — только вручную вне loop (после stop runner / исчерпания queue).
"""


def build_prompt(
    cwd: str | Path,
    *,
    shape_errors: list[str] | None = None,
    load_now: list[str] | None = None,
    delta_ok: bool | None = None,
    delta_scope: str | None = None,
    delta_paths: list[str] | None = None,
    resume_lines: list[str] | None = None,
    projection: dict[str, Any] | None = None,
    extra_blocks: list[str] | None = None,
) -> str:
    cwd_p = Path(cwd)
    load_now = list(load_now or [])
    shape_errors = list(shape_errors or [])
    paths = mb_paths_for_prompt(cwd_p, load_now)

    if delta_ok is None and delta_scope is None:
        delta_scope, delta_paths = detect_delta_paths(cwd_p, load_now)
    elif delta_scope is None:
        delta_scope = "exist" if delta_ok else "open"
    delta_paths = list(delta_paths or [])

    ac_text = read_active_context(cwd_p)
    marker_finished = handoff_indicates_epic_finished(ac_text)
    gate = epic_complete_allowed(cwd_p)
    projection = projection or {}
    phase = projection.get("phase")
    phase_done = str(phase or "").upper() == "DONE"
    truly_done = bool(
        gate.get("allowed")
        and (marker_finished or phase_done)
    )
    # After EPIC_DONE / ARCHIVE do not discover other decompose indexes (would trigger VAN).
    # Premature EPIC_DONE also must not VAN — stay on the current epic.
    # phase DONE + allowed also must not discover — runner owns roadmap chain.
    if not load_now and not marker_finished and not truly_done:
        for h in discover_decompose_indexes(cwd_p):
            if h not in paths:
                paths.append(h)

    path_lines = "\n".join(f"- `{p}`" for p in paths)
    phase_kind = _phase_kind(phase)
    step_id = _projection_step_id(projection, cwd_p)
    projection_lines = (
        "## projection\n"
        f"- phase: `{phase or 'unknown'}`\n"
        f"- epic: `{projection.get('epic') or 'unknown'}`\n"
        f"- step: `{step_id}`\n"
    )
    path_lines = f"{path_lines}\n\n{projection_lines}"
    degraded = bool(shape_errors) or not load_now

    from roadmap_queue import epic_chain_roadmap_enabled

    chain_on = epic_chain_roadmap_enabled(cwd_p)
    degraded_block = ""
    if degraded and truly_done:
        if chain_on:
            degraded_block = """
## Context degraded (epic finished)
Эпик закрыт (QA pass + REFLECT). Не начинай VAN/ARCHIVE и не выбирай другой decompose/эпик.
FORBIDDEN: ARCHIVE NOW / skill archive в этой сессии.
Runner при EPIC_CHAIN_ROADMAP=1 сам возьмёт следующий эпик из roadmap Queue.
На FINISH оставь в Handoff отдельную строку `EPIC_DONE` (без префикса Стоп:) и stop.
"""
        else:
            degraded_block = """
## Context degraded (epic finished)
Эпик уже закрыт (EPIC_DONE). Не начинай VAN/ARCHIVE и не выбирай другой decompose.
FORBIDDEN: ARCHIVE NOW в loop-сессии (только вручную вне loop).
На FINISH оставь в Handoff отдельную строку `EPIC_DONE` (без префикса Стоп:) и stop.
"""
    elif degraded and marker_finished and not phase_done:
        degraded_block = """
## Context degraded (premature EPIC_DONE)
Handoff содержит EPIC_DONE, но AUDIT/QA pass/REFLECT ещё нет. Эпик НЕ закрыт.
Не начинай VAN и не выбирай другой decompose.
Выполни текущую фазу из projection (AUDIT → QA → REFLECT).
На FINISH НЕ оставляй EPIC_DONE.
"""
    elif degraded and phase_done:
        degraded_block = """
## Context degraded (epic finished)
projection.phase=DONE. Не начинай VAN/ARCHIVE и не выбирай другой decompose/эпик.
FORBIDDEN: ARCHIVE NOW / skill archive в этой сессии.
На FINISH оставь в Handoff отдельную строку `EPIC_DONE` (без префикса Стоп:) и stop.
"""
    elif degraded:
        reasons = []
        if shape_errors:
            reasons.append("shape: " + "; ".join(shape_errors))
        if not load_now:
            reasons.append("load_now пуст или пути не распарсились")
        degraded_block = f"""
## Context degraded
activeContext не разобран ({'; '.join(reasons)}). Не halt.
1. Прочитай `$PROJECT_ROOT/memory-bank/activeContext.md`.
2. **SoT:** `memory-bank/**/plan/decompose-*/index.yaml` — первый step со status `pending`/`active`.
3. **FORBIDDEN:** доверять Handoff step_id или `## done`, если они расходятся с index.yaml (нет implement-шарда / finalize-step).
4. Один следующий шаг = режим + step_id **из index.yaml**, не из Handoff.
5. На FINISH перепиши activeContext:
   `## load_now` (пути в backticks) → 1× `## Handoff` → ≤1× `## done`.
"""

    explorer_block = ""
    finish_block = ""
    explorer_on = explorer_loop_enabled(cwd)
    if phase_done or phase_kind == "done":
        finish_block = _done_finish_block(chain_on=chain_on)
    elif phase_kind == "creative":
        finish_block = _creative_finish_block()
    elif phase_kind == "implement":
        explorer_block = _explorer_block(
            delta_scope=delta_scope or "open",
            delta_paths=delta_paths,
            explorer_on=explorer_on,
        )
        finish_block = _implement_finish_block()
    elif phase_kind == "qa":
        finish_block = _qa_finish_block()
    elif phase_kind == "reflect":
        finish_block = _reflect_finish_block()
    elif phase_kind == "audit":
        finish_block = (
            "## AUDIT FINISH\n"
            "1. Gap-матрица plan vs implement (все step_id).\n"
            "2. HARD: запиши `memory-bank/<role>/audit/<epic_id>/audit-YYYYMMDD-<slug>.yaml`.\n"
            "3. Перепиши activeContext (`## Handoff … AUDIT`). "
            "not_implemented[] пуст → следующий = QA.\n"
            "FORBIDDEN: EPIC_DONE до QA pass + REFLECT.\n"
        )
    elif phase_kind == "analyze":
        finish_block = (
            "## ANALYZE FINISH\n"
            "1. Read-only: plan + decompose shards vs код/repo.\n"
            "2. HARD: `memory-bank/<role>/analyze/<epic_id>/analyze-YYYYMMDD-<slug>.yaml`.\n"
            "3. `critical_count=0` → loop откроет IMPLEMENT; иначе fix plan/decompose и re-ANALYZE.\n"
            "FORBIDDEN: IMPLEMENT / seed-implement до pass ANALYZE gate.\n"
        )
    elif phase_kind == "decompose":
        finish_block = _decompose_finish_block()
    elif phase_kind in {"clarify", "plan"}:
        finish_block = (
            f"## {phase_kind.upper()} FINISH\n"
            "1. Выполни режим из Handoff activeContext.\n"
            "2. Перепиши activeContext: `## load_now` → 1× `## Handoff` → ≤1× `## done`.\n"
        )
    else:
        explorer_block = _explorer_block(
            delta_scope=delta_scope or "open",
            delta_paths=delta_paths,
            explorer_on=explorer_on,
        )
        finish_block = _implement_finish_block()

    resume_block = "\n".join(resume_lines or [])
    extra_block = "\n".join(extra_blocks or [])
    decompose_block = ""
    if phase_kind == "decompose":
        role_key = str(projection.get("role") or "back").lower()
        if role_key not in {"back", "front", "integration"}:
            role_key = "back"
        epic_key = str(projection.get("epic") or projection.get("epic_id") or "unknown")
        decompose_block = _decompose_work_block(role_key, epic_key)

    return f"""Выполни один шаг.

{resume_block}

Контекст:
{path_lines}
{degraded_block}
{decompose_block}## Команды
1. Не вызывай: loop.sh, epic_resolve after|resolve|arm|halt|complete|record-session.
2. Стоп: `BLOCKED:` или `NEED_HUMAN:` — **только** внешний/человеческий стоп.
   FORBIDDEN: `BLOCKED:` из‑за incomplete AC / pending cp / gaps.blocked / parity FAIL текущего эпика
   (это чинится в сессии: FAIL → fix → re-verify).
   FORBIDDEN stop-маркер: `GAPS:` / `**GAPS:**`.
   Отложено → `Отложено:` / `Deferred:`.
3. Silent chat (HARD): no thinking aloud; no restating rules/HARD/TodoWrite; no tool-call narration; chat = итог only. Cursor TodoWrite nudge — ignore (do not quote).

{explorer_block}
{extra_block}
{finish_block}
"""


def _incomplete_step_fix_blocks(cwd: Path) -> list[str]:
    """When step has pending cps / gaps.blocked — force fix, not BLOCKED spin."""
    try:
        blockers = verify_pass_step_blockers(cwd)
    except Exception:
        return []
    if not blockers:
        return []
    return [
        "## FIX INCOMPLETE (HARD)",
        "Текущий implement-шаг НЕ готов к закрытию:",
        *[f"- {item}" for item in blockers],
        "Сейчас: устрани причину (добей cp / сними gaps.blocked / дополни harness/parity/seed),",
        "затем validate-step → Handoff → @verify. FAIL → снова fix.",
        "FORBIDDEN: `BLOCKED:` / «нужен отдельный bugfix» / PASS на consistent blocked-state.",
    ]


_POST_IMPLEMENT_PHASES = frozenset({"AUDIT", "QA", "REFLECT", "BUGFIX"})


def _is_post_implement_step(step_id: str | None) -> bool:
    return str(step_id or "").strip().upper() in _POST_IMPLEMENT_PHASES


def _index_step_is_completed(cwd: Path, step_id: str | None) -> bool:
    sid = str(step_id or "").strip()
    if not sid or not re.match(r"^[sera]\d{2}$", sid.lower()):
        return False
    st = load_epic_state(cwd)
    decompose = st.get("armed_decompose")
    if not decompose:
        return False
    loaded = load_decompose_steps_fail_closed(cwd, str(decompose))
    if not loaded.get("ok"):
        return False
    for item in loaded.get("steps") or []:
        if str(item.get("id") or item.get("step_id") or "").strip() != sid:
            continue
        return str(item.get("status") or "").lower() in {"completed", "done"}
    return False


def _analyze_phase_complete(cwd: Path) -> bool:
    from analyze_gate import analyze_required_before_implement
    from roadmap_queue import find_decompose_index, load_steps_for_index

    st = load_epic_state(cwd)
    epic_id = str(st.get("armed_epic") or "").strip()
    if not epic_id:
        return False
    role_dir = str(st.get("role") or "BACK").lower()
    decomp = str(st.get("armed_decompose") or "").strip()
    idx_path = cwd / decomp if decomp else None
    if idx_path is None or not idx_path.is_file():
        idx_path = find_decompose_index(cwd, role_dir, epic_id)
    if idx_path is None or not idx_path.is_file():
        return False
    loaded = load_steps_for_index(cwd, idx_path)
    if not loaded.get("ok"):
        return False
    steps = loaded.get("steps") or []
    gate = analyze_required_before_implement(
        cwd,
        role_dir,
        epic_id,
        steps,
        index_path=idx_path,
    )
    return not gate.get("required")


def _checkpoint_should_advance_after_session(cwd: Path, step_id: str | None) -> bool:
    if _index_step_is_completed(cwd, step_id) or _is_post_implement_step(step_id):
        return True
    if str(step_id or "").upper() == "ANALYZE":
        return _analyze_phase_complete(cwd)
    return False


def _stale_post_implement_identity_conflict(
    resume: dict[str, Any],
    *,
    expected_step: str | None,
) -> bool:
    if resume.get("code") != "checkpoint_identity_conflict":
        return False
    checkpoint = resume.get("checkpoint") or {}
    if checkpoint.get("stage") != "committed" or checkpoint.get("resume_policy") != "same_step":
        return False
    actual = checkpoint.get("identity") or {}
    actual_step = str(actual.get("step") or checkpoint.get("step_id") or "").strip().upper()
    expected = str(expected_step or "").strip().upper()
    if not actual_step or not expected or actual_step == expected:
        return False
    return actual_step in _POST_IMPLEMENT_PHASES and expected in _POST_IMPLEMENT_PHASES


def _step_context_extra_blocks(cwd: Path, load_now: list[str]) -> list[str]:
    """Inject short step pointer when decompose work shard is known."""
    work = _work_shard_path(cwd, load_now)
    if work is None:
        return []
    rel = str(work.relative_to(cwd)).replace("\\", "/")
    if "decompose-" not in rel.replace("\\", "/"):
        return []
    try:
        from epic_paths import epic_id_from_decompose_path
        from epic_yaml import (
            load_decompose,
            load_implement,
            resolve_implement_path,
            seed_checkpoint_bootstrap_lines,
            step_context_prompt_lines,
        )
    except ImportError:
        return []
    try:
        dec = load_decompose(work)
    except Exception:
        return []
    impl = None
    folder_epic = epic_id_from_decompose_path(rel) or dec.plan_id
    impl_rel = resolve_implement_path(
        cwd, dec.role, folder_epic, dec.step_id, plan_id=dec.plan_id
    )
    impl_path = cwd / impl_rel
    if impl_path.is_file():
        try:
            impl = load_implement(impl_path)
        except Exception:
            impl = None
    lines: list[str] = []
    try:
        lines.extend(step_context_prompt_lines(dec, impl, shard_rel=rel))
    except Exception:
        pass
    if impl is None:
        lines.extend(seed_checkpoint_bootstrap_lines(rel))
    return lines


def arm_session(cwd: str | Path, epic: str) -> dict[str, Any]:
    """Switch epic via plan-centric arm_epic (resolver picks phase); legacy decompose path delegates."""
    from epic_paths import resolve_arm_epic_target

    resolved = resolve_arm_epic_target(epic, cwd)
    if resolved:
        epic_id, role = resolved
        legacy_decompose = "decompose-" in str(epic).replace("\\", "/")
        out = arm_epic(
            cwd,
            epic_id,
            role=role,
            require_plan=not legacy_decompose,
        )
        if legacy_decompose:
            out = dict(out)
            out["deprecated"] = "arm via decompose path; prefer arm_epic(epic_id) or --epic-id"
    else:
        out = arm_active_context_from_decompose(cwd, epic)
    if not out.get("ok"):
        return out
    if out.get("complete"):
        return out
    text = read_active_context(cwd)
    out["fingerprint"] = fingerprint_context(text)
    out["load_now"] = extract_load_now(text)
    out["stop"] = detect_stop_marker(text)
    new_step = out.get("step_id")
    if new_step:
        last = load_last_session(cwd, track="epic")
        if last and last.get("status") == "aborted" and last.get("resume_from") != new_step:
            write_last_session(
                cwd,
                track="epic",
                **{k: v for k, v in last.items() if k not in ("updated_at", "resume_from", "step_id")},
                resume_from=new_step,
                step_id=new_step,
            )
    return out


def resolve_premature_epic_done(cwd: str | Path) -> dict[str, Any] | None:
    """Reject EPIC_DONE unless QA pass + reflection exist; rewrite to next phase.

    Returns:
      None — EPIC_DONE allowed (true complete) or marker absent
      dict with rewrote_premature_epic_done — context rewritten to AUDIT/QA/REFLECT
      dict with reject_epic_done — cannot rewrite; caller must NOT complete
    """
    cwd_p = Path(cwd)
    text = read_active_context(cwd_p)
    if detect_stop_marker(text) != "EPIC_DONE" and not handoff_indicates_epic_finished(
        text
    ):
        return None

    gate = epic_complete_allowed(cwd_p)
    if gate.get("allowed"):
        return None

    # ARCHIVE NOW Handoff already closed the epic — never rewrite back to QA/REFLECT.
    handoff = extract_handoff_block(text) or ""
    heading = handoff.splitlines()[0] if handoff.splitlines() else ""
    if re.search(r"(?i)\bARCHIVE\s+NOW\b", heading):
        return {
            "ok": False,
            "complete": False,
            "reject_epic_done": True,
            "rewrote_premature_epic_done": False,
            "phase": gate.get("phase"),
            "reason": gate.get("reason")
            or "EPIC_DONE запрещён: нет QA pass и/или REFLECT",
        }

    decompose = gate.get("decompose") or (load_epic_state(cwd_p) or {}).get(
        "armed_decompose"
    )
    if decompose:
        out = arm_active_context_from_decompose(cwd_p, str(decompose))
        if out.get("ok") and not out.get("complete"):
            new_text = read_active_context(cwd_p)
            if detect_stop_marker(new_text) == "EPIC_DONE":
                return {
                    "ok": False,
                    "complete": False,
                    "reject_epic_done": True,
                    "rewrote_premature_epic_done": False,
                    "phase": out.get("phase") or gate.get("phase"),
                    "reason": (
                        f"invariant: rewrite в {out.get('phase')} оставил EPIC_DONE"
                    ),
                }
            out["rewrote_premature_epic_done"] = True
            out["phase"] = out.get("phase") or gate.get("phase")
            return out
        if out.get("complete") and out.get("stop") == "EPIC_DONE":
            gate2 = epic_complete_allowed(cwd_p)
            if gate2.get("allowed"):
                return None

    return {
        "ok": False,
        "complete": False,
        "reject_epic_done": True,
        "rewrote_premature_epic_done": False,
        "phase": gate.get("phase"),
        "reason": gate.get("reason")
        or "EPIC_DONE запрещён: нет QA pass и/или REFLECT",
    }


def _role_dir_from_state_role(role: str | None) -> str:
    r = (role or "BACK").strip().upper()
    return {
        "BACK": "back",
        "FRONT": "front",
        "INTEG": "integration",
        "INTEGRATION": "integration",
    }.get(r, "back")


def _find_decompose_index_for_epic(
    cwd: Path, epic_id: str, role: str | None
) -> str | None:
    from roadmap_queue import find_decompose_index

    role_dir = _role_dir_from_state_role(role)
    idx = find_decompose_index(cwd, role_dir, epic_id)
    if idx is None:
        return None
    try:
        return idx.relative_to(cwd).as_posix()
    except ValueError:
        return str(idx)


def run_traceability_check_if_enabled(
    cwd: str | Path,
    epic_id: str | None = None,
    *,
    fail_closed: bool = False,
) -> None:
    val = os.getenv("EPIC_TRACEABILITY_CHECK")
    if val in ("0", "false", "FALSE"):
        return
    if not fail_closed and val not in ("1", "true", "TRUE"):
        return
    if not epic_id:
        st = load_epic_state(Path(cwd))
        epic_id = st.get("armed_epic")
    if not epic_id:
        return
    import subprocess
    cmd = [
        sys.executable,
        str(Path(cwd) / ".claude" / "hooks" / "epic_resolve.py"),
        "--cwd",
        str(cwd),
        "validate-traceability",
        "--epic",
        str(epic_id),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    st = load_epic_state(Path(cwd))
    role_dir = str(st.get("role") or "back").lower()
    decomp = str(st.get("armed_decompose") or "").strip()
    art_path = Path(cwd) / decomp if decomp and (Path(cwd) / decomp).is_file() else Path(cwd) / "memory-bank" / "activeContext.md"
    if res.returncode == 2:
        logger.error("validate-traceability error: %s", res.stderr or res.stdout)
        try:
            from epic import _append_event
            if art_path.is_file():
                _append_event(Path(cwd), role_dir, str(epic_id), "traceability_fail", art_path)
        except Exception:
            pass
        raise RuntimeError(
            f"validate-traceability failed (exit 2) for epic {epic_id}: {res.stderr or res.stdout}"
        )
    elif res.returncode == 1:
        logger.warning("validate-traceability warning: %s", res.stdout)
        try:
            from epic import _append_event
            if art_path.is_file():
                _append_event(Path(cwd), role_dir, str(epic_id), "traceability_warn", art_path)
        except Exception:
            pass


def promote_decompose_phase_if_ready(cwd: str | Path) -> dict[str, Any] | None:
    """Auto-advance after DECOMPOSE / ANALYZE FINISH — delegates to promote_if_ready."""
    from loop.epic_transition import _legacy_warn, promote_if_ready

    _legacy_warn("promote_decompose_phase_if_ready")
    cwd_p = Path(cwd)
    st = load_epic_state(cwd_p)
    epic_id = st.get("armed_epic")
    if not epic_id:
        return None
    role = str(st.get("role") or "BACK").lower()
    out = promote_if_ready(cwd_p, str(epic_id), role)
    if out is not None and out.get("ok"):
        try:
            run_traceability_check_if_enabled(cwd_p, str(epic_id), fail_closed=True)
        except RuntimeError as err:
            return {
                "ok": False,
                "error": str(err),
                "diagnostic_code": "traceability_fail",
            }
    return out


def prepare_session(
    cwd: str | Path,
    *,
    model: str | None = None,
    runtime: str | None = None,
) -> dict[str, Any]:
    cwd_p = Path(cwd)
    ac = cwd_p / "memory-bank" / "activeContext.md"
    if not ac.is_file():
        return {
            "ok": False,
            "reason": "нет memory-bank/activeContext.md — создай файл или восстанови из git",
        }

    cleared_role = clear_reserved_role_arm(cwd_p)
    if cleared_role.get("cleared"):
        return {
            "ok": False,
            "halt": True,
            "reason": cleared_role.get("reason"),
            "diagnostic_code": cleared_role.get("diagnostic_code") or "armed_role_slug",
            "cleared_reserved_role_arm": True,
        }

    promoted = promote_decompose_phase_if_ready(cwd_p)
    if promoted is not None and not promoted.get("ok"):
        res = {
            "ok": False,
            "halt": True,
            "reason": promoted.get("error")
            or promoted.get("reason")
            or "decompose promote failed",
            "promote": promoted,
        }
        if promoted.get("diagnostic_code"):
            res["diagnostic_code"] = promoted["diagnostic_code"]
        return res

    projection = rebuild_epic_projection(cwd_p)
    text = read_active_context(cwd_p)
    state = load_epic_state(cwd_p)
    from loop.schemas.active_context import handoff_mode_from_text

    ac_mode = (handoff_mode_from_text(text) or "").upper()
    if (
        ac_mode == "IMPLEMENT"
        and str(state.get("armed_step") or "").upper() == "ANALYZE"
        and (promoted is None or not promoted.get("ok"))
        and _analyze_phase_complete(cwd_p)
    ):
        promoted = promote_decompose_phase_if_ready(cwd_p)
        if promoted is not None and promoted.get("ok"):
            text = read_active_context(cwd_p)
            state = load_epic_state(cwd_p)
            projection = rebuild_epic_projection(cwd_p)
    handoff_phase = handoff_post_implement_phase(text)
    proj = projection.get("projection") if isinstance(projection.get("projection"), dict) else {}
    proj_phase = str(
        proj.get("phase") or projection.get("phase") or state.get("phase") or ""
    ).upper()
    if handoff_phase in {"AUDIT", "REFLECT", "BUGFIX"}:
        state["armed_step"] = handoff_phase
        state["phase"] = handoff_phase
        state["active"] = True
        state["status"] = "running"
        save_epic_state(cwd_p, state)
        proj_phase = handoff_phase
    if proj_phase == "DONE" and handoff_phase not in {
        "AUDIT",
        "REFLECT",
        "BUGFIX",
    }:
        # Clear stale AUDIT/QA/REFLECT armed_step so banner/model key match DONE.
        if state.get("armed_step") not in (None, "", "DONE"):
            state["armed_step"] = None
            state["phase"] = "DONE"
            save_epic_state(cwd_p, state)
        gate_done = epic_complete_allowed(cwd_p)
        if gate_done.get("allowed"):
            state = load_epic_state(cwd_p)
            state["armed_step"] = None
            state["phase"] = "DONE"
            state["active"] = False
            state["status"] = "complete"
            state["halt_reason"] = None
            save_epic_state(cwd_p, state)
            return _epic_done_stop_result(cwd_p)
    if str(state.get("status") or "").lower() == "complete":
        gate = epic_complete_allowed(cwd_p)
        if gate.get("allowed"):
            return {
                "ok": False,
                "complete": True,
                "reason": "EPIC_DONE",
                "stop": "EPIC_DONE",
            }
        state["status"] = "armed"
        state["active"] = True
        state["halt_reason"] = None
        save_epic_state(cwd_p, state)
    armed_step_now = str(state.get("armed_step") or "")
    decompose = resolve_armed_decompose_for_integrity(
        cwd_p,
        armed_step=armed_step_now,
        armed_decompose=state.get("armed_decompose"),
    )
    if decompose != state.get("armed_decompose"):
        state["armed_decompose"] = decompose
        save_epic_state(cwd_p, state)
    if decompose:
        md_repair = repair_index_mirror(cwd_p, decompose)
        if not md_repair.get("ok"):
            logger.warning(
                "prepare: md mirror repair skipped (yaml remains canon): %s",
                md_repair.get("error") or md_repair,
            )
        # index.yaml is cursor SoT — rewrite AC + armed_step before integrity/checkpoint.
        cursor_sync = sync_cursor_from_index(cwd_p)
        if cursor_sync.get("synced"):
            text = read_active_context(cwd_p)
            state = load_epic_state(cwd_p)
            projection = rebuild_epic_projection(cwd_p)
            logger.warning(
                "prepare: cursor synced from index.yaml %s → %s",
                cursor_sync.get("previous_armed"),
                cursor_sync.get("step_id"),
            )
        if cursor_sync.get("ok") is False:
            return {
                "ok": False,
                "halt": True,
                "reason": cursor_sync.get("reason") or "cursor sync from index failed",
                "cursor_sync": cursor_sync,
            }
        if cursor_sync.get("complete") and cursor_sync.get("arm", {}).get("stop") == "EPIC_DONE":
            return _epic_done_stop_result(cwd_p)
        finish_integrity = validate_finish_integrity_with_repair(
            cwd_p,
            decompose=decompose,
            step_id=str(state.get("armed_step") or ""),
            require_verify_pass=True,
        )
        if not finish_integrity["ok"]:
            return {
                "ok": False,
                "halt": True,
                "diagnostic_codes": finish_integrity["diagnostic_codes"],
                "reason": "; ".join(finish_integrity["errors"]),
                "repair": finish_integrity.get("repair"),
                "md_repair": md_repair,
                "cursor_sync": cursor_sync,
            }
    else:
        cursor_sync = {"ok": True, "synced": False, "reason": "no_decompose"}
    resume = checkpoint_resume(
        cwd_p,
        projection_hash=projection.get("projection_hash"),
        index_fingerprint=(projection.get("projection") or {}).get("index_fingerprint"),
        context_fingerprint=fingerprint_context(text),
        identity={
            "pipeline": state.get("pipeline_id") or state.get("dag_pipeline"),
            "epic": state.get("armed_epic"),
            "role": state.get("role") or projection.get("projection", {}).get("role"),
            "step": state.get("armed_step"),
        },
    )
    if not resume.get("ok"):
        conflict_code = resume.get("code") or resume.get("decision")
        # Fingerprints drift after arm / AC rewrite. Prepare always writes a fresh
        # "prepared" checkpoint later — drop the stale file and continue.
        if conflict_code in {
            "checkpoint_projection_conflict",
            "checkpoint_identity_conflict",
        } and (
            conflict_code == "checkpoint_projection_conflict"
            or _stale_post_implement_identity_conflict(
                resume,
                expected_step=str(state.get("armed_step") or ""),
            )
        ):
            cleared = clear_runner_checkpoint(cwd_p)
            if not cleared.get("ok"):
                return {
                    "ok": False,
                    "halt": True,
                    "reason": "checkpoint_clear_failed",
                    "diagnostic_codes": ["checkpoint_clear_failed"],
                    "checkpoint_clear": cleared,
                    "checkpoint": resume.get("checkpoint"),
                }
            logger.warning(
                "prepare: cleared stale checkpoint after %s (path=%s)",
                conflict_code,
                cleared.get("path"),
            )
        else:
            return {
                "ok": False,
                "halt": True,
                "reason": conflict_code,
                "checkpoint": resume.get("checkpoint"),
            }
    stripped_blocked = False
    stop = detect_stop_marker(text)
    if not stop and handoff_indicates_epic_finished(text):
        stop = "EPIC_DONE"
    if stop == "EPIC_DONE":
        fixed = resolve_premature_epic_done(cwd_p)
        if fixed is not None and fixed.get("rewrote_premature_epic_done"):
            text = read_active_context(cwd_p)
            stop = detect_stop_marker(text)
            if not stop and handoff_indicates_epic_finished(text):
                stop = "EPIC_DONE"
            if stop == "EPIC_DONE":
                return _epic_done_stop_result(cwd_p)
        elif fixed is not None and fixed.get("reject_epic_done"):
            return {
                "ok": False,
                "complete": False,
                "halt": True,
                "reason": fixed.get("reason"),
                "phase": fixed.get("phase"),
            }
        elif fixed is None and stop == "EPIC_DONE":
            return _epic_done_stop_result(cwd_p)
    if stop:
        if stop == "EPIC_DONE":
            return _epic_done_stop_result(cwd_p)
        if stop.startswith("NEED_HUMAN"):
            return {"ok": False, "complete": True, "reason": stop, "stop": stop}
        # BLOCKED: left by a previous session — strip and retry with FIX INCOMPLETE
        # when the armed step still has pending cps / gaps.blocked.
        # NEED_HUMAN: requires explicit human intervention — do not auto-clear.
        ac_path = cwd_p / "memory-bank" / "activeContext.md"
        cleaned = re.sub(
            r"(?m)^\s*(?:[-*]\s*)?(?:\*\*)?BLOCKED(?:\*\*)?\s*:.*$",
            "",
            text,
        ).strip()
        ac_path.write_text(cleaned + "\n", encoding="utf-8")
        text = cleaned
        stripped_blocked = True

    shape = validate_active_context_shape(text)
    load_now = extract_load_now(text)
    # Keep only paths that exist — broken links = soft degrade, not halt
    existing: list[str] = []
    for raw in load_now:
        p = raw.strip()
        if not p.startswith("memory-bank/"):
            if p.startswith(("back/", "front/", "integration/")):
                p = f"memory-bank/{p}"
            else:
                continue
        if (cwd_p / p).is_file() or (cwd_p / p).is_dir():
            existing.append(p)

    delta_scope, delta_paths = detect_delta_paths(cwd_p, existing)
    delta_ok = delta_scope == "exist"
    st = load_epic_state(cwd_p)

    # Cursor already synced from index.yaml earlier in prepare (SoT).
    _auto_advanced = bool(cursor_sync.get("synced"))
    if _auto_advanced:
        _last = load_last_session(cwd_p, track="epic")
        if _last and _last.get("status") == "aborted":
            _new_step = st.get("armed_step") or cursor_sync.get("step_id")
            write_last_session(
                cwd_p,
                track="epic",
                **{
                    k: v
                    for k, v in _last.items()
                    if k not in ("updated_at", "resume_from", "step_id")
                },
                resume_from=_new_step,
                step_id=_new_step,
            )

    last = load_last_session(cwd_p, track="epic")
    step_id = st.get("armed_step")
    plan_id = st.get("armed_epic")
    try:
        if last and last.get("status") != "aborted":
            resume_lines = []
        else:
            resume_lines = dirty_resume_prompt_lines(
                cwd_p,
                step_id=step_id,
                plan_id=plan_id,
                epic_id=st.get("armed_epic"),
                delta=existing,
                resume_from=step_id if _auto_advanced else ((last or {}).get("resume_from") or step_id),
                last=last,
            )
    except RuntimeError:
        resume_lines = []
        if last and last.get("status") == "aborted":
            resume_lines = [
                "",
                "## resume_dirty (HARD)",
                "prev_session: aborted"
                + (f" — {last['reason']}" if last.get("reason") else ""),
                f"continue_from_checkpoint: {(last.get('resume_from') or step_id)}",
                "FORBIDDEN: discard/revert dirty step files; full-repo rediscovery.",
            ]

    st_pre = load_epic_state(cwd_p)
    stall_n = int(st_pre.get("fingerprint_stall_count") or 0)
    if stall_n > 0:
        resume_lines = list(resume_lines or [])
        resume_lines.extend(
            [
                "## PRIOR SESSION: fingerprint stall (HARD)",
                "Прошлая сессия вышла без смены `memory-bank/activeContext.md`.",
                "ПЕРВЫМ делом (до кода, если шаг уже частично сделан — всё равно):",
                "Write весь `activeContext.md`: `## load_now` → ровно 1× `## Handoff` → ≤1× `## done`.",
                "В Handoff: что уже сделано + что осталось на текущем шаге; затем доведи шаг или FINISH.",
                f"Это outer retry после stall (счётчик={stall_n}). Без нового Handoff loop снова retry/halt.",
            ]
        )

    extra = list(_step_context_extra_blocks(cwd_p, existing))
    # Surface incomplete blockers so loop cannot "PASS+BLOCKED" spin.
    extra.extend(_incomplete_step_fix_blocks(cwd_p))
    # de-dupe section headers while preserving order
    seen: set[str] = set()
    extra_deduped: list[str] = []
    for line in extra:
        if line.startswith("##"):
            if line in seen:
                continue
            seen.add(line)
        extra_deduped.append(line)

    prompt = build_prompt(
        cwd_p,
        shape_errors=shape,
        load_now=existing,
        delta_scope=delta_scope,
        delta_paths=delta_paths,
        resume_lines=resume_lines,
        projection=_projection_for_gate_armed_step(st, projection),
        extra_blocks=extra_deduped,
    )

    fp = fingerprint_context(text)
    degraded = bool(shape) or not existing

    pp = prompt_path(cwd_p)
    pp.write_text(prompt, encoding="utf-8")

    st = load_epic_state(cwd_p)
    st["active"] = True
    st["status"] = "running"
    st["halt_reason"] = None
    st["pending_fingerprint_before"] = fp
    st["load_now_before"] = existing
    previous_fp = st.get("degraded_fingerprint")
    if degraded:
        if previous_fp == fp:
            st["degraded_count"] = int(st.get("degraded_count") or 0) + 1
        else:
            st["degraded_count"] = 1
        st["degraded_fingerprint"] = fp
        max_degraded = resolve_runtime_config(cwd_p).degraded_max
        if st["degraded_count"] >= max_degraded:
            reason = (
                f"NEED_HUMAN: activeContext shape remains invalid after "
                f"{max_degraded} recovery sessions"
            )
            st["active"] = False
            st["status"] = "halted"
            st["halt_reason"] = reason
            save_epic_state(cwd_p, st)
            return {"ok": False, "complete": False, "halt": True, "reason": reason}
    else:
        st["degraded_count"] = 0
        st["degraded_fingerprint"] = None
    st["context_degraded"] = degraded
    st["delta_paths_exist"] = delta_scope == "exist"
    st["delta_paths_scoped"] = delta_scope == "scoped"
    st["delta_scope"] = delta_scope
    st["delta_paths"] = delta_paths
    proj_for_phase = _projection_for_gate_armed_step(st, projection)
    phase_raw = proj_for_phase.get("phase") or st.get("phase") or projection.get("phase")
    armed_step_now = st.get("armed_step")
    runtime_config = resolve_runtime_config(cwd_p)
    effective_runtime = (runtime or "").strip() or runtime_config.epic_runtime
    resolved = resolve_loop_phase_model(
        phase=str(phase_raw) if phase_raw else None,
        armed_step=str(armed_step_now) if armed_step_now else None,
        cli_model=model,
        project_dir=HUB_ROOT,
    )
    effective_model = resolved.get("model") or model
    if effective_model:
        st["model"] = effective_model
    checkpoint_session = (
        str(st.get("session_id") or "").strip()
        or str(os.environ.get("EPIC_RUNNER_SESSION_ID") or "").strip()
        or f"prepare-{projection.get('phase_epoch') or fp}"
    )
    st["session_id"] = checkpoint_session
    proj = st.get("projection")
    if isinstance(proj, dict):
        proj["session_id"] = checkpoint_session
    st["updated_at"] = utc_now()
    try:
        ep_id = begin_episode(
            cwd_p,
            epic_id=str(st.get("armed_epic") or "T-HUB-031"),
            role=str(st.get("role") or "back"),
            armed_step=str(st.get("armed_step") or "s01"),
        )
        st["episode_id"] = ep_id
    except Exception as err:
        logger.warning("prepare: begin_episode failed: %s", err)
        ep_id = None
    save_epic_state(cwd_p, st)
    checkpoint_lifecycle(
        cwd_p,
        checkpoint_id=f"{checkpoint_session}:{st.get('armed_step') or 'context'}",
        session_id=checkpoint_session,
        runner_id=st.get("runner_id") or os.environ.get("EPIC_RUNNER_ID"),
        identity={
            "pipeline": st.get("pipeline_id") or st.get("dag_pipeline"),
            "epic": st.get("armed_epic"),
            "role": st.get("role") or projection.get("projection", {}).get("role"),
            "step": st.get("armed_step"),
            "action": "invoke",
        },
        step_id=st.get("armed_step") or "memory-bank/activeContext.md",
        phase=projection.get("phase") or "UNKNOWN",
        phase_epoch=projection.get("phase_epoch") or "unknown",
        projection_hash=projection.get("projection_hash"),
        index_fingerprint=projection.get("projection", {}).get("index_fingerprint"),
        context_fingerprint=fp,
        stage="prepared",
        status="active",
        next_action="invoke",
        resume_policy="same_step",
        degraded_count=int(st.get("degraded_count") or 0),
    )

    return {
        "ok": True,
        "prompt_file": str(pp),
        "checkpoint": checkpoint_session,
        "load_now": existing,
        "fingerprint": fp,
        "model": effective_model or st.get("model"),
        "model_source": resolved.get("model_source"),
        "model_env": resolved.get("model_env"),
        "loop_phase": resolved.get("loop_phase"),
        "runtime": effective_runtime,
        "dsh_profile": f"epic-{(resolved.get('loop_phase') or 'implement').lower()}",
        "dsh_workspace": str(cwd_p),
        "phase": phase_raw,
        "armed_step": armed_step_now,
        "episode_id": ep_id,
        "degraded": degraded,
        "shape_errors": shape,
        "delta_paths_exist": delta_scope == "exist",
        "delta_paths_scoped": delta_scope == "scoped",
        "delta_scope": delta_scope,
        "delta_paths": delta_paths,
        "cursor_sync": cursor_sync,
    }


def _run_tier0_check_after(cwd_p: Path, res: dict[str, Any]) -> dict[str, Any]:
    from epic_paths import epic_dir
    from loop.incidents.schema import IncidentRecord, compute_incident_id
    from loop.incidents.store import append_incident, list_open_incidents
    from loop.incidents.tier0 import run_tier0_for_incident
    from loop.incidents.tier1 import is_tier1_eligible
    from _lib import load_runner_owner, runner_pid_alive

    st_ep = load_epic_state(cwd_p)
    episode_id = st_ep.get("episode_id")
    if episode_id:
        try:
            finalize_episode(cwd_p, episode_id, check_after_result=res)
            res["episode_id"] = episode_id
        except Exception as err:
            logger.warning("_run_tier0_check_after: finalize_episode failed: %s", err)

    edir = epic_dir(cwd_p)
    text = read_active_context(cwd_p)
    shape = validate_active_context_shape(text)
    st = load_epic_state(cwd_p)

    diag_codes = set(res.get("diagnostic_codes") or [])
    if res.get("diagnostic_code"):
        diag_codes.add(res["diagnostic_code"])

    # Check stale runner owner
    owner_file = edir / "runner.json"
    owner_info = load_runner_owner(owner_file)
    if owner_info and not runner_pid_alive(owner_info.pid):
        diag_codes.add("stale_owner")

    # Check active context shape
    if shape:
        diag_codes.add("active_context_shape_invalid")

    if not diag_codes and not list_open_incidents(edir) and not res.get("halt"):
        return res

    epic_id = st.get("epic_id") or st.get("armed_epic") or "unknown"
    step_id = st.get("armed_step") or "s00"
    phase = st.get("phase") or "BACK IMPLEMENT"
    session_id = st.get("session_id") or "check_after"
    fp_now = fingerprint_context(text)

    existing_open = list_open_incidents(edir)
    existing_open_codes = {c for inc in existing_open for c in inc.diagnostic_codes}

    for code in diag_codes:
        if code not in existing_open_codes:
            inc_id = compute_incident_id(
                project_root=str(cwd_p),
                epic_id=epic_id,
                step_id=step_id,
                session_id=session_id,
                diagnostic_codes=[code],
                fingerprint=fp_now,
            )
            inc_meta: dict[str, Any] = {}
            if episode_id:
                inc_meta["episode_id"] = episode_id
            rec = IncidentRecord(
                incident_id=inc_id,
                status="open",
                opened_at=datetime.now(timezone.utc).isoformat(),
                project_root=str(cwd_p),
                epic_id=epic_id,
                step_id=step_id,
                phase=phase,
                session_id=session_id,
                source="check_after",
                diagnostic_codes=[code],
                fingerprint=fp_now,
                metadata=inc_meta,
            )
            append_incident(edir, rec)

    open_incidents = list_open_incidents(edir)
    tier0_attempted = False
    tier0_resolved_ids = []
    tier0_repaired = False
    repair_exhausted = False
    tier1_eligible_flag = False

    if open_incidents:
        for inc in open_incidents:
            t0_res = run_tier0_for_incident(cwd_p, inc, decompose_path=st.get("armed_decompose"))
            if t0_res.attempted:
                tier0_attempted = True
            if t0_res.resolved:
                tier0_resolved_ids.append(inc.incident_id)
                tier0_repaired = True
            elif t0_res.repair_exhausted:
                repair_exhausted = True
                if is_tier1_eligible(inc):
                    tier1_eligible_flag = True

    remaining_open = list_open_incidents(edir)

    if tier0_repaired and not remaining_open:
        text_new = read_active_context(cwd_p)
        shape_new = validate_active_context_shape(text_new)
        if not shape_new:
            res["ok"] = True
            res["halt"] = False
            res["tier0_attempted"] = tier0_attempted
            res["tier0_repaired"] = True
            res["incidents_resolved"] = tier0_resolved_ids
            res["incidents_open_count"] = 0
            return res

    if remaining_open or repair_exhausted or res.get("halt") or shape:
        all_codes = sorted(list({c for inc in remaining_open for c in inc.diagnostic_codes} | diag_codes))
        res["halt"] = True
        res["ok"] = False
        res["diagnostic_codes"] = all_codes
        res["tier0_attempted"] = tier0_attempted
        res["tier0_repaired"] = tier0_repaired
        res["repair_exhausted"] = repair_exhausted or bool(remaining_open)
        res["tier1_eligible"] = tier1_eligible_flag or any(is_tier1_eligible(inc) for inc in remaining_open)
        res["incidents_open_count"] = len(remaining_open)
        return res

    res["tier0_attempted"] = tier0_attempted
    res["tier0_repaired"] = tier0_repaired
    if tier0_resolved_ids:
        res["incidents_resolved"] = tier0_resolved_ids
    res["incidents_open_count"] = len(remaining_open)
    return res


def check_after(
    cwd: str | Path,
    *,
    fingerprint_before: str | None = None,
) -> dict[str, Any]:
    cwd_p = Path(cwd)
    reconcile_current_epic_events(cwd_p)
    cleared_role = clear_reserved_role_arm(cwd_p)
    if cleared_role.get("cleared"):
        return {
            "ok": False,
            "halt": True,
            "reason": cleared_role.get("reason"),
            "diagnostic_code": cleared_role.get("diagnostic_code") or "armed_role_slug",
            "cleared_reserved_role_arm": True,
        }

    text = read_active_context(cwd_p)

    archived_done = complete_archived_armed_epic(cwd_p)
    if archived_done is not None:
        return archived_done

    stop = detect_stop_marker(text)
    if not stop and handoff_indicates_epic_finished(text):
        stop = "EPIC_DONE"
    if stop == "EPIC_DONE":
        fixed = resolve_premature_epic_done(cwd_p)
        if fixed is not None and fixed.get("rewrote_premature_epic_done"):
            text = read_active_context(cwd_p)
            return {
                "ok": True,
                "complete": False,
                "rewrote_premature_epic_done": True,
                "phase": fixed.get("phase"),
                "load_now": extract_load_now(text),
                "fingerprint": fingerprint_context(text),
                "reason": (
                    f"преждевременный EPIC_DONE сброшен → {fixed.get('phase')} "
                    f"(эпик DONE только после QA + REFLECT)"
                ),
            }
        if fixed is not None and fixed.get("reject_epic_done"):
            return {
                "ok": False,
                "complete": False,
                "halt": True,
                "reject_epic_done": True,
                "phase": fixed.get("phase"),
                "reason": fixed.get("reason"),
            }
    if stop:
        if stop == "EPIC_DONE":
            gate = epic_complete_allowed(cwd_p)
            if not gate.get("allowed"):
                archived_fallback = complete_archived_armed_epic(cwd_p)
                if archived_fallback is not None:
                    return archived_fallback
                return {
                    "ok": False,
                    "complete": False,
                    "halt": True,
                    "reject_epic_done": True,
                    "phase": gate.get("phase"),
                    "reason": gate.get("reason"),
                }
        st = load_epic_state(cwd_p)
        st["active"] = False
        st["status"] = "complete" if stop == "EPIC_DONE" else "halted"
        st["halt_reason"] = None if stop == "EPIC_DONE" else stop
        save_epic_state(cwd_p, st)
        return {
            "ok": True,
            "complete": True,
            "stop": stop,
            "reason": stop,
        }

    state = load_epic_state(cwd_p)
    armed_step_now = str(state.get("armed_step") or "")
    decompose = resolve_armed_decompose_for_integrity(
        cwd_p,
        armed_step=armed_step_now,
        armed_decompose=state.get("armed_decompose"),
    )
    if decompose != state.get("armed_decompose"):
        state["armed_decompose"] = decompose
        save_epic_state(cwd_p, state)
    if decompose:
        md_repair = repair_index_mirror(cwd_p, decompose)
        if not md_repair.get("ok"):
            logger.warning(
                "check_after: md mirror repair skipped (yaml remains canon): %s",
                md_repair.get("error") or md_repair,
            )
        finish_integrity = validate_finish_integrity_with_repair(
            cwd_p,
            decompose=decompose,
            step_id=armed_step_now,
            require_verify_pass=True,
        )
        if not finish_integrity["ok"]:
            archived_fallback = complete_archived_armed_epic(cwd_p)
            if archived_fallback is not None:
                return archived_fallback
            res = {
                "ok": False,
                "halt": True,
                "diagnostic_codes": finish_integrity["diagnostic_codes"],
                "reason": "; ".join(finish_integrity["errors"]),
                "repair": finish_integrity.get("repair"),
                "md_repair": md_repair,
            }
            return _run_tier0_check_after(cwd_p, res)

    fp_now = fingerprint_context(text)
    before = fingerprint_before
    if before is None:
        before = (load_epic_state(cwd_p) or {}).get("pending_fingerprint_before")

    fingerprint_repair = None
    if before and fp_now == before:
        fingerprint_repair = repair_fingerprint_stall(cwd_p)
        if fingerprint_repair.get("repaired") and fingerprint_repair.get("ok"):
            text = read_active_context(cwd_p)
            fp_now = fingerprint_context(text)
            logger.warning(
                "check_after: fingerprint stall repaired mode=%s step=%s",
                fingerprint_repair.get("mode"),
                fingerprint_repair.get("step_id"),
            )
        if before and fp_now == before:
            st_stall = load_epic_state(cwd_p)
            prev_stall_fp = st_stall.get("fingerprint_stall_fingerprint")
            if prev_stall_fp == fp_now:
                stall_count = int(st_stall.get("fingerprint_stall_count") or 0) + 1
            else:
                stall_count = 1
            max_stall = resolve_runtime_config(cwd_p).degraded_max
            st_stall["fingerprint_stall_count"] = stall_count
            st_stall["fingerprint_stall_fingerprint"] = fp_now
            if stall_count >= max_stall:
                reason = (
                    f"NEED_HUMAN: activeContext fingerprint unchanged after "
                    f"{max_stall} sessions — агент не обновил Handoff/load_now"
                )
                st_stall["active"] = False
                st_stall["status"] = "halted"
                st_stall["halt_reason"] = reason
                save_epic_state(cwd_p, st_stall)
                return {
                    "ok": False,
                    "halt": True,
                    "stop": reason,
                    "reason": reason,
                    "fingerprint_repair": fingerprint_repair,
                    "fingerprint_stall_count": stall_count,
                }
            save_epic_state(cwd_p, st_stall)
            reason = (
                "activeContext fingerprint не изменился после сессии — "
                f"outer retry {stall_count}/{max_stall} (новый агент допишет Handoff/load_now)"
            )
            logger.warning("check_after: %s", reason)
            return {
                "ok": True,
                "halt": False,
                "complete": False,
                "retry": True,
                "retry_fingerprint_stall": True,
                "reason": reason,
                "fingerprint_repair": fingerprint_repair,
                "fingerprint_stall_count": stall_count,
                "fingerprint": fp_now,
            }

    shape = validate_active_context_shape(text)
    st = load_epic_state(cwd_p)
    st["fingerprint_stall_count"] = 0
    st["fingerprint_stall_fingerprint"] = None
    save_epic_state(cwd_p, st)
    promoted = promote_decompose_phase_if_ready(cwd_p)
    if promoted is not None and not promoted.get("ok"):
        res = {
            "ok": False,
            "halt": True,
            "reason": promoted.get("error")
            or promoted.get("reason")
            or "decompose promote failed",
            "promote": promoted,
        }
        if promoted.get("diagnostic_code"):
            res["diagnostic_code"] = promoted["diagnostic_code"]
        return res
    if promoted is not None and promoted.get("ok"):
        text = read_active_context(cwd_p)
        st = load_epic_state(cwd_p)
        fp_now = fingerprint_context(text)
        shape = validate_active_context_shape(text)
    degraded = bool(shape) or not extract_load_now(text)
    if degraded:
        max_degraded = resolve_runtime_config(cwd_p).degraded_max
        count = int(st.get("degraded_count") or 0)
        if st.get("degraded_fingerprint") == fp_now:
            count += 1
        else:
            count = 1
        st["degraded_count"] = count
        st["degraded_fingerprint"] = fp_now
        save_epic_state(cwd_p, st)
        if count >= max_degraded:
            reason = (
                f"NEED_HUMAN: activeContext shape remains invalid after "
                f"{max_degraded} recovery sessions"
            )
            st["active"] = False
            st["status"] = "halted"
            st["halt_reason"] = reason
            save_epic_state(cwd_p, st)
            return {"ok": False, "halt": True, "reason": reason}
    else:
        st["degraded_count"] = 0
        st["degraded_fingerprint"] = None
        save_epic_state(cwd_p, st)
        projection = rebuild_epic_projection(cwd_p)
        cp = load_checkpoint(cwd_p)
        if cp:
            step_id = str(st.get("armed_step") or cp.get("step_id") or "").strip()
            step_completed = _checkpoint_should_advance_after_session(cwd_p, step_id)
            # Advance when index step finalized or post-implement phase finished
            # (AUDIT/QA/REFLECT/BUGFIX). Otherwise same_step — avoids committed/next_step
            # ghosts that halt re-arm with checkpoint_projection_conflict while index
            # still pending.
            checkpoint_lifecycle(
                cwd_p,
                checkpoint_id=cp["checkpoint_id"],
                session_id=cp["session_id"],
                runner_id=cp.get("runner_id"),
                identity=cp.get("identity"),
                step_id=cp["step_id"],
                phase=cp["phase"],
                phase_epoch=projection.get("phase_epoch") or cp["phase_epoch"],
                projection_hash=projection.get("projection_hash"),
                index_fingerprint=(projection.get("projection") or {}).get("index_fingerprint"),
                context_fingerprint=fp_now,
                stage="committed",
                status="committed",
                next_action="advance" if step_completed else "resume",
                resume_policy="next_step" if step_completed else "same_step",
            )
    post_phase = None
    epic_info = discover_epic_for_pipeline(cwd_p)
    if epic_info:
        post_phase, _, _ = post_implement_phase(
            cwd_p, epic_info["role_dir"], epic_info["epic_id"]
        )
    res = {
        "ok": True,
        "complete": False,
        "load_now": extract_load_now(text),
        "fingerprint": fp_now,
        "shape_errors": shape,
        "degraded": degraded,
        "fingerprint_repair": fingerprint_repair,
        "post_implement_phase": post_phase,
    }
    return _run_tier0_check_after(cwd_p, res)


def record_abort(
    cwd: str | Path,
    *,
    log_path: str | Path,
    exit_code: int,
    attempt: int = 1,
    runtime: str = "claude",
) -> dict[str, Any]:
    cwd_p = Path(cwd)
    st = load_epic_state(cwd_p)
    step_id = st.get("armed_step")
    plan_id = st.get("armed_epic")
    resume_from = step_id or "memory-bank/activeContext.md"
    try:
        dirty = git_dirty_paths(cwd_p)
    except RuntimeError:
        dirty = []

    analysis = analyze_session_log(
        Path(log_path),
        exit_code=exit_code,
        attempt=attempt,
        expected_model=(st.get("model") or None),
        runtime=st.get("runtime") if isinstance(st.get("runtime"), str) else runtime,
    )
    reason = analysis["reason"]
    retryable = analysis["retryable"]
    kind = analysis["abort_kind"]
    if not analysis["aborted"]:
        marker = write_last_session(
            cwd_p,
            track="epic",
            status="completed",
            plan_id=plan_id,
            step_id=step_id,
            resume_from=resume_from,
            dirty=dirty,
            log_file=str(log_path),
            exit_code=exit_code,
            outcome=analysis["outcome"],
            retry_count=attempt,
            resume_dirty=False,
        )
        return {
            "ok": True,
            "retryable": False,
            "abort_kind": None,
            "outcome": analysis["outcome"],
            "reason": None,
            "last_session": str(marker),
        }

    marker = write_last_session(
        cwd_p,
        track="epic",
        status="aborted",
        reason=reason,
        plan_id=plan_id,
        step_id=step_id,
        resume_from=resume_from,
        dirty=dirty,
        log_file=str(log_path),
        exit_code=exit_code,
        abort_kind=kind,
        retryable=retryable,
        outcome=analysis["outcome"],
        retry_count=attempt,
        resume_dirty=True,
    )
    if retryable:
        st["halt_reason"] = reason or "other"
        save_epic_state(cwd_p, st)
    else:
        st["status"] = "halted"
        st["halt_reason"] = reason
        save_epic_state(cwd_p, st)
    return {
        "ok": False,
        "retryable": retryable,
        "abort_kind": kind,
        "outcome": analysis["outcome"],
        "reason": reason,
        "halted": not retryable,
        "backoff_sec": analysis["backoff_sec"],
        "last_session": str(marker),
    }


_DAG_DIR = Path("loop") / "dag"


def _dag_path(cwd: str | Path, pipeline_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", pipeline_id).strip("-")
    if not safe:
        raise ValueError("pipeline_id must not be empty")
    return Path(cwd) / _DAG_DIR / f"{safe}.yaml"


def _is_fixture_dag_manifest(data: dict[str, Any]) -> bool:
    """Skip canary manifests and test-only DAG fixtures by default."""
    pipeline = data.get("pipeline") if isinstance(data.get("pipeline"), dict) else {}
    pipeline_id = str(pipeline.get("id") or data.get("pipeline_id") or "").strip()
    if not pipeline_id:
        return False
    if pipeline_id.startswith("canary-"):
        return True
    if pipeline_id.endswith("-demo") and any(
        str(node.get("id", "")).startswith(("back_", "front_", "integ_"))
        for node in data.get("nodes") or []
        if isinstance(node, dict)
    ):
        return False
    if pipeline_id.endswith("-demo"):
        return True
    source = data.get("source") if isinstance(data.get("source"), dict) else {}
    artifacts = source.get("artifacts") or []
    return any("loop/tests/" in str(item) for item in artifacts)


def _load_dag(cwd: str | Path, pipeline_id: str | None = None) -> dict[str, Any] | None:
    root = Path(cwd)
    if pipeline_id:
        paths = [_dag_path(root, pipeline_id)]
    else:
        paths = sorted((root / _DAG_DIR).glob("*.yaml"))
    candidates: list[dict[str, Any]] = []
    for path in paths:
        if not path.is_file():
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(data, dict):
            continue
        if pipeline_id:
            return data
        if _is_fixture_dag_manifest(data):
            continue
        candidates.append(data)
    if len(candidates) == 1:
        return candidates[0]
    return None


def _dag_nodes(dag: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = dag.get("nodes") or []
    return [node for node in nodes if isinstance(node, dict) and node.get("id")]


def _node_decompose_path(node: dict[str, Any]) -> str:
    target = str(node.get("decompose") or "")
    if target.startswith("memory-bank/"):
        return target
    role = str(node.get("role") or "INTEG").upper()
    role_dir = {"BACK": "back", "FRONT": "front", "INTEG": "integration"}.get(role, "integration")
    return f"memory-bank/{role_dir}/plan/{target}"


def _node_status(cwd: Path, node: dict[str, Any]) -> str:
    completion = node.get("completion") or {}
    if completion.get("type") == "artifact":
        artifact = completion.get("artifact") or node.get("artifact")
        if not isinstance(artifact, str):
            return "unknown"
        path = cwd / artifact
        if not path.is_file():
            return "pending"
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            return "unknown"
        return "done" if (
            isinstance(data, dict)
            and str(data.get("status", "")).lower() in {"closed", "complete", "completed"}
            and str(data.get("integration_gate", "")).lower() in {"pass", "passed", "ok"}
        ) else "pending"

    decompose = _node_decompose_path(node)
    idx = Path(cwd) / decompose
    if idx.is_dir():
        idx = idx / "index.md"
    try:
        from epic import find_next_decompose_step_from_queue
        from epic import load_decompose_steps_fail_closed
        loaded = load_decompose_steps_fail_closed(cwd, str(idx))
    except (OSError, TypeError, ValueError, yaml.YAMLError):
        return "unknown"
    if not loaded["ok"]:
        if loaded.get("diagnostic_code") == "index_ambiguous":
            try:
                from epic import parse_steps_from_md
                md_steps = parse_steps_from_md(idx.read_text(encoding="utf-8", errors="replace"))
            except (OSError, Exception):
                return "unknown"
            return "done" if not md_steps else "unknown"
        return "unknown"
    if find_next_decompose_step_from_queue(loaded["steps"]):
        return "pending"

    try:
        from epic import epic_complete_allowed
        return "done" if epic_complete_allowed(cwd).get("allowed") else "pending"
    except (OSError, TypeError, ValueError):
        return "pending"


def _dag_dependencies(node: dict[str, Any]) -> list[str]:
    return [str(dep) for dep in node.get("depends_on") or []]


def _dag_dependents_ready(done: set[str], nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        (
            node for node in nodes
            if str(node["id"]) not in done
            and all(dep in done for dep in _dag_dependencies(node))
        ),
        key=lambda node: str(node["id"]),
    )


def _dag_blocked(done: set[str], nodes: list[dict[str, Any]]) -> dict[str, list[str]]:
    return {
        str(node["id"]): [dep for dep in _dag_dependencies(node) if dep not in done]
        for node in nodes
        if str(node["id"]) not in done and any(dep not in done for dep in _dag_dependencies(node))
    }


def _dag_mark_completed(root: Path, dag: dict[str, Any]) -> set[str]:
    state = load_epic_state(root)
    done = set(state.get("dag_done") or [])
    for node in _dag_nodes(dag):
        if _node_status(root, node) == "done":
            done.add(str(node["id"]))
    return done


def _dag_arm_target(
    root: Path,
    dag: dict[str, Any],
    node: dict[str, Any],
    done: set[str],
    ready: list[str],
) -> dict[str, Any]:
    if (node.get("completion") or {}).get("type") == "artifact":
        return {"ok": False, "armed": False, "node": node["id"], "error": "close node has no arm target"}
    target = _node_decompose_path(node)
    armed = arm_session(root, target)
    if not armed.get("ok"):
        error = armed.get("error") or armed.get("reason")
        return {"ok": False, "armed": False, "node": node["id"], "error": error, "diagnostic": {"code": "index_invalid"}}
    pipeline_id = dag.get("pipeline", {}).get("id")
    state = load_epic_state(root)
    state.update({"dag_pipeline": pipeline_id, "dag_cursor": node["id"], "dag_done": sorted(done)})
    save_epic_state(root, state)
    return {"ok": True, "armed": True, "node": node["id"], "target": target, "ready": ready, "execution": "sequential"}

def _arm_dag_next(cwd: str | Path, pipeline_id: str | None = None) -> dict[str, Any]:
    root = Path(cwd)
    dag = _load_dag(root, pipeline_id)
    if not dag:
        if pipeline_id:
            return {"ok": False, "armed": False, "diagnostic": {"code": "dag_manifest_missing", "pipeline": pipeline_id}}
        return {"ok": True, "armed": False, "reason": "DAG manifest not found", "execution": "sequential"}
    from dag import validate_manifest
    validation = validate_manifest(dag)
    if not validation["ok"]:
        from dag import adapt_manifest
        legacy = adapt_manifest(dag)
        if not legacy.get("ok"):
            return {"ok": False, "armed": False, "diagnostic": {"code": "dag_schema_invalid", "diagnostics": validation["diagnostics"]}}
        dag = legacy["manifest"]
    state = load_epic_state(root)
    state["dag_pipeline"] = dag.get("pipeline", {}).get("id") or dag.get("pipeline_id")
    save_epic_state(root, state)
    nodes = _dag_nodes(dag)
    done = _dag_mark_completed(root, dag)
    cursor = state.get("dag_cursor")
    if cursor and cursor not in done:
        current = next((node for node in nodes if str(node["id"]) == str(cursor)), None)
        if current is not None:
            blocked = {str(cursor): _dag_dependencies(current) or ["completion_contract"]}
            return {
                "ok": True,
                "armed": False,
                "complete": False,
                "execution": "sequential",
                "diagnostic": {"code": "dag_blocked"},
                "blocked": blocked,
                "dag_done": sorted(done),
            }
    ready_nodes = _dag_dependents_ready(done, nodes)
    ready_ids = [str(node["id"]) for node in ready_nodes]
    if ready_nodes:
        if (ready_nodes[0].get("completion") or {}).get("type") == "artifact":
            node_id = str(ready_nodes[0]["id"])
            return {
                "ok": True,
                "armed": False,
                "complete": False,
                "execution": "sequential",
                "diagnostic": {"code": "dag_blocked"},
                "blocked": {node_id: ["completion_contract"]},
                "dag_done": sorted(done),
            }
        return _dag_arm_target(root, dag, ready_nodes[0], done, ready_ids)
    blocked = _dag_blocked(done, nodes)
    state = load_epic_state(root)
    state.update({"dag_done": sorted(done), "fanout_cursor": None})
    save_epic_state(root, state)
    if blocked:
        return {"ok": True, "armed": False, "complete": False, "execution": "sequential", "diagnostic": {"code": "dag_blocked"}, "blocked": blocked, "dag_done": sorted(done)}
    return {"ok": True, "armed": False, "complete": bool(nodes) and len(done) == len(nodes), "execution": "sequential", "dag_done": sorted(done)}


def dag_fanout(cwd: str | Path) -> dict[str, Any]:
    """Arm the next dependency-ready epic from the runner-owned DAG manifest."""
    return _arm_dag_next(cwd)


def _status_session(root: Path, state: dict[str, Any]) -> dict[str, Any]:
    session = load_last_session(root) or {}
    return {
        "id": state.get("session_id") or session.get("session_id"),
        "started_at": state.get("started_at") or session.get("started_at"),
        "ended_at": session.get("updated_at"),
        "exit_code": session.get("exit_code"),
        "abort_kind": session.get("abort_kind"),
        "outcome": session.get("outcome"),
        "retry_count": session.get("retry_count", state.get("retry_count", 0)),
        "log_path": session.get("log_file"),
    }


def _status_event(root: Path, projection: dict[str, Any]) -> dict[str, Any]:
    epic_id = projection.get("epic_id")
    role = projection.get("role")
    if not epic_id or not role:
        return {
            "last_seq": None,
            "last_kind": None,
            "last_artifact": None,
            "stream_digest": projection.get("event_digest"),
            "archive_count": 0,
            "invalid_count": 0,
        }
    from epic_events import read_event_log_result

    result = read_event_log_result(
        _event_log_path(root, str(role).lower(), str(epic_id)),
        expected_epic_id=str(epic_id),
        cwd=root,
    )
    last = result.events[-1] if result.events else {}
    return {
        "last_seq": last.get("seq"),
        "last_kind": last.get("kind"),
        "last_artifact": last.get("artifact"),
        "stream_digest": f"sha256:{__import__('epic_events').event_stream_digest(result)}",
        "archive_count": result.archive_count,
        "invalid_count": result.invalid_count,
    }


def _status_dag(root: Path, state: dict[str, Any], dag: dict[str, Any] | None) -> dict[str, Any]:
    nodes = _dag_nodes(dag) if dag else []
    done = {str(item) for item in state.get("dag_done", [])}
    ready = [str(node.get("id")) for node in nodes if str(node.get("id")) not in done]
    return {
        "pipeline_id": (dag or {}).get("pipeline", {}).get("id") or (dag or {}).get("pipeline_id") or state.get("dag_pipeline"),
        "manifest": state.get("dag_pipeline"),
        "execution": (dag or {}).get("execution", "sequential"),
        "current_node": state.get("dag_cursor"),
        "ready_nodes": ready,
        "dependency_blockers": (dag or {}).get("blocked", {}),
        "diagnostics": (dag or {}).get("diagnostic"),
    }


def _status_checkpoint(root: Path) -> dict[str, Any]:
    from epic import load_checkpoint

    checkpoint = load_checkpoint(root)
    if checkpoint is None:
        return {"status": "none", "checkpoint_seq": None, "step_id": None, "diagnostic": None}
    return {
        "status": checkpoint.get("status"),
        "stage": checkpoint.get("stage"),
        "checkpoint_seq": checkpoint.get("checkpoint_seq"),
        "step_id": checkpoint.get("step_id"),
        "next_action": checkpoint.get("next_action"),
        "resume_policy": checkpoint.get("resume_policy"),
        "diagnostic": None,
    }


def _status_agent_policy(root: Path, state: dict[str, Any]) -> dict[str, Any]:
    """Return bounded registry and policy state for loop observability."""
    context = AgentContext.LOOP if is_epic_loop_env() else AgentContext.CHAT
    registry = discover_registry(root)
    project_env = merged_project_env_map(root)
    active: list[str] = []
    inactive: list[dict[str, str]] = []
    gates: dict[str, dict[str, bool]] = {}
    diagnostics_by_agent: dict[str, list[str]] = {}
    errors: list[dict[str, str | None]] = []

    for diagnostic in registry.diagnostics:
        item = {
            "code": str(diagnostic.code),
            "agent_id": diagnostic.agent_id,
            "key": diagnostic.key,
        }
        errors.append(item)
        if diagnostic.agent_id:
            diagnostics_by_agent.setdefault(diagnostic.agent_id, []).append(str(diagnostic.code))

    for definition in registry.definitions:
        if not definition.managed:
            continue
        policy = resolve_agent_policy(
            definition.id,
            context,
            env=os.environ,
            project_env=project_env,
            metadata={
                "enabled_loop": "1" if definition.loop_enabled else "0",
                "enabled_chat": "1" if definition.chat_enabled else "0",
                "model": definition.model or "inherit",
            },
        )
        is_active = definition.runnable and policy.error is None and policy.enabled
        if is_active:
            active.append(definition.id)
        else:
            reason = diagnostics_by_agent.get(definition.id, [])
            if policy.error is not None:
                reason = [str(policy.error.value)]
            elif not definition.runnable and not reason:
                reason = ["not_runnable"]
            elif not policy.enabled and not reason:
                reason = [f"{context.value}_disabled"]
            inactive.append({"id": definition.id, "reason": reason[0]})

        if definition.mode == "gate":
            gates[definition.id] = {
                "required": bool(state.get(f"need_{definition.id}")),
                "active": is_active,
                "done": bool(state.get(f"{definition.id}_done")),
            }

    return {
        "context": context.value,
        "workflow_policy": workflow_policy(root),
        "registry_revision": registry.revision,
        "active": sorted(active),
        "inactive": sorted(inactive, key=lambda item: item["id"]),
        "errors": errors,
        "gates": gates,
    }


def status(cwd: str | Path) -> dict[str, Any]:
    root = Path(cwd)
    projection_state = rebuild_epic_projection(root)
    text = read_active_context(root)
    st = load_epic_state(root)
    projection = projection_state.get("projection") or {}
    dag = _load_dag(root, st.get("dag_pipeline"))
    owner = runner_owner_status(root / ".claude" / "runtime" / "epic")
    if not owner.get("owner") and hub_root() != root:
        owner = runner_owner_status(runtime_dir(root))
    try:
        config = runtime_config_status(resolve_runtime_config(root))
    except (RuntimeError, ValueError) as exc:
        config = {"effective": None, "sources": {}, "diagnostics": [{"code": "invalid_runtime_config", "reason": str(exc)}]}
    gates = projection.get("gates") or gates_from_phase(projection.get("phase"))
    raw_diagnostics = projection.get("diagnostic_codes") or []
    diagnostics = sorted({code for code in raw_diagnostics if isinstance(code, str)})
    if any(not isinstance(code, str) for code in raw_diagnostics):
        diagnostics.append("invalid_diagnostic_codes")
    if owner.get("owner") and not owner.get("owner_alive"):
        diagnostics.append("stale_owner")
    finish_integrity = {
        "ok": True,
        "errors": [],
        "diagnostic_codes": [],
        "armed_epic": st.get("armed_epic"),
        "armed_step": st.get("armed_step"),
    }
    if st.get("armed_decompose"):
        integrity = validate_finish_integrity(
            root,
            decompose=st["armed_decompose"],
            step_id=str(st.get("armed_step") or ""),
            require_verify_pass=True,
        )
        finish_integrity.update(
            ok=integrity["ok"],
            errors=integrity["errors"],
            diagnostic_codes=integrity["diagnostic_codes"],
        )
    return {
        "ok": True,
        "schema": "loop-status/v1",
        "shape_errors": validate_active_context_shape(text),
        "stop": detect_stop_marker(text),
        "load_now": extract_load_now(text),
        "fingerprint": fingerprint_context(text) if text.strip() else None,
        "runner": owner,
        "session": _status_session(root, st),
        "projection": projection,
        "projection_hash": projection.get("projection_hash"),
        "phase_epoch": projection.get("phase_epoch"),
        "event": _status_event(root, projection),
        "gates": gates,
        "dag": _status_dag(root, st, dag),
        "recovery": {
            "state_rebuilt": "state_rebuilt" in diagnostics,
            "degraded_count": st.get("degraded_count", 0),
            "last_stop_marker": detect_stop_marker(text),
            "halt_reason": st.get("halt_reason"),
            "diagnostics": diagnostics,
        },
        "checkpoint": _status_checkpoint(root),
        "configuration": config,
        "finish_integrity": finish_integrity,
        "agent_policy": _status_agent_policy(root, st),
        "incidents": _status_incidents(root),
        "metrics": _status_metrics(root),
        "trace_tail": _status_trace_tail(root),
    }


def _status_incidents(cwd: Path) -> dict[str, Any]:
    from epic_paths import epic_dir as get_epic_dir
    from loop.incidents.store import CorruptIncidentError, parse_incidents_jsonl

    edir = get_epic_dir(cwd)
    try:
        records = parse_incidents_jsonl(edir / "incidents.jsonl")
    except CorruptIncidentError:
        return {"open_count": 0, "last": [], "incidents_corrupt": True}
    except Exception:
        return {"open_count": 0, "last": []}

    open_recs = [r for r in records if r.status == "open"]
    last_recs = open_recs[:5]
    clean_last = []
    for r in last_recs:
        d = r.model_dump(by_alias=True, exclude_none=True)
        d.pop("prompt", None)
        d.pop("secrets", None)
        clean_last.append(d)
    return {
        "open_count": len(open_recs),
        "last": clean_last,
    }


def _status_metrics(cwd: Path) -> dict[str, Any]:
    from epic_paths import epic_dir as get_epic_dir
    from loop.incidents.metrics import load_metrics

    edir = get_epic_dir(cwd)
    try:
        m = load_metrics(edir)
        return m.model_dump(by_alias=True, exclude_none=True)
    except Exception:
        return {"counters": {}, "rates": {}}


def _status_trace_tail(cwd: Path) -> list[dict[str, Any]]:
    from epic_paths import epic_dir as get_epic_dir
    from loop.incidents.trace import read_session_trace_tail

    edir = get_epic_dir(cwd)
    try:
        tail = read_session_trace_tail(edir, limit=10)
        clean_tail = []
        for entry in tail:
            e = dict(entry)
            if "detail" in e and isinstance(e["detail"], dict):
                e["detail"] = {
                    k: v
                    for k, v in e["detail"].items()
                    if k not in ("prompt", "secrets", "secret_prompt")
                }
            clean_tail.append(e)
        return clean_tail
    except Exception:
        return []


def _cmd_dag_generate(cwd: str | Path, pipeline_id: str) -> dict[str, Any]:
    from dag import validate_manifest

    root = Path(cwd)
    gap_dir = root / "memory-bank" / "integration" / "gap"
    gaps = (
        sorted(gap_dir.glob("**/gap-*.yaml"))
        + sorted(gap_dir.glob("**/gap-*.yml"))
        + sorted(gap_dir.glob("**/gap-*.md"))
    )
    nodes: list[dict[str, Any]] = []
    source_artifacts: list[str] = []
    legacy = False
    for gap in gaps:
        try:
            data = {} if gap.suffix == ".md" else (yaml.safe_load(gap.read_text(encoding="utf-8")) or {})
        except (OSError, yaml.YAMLError):
            continue
        if gap.suffix == ".md" or not isinstance(data, dict):
            legacy = True
            source_artifacts.append(gap.relative_to(root).as_posix())
            text = gap.read_text(encoding="utf-8", errors="replace")
            links = list(dict.fromkeys(re.findall(r"decompose-[A-Za-z0-9._-]+", text)))
            data = {
                "back": {"decompose": f"memory-bank/back/plan/{links[0]}/index.md"}
                if links else {},
                "front": {"decompose": f"memory-bank/front/plan/{links[1]}/index.md"}
                if len(links) > 1 else {},
            }
        elif not isinstance(data, dict):
            continue
        if not isinstance(data, dict):
            continue
        if gap.suffix != ".md":
            source_artifacts.append(gap.relative_to(root).as_posix())
        gap_id = gap.stem
        close_id = f"{gap_id}-close"
        nodes.append({
            "id": close_id,
            "role": "INTEG",
            "artifact": gap.relative_to(root).as_posix(),
            "depends_on": [],
            "completion": {"type": "artifact"},
            "action": "close",
        })
        for role in ("BACK", "FRONT"):
            entry = data.get(role.lower()) or data.get(role)
            if not isinstance(entry, dict):
                continue
            decompose = entry.get("decompose")
            if not isinstance(decompose, str):
                continue
            from epic_paths import epic_id_from_decompose_path, is_reserved_role_epic_id

            epic_from_path = epic_id_from_decompose_path(decompose)
            if is_reserved_role_epic_id(epic_from_path):
                return {
                    "ok": False,
                    "path": None,
                    "nodes": nodes,
                    "diagnostics": [
                        {
                            "code": "epic_id_reserved",
                            "message": (
                                f"gap decompose epic_id must not be a role slug: "
                                f"{epic_from_path!r} (path={decompose})"
                            ),
                            "gap": gap.relative_to(root).as_posix(),
                        }
                    ],
                }
            node_id = f"{gap_id}-{role.lower()}"
            nodes.append({
                "id": node_id,
                "role": role,
                "decompose": decompose,
                "depends_on": [],
                "completion": {"type": "decompose"},
                "action": "implement",
            })
            nodes[0]["depends_on"].append(node_id)
    manifest = {
        "schema": "loop-dag/v2",
        "pipeline": {"id": pipeline_id},
        "source": {"kind": "integration_gap", "artifacts": source_artifacts or [f"memory-bank/integration/gap/{pipeline_id}"]},
        "execution": {"autonomous": not legacy},
        "nodes": nodes,
    }
    result = validate_manifest(manifest)
    if not result["ok"]:
        return {"ok": False, "path": None, "nodes": nodes, "diagnostics": result["diagnostics"]}
    if legacy:
        result["diagnostics"].append({"code": "legacy_gap_inference", "message": "legacy gap links are compatibility-only"})
    path = _dag_path(root, pipeline_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return {"ok": True, "path": path.relative_to(root).as_posix(), "nodes": nodes, "diagnostics": []}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Context-first loop CLI")
    parser.add_argument(
        "--cwd",
        default=(os.environ.get("PROJECT_ROOT") or "").strip() or str(ROOT),
        help="Product repo root (memory-bank/). Default: $PROJECT_ROOT or hub root.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_prep = sub.add_parser("prepare", help="Build prompt + fingerprint before session")
    p_prep.add_argument("--model", default=None)
    p_prep.add_argument("--runtime", choices=["claude", "dsh"], default=None)

    p_arm = sub.add_parser(
        "arm",
        help="Arm epic via resolver (epic id, plan path, or legacy decompose path)",
    )
    p_arm.add_argument(
        "--epic",
        required=True,
        help="Epic id (T-HUB-029), plan-*.md, or decompose-<id>[/index.md] (legacy)",
    )

    p_after = sub.add_parser("check-after", help="Inspect activeContext after session")
    p_after.add_argument("--fingerprint-before", default=None)

    p_rec = sub.add_parser("record-session", help="Classify abort from session log")
    p_rec.add_argument("--log", required=True)
    p_rec.add_argument("--exit-code", type=int, default=0)
    p_rec.add_argument("--attempt", type=int, default=1)
    p_rec.add_argument("--runtime", choices=["claude", "dsh"], default=None)

    p_fanout = sub.add_parser("dag-fanout", help="Arm the next DAG node")
    p_fanout.add_argument("--pipeline", default=None)

    p_generate = sub.add_parser(
        "dag-generate", help="Generate DAG from integ gap artifacts"
    )
    p_generate.add_argument("--pipeline", required=True)

    sub.add_parser(
        "roadmap-advance",
        help="Arm next epic from roadmap Queue (EPIC_CHAIN_ROADMAP)",
    )

    p_merge = sub.add_parser(
        "roadmap-merge",
        help="Merge roadmap-*-epics.queue.yaml into roadmap-epics.queue.yaml",
    )
    p_merge.add_argument(
        "--role",
        default="back",
        choices=["back", "front", "integration"],
        help="Plan role directory (default: back)",
    )
    p_merge.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute merge without writing files",
    )
    p_merge.add_argument(
        "--no-md",
        action="store_true",
        help="Do not write sibling roadmap-epics.md",
    )

    sub.add_parser("status", help="Show context cursor")

    p_doc = sub.add_parser("doctor", help="Preflight check before autopilot")
    p_doc.add_argument(
        "--auto-repair",
        action="store_true",
        help="Attempt safe automatic remediation for stale locks / corrupt records",
    )
    p_doc.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (text or json)",
    )

    p_istatus = sub.add_parser("incident-status", help="Show incident store status")
    p_istatus.add_argument("--json", action="store_true", help="Output JSON format")

    p_iretry = sub.add_parser("incident-retry", help="Retry a tier1 incident")
    p_iretry.add_argument("incident_id", help="Incident ID to retry")

    p_eplist = sub.add_parser("episode-list", help="List episode packages manifests")
    p_eplist.add_argument("--last", type=int, default=None, help="Limit output to last N episodes")
    p_eplist.add_argument("--json", action="store_true", help="Output JSON format")

    p_epshow = sub.add_parser("episode-show", help="Show episode package detail")
    p_epshow.add_argument("episode_id", help="Episode ID to show")
    p_epshow.add_argument("--json", action="store_true", help="Output JSON format")

    args = parser.parse_args(argv)
    cwd = args.cwd

    if args.cmd == "arm":
        out = arm_session(cwd, args.epic)
        print(json.dumps(out, ensure_ascii=False))
        if out.get("complete"):
            return 3
        return 0 if out.get("ok") else 1

    if args.cmd == "prepare":
        out = prepare_session(cwd, model=args.model, runtime=args.runtime)
        print(json.dumps(out, ensure_ascii=False))
        if out.get("complete"):
            return 3
        return 0 if out.get("ok") else 1

    if args.cmd == "check-after":
        out = check_after(cwd, fingerprint_before=args.fingerprint_before)
        print(json.dumps(out, ensure_ascii=False))
        if out.get("complete"):
            return 3
        if out.get("halt"):
            return 1
        return 0 if out.get("ok") else 1

    if args.cmd == "record-session":
        out = record_abort(
            cwd,
            log_path=args.log,
            exit_code=args.exit_code,
            attempt=args.attempt,
            runtime=args.runtime or "claude",
        )
        print(json.dumps(out, ensure_ascii=False))
        if out.get("ok"):
            return 0
        if out.get("retryable"):
            return 3
        return 1

    if args.cmd == "dag-fanout":
        out = _arm_dag_next(cwd, args.pipeline)
        if out.get("armed"):
            out["phase"] = "GAP_FANOUT"
        if out.get("complete"):
            out["phase"] = "DONE"
        print(json.dumps(out, ensure_ascii=False, indent=2))
        if out.get("complete"):
            return 3
        return 0 if out.get("ok") else 1

    if args.cmd == "dag-generate":
        out = _cmd_dag_generate(cwd, args.pipeline)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0 if out.get("ok") else 1

    if args.cmd == "roadmap-advance":
        from roadmap_queue import roadmap_advance

        out = roadmap_advance(cwd)
        print(json.dumps(out, ensure_ascii=False))
        if out.get("complete"):
            return 3
        if out.get("halt") and not out.get("armed"):
            return 1
        return 0 if out.get("ok") and out.get("armed") else 1

    if args.cmd == "roadmap-merge":
        from roadmap_queue import roadmap_merge

        out = roadmap_merge(
            cwd,
            role=args.role,
            dry_run=bool(args.dry_run),
            write_md=not bool(args.no_md),
        )
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out.get("ok") else 1

    if args.cmd == "status":
        print(json.dumps(status(cwd), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "doctor":
        from loop.incidents.doctor import run_doctor

        rep = run_doctor(cwd, auto_repair=bool(args.auto_repair), format=args.format)
        if args.format == "json":
            out = {
                "ok": rep.exit_code == 0,
                "exit_code": rep.exit_code,
                "checklist": [
                    {"name": c.name, "status": c.status, "detail": c.detail}
                    for c in rep.checklist
                ],
                "blockers": rep.blockers,
                "warnings": rep.warnings,
            }
            print(json.dumps(out, ensure_ascii=False, indent=2))
        else:
            for c in rep.checklist:
                symbol = "✓" if c.status == "pass" else ("⚠" if c.status == "warn" else ("⁃" if c.status == "skipped" else "✗"))
                detail_str = f" ({c.detail})" if c.detail else ""
                print(f"[{symbol}] {c.name}: {c.status}{detail_str}")
            if rep.blockers:
                print("\nBlockers:")
                for b in rep.blockers:
                    print(f"  - {b}")
            if rep.warnings:
                print("\nWarnings:")
                for w in rep.warnings:
                    print(f"  - {w}")
        return rep.exit_code

    if args.cmd == "incident-status":
        from epic_paths import epic_dir
        from loop.incidents.store import parse_incidents_jsonl
        edir = epic_dir(cwd)
        incidents_file = edir / "incidents.jsonl"
        all_incidents = parse_incidents_jsonl(incidents_file) if incidents_file.is_file() else []
        open_incidents = [r for r in all_incidents if r.status == "open"]
        res = {
            "ok": True,
            "total_count": len(all_incidents),
            "open_count": len(open_incidents),
            "incidents": [inc.model_dump(by_alias=True) for inc in all_incidents],
        }
        if getattr(args, "json", False):
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            print(f"Found {len(open_incidents)} open incidents (total: {len(all_incidents)}):")
            for inc in open_incidents:
                print(f"  - {inc.incident_id}: {inc.diagnostic_codes} (attempts: {inc.tier0_attempts})")
        return 0

    if args.cmd == "incident-retry":
        from epic_paths import epic_dir
        from loop.incidents.store import parse_incidents_jsonl, reset_tier1_attempts
        from loop.incidents.tier1 import is_tier1_eligible
        edir = epic_dir(cwd)
        incidents_file = edir / "incidents.jsonl"
        all_incidents = parse_incidents_jsonl(incidents_file) if incidents_file.is_file() else []
        target = next((r for r in all_incidents if r.incident_id == args.incident_id), None)
        if not target:
            sys.stderr.write(f"Error: incident {args.incident_id} not found\n")
            return 1
        if not is_tier1_eligible(target):
            sys.stderr.write(f"Error: incident {args.incident_id} is not eligible for tier1 retry\n")
            return 1
        reset_tier1_attempts(edir, args.incident_id)
        print(f"Incident {args.incident_id} reset. Ready for tier1 retry on next loop iteration.")
        return 0

    if args.cmd == "episode-list":
        from loop.episodes.cli import episode_list, format_episode_list, scan_episodes

        if getattr(args, "json", False):
            res = episode_list(cwd, last=args.last)
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            manifests = scan_episodes(cwd)
            if args.last is not None and args.last > 0:
                manifests = manifests[:args.last]
            print(format_episode_list(manifests))
        return 0

    if args.cmd == "episode-show":
        from loop.episodes.cli import show_episode

        try:
            res = show_episode(cwd, args.episode_id)
            print(json.dumps(res, ensure_ascii=False, indent=2))
            return 0
        except FileNotFoundError as err:
            sys.stderr.write(f"Error: {err}\n")
            return 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
