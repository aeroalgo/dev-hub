from __future__ import annotations

from pathlib import Path

from loop.context_loop import _cmd_dag_generate
from loop.dag import adapt_manifest


def _write_gap(root: Path, body: str) -> None:
    path = root / "memory-bank/integration/gap/portal/gap-portal.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(body, encoding="utf-8")


def test_generate_valid_gap_emits_back_front_and_close_nodes(tmp_path: Path) -> None:
    _write_gap(
        tmp_path,
        "back:\n"
        "  decompose: memory-bank/back/plan/decompose-demo/index.md\n"
        "front:\n"
        "  decompose: memory-bank/front/plan/decompose-demo-front/index.md\n",
    )

    result = _cmd_dag_generate(tmp_path, "portal")
    manifest = (tmp_path / result["path"]).read_text(encoding="utf-8")

    assert result["ok"] is True
    assert "loop-dag/v2" in manifest
    assert "gap-portal-back" in manifest
    assert "gap-portal-front" in manifest
    assert "gap-portal-close" in manifest
    assert "legacy_gap_inference" not in manifest


def test_generate_rejects_unsafe_structured_gap_source(tmp_path: Path) -> None:
    _write_gap(
        tmp_path,
        "back:\n"
        "  decompose: ../escape/index.md\n"
        "front:\n"
        "  decompose: memory-bank/front/plan/decompose-demo-front/index.md\n",
    )

    result = _cmd_dag_generate(tmp_path, "portal")

    assert result["ok"] is False
    assert any(item["code"] == "path_invalid" for item in result["diagnostics"])
    assert not (tmp_path / "loop/dag/portal.yaml").exists()


def test_legacy_links_are_compatible_but_cannot_arm_autonomous_fanout() -> None:
    result = adapt_manifest(
        {
            "schema": "loop-dag/v1",
            "pipeline_id": "portal",
            "nodes": [
                {
                    "id": "back",
                    "role_dir": "back",
                    "decompose": "memory-bank/back/plan/decompose-demo/index.md",
                    "depends_on": [],
                },
                {
                    "id": "front",
                    "role_dir": "front",
                    "decompose": "memory-bank/front/plan/decompose-demo-front/index.md",
                    "depends_on": [],
                },
            ],
        }
    )

    assert result["ok"] is True
    assert result["autonomous"] is False
    assert any(item["code"] == "legacy_gap_inference" for item in result["diagnostics"])
