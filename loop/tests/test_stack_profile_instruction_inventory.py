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
    r"(?:#\s*managed\s+project\s+capability\s+check|capability[- ]scoped\s+execution\s+evidence)",
    re.I,
)
NEGATIVE_PAT = re.compile(
    r"(?:forbidden\s*:\s*(?:[^.\n]*?(?:fallback|runner|pytest|command))|"
    r"(?:##\s*|\*\*|#\s*|-\s*)FORBIDDEN|"
    r"FORBIDDEN\s+pytest|"
    r"no\s+fallback\s+to\s+(?:pytest|\.venv)|"
    r"без\s+(?:pytest|fallback(?:\s+на\s+generic|\s+к\s+raw)?|generic\s+fallback)|"
    r"запрещён\s+.*?(?:запуск|pytest|fallback|runner)|"
    r"do\s+not\s+(?:substitute\s+a\s+raw\s+runner|run\s+pytest)|"
    r"without\s+(?:generic\s+fallback|capability_checks)|"
    r"без\s+generic\s+fallback|"
    r"no\s+generic\s+runner|"
    r"does\s+not\s+run\s+(?:pytest|vitest|tests?|suite)|"
    r"never\s+(?:run|edit)[^.\n]*?(?:pytest|code)|"
    r"не\s+запуска(?:й|йте|ть)\s+(?:pytest|frontend-тесты|тесты|vitest|playwright|suite|runner)|"
    r"не\s+(?:гоняй|перезапускай)\s+pytest|"
    r"не\s+запускает\s+suite|"
    r"no\s+pytest|"
    r"rejects?\s+(?:raw\s+commands?|unqualified)|"
    r"anti-fallback\s+rg|"
    r"→\s*FAIL|"
    r"список\s+pytest-имён|"
    r"запуск\s+pytest|"
    r"pytest\s*/\s*implement|"
    r"запрещено)",
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
    if NEGATIVE_PAT.search(line):
        return None
    if READONLY_PAT.search(line):
        return None
    if PARENT_ONLY_PAT.search(line):
        return None
    if HUB_SCOPE_PAT.search(line):
        return None
    if MANAGED_SCOPE_PAT.search(line):
        return None

    if prev_line:
        if not NEGATIVE_PAT.search(prev_line) and not READONLY_PAT.search(prev_line):
            if HUB_SCOPE_PAT.search(prev_line):
                return None
            if PARENT_ONLY_PAT.search(prev_line):
                return None
            if MANAGED_SCOPE_PAT.search(prev_line):
                return None

    return "unqualified_runner_action"


def get_active_corpus_files(root: Path | None = None) -> list[Path]:
    """Discover all active workflow, rules, skills, entrypoints, templates, and agent instructions."""
    base = root or _repo_root()
    files: set[Path] = set()
    seen_resolved: set[Path] = set()

    def _add_file(p: Path) -> None:
        if p.is_file():
            try:
                resolved = p.resolve()
            except OSError:
                resolved = p
            if resolved not in seen_resolved:
                seen_resolved.add(resolved)
                files.add(p)

    # 1. Cursor rules (excluding _archive)
    for p in (base / "harness/cursor/rules").rglob("*"):
        if p.is_file() and p.suffix in (".mdc", ".md", ".yaml"):
            if "_archive" in p.parts:
                continue
            _add_file(p)

    # 2. Claude rules (excluding _archive)
    for p in (base / "harness/claude/rules").rglob("*"):
        if p.is_file() and p.suffix in (".mdc", ".md", ".yaml"):
            if "_archive" in p.parts:
                continue
            _add_file(p)

    # 3. Role command skills
    for p in [
        base / "harness/skills/role-command/SKILL.md",
        base / "harness/claude/skills/role-command/SKILL.md",
    ]:
        if p.is_file():
            _add_file(p)

    # 4. Entrypoint source and projections
    for p in [
        base / "harness/instructions/main.md",
        base / "AGENTS.md",
        base / "CLAUDE.md",
    ]:
        if p.is_file():
            _add_file(p)

    # 5. Templates
    for p in (base / "harness/cursor/templates").rglob("*"):
        if p.is_file() and p.suffix in (".md", ".yaml", ".mdc"):
            _add_file(p)

    # 6. Operator docs
    for p in [base / "loop/WORKFLOW.md", base / "loop/README.md"]:
        if p.is_file():
            _add_file(p)

    # 7. Agent instructions (including symlinked .agents projections if present)
    for agent_dir in [base / "harness/agents", base / ".agents/agents", base / ".agents"]:
        if agent_dir.exists():
            for p in agent_dir.rglob("*.md"):
                if "_archive" in p.parts or "skills" in p.parts:
                    continue
                _add_file(p)

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
        "Managed projects: run bin/pytest -q --tb=line",
        "For managed projects, execute pytest",
        "In managed roots: cargo test --all",
        "Managed capability_checks: run bin/pytest -q --tb=line",
        "Declare capability_checks and execute bin/pytest directly",
        "capability_checks: run pytest",
        "In managed roots, use capability_checks with cargo test",
        "capability_checks: bin/pytest -q --tb=line",
        "For managed projects with capability_checks, execute pytest",
    ]

    for fix in positive_fixtures:
        res = classify_instruction_line(fix)
        assert res is None, f"Expected positive fixture to be valid, got {res} for: {fix!r}"

    for fix in negative_fixtures:
        res = classify_instruction_line(fix)
        assert res is not None, f"Expected negative fixture to be rejected, got None for: {fix!r}"
        assert res == "unqualified_runner_action"


def test_corpus_inventory():
    """cp2 / FR-001 / FR-009 / SC-001: Discover the active corpus and verify clean diagnostics."""
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

    assert any("harness/agents/verify-implement.md" in p for p in discovered_rel)

    # 2. Scan active corpus and verify diagnostic structure and zero violations
    # For rules, skills, entrypoints, templates, and docs (already rewritten in I1)
    non_agent_violations = scan_active_corpus(
        root,
        path_filter=lambda p: "agents" not in p.parts,
    )
    assert isinstance(non_agent_violations, dict)

    report = []
    for file_path, viols in non_agent_violations.items():
        assert file_path.is_file()
        for line_num, line_content, reason in viols:
            assert line_num > 0
            assert len(line_content) > 0
            assert reason == "unqualified_runner_action"
            report.append(f"{file_path.relative_to(root)}:L{line_num} [{reason}] {line_content}")

    details = "\n".join(report)
    assert not non_agent_violations, f"Unqualified runner actions found in active corpus:\n{details}"


def test_diagnostic_structure_on_injected_unrewritten_samples(tmp_path: Path):
    """Preserve red-state diagnostics for representative unrewritten corpus files."""
    unrewritten_samples = [
        "harness/cursor/rules/integration_developer/workflow-implement.mdc",
        "harness/skills/role-command/SKILL.md",
        "harness/instructions/main.md",
    ]
    for sample in unrewritten_samples:
        sample_path = tmp_path / sample
        sample_path.parent.mkdir(parents=True, exist_ok=True)
        sample_path.write_text(
            "---\ndescription: injected fixture\n---\n"
            "TDD targeted → code → green (bin/pytest)\n",
            encoding="utf-8",
        )

    all_violations = scan_active_corpus(tmp_path)
    assert len(all_violations) > 0

    for file_path, viols in all_violations.items():
        assert file_path.is_file()
        for line_num, line_content, reason in viols:
            assert line_num > 0
            assert len(line_content) > 0
            assert reason == "unqualified_runner_action"

    for sample in unrewritten_samples:
        matching = [p for p in all_violations if sample in str(p)]
        assert len(matching) > 0, f"Expected red violations in injected sample {sample}"


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


def test_agents_corpus_discovery(tmp_path: Path):
    """cp1 / FR-I2-001 / AC+ #1 / AC− #7: get_active_corpus_files returns all active harness/agents/**/*.md deduplicated against symlinked .agents."""
    root = _repo_root()
    active_files = get_active_corpus_files(root)
    discovered_rel = [str(f.relative_to(root)) for f in active_files]

    # Verify all active agent instructions are discovered
    expected_agents = [
        "harness/agents/analyze-verify.md",
        "harness/agents/explorer.md",
        "harness/agents/gate-repair.md",
        "harness/agents/reconcile-verify.md",
        "harness/agents/sunset-inventory.md",
        "harness/agents/verify-bugfix.md",
        "harness/agents/verify-decompose.md",
        "harness/agents/verify-edit.md",
        "harness/agents/verify-implement.md",
        "harness/agents/verify-publish.md",
        "harness/agents/verify-qa.md",
        "harness/agents/verify-script.md",
    ]
    for agent_rel in expected_agents:
        assert agent_rel in discovered_rel, f"Active agent instruction missing from corpus discovery: {agent_rel}"

    # Verify non-md and archive files in agents directory are excluded
    assert not any(p.endswith(".py") or p.endswith(".pyc") for p in discovered_rel if "agents" in p)
    assert not any("_archive" in p.split("/") for p in discovered_rel)

    # Test symlink deduplication against .agents/agents tree
    fake_harness_agents = tmp_path / "harness" / "agents"
    fake_harness_agents.mkdir(parents=True)
    fake_agent_file = fake_harness_agents / "custom-agent.md"
    fake_agent_file.write_text("# Custom agent\n", encoding="utf-8")

    fake_dot_agents = tmp_path / ".agents"
    fake_dot_agents.mkdir(parents=True)
    symlink_target = fake_dot_agents / "agents"
    try:
        symlink_target.symlink_to(fake_harness_agents, target_is_directory=True)
        tmp_discovered = get_active_corpus_files(tmp_path)
        # Should contain custom-agent.md exactly once
        custom_matches = [f for f in tmp_discovered if f.name == "custom-agent.md"]
        assert len(custom_matches) == 1, f"Expected exactly 1 deduplicated entry for symlinked agent, found {len(custom_matches)}"
    except (OSError, NotImplementedError):
        pass


def test_agents_corpus_omission_guard(tmp_path: Path):
    """cp2 / FR-I2-008 / AC+ #1 / AC− #1: Omission regression guard fails if agents directory is excluded from discovery."""
    root = _repo_root()
    active_files = get_active_corpus_files(root)

    # Guard function ensuring agents are present in the active corpus
    def assert_corpus_includes_agents(corpus: list[Path]) -> None:
        agent_entries = [f for f in corpus if "agents" in f.parts and f.suffix == ".md"]
        if not agent_entries:
            raise AssertionError("Corpus omission violation: harness/agents/**/*.md excluded from active corpus discovery")

    # 1. Real active corpus must pass the omission guard
    assert_corpus_includes_agents(active_files)

    # 2. Simulated omission (corpus stripped of agents) must trigger failure
    stripped_corpus = [f for f in active_files if "agents" not in f.parts]
    with pytest.raises(AssertionError, match="Corpus omission violation"):
        assert_corpus_includes_agents(stripped_corpus)

    # 3. Dynamic workspace with only agents must be discovered by get_active_corpus_files
    agents_dir = tmp_path / "harness" / "agents"
    agents_dir.mkdir(parents=True)
    test_agent = agents_dir / "guard-test-agent.md"
    test_agent.write_text("# Guard agent\n", encoding="utf-8")

    discovered = get_active_corpus_files(tmp_path)
    assert test_agent in discovered, "Dynamic agent file was omitted from corpus discovery"
    assert_corpus_includes_agents(discovered)


def test_verify_bugfix_and_gate_repair_instruction_parity():
    """cp1, cp2 / FR-I2-004 / FR-I2-006: verify-bugfix and gate-repair have zero unqualified runner lines and qualify Hub vs Managed."""
    root = _repo_root()
    bugfix_path = root / "harness/agents/verify-bugfix.md"
    gate_repair_path = root / "harness/agents/gate-repair.md"

    assert bugfix_path.exists(), "harness/agents/verify-bugfix.md missing"
    assert gate_repair_path.exists(), "harness/agents/gate-repair.md missing"

    # 1. Zero scanner violations on both agent instruction files
    for p in (bugfix_path, gate_repair_path):
        viols = scan_file_for_instruction_violations(p)
        if viols:
            report = [f"{p.relative_to(root)}:L{line_no} [{reason}] {content}" for line_no, content, reason in viols]
            pytest.fail(f"Unqualified runner actions found in {p.relative_to(root)}:\n" + "\n".join(report))

    # 2. Positive checks for verify-bugfix.md (cp1 / FR-I2-004)
    bugfix_content = bugfix_path.read_text(encoding="utf-8")
    assert "Hub (dev-hub self-test)" in bugfix_content, "verify-bugfix.md missing explicit Hub qualification"
    assert "capability_checks" in bugfix_content, "verify-bugfix.md missing explicit capability_checks qualification"
    assert "НЕ запускай frontend-тесты" in bugfix_content, "verify-bugfix.md missing subagent frontend test prohibition"

    # 3. Positive checks for gate-repair.md (cp2 / FR-I2-006)
    gate_repair_content = gate_repair_path.read_text(encoding="utf-8")
    assert "Hub (dev-hub self-test)" in gate_repair_content, "gate-repair.md missing explicit Hub qualification"
    assert "capability_checks" in gate_repair_content, "gate-repair.md missing explicit capability_checks qualification"
    assert "НЕ запускай frontend-тесты" in gate_repair_content, "gate-repair.md missing subagent frontend test prohibition"


def test_verify_qa_instruction_parity():
    """cp1 / FR-I2-005: verify-qa distinguishes Hub parent suite vs Managed capability checks without unqualified runner lines."""
    root = _repo_root()
    qa_path = root / "harness/agents/verify-qa.md"
    assert qa_path.exists(), "harness/agents/verify-qa.md missing"

    # 1. Zero scanner violations
    viols = scan_file_for_instruction_violations(qa_path)
    if viols:
        report = [f"{qa_path.relative_to(root)}:L{line_no} [{reason}] {content}" for line_no, content, reason in viols]
        pytest.fail(f"Unqualified runner actions found in {qa_path.relative_to(root)}:\n" + "\n".join(report))

    # 2. Positive checks for verify-qa.md (FR-I2-005)
    content = qa_path.read_text(encoding="utf-8")
    assert "Hub (dev-hub self-test)" in content or "Hub dev-hub self-test" in content, "verify-qa.md missing Hub qualification"
    assert "capability_checks" in content, "verify-qa.md missing capability_checks qualification"
    assert "не гоняй pytest" in content, "verify-qa.md missing negative subagent pytest prohibition"
    assert "НЕ запускай frontend-тесты" in content, "verify-qa.md missing subagent frontend test prohibition"


def test_readonly_agents_instruction_parity():
    """cp2 / FR-I2-007 / NFR-I2-003: all read-only and specialized agents pass instruction inventory without false positives."""
    root = _repo_root()
    agent_paths = [
        root / "harness/agents/analyze-verify.md",
        root / "harness/agents/explorer.md",
        root / "harness/agents/reconcile-verify.md",
        root / "harness/agents/sunset-inventory.md",
        root / "harness/agents/verify-decompose.md",
        root / "harness/agents/verify-edit.md",
        root / "harness/agents/verify-publish.md",
        root / "harness/agents/verify-script.md",
    ]

    for p in agent_paths:
        assert p.exists(), f"Agent instruction file {p.relative_to(root)} missing"
        viols = scan_file_for_instruction_violations(p)
        if viols:
            report = [f"{p.relative_to(root)}:L{line_no} [{reason}] {content}" for line_no, content, reason in viols]
            pytest.fail(f"Unqualified runner actions found in {p.relative_to(root)}:\n" + "\n".join(report))

    # Check preserved negative/forbidden phrases on read-only agents
    decomp_content = (root / "harness/agents/verify-decompose.md").read_text(encoding="utf-8")
    assert "no pytest" in decomp_content, "verify-decompose.md missing negative no pytest phrase"
    assert "FORBIDDEN pytest" in decomp_content, "verify-decompose.md missing FORBIDDEN pytest phrase"

    analyze_content = (root / "harness/agents/analyze-verify.md").read_text(encoding="utf-8")
    assert "Без pytest" in analyze_content, "analyze-verify.md missing negative Без pytest phrase" 



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


def test_adversarial_classifier_fixtures():
    """AC−-1 / AC−-3: Negative/readonly prev_line must not mask subsequent unqualified runner actions."""
    adversarial_pairs = [
        ("Do not run pytest.", "bin/pytest loop/tests/"),
        ("FORBIDDEN: raw runner fallback", "pytest -q"),
        ("Never run pytest in subagents.", "pytest -q --tb=line"),
        ("ANALYZE is read-only and does not run pytest.", "npm test"),
        ("No fallback to .venv/bin/pytest or raw test commands.", "bin/pytest loop/tests/test_foo.py"),
        ("не запускай тесты", "pytest"),
        ("Не запускать pytest/vitest и не превращать ANALYZE в тестовый режим.", "vitest run"),
        ("без fallback на generic runner", ".venv/bin/pytest"),
        ("without generic fallback", "npm test"),
        ("Rejects raw commands such as npm test or cargo test.", "cargo test"),
        ("## FORBIDDEN", "pytest loop/tests"),
        ("5. STRICTLY READ-ONLY: do not change code", "bin/pytest loop/tests"),
    ]
    for prev, cur in adversarial_pairs:
        res = classify_instruction_line(cur, prev)
        assert res == "unqualified_runner_action", f"Adversarial pair falsely allowed: prev={prev!r}, cur={cur!r}, got {res}"


def test_role_command_skills_parity():
    """TM-080-05 / FR-006 / SC-003 / AC-7 / AC−-5: Codex and Claude role-command skills carry full body equivalence and hub/managed policy markers."""
    root = _repo_root()
    codex_skill = root / "harness/skills/role-command/SKILL.md"
    claude_skill = root / "harness/claude/skills/role-command/SKILL.md"

    assert codex_skill.is_file(), f"Missing {codex_skill}"
    assert claude_skill.is_file(), f"Missing {claude_skill}"

    codex_text = codex_skill.read_text(encoding="utf-8")
    claude_text = claude_skill.read_text(encoding="utf-8")

    # Strict body equivalence
    assert codex_text == claude_text, "Codex and Claude role-command SKILL.md copies drifted"

    # Both must mention capability_checks or managed
    for text, name in [(codex_text, "Codex"), (claude_text, "Claude")]:
        assert "capability_checks" in text, f"{name} skill lacks capability_checks guidance"
        assert "dev-hub" in text or "hub" in text.lower(), f"{name} skill lacks explicit hub scope"


def test_entrypoints_parity():
    """TM-080-06 / FR-007 / SC-006 / AC-7 / AC−-5: AGENTS.md, CLAUDE.md, and main.md have exact Root classification & Testing parity."""
    root = _repo_root()
    entrypoint_files = [
        root / "AGENTS.md",
        root / "CLAUDE.md",
        root / "harness/instructions/main.md",
    ]
    sections = {}
    for p in entrypoint_files:
        assert p.is_file(), f"Missing entrypoint {p}"
        entry_text = p.read_text(encoding="utf-8")
        assert "## Root classification & Testing" in entry_text, f"{p.name} missing '## Root classification & Testing' section"
        sec = entry_text.split("## Root classification & Testing")[1].split("##")[0].strip()
        sections[p.name] = sec

    first_name, first_sec = next(iter(sections.items()))
    for name, sec in sections.items():
        assert sec == first_sec, f"Root classification & Testing section mismatch between {first_name} and {name}:\n{sec}\nvs\n{first_sec}"
        assert "capability_checks" in sec, f"{name} testing section lacks capability_checks"
        assert "dev-hub self-test" in sec, f"{name} testing section lacks dev-hub self-test distinction"


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
    """TM-080-07 / FR-008 / SC-004 / AC-4 / AC+4 / B1: Templates show scoped hub or capability evidence examples with zero unqualified actions and exact structural parity."""
    import yaml
    root = _repo_root()
    viols = scan_active_corpus(
        root,
        path_filter=lambda p: "harness/cursor/templates" in str(p),
    )
    if viols:
        report = []
        for p, issues in viols.items():
            for line_no, content_line, reason in issues:
                report.append(f"{p.relative_to(root)}:L{line_no} [{reason}] {content_line}")
        pytest.fail("Unqualified runner actions in templates:\n" + "\n".join(report))

    # 1. Exact YAML structural parity and required schema/keys validation
    yaml_templates_schema = {
        "harness/cursor/templates/decompose/epic-step.yaml": {
            "schema": "epic-decompose/v1",
            "required_keys": ["schema", "role", "step_id", "plan_id", "title", "next_phase", "needs_creative", "goal", "plan_contract", "context", "as_built", "delta", "deletes", "out_of_scope", "skills", "checkpoints", "verify", "tdd"],
            "required_markers": ["Hub (dev-hub self-test)", "managed: capability_checks: [test.targeted]", "checkpoints[]"],
        },
        "harness/cursor/templates/decompose/legacy-purge-step.yaml": {
            "schema": "epic-decompose/v1",
            "required_keys": ["schema", "role", "step_id", "plan_id", "title", "next_phase", "needs_creative", "goal", "context", "as_built", "delta", "sunset_inventory", "deletes", "out_of_scope", "grep_control", "skills", "checkpoints", "verify", "tdd"],
            "required_markers": ["dev-hub bin/pytest / managed capability_checks", "Hub (dev-hub self-test); managed: capability_checks: [test.targeted]"],
        },
        "harness/cursor/templates/implement/epic-step.yaml": {
            "schema": "epic-implement/v1",
            "required_keys": ["schema", "role", "step_id", "plan_id", "task_id", "title", "level", "status", "decompose_ref", "date", "skills_used", "done", "files", "deletes", "tests", "integration_check", "checkpoints", "resume_from"],
            "required_markers": ["OK (Hub dev-hub self-test)", "OK (Managed project): - 'capability_checks: [test.targeted]'", "tests: []"],
        },
        "harness/cursor/templates/qa/epic-step.yaml": {
            "schema": "epic-qa/v1",
            "required_keys": ["schema", "role", "task_id", "plan_id", "epic_id", "date", "reviewer", "verdict", "scope", "checks", "issues", "blockers", "fix_plan", "limitations", "suite", "checklist_sha256", "ac_plus", "ac_minus", "section_011", "verify_scope"],
            "required_markers": ["full suite green — role-scoped: BACK/hub `bin/pytest -q --tb=line`; FRONT Vitest+Playwright", "BACK/hub: bin/pytest -q --tb=line  # FRONT:"],
        },
        "harness/cursor/templates/refactor/epic-step.yaml": {
            "schema": "epic-refactor/v1",
            "required_keys": ["schema", "role", "step_id", "plan_id", "title", "status", "date", "behavior_freeze", "decompose_ref", "done", "files", "tests", "checkpoints", "resume_from"],
            "required_markers": ["behavior freeze preserved + targeted dev-hub bin/pytest / managed capability_checks green", "tests: []"],
        },
        "harness/cursor/templates/security/epic-step.yaml": {
            "schema": "epic-security/v1",
            "required_keys": ["schema", "role", "step_id", "plan_id", "title", "status", "date", "audit_surface", "scope_paths", "threats", "evidence_commands", "findings", "decompose_ref", "checkpoints", "resume_from"],
            "required_markers": ["bin/pytest … -q  # Hub (dev-hub self-test); managed projects: capability_checks"],
        },
        "harness/cursor/templates/analyze/epic-analyze.yaml": {
            "schema": "epic-analyze/v1",
            "required_keys": ["schema", "role", "plan_id", "slug", "date", "status", "findings", "coverage", "metrics", "recommendation", "next_actions", "constitution_violations"],
            "required_markers": [],
        },
        "harness/cursor/templates/audit/epic-audit.yaml": {
            "schema": "epic-audit/v2",
            "required_keys": ["schema", "role", "epic_id", "plan_id", "date", "auditor", "plan_intent", "summary", "intent_checked", "plan_vs_runtime", "architecture_parity", "findings", "converged", "implemented", "not_implemented", "deviations", "sunset_inventory_scan", "legacy_surfaces_remaining", "fallback_remaining", "instruction_remaining", "purge_step_present", "sot_enforce_scan", "blocked_reason"],
            "required_markers": [],
        },
        "harness/cursor/templates/decompose/index.yaml": {
            "schema": "epic-decompose-index/v1",
            "required_keys": ["schema", "plan_id", "steps"],
            "required_markers": [],
        },
        "harness/cursor/templates/roadmap-queue.yaml": {
            "schema": None,
            "required_keys": ["version", "role", "queue", "done", "batches"],
            "required_markers": [],
        },
    }

    for rel_path, spec in yaml_templates_schema.items():
        tpl_path = root / rel_path
        assert tpl_path.is_file(), f"Missing canonical template {rel_path}"
        raw_text = tpl_path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw_text)
        assert isinstance(data, dict), f"{rel_path} must parse into a YAML dict"
        if spec["schema"] is not None:
            assert data.get("schema") == spec["schema"], f"{rel_path} schema mismatch: expected {spec['schema']}, got {data.get('schema')}"
        for key in spec["required_keys"]:
            assert key in data, f"{rel_path} missing required key '{key}'"
        for marker in spec["required_markers"]:
            assert marker in raw_text, f"{rel_path} lacks required parity marker: {marker!r}"

    # 2. Markdown structural parity and required headers validation
    md_templates_headers = {
        "harness/cursor/templates/plan.md": {
            "required_headers": ["# [T-xxx | slug] PLAN", "## Контекст", "## Delivery closure", "## QA consumes (test plan)", "### Test matrix", "## Replacement / sunset (brownfield)"],
            "required_markers": ["TM-001", "bin/pytest", "dev-hub self-test", "capability_checks: [test.targeted]"],
        },
        "harness/cursor/templates/integration-plan.md": {
            "required_headers": ["# plan-INTEG-<task_id>", "## Суть", "## Продуктовая спека (WHAT)", "## Test matrix", "## Handoff"],
            "required_markers": ["BACK (dev-hub pytest / managed capability_checks)", "FRONT vitest parent-only"],
        },
        "harness/cursor/templates/finish-doc-router.md": {
            "required_headers": ["# FINISH — doc-router update", "## done (один короткий блок)", "## Новый load_now (max 3)"],
            "required_markers": ["dev-hub pytest / managed capability_checks"],
        },
        "harness/cursor/templates/tasks-log-month.md": {
            "required_headers": ["# Delivery log — шаблон месяца", "## Timeline"],
            "required_markers": [],
        },
        "harness/cursor/templates/constitution.md": {
            "required_headers": ["# [Product name] Workflow Constitution", "## MUST", "### MUST-1 — [test and validation policy]"],
            "required_markers": [],
        },
        "harness/cursor/templates/idea-pipeline.md": {
            "required_headers": ["# IDEA: <название>", "## Идея", "## Связь с продуктом"],
            "required_markers": [],
        },
    }

    for rel_path, spec in md_templates_headers.items():
        tpl_path = root / rel_path
        assert tpl_path.is_file(), f"Missing canonical template {rel_path}"
        raw_text = tpl_path.read_text(encoding="utf-8")
        for header in spec["required_headers"]:
            assert header in raw_text, f"{rel_path} missing required section header '{header}'"
        for marker in spec["required_markers"]:
            assert marker in raw_text, f"{rel_path} lacks required parity marker: {marker!r}"


def test_entrypoints_and_templates_have_semantic_destination_parity():
    """TM-080-06 / TM-080-07 / inv-c-05: Runtime entrypoints and template projections maintain exact semantic destination parity."""
    root = _repo_root()
    # 1. Entrypoints parity
    entrypoint_files = [
        root / "AGENTS.md",
        root / "CLAUDE.md",
        root / "harness/instructions/main.md",
    ]
    sections = {}
    for p in entrypoint_files:
        assert p.is_file(), f"Missing entrypoint {p}"
        entry_text = p.read_text(encoding="utf-8")
        assert "## Root classification & Testing" in entry_text, f"{p.name} missing '## Root classification & Testing' section"
        sec = entry_text.split("## Root classification & Testing")[1].split("##")[0].strip()
        sections[p.name] = sec

    first_name, first_sec = next(iter(sections.items()))
    for name, sec in sections.items():
        assert sec == first_sec, f"Root classification & Testing section mismatch between {first_name} and {name}"

    # 2. Template destination / projection parity
    harness_templates_dir = root / "harness/cursor/templates"
    cursor_templates_dir = root / ".cursor/templates"

    assert cursor_templates_dir.exists(), "Missing .cursor/templates directory/symlink"
    for h_path in harness_templates_dir.rglob("*"):
        if h_path.is_file():
            rel = h_path.relative_to(harness_templates_dir)
            c_path = cursor_templates_dir / rel
            assert c_path.is_file(), f"Projected template missing at {c_path}"
            assert h_path.read_text(encoding="utf-8") == c_path.read_text(encoding="utf-8"), (
                f"Template content mismatch between canonical {h_path} and projection {c_path}"
            )


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
    """AC+5 / B2: Comprehensive active corpus scan against sunset legacy patterns (Kind A/B/C/I) and live validator execution."""
    root = _repo_root()
    from harness.hooks.tests_format import validate_tests_entries, is_allowed_test_command
    from harness.hooks.test_run_canon import ALLOWED_TEST_PREFIXES
    from harness.hooks.epic_yaml import EpicImplementDoc, implement_ready_for_finalize_doc

    # === Kind A: Python source & validator authority checks ===
    # 1. CapabilityCheckSpec rejects empty target and invalid selector
    with pytest.raises(Exception):
        CapabilityCheckSpec(capability="test.full", target="")

    with pytest.raises(Exception):
        CapabilityCheckSpec(capability="invalid.selector", target="backend")

    # 2. Hub test command authority rejects unmanaged raw commands
    assert not is_allowed_test_command("cargo test --all-targets")
    assert not is_allowed_test_command("npm run test")
    assert not is_allowed_test_command("vitest run")
    assert not is_allowed_test_command("pytest -q")
    assert not any(p.startswith(("cargo", "npm", "vitest", "go ")) for p in ALLOWED_TEST_PREFIXES)

    # 3. validate_tests_entries execution
    assert validate_tests_entries(["`bin/pytest loop/tests/ -q` — PASS"]) == []
    assert len(validate_tests_entries([], finish=True, require_executable=True)) > 0
    assert len(validate_tests_entries([{"command": "pytest", "result": "pass"}])) > 0

    doc_base = {
        "schema": "epic-implement/v1",
        "role": "back",
        "step_id": "s05",
        "plan_id": "T-HUB-080-workflow-capability-instruction-parity",
        "title": "legacy fallback purge",
        "status": "completed",
        "date": "2026-09-10",
        "done": ["implemented"],
        "files": ["loop/tests/test_stack_profile_instruction_inventory.py"],
        "integration_check": ["passed"],
    }
    valid_capability_doc = EpicImplementDoc(
        **doc_base,
        tests=[
            "`bin/pytest loop/tests/test_stack_profile_instruction_inventory.py -q` — PASS; "
            "capability_checks: [test.targeted]"
        ],
    )
    invalid_raw_command_doc = EpicImplementDoc(
        **doc_base,
        tests=["`pytest loop/tests/test_stack_profile_instruction_inventory.py -q` — PASS"],
    )
    assert implement_ready_for_finalize_doc(valid_capability_doc) == []
    assert implement_ready_for_finalize_doc(invalid_raw_command_doc)

    # === Kind B / Kind C: Anti-fallback & silent defaults active corpus scan ===
    active_files = get_active_corpus_files(root)
    assert len(active_files) >= 50, "Active corpus discovery incomplete"

    kind_b_anti_fallback_patterns = [
        ("generic_fallback", re.compile(r"fallback\s+to\s+(?:pytest|\.venv|generic\s+runner)", re.I)),
        ("unmanaged_runner_fallback", re.compile(r"if\s+(?:capability_checks|managed)\s+(?:missing|unconfigured|fail).*?(?:run|use)\s+pytest", re.I)),
    ]
    for name, pat in kind_b_anti_fallback_patterns:
        for f in active_files:
            content = f.read_text(encoding="utf-8")
            assert not pat.search(content), f"Kind B anti-fallback violation [{name}] in {f.relative_to(root)}"

    kind_c_checks = [
        ("silent_default_runner", re.compile(r"default.*(?:bin/pytest|\.venv/bin/pytest)", re.I)),
        ("unqualified_http_scenario", re.compile(r"(?<!Hub )(?<!Hub \(dev-hub self-test\) )pytest HTTP outcome", re.I)),
    ]
    for name, pat in kind_c_checks:
        for f in active_files:
            content = f.read_text(encoding="utf-8")
            assert not pat.search(content), f"Kind C violation [{name}] in {f.relative_to(root)}"

    # Test file presence-only allowlist check
    test_files = list((root / "loop/tests").glob("*.py"))
    for tf in test_files:
        if tf.name != "test_stack_profile_instruction_inventory.py":
            content = tf.read_text(encoding="utf-8")
            assert not re.search(r"ALLOWED_ACTIVE_FILES\s*=", content), f"Kind C violation in {tf.relative_to(root)}"

    # === Kind I: Active instruction surfaces scan across full corpus for sunset patterns ===
    kind_i_checks = [
        ("inv-i-01", r"green \(bin/pytest\)", [root / "harness/cursor/rules/back_developer"]),
        ("inv-i-02", r"red → green: \.venv/bin/pytest", [root / "harness/cursor/rules/back_developer"]),
        ("inv-i-03", r"regression red → fix → green \(\.venv/bin/pytest\)", [root / "harness/cursor/rules/back_developer"]),
        ("inv-i-04", r"Full pytest \.\.\. bin/pytest", [root / "harness/cursor/rules/back_developer"]),
        ("inv-i-05", r"\.venv/bin/pytest", [root / "harness/cursor/rules/back_developer/mainrule-core.mdc"]),
        ("inv-i-06", r"\.venv/bin/pytest", [root / "harness/cursor/rules/back_developer/isolation_rules/_lean"]),
        ("inv-i-07", r"targeted \.venv/bin/pytest", [root / "harness/cursor/rules/integration_developer"]),
        ("inv-i-08", r"full bin/pytest", [root / "harness/cursor/rules/integration_developer"]),
        (
            "inv-i-09",
            r"\.venv/bin/pytest",
            [
                root / "harness/cursor/rules/integration_developer/mainrule-core.mdc",
                root / "harness/cursor/rules/integration_developer/isolation_rules/_lean",
            ],
        ),
        ("inv-i-10", r"\.venv/bin/pytest", [root / "harness/cursor/rules/front_developer/mainrule-core.mdc"]),
        ("inv-i-11", r"pytest \.\.\.", [root / "harness/cursor/rules/shared/test-timeout.mdc"]),
        ("inv-i-12", r"\.venv/bin/pytest", [root / "harness/claude/rules/context-economy-cc.md"]),
        (
            "inv-i-13",
            r"pytest",
            [
                root / "harness/skills/role-command/SKILL.md",
                root / "harness/claude/skills/role-command/SKILL.md",
            ],
        ),
        ("inv-i-14", r"verify:\s*\"\.venv/bin/pytest", [root / "harness/cursor/templates"]),
        ("inv-i-15", r"bin/pytest", [root / "loop/WORKFLOW.md", root / "loop/README.md"]),
    ]

    # 1. Scoped target checks
    for name, pat, check_paths in kind_i_checks:
        pattern = re.compile(pat)
        for target in check_paths:
            assert target.exists(), f"Kind I target missing [{name}]: {target.relative_to(root)}"
            files = [target] if target.is_file() else list(target.rglob("*"))
            for file_path in files:
                if file_path.is_file() and not file_path.name.endswith(".pyc"):
                    lines = file_path.read_text(encoding="utf-8").splitlines()
                    for line_number, line in enumerate(lines):
                        if pattern.search(line):
                            previous = lines[line_number - 1] if line_number else ""
                            assert classify_instruction_line(line, previous) is None, (
                                f"Kind I violation [{name}] in {file_path.relative_to(root)}:"
                                f"L{line_number + 1} {line.strip()}"
                            )

    # 2. Corpus-wide Kind I scan across ALL active files (entrypoints, rules, skills, templates, docs)
    active_non_agent_files = [f for f in active_files if "agents" not in f.parts]
    for name, pat, _ in kind_i_checks:
        pattern = re.compile(pat)
        for file_path in active_non_agent_files:
            lines = file_path.read_text(encoding="utf-8").splitlines()
            for line_number, line in enumerate(lines):
                if pattern.search(line):
                    previous = lines[line_number - 1] if line_number else ""
                    assert classify_instruction_line(line, previous) is None, (
                        f"Corpus Kind I violation [{name}] in {file_path.relative_to(root)}:"
                        f"L{line_number + 1} {line.strip()}"
                    )
