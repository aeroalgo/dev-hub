from pathlib import Path
import pytest

from loop.kernel.roadmap import prepare_advance_after_context_sync
from loop.kernel.index import plan_path


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_roadmap_security_plan_discovery_and_advance(tmp_path: Path) -> None:
    # Current epic E1 (feature) QA pass + context-sync artifact (roadmap advance)
    write(tmp_path / "memory-bank/back/qa/E1/qa-20261024-pass.yaml", "schema: epic-qa/v1\nverdict: pass\n")
    write(tmp_path / "memory-bank/back/context-sync/E1/sync-20261024-e1.md", "# Context sync\n")

    # Next epic SEC1 (security) with plan under memory-bank/back/security/plan/SEC1/md/plan.md
    sec_plan = tmp_path / "memory-bank/back/security/plan/SEC1/md/plan.md"
    write(sec_plan, "# Security Plan SEC1\n")

    write(
        tmp_path / "memory-bank/back/roadmap/queue.yaml",
        """version: roadmap-queue/v2
role: back
queue:
- id: T-E1
  epic_id: E1
  kind: feature
  plan: plan-E1.md
- id: T-SEC1
  epic_id: SEC1
  kind: security
  plan: plan-SEC1.md
done: []
batches: {}
""",
    )

    advance = prepare_advance_after_context_sync(tmp_path, role="back", epic_id="E1")
    assert advance.marked is True
    assert advance.complete is False
    assert advance.next_epic_id == "SEC1"
    assert advance.next_kind == "security"

    # Verify plan_path with kind="security" resolves to the expected path
    resolved_path = plan_path(tmp_path, "back", "SEC1", kind=advance.next_kind)
    assert resolved_path == sec_plan
    assert resolved_path.is_file()


def test_roadmap_security_plan_missing_raises_error(tmp_path: Path) -> None:
    write(tmp_path / "memory-bank/back/qa/E1/qa-20261024-pass.yaml", "schema: epic-qa/v1\nverdict: pass\n")
    write(tmp_path / "memory-bank/back/context-sync/E1/sync-20261024-e1.md", "# Context sync\n")

    write(
        tmp_path / "memory-bank/back/roadmap/queue.yaml",
        """version: roadmap-queue/v2
role: back
queue:
- id: T-E1
  epic_id: E1
  kind: feature
  plan: plan-E1.md
- id: T-SEC1
  epic_id: SEC1
  kind: security
  plan: plan-SEC1.md
done: []
batches: {}
""",
    )

    with pytest.raises(ValueError, match="next_epic_plan_missing: memory-bank/back/security/plan/SEC1/md/plan.md"):
        prepare_advance_after_context_sync(tmp_path, role="back", epic_id="E1")
