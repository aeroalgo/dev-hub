from __future__ import annotations

from loop.dag import adapt_manifest, validate_manifest


def _valid_manifest() -> dict:
    return {
        "schema": "loop-dag/v2",
        "pipeline": {"id": "portal"},
        "source": {
            "kind": "integration_gap",
            "artifacts": ["memory-bank/integration/gap/portal/gap-portal.yaml"],
        },
        "execution": {"autonomous": True},
        "nodes": [
            {
                "id": "back",
                "role": "BACK",
                "decompose": "memory-bank/back/plan/decompose-demo/index.md",
                "depends_on": [],
                "completion": {"type": "decompose"},
                "action": "implement",
            },
            {
                "id": "front",
                "role": "FRONT",
                "decompose": "memory-bank/front/plan/decompose-demo-front/index.md",
                "depends_on": [],
                "completion": {"type": "decompose"},
                "action": "implement",
            },
            {
                "id": "close",
                "role": "INTEG",
                "artifact": "memory-bank/integration/gap/portal/gap-portal.yaml",
                "depends_on": ["back", "front"],
                "completion": {"type": "artifact"},
                "action": "close",
            },
        ],
    }


def test_validate_manifest_accepts_structured_v2_contract() -> None:
    result = validate_manifest(_valid_manifest())

    assert result["ok"] is True
    assert result["manifest"]["pipeline"]["id"] == "portal"
    assert result["diagnostics"] == []


def test_validate_manifest_reports_typed_topology_and_source_errors() -> None:
    manifest = _valid_manifest()
    manifest["source"] = {"kind": "unknown", "artifacts": ["/tmp/gap.yaml"]}
    manifest["nodes"][1]["role"] = "OPS"
    manifest["nodes"][2]["depends_on"] = ["missing", "close"]
    manifest["nodes"][2]["decompose"] = "../escape/index.md"

    result = validate_manifest(manifest)
    codes = {item["code"] for item in result["diagnostics"]}

    assert result["ok"] is False
    assert {"source_invalid", "role_unknown", "missing_dependency", "path_invalid", "cycle"} <= codes


def test_validate_manifest_rejects_duplicate_ids_and_self_edges() -> None:
    manifest = _valid_manifest()
    manifest["nodes"][1]["id"] = "back"
    manifest["nodes"][0]["depends_on"] = ["back"]

    result = validate_manifest(manifest)
    codes = {item["code"] for item in result["diagnostics"]}

    assert result["ok"] is False
    assert "duplicate_node" in codes
    assert "cycle" in codes


def _load_integ_demo() -> dict:
    import yaml
    from pathlib import Path

    path = Path(__file__).parent.parent.parent / "loop" / "dag" / "integ-demo.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_dag_manifest_validates() -> None:
    data = _load_integ_demo()
    result = validate_manifest(data)
    assert result["ok"] is True
    assert result["diagnostics"] == []


def test_dag_manifest_no_cycles() -> None:
    data = _load_integ_demo()
    result = validate_manifest(data)
    codes = [d["code"] for d in result["diagnostics"]]
    assert "cycle" not in codes


def test_dag_manifest_no_dup_ids() -> None:
    data = _load_integ_demo()
    ids = [n["id"] for n in data["nodes"]]
    assert len(ids) == len(set(ids))


def test_legacy_manifest_is_read_only_and_not_autonomous() -> None:
    legacy = {
        "schema": "loop-dag/v1",
        "pipeline_id": "portal",
        "nodes": [
            {
                "id": "back",
                "role_dir": "back",
                "decompose": "memory-bank/back/plan/decompose-demo/index.md",
                "depends_on": [],
            }
        ],
    }

    result = adapt_manifest(legacy)

    assert result["ok"] is True
    assert result["autonomous"] is False
    assert result["manifest"]["schema"] == "loop-dag/v2"
    assert any(item["code"] == "legacy_gap_inference" for item in result["diagnostics"])
