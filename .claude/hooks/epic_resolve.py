#!/usr/bin/env python3
"""CLI helpers for agents: validate-step · mark-index-status · sync-index-yaml · flush-checkpoint · status.

Loop orchestration = loop/context_loop.py + ./loop/loop.sh (not this file).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOOP = ROOT / "loop"
if str(LOOP) not in sys.path:
    sys.path.insert(0, str(LOOP))

from context_loop import status as operational_status  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from epic_index import sync_yaml_from_md  # noqa: E402
from epic.core import repair_index_mirror  # noqa: E402
from epic_lib import (  # noqa: E402
    _decompose_index_path,
    finalize_step,
    halt_epic,
    load_epic_state,
    mark_index_step_status,
    validate_finish_integrity,
)
from epic_yaml import (  # noqa: E402
    load_implement,
    seed_implement_from_decompose,
    validate_shard_yaml_full,
)
from _lib import resolve_cli_cwd  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(
        description="epic helpers (not the loop runner)",
    )
    ap.add_argument(
        "--cwd",
        default=None,
        help="product repo root (memory-bank/). Default: $PROJECT_ROOT, else cwd. "
        "Hub cwd + PROJECT_ROOT=product → product (anti-mix).",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_val = sub.add_parser("validate-step", help="lint one shard yaml")
    p_val.add_argument("--path", required=True)
    p_val.add_argument("--verdict", default=None)
    p_val.add_argument("--strict", action="store_true")

    p_finish = sub.add_parser(
        "validate-finish-integrity",
        help="diagnose finish-integrity without mutating the index",
    )
    p_finish.add_argument("--decompose", required=True)
    p_finish.add_argument("--step", default=None)

    p_mark = sub.add_parser(
        "mark-index-status",
        help="set one step status in index.yaml (canon) + mirror index.md",
    )
    p_mark.add_argument("--decompose", required=True)
    p_mark.add_argument("--step", required=True)
    p_mark.add_argument("--status", required=True)
    p_mark.add_argument("--no-checklist", action="store_true")

    p_finalize = sub.add_parser(
        "finalize-step",
        help="atomically require verify PASS, validate implement completion, then sync index + activeContext",
    )
    p_finalize.add_argument(
        "--decompose",
        required=True,
        help="index.md | index.yaml | decompose dir | step shard yaml in that dir",
    )
    p_finalize.add_argument("--step", required=True)
    p_finalize.add_argument("--implement", default=None)
    p_finalize.add_argument("--no-checklist", action="store_true")

    p_repair = sub.add_parser(
        "repair-index-mirror",
        help="sync/rebuild index.md queue from index.yaml (SoT); never mutates yaml",
    )
    p_repair.add_argument("--decompose", required=True)

    p_sync = sub.add_parser(
        "sync-index-yaml",
        help="build/refresh index.yaml from index.md (structure); status from yaml by default",
    )
    p_sync.add_argument("--decompose", required=True)
    p_sync.add_argument(
        "--from-md-status",
        action="store_true",
        help="take statuses from md (bootstrap); default preserves yaml status",
    )

    p_flush = sub.add_parser("flush-checkpoint", help="mark checkpoint done on implement yaml")
    p_flush.add_argument("--path", required=True)
    p_flush.add_argument("--cp", required=True)

    p_seed = sub.add_parser(
        "seed-implement",
        help="create in_progress implement YAML from decompose shard (cp=pending)",
    )
    p_seed.add_argument("--decompose", required=True, help="path to decompose sNN|eNN yaml")
    p_seed.add_argument(
        "--force",
        action="store_true",
        help="re-seed in_progress file (refuse if completed)",
    )

    sub.add_parser("status", help="show .claude/runtime/epic/state.json")

    p_halt = sub.add_parser("halt", help="halt epic runtime state")
    p_halt.add_argument("--reason", required=True)

    args = ap.parse_args()
    cwd = str(resolve_cli_cwd(args.cwd))

    if args.cmd == "validate-step":
        if not isinstance(args.path, (str, Path)):
            print(json.dumps({"ok": False, "error": f"invalid_arg: expected str/Path, got {type(args.path).__name__}"}, ensure_ascii=False))
            return 2
        rel = str(args.path).strip()
        step = Path(cwd) / rel
        errors, warnings = validate_shard_yaml_full(
            step,
            finish=True,
            expected_verdict=args.verdict,
        )
        if args.strict:
            errors = [*errors, *warnings]
        payload = {
            "ok": not errors,
            "path": rel,
            "errors": errors,
            "warnings": warnings,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["ok"] else 2

    if args.cmd == "mark-index-status":
        r = mark_index_step_status(
            cwd,
            args.decompose,
            args.step,
            args.status,
            sync_checklist=not args.no_checklist,
        )
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r.get("ok") else 2

    if args.cmd == "finalize-step":
        r = finalize_step(
            cwd,
            args.decompose,
            args.step,
            implement=args.implement,
            sync_checklist=not args.no_checklist,
        )
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r.get("ok") else 2

    if args.cmd == "repair-index-mirror":
        r = repair_index_mirror(cwd, args.decompose)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r.get("ok") else 2

    if args.cmd == "sync-index-yaml":
        idx = _decompose_index_path(cwd, args.decompose)
        if idx is None or not idx.is_file():
            print(
                json.dumps(
                    {"ok": False, "error": f"missing decompose index: {args.decompose}"},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 2
        r = sync_yaml_from_md(
            idx,
            preserve_yaml_status=not args.from_md_status,
        )
        if not isinstance(r, dict):
            r = {
                "ok": False,
                "error": f"invalid_result: expected dict, got {type(r).__name__}",
            }
        elif r.get("ok"):
            for key in ("path", "source_md"):
                value = r.get(key)
                if not isinstance(value, (str, Path)):
                    r = {
                        "ok": False,
                        "error": (
                            f"invalid_arg: expected str/Path for {key}, "
                            f"got {type(value).__name__}"
                        ),
                    }
                    break
                p = Path(value)
                try:
                    r[key] = str(p.relative_to(cwd))
                except ValueError:
                    pass
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r.get("ok") else 2

    if args.cmd == "flush-checkpoint":
        import yaml as _yaml
        from datetime import datetime, timezone

        rel = args.path.strip()
        path = Path(cwd) / rel
        if not path.is_file():
            print(json.dumps({"ok": False, "error": f"missing {rel}"}, ensure_ascii=False))
            return 2
        try:
            doc = load_implement(path)
        except Exception as exc:
            raw_text = path.read_text(encoding="utf-8")
            try:
                raw = _yaml.safe_load(raw_text)
            except _yaml.YAMLError:
                raw = None
            schema = raw.get("schema") if isinstance(raw, dict) else None
            if schema is None:
                for line in raw_text.splitlines():
                    if line.startswith("schema:"):
                        schema = line.partition(":")[2].strip().strip("'\"")
                        break
            if schema != "epic-implement/v1":
                print(
                    json.dumps(
                        {
                            "ok": False,
                            "path": rel,
                            "error": (
                                "shard is not epic-implement; "
                                "checkpoint tracking is implement-only"
                            ),
                            "skipped": True,
                        },
                        ensure_ascii=False,
                    )
                )
                return 0
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
            return 2
        cp_id = args.cp.strip().lower()
        found = False
        for cp in doc.checkpoints:
            if cp.id == cp_id:
                if cp.status == "done":
                    print(
                        json.dumps(
                            {
                                "ok": False,
                                "error": f"{cp_id} already done",
                            },
                            ensure_ascii=False,
                        )
                    )
                    return 2
                cp.status = "done"
                cp.done_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                found = True
                break
        if not found:
            print(json.dumps({"ok": False, "error": f"unknown checkpoint {cp_id}"}, ensure_ascii=False))
            return 2
        data = doc.model_dump(mode="python", by_alias=True, exclude_none=True)
        path.write_text(
            _yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        print(json.dumps({"ok": True, "path": rel, "cp": cp_id}, ensure_ascii=False))
        return 0

    if args.cmd == "validate-finish-integrity":
        r = validate_finish_integrity(
            cwd,
            decompose=args.decompose,
            step_id=args.step,
            require_verify_pass=True,
        )
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r.get("ok") else 2

    if args.cmd == "seed-implement":
        r = seed_implement_from_decompose(
            cwd, args.decompose, force=bool(args.force)
        )
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r.get("ok") else 2

    if args.cmd == "status":
        print(json.dumps(operational_status(cwd), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "halt":
        st = halt_epic(cwd, args.reason)
        print(json.dumps(st, ensure_ascii=False, indent=2))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
