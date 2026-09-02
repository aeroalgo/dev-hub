"""Resolver for loop/mb_load mode matrix & bundle path resolution."""

import re
from pathlib import Path
from typing import NamedTuple

from harness.hooks.epic_paths import epic_id_from_decompose_path, role_from_decompose_path
from harness.hooks.epic_yaml import role_dir, resolve_implement_path

_PLAN_MD_RE = re.compile(r"(?:^|/)plan-[^/]+\.md$")


class ResolvedBundle(NamedTuple):
    resolved_paths: list[str]
    auto_added: list[str]
    forbidden_skipped: list[str]
    diagnostics: list[str]


def resolve_bundle_paths(
    cwd: str | Path,
    mode: str | None,
    step_id: str | None,
    load_now_paths: list[str],
) -> ResolvedBundle:
    """Resolves and filters load_now bundle paths based on current mode matrix and step_id.

    - mode=IMPLEMENT: auto-resolves implement yaml shard if missing from load_now_paths.
      Rejects plan-*.md as forbidden.
    - mode=QA / BUGFIX / DECOMPOSE: allows mode-specific bundle policies.
      DECOMPOSE allows plan-*.md files.
    """
    cwd_path = Path(cwd).resolve()
    mode_upper = (mode or "").strip().upper()

    resolved_paths = list(load_now_paths)
    auto_added: list[str] = []
    forbidden_skipped: list[str] = []
    diagnostics: list[str] = []

    # 1. IMPLEMENT mode auto-resolve implement shard if missing
    if mode_upper == "IMPLEMENT" and step_id:
        has_implement_yaml = any(
            "implement-" in p and (p.endswith(".yaml") or p.endswith(".yml"))
            for p in resolved_paths
        )
        if not has_implement_yaml:
            impl_rel: str | None = None
            decompose_rel: str | None = None
            for p in resolved_paths:
                if "/decompose-" in p and (p.endswith(".yaml") or p.endswith(".yml")):
                    decompose_rel = p
                    break

            if decompose_rel:
                role = role_from_decompose_path(decompose_rel) or "back"
                epic_id = epic_id_from_decompose_path(decompose_rel)
                if epic_id:
                    try:
                        cand = resolve_implement_path(
                            cwd_path,
                            role=role_dir(role),
                            epic_id=epic_id,
                            step_id=step_id,
                        )
                        if (cwd_path / cand).is_file():
                            impl_rel = cand
                    except Exception:
                        pass

            if not impl_rel:
                # Glob search fallback
                for found in cwd_path.glob(f"memory-bank/**/implement/**/{step_id}*.yaml"):
                    if found.is_file():
                        impl_rel = found.relative_to(cwd_path).as_posix()
                        break

            if impl_rel and impl_rel not in resolved_paths:
                resolved_paths.append(impl_rel)
                auto_added.append(impl_rel)

    # 2. QA / BUGFIX mode auto-resolve shards if needed
    if mode_upper in ("QA", "BUGFIX") and step_id:
        kind = mode_upper.lower()
        for found in cwd_path.glob(f"memory-bank/**/{kind}/**/{kind}-*{step_id}*.yaml"):
            if found.is_file():
                rel = found.relative_to(cwd_path).as_posix()
                if rel not in resolved_paths:
                    resolved_paths.append(rel)
                    auto_added.append(rel)
                    break

    # 3. Apply mode matrix forbidden rules
    final_paths: list[str] = []
    for p in resolved_paths:
        is_plan_md = bool(_PLAN_MD_RE.search(p))
        if is_plan_md and mode_upper != "DECOMPOSE":
            forbidden_skipped.append(p)
        else:
            final_paths.append(p)

    return ResolvedBundle(
        resolved_paths=final_paths,
        auto_added=auto_added,
        forbidden_skipped=forbidden_skipped,
        diagnostics=diagnostics,
    )
