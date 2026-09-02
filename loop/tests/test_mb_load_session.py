import pytest
from pathlib import Path
from loop.mb_load import load_session, MbLoadRequest, MbLoadResult
from loop.mb_finish.schemas import LoopHandoffMeta


def test_schemas_contract():
    req = MbLoadRequest()
    res = MbLoadResult(ok=True)
    assert req.schema == "mb-load-request/v1"
    assert res.schema == "mb-load-result/v1"
    # Ensure LoopHandoffMeta imported without duplicate definitions
    assert LoopHandoffMeta is not None


def test_load_session_happy(tmp_path: Path):
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
    act_content = "Invalid content without load_now or handoff"
    mb_dir = tmp_path / "memory-bank"
    mb_dir.mkdir()
    (mb_dir / "activeContext.md").write_text(act_content, encoding="utf-8")

    res = load_session(cwd=tmp_path)
    assert res.ok is False
    assert len(res.diagnostic_codes) > 0


def test_load_session_forbidden_path(tmp_path: Path):
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
