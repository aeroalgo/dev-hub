"""Integration smoke & regression tests for workflow pack paths (s08).

Verifies TM-001 (video pack e2e integration smoke) and NFR-001 (software pack regression parity):
mb_load -> resolve_mb_root -> validate_active_context_shape -> mb_finish -> activeContext written.
"""

from pathlib import Path
from unittest.mock import patch
import pytest

from loop.incidents.doctor import validate_active_context_shape
from loop.mb_finish.impl import finish_handoff
from loop.mb_finish.schemas import HandoffBody, LoadNowItem, LoopHandoffMeta
from loop.mb_load import load_session
from loop.paths.epic_paths import resolve_epic_path
from loop.paths.forbidden_policy import policy_for_layout
from loop.paths.pack_layout import resolve_mb_root
from loop.workflow.schemas import WorkflowPack


PACK_CONFIGS = [
    (
        "software",
        WorkflowPack(
            id="dev-hub-software",
            roles=["back", "front", "integration"],
            command_prefixes=["BACK", "FRONT", "INTEG"],
            phase_registry="loop/schemas/phase_registry.yaml",
            memory_bank="memory-bank",
            rules_root=".cursor/rules",
            artifact_layout="software-epic-v1",
        ),
        "T-HUB-050",
    ),
    (
        "video",
        WorkflowPack(
            id="dev-hub-video",
            roles=["video", "audio"],
            command_prefixes=["VIDEO", "AUDIO"],
            phase_registry="loop/schemas/phase_registry.yaml",
            memory_bank="memory-bank/video",
            rules_root=".cursor/rules",
            artifact_layout="software-epic-v1",
        ),
        "T-VID-001",
    ),
]


@pytest.mark.parametrize("pack_name,pack,epic_id", PACK_CONFIGS)
def test_pack_integration_matrix_e2e(
    tmp_path: Path,
    pack_name: str,
    pack: WorkflowPack,
    epic_id: str,
):
    """TM-001 & NFR-001: Matrix test verifying full lifecycle across workflow packs.

    Lifecycle steps:
    1. resolve_mb_root resolves correct path per pack
    2. Write valid activeContext.md at mb_root
    3. validate_active_context_shape returns valid=True
    4. mb_load loads session successfully with fingerprint and files
    5. policy_for_layout returns policy for pack's artifact_layout
    6. resolve_epic_path resolves correct subpaths
    7. mb_finish updates activeContext in expected pack directory
    """
    # 1. resolve_mb_root dynamically from pack config without hardcoding
    with patch("loop.workflow.registry.get_pack", return_value=pack), \
         patch("loop.paths.pack_layout.resolve_workflow_pack") as mock_resolve:
        from loop.workflow.schemas import PackResolveResult
        mock_resolve.return_value = PackResolveResult(
            ok=True,
            pack_id=pack.id,
            pack=pack,
            diagnostic_codes=[],
        )

        mb_root = resolve_mb_root(cwd=tmp_path, pack=pack)
        mb_root.mkdir(parents=True, exist_ok=True)
        assert mb_root == tmp_path / pack.memory_bank

        # 2. Setup initial activeContext.md using relative path from pack.memory_bank
        step_file_rel = f"{pack.memory_bank}/back/plan/{epic_id}/yaml/steps/s01.yaml"
        step_file_abs = tmp_path / step_file_rel
        step_file_abs.parent.mkdir(parents=True, exist_ok=True)
        step_file_abs.write_text("step_id: s01\n", encoding="utf-8")

        initial_ac = f"""---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: {epic_id}
step_id: s01
---

## load_now
1. [{step_file_rel}]({step_file_rel}) — work shard.

## Handoff BACK IMPLEMENT — s01
- **Эпик:** {epic_id}
"""
        ac_file = mb_root / "activeContext.md"
        ac_file.write_text(initial_ac, encoding="utf-8")

        # 3. validate_active_context_shape
        shape_res = validate_active_context_shape(ac_file)
        assert shape_res.valid is True, f"Shape validation failed: {shape_res.diagnostic}"

        # 4. mb_load
        load_res = load_session(cwd=tmp_path)
        assert load_res.ok is True, f"load_session failed: {load_res.diagnostic_codes}"
        assert load_res.meta is not None
        assert load_res.meta.epic_id == epic_id
        assert load_res.fingerprint is not None
        assert any(f.path == step_file_rel for f in load_res.files)

        # 5. policy_for_layout
        policy = policy_for_layout(pack.artifact_layout)
        plan_file_rel = f"{pack.memory_bank}/back/plan/plan-{epic_id}.md"
        assert policy.is_forbidden(plan_file_rel, mode="IMPLEMENT") is True
        assert policy.is_forbidden(step_file_rel, mode="IMPLEMENT") is False

        # 6. resolve_epic_path
        plan_path = resolve_epic_path("plan", epic_id, pack=pack, cwd=tmp_path)
        assert plan_path == mb_root / "back" / "plan" / epic_id / "md"

        # 7. mb_finish
        meta = LoopHandoffMeta(
            role="BACK",
            mode="IMPLEMENT",
            epic_id=epic_id,
            step_id="s01",
        )
        load_now = [
            LoadNowItem(
                path=step_file_rel,
                description="work shard",
            )
        ]
        body = HandoffBody(
            mode="IMPLEMENT",
            next_hint=f"continue {epic_id} s01",
            epic_id=epic_id,
            step_id="s01",
        )

        finish_res = finish_handoff(meta, load_now, body, cwd=tmp_path)
        assert finish_res.ok is True
        assert ac_file.exists()
        updated_content = ac_file.read_text(encoding="utf-8")
        assert f"continue {epic_id} s01" in updated_content

        # Verify isolation: other packs' resolved roots do not have activeContext created
        other_packs = [p for _, p, _ in PACK_CONFIGS if p.id != pack.id]
        for other_pack in other_packs:
            other_root = resolve_mb_root(cwd=tmp_path, pack=other_pack)
            assert not (other_root / "activeContext.md").exists()
