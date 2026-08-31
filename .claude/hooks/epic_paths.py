"""Epic loop path/state utilities — leaf module (zone A).

Pure path normalization, decompose-path inference, and step-basename helpers.
No dependency on epic_lib / orchestration — only stdlib. Extracted from the
epic_lib god-module (BACK REFACTOR r01). Behavior frozen 1-в-1.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

EPIC_DIRNAME = "epic"
STATE_NAME = "state.json"
NEXT_PROMPT_NAME = "next-prompt.txt"

_INTEG_E_MD = re.compile(r"(?i)/e\d{2}-[a-z0-9-]+\.md$")
_EPIC_S_MD = re.compile(r"(?i)/s\d{2}-[a-z0-9-]+\.md$")

STEP_BASENAME_RE = re.compile(
    r"(?i)((?:s|e)\d{2}-[a-z0-9][a-z0-9-]*)(?:\.(md|ya?ml))?$"
)


def epic_dir(cwd: str | Path) -> Path:
    import os

    # Prefer PROJECT_ROOT so hooks running with Claude cwd=hub still hit the product repo.
    hub_root = Path(__file__).resolve().parents[2]
    cwd_p = Path(cwd).expanduser().resolve()
    proj = (os.environ.get("PROJECT_ROOT") or "").strip()
    project_p = Path(proj).expanduser().resolve() if proj else None
    effective_cwd = project_p if project_p is not None and cwd_p == hub_root else cwd_p
    hub = (os.environ.get("DEV_HUB") or os.environ.get("HUB_ROOT") or "").strip()
    # An explicit temporary/test cwd must stay isolated when the inherited
    # PROJECT_ROOT points at this hub; production products use hub runtime.
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

    cwd_p = Path(cwd).expanduser().resolve()
    hub_root = Path(__file__).resolve().parents[2]
    proj = (os.environ.get("PROJECT_ROOT") or "").strip()
    root = Path(proj).expanduser().resolve() if proj and cwd_p == hub_root else cwd_p
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


# Role directory slugs must never be used as epic_id (→ phantom decompose-back/).
RESERVED_ROLE_EPIC_IDS = frozenset({"back", "front", "integration", "integ"})


def is_reserved_role_epic_id(epic_id: str | None) -> bool:
    return bool(epic_id) and str(epic_id).strip().lower() in RESERVED_ROLE_EPIC_IDS


def epic_id_from_decompose_path(decompose: str | Path) -> str:
    if not isinstance(decompose, (str, Path)):
        return ""
    raw = str(decompose).strip()
    if not raw:
        return ""
    path = Path(raw.replace("\\", "/"))
    for part in reversed(path.parts):
        if part.startswith("decompose-"):
            return part[len("decompose-") :]
    name = path.stem
    return name if name not in {".", "..", "", "index"} else ""


def plan_id_from_decompose_index(index_path: Path) -> str | None:
    """Read plan_id from decompose index.yaml when present."""
    path = index_path
    if path.name == "index.md":
        yaml_sibling = path.with_name("index.yaml")
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
        if raw.endswith(".md"):
            idx = Path(raw)
        elif raw.endswith(".yaml") or raw.endswith(".yml"):
            idx = Path(raw)
        else:
            idx = Path(raw) / "index.yaml"
    if idx.name == "index.md":
        yaml_sibling = idx.with_name("index.yaml")
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
    """Resolve decompose index.yaml|.md by folder name or index plan_id."""
    if not epic_id:
        return None
    root = Path(cwd)
    plan_dir = root / "memory-bank" / role / "plan"
    if not plan_dir.is_dir():
        return None
    lookup = epic_lookup_ids(epic_id)
    for lookup_id in lookup:
        found = _find_decompose_index_in_plan_dir(plan_dir, lookup_id)
        if found is not None:
            return found
    lookup_set = set(lookup)
    for ypath in sorted(plan_dir.glob("decompose-*/index.yaml")):
        plan_id = plan_id_from_decompose_index(ypath)
        if plan_id and plan_id in lookup_set:
            return ypath
    for mdpath in sorted(plan_dir.glob("decompose-*/index.md")):
        ypath = mdpath.with_name("index.yaml")
        if ypath.is_file() and plan_id_from_decompose_index(ypath) in lookup_set:
            return ypath
        if plan_id_from_decompose_index(mdpath) in lookup_set:
            return mdpath
    return None


def resolve_decompose_ref_for_gate(cwd: str | Path, epic: dict[str, Any]) -> str | None:
    """Resolve decompose index path for DECOMPOSE FINISH gate.

    Uses armed_decompose when set; otherwise finds index by armed_epic + role
    (headless DECOMPOSE often arms with armed_decompose=None until tree exists).
    """
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
    root = Path(cwd)
    idx = find_decompose_index_path(root, role, epic_id)
    if idx and idx.is_file():
        try:
            return idx.relative_to(root).as_posix()
        except ValueError:
            return str(idx).replace("\\", "/")
    expected = root / "memory-bank" / role / "plan" / f"decompose-{epic_id}" / "index.yaml"
    if expected.is_file():
        try:
            return expected.relative_to(root).as_posix()
        except ValueError:
            return str(expected).replace("\\", "/")
    return None


_EPIC_ID_RE = re.compile(r"^T-[\w-]+$")
_HUB_EPIC_PREFIX_RE = re.compile(r"^(T-HUB-\d+)")


def epic_lookup_ids(epic_id: str) -> tuple[str, ...]:
    """Ordered epic ids for artifact lookup (exact slug, then roadmap queue prefix).

    Roadmap queue uses short ids (T-HUB-030) while plan files often carry a
    descriptive slug (T-HUB-030-harness-runtime-wire). Decompose folders may
    exist under either form; try both without collapsing the caller's epic_id.
    """
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


def _find_decompose_index_in_plan_dir(plan_dir: Path, epic_id: str) -> Path | None:
    exact_dir = plan_dir / f"decompose-{epic_id}"
    for name in ("index.yaml", "index.md"):
        candidate = exact_dir / name
        if candidate.is_file():
            return candidate
    for d in sorted(plan_dir.glob(f"decompose-{epic_id}-*")):
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
            if (plan_dir / f"plan-{lookup_id}.md").is_file():
                return role
            if any(plan_dir.glob(f"plan-{lookup_id}-*.md")):
                return role
            decomp = plan_dir / f"decompose-{lookup_id}"
            if (decomp / "index.yaml").is_file() or (decomp / "index.md").is_file():
                return role
            if any(plan_dir.glob(f"decompose-{lookup_id}-*/index.yaml")):
                return role
            if any(plan_dir.glob(f"decompose-{lookup_id}-*/index.md")):
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
    if "decompose-" in raw:
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
