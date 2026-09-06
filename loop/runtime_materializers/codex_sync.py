from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from loop.runtime_materializers.agents import materialize_agents
from loop.runtime_materializers.hooks_json import generate_hooks_json
from loop.runtime_materializers.manifest_schema import HarnessManifest
from loop.runtime_materializers.sync import ApplyResult, ManifestSync


@dataclass
class CodexApplyResult:
    agents: list[str]
    hooks_json: str
    instructions: ApplyResult


def apply_codex(
    manifest: HarnessManifest,
    *,
    manifest_path: Path,
    root_dir: Path,
) -> CodexApplyResult:
    root_dir = root_dir.resolve()
    agents = materialize_agents(manifest, "codex", dest_root=root_dir, repo_root=root_dir)
    hooks_dest = root_dir / ".codex" / "hooks.json"
    generate_hooks_json(manifest, manifest_path, hooks_dest, repo_root=root_dir)

    sync = ManifestSync(manifest, root_dir=root_dir)
    instruction_result = ApplyResult()
    for target in sync.collect_targets("codex"):
        if target.kind != "instruction":
            continue
        if not target.source.exists():
            instruction_result.skipped += 1
            continue
        target.dest.parent.mkdir(parents=True, exist_ok=True)
        existed = target.dest.exists()
        shutil.copy2(target.source, target.dest)
        if existed:
            instruction_result.updated += 1
        else:
            instruction_result.created += 1

    return CodexApplyResult(
        agents=agents,
        hooks_json=str(hooks_dest),
        instructions=instruction_result,
    )


def codex_drift_items(
    manifest: HarnessManifest,
    *,
    manifest_path: Path,
    root_dir: Path,
) -> list[str]:
    root_dir = root_dir.resolve()
    issues: list[str] = []

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        expected_agents = materialize_agents(
            manifest, "codex", dest_root=tmp_root, repo_root=root_dir
        )
        for expected_path in expected_agents:
            expected = Path(expected_path)
            actual = root_dir / expected.relative_to(tmp_root)
            if not actual.exists():
                issues.append(f"missing_dest: {actual}")
                continue
            if actual.read_text(encoding="utf-8") != expected.read_text(encoding="utf-8"):
                issues.append(f"hash_mismatch: {actual}")

        expected_hooks = tmp_root / ".codex" / "hooks.json"
        generate_hooks_json(manifest, manifest_path, expected_hooks, repo_root=root_dir)
        actual_hooks = root_dir / ".codex" / "hooks.json"
        if not actual_hooks.exists():
            issues.append(f"missing_dest: {actual_hooks}")
        elif actual_hooks.read_text(encoding="utf-8") != expected_hooks.read_text(encoding="utf-8"):
            issues.append(f"hash_mismatch: {actual_hooks}")

    sync = ManifestSync(manifest, root_dir=root_dir)
    for item in sync.check("codex"):
        if item.target.kind == "instruction":
            issues.append(f"{item.reason}: {item.target.dest}")

    # Check for orphan agent markdown files not in manifest
    agents_dir = manifest_path.parent / "agents"
    if agents_dir.exists() and agents_dir.is_dir():
        for prompt_file in sorted(agents_dir.glob("*.md")):
            agent_id = prompt_file.stem
            if agent_id not in manifest.agents:
                issues.append(f"missing_manifest_agent: {agent_id}")

    return issues
