import tempfile
from pathlib import Path
import subprocess
import sys
import yaml
import pytest

def test_check_mode_exit1_on_drift(tmp_path: Path):
    manifest_data = {
        "schema_version": "harness-manifest/v1",
        "agents": {
            "test-agent": {
                "description": "Test",
                "source": "harness/agents/test.md",
                "runtimes": {
                    "codex": {
                        "materialize": True,
                        "target": ".codex/agents/test.toml",
                    }
                }
            }
        },
        "hooks": {},
        "instructions": {},
    }
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(yaml.dump(manifest_data), encoding="utf-8")

    # Source exists, but dest does not -> drift
    source_file = tmp_path / "harness/agents/test.md"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("agent code", encoding="utf-8")

    bin_path = Path(__file__).resolve().parents[2] / "bin" / "runtime-sync"

    res = subprocess.run(
        [sys.executable, str(bin_path), "--manifest", str(manifest_path), "--runtime", "codex", "--check"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True
    )
    assert res.returncode == 1
    assert "Drift detected" in res.stdout or "Drift detected" in res.stderr

# Alias for cp1 matching -k check_exit1
test_check_exit1 = test_check_mode_exit1_on_drift

def test_check_mode_exit0_no_drift(tmp_path: Path):
    manifest_data = {
        "schema_version": "harness-manifest/v1",
        "agents": {
            "test-agent": {
                "description": "Test",
                "source": "harness/agents/test.md",
                "runtimes": {
                    "codex": {
                        "materialize": True,
                        "target": ".codex/agents/test.toml",
                    }
                }
            }
        },
        "hooks": {},
        "instructions": {},
    }
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(yaml.dump(manifest_data), encoding="utf-8")

    source_file = tmp_path / "harness/agents/test.md"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("agent code", encoding="utf-8")

    bin_path = Path(__file__).resolve().parents[2] / "bin" / "runtime-sync"
    subprocess.run(
        [sys.executable, str(bin_path), "--manifest", str(manifest_path), "--runtime", "codex", "--apply"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        check=True,
    )

    res = subprocess.run(
        [sys.executable, str(bin_path), "--manifest", str(manifest_path), "--runtime", "codex", "--check"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True
    )
    assert res.returncode == 0
    assert "No drift detected" in res.stdout

# Alias for cp2 matching -k check_exit0
test_check_exit0 = test_check_mode_exit0_no_drift

def test_apply_mode_calls_generators(tmp_path: Path):
    manifest_data = {
        "schema_version": "harness-manifest/v1",
        "agents": {
            "test-agent": {
                "description": "Test",
                "source": "harness/agents/test.md",
                "runtimes": {
                    "codex": {
                        "materialize": True,
                        "target": ".codex/agents/test.toml",
                    }
                }
            }
        },
        "hooks": {},
        "instructions": {},
    }
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(yaml.dump(manifest_data), encoding="utf-8")

    source_file = tmp_path / "harness/agents/test.md"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("agent code", encoding="utf-8")

    bin_path = Path(__file__).resolve().parents[2] / "bin" / "runtime-sync"

    res = subprocess.run(
        [sys.executable, str(bin_path), "--manifest", str(manifest_path), "--runtime", "codex", "--apply"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True
    )
    assert res.returncode == 0
    dest_text = (tmp_path / ".codex/agents/test.toml").read_text(encoding="utf-8")
    assert 'name = "test-agent"' in dest_text
    assert "agent code" in dest_text

def test_runtime_all_iterates(tmp_path: Path):
    manifest_data = {
        "schema_version": "harness-manifest/v1",
        "agents": {
            "test-agent": {
                "description": "Test",
                "source": "harness/agents/test.md",
                "runtimes": {
                    "codex": {
                        "materialize": True,
                        "target": ".codex/agents/test.toml",
                    },
                    "dsh": {
                        "materialize": True,
                        "target": ".dsh/agents/test.toml",
                    }
                }
            }
        },
        "hooks": {},
        "instructions": {},
    }
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(yaml.dump(manifest_data), encoding="utf-8")

    source_file = tmp_path / "harness/agents/test.md"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("agent code", encoding="utf-8")

    bin_path = Path(__file__).resolve().parents[2] / "bin" / "runtime-sync"

    res = subprocess.run(
        [sys.executable, str(bin_path), "--manifest", str(manifest_path), "--runtime", "all", "--apply"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True
    )
    assert res.returncode == 0
    assert (tmp_path / ".codex/agents/test.toml").exists()
    assert (tmp_path / ".dsh/agents/test.toml").exists()

# Alias for cp3 matching -k all_runtimes
test_all_runtimes = test_runtime_all_iterates

def test_preflight_warn_no_abort(tmp_path: Path):
    manifest_data = {
        "schema_version": "harness-manifest/v1",
        "agents": {
            "test-agent": {
                "description": "Test",
                "source": "harness/agents/test.md",
                "runtimes": {
                    "codex": {
                        "materialize": True,
                        "target": ".codex/agents/test.toml",
                    }
                }
            }
        },
        "hooks": {},
        "instructions": {},
    }
    manifest_path = tmp_path / "harness/manifest.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(yaml.dump(manifest_data), encoding="utf-8")

    source_file = tmp_path / "harness/agents/test.md"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("agent code", encoding="utf-8")

    session_start = Path(__file__).resolve().parents[2] / "harness" / "hooks" / "session-start.py"

    env = {
        "EPIC_RUNTIME": "codex",
        "PATH": subprocess.os.environ.get("PATH", ""),
        "PYTHONPATH": str(Path(__file__).resolve().parents[2]),
    }

    input_data = '{"cwd": "%s", "source": "startup"}' % str(tmp_path)

    res = subprocess.run(
        [sys.executable, str(session_start)],
        input=input_data,
        env=env,
        capture_output=True,
        text=True
    )
    assert res.returncode == 0
    assert "WARNING" in res.stderr or "drift" in res.stderr

# Alias for cp4 matching -k preflight_warn
test_preflight_warn = test_preflight_warn_no_abort
