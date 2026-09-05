"""Tests for roadmap Queue canon + roadmap-advance + degraded DONE prompt."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = str(ROOT / ".claude" / "hooks")
LOOP = str(ROOT / "loop")


def _load_rq():
    if HOOKS not in sys.path:
        sys.path.insert(0, HOOKS)
    if LOOP not in sys.path:
        sys.path.insert(0, LOOP)
    import roadmap_queue

    return importlib.reload(roadmap_queue)


def _load_ctx():
    path = ROOT / "loop" / "context_loop.py"
    spec = importlib.util.spec_from_file_location("context_loop", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    if HOOKS not in sys.path:
        sys.path.insert(0, HOOKS)
    if LOOP not in sys.path:
        sys.path.insert(0, LOOP)
    spec.loader.exec_module(mod)
    return mod


def _write(cwd: Path, rel: str, body: str) -> None:
    p = cwd / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def _roadmap_md() -> str:
    return (
        "# Roadmap\n\n"
        "## Queue (loop machine)\n\n"
        "→ [`roadmap-epics.queue.yaml`](roadmap-epics.queue.yaml)\n"
    )


def _write_queue(cwd: Path, queue_yaml: str, *, name: str = "queue") -> None:
    """Write canon queue.yaml or a batches/<name>.yaml source."""
    body = queue_yaml.strip() + "\n"
    if name in {"queue", "roadmap-epics"}:
        _write(cwd, "memory-bank/back/roadmap/queue.yaml", body)
        return
    _write(cwd, f"memory-bank/back/roadmap/batches/{name}.yaml", body)


def _minimal_queue(*ids: str) -> str:
    lines = [
        "version: roadmap-queue/v2",
        "role: back",
        "queue:",
    ]
    for i, epic_id in enumerate(ids):
        deps = f"[{ids[i - 1]}]" if i else "[]"
        lines.append(f"  - id: {epic_id}")
        lines.append(f"    epic_id: {epic_id}")
        lines.append(f"    plan: plan-{epic_id}.md")
        lines.append(f"    deps: {deps}")
    lines.append("done: []")
    return "\n".join(lines)


def _mark_epic_done(cwd: Path, epic_id: str) -> None:
    _write(
        cwd,
        f"memory-bank/back/plan/decompose-{epic_id}/index.yaml",
        "schema: epic-decompose-index/v1\n"
        f"plan_id: {epic_id}\n"
        "steps:\n"
        "- id: s01\n  file: s01.yaml\n  status: completed\n",
    )
    _write(cwd, f"memory-bank/back/plan/decompose-{epic_id}/index.md", f"# {epic_id}\n")
    _write(cwd, f"memory-bank/back/plan/decompose-{epic_id}/s01.yaml", "step_id: s01\n")
    _write(
        cwd,
        f"memory-bank/back/qa/{epic_id}/qa-20260815-pass.yaml",
        "schema: epic-qa/v1\nverdict: pass\nissues: []\n",
    )
    _write(
        cwd,
        f"memory-bank/back/reflection/reflection-{epic_id}.md",
        f"# refl\nepic: {epic_id}\n",
    )
    if HOOKS not in sys.path:
        sys.path.insert(0, HOOKS)
    from epic import reconcile_epic_events

    reconcile_epic_events(cwd, "back", epic_id)


def test_parse_valid_queue_yaml(tmp_path: Path) -> None:
    rq = _load_rq()
    _write_queue(tmp_path, _minimal_queue("T-A", "T-B"))
    out = rq.parse_roadmap_queue(tmp_path)
    assert out["ok"] is True
    assert [x["id"] for x in out["queue"]] == ["T-A", "T-B"]
    assert out["queue"][1]["deps"] == ["T-A"]


def test_parse_missing_queue_fail_closed(tmp_path: Path) -> None:
    rq = _load_rq()
    _write(tmp_path, "memory-bank/back/plan/roadmap-epics.md", "# human only\n")
    out = rq.parse_roadmap_queue(tmp_path)
    assert out["ok"] is False
    assert out["error"] == "queue_yaml_missing"


def test_parse_bad_version_fail_closed(tmp_path: Path) -> None:
    rq = _load_rq()
    bad = _minimal_queue("T-A").replace("roadmap-queue/v2", "roadmap-queue/v0")
    _write_queue(tmp_path, bad)
    out = rq.parse_roadmap_queue(tmp_path)
    assert out["ok"] is False
    assert out["error"] == "queue_version_mismatch"


def test_next_epic_skips_done_respects_hard_deps(tmp_path: Path) -> None:
    rq = _load_rq()
    _write_queue(tmp_path, _minimal_queue("T-A", "T-B", "T-C"))
    for epic in ("T-A", "T-B", "T-C"):
        _write(tmp_path, f"memory-bank/back/plan/plan-{epic}.md", f"# {epic}\n")
    _mark_epic_done(tmp_path, "T-A")
    out = rq.select_next_epic(tmp_path)
    assert out["ok"] is True
    assert out["entry"]["epic"] == "T-B"
    assert out["entry"]["phase"] == "DECOMPOSE"
    assert "T-A" in out["done_ids"]


def test_smart_entry_decompose_when_no_index(tmp_path: Path) -> None:
    rq = _load_rq()
    _write(tmp_path, "memory-bank/back/plan/plan-T-X.md", "# plan\n")
    entry = rq.resolve_entry(
        tmp_path, role="back", epic_id="T-X", plan_name="plan-T-X.md"
    )
    assert entry["ok"] is True
    assert entry["phase"] == "DECOMPOSE"


def test_smart_entry_implement_when_pending(tmp_path: Path) -> None:
    rq = _load_rq()
    _write(tmp_path, "memory-bank/back/plan/plan-T-Y.md", "# plan\n")
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-T-Y/index.yaml",
        "schema: epic-decompose-index/v1\nplan_id: T-Y\nsteps:\n"
        "- id: s01\n  file: s01-one.yaml\n  status: pending\n",
    )
    _write(tmp_path, "memory-bank/back/plan/decompose-T-Y/index.md", "# Y\n")
    _write(
        tmp_path,
        "memory-bank/back/analyze/T-Y/analyze-20260831-pass.yaml",
        "schema: epic-analyze/v1\nmetrics:\n  critical_count: 0\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-T-Y/s01-one.yaml",
        "schema: epic-decompose/v1\nstep_id: s01\n",
    )
    entry = rq.resolve_entry(
        tmp_path, role="back", epic_id="T-Y", plan_name="plan-T-Y.md"
    )
    assert entry["phase"] == "IMPLEMENT"
    assert entry["step_id"] == "s01"


def test_smart_entry_qa_when_all_completed(tmp_path: Path) -> None:
    rq = _load_rq()
    _write(tmp_path, "memory-bank/back/plan/plan-T-Z.md", "# plan\n")
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-T-Z/index.yaml",
        "schema: epic-decompose-index/v1\nplan_id: T-Z\nsteps:\n"
        "- id: s01\n  file: s01.yaml\n  status: completed\n",
    )
    _write(tmp_path, "memory-bank/back/plan/decompose-T-Z/index.md", "# Z\n")
    _write(tmp_path, "memory-bank/back/plan/decompose-T-Z/s01.yaml", "step_id: s01\n")
    entry = rq.resolve_entry(
        tmp_path, role="back", epic_id="T-Z", plan_name="plan-T-Z.md"
    )
    assert entry["phase"] in {"AUDIT", "QA"}


def test_roadmap_advance_arms_implement_via_arm_epic(tmp_path: Path) -> None:
    rq = _load_rq()
    _write_queue(tmp_path, _minimal_queue("T-IMP"))
    _write(tmp_path, "memory-bank/back/plan/plan-T-IMP.md", "# plan\n")
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-T-IMP/index.yaml",
        "schema: epic-decompose-index/v1\nplan_id: T-IMP\nsteps:\n"
        "- id: s01\n  file: s01-one.yaml\n  status: completed\n"
        "- id: s02\n  file: s02-two.yaml\n  status: pending\n",
    )
    _write(tmp_path, "memory-bank/back/plan/decompose-T-IMP/index.md", "# imp\n")
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-T-IMP/s01-one.yaml",
        "schema: epic-decompose/v1\nstep_id: s01\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-T-IMP/s02-two.yaml",
        "schema: epic-decompose/v1\nstep_id: s02\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/analyze/T-IMP/analyze-20260831-pass.yaml",
        "schema: epic-analyze/v1\nmetrics:\n  critical_count: 0\n",
    )
    sel = rq.select_next_epic(tmp_path)
    assert sel["ok"] is True
    assert sel["entry"]["phase"] == "IMPLEMENT"
    out = rq.arm_roadmap_entry(tmp_path, sel)
    assert out["ok"] is True
    assert out["armed"] is True
    assert out["phase"] == "IMPLEMENT"
    assert out["step_id"] == "s02"
    text = (tmp_path / "memory-bank/activeContext.md").read_text(encoding="utf-8")
    assert "s02" in text
    assert "decompose-T-IMP" in text


def test_roadmap_advance_arms_next_after_done(tmp_path: Path) -> None:
    rq = _load_rq()
    _write_queue(tmp_path, _minimal_queue("T-005", "T-013"))
    _write(tmp_path, "memory-bank/back/plan/plan-T-005.md", "# 5\n")
    _write(tmp_path, "memory-bank/back/plan/plan-T-013.md", "# 13\n")
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-T-005-docker-linux-runtime/index.yaml",
        "schema: epic-decompose-index/v1\nplan_id: T-005-docker-linux-runtime\nsteps:\n"
        "- id: s01\n  file: s01.yaml\n  status: completed\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-T-005-docker-linux-runtime/index.md",
        "# T-005\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-T-005-docker-linux-runtime/s01.yaml",
        "step_id: s01\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/qa/T-005-docker-linux-runtime/qa-20260815-pass.yaml",
        "schema: epic-qa/v1\nverdict: pass\nissues: []\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/reflection/reflection-T-005-docker-linux-runtime.md",
        "# done\nepic: T-005-docker-linux-runtime\n",
    )
    if HOOKS not in sys.path:
        sys.path.insert(0, HOOKS)
    from epic import reconcile_epic_events

    reconcile_epic_events(tmp_path, "back", "T-005-docker-linux-runtime")
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n- n/a\n\n## Handoff\nEPIC_DONE\n",
    )
    _write(
        tmp_path,
        ".claude/runtime/epic/state.json",
        '{"armed_epic":"T-005-docker-linux-runtime","status":"complete","active":false}\n',
    )
    out = rq.roadmap_advance(tmp_path, skip_epic="T-005-docker-linux-runtime")
    assert out["ok"] is True
    assert out["armed"] is True
    assert out["phase"] == "DECOMPOSE"
    assert out["epic"] == "T-013"
    text = (tmp_path / "memory-bank/activeContext.md").read_text(encoding="utf-8")
    assert "DECOMPOSE" in text
    assert "T-013" in text
    assert "plan-T-013.md" in text


def test_roadmap_advance_decompose_prepare_ok_without_index(tmp_path: Path) -> None:
    rq = _load_rq()
    ctx = _load_ctx()
    _write_queue(tmp_path, _minimal_queue("T-005", "T-013"))
    _write(tmp_path, "memory-bank/back/plan/plan-T-005.md", "# 5\n")
    _write(tmp_path, "memory-bank/back/plan/plan-T-013.md", "# 13\n")
    _mark_epic_done(tmp_path, "T-005")
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n- n/a\n\n## Handoff\nEPIC_DONE\n",
    )
    _write(
        tmp_path,
        ".claude/runtime/epic/state.json",
        '{"armed_epic":"T-005","status":"complete","active":false}\n',
    )
    advance = rq.roadmap_advance(tmp_path, skip_epic="T-005")
    assert advance["ok"] is True
    assert advance["phase"] == "DECOMPOSE"
    assert advance["epic"] == "T-013"
    prep = ctx.prepare_session(tmp_path)
    assert prep.get("ok") is True, prep
    assert prep.get("halt") is not True
    st_path = tmp_path / ".claude/runtime/epic/state.json"
    st = json.loads(st_path.read_text(encoding="utf-8"))
    assert st.get("armed_step") == "DECOMPOSE"
    assert st.get("armed_decompose") in (None, "")


def test_epic_chain_flag_default_off(tmp_path: Path, monkeypatch) -> None:
    rq = _load_rq()
    monkeypatch.setenv("EPIC_CHAIN_ROADMAP", "0")
    _write(tmp_path, ".claude/project.env", "EPIC_CHAIN_ROADMAP=0\n")
    assert rq.epic_chain_roadmap_enabled(tmp_path) is False
    monkeypatch.setenv("EPIC_CHAIN_ROADMAP", "1")
    assert rq.epic_chain_roadmap_enabled(tmp_path) is True


def test_degraded_prompt_phase_done_no_find_decompose(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n\n## Handoff BACK QA — demo\n- **Статус:** COMPLETED\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-other/index.yaml",
        "schema: epic-decompose-index/v1\nplan_id: other\nsteps:\n"
        "- id: s01\n  file: s01.yaml\n  status: pending\n",
    )
    prompt = ctx.build_prompt(
        tmp_path,
        load_now=[],
        shape_errors=[],
        projection={"phase": "DONE", "epic": "demo", "next_step": None},
    )
    assert "Найди `memory-bank/**/plan/decompose-*/index.yaml`" not in prompt
    assert "epic finished" in prompt


def test_degraded_prompt_truly_done_with_artifacts(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-demo/index.yaml",
        "schema: epic-decompose-index/v1\nplan_id: demo\nsteps:\n"
        "- id: s01\n  file: s01.yaml\n  status: completed\n",
    )
    _write(tmp_path, "memory-bank/back/plan/decompose-demo/index.md", "# demo\n")
    _write(tmp_path, "memory-bank/back/plan/decompose-demo/s01.yaml", "step_id: s01\n")
    _write(
        tmp_path,
        "memory-bank/back/qa/demo/qa-20260815-pass.yaml",
        "schema: epic-qa/v1\nverdict: pass\nissues: []\n",
    )
    _write(tmp_path, "memory-bank/back/reflection/reflection-demo.md", "# refl\nepic: demo\n")
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n- n/a\n\n## Handoff\nEPIC_DONE\n",
    )
    _write(
        tmp_path,
        ".claude/runtime/epic/state.json",
        '{"armed_epic":"demo","armed_decompose":'
        '"memory-bank/back/plan/decompose-demo/index.md","status":"complete"}\n',
    )
    prompt = ctx.build_prompt(
        tmp_path,
        load_now=[],
        shape_errors=[],
        projection={"phase": "DONE", "epic": "demo", "next_step": None},
    )
    assert "Найди `memory-bank/**/plan/decompose-*/index.yaml`" not in prompt
    assert "epic finished" in prompt


def test_context_loop_roadmap_advance_cli(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _write_queue(tmp_path, _minimal_queue("T-N"))
    _write(tmp_path, "memory-bank/back/plan/plan-T-N.md", "# n\n")
    _write(tmp_path, "memory-bank/activeContext.md", "## load_now\n1. x\n\n## Handoff\n")
    rc = ctx.main(["--cwd", str(tmp_path), "roadmap-advance"])
    assert rc == 0
    text = (tmp_path / "memory-bank/activeContext.md").read_text(encoding="utf-8")
    assert "T-N" in text
    assert "DECOMPOSE" in text


def test_roadmap_done_when_all_complete(tmp_path: Path) -> None:
    rq = _load_rq()
    _write_queue(tmp_path, _minimal_queue("T-ONLY"))
    _write(tmp_path, "memory-bank/back/plan/plan-T-ONLY.md", "# only\n")
    _mark_epic_done(tmp_path, "T-ONLY")
    assert rq.is_epic_done(tmp_path, "back", "T-ONLY") is True
    out = rq.roadmap_advance(tmp_path)
    assert out["ok"] is True
    assert out["complete"] is True
    assert out["stop"] == "ROADMAP_DONE"


def test_arm_roadmap_entry_promotes_analyze(tmp_path: Path, monkeypatch) -> None:
    rq = _load_rq()
    called = []
    def dummy_promote(cwd, epic_id, role):
        called.append((str(cwd), epic_id, role))
        return {
            "ok": True,
            "armed_step": "IMPLEMENT",
            "phase": "IMPLEMENT",
            "promoted_from": "ANALYZE",
            "reason": "implement_promote",
        }

    import loop.epic_transition as et
    monkeypatch.setattr(et, "promote_if_ready", dummy_promote)

    selection = {
        "role": "back",
        "entry": {"epic": "T-TEST", "queue_id": "T-TEST", "plan": "plan-T-TEST.md", "phase": "ANALYZE"},
    }
    _write(tmp_path, "memory-bank/back/plan/plan-T-TEST.md", "# test plan\n")
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-T-TEST/index.yaml",
        "schema: epic-decompose-index/v1\nplan_id: T-TEST\nsteps:\n- id: s01\n  file: s01.yaml\n  status: pending\n",
    )
    _write(tmp_path, "memory-bank/back/plan/decompose-T-TEST/index.md", "# test\n")
    _write(tmp_path, "memory-bank/back/plan/decompose-T-TEST/s01.yaml", "step_id: s01\n")

    out = rq.arm_roadmap_entry(tmp_path, selection)
    assert out["ok"] is True
    assert out["armed"] is True
    assert out["phase"] == "IMPLEMENT"
    assert out.get("promoted_from") == "ANALYZE"
    assert len(called) == 1


def test_repo_roadmap_queue_parses() -> None:
    rq = _load_rq()
    out = rq.parse_roadmap_queue(ROOT)
    assert out["ok"] is True
    assert out["path"].endswith("roadmap/queue.yaml")
    assert out["version"] == "roadmap-queue/v2"
    assert len(out["queue"]) >= 1
    assert all(item.get("id") and item.get("plan") for item in out["queue"])


def test_queue_rel_from_roadmap() -> None:
    rq = _load_rq()
    assert (
        rq.queue_rel_from_roadmap("memory-bank/back/plan/roadmap-foo-epics.md")
        == "memory-bank/back/plan/roadmap-foo-epics.queue.yaml"
    )
    assert (
        rq.queue_rel_from_roadmap("memory-bank/back/roadmap")
        == "memory-bank/back/roadmap/queue.yaml"
    )
    assert (
        rq.queue_rel_from_roadmap("memory-bank/back/roadmap/queue.yaml")
        == "memory-bank/back/roadmap/queue.yaml"
    )


def test_build_prompt_phase_done_forbids_archive(tmp_path: Path, monkeypatch) -> None:
    ctx = _load_ctx()
    monkeypatch.setenv("EPIC_CHAIN_ROADMAP", "1")
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n- memory-bank/back/reflection/reflection-demo.md\n\n"
        "## Handoff BACK REFLECT — demo\n- next ARCHIVE\n",
    )
    _write(tmp_path, "memory-bank/back/reflection/reflection-demo.md", "# refl\n")
    prompt = ctx.build_prompt(
        tmp_path,
        load_now=["memory-bank/back/reflection/reflection-demo.md"],
        shape_errors=[],
        projection={"phase": "DONE", "epic": "demo", "next_step": None},
    )
    assert "## DONE FINISH" in prompt
    assert "IMPLEMENT FINISH" not in prompt
    assert "FORBIDDEN" in prompt and "ARCHIVE" in prompt
    assert "EPIC_DONE" in prompt


def test_roadmap_merge_sources_into_canon(tmp_path: Path) -> None:
    rq = _load_rq()
    _write_queue(tmp_path, _minimal_queue("T-A", "T-B"), name="alpha")
    _write(
        tmp_path,
        "memory-bank/back/roadmap/batches/beta.yaml",
        "version: roadmap-queue/v2\n"
        "role: back\n"
        "queue:\n"
        "  - id: T-C\n"
        "    epic_id: T-C\n"
        "    plan: plan-T-C.md\n"
        "    deps: [T-B]\n"
        "done: []\n",
    )
    for plan in ("plan-T-A.md", "plan-T-B.md", "plan-T-C.md"):
        _write(tmp_path, f"memory-bank/back/plan/{plan}", f"# {plan}\n")

    out = rq.roadmap_merge(tmp_path, role="back", write_md=False)
    assert out["ok"] is True
    assert out["ids"] == ["T-A", "T-B", "T-C"]
    assert out["written"] is True
    assert out["md_written"] is False
    parsed = rq.parse_roadmap_queue(tmp_path)
    assert parsed["ok"] is True
    assert [x["id"] for x in parsed["queue"]] == ["T-A", "T-B", "T-C"]
    assert parsed["queue"][2]["deps"] == ["T-B"]
    assert (tmp_path / "memory-bank/back/roadmap/queue.yaml").is_file()
    assert not (tmp_path / "memory-bank/back/roadmap/roadmap-epics.md").is_file()


def test_roadmap_merge_skips_done_and_preserves_canon_order(tmp_path: Path) -> None:
    rq = _load_rq()
    _write_queue(tmp_path, _minimal_queue("T-OLD", "T-NEW"))
    _mark_epic_done(tmp_path, "T-OLD")
    _write(
        tmp_path,
        "memory-bank/back/roadmap/batches/extra.yaml",
        "version: roadmap-queue/v2\n"
        "role: back\n"
        "queue:\n"
        "  - id: T-NEW\n"
        "    epic_id: T-NEW\n"
        "    plan: plan-T-NEW.md\n"
        "    deps: []\n"
        "  - id: T-X\n"
        "    epic_id: T-X\n"
        "    plan: plan-T-X.md\n"
        "    deps: []\n"
        "done: []\n",
    )
    for plan in ("plan-T-OLD.md", "plan-T-NEW.md", "plan-T-X.md"):
        _write(tmp_path, f"memory-bank/back/plan/{plan}", f"# {plan}\n")

    out = rq.roadmap_merge(tmp_path, role="back")
    assert out["ok"] is True
    assert "T-OLD" in out["skipped_done"]
    assert out["ids"] == ["T-NEW", "T-X"]


def test_roadmap_merge_plan_conflict_fail_closed(tmp_path: Path) -> None:
    rq = _load_rq()
    _write(
        tmp_path,
        "memory-bank/back/roadmap/batches/a.yaml",
        "version: roadmap-queue/v2\n"
        "role: back\n"
        "queue:\n"
        "  - id: T-1\n"
        "    epic_id: T-1-a\n"
        "    plan: plan-T-1-a.md\n"
        "    deps: []\n"
        "done: []\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/roadmap/batches/b.yaml",
        "version: roadmap-queue/v2\n"
        "role: back\n"
        "queue:\n"
        "  - id: T-1\n"
        "    epic_id: T-1-b\n"
        "    plan: plan-T-1-b.md\n"
        "    deps: []\n"
        "done: []\n",
    )
    out = rq.roadmap_merge(tmp_path, role="back")
    assert out["ok"] is False
    assert out["error"] == "roadmap_merge_plan_conflict"


def test_is_source_queue_name() -> None:
    rq = _load_rq()
    assert rq.is_source_queue_name("roadmap-foo-epics.queue.yaml") is True
    assert rq.is_source_queue_name("roadmap-epics.queue.yaml") is False
    assert rq.is_source_queue_name("queue.yaml") is False


def test_roadmap_upsert_batch(tmp_path: Path) -> None:
    rq = _load_rq()
    out = rq.roadmap_upsert_batch(
        tmp_path,
        role="back",
        batch="pack",
        title="Pack",
        items=[
            {"id": "T-A", "epic_id": "T-A-one", "plan": "plan-T-A-one.md", "deps": []},
            {
                "id": "T-B",
                "epic_id": "T-B-two",
                "plan": "plan-T-B-two.md",
                "deps": ["T-A"],
            },
        ],
    )
    assert out["ok"] is True
    parsed = rq.parse_roadmap_queue(tmp_path)
    assert [x["id"] for x in parsed["queue"]] == ["T-A", "T-B"]
    assert parsed["batches"]["pack"]["title"] == "Pack"


def test_plan_stem_from_name() -> None:
    rq = _load_rq()
    assert rq.plan_stem_from_name("plan-T-HUB-023-hooks-llm-fallbacks.md") == (
        "T-HUB-023-hooks-llm-fallbacks"
    )
    assert rq.plan_stem_from_name("memory-bank/back/plan/plan-T-1.md") == "T-1"


def test_resolve_epic_slug_prefers_plan_name_and_disk_slug(tmp_path: Path) -> None:
    rq = _load_rq()
    assert (
        rq.resolve_epic_slug(
            tmp_path,
            "back",
            "T-HUB-023",
            plan_name="plan-T-HUB-023-hooks-llm-fallbacks.md",
        )
        == "T-HUB-023-hooks-llm-fallbacks"
    )
    plan_dir = tmp_path / "memory-bank" / "back" / "plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "plan-T-HUB-023-hooks-llm-fallbacks.md").write_text("# p\n", encoding="utf-8")
    assert rq.resolve_epic_slug(tmp_path, "back", "T-HUB-023") == (
        "T-HUB-023-hooks-llm-fallbacks"
    )


def test_resolve_entry_decompose_uses_plan_stem(tmp_path: Path) -> None:
    rq = _load_rq()
    _write(
        tmp_path,
        "memory-bank/back/plan/plan-T-HUB-023-hooks-llm-fallbacks.md",
        "# plan\n",
    )
    entry = rq.resolve_entry(
        tmp_path,
        role="back",
        epic_id="T-HUB-023",
        plan_name="plan-T-HUB-023-hooks-llm-fallbacks.md",
    )
    assert entry["ok"] is True
    assert entry["phase"] == "DECOMPOSE"
    assert entry["epic"] == "T-HUB-023-hooks-llm-fallbacks"
    assert entry["queue_id"] == "T-HUB-023"


def test_arm_roadmap_entry_decompose_arms_full_slug(tmp_path: Path) -> None:
    rq = _load_rq()
    _write_queue(
        tmp_path,
        "version: roadmap-queue/v2\n"
        "role: back\n"
        "queue:\n"
        "  - id: T-HUB-023\n"
        "    epic_id: T-HUB-023-hooks-llm-fallbacks\n"
        "    plan: plan-T-HUB-023-hooks-llm-fallbacks.md\n"
        "    deps: []\n"
        "done: []\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/plan/plan-T-HUB-023-hooks-llm-fallbacks.md",
        "# plan\n",
    )
    sel = rq.select_next_epic(tmp_path)
    assert sel["ok"] is True
    assert sel["entry"]["phase"] == "DECOMPOSE"
    assert sel["entry"]["epic"] == "T-HUB-023-hooks-llm-fallbacks"
    out = rq.arm_roadmap_entry(tmp_path, sel)
    assert out["ok"] is True
    assert out["epic"] == "T-HUB-023-hooks-llm-fallbacks"
    ac = (tmp_path / "memory-bank/activeContext.md").read_text(encoding="utf-8")
    assert "T-HUB-023-hooks-llm-fallbacks/yaml/decompose-index.yaml" in ac
    assert "epic_id: T-HUB-023-hooks-llm-fallbacks" in ac
    assert "decompose-T-HUB-023/" not in ac


def test_plan_path_resolves_layout_v2(tmp_path: Path) -> None:
    rq = _load_rq()
    v2 = (
        tmp_path
        / "memory-bank/back/plan/T-HUB-048-workflow-pack-registry/md/plan.md"
    )
    v2.parent.mkdir(parents=True)
    v2.write_text("# plan v2\n", encoding="utf-8")
    found = rq.plan_path(
        tmp_path, "back", "plan-T-HUB-048-workflow-pack-registry.md"
    )
    assert found == v2
    assert found.is_file()


def test_resolve_entry_accepts_layout_v2_plan(tmp_path: Path) -> None:
    rq = _load_rq()
    _write(
        tmp_path,
        "memory-bank/back/plan/T-HUB-048-workflow-pack-registry/md/plan.md",
        "# plan\n",
    )
    entry = rq.resolve_entry(
        tmp_path,
        role="back",
        epic_id="T-HUB-048",
        plan_name="plan-T-HUB-048-workflow-pack-registry.md",
    )
    assert entry["ok"] is True, entry
    assert entry.get("stop") != "NEED_HUMAN: no_plan for T-HUB-048"
    assert entry["phase"] == "DECOMPOSE"
    assert entry["epic"] == "T-HUB-048-workflow-pack-registry"


def test_mark_queue_epic_done_moves_row(tmp_path: Path) -> None:
    rq = _load_rq()
    _write_queue(
        tmp_path,
        "version: roadmap-queue/v2\n"
        "role: back\n"
        "queue:\n"
        "- id: T-HUB-048\n"
        "  epic_id: T-HUB-048-workflow-pack-registry\n"
        "  plan: plan-T-HUB-048-workflow-pack-registry.md\n"
        "  deps: []\n"
        "  batch: workflow-pack-framework\n"
        "- id: T-HUB-049\n"
        "  epic_id: T-HUB-049-workflow-pack-phase-router\n"
        "  plan: plan-T-HUB-049-workflow-pack-phase-router.md\n"
        "  deps: [T-HUB-048]\n"
        "  batch: workflow-pack-framework\n"
        "done: []\n",
    )
    out = rq.mark_queue_epic_done(
        tmp_path, "T-HUB-048-workflow-pack-registry", role="back"
    )
    assert out["ok"] is True
    assert out["written"] is True
    assert out["id"] == "T-HUB-048"
    parsed = rq.parse_roadmap_queue(tmp_path)
    assert [x["id"] for x in parsed["queue"]] == ["T-HUB-049"]
    assert [x["id"] for x in parsed["done"]] == ["T-HUB-048"]
    again = rq.mark_queue_epic_done(tmp_path, "T-HUB-048", role="back")
    assert again["ok"] is True
    assert again["already_done"] is True
    assert again["written"] is False


def test_roadmap_advance_persists_done_before_next(tmp_path: Path) -> None:
    rq = _load_rq()
    _write_queue(tmp_path, _minimal_queue("T-A", "T-B"))
    for epic in ("T-A", "T-B"):
        _write(tmp_path, f"memory-bank/back/plan/plan-{epic}.md", f"# {epic}\n")
    _mark_epic_done(tmp_path, "T-A")
    if HOOKS not in sys.path:
        sys.path.insert(0, HOOKS)
    from epic import save_epic_state, default_state

    st = default_state()
    st["active"] = True
    st["armed_epic"] = "T-A"
    st["armed_role"] = "back"
    st["role"] = "back"
    save_epic_state(tmp_path, st)
    out = rq.roadmap_advance(tmp_path)
    assert out.get("ok") is True
    assert out.get("mark_done", {}).get("written") is True or out.get("mark_done", {}).get(
        "already_done"
    )
    parsed = rq.parse_roadmap_queue(tmp_path)
    assert "T-A" in [x["id"] for x in parsed["done"]]
    assert "T-A" not in [x["id"] for x in parsed["queue"]]
