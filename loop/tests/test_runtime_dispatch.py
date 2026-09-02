import json
from pathlib import Path

from loop.runtime.dispatch import print_argv, run_session


def test_claude_dispatch_dry_run(tmp_path, capsys):
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("hello world", encoding="utf-8")

    code = run_session(
        runtime_id="claude",
        prompt_file=prompt_file,
        phase="IMPLEMENT",
        dry_run=True,
    )
    assert code == 0
    captured = capsys.readouterr()
    assert "claude" in captured.out
    assert "hello world" in captured.out


def test_dsh_dispatch_dry_run(tmp_path, capsys):
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("hello dsh", encoding="utf-8")

    code = run_session(
        runtime_id="dsh",
        prompt_file=prompt_file,
        phase="IMPLEMENT",
        dry_run=True,
    )
    assert code == 0
    captured = capsys.readouterr()
    assert "dsh --profile epic-implement" in captured.out
    assert "hello dsh" in captured.out


def test_unknown_runtime_exit2_json_diagnostic(tmp_path, capsys):
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("test", encoding="utf-8")

    code = run_session(
        runtime_id="nonexistent_runtime_xyz",
        prompt_file=prompt_file,
        phase="IMPLEMENT",
        dry_run=True,
    )
    assert code == 2
    captured = capsys.readouterr()
    diag = json.loads(captured.err.strip())
    assert diag["error"] == "unknown_runtime"
    assert diag["runtime_id"] == "nonexistent_runtime_xyz"


def test_dispatch_print_argv_json(tmp_path, capsys):
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text(
        "## load_now\n- `memory-bank/activeContext.md`\n- step s06\n",
        encoding="utf-8",
    )

    code = print_argv(
        runtime_id="claude",
        prompt_file=prompt_file,
        phase="IMPLEMENT",
    )
    assert code == 0
    captured = capsys.readouterr()
    cmd = json.loads(captured.out)
    assert cmd[0] == "claude"
    assert cmd[1] == "-p"
    assert "activeContext.md" in cmd[2]
    assert cmd[2].count("\n") >= 2
    assert "--output-format" in cmd


def test_dispatch_exit_code_passthrough(tmp_path, monkeypatch):
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("test", encoding="utf-8")

    class DummyCompletedProcess:
        returncode = 42

    monkeypatch.setattr("subprocess.run", lambda cmd: DummyCompletedProcess())

    code = run_session(
        runtime_id="claude",
        prompt_file=prompt_file,
        phase="IMPLEMENT",
        dry_run=False,
    )
    assert code == 42


def test_codex_dispatch_pipes_prompt_on_stdin(tmp_path, monkeypatch):
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("hello codex", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs

        class DummyCompletedProcess:
            returncode = 0

        return DummyCompletedProcess()

    monkeypatch.setattr("subprocess.run", fake_run)

    code = run_session(
        runtime_id="codex",
        prompt_file=prompt_file,
        phase="IMPLEMENT",
        extras={"project_root": str(tmp_path)},
        dry_run=False,
    )
    assert code == 0
    assert captured["kwargs"]["input"] == b"hello codex"
    assert "exec" in captured["cmd"]
