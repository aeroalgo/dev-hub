"""Tests for mb_load session loader (TM-001, TM-002)."""

import pytest
from pathlib import Path
from loop.mb_load import load_session, MbLoadRequest, MbLoadResult
from loop.mb_finish.schemas import LoopHandoffMeta


def test_missing_required_path_ok_is_false_and_diagnostic(tmp_path: Path):
    """TM-001 / US-002: missing required load_now path -> ok is False + missing_file in diagnostics."""
    act_content = """---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: T-HUB-072
step_id: s01
---

## load_now
1. [missing.yaml](memory-bank/back/plan/missing.yaml) — missing.

## Handoff BACK IMPLEMENT — s01
- **Эпик:** T-HUB-072
"""
    (tmp_path / "memory-bank").mkdir(parents=True, exist_ok=True)
    (tmp_path / "memory-bank" / "activeContext.md").write_text(act_content, encoding="utf-8")

    res = load_session(cwd=tmp_path)
    assert res.ok is False
    assert res.status == "incomplete"
    assert "missing.yaml" in str(res.required_missing)
    assert any("missing_file:" in d for d in res.diagnostic_codes)

    """TM-001: request/result schemas match canonical names."""
    req = MbLoadRequest()
    res = MbLoadResult(ok=True)
    assert req.schema == "mb-load-request/v1"
    assert res.schema == "mb-load-result/v1"
    # Ensure LoopHandoffMeta imported without duplicate definitions
    assert LoopHandoffMeta is not None


def test_load_session_happy(tmp_path: Path):
    """TM-001: happy path load_session prepares primary SoT files with fingerprint."""
    act_content = """---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: T-HUB-045-harness-workflow-session-load-api
---

## load_now
1. [s01.yaml](memory-bank/back/plan/s01.yaml) — work shard.
2. [index.yaml](memory-bank/back/plan/index.yaml) — queue.

## Handoff BACK IMPLEMENT — s01
- **Эпик:** T-HUB-045
"""
    mb_dir = tmp_path / "memory-bank" / "back" / "plan"
    mb_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "memory-bank" / "activeContext.md").write_text(act_content, encoding="utf-8")
    (mb_dir / "s01.yaml").write_text("step: s01", encoding="utf-8")
    (mb_dir / "index.yaml").write_text("index: data", encoding="utf-8")

    res = load_session(cwd=tmp_path)
    assert res.ok is True
    assert res.fingerprint is not None
    loaded_paths = [f.path for f in res.files]
    assert "memory-bank/back/plan/s01.yaml" in loaded_paths
    assert "memory-bank/back/plan/index.yaml" in loaded_paths
    assert res.meta is not None
    assert res.meta.role == "BACK"


def test_load_session_invalid_shape(tmp_path: Path):
    """TM-002: invalid activeContext shape produces fail-closed response."""
    act_content = "Invalid content without load_now or handoff"
    mb_dir = tmp_path / "memory-bank"
    mb_dir.mkdir()
    (mb_dir / "activeContext.md").write_text(act_content, encoding="utf-8")

    res = load_session(cwd=tmp_path)
    assert res.ok is False
    assert len(res.diagnostic_codes) > 0


def test_load_session_forbidden_path(tmp_path: Path):
    """TM-002: forbidden path is skipped and tracked in forbidden_skipped."""
    act_content = """---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: T-HUB-045
---

## load_now
1. [s01.yaml](memory-bank/back/plan/s01.yaml) — work shard.
2. [memory-bank/back/plan/plan-T-HUB-045.md](memory-bank/back/plan/plan-T-HUB-045.md) — plan file.

## Handoff BACK IMPLEMENT — s01
- **Эпик:** T-HUB-045
"""
    mb_dir = tmp_path / "memory-bank" / "back" / "plan"
    mb_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "memory-bank" / "activeContext.md").write_text(act_content, encoding="utf-8")
    (mb_dir / "s01.yaml").write_text("step: s01", encoding="utf-8")

    res = load_session(cwd=tmp_path)
    assert res.ok is True
    loaded_paths = [f.path for f in res.files]
    assert "memory-bank/back/plan/s01.yaml" in loaded_paths
    assert "memory-bank/back/plan/plan-T-HUB-045.md" not in loaded_paths
    assert "memory-bank/back/plan/plan-T-HUB-045.md" in res.forbidden_skipped


def test_load_session_missing_file(tmp_path: Path):
    """TM-002: missing shard emits missing_file diagnostic code and derives ok=False."""
    act_content = """---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: T-HUB-045
---

## load_now
1. [missing.yaml](memory-bank/back/plan/missing.yaml) — missing file.

## Handoff BACK IMPLEMENT — s01
- **Эпик:** T-HUB-045
"""
    mb_dir = tmp_path / "memory-bank"
    mb_dir.mkdir()
    (mb_dir / "activeContext.md").write_text(act_content, encoding="utf-8")

    res = load_session(cwd=tmp_path)
    assert res.ok is False
    assert res.status == "incomplete"
    assert "memory-bank/back/plan/missing.yaml" in res.required_missing
    assert any("missing_file:" in code for code in res.diagnostic_codes)



def test_fingerprint_stable(tmp_path: Path):
    act_content = """---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: T-HUB-045
---

## load_now
1. [s01.yaml](memory-bank/back/plan/s01.yaml) — shard.

## Handoff BACK IMPLEMENT — s01
- **Эпик:** T-HUB-045
"""
    mb_dir = tmp_path / "memory-bank" / "back" / "plan"
    mb_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "memory-bank" / "activeContext.md").write_text(act_content, encoding="utf-8")
    (mb_dir / "s01.yaml").write_text("step: s01", encoding="utf-8")

    res1 = load_session(cwd=tmp_path)
    res2 = load_session(cwd=tmp_path)
    assert res1.fingerprint == res2.fingerprint


def test_prepare_primary_mb_load_fail_closed_on_invalid_shape(tmp_path: Path):
    from loop.context_loop import prepare_session
    mb_dir = tmp_path / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)
    # Shape broken (missing frontmatter / malformed) -> degraded recovery
    (mb_dir / "activeContext.md").write_text("invalid shape text without headers", encoding="utf-8")

    out = prepare_session(tmp_path)
    assert out.get("ok") is True
    assert out.get("degraded") is True
    assert "shape_errors" in out or "diagnostic_codes" in out
    assert len(out.get("diagnostic_codes", [])) > 0 or len(out.get("shape_errors", [])) > 0


def test_tm_001_load_ok(tmp_path: Path):
    act_content = """---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: T-HUB-057
step_id: s02
---

## load_now
1. [s02.yaml](memory-bank/back/plan/s02.yaml) — work shard.

## Handoff BACK IMPLEMENT — s02
- **Эпик:** T-HUB-057
"""
    mb_dir = tmp_path / "memory-bank" / "back" / "plan"
    mb_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "memory-bank" / "activeContext.md").write_text(act_content, encoding="utf-8")
    (mb_dir / "s02.yaml").write_text("schema: epic-decompose/v1\nstep_id: s02", encoding="utf-8")

    res = load_session(cwd=tmp_path)
    assert res.ok is True
    assert len(res.files) >= 1
    assert any(f.path == "memory-bank/back/plan/s02.yaml" for f in res.files)


def test_tm_002_missing_shard_diagnostic(tmp_path: Path):
    act_content = """---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: T-HUB-057
step_id: s02
---

## load_now
1. [missing-s02.yaml](memory-bank/back/plan/missing-s02.yaml) — work shard.

## Handoff BACK IMPLEMENT — s02
- **Эпик:** T-HUB-057
"""
    mb_dir = tmp_path / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)
    (mb_dir / "activeContext.md").write_text(act_content, encoding="utf-8")

    res = load_session(cwd=tmp_path)
    assert res.ok is False
    assert res.status == "incomplete"
    assert "memory-bank/back/plan/missing-s02.yaml" in res.required_missing
    assert any("missing_file:" in code for code in res.diagnostic_codes)


def test_mb_load_software_regression(tmp_path: Path):
    """CP1: mb_load для software pack -> загружает memory-bank/activeContext.md (regression)."""
    act_content = """---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: T-HUB-050
step_id: s04
---

## load_now
1. [s04.yaml](memory-bank/back/plan/s04.yaml) — work shard.

## Handoff BACK IMPLEMENT — s04
- **Эпик:** T-HUB-050
"""
    mb_dir = tmp_path / "memory-bank" / "back" / "plan"
    mb_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "memory-bank" / "activeContext.md").write_text(act_content, encoding="utf-8")
    (mb_dir / "s04.yaml").write_text("schema: epic-decompose/v1\nstep_id: s04\n", encoding="utf-8")

    res = load_session(cwd=tmp_path)
    assert res.ok is True
    assert res.meta is not None
    assert res.meta.epic_id == "T-HUB-050"
    assert any(f.path == "memory-bank/back/plan/s04.yaml" for f in res.files)


def test_mb_load_video_pack(tmp_path: Path):
    """CP2: mb_load для video pack -> загружает memory-bank/video/activeContext.md."""
    # Configure project.yaml for video pack
    (tmp_path / "project.yaml").write_text("workflow_pack: dev-hub-video\n", encoding="utf-8")

    # Mock or register video pack
    from loop.workflow.schemas import WorkflowPack
    from unittest.mock import patch
    video_pack = WorkflowPack(
        id="dev-hub-video",
        roles=["video", "audio"],
        command_prefixes=["VIDEO", "AUDIO"],
        phase_registry="loop/schemas/phase_registry.yaml",
        memory_bank="memory-bank/video",
        rules_root=".cursor/rules",
        artifact_layout="production-epic-v1",
    )

    act_content = """---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: V-001
step_id: s01
---

## load_now
1. [s01.yaml](memory-bank/video/script/s01.yaml) — script shard.

## Handoff BACK IMPLEMENT — s01
- **Эпик:** V-001
"""
    video_mb = tmp_path / "memory-bank" / "video" / "script"
    video_mb.mkdir(parents=True, exist_ok=True)
    (tmp_path / "memory-bank" / "video" / "activeContext.md").write_text(act_content, encoding="utf-8")
    (video_mb / "s01.yaml").write_text("schema: epic-decompose/v1\nstep_id: s01\n", encoding="utf-8")

    with patch("loop.workflow.registry.get_pack", return_value=video_pack):
        res = load_session(cwd=tmp_path)
        assert res.ok is True
        assert res.meta is not None
        assert res.meta.role == "BACK"
        assert res.meta.epic_id == "V-001"
        assert any(f.path == "memory-bank/video/script/s01.yaml" for f in res.files)


def test_mb_load_and_policy(tmp_path: Path):
    """CP3: forbidden policy check через policy_for_layout (не hardcoded list)."""
    act_content = """---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: T-HUB-050
step_id: s04
---

## load_now
1. [plan-T-HUB-050.md](memory-bank/back/plan/plan-T-HUB-050.md) — full plan (forbidden in IMPLEMENT).
2. [s04.yaml](memory-bank/back/plan/s04.yaml) — work shard.

## Handoff BACK IMPLEMENT — s04
- **Эпик:** T-HUB-050
"""
    mb_dir = tmp_path / "memory-bank" / "back" / "plan"
    mb_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "memory-bank" / "activeContext.md").write_text(act_content, encoding="utf-8")
    (mb_dir / "plan-T-HUB-050.md").write_text("# Plan T-HUB-050\n", encoding="utf-8")
    (mb_dir / "s04.yaml").write_text("schema: epic-decompose/v1\nstep_id: s04\n", encoding="utf-8")

    res = load_session(cwd=tmp_path)
    assert res.ok is True
    assert "memory-bank/back/plan/plan-T-HUB-050.md" in res.forbidden_skipped
    assert not any(f.path == "memory-bank/back/plan/plan-T-HUB-050.md" for f in res.files)
    assert any(f.path == "memory-bank/back/plan/s04.yaml" for f in res.files)


def test_required_missing_ok_false(tmp_path: Path):
    """CP1 / US-004 / FR-006 / QA TM-004: required missing -> ok is False, required_missing set."""
    act_content = """---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: T-HUB-067
step_id: s02
---

## load_now
1. [s02.yaml](memory-bank/back/plan/s02.yaml) — work shard.
2. [missing_shard.yaml](memory-bank/back/plan/missing_shard.yaml) — required missing shard.

## Handoff BACK IMPLEMENT — s02
- **Эпик:** T-HUB-067
"""
    mb_dir = tmp_path / "memory-bank" / "back" / "plan"
    mb_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "memory-bank" / "activeContext.md").write_text(act_content, encoding="utf-8")
    (mb_dir / "s02.yaml").write_text("schema: epic-decompose/v1\nstep_id: s02\n", encoding="utf-8")

    res = load_session(cwd=tmp_path)
    assert res.ok is False
    assert res.status == "incomplete"
    assert "memory-bank/back/plan/missing_shard.yaml" in res.required_missing
    assert any("missing_file:memory-bank/back/plan/missing_shard.yaml" in code for code in res.diagnostic_codes)
    # The present required file is still loaded
    assert any(f.path == "memory-bank/back/plan/s02.yaml" for f in res.files)


def test_read_error_on_required_ok_false(tmp_path: Path):
    """CP1 / FR-006: read error on required file -> ok is False."""
    from unittest.mock import patch
    act_content = """---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: T-HUB-067
step_id: s02
---

## load_now
1. [s02.yaml](memory-bank/back/plan/s02.yaml) — work shard.

## Handoff BACK IMPLEMENT — s02
- **Эпик:** T-HUB-067
"""
    mb_dir = tmp_path / "memory-bank" / "back" / "plan"
    mb_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "memory-bank" / "activeContext.md").write_text(act_content, encoding="utf-8")
    (mb_dir / "s02.yaml").write_text("schema: epic-decompose/v1\nstep_id: s02\n", encoding="utf-8")

    with patch.object(Path, "read_bytes", side_effect=PermissionError("read denied")):
        res = load_session(cwd=tmp_path)
        assert res.ok is False
        assert res.status == "incomplete"
        assert any("read_error:" in code for code in res.diagnostic_codes)


def test_optional_missing_ok_true_field(tmp_path: Path):
    """CP2 / FR-007 / SC-005 / QA TM-006 / AC+4: optional miss -> ok true + optional_missing populated."""
    act_content = """---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: T-HUB-067
step_id: s02
---

## load_now
1. [s02.yaml](memory-bank/back/plan/s02.yaml) — required shard.
2. [notes.md](memory-bank/back/plan/notes.md) (optional) — optional notes.

## Handoff BACK IMPLEMENT — s02
- **Эпик:** T-HUB-067
"""
    mb_dir = tmp_path / "memory-bank" / "back" / "plan"
    mb_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "memory-bank" / "activeContext.md").write_text(act_content, encoding="utf-8")
    (mb_dir / "s02.yaml").write_text("schema: epic-decompose/v1\nstep_id: s02\n", encoding="utf-8")

    res = load_session(cwd=tmp_path)
    assert res.ok is True
    assert res.status == "complete"
    assert "memory-bank/back/plan/notes.md" in res.optional_missing
    assert len(res.required_missing) == 0
    assert any("missing_file:memory-bank/back/plan/notes.md" in code for code in res.diagnostic_codes)


def test_unmarked_entry_required_fail_closed(tmp_path: Path):
    """CP2 / FR-007 / FR-011e: unmarked entry is required by default (fail-closed)."""
    act_content = """---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: T-HUB-067
step_id: s02
---

## load_now
1. [s02.yaml](memory-bank/back/plan/s02.yaml) — shard without optional tag.
2. [unmarked_missing.yaml](memory-bank/back/plan/unmarked_missing.yaml) — unmarked missing.

## Handoff BACK IMPLEMENT — s02
- **Эпик:** T-HUB-067
"""
    mb_dir = tmp_path / "memory-bank" / "back" / "plan"
    mb_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "memory-bank" / "activeContext.md").write_text(act_content, encoding="utf-8")
    (mb_dir / "s02.yaml").write_text("schema: epic-decompose/v1\nstep_id: s02\n", encoding="utf-8")

    res = load_session(cwd=tmp_path)
    assert res.ok is False
    assert res.status == "incomplete"
    assert "memory-bank/back/plan/unmarked_missing.yaml" in res.required_missing
    assert "memory-bank/back/plan/unmarked_missing.yaml" not in res.optional_missing


def test_result_status_incomplete_on_required_miss(tmp_path: Path):
    """CP3 / FR-008: Result schema fields required_missing, optional_missing, status."""
    act_content = """---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: T-HUB-067
step_id: s02
---

## load_now
1. [missing.yaml](memory-bank/back/plan/missing.yaml) — missing.

## Handoff BACK IMPLEMENT — s02
- **Эпик:** T-HUB-067
"""
    mb_dir = tmp_path / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)
    (mb_dir / "activeContext.md").write_text(act_content, encoding="utf-8")

    res = load_session(cwd=tmp_path)
    assert hasattr(res, "required_missing")
    assert hasattr(res, "optional_missing")
    assert hasattr(res, "forbidden_skipped")
    assert hasattr(res, "fingerprint")
    assert hasattr(res, "status")
    assert res.status == "incomplete"
    assert res.ok is False


def test_mcp_wrapper_cannot_ok_partial_required(tmp_path: Path):
    """CP4 / US-004 / AC-1 / Kind C: MCP wrapper cannot override ok to True when required is missing."""
    from loop.mb_load.mcp_server import load_session as mcp_load_session

    act_content = """---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: T-HUB-067
step_id: s02
---

## load_now
1. [s02.yaml](memory-bank/back/plan/s02.yaml) — present shard.
2. [missing_required.yaml](memory-bank/back/plan/missing_required.yaml) — missing required.

## Handoff BACK IMPLEMENT — s02
- **Эпик:** T-HUB-067
"""
    mb_dir = tmp_path / "memory-bank" / "back" / "plan"
    mb_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "memory-bank" / "activeContext.md").write_text(act_content, encoding="utf-8")
    (mb_dir / "s02.yaml").write_text("schema: epic-decompose/v1\nstep_id: s02\n", encoding="utf-8")

    mcp_res = mcp_load_session(cwd=str(tmp_path))
    assert mcp_res["ok"] is False
    assert mcp_res["status"] == "incomplete"
    assert "memory-bank/back/plan/missing_required.yaml" in mcp_res["required_missing"]
    assert len(mcp_res["files"]) == 1


def test_path_only_classifier_and_load_session_plan_md(tmp_path: Path):
    """FR-002, FR-003, US-001, US-004: plan markdown paths have empty content, full sha256/size, path_only diagnostic."""
    from loop.mb_load.session import is_markdown_plan_path
    import hashlib

    # Unit checks on is_markdown_plan_path
    assert is_markdown_plan_path("memory-bank/back/plan/T-HUB-072/md/plan.md") is True
    assert is_markdown_plan_path("md/plan.md") is True
    assert is_markdown_plan_path("memory-bank/back/plan/plan-T-HUB-072.md") is True
    assert is_markdown_plan_path("memory-bank/back/plan/gap-01.md") is True
    assert is_markdown_plan_path("memory-bank/back/plan/decompose-index.md") is True
    assert is_markdown_plan_path("memory-bank/back/analyze/analyze-01.md") is True
    assert is_markdown_plan_path("memory-bank/back/plan/s01.yaml") is False
    assert is_markdown_plan_path("memory-bank/back/plan/state.json") is False

    # Integration via load_session with role/mode where plan.md is allowed (e.g. DECOMPOSE)
    plan_body = "# Mega Plan Document\n" + ("line content\n" * 100)
    full_sha = hashlib.sha256(plan_body.encode("utf-8")).hexdigest()
    full_size = len(plan_body.encode("utf-8"))

    act_content = """---
schema: loop-handoff/v1
role: BACK
mode: DECOMPOSE
epic_id: T-HUB-072
---

## load_now
1. [plan.md](memory-bank/back/plan/T-HUB-072/md/plan.md) — plan doc.
2. [decompose-index.md](memory-bank/back/plan/T-HUB-072/md/decompose-index.md) — decompose index.

## Handoff BACK DECOMPOSE — s01
- **Эпик:** T-HUB-072
"""
    plan_dir = tmp_path / "memory-bank" / "back" / "plan" / "T-HUB-072" / "md"
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "plan.md").write_text(plan_body, encoding="utf-8")
    (plan_dir / "decompose-index.md").write_text("# Decompose index\n", encoding="utf-8")
    (tmp_path / "memory-bank" / "activeContext.md").write_text(act_content, encoding="utf-8")

    res = load_session(cwd=tmp_path)
    assert res.ok is True
    assert len(res.files) == 2

    plan_file = next(f for f in res.files if f.path == "memory-bank/back/plan/T-HUB-072/md/plan.md")
    assert plan_file.content == ""
    assert plan_file.sha256 == full_sha
    assert plan_file.size_bytes == full_size
    assert plan_file.truncated is False

    idx_file = next(f for f in res.files if f.path == "memory-bank/back/plan/T-HUB-072/md/decompose-index.md")
    assert idx_file.content == ""
    assert idx_file.truncated is False

    assert "path_only:memory-bank/back/plan/T-HUB-072/md/plan.md" in res.diagnostic_codes
    assert "path_only:memory-bank/back/plan/T-HUB-072/md/decompose-index.md" in res.diagnostic_codes


def test_yaml_truncated_keeps_ok_true(tmp_path: Path):
    """FR-006: yaml truncation sets truncated=True but keeps ok=True."""
    yaml_body = "key: " + ("val" * 1000)
    act_content = """---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: T-HUB-072
---

## load_now
1. [big.yaml](memory-bank/back/plan/big.yaml) — big yaml shard.

## Handoff BACK IMPLEMENT — s01
- **Эпик:** T-HUB-072
"""
    mb_dir = tmp_path / "memory-bank" / "back" / "plan"
    mb_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "memory-bank" / "activeContext.md").write_text(act_content, encoding="utf-8")
    (mb_dir / "big.yaml").write_text(yaml_body, encoding="utf-8")

    # Call with small max_file_bytes to trigger truncation
    res = load_session(cwd=tmp_path, max_file_bytes=50)
    assert res.ok is True
    assert len(res.files) == 1
    f = res.files[0]
    assert f.truncated is True
    assert len(f.content.encode("utf-8")) == 50
