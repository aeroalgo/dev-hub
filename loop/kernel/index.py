from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from .store import FileMutation


SUPPORTED_ROLES = ("back", "front", "integration")


@dataclass(frozen=True)
class Step:
    step_id: str
    status: str
    title: str
    shard: str | None


@dataclass(frozen=True)
class Queue:
    path: Path
    role: str
    epic_id: str
    steps: tuple[Step, ...]
    kind: str = "feature"

    @property
    def pending(self) -> tuple[Step, ...]:
        return tuple(step for step in self.steps if step.status not in {"completed", "done"})


EpicKind = Literal["feature", "refactor", "security"]
SUPPORTED_KINDS: tuple[EpicKind, ...] = ("feature", "refactor", "security")


def normalize_role(role: str) -> str:
    value = str(role or "").strip().lower()
    if value == "integ":
        value = "integration"
    if value not in SUPPORTED_ROLES:
        raise ValueError(f"unsupported role: {role!r}")
    return value


def normalize_kind(kind: str | None) -> EpicKind:
    value = str(kind or "feature").strip().lower()
    if value not in SUPPORTED_KINDS:
        raise ValueError(f"unsupported kind: {kind!r}")
    return value  # type: ignore[return-value]


def plan_root(kind_or_project: Path | str = "feature", role: str | None = None, kind: str | None = None) -> Path:
    if isinstance(kind_or_project, Path):
        project = kind_or_project
        if role is None:
            raise ValueError("role required when project path is provided")
        k = normalize_kind(kind or "feature")
        sub = Path("plan") if k == "feature" else Path(k) / "plan"
        return project / "memory-bank" / normalize_role(role) / sub
    k = normalize_kind(kind_or_project)
    return Path("plan") if k == "feature" else Path(k) / "plan"


def index_path(project: Path, role: str, epic_id: str, kind: str = "feature") -> Path:
    if not epic_id or Path(epic_id).name != epic_id:
        raise ValueError(f"invalid epic id: {epic_id!r}")
    return plan_root(project, role, kind) / epic_id / "yaml" / "decompose-index.yaml"


def plan_path(project: Path, role: str, epic_id: str, kind: str = "feature") -> Path:
    if not epic_id or Path(epic_id).name != epic_id:
        raise ValueError(f"invalid epic id: {epic_id!r}")
    return plan_root(project, role, kind) / epic_id / "md" / "plan.md"


def discover_epic_kinds(project: Path, epic_id: str, role: str | None = None) -> list[EpicKind]:
    if not epic_id or Path(epic_id).name != epic_id:
        raise ValueError(f"invalid epic id: {epic_id!r}")
    roles = [normalize_role(role)] if role and str(role).strip().lower() != "auto" else list(SUPPORTED_ROLES)
    found: list[EpicKind] = []
    for kind in SUPPORTED_KINDS:
        for r in roles:
            if plan_path(project, r, epic_id, kind=kind).is_file() or index_path(project, r, epic_id, kind=kind).is_file():
                if kind not in found:
                    found.append(kind)
                break
    return found


def discover_epic_roles(project: Path, epic_id: str, kind: str | None = None) -> list[str]:
    if not epic_id or Path(epic_id).name != epic_id:
        raise ValueError(f"invalid epic id: {epic_id!r}")
    kinds = [normalize_kind(kind)] if kind else list(SUPPORTED_KINDS)
    found: list[str] = []
    for role in SUPPORTED_ROLES:
        for k in kinds:
            if plan_path(project, role, epic_id, kind=k).is_file() or index_path(project, role, epic_id, kind=k).is_file():
                if role not in found:
                    found.append(role)
                break
    return found


def _all_searched_plan_roots(epic_id: str, roles: tuple[str, ...] | list[str] = SUPPORTED_ROLES) -> list[str]:
    roots: list[str] = []
    for r in roles:
        for k in SUPPORTED_KINDS:
            sub = "plan" if k == "feature" else f"{k}/plan"
            roots.append(f"memory-bank/{r}/{sub}/{epic_id}/md/plan.md")
    return roots


def resolve_epic_kind(project: Path, epic_id: str, kind: str | None = None, role: str | None = None) -> EpicKind:
    if kind is not None and str(kind).strip().lower() not in {"", "auto"}:
        normalized = normalize_kind(kind)
        kinds = discover_epic_kinds(project, epic_id, role=role)
        if kinds and normalized not in kinds:
            raise FileNotFoundError(
                f"canonical plan missing for kind {normalized!r}: {epic_id} "
                f"(epic exists under kind(s) {kinds}; pass --kind {kinds[0]})"
            )
        if not kinds:
            target_roles = [normalize_role(role)] if role and role != "auto" else SUPPORTED_ROLES
            searched = _all_searched_plan_roots(epic_id, target_roles)
            raise FileNotFoundError(f"canonical plan missing: searched roots {', '.join(searched)}")
        return normalized
    kinds = discover_epic_kinds(project, epic_id, role=role)
    if not kinds:
        target_roles = [normalize_role(role)] if role and role != "auto" else SUPPORTED_ROLES
        searched = _all_searched_plan_roots(epic_id, target_roles)
        raise FileNotFoundError(f"canonical plan missing: searched roots {', '.join(searched)}")
    if len(kinds) > 1:
        raise ValueError(f"ambiguous epic {epic_id!r} found in kinds {kinds}; pass --kind explicitly")
    return kinds[0]


def resolve_epic_role(project: Path, epic_id: str, role: str | None = "auto", kind: str | None = None) -> str:
    requested_role = str(role or "auto").strip().lower()
    if kind is not None and str(kind).strip().lower() not in {"", "auto"}:
        target_kind = normalize_kind(kind)
        if requested_role in {"", "auto"}:
            found = discover_epic_roles(project, epic_id, kind=target_kind)
            if not found:
                other_kinds = discover_epic_kinds(project, epic_id)
                if other_kinds:
                    raise FileNotFoundError(
                        f"canonical plan missing for kind {target_kind!r}: {epic_id} "
                        f"(epic exists under kind(s) {other_kinds}; pass --kind {other_kinds[0]})"
                    )
                searched = _all_searched_plan_roots(epic_id)
                raise FileNotFoundError(f"canonical plan missing: searched roots {', '.join(searched)}")
            if len(found) > 1:
                raise ValueError(
                    f"ambiguous epic {epic_id!r} found in roles {found}; pass --role explicitly"
                )
            return found[0]
        normalized = normalize_role(requested_role)
        plan = plan_path(project, normalized, epic_id, kind=target_kind)
        index = index_path(project, normalized, epic_id, kind=target_kind)
        if plan.is_file() or index.is_file():
            return normalized
        elsewhere = discover_epic_roles(project, epic_id, kind=target_kind)
        if elsewhere:
            raise FileNotFoundError(
                f"canonical plan missing: {plan} "
                f"(epic exists under role(s) {elsewhere}; pass --role {elsewhere[0]})"
            )
        other_kinds = discover_epic_kinds(project, epic_id, role=normalized)
        if other_kinds:
            raise FileNotFoundError(
                f"canonical plan missing for kind {target_kind!r}: {plan} "
                f"(epic exists under kind(s) {other_kinds}; pass --kind {other_kinds[0]})"
            )
        searched = _all_searched_plan_roots(epic_id, [normalized])
        raise FileNotFoundError(f"canonical plan missing: searched roots {', '.join(searched)}")

    target_role = requested_role if requested_role not in {"", "auto"} else None
    if target_role is not None:
        normalized = normalize_role(target_role)
        if not discover_epic_kinds(project, epic_id, role=normalized):
            elsewhere = discover_epic_roles(project, epic_id)
            if elsewhere:
                plan = plan_path(project, normalized, epic_id, kind="feature")
                raise FileNotFoundError(
                    f"canonical plan missing: {plan} "
                    f"(epic exists under role(s) {elsewhere}; pass --role {elsewhere[0]})"
                )
    resolved_kind = resolve_epic_kind(project, epic_id, role=target_role)
    return resolve_epic_role(project, epic_id, role=requested_role, kind=resolved_kind)


def load_queue(project: Path, role: str, epic_id: str, kind: str | None = None) -> Queue:
    resolved_kind = kind
    if resolved_kind is not None:
        path = index_path(project, role, epic_id, kind=resolved_kind)
    else:
        default_path = index_path(project, role, epic_id, kind="feature")
        if default_path.is_file():
            path = default_path
            resolved_kind = "feature"
        else:
            kinds = discover_epic_kinds(project, epic_id, role=role)
            if len(kinds) == 1:
                resolved_kind = kinds[0]
                path = index_path(project, role, epic_id, kind=resolved_kind)
            else:
                resolved_kind = "feature"
                path = default_path
    if not path.is_file():
        raise FileNotFoundError(f"canonical decompose index missing: {path}")
    payload = _load_yaml_mapping(path)
    if not isinstance(payload.get("steps"), list):
        raise ValueError(f"invalid decompose index: {path}")
    steps: list[Step] = []
    for raw in payload["steps"]:
        if not isinstance(raw, dict):
            raise ValueError(f"invalid step entry in {path}")
        step_id = str(raw.get("id") or raw.get("step_id") or "").strip()
        if not step_id:
            raise ValueError(f"step without id in {path}")
        steps.append(
            Step(
                step_id=step_id,
                status=str(raw.get("status") or "pending").lower(),
                title=str(raw.get("title") or step_id),
                shard=str(raw.get("file") or raw.get("shard") or "") or None,
            )
        )
    return Queue(path=path, role=normalize_role(role), epic_id=epic_id, steps=tuple(steps), kind=normalize_kind(resolved_kind))


# YAML 1.1 double-quoted single-char escapes (plus \x / \u / \U handled separately).
_YAML_DQ_ONE_CHAR_ESCAPES = frozenset('0abtnvfre N_LP"\\/')


def repair_yaml_double_quoted_escapes(text: str) -> tuple[str, int]:
    """Fix invalid ``\\.``-style escapes inside double-quoted scalars.

    Authors mean a literal backslash for ``rg``; YAML double-quotes reject most
    ``\\X`` sequences. Doubling the backslash preserves the intended string value.
    """
    out: list[str] = []
    repairs = 0
    i = 0
    n = len(text)
    in_dq = False
    while i < n:
        ch = text[i]
        if not in_dq:
            out.append(ch)
            if ch == '"':
                in_dq = True
            i += 1
            continue
        if ch == "\\" and i + 1 < n:
            nxt = text[i + 1]
            if nxt in _YAML_DQ_ONE_CHAR_ESCAPES:
                out.append(ch)
                out.append(nxt)
                i += 2
                continue
            if nxt == "x" and i + 3 < n and all(c in "0123456789abcdefABCDEF" for c in text[i + 2 : i + 4]):
                out.append(text[i : i + 4])
                i += 4
                continue
            if nxt == "u" and i + 5 < n and all(c in "0123456789abcdefABCDEF" for c in text[i + 2 : i + 6]):
                out.append(text[i : i + 6])
                i += 6
                continue
            if nxt == "U" and i + 9 < n and all(c in "0123456789abcdefABCDEF" for c in text[i + 2 : i + 10]):
                out.append(text[i : i + 10])
                i += 10
                continue
            out.append("\\\\")
            out.append(nxt)
            repairs += 1
            i += 2
            continue
        if ch == '"':
            in_dq = False
        out.append(ch)
        i += 1
    return "".join(out), repairs


_DECOMPOSE_LIST_FIELDS = (
    "as_built",
    "delta",
    "deletes",
    "out_of_scope",
    "checkpoints",
    "verify",
    "tdd",
)


def _coerce_decompose_list_value(value: Any) -> tuple[list[Any], bool]:
    """Normalize bool/scalar mistaken for a list field. Returns (list, changed)."""
    if isinstance(value, list):
        return value, False
    if value is None or value is False or value is True:
        return [], True
    if isinstance(value, str):
        text = value.strip()
        return ([text] if text else []), True
    return [value], True


def normalize_decompose_list_fields(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Rewrite shard when list fields were authored as bool/scalar (e.g. ``tdd: true``)."""
    changed_fields: list[str] = []
    for field in _DECOMPOSE_LIST_FIELDS:
        if field not in payload:
            continue
        coerced, changed = _coerce_decompose_list_value(payload.get(field))
        if changed:
            payload[field] = coerced
            changed_fields.append(field)
    if not changed_fields:
        return payload
    raw = path.read_text(encoding="utf-8")
    lines = raw.splitlines(keepends=True)
    out: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        indent = line[: len(line) - len(stripped)]
        replaced = False
        for field in changed_fields:
            # Only top-level keys (no leading spaces beyond indent of root mapping).
            if re.match(rf"^{re.escape(field)}\s*:", stripped):
                newline = "\n" if line.endswith("\n") else ""
                out.append(f"{indent}{field}: []{newline}")
                replaced = True
                break
        if not replaced:
            out.append(line)
    path.write_text("".join(out), encoding="utf-8")
    return payload


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    try:
        payload = yaml.safe_load(raw) or {}
    except yaml.YAMLError:
        repaired, count = repair_yaml_double_quoted_escapes(raw)
        if count <= 0 or repaired == raw:
            try:
                yaml.safe_load(raw)
            except yaml.YAMLError as exc:
                raise ValueError(
                    f"invalid YAML (unrecoverable): {path}: {exc}"
                ) from exc
        try:
            payload = yaml.safe_load(repaired) or {}
        except yaml.YAMLError as exc:
            raise ValueError(
                f"invalid YAML after escape repair: {path}: {exc}"
            ) from exc
        path.write_text(repaired, encoding="utf-8")
    if not isinstance(payload, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return payload


def purge_orphan_decompose_shards(steps_root: Path, referenced: set[Path]) -> list[str]:
    """Delete steps/*.yaml not listed in the decompose index. Returns removed names."""
    if not steps_root.is_dir():
        return []
    removed: list[str] = []
    for path in sorted(steps_root.glob("*.yaml")):
        if path.resolve() not in referenced:
            path.unlink()
            removed.append(path.name)
    return removed


def decompose_yaml_problems(project: Path, role: str, epic_id: str) -> list[str]:
    """Return remaining problems after auto-repair (empty if clean/missing)."""
    problems: list[str] = []
    index = project / "memory-bank" / normalize_role(role) / "plan" / epic_id / "yaml" / "decompose-index.yaml"
    steps_root = index.parent / "steps"
    if not index.is_file():
        if steps_root.is_dir():
            orphans = sorted(p.name for p in steps_root.glob("*.yaml"))
            if orphans:
                problems.append(f"orphan steps without index: {', '.join(orphans)}")
        return problems
    try:
        validate_decompose_tree(project, role, epic_id)
    except (ValueError, FileNotFoundError, OSError) as exc:
        problems.append(str(exc))
    return problems


_INDEX_STEP_STATUSES = frozenset({"pending", "completed", "done", "in_progress"})
_FRESH_DECOMPOSE_STATUSES = frozenset({"pending"})
_COMPLETED_INDEX_STATUSES = frozenset({"completed", "done"})


def validate_decompose_tree(
    project: Path,
    role: str,
    epic_id: str,
    *,
    require_fresh_pending: bool = False,
) -> Queue:
    queue = load_queue(project, role, epic_id)
    payload = _load_yaml_mapping(queue.path)
    if payload.get("schema") != "epic-decompose-index/v1":
        raise ValueError(f"invalid decompose index schema: {queue.path}")
    if str(payload.get("plan_id") or "") != epic_id:
        raise ValueError(f"decompose index plan_id mismatch: expected {epic_id}, got {payload.get('plan_id')!r}")
    if not queue.steps:
        raise ValueError(f"decompose index has no steps: {queue.path}")

    expected_role = normalize_role(role)
    steps_root = (queue.path.parent / "steps").resolve()
    seen: set[str] = set()
    referenced_shards: set[Path] = set()
    required_step_fields = {
        "schema",
        "role",
        "step_id",
        "plan_id",
        "title",
        "next_phase",
        "goal",
        "plan_contract",
        "context",
        "as_built",
        "delta",
        "deletes",
        "out_of_scope",
        "skills",
        "checkpoints",
        "verify",
        "tdd",
    }
    for position, raw in enumerate(payload["steps"]):
        missing_index_fields = sorted({"id", "file", "title", "next_phase", "status"}.difference(raw))
        if missing_index_fields:
            raise ValueError(f"decompose index step missing fields {missing_index_fields}: {queue.path}")
        step_id = str(raw.get("id") or raw.get("step_id") or "").strip()
        if step_id in seen:
            raise ValueError(f"duplicate decompose step: {step_id}")
        seen.add(step_id)
        status = str(raw.get("status") or "pending").strip().lower()
        if status not in _INDEX_STEP_STATUSES:
            raise ValueError(
                f"decompose index step {step_id!r} has invalid status {status!r}; "
                f"allowed={sorted(_INDEX_STEP_STATUSES)}"
            )
        if require_fresh_pending and status not in _FRESH_DECOMPOSE_STATUSES:
            raise ValueError(
                f"decompose finish forbids step {step_id!r} status {status!r}; "
                "must be pending (completed is machine-owned only after IMPLEMENT finish)"
            )
        file_ref = str(raw.get("file") or "").strip()
        if not file_ref:
            raise ValueError(f"decompose step {step_id!r} has no file")
        shard = shard_path(project, queue, queue.steps[position])
        if shard is None or not shard.is_file():
            raise FileNotFoundError(f"decompose shard missing: {file_ref} ({queue.path})")
        if shard.resolve().parent != steps_root:
            raise ValueError(f"decompose shard outside canonical steps directory: {shard}")
        referenced_shards.add(shard.resolve())
        shard_payload = normalize_decompose_list_fields(shard, _load_yaml_mapping(shard))
        missing = sorted(required_step_fields.difference(shard_payload))
        if missing:
            raise ValueError(f"decompose shard missing fields {missing}: {shard}")
        if shard_payload.get("schema") != "epic-decompose/v1":
            raise ValueError(f"invalid decompose shard schema: {shard}")
        if normalize_role(str(shard_payload.get("role") or "")) != expected_role:
            raise ValueError(f"decompose shard role mismatch: {shard}")
        if str(shard_payload.get("step_id") or "") != step_id:
            raise ValueError(f"decompose shard step_id mismatch: {shard}")
        if str(shard_payload.get("plan_id") or "") != epic_id:
            raise ValueError(f"decompose shard plan_id mismatch: {shard}")
        for field in _DECOMPOSE_LIST_FIELDS:
            if not isinstance(shard_payload.get(field), list):
                raise ValueError(f"decompose shard field {field!r} must be a list: {shard}")
        for field in ("plan_contract", "context", "skills"):
            if not isinstance(shard_payload.get(field), dict):
                raise ValueError(f"decompose shard field {field!r} must be a mapping: {shard}")
    purge_orphan_decompose_shards(steps_root, referenced_shards)
    return queue


def step_implement_complete(project: Path, queue: Queue, step: Step) -> tuple[bool, str]:
    """Whether a step has a machine-valid completed implement artifact."""
    from .implement_schema import validate_implement_artifact

    path = implement_path(project, queue.role, queue.epic_id, step)
    if not path.is_file():
        return False, f"implement artifact missing: {path}"
    try:
        model = validate_implement_artifact(
            path,
            expected_step_id=step.step_id,
            expected_plan_id=queue.epic_id,
            rewrite=False,
        )
    except ValueError as exc:
        return False, str(exc)
    if model.status != "completed":
        return False, f"implement status {model.status!r} not completed: {path}"
    return True, "implement complete"


def queue_implement_gaps(project: Path, queue: Queue) -> tuple[tuple[Step, str], ...]:
    """Steps that still need IMPLEMENT evidence before QA is legal."""
    gaps: list[tuple[Step, str]] = []
    for step in queue.steps:
        ok, reason = step_implement_complete(project, queue, step)
        if not ok:
            gaps.append((step, reason))
    return tuple(gaps)


def queue_ready_for_qa(project: Path, queue: Queue) -> tuple[bool, str]:
    """Fail-closed: every step must be index-completed AND have completed implement yaml."""
    if not queue.steps:
        return False, "decompose index has no steps"
    gaps = queue_implement_gaps(project, queue)
    if gaps:
        detail = "; ".join(f"{step.step_id}: {reason}" for step, reason in gaps[:8])
        more = "" if len(gaps) <= 8 else f" (+{len(gaps) - 8} more)"
        return False, f"implement incomplete before QA: {detail}{more}"
    incomplete_index = [
        step.step_id
        for step in queue.steps
        if step.status not in _COMPLETED_INDEX_STATUSES
    ]
    if incomplete_index:
        return (
            False,
            "index steps not completed before QA: " + ", ".join(incomplete_index),
        )
    return True, "implement queue complete"


def prepare_step_status(queue: Queue, step_id: str, status: str) -> FileMutation:
    payload = dict(_load_yaml_mapping(queue.path))
    changed = False
    for raw in payload.get("steps", []):
        if str(raw.get("id") or raw.get("step_id") or "") == step_id:
            raw["status"] = status
            changed = True
            break
    if not changed:
        raise ValueError(f"step {step_id!r} not found in {queue.path}")
    current = queue.path.read_text(encoding="utf-8")
    content = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
    expected_hash = "sha256:" + hashlib.sha256(current.encode("utf-8")).hexdigest()
    return FileMutation(queue.path.resolve(), content, expected_hash)


def shard_path(project: Path, queue: Queue, step: Step) -> Path | None:
    if not step.shard:
        return None
    raw = Path(step.shard)
    if raw.is_absolute():
        return raw
    candidates = (
        queue.path.parent / raw,
        queue.path.parent / "steps" / raw.name,
        project / "memory-bank" / queue.role / "implement" / queue.epic_id / raw.name,
    )
    return next((candidate for candidate in candidates if candidate.is_file()), candidates[0])


def execute_path(project: Path, role: str, epic_id: str, step: Step | str, kind: str = "feature") -> Path:
    if not epic_id or Path(epic_id).name != epic_id:
        raise ValueError(f"invalid epic id: {epic_id!r}")
    k = normalize_kind(kind)
    sub = Path("implement") if k == "feature" else Path(k) / "implement"
    if isinstance(step, Step):
        filename = Path(step.shard).name if step.shard else f"{step.step_id}.yaml"
    else:
        filename = Path(step).name if step.endswith(".yaml") else f"{step}.yaml"
    return project / "memory-bank" / normalize_role(role) / sub / epic_id / filename


def implement_path(project: Path, role: str, epic_id: str, step: Step, kind: str = "feature") -> Path:
    return execute_path(project, role, epic_id, step, kind=kind)


def phase_artifacts(project: Path, role: str, epic_id: str, kind: str) -> list[Path]:
    root = project / "memory-bank" / normalize_role(role) / kind / epic_id
    if not root.is_dir():
        return []
    if kind == "qa":
        pattern = "qa-*.yaml"
    elif kind == "context-sync":
        pattern = "sync-*.md"
    else:
        pattern = "*.yaml"
    return sorted(root.glob(pattern))


def phase_payload(path: Path) -> dict[str, Any] | None:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeError, yaml.YAMLError):
        return None
    return payload if isinstance(payload, dict) else None


def latest_phase_payload(paths: list[Path]) -> tuple[Path | None, dict[str, Any] | None]:
    for path in reversed(paths):
        payload = phase_payload(path)
        if payload is not None:
            return path, payload
    return None, None




def bugfix_queue_path(project: Path, role: str, epic_id: str) -> Path:
    return project / "memory-bank" / normalize_role(role) / "bugfix" / epic_id / "bugfix-queue.yaml"


def bugfix_report_paths(project: Path, role: str, epic_id: str) -> list[Path]:
    root = bugfix_queue_path(project, role, epic_id).parent
    return sorted(root.glob("bugfix-*.md")) if root.is_dir() else []


def bugfix_queue_state(project: Path, role: str, epic_id: str) -> tuple[bool, str]:
    """Validate the machine SoT that controls BUGFIX completion."""
    path = bugfix_queue_path(project, role, epic_id)
    payload = phase_payload(path)
    if payload is None:
        return False, "bugfix_queue_missing"
    if payload.get("schema") != "epic-bugfix-queue/v1":
        return False, "bugfix_queue_schema_invalid"
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        return False, "bugfix_queue_items_missing"
    statuses: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            return False, "bugfix_queue_item_invalid"
        status = str(item.get("status") or "").strip().lower()
        if status not in {"open", "in_progress", "blocked", "done", "closed", "cancelled"}:
            return False, "bugfix_queue_item_invalid"
        statuses.append(status)
    if any(status in {"open", "in_progress", "blocked"} for status in statuses):
        return False, "bugfix_queue_open"
    verification = payload.get("verification")
    if not isinstance(verification, dict) or str(verification.get("status") or "").strip().lower() != "pass":
        return False, "bugfix_verification_required"
    if not all(str(verification.get(field) or "").strip() for field in ("command", "last_run_at", "evidence")):
        return False, "bugfix_verification_required"
    return True, "bugfix_queue_ready"


def bugfix_queue_intake(project: Path, role: str, epic_id: str) -> tuple[bool, str]:
    """Validate a QA-created queue before BUGFIX has completed it."""
    path = bugfix_queue_path(project, role, epic_id)
    payload = phase_payload(path)
    if payload is None:
        return False, "bugfix_queue_missing"
    if payload.get("schema") != "epic-bugfix-queue/v1":
        return False, "bugfix_queue_schema_invalid"
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        return False, "bugfix_queue_items_missing"
    statuses = []
    for item in items:
        if not isinstance(item, dict):
            return False, "bugfix_queue_item_invalid"
        status = str(item.get("status") or "").strip().lower()
        if status not in {"open", "in_progress", "blocked", "done", "closed", "cancelled"}:
            return False, "bugfix_queue_item_invalid"
        statuses.append(status)
    return True, "bugfix_queue_valid"


def qa_verdict(path: Path) -> str | None:
    payload = phase_payload(path)
    if payload is None:
        return None
    if payload.get("schema") != "epic-qa/v1":
        return None
    return str(payload.get("verdict") or payload.get("status") or "").lower() or None
