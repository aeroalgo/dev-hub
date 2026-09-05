"""Regression coverage for pack API gaps accepted by T-HUB-050 AUDIT."""
from pathlib import Path
import json
import subprocess
import sys


def test_missing_pack_helpers_resolve_paths(tmp_path):
    import loop.paths.pack_layout as layout
    from loop.workflow.schemas import WorkflowPack
    pack = WorkflowPack(id="sample", roles=["script"], command_prefixes=["SCRIPT"], phase_registry="phases.yaml", memory_bank="memory-bank/video", rules_root="rules", artifact_layout="production-epic-v1")
    assert callable(getattr(layout, "resolve_active_context", None))
    assert callable(getattr(layout, "resolve_role_root", None))
    assert layout.resolve_active_context(tmp_path, pack=pack) == tmp_path / "memory-bank/video/activeContext.md"
    assert layout.resolve_role_root(pack, "script", cwd=tmp_path) == tmp_path / "memory-bank/video/script"


def test_mb_finish_cli_reports_pack_metadata(tmp_path):
    proc = subprocess.run([sys.executable, "harness/hooks/epic_resolve.py", "--cwd", str(tmp_path), "mb-finish", "bugfix"], capture_output=True, text=True)
    data = json.loads(proc.stdout)
    assert data["workflow_pack"] == "dev-hub-software"
    assert data["mb_root"] == str(tmp_path / "memory-bank")


def test_load_plan_section_uses_layout_v2_and_named_role(tmp_path):
    from loop.mb_load.plan_section import load_plan_section
    mb = tmp_path / "memory-bank"
    mb.mkdir()
    (mb / "activeContext.md").write_text("---\nschema: loop-handoff/v1\nrole: FRONT\nmode: QA\nepic_id: T-NEW\n---\n## load_now\n## Handoff FRONT QA\n")
    plan = mb / "front/plan/T-NEW/md/plan.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("# Plan\n## QA consumes\ncorrect role and epic\n")
    assert load_plan_section(tmp_path, 1) == ("## QA consumes\ncorrect role and epic", None)
