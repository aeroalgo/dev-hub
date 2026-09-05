"""Epic loop path/state utilities — thin wrapper and compat layer over loop.paths.epic_layout.

Re-exports resolver API and maintains public helper functions for backwards compatibility.
Emits layout_v1_deprecated diagnostics when falling back to legacy v1 paths.
"""
from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from typing import Any

# Ensure project root is available for loop imports
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from loop.paths.epic_layout import resolve, resolve_request, EpicLayoutKind

logger = logging.getLogger(__name__)

EPIC_DIRNAME = "epic"
STATE_NAME = "state.json"
NEXT_PROMPT_NAME = "next-prompt.txt"

_INTEG_E_MD = re.compile(r"(?i)/e\d{2}-[a-z0-9-]+\.md$")
_EPIC_S_MD = re.compile(r"(?i)/s\d{2}-[a-z0-9-]+\.md$")

STEP_BASENAME_RE = re.compile(
    r"(?i)((?:s|e)\d{2}-[a-z0-9][a-z0-9-]*)(?:\.(md|ya?ml))?$"
)

# Role directory slugs must never be used as epic_id (→ phantom role folders).
RESERVED_ROLE_EPIC_IDS = frozenset({"back", "front", "integration", "integ"})
_EPIC_ID_RE = re.compile(r"^T-[\w-]+$")
_HUB_EPIC_PREFIX_RE = re.compile(r"^(T-HUB-\d+)")
_LEGACY_DECOMPOSE_PREFIX = "decompose-"  # layout_v1_deprecated prefix marker


def _warn_layout_v1_deprecated(feature: str, details: str = "") -> None:
    """Log structured warning for legacy layout v1 usage."""
    msg = f"layout_v1_deprecated: {feature}"
    if details:
        msg = f"{msg} ({details})"
    logger.warning(msg)


def epic_dir(cwd: str | Path) -> Path:
    import os

    hub_root = Path(__file__).resolve().parents[2]
    cwd_p = Path(cwd).expanduser().resolve()
    proj = (os.environ.get("PROJECT_ROOT") or "").strip()
    project_p = Path(proj).expanduser().resolve() if proj else None
    effective_cwd = project_p if project_p is not None and cwd_p == hub_root else cwd_p
    hub = (os.environ.get("DEV_HUB") or os.environ.get("HUB_ROOT") or "").strip()
    use_hub_runtime = bool(
        hub and (project_p is None or project_p != hub_root)
    )
    if use_hub_runtime:
        d = Path(hub).expanduser().resolve() / "runtime" / effective_cwd.name / EPIC_DIRNAME
    else:
        d = effective_cwd / ".claude" / "runtime" / EPIC_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def state_path(cwd: str | Path) -> Path:
    return epic_dir(cwd) / STATE_NAME


def next_prompt_path(cwd: str | Path) -> Path:
    return epic_dir(cwd) / NEXT_PROMPT_NAME


def active_context_path(cwd: str | Path) -> Path:
    import os
    from loop.paths.pack_layout import resolve_mb_root

    cwd_p = Path(cwd).expanduser().resolve()
    hub_root = Path(__file__).resolve().parents[2]
    proj = (os.environ.get("PROJECT_ROOT") or "").strip()
    root = Path(proj).expanduser().resolve() if proj and cwd_p == hub_root else cwd_p
    try:
        return resolve_mb_root(root) / "activeContext.md"
    except Exception:
        return root / "memory-bank" / "activeContext.md"


def _normalize_mb_path(path: str | Path) -> str:
    if not isinstance(path, (str, Path)):
        return ""
    p = str(path).strip().lstrip("./")
    if p.startswith(("back/", "front/", "integration/")):
        return f"memory-bank/{p}"
    return p


def _coerce_epic_shard_path(path: str | Path) -> str:
    if not isinstance(path, (str, Path)):
        return ""
    norm = str(path).replace("\\", "/")
    for pat in (
        r"(?i)((?:s|e|r|a)\d{2}-[a-z0-9-]+)\.md$",
        r"(?i)(qa-\d{8}-[a-z0-9-]+)\.md$",
    ):
        m = re.search(pat, norm)
        if m:
            return f"{norm[: m.start()]}{m.group(1).lower()}.yaml"
    return norm


def assert_epic_yaml_shards(paths: list[str | Path]) -> list[str | Path]:
    """Epic shards sNN/eNN — только .yaml/.yml (без md fallback)."""
    for p in paths:
        if not isinstance(p, (str, Path)):
            raise ValueError(f"Epic shard path must be str/Path: {p!r}")
        norm = str(p).replace("\\", "/")
        if _INTEG_E_MD.search(norm) or _EPIC_S_MD.search(norm):
            raise ValueError(f"Epic shard must be .yaml, not .md: {p}")
    return paths


assert_integ_yaml_shards = assert_epic_yaml_shards


def extract_step_basename(path: str | Path) -> str | None:
    if not isinstance(path, (str, Path)):
        return None
    norm = str(path).replace("\\", "/").split("/")[-1]
    m = STEP_BASENAME_RE.match(norm)
    if not m:
        return None
    stem = m.group(1).lower()
    ext = (m.group(2) or "").lower()
    if stem.startswith("e") or stem.startswith("s"):
        if ext == "md":
            return f"{stem}.yaml"
        if ext not in {"yaml", "yml", ""}:
            return None
        return f"{stem}.yaml"
    if ext in {"yaml", "yml"}:
        return f"{stem}.{ext}"
    return None


def is_epic_implement_step_path(path: Path | str) -> bool:
    if not isinstance(path, (str, Path)):
        return False
    name = Path(path).name.lower()
    return bool(re.match(r"[se]\d{2}-", name)) and Path(path).suffix.lower() in {
        ".yaml",
        ".yml",
    }


is_integ_implement_step_path = is_epic_implement_step_path


def role_from_decompose_path(decompose: str | Path) -> str | None:
    """Infer BACK|FRONT|INTEG from normalized memory-bank path. None if unknown."""
    if not isinstance(decompose, (str, Path)):
        return None
    p = str(decompose).replace("\\", "/").lstrip("./")
    markers = (
        ("/integration/", "INTEG"),
        ("memory-bank/integration/", "INTEG"),
        ("/front/", "FRONT"),
        ("memory-bank/front/", "FRONT"),
        ("/back/", "BACK"),
        ("memory-bank/back/", "BACK"),
    )
    for needle, role in markers:
        if needle in p or p.startswith(needle.lstrip("/")):
            return role
    return None


def is_reserved_role_epic_id(epic_id: str | None) -> bool:
    return bool(epic_id) and str(epic_id).strip().lower() in RESERVED_ROLE_EPIC_IDS


def epic_id_from_decompose_path(decompose: str | Path) -> str:
    """Extract epic_id from a decompose or plan path (v2 or v1)."""
    if not isinstance(decompose, (str, Path)):
        return ""
    raw = str(decompose).strip()
    if not raw:
        return ""
    path = Path(raw.replace("\\", "/"))
    parts = list(path.parts)
    for idx, part in enumerate(parts):
        # Layout v2: memory-bank/<role>/plan/<epic_id>/...
        if part == "plan" and idx + 1 < len(parts):
            next_part = parts[idx + 1]
            if next_part.startswith(_LEGACY_DECOMPOSE_PREFIX):
                _warn_layout_v1_deprecated("decompose_folder_v1", next_part)
                return next_part[len(_LEGACY_DECOMPOSE_PREFIX) :]
            elif next_part not in {"md", "yaml", "steps"}:
                return next_part
        if part.startswith(_LEGACY_DECOMPOSE_PREFIX):
            _warn_layout_v1_deprecated("decompose_folder_v1", part)
            return part[len(_LEGACY_DECOMPOSE_PREFIX) :]
    name = path.stem
    return name if name not in {".", "..", "", "index", "decompose-index"} else ""  # layout_v1_deprecated index stem


def plan_id_from_decompose_index(index_path: Path) -> str | None:
    """Read plan_id from decompose index.yaml when present."""
    path = index_path
    if path.name in {"index.md", "decompose-index.md"}:  # layout_v1_deprecated index filename
        yaml_sibling = path.with_name(path.name.replace(".md", ".yaml"))
        if yaml_sibling.is_file():
            path = yaml_sibling
    if not path.is_file():
        return None
    try:
        from epic_index import load_index_yaml

        doc = load_index_yaml(path) or {}
    except Exception:
        return None
    plan_id = str(doc.get("plan_id") or "").strip()
    return plan_id or None


def canonical_epic_id_for_decompose(decompose: str | Path, *, index_path: Path | None = None) -> str:
    """Epic id: plan_id from index.yaml when set, else folder slug."""
    idx = index_path
    if idx is None:
        raw = str(decompose).strip().replace("\\", "/")
        if raw.endswith(".md") or raw.endswith(".yaml") or raw.endswith(".yml"):
            idx = Path(raw)
        else:
            idx = Path(raw) / "index.yaml"
    if idx.name in {"index.md", "decompose-index.md"}:  # layout_v1_deprecated index filename
        yaml_sibling = idx.with_name(idx.name.replace(".md", ".yaml"))
        if yaml_sibling.is_file():
            idx = yaml_sibling
    plan_id = plan_id_from_decompose_index(idx)
    if plan_id:
        return plan_id
    return epic_id_from_decompose_path(decompose)


def find_decompose_index_path(
    cwd: str | Path,
    role: str,
    epic_id: str,
) -> Path | None:
    """Resolve decompose index path via resolver (v2) with legacy v1 fallback."""
    if not epic_id:
        return None
    root = Path(cwd)
    role_norm = role.lower()
    if role_norm == "integ":
        role_norm = "integration"

    # Try resolver (v2) first
    try:
        v2_yaml = resolve(role_norm, epic_id, EpicLayoutKind.DECOMPOSE_INDEX_YAML, project_root=root)
        if v2_yaml.is_file():
            return v2_yaml
        v2_md = resolve(role_norm, epic_id, EpicLayoutKind.DECOMPOSE_INDEX_MD, project_root=root)
        if v2_md.is_file():
            return v2_md
    except Exception:
        pass

    # Legacy v1 fallback with deprecation warning
    plan_dir = root / "memory-bank" / role_norm / "plan"
    if not plan_dir.is_dir():
        return None

    lookup = epic_lookup_ids(epic_id)
    for lookup_id in lookup:
        # Check v2 lookup candidate
        try:
            cand_v2 = resolve(role_norm, lookup_id, EpicLayoutKind.DECOMPOSE_INDEX_YAML, project_root=root)
            if cand_v2.is_file():
                return cand_v2
        except Exception:
            pass

        found = _find_layout_v1_deprecated_decompose_index(plan_dir, lookup_id)
        if found is not None:
            _warn_layout_v1_deprecated("decompose_index_path", str(found))
            return found

    lookup_set = set(lookup)
    for ypath in sorted(plan_dir.glob("*/yaml/decompose-index.yaml")):  # layout_v2 glob
        plan_id = plan_id_from_decompose_index(ypath)
        if plan_id and plan_id in lookup_set:
            return ypath

    # Legacy v1 glob fallback (layout_v1_deprecated)
    for ypath in sorted(plan_dir.glob(f"{_LEGACY_DECOMPOSE_PREFIX}*/index.yaml")):
        plan_id = plan_id_from_decompose_index(ypath)
        if plan_id and plan_id in lookup_set:
            _warn_layout_v1_deprecated("decompose_glob_v1", str(ypath))
            return ypath
    for mdpath in sorted(plan_dir.glob(f"{_LEGACY_DECOMPOSE_PREFIX}*/index.md")):
        ypath = mdpath.with_name("index.yaml")
        if ypath.is_file() and plan_id_from_decompose_index(ypath) in lookup_set:
            _warn_layout_v1_deprecated("decompose_glob_v1", str(ypath))
            return ypath
        if plan_id_from_decompose_index(mdpath) in lookup_set:
            _warn_layout_v1_deprecated("decompose_glob_v1", str(mdpath))
            return mdpath
    return None


def epic_id_from_plan_path(plan: str | Path | None) -> str | None:
    """Extract epic_id from v2 ``…/{epic_id}/md/plan.md`` or legacy ``plan-{epic_id}.md``."""
    if plan is None:
        return None
    path = Path(plan)
    if not path.name:
        return None
    if path.name == "plan.md" and path.parent.name == "md":
        return path.parent.parent.name or None
    stem = path.stem
    if stem.startswith("plan-"):
        return stem[len("plan-") :] or None
    return stem or None


def find_plan_md_path(
    cwd: str | Path,
    role: str,
    epic_id: str,
) -> Path | None:
    """Resolve plan.md via layout v2 first, then legacy ``plan-{id}.md`` (deprecated)."""
    if not epic_id:
        return None
    root = Path(cwd)
    role_norm = role.lower()
    if role_norm == "integ":
        role_norm = "integration"

    plan_dir = root / "memory-bank" / role_norm / "plan"
    lookup = epic_lookup_ids(epic_id)

    for lookup_id in lookup:
        try:
            v2_plan = resolve(role_norm, lookup_id, EpicLayoutKind.PLAN_MD, project_root=root)
            if v2_plan.is_file():
                return v2_plan
        except Exception:
            pass

    if plan_dir.is_dir():
        for lookup_id in lookup:
            for cand in sorted(plan_dir.glob(f"{lookup_id}-*/md/plan.md")):
                if cand.is_file():
                    return cand
            exact = plan_dir / lookup_id / "md" / "plan.md"
            if exact.is_file():
                return exact

        for lookup_id in lookup:
            exact_v1 = plan_dir / f"plan-{lookup_id}.md"
            if exact_v1.is_file():
                _warn_layout_v1_deprecated("plan_md_v1", str(exact_v1))
                return exact_v1
            matches = sorted(plan_dir.glob(f"plan-{lookup_id}-*.md"))
            if matches:
                _warn_layout_v1_deprecated("plan_md_v1", str(matches[0]))
                return matches[0]
    return None


def resolve_decompose_ref_for_gate(cwd: str | Path, epic: dict[str, Any]) -> str | None:
    """Resolve decompose index path for DECOMPOSE FINISH gate."""
    raw = str(epic.get("armed_decompose") or "").strip()
    if raw:
        return raw.replace("\\", "/")
    armed_step = str(epic.get("armed_step") or "").upper()
    if armed_step != "DECOMPOSE":
        return None
    epic_id = str(epic.get("armed_epic") or "").strip()
    if not epic_id:
        return None
    role = str(epic.get("role") or "back").lower()
    if role == "integ":
        role = "integration"
    root = Path(cwd)
    idx = find_decompose_index_path(root, role, epic_id)
    if idx and idx.is_file():
        try:
            return idx.relative_to(root).as_posix()
        except ValueError:
            return str(idx).replace("\\", "/")

    # Resolver v2 expected path
    try:
        v2_path = resolve(role, epic_id, EpicLayoutKind.DECOMPOSE_INDEX_YAML, project_root=root)
        if v2_path.is_file():
            try:
                return v2_path.relative_to(root).as_posix()
            except ValueError:
                return str(v2_path).replace("\\", "/")
    except Exception:
        pass

    return None


def epic_lookup_ids(epic_id: str) -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        key = (value or "").strip()
        if key and key not in seen:
            seen.add(key)
            out.append(key)

    add(epic_id)
    m = _HUB_EPIC_PREFIX_RE.match(epic_id or "")
    if m:
        add(m.group(1))
    return tuple(out)


def _find_layout_v1_deprecated_decompose_index(plan_dir: Path, epic_id: str) -> Path | None:
    """Legacy v1 decompose finder (layout_v1_deprecated)."""
    exact_dir = plan_dir / f"{_LEGACY_DECOMPOSE_PREFIX}{epic_id}"
    for name in ("index.yaml", "index.md"):
        candidate = exact_dir / name
        if candidate.is_file():
            return candidate
    for d in sorted(plan_dir.glob(f"{_LEGACY_DECOMPOSE_PREFIX}{epic_id}-*")):
        if not d.is_dir():
            continue
        for name in ("index.yaml", "index.md"):
            candidate = d / name
            if candidate.is_file():
                return candidate
    return None


def discover_epic_role(cwd: str | Path, epic_id: str) -> str | None:
    """Find role directory that owns plan or decompose artifacts for epic_id."""
    if not epic_id:
        return None
    root = Path(cwd)
    mb = root / "memory-bank"
    for role in ("back", "front", "integration"):
        plan_dir = mb / role / "plan"
        if not plan_dir.is_dir():
            continue
        for lookup_id in epic_lookup_ids(epic_id):
            # v2 checks
            try:
                v2_plan = resolve(role, lookup_id, EpicLayoutKind.PLAN_MD, project_root=root)
                if v2_plan.is_file():
                    return role
                v2_idx = resolve(role, lookup_id, EpicLayoutKind.DECOMPOSE_INDEX_YAML, project_root=root)
                if v2_idx.is_file():
                    return role
            except Exception:
                pass

            # Legacy v1 checks with warning (layout_v1_deprecated)
            if (plan_dir / f"plan-{lookup_id}.md").is_file():
                _warn_layout_v1_deprecated("plan_md_v1", f"plan-{lookup_id}.md")
                return role
            if any(plan_dir.glob(f"plan-{lookup_id}-*.md")):
                _warn_layout_v1_deprecated("plan_md_v1", f"plan-{lookup_id}-*.md")
                return role
            decomp = plan_dir / f"{_LEGACY_DECOMPOSE_PREFIX}{lookup_id}"
            if (decomp / "index.yaml").is_file() or (decomp / "index.md").is_file():
                _warn_layout_v1_deprecated("decompose_dir_v1", str(decomp))
                return role
            if any(plan_dir.glob(f"{_LEGACY_DECOMPOSE_PREFIX}{lookup_id}-*/index.yaml")):
                _warn_layout_v1_deprecated("decompose_dir_v1", f"{_LEGACY_DECOMPOSE_PREFIX}{lookup_id}-*/index.yaml")
                return role
            if any(plan_dir.glob(f"{_LEGACY_DECOMPOSE_PREFIX}{lookup_id}-*/index.md")):
                _warn_layout_v1_deprecated("decompose_dir_v1", f"{_LEGACY_DECOMPOSE_PREFIX}{lookup_id}-*/index.md")
                return role
    return None


def role_from_memory_bank_path(target: str | Path) -> str:
    raw = str(target).strip().replace("\\", "/").lstrip("./")
    norm = f"/{raw}" if not raw.startswith("/") else raw
    if "/memory-bank/front/" in norm or raw.startswith("front/"):
        return "front"
    if "/memory-bank/integration/" in norm or raw.startswith("integration/"):
        return "integration"
    return "back"


def resolve_arm_epic_target(
    target: str | Path,
    cwd: str | Path | None = None,
) -> tuple[str, str] | None:
    """Map arm CLI target (epic id, plan path, or decompose path) to (epic_id, role)."""
    raw = str(target).strip().replace("\\", "/")
    if not raw:
        return None
    role = role_from_memory_bank_path(raw)
    epic_id = ""
    if _LEGACY_DECOMPOSE_PREFIX in raw or "/plan/" in raw:  # layout_v1_deprecated compat
        epic_id = epic_id_from_decompose_path(raw)
    else:
        name = Path(raw.rstrip("/")).name
        if name.startswith("plan-"):
            epic_id = name[len("plan-") :].removesuffix(".md")
        elif _EPIC_ID_RE.match(name):
            epic_id = name
    if not epic_id:
        return None
    if cwd is not None and (
        "/memory-bank/" not in f"/{raw.lstrip('./')}"
        and not raw.startswith(("back/", "front/", "integration/"))
    ):
        discovered = discover_epic_role(cwd, epic_id)
        if discovered:
            role = discovered
    return (epic_id, role)
