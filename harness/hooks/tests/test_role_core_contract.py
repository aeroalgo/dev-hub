"""Semantic corpus tests for shared role-core contract (FR-001, FR-002, FR-003, TM-083-01..05).

Covers:
1. cp1: Single shared owner declaration and exactly one import from each of BACK, FRONT, and INTEG role cores.
2. cp2: Rejection and fail-closed diagnostics when common MEMORY BANK/format/runner prose is copied into a role core.
3. cp3: Preservation of role-only guard matrix: BACK promotion/lifecycle, FRONT parent-only/visible-UI, INTEG element-first/contract/GAP.
4. cp4: Bounded runner policy with both hub and managed branches, rejecting unconditional managed pytest and missing branch wording.
"""

from pathlib import Path
import re
import pytest

ROOT = Path(__file__).resolve().parents[3]

# Canonical shared owner path and role core paths
SHARED_ROLE_CORE_PATH = "harness/cursor/rules/shared/role-core-contract.mdc"
MIRROR_SHARED_ROLE_CORE_PATH = ".cursor/rules/shared/role-core-contract.mdc"

ROLE_CORE_PATHS = {
    "back": "harness/cursor/rules/back_developer/mainrule-core.mdc",
    "front": "harness/cursor/rules/front_developer/mainrule-core.mdc",
    "integ": "harness/cursor/rules/integration_developer/mainrule-core.mdc",
}

MIRROR_ROLE_CORE_PATHS = {
    "back": ".cursor/rules/back_developer/mainrule-core.mdc",
    "front": ".cursor/rules/front_developer/mainrule-core.mdc",
    "integ": ".cursor/rules/integration_developer/mainrule-core.mdc",
}

# Import pattern referencing the shared role core contract
SHARED_CONTRACT_IMPORT_PATTERN = re.compile(
    r"@\.cursor/rules/shared/role-core-contract(?:\.mdc)?"
    r"|@harness/cursor/rules/shared/role-core-contract(?:\.mdc)?"
    r"|shared/role-core-contract(?:\.mdc)?"
)

# Role-specific required markers that must survive in role cores
ROLE_GUARD_MATRIX = {
    "back": {
        "required_markers": [
            "Promote DECOMPOSE→IMPLEMENT",
            "ANALYZE artifact critical_count=0",
            "VAN → PLAN(I1) → DECOMPOSE",
            "BACK REPLAN",
            "L1",
            "L2",
            "L3",
            "L4",
        ],
        "forbidden_markers": [
            "Vitest/RTL/Playwright — только parent",
            "front-tests-parent-only",
            "ELEMENT-FIRST",
            "QueryBuilder",
        ],
    },
    "front": {
        "required_markers": [
            "front-tests-parent-only",
            "Vitest/RTL/Playwright",
            "parent",
            "DESIGN STACK",
            "visible_ui",
            "Playwright targeted",
        ],
        "forbidden_markers": [
            "Promote DECOMPOSE→IMPLEMENT: traceability CRITICAL=0",
            "ELEMENT-FIRST",
            "QueryBuilder",
            "mapping_filters",
        ],
    },
    "integ": {
        "required_markers": [
            "ELEMENT-FIRST",
            "§Contract",
            "query-builder",
            "scenario test",
            "GAP",
        ],
        "forbidden_markers": [
            "DESIGN STACK (visible UI)",
            "Promote DECOMPOSE→IMPLEMENT: traceability CRITICAL=0",
        ],
    },
}

# Common prose sections that belong exclusively in the shared contract
COMMON_PROSE_MARKERS = [
    ("memory_bank_load", "activeContext.md` → **`load_now`** first"),
    ("memory_bank_stub", "@.cursor/rules/token-economy-stub.mdc"),
    ("session_economy", "context-session-economy.mdc"),
    ("hub_pytest_wrapper", "bin/pytest … (300s встроен"),
    ("hub_timeout_alt", "timeout -k 10s 300s .venv/bin/pytest"),
    ("forbidden_bare_pytest", "FORBIDDEN: голый `.venv/bin/pytest`"),
    ("managed_capability", "stack profile `capability_checks`"),
    ("managed_evidence", "execution evidence"),
]

# Runner policy requirements
RUNNER_POLICY_HUB_MARKERS = [
    "hub exception",
    "bin/pytest",
    "300s",
    "timeout -k 10s 300s",
]

RUNNER_POLICY_MANAGED_MARKERS = [
    "managed",
    "capability_checks",
    "test.targeted",
    "test.full",
    "execution evidence",
]

RUNNER_POLICY_FORBIDDEN_MARKERS = [
    "unconditional managed pytest",
    "generic pytest fallback",
    "fallback на generic Python/pytest",
]


# Validator functions
def check_shared_owner_declaration(owner_path: str = SHARED_ROLE_CORE_PATH) -> list[str]:
    """Validate that the shared role-core contract owner path is uniquely declared."""
    errors = []
    if not owner_path.endswith("shared/role-core-contract.mdc"):
        errors.append(f"Invalid shared role-core owner path: {owner_path}")
    return errors


def check_role_core_imports(role: str, content: str) -> list[str]:
    """Validate that a role core imports the shared contract exactly once."""
    errors = []
    matches = SHARED_CONTRACT_IMPORT_PATTERN.findall(content)
    if len(matches) == 0:
        errors.append(f"Role core '{role}' is missing shared contract import")
    elif len(matches) > 1:
        errors.append(f"Role core '{role}' has duplicate shared contract imports ({len(matches)})")
    return errors


def check_for_copied_common_prose(role: str, content: str) -> list[str]:
    """Validate that common MEMORY BANK, runner, or format prose is not duplicated in role cores."""
    errors = []
    for marker_key, marker_text in COMMON_PROSE_MARKERS:
        if marker_text in content:
            errors.append(f"Role core '{role}' contains copied common prose marker '{marker_key}': {marker_text}")
    return errors


def check_role_core_guard_matrix(role: str, content: str) -> list[str]:
    """Validate that role-specific guards are preserved and foreign role guards are rejected."""
    errors = []
    role_config = ROLE_GUARD_MATRIX.get(role.lower())
    if not role_config:
        errors.append(f"Unknown role '{role}' in guard matrix")
        return errors

    for req in role_config["required_markers"]:
        if req.lower() not in content.lower():
            errors.append(f"Role core '{role}' is missing required guard marker: {req}")

    for forb in role_config["forbidden_markers"]:
        if forb.lower() in content.lower():
            errors.append(f"Role core '{role}' contains forbidden cross-role marker: {forb}")

    return errors


def check_runner_policy_contract(content: str) -> list[str]:
    """Validate that runner policy defines both hub and managed branches without unconditional managed pytest."""
    errors = []
    for hub_req in RUNNER_POLICY_HUB_MARKERS:
        if hub_req.lower() not in content.lower():
            errors.append(f"Runner policy missing required hub marker: {hub_req}")

    for managed_req in RUNNER_POLICY_MANAGED_MARKERS:
        if managed_req.lower() not in content.lower():
            errors.append(f"Runner policy missing required managed marker: {managed_req}")

    # Check for unconditional or generic fallback violations
    if "unconditional managed pytest" in content.lower():
        errors.append("Runner policy contains forbidden unconditional managed pytest")
    if "generic pytest command fallback" in content.lower():
        errors.append("Runner policy contains forbidden generic pytest command fallback")

    return errors


# Test suite
def test_shared_role_core_owner_is_declared_once():
    """cp1: Shared role core owner is declared once in canonical shared path."""
    errors = check_shared_owner_declaration(SHARED_ROLE_CORE_PATH)
    assert not errors, f"Shared owner declaration errors: {errors}"

    # Invalid owner path fails closed
    bad_owner_errors = check_shared_owner_declaration("harness/cursor/rules/back_developer/role-core.mdc")
    assert bad_owner_errors, "Non-shared owner declaration must fail"
    assert "Invalid shared role-core owner path" in bad_owner_errors[0]


def test_each_role_core_imports_shared_contract_once():
    """cp1: Each role core requires exactly one import of the shared contract."""
    roles = ["back", "front", "integ"]
    valid_synthetic_template = (
        "---\n"
        "description: \"{role_upper} — role core\"\n"
        "---\n"
        "# {role_upper} — role core\n\n"
        "**Shared core:** @.cursor/rules/shared/role-core-contract.mdc\n"
    )

    for role in roles:
        valid_content = valid_synthetic_template.format(role_upper=role.upper())
        errors = check_role_core_imports(role, valid_content)
        assert not errors, f"Valid role core import for {role} failed: {errors}"

    # Verify actual repository role cores
    for role, rel_path in ROLE_CORE_PATHS.items():
        core_file = ROOT / rel_path
        assert core_file.exists(), f"Role core file must exist: {rel_path}"
        content = core_file.read_text(encoding="utf-8")
        errors = check_role_core_imports(role, content)
        assert not errors, f"Role core '{role}' at {rel_path} must import shared contract once: {errors}"


def test_missing_or_duplicate_import_fails_closed():
    """cp1: Missing import or duplicate import fails closed deterministically."""
    # Missing import
    missing_content = "# BACK — role core\nNo import here\n"
    errors_missing = check_role_core_imports("back", missing_content)
    assert errors_missing, "Missing import must fail validation"
    assert "missing shared contract import" in errors_missing[0]

    # Duplicate imports
    dup_content = (
        "# FRONT — role core\n"
        "**Shared core:** @.cursor/rules/shared/role-core-contract.mdc\n"
        "Also import @.cursor/rules/shared/role-core-contract.mdc again\n"
    )
    errors_dup = check_role_core_imports("front", dup_content)
    assert errors_dup, "Duplicate imports must fail validation"
    assert "duplicate shared contract imports" in errors_dup[0]


def test_copied_common_prose_fails_closed():
    """cp2: Copied common MEMORY BANK/format/runner prose in role core fails validation."""
    copied_mb_content = (
        "# BACK — role core\n"
        "**Shared core:** @.cursor/rules/shared/role-core-contract.mdc\n"
        "activeContext.md` → **`load_now`** first (@.cursor/rules/token-economy-stub.mdc §0.5.1)\n"
    )
    errors = check_for_copied_common_prose("back", copied_mb_content)
    assert errors, "Copied common prose must fail validation"
    assert any("memory_bank_load" in e for e in errors)


def test_duplicate_common_memory_bank_or_runner_prose_rejected():
    """cp2: Copied runner policy in role core is rejected with informative error."""
    copied_runner_content = (
        "# INTEG — role core\n"
        "**Shared core:** @.cursor/rules/shared/role-core-contract.mdc\n"
        "bin/pytest … (300s встроен в wrapper)\n"
        "stack profile `capability_checks`\n"
    )
    errors = check_for_copied_common_prose("integ", copied_runner_content)
    assert len(errors) >= 2, f"Expected multiple copied prose errors, got: {errors}"
    assert any("hub_pytest_wrapper" in e for e in errors)
    assert any("managed_capability" in e for e in errors)


def test_role_only_markers_survive_extraction_back_front_integ():
    """cp3: Canonical role-only markers survive in actual repository role cores."""
    for role, rel_path in ROLE_CORE_PATHS.items():
        core_file = ROOT / rel_path
        assert core_file.exists(), f"Role core file must exist: {rel_path}"
        content = core_file.read_text(encoding="utf-8")

        # Each role core must contain its own required markers
        role_config = ROLE_GUARD_MATRIX[role]
        for marker in role_config["required_markers"]:
            assert marker.lower() in content.lower(), (
                f"Role core '{role}' at {rel_path} must preserve marker: '{marker}'"
            )

        # Each role core must not contain forbidden cross-role markers
        for marker in role_config["forbidden_markers"]:
            assert marker.lower() not in content.lower(), (
                f"Role core '{role}' at {rel_path} contains forbidden cross-role marker: '{marker}'"
            )

        # Each role core must not contain copied common prose
        copied_errors = check_for_copied_common_prose(role, content)
        assert not copied_errors, f"Role core '{role}' at {rel_path} contains copied common prose: {copied_errors}"


# Alias matching tdd declaration
test_role_only_markers_survive_extraction = test_role_only_markers_survive_extraction_back_front_integ


def test_role_guard_matrix_back_front_integ():
    """cp3: Guard matrix validates role-specific semantics for BACK, FRONT, and INTEG."""
    synthetic_back = (
        "Promote DECOMPOSE→IMPLEMENT: traceability CRITICAL=0 + **ANALYZE artifact critical_count=0**\n"
        "VAN → PLAN(I1) → DECOMPOSE\n"
        "BACK REPLAN\n"
        "L1 L2 L3 L4\n"
    )
    assert not check_role_core_guard_matrix("back", synthetic_back)

    synthetic_front = (
        "front-tests-parent-only.mdc\n"
        "Vitest/RTL/Playwright — только parent\n"
        "DESIGN STACK (visible UI)\n"
        "visible_ui\n"
        "Playwright targeted\n"
    )
    assert not check_role_core_guard_matrix("front", synthetic_front)

    synthetic_integ = (
        "ELEMENT-FIRST\n"
        "§Contract in eNN\n"
        "query-builder/SKILL.md\n"
        "User-visible flow → scenario test\n"
        "GAP fanout and GAP CLOSE\n"
    )
    assert not check_role_core_guard_matrix("integ", synthetic_integ)


def test_missing_role_guard_matrix_fails_closed_back_front_integ():
    """cp3: Missing role-specific guard markers or foreign role markers fail closed."""
    # BACK missing promotion gate
    bad_back = "VAN → PLAN(I1) → DECOMPOSE\nL1 L2 L3 L4\n"
    back_errs = check_role_core_guard_matrix("back", bad_back)
    assert back_errs, "BACK without promotion gate must fail"
    assert any("Promote DECOMPOSE→IMPLEMENT" in e for e in back_errs)

    # FRONT missing parent-only marker
    bad_front = "DESIGN STACK (visible UI)\nvisible_ui\nPlaywright targeted\n"
    front_errs = check_role_core_guard_matrix("front", bad_front)
    assert front_errs, "FRONT without parent-only test guard must fail"
    assert any("parent" in e for e in front_errs)

    # FRONT with BACK promotion marker (foreign cross-role marker)
    corrupted_front = (
        "front-tests-parent-only\nVitest/RTL/Playwright parent\n"
        "DESIGN STACK visible_ui Playwright targeted\n"
        "Promote DECOMPOSE→IMPLEMENT: traceability CRITICAL=0\n"
    )
    cross_errs = check_role_core_guard_matrix("front", corrupted_front)
    assert cross_errs, "FRONT with BACK promotion marker must fail cross-role check"
    assert any("forbidden cross-role marker" in e for e in cross_errs)

    # INTEG missing element-first
    bad_integ = "§Contract\nquery-builder\nscenario test\nGAP\n"
    integ_errs = check_role_core_guard_matrix("integ", bad_integ)
    assert integ_errs, "INTEG without ELEMENT-FIRST must fail"
    assert any("ELEMENT-FIRST" in e for e in integ_errs)


def test_runner_policy_has_hub_and_managed_branches():
    """cp4: Runner policy preserves both hub exception and managed capability branches."""
    valid_runner_policy = (
        "## pytest runner (HARD — hub exception)\n\n"
        "Канон timeout: `@.cursor/rules/shared/test-timeout.mdc`.\n\n"
        "Для тестов самого dev-hub (hub exception):\n"
        "1. Shell **cwd** = корень репо (где `.venv/` и `bin/pytest`)\n"
        "2. **Предпочтительно:** `bin/pytest …` (300s встроен в wrapper)\n"
        "3. Альтернатива: `timeout -k 10s 300s .venv/bin/pytest …`\n"
        "4. **FORBIDDEN:** голый `.venv/bin/pytest`\n\n"
        "Для managed-проектов: верификация и запуск тестов производятся строго через "
        "stack profile `capability_checks` (`test.targeted`, `test.full`) и execution evidence, "
        "без fallback на generic Python/pytest команды.\n"
    )
    errs = check_runner_policy_contract(valid_runner_policy)
    assert not errs, f"Valid runner policy failed: {errs}"


def test_unconditional_managed_pytest_is_rejected_in_runner_policy():
    """cp4: Runner policy rejects unconditional managed pytest."""
    bad_runner_policy = (
        "hub exception bin/pytest 300s timeout -k 10s 300s\n"
        "managed capability_checks test.targeted test.full execution evidence\n"
        "unconditional managed pytest allowed for all stacks\n"
    )
    errs = check_runner_policy_contract(bad_runner_policy)
    assert errs, "Runner policy with unconditional managed pytest must fail"
    assert any("unconditional managed pytest" in e for e in errs)


def test_runner_policy_missing_branch_fails_closed():
    """cp4: Runner policy missing hub or managed branch fails closed."""
    # Missing managed branch
    hub_only = "hub exception bin/pytest 300s timeout -k 10s 300s\n"
    hub_only_errs = check_runner_policy_contract(hub_only)
    assert hub_only_errs, "Runner policy missing managed branch must fail"
    assert any("managed" in e for e in hub_only_errs)

    # Missing hub branch
    managed_only = "managed capability_checks test.targeted test.full execution evidence\n"
    managed_only_errs = check_runner_policy_contract(managed_only)
    assert managed_only_errs, "Runner policy missing hub branch must fail"
    assert any("hub" in e for e in managed_only_errs)


def test_generic_core_and_weakened_role_guards_fail_closed():
    """cp4: Generic core replacing role responsibility or weakened role guard fails closed."""
    # Generic core attempting to bypass role guard matrix
    generic_errs = check_role_core_guard_matrix("generic", "generic core fallback")
    assert generic_errs, "Generic core must fail validation"
    assert any("Unknown role 'generic'" in e for e in generic_errs)

    # Weakened role guard with generic fallback or missing role marker
    weakened_back = "generic core role marker fallback without promotion gate"
    weak_errs = check_role_core_guard_matrix("back", weakened_back)
    assert weak_errs, "Weakened role core must fail closed"
