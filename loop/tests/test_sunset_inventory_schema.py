"""Unit tests for loop-sunset-inventory/v1 Pydantic models."""

import pytest
from pydantic import ValidationError

from loop.schemas.sunset_inventory import (
    SCHEMA_LOOP_SUNSET_INVENTORY,
    SunsetItem,
    SunsetReport,
)


def test_valid_report() -> None:
    data = {
        "schema": SCHEMA_LOOP_SUNSET_INVENTORY,
        "boundary_id": "T-HUB-058",
        "new_sot": "loop/schemas/sunset_inventory.py",
        "forbidden_for_parent": ["how_to_replace", "design_suggestions"],
        "diagnostic_codes": ["SUNSET_001"],
        "ok": True,
        "items": [
            {
                "kind": "A",
                "symbol": "OldClass",
                "path": "loop/old.py",
                "start_line": 10,
                "end_line": 25,
                "excerpt": "class OldClass:\n    pass\n",
                "mark": "REPLACE",
                "role": "legacy parser",
                "notes": "replaced by NewClass",
            },
            {
                "kind": "I",
                "symbol": "import_old",
                "path": "loop/main.py",
                "start_line": 1,
                "end_line": 1,
                "excerpt": "from loop.old import OldClass",
                "mark": "REPLACE",
                "role": "import site",
            },
        ],
    }

    report = SunsetReport.model_validate(data)
    assert report.schema_version == SCHEMA_LOOP_SUNSET_INVENTORY
    assert report.boundary_id == "T-HUB-058"
    assert report.new_sot == "loop/schemas/sunset_inventory.py"
    assert report.ok is True
    assert len(report.items) == 2
    assert report.items[0].kind == "A"
    assert report.items[0].mark == "REPLACE"
    assert report.items[1].kind == "I"
    assert report.items[1].mark == "REPLACE"
    assert report.items[1].notes is None


def test_missing_mark_rejected() -> None:
    # missing mark -> ValidationError
    with pytest.raises(ValidationError):
        SunsetItem.model_validate(
            {
                "kind": "A",
                "symbol": "OldClass",
                "path": "loop/old.py",
                "start_line": 10,
                "end_line": 25,
                "excerpt": "class OldClass:\n    pass\n",
                "role": "legacy parser",
            }
        )

    # invalid mark -> ValidationError
    with pytest.raises(ValidationError):
        SunsetItem.model_validate(
            {
                "kind": "A",
                "symbol": "OldClass",
                "path": "loop/old.py",
                "start_line": 10,
                "end_line": 25,
                "excerpt": "class OldClass:\n    pass\n",
                "mark": "DELETE",  # only REPLACE is permitted
                "role": "legacy parser",
            }
        )


def test_design_fields_rejected() -> None:
    # SunsetItem rejects extra fields (e.g. how_to_replace, recommendation)
    with pytest.raises(ValidationError):
        SunsetItem.model_validate(
            {
                "kind": "A",
                "symbol": "OldClass",
                "path": "loop/old.py",
                "start_line": 10,
                "end_line": 25,
                "excerpt": "class OldClass:\n    pass\n",
                "mark": "REPLACE",
                "role": "legacy parser",
                "how_to_replace": "Use NewClass instead and update calls",
            }
        )

    with pytest.raises(ValidationError):
        SunsetItem.model_validate(
            {
                "kind": "B",
                "symbol": "OldFunc",
                "path": "loop/old.py",
                "start_line": 30,
                "end_line": 40,
                "excerpt": "def OldFunc(): pass",
                "mark": "REPLACE",
                "role": "legacy func",
                "recommendation": "Rewrite using pydantic",
            }
        )

    # SunsetReport also rejects extra fields
    with pytest.raises(ValidationError):
        SunsetReport.model_validate(
            {
                "schema": SCHEMA_LOOP_SUNSET_INVENTORY,
                "boundary_id": "T-HUB-058",
                "new_sot": "loop/schemas/sunset_inventory.py",
                "extra_design_advice": "Do not use old components",
                "items": [],
            }
        )


def test_excerpt_budget_and_truncation() -> None:
    # 40 lines is allowed
    excerpt_40 = "\n".join(f"line {i}" for i in range(40))
    item = SunsetItem(
        kind="A",
        symbol="Sym",
        path="path.py",
        start_line=1,
        end_line=40,
        excerpt=excerpt_40,
        mark="REPLACE",
        role="role",
    )
    assert len(item.excerpt.splitlines()) == 40

    # 41 lines is rejected
    excerpt_41 = "\n".join(f"line {i}" for i in range(41))
    with pytest.raises(ValidationError):
        SunsetItem(
            kind="A",
            symbol="Sym",
            path="path.py",
            start_line=1,
            end_line=41,
            excerpt=excerpt_41,
            mark="REPLACE",
            role="role",
        )
