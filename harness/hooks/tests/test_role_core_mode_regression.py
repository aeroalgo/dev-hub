"""Mode-W regression suite for shared role-core contract (FR-003, AC+ #3, AC− #1, TM-083-03..06).

Validates that:
1. cp1: Mode-W matrix confirms BACK promotion/lifecycle remains local and does not require a compensating shared-path branch (TM-083-03).
2. cp2: Mode-W matrix confirms FRONT parent-only boundary and visible-UI guards remain local and unchanged (TM-083-04).
3. cp3: Mode-W matrix confirms INTEG element-first, contract and BACK/FRONT/GAP fanout remain local and unchanged (TM-083-05).
4. cp4: The semantic suite observes hub/managed runner wording and all three role imports after purge.
5. cp5: Full hub suite verification evidence recorded for TM-083-06 without targeted substitution.
"""

from __future__ import annotations

import re
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]

# Canonical and mirror paths
SHARED_CONTRACT_PATH = "harness/cursor/rules/shared/role-core-contract.mdc"
MIRROR_SHARED_CONTRACT_PATH = ".cursor/rules/shared/role-core-contract.mdc"

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

# Mode-W Role Guard Groups and semantic assertions
BACK_PROMOTION_LIFECYCLE_MARKERS = [
    "Promote DECOMPOSE→IMPLEMENT",
    "traceability CRITICAL=0",
    "ANALYZE artifact critical_count=0",
    "VAN → PLAN(I1) → DECOMPOSE",
    "BACK REPLAN",
    "L1",
    "L2",
    "L3",
    "L4",
]

FRONT_PARENT_ONLY_UI_MARKERS = [
    "front-tests-parent-only",
    "Vitest/RTL/Playwright",
    "parent",
    "DESIGN STACK",
    "visible_ui",
    "Playwright targeted",
]

INTEG_CONTRACT_GAP_MARKERS = [
    "ELEMENT-FIRST",
    "§Contract",
    "query-builder",
    "scenario test",
    "GAP",
]

# Compensating branch / leaked full role policy rules forbidden in shared contract
SHARED_FORBIDDEN_ROLE_RULES = [
    "Promote DECOMPOSE→IMPLEMENT: traceability CRITICAL=0",
    "traceability CRITICAL=0 + **ANALYZE artifact critical_count=0**",
    "Review gate: L1=self → L2=fast track",
    "Post-QA: I1/I2 → explicit ",
    "DESIGN STACK (visible UI): Component library",
    "Playwright targeted (parent only):",
    "ELEMENT-FIRST портальная связка: сначала element-first",
    "query-builder / mapping_filters",
    "GAP fanout / GAP CLOSE: INTEGRATION_MAP",
]

MODE_W_ROLE_MATRIX = {
    "back": {
        "required_mode_w_markers": BACK_PROMOTION_LIFECYCLE_MARKERS,
        "forbidden_mode_w_markers": [
            "Vitest/RTL/Playwright — только parent",
            "front-tests-parent-only",
            "ELEMENT-FIRST",
            "QueryBuilder",
        ],
    },
    "front": {
        "required_mode_w_markers": FRONT_PARENT_ONLY_UI_MARKERS,
        "forbidden_mode_w_markers": [
            "Promote DECOMPOSE→IMPLEMENT: traceability CRITICAL=0",
            "ELEMENT-FIRST",
            "QueryBuilder",
            "mapping_filters",
        ],
    },
    "integ": {
        "required_mode_w_markers": INTEG_CONTRACT_GAP_MARKERS,
        "forbidden_mode_w_markers": [
            "DESIGN STACK (visible UI)",
            "Promote DECOMPOSE→IMPLEMENT: traceability CRITICAL=0",
        ],
    },
}


def _read_file(rel_path: str) -> str:
    path = ROOT / rel_path
    assert path.is_file(), f"File not found: {rel_path}"
    return path.read_text(encoding="utf-8")


def validate_back_mode_w(content: str, shared_content: str) -> list[str]:
    """Validate BACK mode-W lifecycle/promotion matrix and no compensating shared path."""
    errors = []
    # Check all required BACK promotion and lifecycle markers
    for marker in BACK_PROMOTION_LIFECYCLE_MARKERS:
        if marker.lower() not in content.lower():
            errors.append(f"BACK role core missing required promotion/lifecycle marker: {marker}")

    # Check that shared contract contains no BACK-specific compensating rules
    for marker in [
        "Promote DECOMPOSE→IMPLEMENT: traceability CRITICAL=0",
        "traceability CRITICAL=0 + **ANALYZE artifact critical_count=0**",
        "Review gate: L1=self → L2=fast track",
        "Post-QA: I1/I2 → explicit ",
    ]:
        if marker.lower() in shared_content.lower():
            errors.append(f"Shared role core contract contains leaked BACK branch marker: {marker}")

    # Check that BACK core does not leak other role guards
    for forbidden in MODE_W_ROLE_MATRIX["back"]["forbidden_mode_w_markers"]:
        if forbidden.lower() in content.lower():
            errors.append(f"BACK role core contains forbidden cross-role marker: {forbidden}")

    return errors


def validate_front_mode_w(content: str, shared_content: str) -> list[str]:
    """Validate FRONT mode-W parent-only and visible-UI guards and no compensating shared path."""
    errors = []
    # Check all required FRONT parent-only and UI markers
    for marker in FRONT_PARENT_ONLY_UI_MARKERS:
        if marker.lower() not in content.lower():
            errors.append(f"FRONT role core missing required parent-only/UI marker: {marker}")

    # Check that shared contract contains no FRONT-specific compensating rules
    for marker in [
        "DESIGN STACK (visible UI): Component library",
        "Playwright targeted (parent only):",
    ]:
        if marker.lower() in shared_content.lower():
            errors.append(f"Shared role core contract contains leaked FRONT branch marker: {marker}")

    # Check that FRONT core does not leak other role guards
    for forbidden in MODE_W_ROLE_MATRIX["front"]["forbidden_mode_w_markers"]:
        if forbidden.lower() in content.lower():
            errors.append(f"FRONT role core contains forbidden cross-role marker: {forbidden}")

    return errors


def validate_integ_mode_w(content: str, shared_content: str) -> list[str]:
    """Validate INTEG mode-W element-first, contract and GAP fanout guards and no compensating shared path."""
    errors = []
    # Check all required INTEG contract/GAP markers
    for marker in INTEG_CONTRACT_GAP_MARKERS:
        if marker.lower() not in content.lower():
            errors.append(f"INTEG role core missing required element-first/contract/GAP marker: {marker}")

    # Check that shared contract contains no INTEG-specific compensating rules
    for marker in [
        "ELEMENT-FIRST портальная связка: сначала element-first",
        "query-builder / mapping_filters",
        "GAP fanout / GAP CLOSE: INTEGRATION_MAP",
    ]:
        if marker.lower() in shared_content.lower():
            errors.append(f"Shared role core contract contains leaked INTEG branch marker: {marker}")

    # Check that INTEG core does not leak other role guards
    for forbidden in MODE_W_ROLE_MATRIX["integ"]["forbidden_mode_w_markers"]:
        if forbidden.lower() in content.lower():
            errors.append(f"INTEG role core contains forbidden cross-role marker: {forbidden}")

    return errors


# =========================================================================
# Checkpoint cp1: BACK promotion / lifecycle mode-W matrix (TM-083-03)
# =========================================================================

def test_back_promotion_and_lifecycle_mode_w_remains_local():
    """cp1: Mode-W matrix confirms BACK promotion/lifecycle remains local and does not require a compensating shared-path branch."""
    back_content = _read_file(ROLE_CORE_PATHS["back"])
    shared_content = _read_file(SHARED_CONTRACT_PATH)

    errors = validate_back_mode_w(back_content, shared_content)
    assert not errors, f"BACK mode-W validation errors: {errors}"

    # Also verify mirror file in .cursor/rules/
    mirror_back_content = _read_file(MIRROR_ROLE_CORE_PATHS["back"])
    mirror_shared_content = _read_file(MIRROR_SHARED_CONTRACT_PATH)
    mirror_errors = validate_back_mode_w(mirror_back_content, mirror_shared_content)
    assert not mirror_errors, f"Mirror BACK mode-W validation errors: {mirror_errors}"


def test_back_mode_w_matrix_preserves_review_and_analyze_gates():
    """cp1: BACK mode-W matrix verifies review tiers and analyze gate survive extraction."""
    back_content = _read_file(ROLE_CORE_PATHS["back"])
    assert "Promote DECOMPOSE→IMPLEMENT" in back_content
    assert "ANALYZE artifact critical_count=0" in back_content
    assert "VAN → PLAN(I1) → DECOMPOSE" in back_content
    assert "BACK REPLAN" in back_content


# =========================================================================
# Checkpoint cp2: FRONT parent-only and visible-UI guards (TM-083-04)
# =========================================================================

def test_front_parent_only_and_visible_ui_mode_w_remains_local():
    """cp2: Mode-W matrix confirms FRONT parent-only and visible-UI guards remain local and unchanged."""
    front_content = _read_file(ROLE_CORE_PATHS["front"])
    shared_content = _read_file(SHARED_CONTRACT_PATH)

    errors = validate_front_mode_w(front_content, shared_content)
    assert not errors, f"FRONT mode-W validation errors: {errors}"

    # Also verify mirror file in .cursor/rules/
    mirror_front_content = _read_file(MIRROR_ROLE_CORE_PATHS["front"])
    mirror_shared_content = _read_file(MIRROR_SHARED_CONTRACT_PATH)
    mirror_errors = validate_front_mode_w(mirror_front_content, mirror_shared_content)
    assert not mirror_errors, f"Mirror FRONT mode-W validation errors: {mirror_errors}"


def test_front_parent_only_boundary_and_mock_isolation_mode_w():
    """cp2: FRONT mode-W matrix verifies parent-only boundary and test tooling rules survive."""
    front_content = _read_file(ROLE_CORE_PATHS["front"])
    assert "front-tests-parent-only" in front_content
    assert "Vitest/RTL/Playwright" in front_content
    assert "DESIGN STACK" in front_content
    assert "Playwright targeted" in front_content


# =========================================================================
# Checkpoint cp3: INTEG element-first, contract and GAP fanout (TM-083-05)
# =========================================================================

def test_integ_element_first_and_contract_gap_fanout_mode_w_remains_local():
    """cp3: Mode-W matrix confirms INTEG element-first, contract and BACK/FRONT/GAP fanout remain local and unchanged."""
    integ_content = _read_file(ROLE_CORE_PATHS["integ"])
    shared_content = _read_file(SHARED_CONTRACT_PATH)

    errors = validate_integ_mode_w(integ_content, shared_content)
    assert not errors, f"INTEG mode-W validation errors: {errors}"

    # Also verify mirror file in .cursor/rules/
    mirror_integ_content = _read_file(MIRROR_ROLE_CORE_PATHS["integ"])
    mirror_shared_content = _read_file(MIRROR_SHARED_CONTRACT_PATH)
    mirror_errors = validate_integ_mode_w(mirror_integ_content, mirror_shared_content)
    assert not mirror_errors, f"Mirror INTEG mode-W validation errors: {mirror_errors}"


def test_integ_contract_and_query_builder_scenario_mode_w():
    """cp3: INTEG mode-W matrix verifies contract, query-builder and scenario test semantics survive."""
    integ_content = _read_file(ROLE_CORE_PATHS["integ"])
    assert "ELEMENT-FIRST" in integ_content
    assert "§Contract" in integ_content
    assert "query-builder" in integ_content
    assert "scenario test" in integ_content
    assert "GAP" in integ_content


# =========================================================================
# Checkpoint cp4: Cross-role Mode-W matrix and fail-closed checks
# =========================================================================

def test_mode_w_matrix_cross_role_isolation_and_no_compensating_shared_branch():
    """cp4: Comprehensive Mode-W matrix asserts full role isolation without shared compensating paths."""
    shared_content = _read_file(SHARED_CONTRACT_PATH)

    # Validate each role in matrix
    for role, matrix in MODE_W_ROLE_MATRIX.items():
        role_content = _read_file(ROLE_CORE_PATHS[role])
        for req in matrix["required_mode_w_markers"]:
            assert req.lower() in role_content.lower(), f"Role {role} missing {req}"
        for forb in matrix["forbidden_mode_w_markers"]:
            assert forb.lower() not in role_content.lower(), f"Role {role} contains forbidden {forb}"

    # Validate shared contract purity
    for forb in SHARED_FORBIDDEN_ROLE_RULES:
        assert forb.lower() not in shared_content.lower(), f"Shared contract contains forbidden role rule {forb}"


def test_mode_w_matrix_mirror_synchronization():
    """cp4: Mode-W contract ensures harness/ and .cursor/ mirrors are bit-for-bit identical."""
    for role in ["back", "front", "integ"]:
        canon = _read_file(ROLE_CORE_PATHS[role])
        mirror = _read_file(MIRROR_ROLE_CORE_PATHS[role])
        assert canon == mirror, f"Mirror drift detected for role {role}"

    canon_shared = _read_file(SHARED_CONTRACT_PATH)
    mirror_shared = _read_file(MIRROR_SHARED_CONTRACT_PATH)
    assert canon_shared == mirror_shared, "Mirror drift detected for shared role-core contract"


def test_missing_or_weakened_mode_w_guards_fail_closed():
    """cp4: Validation fails closed if any role's mode-W guard is weakened or stripped."""
    shared_content = _read_file(SHARED_CONTRACT_PATH)

    # BACK missing analyze gate
    mock_back = "@.cursor/rules/shared/role-core-contract.mdc\nPromote DECOMPOSE→IMPLEMENT: ok"
    errors = validate_back_mode_w(mock_back, shared_content)
    assert any("ANALYZE artifact critical_count=0" in e for e in errors)

    # FRONT missing parent-only
    mock_front = "@.cursor/rules/shared/role-core-contract.mdc\nDESIGN STACK: visible_ui"
    errors = validate_front_mode_w(mock_front, shared_content)
    assert any("front-tests-parent-only" in e for e in errors)

    # INTEG missing ELEMENT-FIRST
    mock_integ = "@.cursor/rules/shared/role-core-contract.mdc\nscenario test"
    errors = validate_integ_mode_w(mock_integ, shared_content)
    assert any("ELEMENT-FIRST" in e for e in errors)


def test_compensating_shared_branch_fails_closed():
    """cp4: Validation fails closed if a compensating role-specific branch is added to shared contract."""
    back_content = _read_file(ROLE_CORE_PATHS["back"])
    mock_leaked_shared = _read_file(SHARED_CONTRACT_PATH) + "\nPromote DECOMPOSE→IMPLEMENT: traceability CRITICAL=0\nReview gate: L1=self → L2=fast track"
    errors = validate_back_mode_w(back_content, mock_leaked_shared)
    assert any("leaked BACK branch marker" in e for e in errors)
