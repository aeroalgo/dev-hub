from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path


def _seed_prepare_context(cwd: Path) -> None:
    shard = cwd / "memory-bank" / "integration" / "plan" / "decompose-x" / "e16-foo.yaml"
    shard.parent.mkdir(parents=True)
    shard.write_text("schema: epic-decompose/v1\nstep_id: e16\n", encoding="utf-8")
    index = cwd / "memory-bank" / "integration" / "implement" / "implement-x" / "index.md"
    index.parent.mkdir(parents=True)
    index.write_text("| Step | Status |\n| e16 | pending |\n", encoding="utf-8")
    active = cwd / "memory-bank" / "activeContext.md"
    active.parent.mkdir(parents=True, exist_ok=True)
    active.write_text(
        "## load_now\n"
        "1. [e16-foo.yaml](integration/plan/decompose-x/e16-foo.yaml)\n"
        "2. [index.md](integration/implement/implement-x/index.md)\n\n"
        "## Handoff INTEG IMPLEMENT\n"
        "- **Следующий:** `INTEG IMPLEMENT e16`\n"
        "- **Gaps:** none.\n",
        encoding="utf-8",
    )


def _prepare_for_phase(
    tmp_path: Path, monkeypatch, phase: str | None, runtime: str = "dsh"
):
    module = _load_ctx()
    _seed_prepare_context(tmp_path)
    projection = {
        "phase": phase,
        "projection": {
            "phase": phase,
            "phase_epoch": "test",
            "projection_hash": "sha256:test",
            "index_fingerprint": "sha256:index",
        },
        "projection_hash": "sha256:test",
    }
    monkeypatch.setattr(module, "rebuild_epic_projection", lambda _cwd: projection)
    monkeypatch.setenv("EPIC_RUNTIME", runtime)
    return module.prepare_session(tmp_path)


ROOT = Path(__file__).resolve().parents[2]
SYNC_PATH = ROOT / "dsh" / "scripts" / "sync-agent-md-to-presets.py"
INSTALL_PATH = ROOT / "dsh" / "scripts" / "install-profiles.sh"


def _load_sync():
    spec = importlib.util.spec_from_file_location("sync_agent_md_to_presets", SYNC_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_ctx():
    hooks = str(ROOT / ".claude" / "hooks")
    loop = str(ROOT / "loop")
    for path in (hooks, loop):
        if path not in sys.path:
            sys.path.insert(0, path)
    spec = importlib.util.spec_from_file_location(
        "context_loop_dsh_profile_mapping", ROOT / "loop" / "context_loop.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PHASE_MODELS = ROOT / "dsh" / "patches" / "phase-models.yml"
PROFILE_PHASES = {
    "epic-implement": "IMPLEMENT",
    "epic-qa": "QA",
    "epic-decompose": "DECOMPOSE",
    "epic-plan": "PLAN",
    "epic-creative": "CREATIVE",
    "epic-audit": "AUDIT",
    "epic-bugfix": "BUGFIX",
    "epic-reflect": "REFLECT",
}


def test_install_profiles_provisions_local_bundle(tmp_path: Path) -> None:
    import os
    import stat
    import subprocess

    dsh_home = tmp_path / "dsh"
    fakebin = tmp_path / "bin"
    fakebin.mkdir()
    pnpm_log = tmp_path / "pnpm.log"
    pnpm = fakebin / "pnpm"
    pnpm.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'printf "%s\\t%s\\n" "$PWD" "$*" >>"${PNPM_LOG}"\n'
        'if [[ "${1:-}" != "install" ]]; then\n'
        '  printf "unexpected pnpm args: %s\\n" "$*" >&2\n'
        "  exit 2\n"
        "fi\n"
        "mkdir -p node_modules/dsh-phase-models\n"
        "cp ../../patches/package.json node_modules/dsh-phase-models/package.json\n",
        encoding="utf-8",
    )
    pnpm.chmod(pnpm.stat().st_mode | stat.S_IEXEC)

    env = os.environ.copy()
    env["DSH_HOME"] = str(dsh_home)
    env["PATH"] = f"{fakebin}{os.pathsep}{env['PATH']}"
    env["PNPM_LOG"] = str(pnpm_log)

    result = subprocess.run(
        ["bash", str(INSTALL_PATH)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert (dsh_home / "patches" / "package.json").is_file()
    assert (dsh_home / "patches" / "phase-models.yml").is_file()

    log_lines = pnpm_log.read_text(encoding="utf-8").strip().splitlines()
    assert len(log_lines) == len(PROFILE_PHASES), log_lines

    for profile in PROFILE_PHASES:
        profile_dir = dsh_home / "profiles" / profile
        assert (profile_dir / "package.json").is_file()
        assert not (profile_dir / "node_modules" / ".pnpm").exists()
        bundle = profile_dir / "node_modules" / "dsh-phase-models" / "package.json"
        assert bundle.is_file()
        assert '"name": "dsh-phase-models"' in bundle.read_text(encoding="utf-8")
        matched = [
            line
            for line in log_lines
            if str(profile_dir) in line and "install --ignore-scripts" in line
        ]
        assert matched, log_lines


def test_shared_phase_models_is_a_dsh_bundle() -> None:
    manifest = json.loads((ROOT / "dsh" / "patches" / "package.json").read_text(encoding="utf-8"))
    assert manifest["dsh"]["bundle"]["patch"] == "./phase-models.yml"


def test_profiles_include_shared_phase_models_bundle() -> None:
    for profile in PROFILE_PHASES:
        manifest = json.loads(
            (ROOT / "dsh" / "profiles" / profile / "package.json").read_text(encoding="utf-8")
        )
        assert "dsh-phase-models" in manifest["dsh"]["profile"]["bundles"]
        assert manifest["dependencies"]["dsh-phase-models"] == "file:../../patches"


def test_shared_phase_models_maps_each_profile_phase() -> None:
    text = PHASE_MODELS.read_text(encoding="utf-8")
    for phase in PROFILE_PHASES.values():
        assert f"{phase}:" in text
        assert f"PROJECT_LOOP_{phase}_MODEL" in text


def test_shared_phase_models_is_a_top_level_dsh_patch_list() -> None:
    text = PHASE_MODELS.read_text(encoding="utf-8")
    assert "\n- id: llm" in text
    assert "phases:" not in text
    assert "dsh-phase-models" in text


def test_profile_patch_keeps_phase_specific_llm_bridge() -> None:
    for profile, phase in PROFILE_PHASES.items():
        text = (ROOT / "dsh" / "profiles" / profile / "cordis.patch.yml").read_text(
            encoding="utf-8"
        )
        assert f"PROJECT_LOOP_{phase}_MODEL" in text
        assert "id: llm" in text



def test_shared_phase_models_is_a_top_level_dsh_patch_list() -> None:
    text = PHASE_MODELS.read_text(encoding="utf-8")
    assert "\n- id: llm" in text
    assert "phases:" not in text
    assert "dsh-phase-models" in text


def test_profile_patch_keeps_phase_specific_llm_bridge() -> None:
    for profile, phase in PROFILE_PHASES.items():
        text = (ROOT / "dsh" / "profiles" / profile / "cordis.patch.yml").read_text(
            encoding="utf-8"
        )
        assert f"PROJECT_LOOP_{phase}_MODEL" in text
        assert "id: llm" in text


#


def test_prepare_emits_dsh_profile_implement(tmp_path: Path, monkeypatch) -> None:
    out = _prepare_for_phase(tmp_path, monkeypatch, "BACK IMPLEMENT")
    assert out["dsh_profile"] == "epic-implement"


#


def test_prepare_emits_dsh_profile_qa(tmp_path: Path, monkeypatch) -> None:
    out = _prepare_for_phase(tmp_path, monkeypatch, "BACK QA")
    assert out["dsh_profile"] == "epic-qa"


#


def test_prepare_emits_dsh_profile_decompose(tmp_path: Path, monkeypatch) -> None:
    out = _prepare_for_phase(tmp_path, monkeypatch, "BACK DECOMPOSE")
    assert out["dsh_profile"] == "epic-decompose"


#


def test_prepare_dsh_profile_default_implement(tmp_path: Path, monkeypatch) -> None:
    out = _prepare_for_phase(tmp_path, monkeypatch, None)
    assert out["dsh_profile"] == "epic-implement"


#


def test_prepare_claude_runtime_no_dsh_profile_required(tmp_path: Path, monkeypatch) -> None:
    out = _prepare_for_phase(tmp_path, monkeypatch, "BACK IMPLEMENT", runtime="claude")
    assert out["runtime"] == "claude"
    assert out.get("dsh_profile") in {None, "epic-implement"}


#


def test_sync_verify_implement_preset_contains_ac_plus() -> None:
    module = _load_sync()
    agent_md = (ROOT / ".claude" / "agents" / "verify-implement.md").read_text(encoding="utf-8")
    preset = (ROOT / "dsh" / "presets" / "verify-implement.prompt.md").read_text(encoding="utf-8")

    assert "AC+" in agent_md
    assert "AC+" in preset
    assert preset == module.strip_frontmatter(agent_md)


#


def test_sync_verify_qa_preset_contains_ac_plus() -> None:
    module = _load_sync()
    agent_md = (ROOT / ".claude" / "agents" / "verify-qa.md").read_text(encoding="utf-8")
    preset = (ROOT / "dsh" / "presets" / "verify-qa.prompt.md").read_text(encoding="utf-8")

    assert "AC+" in agent_md
    assert "AC+" in preset
    assert preset == module.strip_frontmatter(agent_md)


#


def test_sync_explorer_preset_contains_body() -> None:
    module = _load_sync()
    agent_md = (ROOT / ".claude" / "agents" / "explorer.md").read_text(encoding="utf-8")
    preset = (ROOT / "dsh" / "presets" / "explorer.prompt.md").read_text(encoding="utf-8")

    assert "name: explorer" not in preset
    assert preset == module.strip_frontmatter(agent_md)


#


def test_strip_frontmatter_basic() -> None:
    module = _load_sync()

    assert module.strip_frontmatter("---\nname: x\n---\nbody") == "body"


#


def test_strip_frontmatter_no_frontmatter() -> None:
    module = _load_sync()
    text = "plain markdown\n---\nbody"

    assert module.strip_frontmatter(text) == text


#


def test_sync_idempotent() -> None:
    module = _load_sync()

    assert module.sync() == 0
    first = {
        path: path.read_bytes()
        for path in (ROOT / "dsh" / "presets").glob("*.prompt.md")
    }
    assert module.sync() == 0
    second = {
        path: path.read_bytes()
        for path in (ROOT / "dsh" / "presets").glob("*.prompt.md")
    }

    assert first == second


#


def test_sync_verify_implement_preset_hash_matches_agent_md() -> None:
    module = _load_sync()
    expected = module.strip_frontmatter(
        (ROOT / ".claude" / "agents" / "verify-implement.md").read_text(encoding="utf-8")
    ).encode("utf-8")
    actual = (ROOT / "dsh" / "presets" / "verify-implement.prompt.md").read_bytes()
    assert hashlib.sha256(actual).digest() == hashlib.sha256(expected).digest()


#


def test_sync_verify_implement_preset_tracks_agent_md(tmp_path: Path, monkeypatch) -> None:
    module = _load_sync()
    agents_dir = tmp_path / "agents"
    presets_dir = tmp_path / "presets"
    agents_dir.mkdir()
    for agent_id in module.AGENT_IDS:
        (agents_dir / f"{agent_id}.md").write_text(
            f"---\nname: {agent_id}\n---\n{agent_id} body\n",
            encoding="utf-8",
        )
    monkeypatch.setattr(module, "AGENTS_DIR", agents_dir)
    monkeypatch.setattr(module, "PRESETS_DIR", presets_dir)

    assert module.sync() == 0
    (agents_dir / "verify-implement.md").write_text(
        "---\nname: verify\n---\nAC+ changed\n", encoding="utf-8"
    )

    assert module.sync() == 0
    assert (presets_dir / "verify-implement.prompt.md").read_text(encoding="utf-8") == "AC+ changed\n"
    assert module.sync(check=True) == 0


def test_profile_patch_contains_no_unsupported_shared_include_keys() -> None:
    for profile in PROFILE_PHASES:
        text = (ROOT / "dsh" / "profiles" / profile / "cordis.patch.yml").read_text(
            encoding="utf-8"
        )
        assert "include:" not in text
        assert "import:" not in text
        assert "extends:" not in text


def test_dsh_bundle_dependency_is_executable_from_profile_directory() -> None:
    manifest = json.loads((ROOT / "dsh" / "patches" / "package.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "dsh-phase-models"
    assert (ROOT / "dsh" / "patches" / manifest["dsh"]["bundle"]["patch"]).is_file()


def test_phase_model_bundle_uses_loader_patch_shape() -> None:
    text = PHASE_MODELS.read_text(encoding="utf-8")
    assert text.lstrip().startswith("#")
    assert "\n- id: llm\n" in text
    assert "model: !!js process.env.PROJECT_LOOP_MODEL ?? 'default'" in text
    assert "model: PROJECT_LOOP_MODEL" in text
    assert "credentials: !!js process.env.DSH_HOME + '/.credentials.yaml'" in text


def test_all_profiles_have_shared_bundle_and_phase_bridge() -> None:
    for profile, phase in PROFILE_PHASES.items():
        manifest = json.loads(
            (ROOT / "dsh" / "profiles" / profile / "package.json").read_text(encoding="utf-8")
        )
        patch = (ROOT / "dsh" / "profiles" / profile / "cordis.patch.yml").read_text(
            encoding="utf-8"
        )
        assert "dsh-phase-models" in manifest["dsh"]["profile"]["bundles"]
        assert f"PROJECT_LOOP_{phase}_MODEL" in patch
        assert "id: llm" in patch


def test_shared_bundle_is_loaded_before_profile_local_patch() -> None:
    for profile in PROFILE_PHASES:
        manifest = json.loads(
            (ROOT / "dsh" / "profiles" / profile / "package.json").read_text(encoding="utf-8")
        )
        bundles = manifest["dsh"]["profile"]["bundles"]
        assert bundles.index("dsh-phase-models") > bundles.index("@deepseek-ai/dsh-base")
        assert bundles.index("dsh-phase-models") < len(bundles)


def test_phase_model_source_keeps_all_eight_rows() -> None:
    text = PHASE_MODELS.read_text(encoding="utf-8")
    assert text.count("PROJECT_LOOP_") >= 8
    for phase in PROFILE_PHASES.values():
        assert f"# {phase}: PROJECT_LOOP_{phase}_MODEL" in text


def test_phase_model_package_has_no_runtime_code() -> None:
    assert not (ROOT / "dsh" / "patches" / "index.js").exists()
    assert not (ROOT / "dsh" / "patches" / "index.ts").exists()


