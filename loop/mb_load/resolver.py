"""Resolve session bundles within the current pack, role and epic."""

from pathlib import Path
from typing import NamedTuple

from loop.paths.forbidden_policy import policy_for_layout
from loop.paths.pack_layout import resolve_mb_root
from loop.workflow.registry import resolve_workflow_pack


class ResolvedBundle(NamedTuple):
    resolved_paths: list[str]
    auto_added: list[str]
    forbidden_skipped: list[str]
    diagnostics: list[str]


def _artifact_identity(path: Path, mb_root: Path) -> tuple[str, str] | None:
    try:
        parts = path.resolve().relative_to(mb_root.resolve()).parts
    except ValueError:
        return None
    if len(parts) < 4 or parts[1] not in {"plan", "implement", "qa", "bugfix", "audit"}:
        return None
    epic = parts[2]
    for prefix in ("decompose-", "implement-", "qa-"):
        if epic.startswith(prefix):
            epic = epic[len(prefix):]
            break
    return parts[0], epic


def resolve_bundle_paths(
    cwd: str | Path,
    mode: str | None,
    step_id: str | None,
    load_now_paths: list[str],
    *,
    epic_id: str | None = None,
    role: str | None = None,
) -> ResolvedBundle:
    """Auto-add only current epic evidence; never substitute another epic's step."""
    cwd_path = Path(cwd).resolve()
    mode_upper = (mode or "").strip().upper()
    diagnostics: list[str] = []
    try:
        pack = resolve_workflow_pack(cwd=cwd_path)
        if not pack.ok or pack.pack is None:
            return ResolvedBundle([], [], list(load_now_paths), ["workflow_pack_unresolved"])
        mb_root = resolve_mb_root(cwd=cwd_path, pack=pack.pack)
        policy = policy_for_layout(pack.pack.artifact_layout)
    except (ValueError, RuntimeError) as exc:
        return ResolvedBundle([], [], list(load_now_paths), [f"bundle_layout_invalid:{exc}"])

    role = (role or "").lower()
    if role == "integ":
        role = "integration"
    identities = {_artifact_identity(cwd_path / p, mb_root) for p in load_now_paths}
    identities.discard(None)
    if not epic_id and len(identities) == 1:
        inferred_role, epic_id = next(iter(identities))
        role = role or inferred_role
    if epic_id and not role:
        roles = {r for r, e in identities if e == epic_id}
        if len(roles) == 1:
            role = roles.pop()

    resolved: list[str] = []
    forbidden: list[str] = []
    for path in load_now_paths:
        identity = _artifact_identity(cwd_path / path, mb_root)
        if identity and epic_id and role and identity != (role, epic_id):
            forbidden.append(path)
            diagnostics.append(f"artifact_identity_mismatch:{path}")
        elif policy.is_forbidden(path, mode=mode_upper):
            forbidden.append(path)
        else:
            resolved.append(path)

    auto_added: list[str] = []
    if epic_id and role and mode_upper in {"IMPLEMENT", "QA", "BUGFIX"}:
        kind = mode_upper.lower()
        directories = [mb_root / role / kind / epic_id]
        if kind == "implement":
            directories.append(mb_root / role / kind / f"implement-{epic_id}")
            patterns = [f"{step_id}-*.yaml", f"{step_id}.yaml"] if step_id else []
        else:
            patterns = [f"{kind}-*.{'md' if kind == 'bugfix' else 'yaml'}"]
        has_kind = any(kind in Path(p).parts for p in resolved)
        candidates = {p for d in directories for pattern in patterns for p in d.glob(pattern) if p.is_file()}
        if not has_kind and candidates:
            if kind == "implement" and len(candidates) > 1:
                diagnostics.append("implement_artifact_ambiguous")
            else:
                candidate = max(candidates, key=lambda p: (p.stat().st_mtime_ns, p.name))
                rel = candidate.relative_to(cwd_path).as_posix()
                if rel not in resolved:
                    resolved.append(rel)
                    auto_added.append(rel)
    return ResolvedBundle(resolved, auto_added, forbidden, diagnostics)
