"""Corpus contract tests for workflow hot-path consolidation (FR-001, FR-003, FR-004, TM-081-01..03).

Ensures:
1. Four canonical workflow files are the single owners of '## Hot path' for their modes:
   - BACK DECOMPOSE: harness/cursor/rules/back_developer/workflow-decompose.mdc
   - BACK IMPLEMENT: harness/cursor/rules/back_developer/workflow-implement.mdc
   - BACK PLAN: harness/cursor/rules/back_developer/workflow-plan.mdc
   - INTEG PLAN: harness/cursor/rules/integration_developer/workflow-plan.mdc
2. No dangling references to the four standalone cheatsheets (back-decompose, back-implement, back-plan, integ-plan)
   exist in active workflow/rule scopes.
3. Archive and history paths are explicitly excluded from the active-caller corpus.
"""

from pathlib import Path
import re
import pytest

ROOT = Path(__file__).resolve().parents[3]

# Required mode markers and their canonical owning workflow files
CANONICAL_HOT_PATH_OWNERS = {
    "BACK DECOMPOSE": "harness/cursor/rules/back_developer/workflow-decompose.mdc",
    "BACK IMPLEMENT": "harness/cursor/rules/back_developer/workflow-implement.mdc",
    "BACK PLAN": "harness/cursor/rules/back_developer/workflow-plan.mdc",
    "INTEG PLAN": "harness/cursor/rules/integration_developer/workflow-plan.mdc",
}

# Standalone cheatsheet files that are being consolidated/deprecated
DEPRECATED_CHEATSHEET_PATTERNS = [
    re.compile(r"shared/cheatsheets/back-decompose(?:\.mdc)?"),
    re.compile(r"shared/cheatsheets/back-implement(?:\.mdc)?"),
    re.compile(r"shared/cheatsheets/back-plan(?:\.mdc)?"),
    re.compile(r"shared/cheatsheets/integ-plan(?:\.mdc)?"),
    re.compile(r"cheatsheets/(?:back-decompose|back-implement|back-plan|integ-plan)(?:\.mdc)?"),
]

# Active rule directories to scan for active callers
ACTIVE_CORPUS_ROOTS = [
    ROOT / "harness/cursor/rules",
    ROOT / "harness/claude",
    ROOT / ".cursor/rules",
    ROOT / ".claude",
]

# Patterns for files/directories that are archive/history and must be excluded
ARCHIVE_EXCLUSION_PATTERNS = [
    re.compile(r"_archive/"),
    re.compile(r"archive/"),
    re.compile(r"tasks/log/"),
    re.compile(r"memory-bank/"),
    re.compile(r"\.git/"),
    re.compile(r"\.claude/runtime/"),
    re.compile(r"graphify-out/"),
]


def get_active_corpus_files():
    """Return list of active rule/workflow markdown files, excluding archive/history/vendor/cheatsheets."""
    files = []
    seen = set()
    for root in ACTIVE_CORPUS_ROOTS:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix not in (".md", ".mdc", ".json", ".yaml", ".yml"):
                continue
            rel_str = str(p.relative_to(ROOT))
            if any(pat.search(rel_str) for pat in ARCHIVE_EXCLUSION_PATTERNS):
                continue
            # Skip the standalone cheatsheet files themselves during the active caller reference check
            if "shared/cheatsheets" in rel_str:
                continue
            if rel_str not in seen:
                seen.add(rel_str)
                files.append(p)
    return sorted(files)


def extract_hot_path_sections(file_path: Path) -> list[str]:
    """Extract all '## Hot path' section headers from a file."""
    if not file_path.exists():
        return []
    content = file_path.read_text(encoding="utf-8")
    # Match headers like `## Hot path` or `## Hot path (MODE)` or `## Hot path:`
    matches = re.findall(r"^##\s+Hot path\b.*$", content, re.MULTILINE | re.IGNORECASE)
    return matches


def test_corpus_each_required_mode_has_single_hot_path_owner():
    """cp1 / cp4 / TM-081-02: Check that each of the four required modes has exactly one canonical owner file containing '## Hot path'."""
    missing_or_duplicate = []
    for mode, rel_owner_path in CANONICAL_HOT_PATH_OWNERS.items():
        owner_file = ROOT / rel_owner_path
        if not owner_file.exists():
            missing_or_duplicate.append(f"{mode}: owner file {rel_owner_path} does not exist")
            continue
        sections = extract_hot_path_sections(owner_file)
        if len(sections) == 0:
            missing_or_duplicate.append(f"{mode}: {rel_owner_path} is missing '## Hot path' section")
        elif len(sections) > 1:
            missing_or_duplicate.append(f"{mode}: {rel_owner_path} has multiple ({len(sections)}) '## Hot path' sections")

    assert not missing_or_duplicate, "Hot path owner contract violated:\n" + "\n".join(missing_or_duplicate)


def test_corpus_required_mode_markers_are_present():
    """cp1 / cp4 / TM-081-02: Ensure each canonical owner file declares its exact mode marker."""
    missing_markers = []
    for mode, rel_owner_path in CANONICAL_HOT_PATH_OWNERS.items():
        owner_file = ROOT / rel_owner_path
        if not owner_file.exists():
            missing_markers.append(f"{mode}: file {rel_owner_path} missing")
            continue
        content = owner_file.read_text(encoding="utf-8")
        if mode not in content:
            missing_markers.append(f"{mode}: marker '{mode}' not found in {rel_owner_path}")
        # Also check for presence of ## Hot path
        if not re.search(r"^##\s+Hot path\b", content, re.MULTILINE | re.IGNORECASE):
            missing_markers.append(f"{mode}: embedded '## Hot path' section missing in {rel_owner_path}")

    assert not missing_markers, "Required mode markers or sections missing:\n" + "\n".join(missing_markers)


def test_corpus_old_cheatsheet_reference_is_reported_as_dangling():
    """cp2 / cp4 / TM-081-01: Injected or existing references to standalone cheatsheets in active corpus files are reported as dangling."""
    active_files = get_active_corpus_files()
    dangling_refs = []
    for f in active_files:
        content = f.read_text(encoding="utf-8")
        rel_path = str(f.relative_to(ROOT))
        for line_no, line in enumerate(content.splitlines(), start=1):
            for pat in DEPRECATED_CHEATSHEET_PATTERNS:
                if pat.search(line):
                    dangling_refs.append(f"{rel_path}:{line_no}: {line.strip()}")

    assert not dangling_refs, "Dangling references to standalone cheatsheets found in active corpus:\n" + "\n".join(dangling_refs)


def test_no_standalone_hot_path_sources_after_cutover():
    """s05 / FR-002 / TM-081-03: Verify standalone cheatsheet files are absent after cutover."""
    standalone_files = [
        "harness/cursor/rules/shared/cheatsheets/back-decompose.mdc",
        "harness/cursor/rules/shared/cheatsheets/back-implement.mdc",
        "harness/cursor/rules/shared/cheatsheets/back-plan.mdc",
        "harness/cursor/rules/shared/cheatsheets/integ-plan.mdc",
    ]
    present = []
    for rel_path in standalone_files:
        p = ROOT / rel_path
        if p.exists():
            present.append(rel_path)
    assert not present, f"Standalone cheatsheet files must not exist after cutover: {present}"


def test_no_active_old_cheatsheet_callers():
    """s05 / FR-003 / AC+2: Verify active corpus has zero callers to deprecated cheatsheet files."""
    active_files = get_active_corpus_files()
    callers = []
    for f in active_files:
        content = f.read_text(encoding="utf-8")
        rel_path = str(f.relative_to(ROOT))
        for line_no, line in enumerate(content.splitlines(), start=1):
            for pat in DEPRECATED_CHEATSHEET_PATTERNS:
                if pat.search(line):
                    callers.append(f"{rel_path}:{line_no}: {line.strip()}")
    assert not callers, f"Active callers to deprecated cheatsheet files found:\n" + "\n".join(callers)


def test_required_markers_and_single_owner_after_purge():
    """s05 / FR-001 / AC+1: Verify every canonical owner contains mode marker and exactly one Hot path."""
    for mode, rel_owner_path in CANONICAL_HOT_PATH_OWNERS.items():
        owner_file = ROOT / rel_owner_path
        assert owner_file.exists(), f"Owner file {rel_owner_path} missing"
        content = owner_file.read_text(encoding="utf-8")
        assert mode in content, f"Marker {mode} not found in {rel_owner_path}"
        sections = extract_hot_path_sections(owner_file)
        assert len(sections) == 1, f"Expected exactly 1 '## Hot path' in {rel_owner_path}, got {len(sections)}"


def test_archive_history_excluded_from_active_scan():
    """s05 / AC-3: Ensure archive and history files are excluded from active caller scanning."""
    active_files = get_active_corpus_files()
    active_rel_paths = [str(f.relative_to(ROOT)) for f in active_files]
    for rel in active_rel_paths:
        for pat in ARCHIVE_EXCLUSION_PATTERNS:
            assert not pat.search(rel), f"Archive/history file {rel} was unexpectedly included in active corpus"


def test_archive_and_history_are_not_active_callers():
    """cp3 / TM-081-03: Verify that archive/history paths are correctly excluded from active scan."""
    archive_paths = [
        ROOT / "_archive/cursor-rules/workflow-something.mdc",
        ROOT / "tasks/log/2026-09-08-some-log.md",
        ROOT / "memory-bank/activeContext.md",
    ]
    for p in archive_paths:
        rel_str = str(p.relative_to(ROOT))
        is_excluded = any(pat.search(rel_str) for pat in ARCHIVE_EXCLUSION_PATTERNS)
        assert is_excluded, f"Expected {rel_str} to be classified as archive/history and excluded from active corpus"


def test_back_audit_cheatsheet_and_loader_are_purged():
    cheatsheet = ROOT / "harness/cursor/rules/shared/cheatsheets/back-audit.mdc"
    assert not cheatsheet.exists()
    core_source = (ROOT / "harness/hooks/epic/core.py").read_text(encoding="utf-8")
    assert "shared/cheatsheets/back-audit" not in core_source
