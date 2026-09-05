"""Tests for mb_load session loader (TM-001, TM-002)."""

import pytest
from pathlib import Path
from loop.mb_load import load_session, MbLoadRequest, MbLoadResult
from loop.mb_finish.schemas import LoopHandoffMeta


def test_schemas_contract():
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
    """TM-002: missing shard emits missing_file diagnostic code."""
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
    assert res.ok is True
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


