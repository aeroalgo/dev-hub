from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Sequence

# Regex matching literal @.agents/skills/<name> with optional /SKILL.md or /
# Matches @.agents/skills/writing-plans/SKILL.md or @.agents/skills/writing-plans or @.agents/skills/writing-plans/
SKILL_REF_PATTERN = re.compile(r"@\.agents/skills/([-a-z0-9]+)(?:/SKILL\.md|/)?")

CORPUS_GLOBS = (
    ".cursor/rules/**/*.mdc",
    ".claude/skills/**/*.md",
    "harness/claude/skills/**/*.md",
    "harness/claude/rules/**/*.md",
)

DEFAULT_EXCLUDE_PARTS = (
    "_archive",
    ".cursor/templates",
)


@dataclass(frozen=True)
class SkillRef:
    skill_name: str
    source_file: Path
    line_number: int
    raw_match: str


@dataclass(frozen=True)
class MissingSkillRef:
    ref: SkillRef
    expected_path: Path
    error_code: str = "skill_ref_missing"


def extract_skill_refs_from_text(text: str, source_file: Path | None = None) -> list[SkillRef]:
    refs: list[SkillRef] = []
    dummy_file = source_file or Path("<memory>")
    for line_no, line in enumerate(text.splitlines(), start=1):
        for match in SKILL_REF_PATTERN.finditer(line):
            skill_name = match.group(1)
            refs.append(
                SkillRef(
                    skill_name=skill_name,
                    source_file=dummy_file,
                    line_number=line_no,
                    raw_match=match.group(0),
                )
            )
    return refs


def extract_skill_refs_from_file(file_path: Path) -> list[SkillRef]:
    if not file_path.is_file():
        return []
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return extract_skill_refs_from_text(text, source_file=file_path)


def should_exclude(path: Path, exclude_parts: Sequence[str] = DEFAULT_EXCLUDE_PARTS) -> bool:
    as_posix = path.as_posix()
    for part in exclude_parts:
        if part in as_posix:
            return True
    return False


def collect_corpus_files(
    repo_root: Path,
    corpus_globs: Sequence[str] = CORPUS_GLOBS,
    exclude_parts: Sequence[str] = DEFAULT_EXCLUDE_PARTS,
) -> list[Path]:
    collected: set[Path] = set()
    for glob_pat in corpus_globs:
        for p in repo_root.glob(glob_pat):
            if p.is_file() and not should_exclude(p, exclude_parts):
                collected.add(p)
    return sorted(collected)


def collect_corpus_skill_refs(
    repo_root: Path,
    corpus_globs: Sequence[str] = CORPUS_GLOBS,
    exclude_parts: Sequence[str] = DEFAULT_EXCLUDE_PARTS,
) -> list[SkillRef]:
    refs: list[SkillRef] = []
    for file_path in collect_corpus_files(repo_root, corpus_globs, exclude_parts):
        refs.extend(extract_skill_refs_from_file(file_path))
    return refs


def resolve_canonical_skill_path(skill_name: str, repo_root: Path) -> Path:
    """Resolve skill directly to its canonical path without any nested or legacy fallback."""
    return repo_root / ".agents" / "skills" / skill_name / "SKILL.md"


def check_skill_refs(
    repo_root: Path,
    corpus_globs: Sequence[str] = CORPUS_GLOBS,
    exclude_parts: Sequence[str] = DEFAULT_EXCLUDE_PARTS,
) -> list[MissingSkillRef]:
    refs = collect_corpus_skill_refs(repo_root, corpus_globs, exclude_parts)
    missing: list[MissingSkillRef] = []

    # We only check referenced skill paths on canonical target: .agents/skills/<name>/SKILL.md
    for ref in refs:
        canonical_target = repo_root / ".agents" / "skills" / ref.skill_name / "SKILL.md"
        if not canonical_target.exists():
            missing.append(
                MissingSkillRef(
                    ref=ref,
                    expected_path=canonical_target,
                )
            )
    return missing


class MissingSkillRefError(AssertionError):
    """Raised when one or more skill references in the corpus point to non-existent paths."""

    def __init__(self, missing: Sequence[MissingSkillRef]):
        self.missing = list(missing)
        self.error_code = "skill_ref_missing"
        lines = [f"skill_ref_missing: found {len(missing)} missing canonical skill ref(s):"]
        for m in missing:
            lines.append(
                f"  - [{m.error_code}] {m.ref.source_file}:{m.ref.line_number} -> {m.ref.skill_name} "
                f"(expected {m.expected_path})"
            )
        super().__init__("\n".join(lines))


def assert_zero_missing_skill_refs(
    repo_root: Path,
    corpus_globs: Sequence[str] = CORPUS_GLOBS,
    exclude_parts: Sequence[str] = DEFAULT_EXCLUDE_PARTS,
) -> None:
    missing = check_skill_refs(repo_root, corpus_globs=corpus_globs, exclude_parts=exclude_parts)
    if missing:
        raise MissingSkillRefError(missing)

