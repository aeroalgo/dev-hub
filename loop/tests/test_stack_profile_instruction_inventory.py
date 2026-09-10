from __future__ import annotations

from pathlib import Path
import re
import pytest

from loop.stack_profiles.schemas import CapabilityName
from loop.stack_profiles.execution import CapabilityCheckSpec


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


RUNNER_PATTERNS = [
    re.compile(r"(?:\.venv/bin/|bin/)?pytest\b"),
    re.compile(r"\bcargo\s+test\b"),
    re.compile(r"\bnpm\s+(?:run\s+)?test\b"),
    re.compile(r"\bvitest\b"),
    re.compile(r"\bplaywright\b(?!-)"),
]

HUB_SCOPE_PAT = re.compile(
    r"(?:dev-hub(?:\s+self-tests?)?|hub(?:-only|\s+self-tests?|\s+qa|\s+roots?|\s+tests?|\s+timeout|\s+exception|\s+example)?|"
    r"только\s+dev-hub|только\s+для\s+dev-hub|Hub\s*\(|dev-hub\s*\(|shared/test-timeout|300s\s+built-in|runnable\s+pytest)",
    re.I,
)
MANAGED_SCOPE_PAT = re.compile(
    r"(?:capability_checks|typed\s+(?:execution\s+)?evidence|managed\s+projects?|managed\s+roots?|managed\s+capability|"
    r"managed\s+targets?|managed\s+alternatives?|managed\s+examples?)",
    re.I,
)
NEGATIVE_PAT = re.compile(
    r"(?:forbidden\s*:\s*(?:[^.\n]*?(?:fallback|runner|pytest|command))|"
    r"no\s+fallback\s+to\s+(?:pytest|\.venv)|"
    r"no\s+generic\s+runner|"
    r"does\s+not\s+run\s+(?:pytest|vitest|tests?|suite)|"
    r"never\s+(?:run|edit)[^.\n]*?(?:pytest|code)|"
    r"не\s+запускай\s+(?:pytest|frontend-тесты|тесты)|"
    r"##\s*FORBIDDEN|"
    r"не\s+запускает\s+suite|"
    r"no\s+pytest|"
    r"rejects?\s+(?:raw\s+commands?|unqualified)|"
    r"anti-fallback\s+rg|"
    r"→\s*FAIL|"
    r"список\s+pytest-имён)",
    re.I,
)
PARENT_ONLY_PAT = re.compile(r"(?:parent[- ]only|только\s+parent|parent-агент|front-tests-parent-only)", re.I)
READONLY_PAT = re.compile(r"(?:read-only|только\s+чтение|не\s+запускает\s+suite)", re.I)


def classify_instruction_line(line: str, prev_line: str = "") -> str | None:
    """Classify a single instruction line for unqualified runner actions.

    Returns None if valid/exempt, or a diagnostic error string if unqualified.
    """
    has_runner = any(p.search(line) for p in RUNNER_PATTERNS)
    if not has_runner:
        return None
    combined = f"{prev_line} {line}".strip()
    if NEGATIVE_PAT.search(combined):
        return None
    if PARENT_ONLY_PAT.search(combined):
        return None
    if READONLY_PAT.search(combined):
        return None
    if HUB_SCOPE_PAT.search(combined):
        return None
    if MANAGED_SCOPE_PAT.search(combined):
        return None
    return "unqualified_runner_action"


def get_active_corpus_files(root: Path | None = None) -> list[Path]:
    """Discover all active workflow, rules, skills, entrypoints, and templates."""
    base = root or _repo_root()
    files: set[Path] = set()

    # 1. Cursor rules (excluding _archive)
    for p in (base / "harness/cursor/rules").rglob("*"):
        if p.is_file() and p.suffix in (".mdc", ".md", ".yaml"):
            if "_archive" in p.parts:
                continue
            files.add(p)

    # 2. Claude rules (excluding _archive)
    for p in (base / "harness/claude/rules").rglob("*"):
        if p.is_file() and p.suffix in (".mdc", ".md", ".yaml"):
            if "_archive" in p.parts:
                continue
            files.add(p)

    # 3. Role command skills
    for p in [
        base / "harness/skills/role-command/SKILL.md",
        base / "harness/claude/skills/role-command/SKILL.md",
    ]:
        if p.is_file():
            files.add(p)

    # 4. Entrypoint source and projections
    for p in [
        base / "harness/instructions/main.md",
        base / "AGENTS.md",
        base / "CLAUDE.md",
    ]:
        if p.is_file():
            files.add(p)

    # 5. Templates
    for p in (base / "harness/cursor/templates").rglob("*"):
        if p.is_file() and p.suffix in (".md", ".yaml", ".mdc"):
            files.add(p)

    # 6. Operator docs
    for p in [base / "loop/WORKFLOW.md", base / "loop/README.md"]:
        if p.is_file():
            files.add(p)

    return sorted(list(files))


def scan_file_for_instruction_violations(file_path: Path) -> list[tuple[int, str, str]]:
    """Scan a single file and return list of (line_num, line_content, reason)."""
    text = file_path.read_text(encoding="utf-8", errors="replace")
    violations: list[tuple[int, str, str]] = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        prev = lines[i - 1] if i > 0 else ""
        reason = classify_instruction_line(line, prev)
        if reason:
            violations.append((i + 1, line.strip(), reason))
    return violations


def scan_active_corpus(
    root: Path | None = None,
    path_filter: callable | None = None,
) -> dict[Path, list[tuple[int, str, str]]]:
    """Scan all active corpus files (or a filtered subset) and return violations."""
    active = get_active_corpus_files(root)
    results: dict[Path, list[tuple[int, str, str]]] = {}
    for f in active:
        if path_filter and not path_filter(f):
            continue
        viols = scan_file_for_instruction_violations(f)
        if viols:
            results[f] = viols
    return results


def test_synthetic_fixtures():
    """cp1: Synthetic negative/positive fixtures distinguish unqualified pytest lines from explicit hub exception and capability_checks."""
    positive_fixtures = [
        "Hub (dev-hub self-test): bin/pytest loop/tests/ -q --tb=line",
        "Dev-hub self-tests: run bin/pytest from root.",
        "Только dev-hub: bin/pytest -q --tb=line",
        "Shared timeout contract: bin/pytest ... (300s built-in)",
        "Managed project: declare capability_checks: [test.targeted] and consume typed execution evidence.",
        "capability_checks: [test.full]; typed execution evidence required; do not substitute a raw runner.",
        "FORBIDDEN: fallback to pytest in managed projects.",
        "No fallback to .venv/bin/pytest or raw test commands.",
        "Rejects raw commands such as npm test or cargo test.",
        "No generic runner authority is granted.",
        "ANALYZE is read-only and does not run pytest.",
        "Never edits code; no pytest.",
        "Playwright/Vitest — parent only; subagents never execute browser tests.",
        "FRONT frontend tests: только parent.",
        "Update documentation as necessary.",
    ]

    negative_fixtures = [
        "TDD targeted → code → green (bin/pytest)",
        "TDD red → green: .venv/bin/pytest",
        "regression red → fix → green (.venv/bin/pytest)",
        "Full pytest: bin/pytest -q --tb=line",
        "targeted .venv/bin/pytest -q --tb=line",
        "pytest HTTP outcome",
        "Run cargo test --all-targets before submitting.",
        "Run npm test to verify changes.",
        "Run npm run test for unit tests.",
        "Python tests запускай из корня репозитория через bin/pytest ….",
    ]

    for fix in positive_fixtures:
        res = classify_instruction_line(fix)
        assert res is None, f"Expected positive fixture to be valid, got {res} for: {fix!r}"

    for fix in negative_fixtures:
        res = classify_instruction_line(fix)
        assert res is not None, f"Expected negative fixture to be rejected, got None for: {fix!r}"
        assert res == "unqualified_runner_action"


def test_corpus_inventory():
    """cp2 / FR-001 / FR-009 / SC-001: Discover all active workflow/rules/templates and verify red state diagnostics."""
    root = _repo_root()
    active_files = get_active_corpus_files(root)

    # 1. Verify discovery completeness across all active surfaces
    assert len(active_files) >= 30, f"Expected at least 30 active files, found {len(active_files)}"

    discovered_rel = [str(f.relative_to(root)) for f in active_files]

    # Verify presence of major categories
    assert any("back_developer/workflow-implement.mdc" in p for p in discovered_rel)
    assert any("integration_developer/workflow-implement.mdc" in p for p in discovered_rel)
    assert any("front_developer/mainrule-core.mdc" in p for p in discovered_rel)
    assert any("shared/test-timeout.mdc" in p for p in discovered_rel)
    assert any("claude/rules/context-economy-cc.md" in p for p in discovered_rel)
    assert any("skills/role-command/SKILL.md" in p for p in discovered_rel)
    assert any("harness/instructions/main.md" in p for p in discovered_rel)
    assert any("templates/decompose/epic-step.yaml" in p for p in discovered_rel)
    assert any("loop/WORKFLOW.md" in p for p in discovered_rel)

    # Verify exclusions: no _archive, no tests directory
    for p in discovered_rel:
        assert "_archive" not in p.split("/"), f"Archive path was not excluded: {p}"
        assert not p.startswith("loop/tests/"), f"Test path was not excluded: {p}"
        assert not p.startswith("harness/hooks/tests/"), f"Test path was not excluded: {p}"

    # 2. Scan active corpus and verify exact diagnostics structure
    all_violations = scan_active_corpus(root)
    assert len(all_violations) > 0, "Expected active corpus to report red violations before rewrites"

    for file_path, viols in all_violations.items():
        assert file_path.is_file()
        for line_num, line_content, reason in viols:
            assert line_num > 0
            assert len(line_content) > 0
            assert reason == "unqualified_runner_action"

    # Known unrewritten files must be reported in red state
    unrewritten_samples = [
        "harness/cursor/rules/integration_developer/workflow-implement.mdc",
        "harness/skills/role-command/SKILL.md",
        "harness/instructions/main.md",
    ]
    for sample in unrewritten_samples:
        matching = [p for p in all_violations if sample in str(p)]
        assert len(matching) > 0, f"Expected red violations in unrewritten sample {sample}"


def test_dynamic_discovery_fails_on_injected_ambiguous_runner(tmp_path: Path):
    """AC-4: Adding a new active workflow/rule file with an ambiguous runner line makes the scanner detect it as a violation."""
    rules_dir = tmp_path / "harness" / "cursor" / "rules" / "test_developer"
    rules_dir.mkdir(parents=True)
    injected_file = rules_dir / "workflow-injected.mdc"
    injected_file.write_text(
        "---\ndescription: injected rule\n---\n"
        "TDD targeted → code → green (.venv/bin/pytest)\n",
        encoding="utf-8",
    )

    discovered = get_active_corpus_files(tmp_path)
    assert injected_file in discovered, "Injected rule file was not discovered dynamically"

    violations = scan_file_for_instruction_violations(injected_file)
    assert len(violations) == 1
    assert violations[0][0] == 4
    assert violations[0][2] == "unqualified_runner_action"


def test_back_workflow_inventory():
    """TM-080-01 / TM-080-02 / FR-003: BACK workflow files and lean gates have zero unqualified runner lines."""
    root = _repo_root()
    viols = scan_active_corpus(
        root,
        path_filter=lambda p: "back_developer" in p.parts,
    )
    if viols:
        report = []
        for p, issues in viols.items():
            for line_no, content, reason in issues:
                report.append(f"{p.relative_to(root)}:L{line_no} [{reason}] {content}")
        pytest.fail(f"Unqualified runner actions in BACK workflow/gates:\n" + "\n".join(report))


def test_integ_workflow_inventory():
    """TM-080-03 / FR-004: INTEG workflow files and lean gates have zero unqualified runner lines."""
    root = _repo_root()
    viols = scan_active_corpus(
        root,
        path_filter=lambda p: "integration_developer" in p.parts,
    )
    if viols:
        report = []
        for p, issues in viols.items():
            for line_no, content, reason in issues:
                report.append(f"{p.relative_to(root)}:L{line_no} [{reason}] {content}")
        pytest.fail(f"Unqualified runner actions in INTEG workflow/gates:\n" + "\n".join(report))


def test_front_workflow_inventory():
    """TM-080-09 / FR-005: FRONT workflow and rules have zero unqualified runner lines."""
    root = _repo_root()
    viols = scan_active_corpus(
        root,
        path_filter=lambda p: "front_developer" in p.parts or p.name == "front-tests-parent-only.mdc",
    )
    if viols:
        report = []
        for p, issues in viols.items():
            for line_no, content, reason in issues:
                report.append(f"{p.relative_to(root)}:L{line_no} [{reason}] {content}")
        pytest.fail(f"Unqualified runner actions in FRONT workflow/rules:\n" + "\n".join(report))


def test_shared_rules_inventory():
    """FR-001 / FR-002: Shared rules have zero unqualified runner lines."""
    root = _repo_root()
    viols = scan_active_corpus(
        root,
        path_filter=lambda p: "harness/cursor/rules/shared" in str(p),
    )
    if viols:
        report = []
        for p, issues in viols.items():
            for line_no, content, reason in issues:
                report.append(f"{p.relative_to(root)}:L{line_no} [{reason}] {content}")
        pytest.fail(f"Unqualified runner actions in shared rules:\n" + "\n".join(report))


def test_claude_rules_inventory():
    """FR-001 / FR-002: Claude rules have zero unqualified runner lines."""
    root = _repo_root()
    viols = scan_active_corpus(
        root,
        path_filter=lambda p: "harness/claude/rules" in str(p),
    )
    if viols:
        report = []
        for p, issues in viols.items():
            for line_no, content, reason in issues:
                report.append(f"{p.relative_to(root)}:L{line_no} [{reason}] {content}")
        pytest.fail(f"Unqualified runner actions in Claude rules:\n" + "\n".join(report))


def test_role_command_skills_inventory():
    """TM-080-05 / FR-006: Both role-command skill copies have zero unqualified runner lines and semantic parity."""
    root = _repo_root()
    viols = scan_active_corpus(
        root,
        path_filter=lambda p: p.name == "SKILL.md" and "role-command" in p.parts,
    )
    if viols:
        report = []
        for p, issues in viols.items():
            for line_no, content, reason in issues:
                report.append(f"{p.relative_to(root)}:L{line_no} [{reason}] {content}")
        pytest.fail(f"Unqualified runner actions in role-command skills:\n" + "\n".join(report))


def test_role_command_skills_parity():
    """TM-080-05 / FR-006 / SC-003: Codex and Claude role-command skills carry equivalent hub/managed policy markers."""
    root = _repo_root()
    codex_skill = root / "harness/skills/role-command/SKILL.md"
    claude_skill = root / "harness/claude/skills/role-command/SKILL.md"

    assert codex_skill.is_file(), f"Missing {codex_skill}"
    assert claude_skill.is_file(), f"Missing {claude_skill}"

    codex_text = codex_skill.read_text(encoding="utf-8")
    claude_text = claude_skill.read_text(encoding="utf-8")

    # Both must mention capability_checks or managed
    for text, name in [(codex_text, "Codex"), (claude_text, "Claude")]:
        assert "capability_checks" in text or "managed" in text.lower(), f"{name} skill lacks managed capability guidance"
        assert "hub" in text.lower() or "dev-hub" in text.lower(), f"{name} skill lacks explicit hub scope"


def test_entrypoints_inventory():
    """TM-080-06 / FR-007 / SC-006: Instruction source and runtime entrypoints have zero unqualified runner lines."""
    root = _repo_root()
    viols = scan_active_corpus(
        root,
        path_filter=lambda p: p.name in ("main.md", "AGENTS.md", "CLAUDE.md"),
    )
    if viols:
        report = []
        for p, issues in viols.items():
            for line_no, content, reason in issues:
                report.append(f"{p.relative_to(root)}:L{line_no} [{reason}] {content}")
        pytest.fail(f"Unqualified runner actions in entrypoints:\n" + "\n".join(report))


def test_templates_inventory():
    """TM-080-07 / FR-008 / SC-004: Templates show scoped hub or capability evidence examples with zero unqualified actions."""
    root = _repo_root()
    viols = scan_active_corpus(
        root,
        path_filter=lambda p: "harness/cursor/templates" in str(p),
    )
    if viols:
        report = []
        for p, issues in viols.items():
            for line_no, content, reason in issues:
                report.append(f"{p.relative_to(root)}:L{line_no} [{reason}] {content}")
        pytest.fail(f"Unqualified runner actions in templates:\n" + "\n".join(report))


def test_operator_docs_inventory():
    """FR-001 / FR-002: Operator docs label test commands as dev-hub self-tests."""
    root = _repo_root()
    viols = scan_active_corpus(
        root,
        path_filter=lambda p: p.name in ("WORKFLOW.md", "README.md") and "loop" in p.parts,
    )
    if viols:
        report = []
        for p, issues in viols.items():
            for line_no, content, reason in issues:
                report.append(f"{p.relative_to(root)}:L{line_no} [{reason}] {content}")
        pytest.fail(f"Unqualified runner actions in operator docs:\n" + "\n".join(report))


def test_front_parent_only_boundary():
    """TM-080-09 / FR-005 / FR-010 / SC-007: FRONT parent-only boundary is preserved without introducing test.e2e capability."""
    root = _repo_root()
    instruction_files = [
        root / "harness/claude/skills/role-command/SKILL.md",
        root / "harness/cursor/rules/shared/test-timeout.mdc",
    ]

    for p in instruction_files:
        content = p.read_text(encoding="utf-8")
        if p.name == "SKILL.md":
            assert "FRONT + любой frontend" in content and "только parent" in content
        assert "test.e2e" not in [c.value for c in CapabilityName]


def test_sunset_a_b_c_i_scans_have_no_live_legacy_authority():
    """SC-005 / FR-010: Verification declaration requires target and selector, rejects raw commands."""
    from harness.hooks.tests_format import is_allowed_test_command
    from harness.hooks.test_run_canon import ALLOWED_TEST_PREFIXES

    with pytest.raises(Exception):
        CapabilityCheckSpec(capability="test.full", target="")

    with pytest.raises(Exception):
        CapabilityCheckSpec(capability="invalid.selector", target="backend")

    # Kind A: hub test command authority rejects managed targets
    assert not is_allowed_test_command("cargo test --all-targets")
    assert not is_allowed_test_command("npm run test")
    assert not any(p.startswith("cargo") for p in ALLOWED_TEST_PREFIXES)
