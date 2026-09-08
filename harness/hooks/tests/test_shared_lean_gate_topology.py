"""Corpus contract tests for shared lean gate topology (FR-003, FR-004, TM-082-01..04).

Covers:
1. Explicit bounded candidate inventory for roadmap-merge, security, and VAN gates across BACK, FRONT, INTEG.
2. Exact roadmap-merge duplicates across roles and BACK/INTEG VAN equivalence while preserving FRONT VAN and security deltas.
3. Fail-closed diagnostics for duplicate local owner, missing role patch, symlinks, local fallbacks, and dangling old paths.
4. Exclusion of archive, history, and runtime scopes from active caller analysis.
"""

from pathlib import Path
import re
import pytest

ROOT = Path(__file__).resolve().parents[3]

# Explicit inventory of candidates and allowlist definitions
ALLOWLIST_LEAN_GATES = {
    "roadmap-merge": [
        "harness/cursor/rules/shared/_lean/roadmap-merge.mdc",
    ],
    "security": [
        "harness/cursor/rules/back_developer/isolation_rules/_lean/security.mdc",
        "harness/cursor/rules/front_developer/isolation_rules/_lean/security.mdc",
        "harness/cursor/rules/integration_developer/isolation_rules/_lean/security.mdc",
    ],
    "van": [
        "harness/cursor/rules/back_developer/isolation_rules/_lean/van.mdc",
        "harness/cursor/rules/front_developer/isolation_rules/_lean/van.mdc",
        "harness/cursor/rules/integration_developer/isolation_rules/_lean/van.mdc",
    ],
}

# Active caller search scope roots
ACTIVE_CORPUS_ROOTS = [
    ROOT / "harness/cursor/rules",
    ROOT / "harness/claude",
    ROOT / ".cursor/rules",
    ROOT / ".claude",
]

# Paths and directories excluded from active topology caller scope
ARCHIVE_AND_HISTORY_EXCLUSIONS = [
    re.compile(r"_archive/"),
    re.compile(r"archive/"),
    re.compile(r"tasks/log/"),
    re.compile(r"memory-bank/"),
    re.compile(r"dsh/"),
    re.compile(r"runtime/"),
    re.compile(r"tests/"),
]

# Security role-specific delta expectations
SECURITY_COMMON_MARKERS = [
    "# SECURITY — gates",
    "**Канон путей:**",
    "## Gates (все submodes)",
    "Path rule: эпик",
    "SECURITY не чинит код",
    "Findings: severity Critical→Low + evidence + suggested fix mode",
    "## PLAN-only",
    "## DECOMPOSE-only",
    "next_phase: * SECURITY",
    "## Abort",
]

SECURITY_ROLE_PATCH_DELTAS = {
    "back": {
        "required_markers": [
            "Role patch (BACK)",
            "api/auth/db/jobs/secrets/deps/ci",
            "BUGFIX / IMPLEMENT (no GAP)",
        ],
        "forbidden_markers": ["(FRONT: XSS/tokens/CSP/bundle/deps)", "INTEG:", "wire×authz×IDOR×contract"],
    },
    "front": {
        "required_markers": [
            "Role patch (FRONT)",
            "XSS/tokens/CSP/bundle/deps",
            "BUGFIX / IMPLEMENT",
        ],
        "forbidden_markers": ["INTEG:", "wire×authz×IDOR×contract", "no GAP"],
    },
    "integ": {
        "required_markers": [
            "Role patch (INTEG)",
            "wire×authz×IDOR×contract",
            "BUGFIX / IMPLEMENT / GAP",
            "drift контракта → GAP",
        ],
        "forbidden_markers": ["(FRONT: XSS/tokens/CSP/bundle/deps)"],
    },
}

DUPLICATED_COMMON_MARKERS = [
    "## Gates (все submodes)",
    "## DECOMPOSE-only",
    "Findings: severity Critical→Low",
    "Path rule: эпик →",
]

VAN_COMMON_MARKERS = [
    "# VAN — gates (shared common contract)",
    "**Карта (brownfield):** `memory-bank/architecture/`",
    "**Brownfield:** @.cursor/rules/shared/workflow-van-brownfield.mdc",
    "**Пути:** @.cursor/rules/shared/memory-bank-paths.mdc",
    "## Gates (common)",
    "memory-bank/` valid",
    "Mode detected: greenfield | brownfield",
    "Complexity / level определён и зафиксирован",
    "architecture shards refreshed",
    "mermaid minimum (services + data-flow + erd|n/a)",
    "## Complexity",
    "## Abort",
]

VAN_ROLE_PATCH_DELTAS = {
    "back": {
        "required_markers": [
            "Role patch (BACK)",
            "memory-bank/back/van/van-YYYYMMDD.md",
            "backend-scope shards",
            "L1–L4 записан в `tasks.md`",
            "L1 → IMPLEMENT",
            "L2–L4 → PLAN",
        ],
        "forbidden_markers": [
            "frontend.md",
            "memory-bank/integration",
            "mapping_filters",
            "UI fix",
            "design system",
        ],
    },
    "integ": {
        "required_markers": [
            "Role patch (INTEG)",
            "memory-bank/integration/van/van-YYYYMMDD-<slug>.md",
            "frontend.md` = absent",
            "Домен/scope",
            "As-built checklist",
            "L1: flat CRUD",
            "L2: filters + URL sync",
            "L3: joins, mapping_filters",
            "L4: dashboard N API",
            "L1 → IMPLEMENT",
            "L2+ → GAP",
        ],
        "forbidden_markers": [
            "memory-bank/back/van",
            "UI fix",
            "design system",
        ],
    },
}

DUPLICATED_VAN_COMMON_MARKERS = [
    "## Gates (common)",
    "mermaid minimum (services + data-flow + erd|n/a)",
    "| L3 | фича, возможен CREATIVE |",
]


def is_active_scope_path(path: Path, root_dir: Path = ROOT) -> bool:
    """Determine whether path is inside active caller scope (excluding archive/history/runtime)."""
    try:
        rel = str(path.relative_to(root_dir))
    except ValueError:
        rel = str(path)
    for pat in ARCHIVE_AND_HISTORY_EXCLUSIONS:
        if pat.search(rel):
            return False
    return True


def check_for_symlinks(paths: list[str | Path], root_dir: Path = ROOT) -> list[str]:
    """Fail-closed check rejecting symlink usage in topology paths."""
    violations = []
    for rel_or_abs in paths:
        full_path = root_dir / rel_or_abs if isinstance(rel_or_abs, str) else rel_or_abs
        if full_path.is_symlink():
            violations.append(f"Symlink forbidden: {rel_or_abs}")
    return violations


def check_for_duplicate_owners(paths: list[str | Path], max_allowed: int = 1, root_dir: Path = ROOT) -> list[str]:
    """Fail-closed check for duplicate local owner copies when single owner expected."""
    existing = [str(p) for p in paths if (root_dir / p).exists()]
    if len(existing) > max_allowed:
        return [f"Duplicate owner detected: multiple copies exist: {existing}"]
    return []


def check_for_local_fallback(shared_path: str, fallback_path: str, root_dir: Path = ROOT) -> list[str]:
    """Fail-closed check rejecting local fallback copies when canonical shared source is missing or bypassed."""
    shared = root_dir / shared_path
    fallback = root_dir / fallback_path
    violations = []
    if fallback.exists():
        if not shared.exists():
            violations.append(f"Local fallback forbidden when shared source is missing: {fallback_path}")
        else:
            violations.append(f"Redundant local fallback forbidden alongside shared source: {fallback_path}")
    return violations


def check_security_role_patch(role: str, content: str) -> list[str]:
    """Verify security role patch has shared reference, role deltas, and no duplicated common body."""
    errors = []
    if "shared/_lean/security.mdc" not in content:
        errors.append(f"missing shared security reference in role patch for {role}")
    deltas = SECURITY_ROLE_PATCH_DELTAS.get(role, {})
    for req in deltas.get("required_markers", []):
        if req not in content:
            errors.append(f"missing role patch delta in security for {role}: '{req}'")
    for forb in deltas.get("forbidden_markers", []):
        if forb in content:
            errors.append(f"unexpected marker in security for {role}: '{forb}'")
    for dup in DUPLICATED_COMMON_MARKERS:
        if dup in content:
            errors.append(f"duplicated common body detected in role patch for {role}: '{dup}'")
    return errors


def check_van_role_patch(role: str, content: str) -> list[str]:
    """Verify VAN role patch has shared reference, role deltas, and no duplicated common body."""
    errors = []
    if "shared/_lean/van.mdc" not in content:
        errors.append(f"missing shared VAN reference in role patch for {role}")
    deltas = VAN_ROLE_PATCH_DELTAS.get(role, {})
    for req in deltas.get("required_markers", []):
        if req not in content:
            errors.append(f"missing role patch delta in VAN for {role}: '{req}'")
    for forb in deltas.get("forbidden_markers", []):
        if forb in content:
            errors.append(f"unexpected marker in VAN for {role}: '{forb}'")
    for dup in DUPLICATED_VAN_COMMON_MARKERS:
        if dup in content:
            errors.append(f"duplicated common body detected in VAN role patch for {role}: '{dup}'")
    return errors


def check_dangling_references(target_pattern: str, search_roots: list[Path], root_dir: Path = ROOT) -> list[tuple[str, int, str]]:
    """Scan active files for dangling references to removed/deprecated paths."""
    findings = []
    regex = re.compile(target_pattern)
    for root in search_roots:
        if not root.exists():
            continue
        for file_path in root.rglob("*.md*"):
            if not is_active_scope_path(file_path, root_dir=root_dir):
                continue
            try:
                text = file_path.read_text(encoding="utf-8")
            except Exception:
                continue
            for line_idx, line in enumerate(text.splitlines(), start=1):
                if regex.search(line):
                    try:
                        rel_name = str(file_path.relative_to(root_dir))
                    except ValueError:
                        rel_name = file_path.name
                    findings.append((rel_name, line_idx, line.strip()))
    return findings


def test_candidate_inventory_is_explicit_and_bounded():
    """cp1: Verify inventory is explicitly bounded to roadmap-merge, security, VAN gates."""
    # Ensure all allowlisted candidate files exist as current baseline
    all_candidates = []
    for gate_type, candidate_list in ALLOWLIST_LEAN_GATES.items():
        for rel_path in candidate_list:
            candidate_file = ROOT / rel_path
            assert candidate_file.exists(), f"Allowlisted candidate path must exist: {rel_path}"
            all_candidates.append(rel_path)

    # Verify roadmap-merge local copies are purged and single shared owner is unique
    purged_roadmap_copies = [
        "harness/cursor/rules/back_developer/isolation_rules/_lean/roadmap-merge.mdc",
        "harness/cursor/rules/front_developer/isolation_rules/_lean/roadmap-merge.mdc",
        "harness/cursor/rules/integration_developer/isolation_rules/_lean/roadmap-merge.mdc",
    ]
    for p in purged_roadmap_copies:
        assert not (ROOT / p).exists(), f"Local roadmap-merge copy must be purged: {p}"

    # Verify unrelated _lean files are excluded from this topology inventory
    unrelated_lean_names = ["implement.mdc", "plan.mdc", "decompose.mdc", "qa.mdc", "refactor.mdc", "bugfix.mdc"]
    for role_dir in ["back_developer", "front_developer", "integration_developer"]:
        lean_dir = ROOT / "harness/cursor/rules" / role_dir / "isolation_rules/_lean"
        if lean_dir.exists():
            for entry in lean_dir.iterdir():
                if entry.name in unrelated_lean_names:
                    rel_p = str(entry.relative_to(ROOT))
                    assert rel_p not in all_candidates, f"Unrelated _lean file {rel_p} must not be in candidate inventory"


def test_roadmap_merge_duplicates_and_back_integ_van_equivalence():
    """cp2: Verify single shared roadmap-merge owner and BACK/INTEG VAN equivalence."""
    # Roadmap merge: single canonical shared owner
    shared_rm = (ROOT / ALLOWLIST_LEAN_GATES["roadmap-merge"][0]).read_text(encoding="utf-8")
    assert "roadmap/queue.yaml" in shared_rm
    assert "workflow-roadmap-merge.mdc" in shared_rm

    # VAN: BACK and INTEG share common domain and brownfield architecture structure
    van_back = (ROOT / ALLOWLIST_LEAN_GATES["van"][0]).read_text(encoding="utf-8")
    van_integ = (ROOT / ALLOWLIST_LEAN_GATES["van"][2]).read_text(encoding="utf-8")
    van_front = (ROOT / ALLOWLIST_LEAN_GATES["van"][1]).read_text(encoding="utf-8")

    # Common structural markers for BACK and INTEG VAN equivalence
    assert "Brownfield" in van_back and "Brownfield" in van_integ
    assert "memory-bank/architecture" in van_back and "memory-bank/architecture" in van_integ

    # FRONT VAN preserves UI-specific semantics and frontend.md artifact
    assert "frontend.md" in van_front, "FRONT VAN must reference frontend.md"
    assert "frontend.md" not in van_back, "BACK VAN must not reference frontend.md"
    assert "UI fix" in van_front or "design system" in van_front, "FRONT VAN must preserve UI semantics"


def test_security_role_deltas_are_present():
    """cp2: Verify security common body and role-specific delta patches."""
    sec_back = (ROOT / ALLOWLIST_LEAN_GATES["security"][0]).read_text(encoding="utf-8")
    sec_front = (ROOT / ALLOWLIST_LEAN_GATES["security"][1]).read_text(encoding="utf-8")
    sec_integ = (ROOT / ALLOWLIST_LEAN_GATES["security"][2]).read_text(encoding="utf-8")

    # Validate BACK role delta
    back_errs = check_security_role_patch("back", sec_back)
    assert not back_errs, f"BACK security validation errors: {back_errs}"

    # Validate FRONT role delta
    front_errs = check_security_role_patch("front", sec_front)
    assert not front_errs, f"FRONT security validation errors: {front_errs}"

    # Validate INTEG role delta
    integ_errs = check_security_role_patch("integ", sec_integ)
    assert not integ_errs, f"INTEG security validation errors: {integ_errs}"


def test_missing_patch_duplicate_owner_and_dangling_path_fail_closed(tmp_path: Path):
    """cp3: Fail-closed checks for missing role patch, duplicate owner, symlink/fallback, and dangling path."""
    # 1. Missing role patch fails deterministically
    corrupted_front_sec = "## Role patch (FRONT)\n**Shared contract:** @.cursor/rules/shared/_lean/security.mdc\n"
    errs = check_security_role_patch("front", corrupted_front_sec)
    assert any("missing role patch delta" in e for e in errs), "Should fail when required role delta is missing"

    # 1b. Duplicated common body in role patch fails deterministically
    duplicated_body_sec = (
        "## Role patch (FRONT)\n**Shared contract:** @.cursor/rules/shared/_lean/security.mdc\n"
        "XSS/tokens/CSP/bundle/deps\nBUGFIX / IMPLEMENT\n"
        "## Gates (все submodes)\nFindings: severity Critical→Low + evidence + suggested fix mode\n"
    )
    dup_body_errs = check_security_role_patch("front", duplicated_body_sec)
    assert any("duplicated common body" in e for e in dup_body_errs), "Should fail when common body is duplicated in patch"

    # 1c. Missing VAN role patch fails deterministically
    corrupted_back_van = "## Role patch (BACK)\n**Shared contract:** @.cursor/rules/shared/_lean/van.mdc\n"
    van_errs = check_van_role_patch("back", corrupted_back_van)
    assert any("missing role patch delta" in e for e in van_errs), "Should fail when required role delta is missing in VAN"

    # 1d. Duplicated common body in VAN role patch fails deterministically
    duplicated_body_van = (
        "## Role patch (BACK)\n**Shared contract:** @.cursor/rules/shared/_lean/van.mdc\n"
        "memory-bank/back/van/van-YYYYMMDD.md\nbackend-scope shards\nL1–L4 записан в `tasks.md`\n"
        "L1 → IMPLEMENT\nL2–L4 → PLAN\n"
        "## Gates (common)\nmermaid minimum (services + data-flow + erd|n/a)\n"
    )
    dup_van_errs = check_van_role_patch("back", duplicated_body_van)
    assert any("duplicated common body" in e for e in dup_van_errs), "Should fail when VAN common body is duplicated in patch"

    # 1e. False merge of FRONT into VAN role patch fails deterministically
    false_front_merge_van = (
        "## Role patch (BACK)\n**Shared contract:** @.cursor/rules/shared/_lean/van.mdc\n"
        "memory-bank/back/van/van-YYYYMMDD.md\nbackend-scope shards\nL1–L4 записан в `tasks.md`\n"
        "L1 → IMPLEMENT\nL2–L4 → PLAN\n"
        "frontend.md UI fix design system\n"
    )
    false_merge_errs = check_van_role_patch("back", false_front_merge_van)
    assert any("unexpected marker in VAN" in e for e in false_merge_errs), "Should fail on false merge with FRONT VAN semantics"

    # 2. Duplicate local owner detection fails deterministically
    synthetic_duplicate_paths = [
        tmp_path / "dup1.mdc",
        tmp_path / "dup2.mdc",
    ]
    for p in synthetic_duplicate_paths:
        p.write_text("duplicate content", encoding="utf-8")
    dup_errs = check_for_duplicate_owners(synthetic_duplicate_paths, max_allowed=1, root_dir=tmp_path)
    assert dup_errs, "Should fail when duplicate owners exist for a single-owner contract"
    assert "Duplicate owner detected" in dup_errs[0]

    # 3. Symlink failure detection on synthetic symlink
    real_file = tmp_path / "target.mdc"
    real_file.write_text("content", encoding="utf-8")
    symlink_file = tmp_path / "symlink.mdc"
    symlink_file.symlink_to(real_file)
    symlink_violations = check_for_symlinks([symlink_file], root_dir=tmp_path)
    assert symlink_violations, "check_for_symlinks must detect synthetic symlink"
    assert "Symlink forbidden" in symlink_violations[0]

    # 4. Local fallback failure detection
    fallback_errs = check_for_local_fallback("shared/missing_source.mdc", "local/fallback.mdc", root_dir=tmp_path)
    assert not fallback_errs, "No error when fallback file does not exist"
    fallback_file = tmp_path / "local" / "fallback.mdc"
    fallback_file.parent.mkdir(parents=True, exist_ok=True)
    fallback_file.write_text("fallback content", encoding="utf-8")
    fallback_errs = check_for_local_fallback("shared/missing_source.mdc", "local/fallback.mdc", root_dir=tmp_path)
    assert fallback_errs, "check_for_local_fallback must fail when local fallback file exists"
    assert "Local fallback forbidden" in fallback_errs[0]

    # 5. Dangling path check helper detects obsolete references in synthetic rule
    synthetic_rule_dir = tmp_path / "rules"
    synthetic_rule_dir.mkdir(parents=True, exist_ok=True)
    bad_rule = synthetic_rule_dir / "workflow-test.mdc"
    bad_rule.write_text("include @.cursor/rules/back_developer/isolation_rules/_lean/obsolete_path.mdc\n", encoding="utf-8")
    dangling_findings = check_dangling_references(r"obsolete_path\.mdc", [synthetic_rule_dir], root_dir=tmp_path)
    assert len(dangling_findings) == 1, "check_dangling_references must catch synthetic dangling reference"
    assert "workflow-test.mdc" in dangling_findings[0][0]


def test_archive_and_runtime_paths_are_outside_active_scope():
    """cp4: Verify archive, history, and runtime scopes are excluded from active caller analysis."""
    # Positive: active rules and claude files
    active_sample_1 = ROOT / "harness/cursor/rules/back_developer/workflow-implement.mdc"
    active_sample_2 = ROOT / ".cursor/rules/mainrule.mdc"
    assert is_active_scope_path(active_sample_1)
    assert is_active_scope_path(active_sample_2)

    # Negative: archive, history, memory-bank, runtime, and test logs
    archive_sample = ROOT / "_archive/cursor-rules/some_rule.mdc"
    memory_bank_sample = ROOT / "memory-bank/back/plan/some_plan.md"
    task_log_sample = ROOT / "tasks/log/2026-09-08.md"
    runtime_sample = ROOT / ".claude/runtime/bash-dumps/dump.log"

    assert not is_active_scope_path(archive_sample), "Archive paths must not be in active scope"
    assert not is_active_scope_path(memory_bank_sample), "Memory-bank history must not be in active scope"
    assert not is_active_scope_path(task_log_sample), "Task logs must not be in active scope"
    assert not is_active_scope_path(runtime_sample), "Runtime dumps must not be in active scope"


def test_shared_roadmap_merge_contract_and_all_callers():
    """Verify shared roadmap-merge owner exists and all three role callers reference it (s02)."""
    shared_owner = ROOT / "harness/cursor/rules/shared/_lean/roadmap-merge.mdc"
    assert shared_owner.exists(), "Shared roadmap-merge owner contract must exist"
    content = shared_owner.read_text(encoding="utf-8")

    # cp1: complete current gate contract preserved
    for marker in [
        "roadmap/queue.yaml",
        "roadmap-queue/v2",
        "workflow-roadmap-merge.mdc",
        "context_loop.py roadmap-merge",
        "Skip done",
        "Topo hard deps",
        "next = DECOMPOSE",
    ]:
        assert marker in content, f"Shared owner must retain marker: {marker}"

    # cp2: BACK, FRONT, and INTEG workflows reference shared lean owner
    callers = [
        ROOT / "harness/cursor/rules/back_developer/workflow-roadmap-merge.mdc",
        ROOT / "harness/cursor/rules/front_developer/workflow-roadmap-merge.mdc",
        ROOT / "harness/cursor/rules/integration_developer/workflow-roadmap-merge.mdc",
    ]
    for caller in callers:
        assert caller.exists(), f"Caller workflow must exist: {caller}"
        c_text = caller.read_text(encoding="utf-8")
        assert "shared/_lean/roadmap-merge.mdc" in c_text, f"{caller.name} must reference shared roadmap-merge owner"
        # cp3: no local fallback or alias
        assert "fallback" not in c_text.lower(), f"{caller.name} must not contain fallback instructions"
        assert "symlink" not in c_text.lower(), f"{caller.name} must not contain symlink references"


def test_shared_security_contract_and_role_patches():
    """Verify shared security owner exists, role patches contain deltas, and workflows reference both (s03)."""
    shared_owner = ROOT / "harness/cursor/rules/shared/_lean/security.mdc"
    assert shared_owner.exists(), "Shared security owner contract must exist"
    content = shared_owner.read_text(encoding="utf-8")

    # cp1: complete common gate contract preserved in shared owner
    for marker in SECURITY_COMMON_MARKERS:
        assert marker in content, f"Shared owner must retain marker: {marker}"

    # cp2: BACK, FRONT, and INTEG role patches have deltas without common duplication
    role_patches = {
        "back": ROOT / ALLOWLIST_LEAN_GATES["security"][0],
        "front": ROOT / ALLOWLIST_LEAN_GATES["security"][1],
        "integ": ROOT / ALLOWLIST_LEAN_GATES["security"][2],
    }
    for role, patch_path in role_patches.items():
        assert patch_path.exists(), f"Role patch must exist: {patch_path}"
        p_text = patch_path.read_text(encoding="utf-8")
        errs = check_security_role_patch(role, p_text)
        assert not errs, f"{role} patch validation errors: {errs}"

    # cp3: BACK, FRONT, and INTEG workflows reference shared lean owner and their role patch
    callers = [
        ROOT / "harness/cursor/rules/back_developer/workflow-security.mdc",
        ROOT / "harness/cursor/rules/front_developer/workflow-security.mdc",
        ROOT / "harness/cursor/rules/integration_developer/workflow-security.mdc",
    ]
    for caller in callers:
        assert caller.exists(), f"Caller workflow must exist: {caller}"
        c_text = caller.read_text(encoding="utf-8")
        assert "shared/_lean/security.mdc" in c_text, f"{caller.name} must reference shared security owner"
        assert "role patch" in c_text or "patch" in c_text, f"{caller.name} must reference role patch"
        assert "fallback" not in c_text.lower(), f"{caller.name} must not contain fallback instructions"
        assert "symlink" not in c_text.lower(), f"{caller.name} must not contain symlink references"


def test_shared_van_contract_role_patches_and_front_independence():
    """Verify shared VAN owner exists, BACK/INTEG role patches contain deltas, FRONT is independent (s04)."""
    shared_owner = ROOT / "harness/cursor/rules/shared/_lean/van.mdc"
    assert shared_owner.exists(), "Shared VAN owner contract must exist"
    content = shared_owner.read_text(encoding="utf-8")

    # cp1: complete common gate contract preserved in shared owner
    for marker in VAN_COMMON_MARKERS:
        assert marker in content, f"Shared owner must retain marker: {marker}"

    # cp2: BACK and INTEG role patches have deltas without common duplication
    role_patches = {
        "back": ROOT / ALLOWLIST_LEAN_GATES["van"][0],
        "integ": ROOT / ALLOWLIST_LEAN_GATES["van"][2],
    }
    for role, patch_path in role_patches.items():
        assert patch_path.exists(), f"Role patch must exist: {patch_path}"
        p_text = patch_path.read_text(encoding="utf-8")
        errs = check_van_role_patch(role, p_text)
        assert not errs, f"{role} patch validation errors: {errs}"

    # cp3: FRONT VAN remains independent local gate with frontend semantics
    front_van_path = ROOT / ALLOWLIST_LEAN_GATES["van"][1]
    assert front_van_path.exists(), "FRONT VAN must exist"
    front_text = front_van_path.read_text(encoding="utf-8")
    assert "FRONT VAN — gates" in front_text
    assert "memory-bank/front/van" in front_text
    assert "frontend.md" in front_text
    assert "shared/_lean/van.mdc" not in front_text, "FRONT VAN must NOT reference shared BACK/INTEG owner"

    # cp4: BACK and INTEG workflows reference shared lean owner and their role patch
    callers = [
        (ROOT / "harness/cursor/rules/back_developer/workflow-van.mdc", "back"),
        (ROOT / "harness/cursor/rules/integration_developer/workflow-van.mdc", "integ"),
    ]
    for caller, role in callers:
        assert caller.exists(), f"Caller workflow must exist: {caller}"
        c_text = caller.read_text(encoding="utf-8")
        assert "shared/_lean/van.mdc" in c_text, f"{caller.name} must reference shared VAN owner"
        assert f"isolation_rules/_lean/van.mdc" in c_text, f"{caller.name} must reference role patch"
        assert "fallback" not in c_text.lower(), f"{caller.name} must not contain fallback instructions"
        assert "symlink" not in c_text.lower(), f"{caller.name} must not contain symlink references"
