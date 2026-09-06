from __future__ import annotations

import argparse
import sys
from pathlib import Path

from loop.runtime_materializers.codex_sync import apply_codex, codex_drift_items
from loop.runtime_materializers.manifest_schema import load_manifest
from loop.runtime_materializers.parity import check_codex_parity
from loop.runtime_materializers.sync import ManifestSync


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Harness runtime sync and parity check CLI")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Path to harness manifest.yaml",
    )
    parser.add_argument(
        "--hooks-json",
        type=Path,
        default=None,
        help="Path to .codex/hooks.json for direct parity check",
    )
    parser.add_argument(
        "--runtime",
        choices=["codex", "dsh", "claude", "all"],
        default="codex",
        help="Target runtime or 'all'",
    )
    parser.add_argument(
        "--root-dir",
        type=Path,
        default=None,
        help="Root directory for relative paths (default: manifest parent or CWD)",
    )
    parser.add_argument(
        "--allow-hash-mismatch",
        action="store_true",
        help="Allow hash mismatches without non-zero exit code (default: fail-closed / false)",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="Check for drift / parity without writing")
    group.add_argument("--apply", action="store_true", help="Apply changes and materialize files")

    args = parser.parse_args(argv)

    if args.manifest:
        manifest_path = args.manifest.resolve()
    else:
        repo_root = Path(__file__).resolve().parents[2]
        manifest_path = repo_root / "harness" / "manifest.yaml"

    if args.root_dir:
        root_dir = args.root_dir.resolve()
    else:
        root_dir = (
            manifest_path.parent.parent
            if manifest_path.parent.name == "harness"
            else manifest_path.parent
        )

    if args.hooks_json:
        hooks_json_path = args.hooks_json.resolve()
    else:
        hooks_json_path = root_dir / ".codex" / "hooks.json"

    if args.check:
        total_drift: list[str] = []

        # If direct --hooks-json was provided
        if args.hooks_json:
            parity_issues = check_codex_parity(
                hooks_json_path=hooks_json_path,
                manifest_path=manifest_path if manifest_path.exists() else None,
                root_dir=root_dir,
            )
            if parity_issues:
                total_drift.extend(parity_issues)
                sys.stdout.write(f"Parity issues detected: {len(parity_issues)}\n")
                for issue in parity_issues:
                    sys.stdout.write(f"  - {issue}\n")
        elif manifest_path.exists():
            manifest = load_manifest(manifest_path)
            runtimes = ["codex", "dsh", "claude"] if args.runtime == "all" else [args.runtime]
            for rt in runtimes:
                if rt == "codex":
                    drift = codex_drift_items(manifest, manifest_path=manifest_path, root_dir=root_dir)
                else:
                    sync = ManifestSync(manifest, root_dir=root_dir)
                    drift = [f"{item.reason}: {item.target.dest}" for item in sync.check(rt)]
                if drift:
                    total_drift.extend(drift)
                    sys.stdout.write(f"Drift detected for runtime '{rt}': {len(drift)} items\n")
                    for item in drift:
                        sys.stdout.write(f"  - {item}\n")

        if total_drift:
            if args.allow_hash_mismatch and all("hash_mismatch" in item for item in total_drift):
                sys.stderr.write(
                    f"Warning: Drift/parity issues detected ({len(total_drift)} items total), allowed via flag\n"
                )
                return 0
            sys.stderr.write(f"Drift/parity issues detected ({len(total_drift)} items total)\n")
            return 1
        sys.stdout.write("No drift detected\n")
        return 0

    if args.apply:
        if not manifest_path.exists():
            sys.stderr.write(f"Error: Manifest file not found at {manifest_path}\n")
            return 1

        manifest = load_manifest(manifest_path)
        runtimes = ["codex", "dsh", "claude"] if args.runtime == "all" else [args.runtime]

        for rt in runtimes:
            if rt == "codex":
                res = apply_codex(manifest, manifest_path=manifest_path, root_dir=root_dir)
                sys.stdout.write(
                    "Applied runtime 'codex': "
                    f"{len(res.agents)} agent(s), hooks={res.hooks_json}, "
                    f"instructions created={res.instructions.created} "
                    f"updated={res.instructions.updated} skipped={res.instructions.skipped}\n"
                )
            else:
                sync = ManifestSync(manifest, root_dir=root_dir)
                apply_res = sync.apply(rt, dry_run=False)
                sys.stdout.write(
                    f"Applied runtime '{rt}': {apply_res.created} created, "
                    f"{apply_res.updated} updated, {apply_res.skipped} skipped\n"
                )
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
