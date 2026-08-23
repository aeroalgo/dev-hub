"""Epic loop path/state utilities — leaf module (zone A).

Pure path normalization, decompose-path inference, and step-basename helpers.
No dependency on epic_lib / orchestration — only stdlib. Extracted from the
epic_lib god-module (BACK REFACTOR r01). Behavior frozen 1-в-1.
"""
from __future__ import annotations

import re
from pathlib import Path

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
    proj = (os.environ.get("PROJECT_ROOT") or "").strip()
    cwd_p = Path(proj).expanduser().resolve() if proj else Path(cwd).resolve()
    hub = (os.environ.get("DEV_HUB") or os.environ.get("HUB_ROOT") or "").strip()
    if hub:
        d = Path(hub).expanduser().resolve() / "runtime" / cwd_p.name / EPIC_DIRNAME
    else:
        d = cwd_p / ".claude" / "runtime" / EPIC_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def state_path(cwd: str | Path) -> Path:
    return epic_dir(cwd) / STATE_NAME


def next_prompt_path(cwd: str | Path) -> Path:
    return epic_dir(cwd) / NEXT_PROMPT_NAME


def active_context_path(cwd: str | Path) -> Path:
    import os

    proj = (os.environ.get("PROJECT_ROOT") or "").strip()
    root = Path(proj).expanduser().resolve() if proj else Path(cwd).resolve()
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
