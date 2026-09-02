from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from loop.runtime_materializers.manifest_schema import HarnessManifest, load_manifest


@dataclass
class SyncTarget:
    source: Path
    dest: Path
    kind: Literal["hook", "agent", "instruction"]


@dataclass
class DriftItem:
    target: SyncTarget
    reason: Literal["missing_dest", "hash_mismatch", "missing_source"]


@dataclass
class ApplyResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0


def _file_hash(path: Path) -> str:
    if not path.exists() or path.is_dir():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ManifestSync:
    def __init__(self, manifest: HarnessManifest, root_dir: str | Path = ".") -> None:
        self.manifest = manifest
        self.root_dir = Path(root_dir)

    @classmethod
    def from_file(cls, manifest_path: str | Path, root_dir: str | Path = ".") -> ManifestSync:
        manifest = load_manifest(manifest_path)
        return cls(manifest=manifest, root_dir=root_dir)

    def collect_targets(self, runtime: str) -> list[SyncTarget]:
        targets: list[SyncTarget] = []

        # Collect agent targets
        for _agent_name, agent_cfg in self.manifest.agents.items():
            if runtime in agent_cfg.runtimes:
                rt_info = agent_cfg.runtimes[runtime]
                source_path = self.root_dir / agent_cfg.source
                dest_path = None
                if rt_info.get("materialize") is True and "target" in rt_info:
                    dest_path = self.root_dir / rt_info["target"]
                elif "copy_to" in rt_info:
                    dest_path = self.root_dir / rt_info["copy_to"]

                if dest_path is not None:
                    targets.append(SyncTarget(source=source_path, dest=dest_path, kind="agent"))

        # Collect hook targets
        for _hook_name, hook_cfg in self.manifest.hooks.items():
            if runtime in hook_cfg.runtimes:
                rt_info = hook_cfg.runtimes[runtime]
                source_path = self.root_dir / hook_cfg.source
                dest_path = None
                if "target" in rt_info:
                    dest_path = self.root_dir / rt_info["target"]

                if dest_path is not None:
                    targets.append(SyncTarget(source=source_path, dest=dest_path, kind="hook"))

        # Collect instruction targets
        for _inst_name, inst_cfg in self.manifest.instructions.items():
            if runtime in inst_cfg.runtimes:
                rt_info = inst_cfg.runtimes[runtime]
                source_path = self.root_dir / inst_cfg.source
                dest_path = None
                if "target" in rt_info:
                    dest_path = self.root_dir / rt_info["target"]

                if dest_path is not None:
                    targets.append(SyncTarget(source=source_path, dest=dest_path, kind="instruction"))

        return targets

    def check(self, runtime: str) -> list[DriftItem]:
        drift: list[DriftItem] = []
        targets = self.collect_targets(runtime)
        for target in targets:
            if not target.source.exists():
                drift.append(DriftItem(target=target, reason="missing_source"))
            elif not target.dest.exists():
                drift.append(DriftItem(target=target, reason="missing_dest"))
            else:
                if _file_hash(target.source) != _file_hash(target.dest):
                    drift.append(DriftItem(target=target, reason="hash_mismatch"))
        return drift

    def apply(self, runtime: str, dry_run: bool = False) -> ApplyResult:
        result = ApplyResult()
        targets = self.collect_targets(runtime)

        for target in targets:
            if not target.source.exists():
                result.skipped += 1
                continue

            dest_exists = target.dest.exists()
            if dest_exists and _file_hash(target.source) == _file_hash(target.dest):
                result.skipped += 1
                continue

            if not dry_run:
                target.dest.parent.mkdir(parents=True, exist_ok=True)
                target.dest.write_bytes(target.source.read_bytes())

            if dest_exists:
                result.updated += 1
            else:
                result.created += 1

        return result
