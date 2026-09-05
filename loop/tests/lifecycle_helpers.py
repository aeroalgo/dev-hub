from pathlib import Path


def record_finished_artifact(cwd: Path, artifact: Path) -> None:
    from harness.hooks.epic.core import _append_event, parse_qa_verdict

    role, phase, epic_id = artifact.relative_to(cwd).parts[1:4]
    kind = "bugfix_done" if phase == "bugfix" else (
        "qa_pass" if parse_qa_verdict(artifact) == "pass" else "qa_fail"
    )
    assert _append_event(cwd, role, epic_id, kind, artifact)
