"""Tests for bin/hub-link alongside mode."""

import os
import subprocess
from pathlib import Path


def test_alongside_is_default(tmp_path: Path):
    """hub-link without --mode on clean fixture defaults to alongside (creates harness/ symlink, .dev-hub, router stub, not full-replace)."""
    hub_dir = Path(__file__).resolve().parents[2]
    product_dir = tmp_path / "default_product"
    product_dir.mkdir()

    env = dict(os.environ, DEV_HUB=str(hub_dir))
    hub_link_bin = hub_dir / "bin" / "hub-link"

    # Invoked without --mode
    res = subprocess.run([str(hub_link_bin), str(product_dir)], env=env, capture_output=True, text=True)
    assert res.returncode == 0, f"hub-link failed: {res.stderr}"

    # Verify alongside artifacts exist
    assert (product_dir / "harness").is_symlink(), "harness must be a symlink"
    assert (product_dir / ".dev-hub").is_file(), ".dev-hub must be created"
    assert (product_dir / ".cursor" / "rules.d" / "dev-hub-harness-router.mdc").is_file()

    # Verify full mode artifacts were NOT created (.cursor/rules as a symlink to hub rules)
    assert not (product_dir / ".cursor" / "rules").is_symlink(), "full-replace .cursor/rules symlink must not be created"


def test_alongside_clean_fixture(tmp_path: Path):
    """alongside on clean product fixture: harness/ symlink + .dev-hub + router stub created; CLAUDE.md absent = no CLAUDE.md created."""
    hub_dir = Path(__file__).resolve().parents[2]
    product_dir = tmp_path / "clean_product"
    product_dir.mkdir()

    env = dict(os.environ, DEV_HUB=str(hub_dir))
    hub_link_bin = hub_dir / "bin" / "hub-link"

    res = subprocess.run([str(hub_link_bin), "--mode=alongside", str(product_dir)], env=env, capture_output=True, text=True)
    assert res.returncode == 0, f"hub-link failed: {res.stderr}"

    # harness/ symlink
    harness_symlink = product_dir / "harness"
    assert harness_symlink.is_symlink(), "harness must be a symlink"
    assert harness_symlink.resolve() == (hub_dir / "harness").resolve()

    # .dev-hub pointer
    dev_hub_file = product_dir / ".dev-hub"
    assert dev_hub_file.exists()
    assert dev_hub_file.read_text().strip() != ""

    # router stub in .cursor/rules.d/
    router_stub = product_dir / ".cursor" / "rules.d" / "dev-hub-harness-router.mdc"
    assert router_stub.exists()
    assert not router_stub.is_symlink()
    assert "dev-hub harness role command router" in router_stub.read_text()

    # CLAUDE.harness.md symlink
    claude_harness = product_dir / "CLAUDE.harness.md"
    assert claude_harness.is_symlink()
    assert claude_harness.resolve() == (hub_dir / "harness" / "claude" / "CLAUDE.harness.md").resolve()

    # AGENTS.md created
    agents_md = product_dir / "AGENTS.md"
    assert agents_md.exists()

    # CLAUDE.md created with marker block
    claude_md = product_dir / "CLAUDE.md"
    assert claude_md.exists()
    assert "<!-- dev-hub:harness:begin -->" in claude_md.read_text()
    assert "<!-- dev-hub:harness:end -->" in claude_md.read_text()


def test_alongside_default_mode(tmp_path: Path):
    """Default mode without --mode flag should be alongside."""
    hub_dir = Path(__file__).resolve().parents[2]
    product_dir = tmp_path / "default_product"
    product_dir.mkdir()

    env = dict(os.environ, DEV_HUB=str(hub_dir))
    hub_link_bin = hub_dir / "bin" / "hub-link"

    res = subprocess.run([str(hub_link_bin), str(product_dir)], env=env, capture_output=True, text=True)
    assert res.returncode == 0, f"hub-link failed: {res.stderr}"

    claude_md = product_dir / "CLAUDE.md"
    assert claude_md.exists()
    assert "<!-- dev-hub:harness:begin -->" in claude_md.read_text()
    assert (product_dir / "harness").is_symlink()


def test_alongside_fails_on_conflict(tmp_path: Path):
    """alongside on fixture with existing regular file where symlink is expected: exit non-zero, file untouched."""
    hub_dir = Path(__file__).resolve().parents[2]
    product_dir = tmp_path / "conflict_product"
    product_dir.mkdir()

    # Create regular file at harness (conflicts with harness/ symlink)
    harness_conflict = product_dir / "harness"
    harness_conflict.write_text("existing user content")

    env = dict(os.environ, DEV_HUB=str(hub_dir))
    hub_link_bin = hub_dir / "bin" / "hub-link"

    res = subprocess.run([str(hub_link_bin), "--mode=alongside", str(product_dir)], env=env, capture_output=True, text=True)
    assert res.returncode != 0
    assert "ERROR:" in res.stderr

    # Untouched
    assert harness_conflict.is_file()
    assert harness_conflict.read_text() == "existing user content"


def test_alongside_preserves_existing_user_agents_and_claude_md(tmp_path: Path):
    """alongside mode patches CLAUDE.md while preserving existing user content, and leaves AGENTS.md intact."""
    hub_dir = Path(__file__).resolve().parents[2]
    product_dir = tmp_path / "existing_files_product"
    product_dir.mkdir()

    claude_md = product_dir / "CLAUDE.md"
    claude_md.write_text("# My User Project\n\nUser custom claude instructions\n")

    agents_md = product_dir / "AGENTS.md"
    agents_md.write_text("User custom agents instructions")

    env = dict(os.environ, DEV_HUB=str(hub_dir))
    hub_link_bin = hub_dir / "bin" / "hub-link"

    res = subprocess.run([str(hub_link_bin), "--mode=alongside", str(product_dir)], env=env, capture_output=True, text=True)
    assert res.returncode == 0

    claude_text = claude_md.read_text()
    assert "# My User Project" in claude_text
    assert "User custom claude instructions" in claude_text
    assert "<!-- dev-hub:harness:begin -->" in claude_text
    assert "<!-- dev-hub:harness:end -->" in claude_text
    assert agents_md.read_text() == "User custom agents instructions"


def test_alongside_creates_claude_md(tmp_path: Path):
    """patch on missing CLAUDE.md creates file with marker block."""
    hub_dir = Path(__file__).resolve().parents[2]
    product_dir = tmp_path / "missing_claude_product"
    product_dir.mkdir()

    env = dict(os.environ, DEV_HUB=str(hub_dir))
    hub_link_bin = hub_dir / "bin" / "hub-link"

    res = subprocess.run([str(hub_link_bin), "--mode=alongside", str(product_dir)], env=env, capture_output=True, text=True)
    assert res.returncode == 0

    claude_md = product_dir / "CLAUDE.md"
    assert claude_md.exists()
    content = claude_md.read_text()
    assert "<!-- dev-hub:harness:begin -->" in content
    assert "<!-- dev-hub:harness:end -->" in content
    assert "Harness role commands" in content


def test_alongside_preserves_claude(tmp_path: Path):
    """patch on existing CLAUDE.md preserves user content outside markers."""
    from loop.hub_claude_patch import patch_claude_md

    claude_file = tmp_path / "CLAUDE.md"
    claude_file.write_text("# Header\nUser instruction line 1\n")

    patch_claude_md(claude_file, "custom harness info")
    text = claude_file.read_text()
    assert "# Header\nUser instruction line 1" in text
    assert "<!-- dev-hub:harness:begin -->\ncustom harness info\n<!-- dev-hub:harness:end -->" in text


def test_alongside_patch_idempotent(tmp_path: Path):
    """patch is idempotent (second call: file hash / content unchanged)."""
    import hashlib
    from loop.hub_claude_patch import patch_claude_md

    claude_file = tmp_path / "CLAUDE.md"
    claude_file.write_text("# User Header\n\nSome guidelines.\n")

    changed1 = patch_claude_md(claude_file, "custom harness info")
    assert changed1 is True
    digest1 = hashlib.sha256(claude_file.read_bytes()).hexdigest()

    changed2 = patch_claude_md(claude_file, "custom harness info")
    assert changed2 is False
    digest2 = hashlib.sha256(claude_file.read_bytes()).hexdigest()

    assert digest1 == digest2


def test_alongside_router_stub_conflict(tmp_path: Path):
    """alongside fails when .cursor/rules.d/dev-hub-harness-router.mdc is a custom user file."""
    hub_dir = Path(__file__).resolve().parents[2]
    product_dir = tmp_path / "router_conflict_product"
    product_dir.mkdir()

    router_dir = product_dir / ".cursor" / "rules.d"
    router_dir.mkdir(parents=True)
    custom_router = router_dir / "dev-hub-harness-router.mdc"
    custom_router.write_text("User custom router rule")

    env = dict(os.environ, DEV_HUB=str(hub_dir))
    hub_link_bin = hub_dir / "bin" / "hub-link"

    res = subprocess.run([str(hub_link_bin), "--mode=alongside", str(product_dir)], env=env, capture_output=True, text=True)
    assert res.returncode != 0
    assert "ERROR:" in res.stderr
    assert custom_router.read_text() == "User custom router rule"


def test_alongside_unlink(tmp_path: Path):
    """alongside unlink removes harness symlink and .dev-hub; CLAUDE.md user content intact."""
    hub_dir = Path(__file__).resolve().parents[2]
    product_dir = tmp_path / "unlink_product"
    product_dir.mkdir()

    # User preexisting CLAUDE.md and settings
    claude_md = product_dir / "CLAUDE.md"
    claude_md.write_text("# My User Project\n\nUser instructions here.\n")

    env = dict(os.environ, DEV_HUB=str(hub_dir))
    hub_link_bin = hub_dir / "bin" / "hub-link"
    hub_unlink_bin = hub_dir / "bin" / "hub-unlink"

    # 1. Link alongside
    res_link = subprocess.run([str(hub_link_bin), "--mode=alongside", str(product_dir)], env=env, capture_output=True, text=True)
    assert res_link.returncode == 0

    assert (product_dir / "harness").is_symlink()
    assert (product_dir / ".dev-hub").is_file()
    assert (product_dir / ".cursor" / "rules.d" / "dev-hub-harness-router.mdc").is_file()

    # 2. Unlink alongside
    res_unlink = subprocess.run([str(hub_unlink_bin), "--mode=alongside", str(product_dir)], env=env, capture_output=True, text=True)
    assert res_unlink.returncode == 0

    # Installer artifacts removed
    assert not (product_dir / "harness").exists()
    assert not (product_dir / ".dev-hub").exists()
    assert not (product_dir / ".cursor" / "rules.d" / "dev-hub-harness-router.mdc").exists()
    assert not (product_dir / "CLAUDE.harness.md").exists()

    # User content preserved
    assert claude_md.exists()
    content = claude_md.read_text()
    assert "# My User Project" in content
    assert "User instructions here." in content
    assert "<!-- dev-hub:harness:begin -->" not in content
    assert "<!-- dev-hub:harness:end -->" not in content


def test_alongside_settings_hooks_point_to_harness(tmp_path: Path):
    """US-005: merged settings keep user permissions; hooks resolve via harness/hooks."""
    import json

    hub_dir = Path(__file__).resolve().parents[2]
    product_dir = tmp_path / "settings_merge_product"
    product_dir.mkdir()

    settings_dir = product_dir / ".claude"
    settings_dir.mkdir()
    settings_file = settings_dir / "settings.json"
    settings_file.write_text(
        json.dumps(
            {
                "permissions": {"deny": ["Bash(rm -rf *)"]},
                "hooks": {
                    "SessionStart": [
                        {"hooks": [{"type": "command", "command": "echo user-start"}]}
                    ]
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    env = dict(os.environ, DEV_HUB=str(hub_dir))
    hub_link_bin = hub_dir / "bin" / "hub-link"
    res = subprocess.run(
        [str(hub_link_bin), "--mode=alongside", str(product_dir)],
        env=env,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"hub-link failed: {res.stderr}"

    merged = json.loads(settings_file.read_text(encoding="utf-8"))
    assert merged["permissions"]["deny"] == ["Bash(rm -rf *)"]

    session_cmds = []
    for entry in merged["hooks"]["SessionStart"]:
        for hook in entry.get("hooks", []):
            if isinstance(hook, dict) and "command" in hook:
                session_cmds.append(hook["command"])

    assert any("echo user-start" in c for c in session_cmds)
    harness_cmds = [c for c in session_cmds if "harness/hooks/session-start.py" in c]
    assert harness_cmds, "SessionStart must include harness/hooks/session-start.py"
    assert not any(".claude/hooks/" in c for c in session_cmds if "session-start.py" in c)

    resolved = (product_dir / "harness" / "hooks" / "session-start.py").resolve()
    assert resolved.is_file()
    assert not (product_dir / ".claude" / "hooks").exists()


def test_alongside_skips_cursor_rules(tmp_path: Path):
    """TM-002: Pre-existing .cursor/rules and other files in .cursor/ are not touched."""
    hub_dir = Path(__file__).resolve().parents[2]
    product_dir = tmp_path / "cursor_rules_product"
    product_dir.mkdir()

    # Pre-existing .cursor/rules/custom.mdc
    user_rule_dir = product_dir / ".cursor" / "rules"
    user_rule_dir.mkdir(parents=True)
    custom_rule = user_rule_dir / "custom-user-rule.mdc"
    custom_rule.write_text("User rule content here")

    env = dict(os.environ, DEV_HUB=str(hub_dir))
    hub_link_bin = hub_dir / "bin" / "hub-link"

    res = subprocess.run([str(hub_link_bin), "--mode=alongside", str(product_dir)], env=env, capture_output=True, text=True)
    assert res.returncode == 0, f"hub-link failed: {res.stderr}"

    # Verify custom rule exists and untouched
    assert custom_rule.is_file()
    assert custom_rule.read_text() == "User rule content here"

    # .cursor/rules directory should not be a symlink or overwritten
    assert not user_rule_dir.is_symlink()
    assert user_rule_dir.is_dir()


def test_alongside_unlink_preserves_claude_body(tmp_path: Path):
    """unlink strips marker block; user lines outside markers preserved."""
    from loop.hub_claude_patch import patch_claude_md, strip_claude_md_block

    claude_file = tmp_path / "CLAUDE.md"
    claude_file.write_text("# Section 1\nSome user notes\n\n# Section 2\nMore notes\n")

    # Patch
    patch_claude_md(claude_file, "harness block details")
    patched_text = claude_file.read_text()
    assert "harness block details" in patched_text

    # Strip
    changed = strip_claude_md_block(claude_file)
    assert changed is True

    final_text = claude_file.read_text()
    assert "# Section 1\nSome user notes" in final_text
    assert "# Section 2\nMore notes" in final_text
    assert "<!-- dev-hub:harness:begin -->" not in final_text
    assert "<!-- dev-hub:harness:end -->" not in final_text


def test_alongside_default_does_not_touch_agents(tmp_path: Path):
    """TM-004: alongside default does not touch .agents."""
    hub_dir = Path(__file__).resolve().parents[2]
    product_dir = tmp_path / "agents_default_product"
    product_dir.mkdir()

    agents_dir = product_dir / ".agents"
    agents_dir.mkdir()
    user_skill = agents_dir / "my-skill.md"
    user_skill.write_text("user custom skill")

    env = dict(os.environ, DEV_HUB=str(hub_dir))
    hub_link_bin = hub_dir / "bin" / "hub-link"

    res = subprocess.run([str(hub_link_bin), "--mode=alongside", str(product_dir)], env=env, capture_output=True, text=True)
    assert res.returncode == 0, f"hub-link failed: {res.stderr}"

    assert not (product_dir / ".agents" / "skills").exists()
    assert not (product_dir / ".agents").is_symlink()
    assert user_skill.read_text() == "user custom skill"


def test_alongside_with_skills_success_and_unlink(tmp_path: Path):
    """TM-004/TM-005: alongside --with-skills links .agents/skills to harness/skills, unlink removes it."""
    hub_dir = Path(__file__).resolve().parents[2]
    product_dir = tmp_path / "agents_skills_product"
    product_dir.mkdir()

    env = dict(os.environ, DEV_HUB=str(hub_dir))
    hub_link_bin = hub_dir / "bin" / "hub-link"
    hub_unlink_bin = hub_dir / "bin" / "hub-unlink"

    # Link with --with-skills
    res = subprocess.run([str(hub_link_bin), "--mode=alongside", "--with-skills", str(product_dir)], env=env, capture_output=True, text=True)
    assert res.returncode == 0, f"hub-link failed: {res.stderr}"

    skills_link = product_dir / ".agents" / "skills"
    assert skills_link.is_symlink()
    assert (skills_link / "role-command").is_dir() or (skills_link / "explore").is_dir() or skills_link.exists()

    # Unlink
    res_u = subprocess.run([str(hub_unlink_bin), "--mode=alongside", str(product_dir)], env=env, capture_output=True, text=True)
    assert res_u.returncode == 0, f"hub-unlink failed: {res_u.stderr}"
    assert not skills_link.exists()


def test_alongside_with_skills_conflict_fail_closed(tmp_path: Path):
    """TM-005: alongside --with-skills fail-closed if .agents/skills is regular directory."""
    hub_dir = Path(__file__).resolve().parents[2]
    product_dir = tmp_path / "agents_conflict_product"
    product_dir.mkdir()

    skills_dir = product_dir / ".agents" / "skills"
    skills_dir.mkdir(parents=True)
    custom_skill = skills_dir / "custom.md"
    custom_skill.write_text("custom user skill content")

    env = dict(os.environ, DEV_HUB=str(hub_dir))
    hub_link_bin = hub_dir / "bin" / "hub-link"

    res = subprocess.run([str(hub_link_bin), "--mode=alongside", "--with-skills", str(product_dir)], env=env, capture_output=True, text=True)
    assert res.returncode == 2, f"expected exit 2, got {res.returncode}"
    assert "ERROR:" in res.stderr
    assert custom_skill.is_file()
    assert custom_skill.read_text() == "custom user skill content"
    assert not skills_dir.is_symlink()


def test_alongside_unlink_preserves_foreign_skills_symlink(tmp_path: Path):
    """AC- N3: unlink alongside must not remove non-installer-owned .agents/skills symlink."""
    hub_dir = Path(__file__).resolve().parents[2]
    product_dir = tmp_path / "foreign_skills_product"
    product_dir.mkdir()

    foreign_skills_dir = tmp_path / "custom_user_skills"
    foreign_skills_dir.mkdir()
    (foreign_skills_dir / "my_custom.md").write_text("custom")

    agents_dir = product_dir / ".agents"
    agents_dir.mkdir()
    skills_link = agents_dir / "skills"
    skills_link.symlink_to(foreign_skills_dir)

    env = dict(os.environ, DEV_HUB=str(hub_dir))
    hub_unlink_bin = hub_dir / "bin" / "hub-unlink"

    res_u = subprocess.run([str(hub_unlink_bin), "--mode=alongside", str(product_dir)], env=env, capture_output=True, text=True)
    assert res_u.returncode == 0, f"hub-unlink failed: {res_u.stderr}"
    assert skills_link.is_symlink()
    assert (skills_link / "my_custom.md").is_file()


def test_alongside_unlink_preserves_custom_harness_substring_skills_symlink(tmp_path: Path):
    """AC- N3: unlink alongside must not remove custom symlink even if target path has substring 'harness/skills'."""
    hub_dir = Path(__file__).resolve().parents[2]
    product_dir = tmp_path / "custom_substring_product"
    product_dir.mkdir()

    custom_dir = tmp_path / "custom-harness" / "skills"
    custom_dir.mkdir(parents=True)
    (custom_dir / "custom_rule.md").write_text("content")

    agents_dir = product_dir / ".agents"
    agents_dir.mkdir()
    skills_link = agents_dir / "skills"
    skills_link.symlink_to(custom_dir)

    env = dict(os.environ, DEV_HUB=str(hub_dir))
    hub_unlink_bin = hub_dir / "bin" / "hub-unlink"

    res_u = subprocess.run([str(hub_unlink_bin), "--mode=alongside", str(product_dir)], env=env, capture_output=True, text=True)
    assert res_u.returncode == 0, f"hub-unlink failed: {res_u.stderr}"
    assert skills_link.is_symlink()
    assert (skills_link / "custom_rule.md").is_file()
