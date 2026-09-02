#!/usr/bin/env python3
"""CLI helpers for agents: validate-step · mark-index-status · sync-index-yaml · flush-checkpoint · status · verify-decompose-creative · reconcile-spec.

Loop orchestration = loop/context_loop.py + ./loop/loop.sh (not this file).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOOP = ROOT / "loop"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(LOOP) not in sys.path:
    sys.path.insert(0, str(LOOP))

from context_loop import status as operational_status  # noqa: E402
from constitution_seed import seed_constitution  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from epic_index import sync_yaml_from_md  # noqa: E402
from epic.traceability import (
    parse_plan_requirements,
    parse_decompose_refs,
    parse_implement_evidence,
    build_report,
    format_report,
)
from epic_lib import (  # noqa: E402
    _decompose_index_path,
    arm_active_context_from_decompose,
    finalize_step,
    halt_epic,
    load_epic_state,
    mark_index_step_status,
    validate_finish_integrity,
)
from epic_yaml import (  # noqa: E402
    load_implement,
    seed_implement_from_decompose,
    validate_decompose_tree,
    validate_shard_yaml_full,
    verify_decompose_creative,
)
from _lib import resolve_cli_cwd  # noqa: E402
from epic.reconcile import run_reconcile_spec
from epic.convergence import run_convergence_checks, format_text, format_json  # noqa: E402


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

    p_val_tree = sub.add_parser(
        "validate-decompose-tree",
        help="lint all sNN|eNN shards listed in decompose index.yaml (DECOMPOSE FINISH gate)",
    )
    p_val_tree.add_argument(
        "--decompose",
        required=True,
        help="decompose dir | index.yaml | index.md | any step shard in that dir",
    )

    p_verify_creative = sub.add_parser(
        "verify-decompose-creative",
        help="advisory plan↔decompose CREATIVE gate (verdict + gaps; exit 0 always)",
    )
    p_verify_creative.add_argument(
        "--decompose",
        required=True,
        help="decompose dir | index.yaml | index.md | any step shard in that dir",
    )

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

    p_arm = sub.add_parser("arm", help="arm activeContext for epic or decompose")
    p_arm.add_argument("--epic-id", default=None, help="epic id")
    p_arm.add_argument("--decompose", default=None, help="decompose dir or index")
    p_arm.add_argument("--role", default="back", help="role slug")

    p_reconcile = sub.add_parser(
        "reconcile-spec",
        help="read-only drift check: default = all tasks.md active epics; optional --plan-id",
    )
    p_reconcile.add_argument(
        "--plan-id",
        default=None,
        help="single epic/plan id (debug); default sweeps tasks.md Status=active",
    )
    p_reconcile.add_argument(
        "--format",
        choices=("text", "json"),
        default="json",
        help="output format",
    )
    p_reconcile.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 when any HIGH finding",
    )

    p_conv = sub.add_parser(
        "analyze-convergence",
        help="read-only cross-artifact convergence check (traceability + reconcile + stale handoff)",
    )
    p_conv.add_argument(
        "--plan-id",
        default=None,
        help="optional single epic plan_id; default sweeps active epics",
    )
    p_conv.add_argument(
        "--format",
        choices=("text", "json"),
        default="json",
        help="output format (text or json)",
    )
    p_conv.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 when any HIGH or CRITICAL finding",
    )
    p_conv.add_argument(
        "--include-git-diff",
        action="store_true",
        help="include git diff cross-checks (stub/reserved)",
    )

    p_vt = sub.add_parser(
        "validate-traceability",
        help="validate epic traceability from plan, decompose, and implement",
    )
    p_vt.add_argument(
        "--epic",
        dest="epic_id",
        required=True,
        help="epic plan_id (e.g. T-HUB-024)",
    )
    p_vt.add_argument("--strict", action="store_true", help="elevate HIGH findings to CRITICAL")
    p_vt.add_argument("--json", action="store_true", help="output JSON format")
    p_vt.add_argument("--tests-dir", default=None, help="path to tests directory for ac markers scan")
    p_vt.add_argument("--ac-strict", action="store_true", help="elevate missing ac marker findings to HIGH")

    p_mb_finish = sub.add_parser("mb-finish", help="mb-finish subcommand dispatcher")
    mb_sub = p_mb_finish.add_subparsers(dest="mb_cmd", required=True)
    p_mb_impl = mb_sub.add_parser("implement", help="finish implement step atomically")
    p_mb_impl.add_argument("--step", required=True, help="step_id (e.g. s01)")
    p_mb_impl.add_argument("--done", default="", help="done summary string")
    p_mb_impl.add_argument("--phase", default="BACK IMPLEMENT", help="phase string")

    p_mb_handoff = mb_sub.add_parser("handoff", help="low-level finish handoff escape hatch")
    p_mb_handoff.add_argument("--role", default="BACK", help="role slug")
    p_mb_handoff.add_argument("--mode", required=True, help="handoff mode (e.g. IMPLEMENT, QA)")
    p_mb_handoff.add_argument("--epic-id", default=None, help="epic id")
    p_mb_handoff.add_argument("--step", default=None, help="step id")
    p_mb_handoff.add_argument("--next-hint", default=None, help="next hint")
    p_mb_handoff.add_argument("--load-now-path", default=None, help="load now item path")
    p_mb_handoff.add_argument("--load-now-desc", default=None, help="load now item description")

    p_mb_qa = mb_sub.add_parser("qa", help="finish qa phase atomically")
    p_mb_qa.add_argument("--step", default="", help="step_id (optional)")
    p_mb_qa.add_argument("--done", default="", help="done summary string")
    p_mb_qa.add_argument("--phase", default="BACK QA", help="phase string")

    p_mb_bugfix = mb_sub.add_parser("bugfix", help="finish bugfix phase atomically")
    p_mb_bugfix.add_argument("--step", default="", help="step_id (optional)")
    p_mb_bugfix.add_argument("--done", default="", help="done summary string")
    p_mb_bugfix.add_argument("--phase", default="BACK BUGFIX", help="phase string")

    p_mb_decompose = mb_sub.add_parser("decompose", help="finish decompose phase atomically")
    p_mb_decompose.add_argument("--step", default="", help="step_id (optional)")
    p_mb_decompose.add_argument("--done", default="", help="done summary string")
    p_mb_decompose.add_argument("--phase", default="BACK DECOMPOSE", help="phase string")

    p_mb_plan = mb_sub.add_parser("plan", help="finish plan phase atomically")
    p_mb_plan.add_argument("--step", default="", help="step_id (optional)")
    p_mb_plan.add_argument("--done", default="", help="done summary string")
    p_mb_plan.add_argument("--phase", default="BACK PLAN", help="phase string")

    p_mb_analyze = mb_sub.add_parser("analyze", help="finish analyze phase atomically")
    p_mb_analyze.add_argument("--step", default="", help="step_id (optional)")
    p_mb_analyze.add_argument("--done", default="", help="done summary string")
    p_mb_analyze.add_argument("--phase", default="BACK ANALYZE", help="phase string")

    p_mb_audit = mb_sub.add_parser("audit", help="finish audit phase atomically")
    p_mb_audit.add_argument("--step", default="", help="step_id (optional)")
    p_mb_audit.add_argument("--done", default="", help="done summary string")
    p_mb_audit.add_argument("--phase", default="BACK AUDIT", help="phase string")

    p_mb_creative = mb_sub.add_parser("creative", help="finish creative phase atomically")
    p_mb_creative.add_argument("--step", default="", help="step_id (optional)")
    p_mb_creative.add_argument("--done", default="", help="done summary string")
    p_mb_creative.add_argument("--phase", default="BACK CREATIVE", help="phase string")

    p_mb_reflect = mb_sub.add_parser("reflect", help="finish reflect phase atomically")
    p_mb_reflect.add_argument("--step", default="", help="step_id (optional)")
    p_mb_reflect.add_argument("--done", default="", help="done summary string")
    p_mb_reflect.add_argument("--phase", default="BACK REFLECT", help="phase string")

    p_mb_load = sub.add_parser("mb-load", help="mb-load subcommand dispatcher")
    mb_load_sub = p_mb_load.add_subparsers(dest="mb_load_cmd", required=True)
    p_mb_load_sess = mb_load_sub.add_parser("session", help="load activeContext session bundle")
    p_mb_load_sess.add_argument("--cwd", default=None, help="product repo root")
    p_mb_load_sess.add_argument("--plan-section", default=None, help="plan section number (optional)")
    p_mb_load_sess.add_argument("--json", action="store_true", help="output JSON format (default True)")

    p_seed_const = sub.add_parser(
        "seed-constitution",
        help="seed memory-bank/constitution.md for product repository",
    )
    p_seed_const.add_argument(
        "--force",
        action="store_true",
        help="overwrite existing memory-bank/constitution.md",
    )
    p_seed_const.add_argument(
        "--product-name",
        default=None,
        help="product name override for placeholders",
    )

    p_formula_render = sub.add_parser(
        "formula-render",
        help="render decompose directory draft from formula",
    )
    p_formula_render.add_argument("--formula", required=True, help="formula id (e.g. hooks-epic)")
    p_formula_render.add_argument("--epic-id", required=True, help="epic id (e.g. T-HUB-999)")
    p_formula_render.add_argument("--slug", required=True, help="descriptive slug")
    p_formula_render.add_argument("--out", default=None, help="output directory path")
    p_formula_render.add_argument("--dry-run", action="store_true", help="print draft to stdout instead of writing files")
    p_formula_render.add_argument("--force", action="store_true", help="overwrite existing files")

    p_formula_list = sub.add_parser(
        "formula-list",
        help="enumerate available decompose formulas",
    )
    p_formula_list.add_argument("--formulas-dir", default=None, help="optional directory override for formula files")

    p_janitor_scan = sub.add_parser(
        "janitor-scan",
        help="read-only entropy audit of memory-bank / runtime artifacts",
    )
    p_janitor_scan.add_argument(
        "--json",
        action="store_true",
        help="emit janitor-report/v1 JSON on stdout",
    )

    p_janitor_gc = sub.add_parser(
        "janitor-gc",
        help="whitelist-only janitor repairs (dry-run by default)",
    )
    p_janitor_gc_mode = p_janitor_gc.add_mutually_exclusive_group()
    p_janitor_gc_mode.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="report planned repairs without writing (default)",
    )
    p_janitor_gc_mode.add_argument(
        "--apply",
        action="store_true",
        help="apply whitelist repairs",
    )

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

    if args.cmd == "validate-decompose-tree":
        errors = validate_decompose_tree(cwd, args.decompose)
        payload = {
            "ok": not errors,
            "decompose": args.decompose,
            "errors": errors,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["ok"] else 2

    if args.cmd == "verify-decompose-creative":
        payload = verify_decompose_creative(cwd, args.decompose)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "mb-finish":
        if args.mb_cmd == "implement":
            from loop.mb_finish.finish_implement import finish_implement_step
            from loop.mb_finish.schemas import MbFinishRequest
            req = MbFinishRequest(
                phase=args.phase,
                step_id=args.step,
                done_summary=args.done,
                cwd=cwd,
            )
            res = finish_implement_step(req)
            out = res.model_dump()
            print(json.dumps(out, ensure_ascii=False, indent=2))
            return 0 if res.ok else 2
        if args.mb_cmd == "handoff":
            from loop.mb_finish.impl import finish_handoff
            from loop.mb_finish.schemas import HandoffBody, LoadNowItem, LoopHandoffMeta
            meta = LoopHandoffMeta(
                role=args.role,
                mode=args.mode,
                epic_id=args.epic_id,
                step_id=args.step,
            )
            load_now = []
            if args.load_now_path and args.load_now_desc:
                load_now.append(LoadNowItem(path=args.load_now_path, description=args.load_now_desc))
            body = HandoffBody(
                mode=args.mode,
                next_hint=args.next_hint,
                epic_id=args.epic_id,
                step_id=args.step,
            )
            res = finish_handoff(meta, load_now, body, cwd=cwd)
            out = res.model_dump()
            print(json.dumps(out, ensure_ascii=False, indent=2))
            return 0 if res.ok else 2
        if args.mb_cmd in ("qa", "bugfix", "decompose", "plan", "analyze", "audit", "creative", "reflect"):
            from loop.mb_finish.impl import (
                finish_analyze,
                finish_audit,
                finish_bugfix,
                finish_creative,
                finish_decompose,
                finish_plan,
                finish_qa,
                finish_reflect,
            )
            from loop.mb_finish.schemas import MbFinishRequest
            req = MbFinishRequest(
                phase=args.phase,
                step_id=args.step,
                done_summary=args.done,
                cwd=cwd,
            )
            if args.mb_cmd == "qa":
                fn = finish_qa
            elif args.mb_cmd == "bugfix":
                fn = finish_bugfix
            elif args.mb_cmd == "decompose":
                fn = finish_decompose
            elif args.mb_cmd == "plan":
                fn = finish_plan
            elif args.mb_cmd == "analyze":
                fn = finish_analyze
            elif args.mb_cmd == "audit":
                fn = finish_audit
            elif args.mb_cmd == "creative":
                fn = finish_creative
            else:
                fn = finish_reflect
            res = fn(req)
            out = res.model_dump()
            print(json.dumps(out, ensure_ascii=False, indent=2))
            return 0 if res.ok else 2

    if args.cmd == "mb-load":
        if args.mb_load_cmd == "session":
            from loop.mb_load.session import load_session
            cmd_cwd = str(resolve_cli_cwd(getattr(args, "cwd", None)))
            plan_sec = int(args.plan_section) if args.plan_section is not None else None
            res = load_session(cwd=cmd_cwd, plan_section=plan_sec)

            # missing-file policy / missing_active_context check:
            # If ok is True but no files were loaded because load_now paths were missing, or ok is False:
            if not res.files and any("missing_file:" in d for d in res.diagnostic_codes):
                res.ok = False

            out = res.model_dump(mode="json")
            print(json.dumps(out, ensure_ascii=False, indent=2))
            return 0 if res.ok else 2

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

    if args.cmd == "seed-constitution":
        res = seed_constitution(
            cwd=cwd,
            force=bool(args.force),
            product_name=args.product_name,
            hub_root=ROOT,
        )
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res.get("ok") else 2

    if args.cmd == "status":
        print(json.dumps(operational_status(cwd), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "halt":
        st = halt_epic(cwd, args.reason)
        print(json.dumps(st, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "arm":
        role = getattr(args, "role", "back") or "back"
        if args.epic_id:
            r = arm_epic(cwd, args.epic_id, role=role)
        elif args.decompose:
            from epic_paths import resolve_arm_epic_target

            resolved = resolve_arm_epic_target(args.decompose, cwd)
            if resolved:
                epic_id, path_role = resolved
                role = getattr(args, "role", None) or path_role or "back"
                r = arm_epic(cwd, epic_id, role=role)
                if r.get("ok"):
                    r = dict(r)
                    r["deprecated"] = "use --epic-id instead of --decompose"
            else:
                r = arm_active_context_from_decompose(cwd, args.decompose)
        else:
            print(json.dumps({"ok": False, "error": "missing --epic-id or --decompose"}, ensure_ascii=False))
            return 2
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r.get("ok") else 2

    if args.cmd == "reconcile-spec":
        payload = run_reconcile_spec(
            cwd,
            plan_id=args.plan_id,
            fmt=args.format,
            strict=bool(args.strict),
        )
        if args.format == "text":
            print(payload.get("text") or "")
        else:
            out = {k: v for k, v in payload.items() if k not in ("text", "format")}
            print(json.dumps(out, ensure_ascii=False, indent=2))
        return int(payload.get("exit_code") or 0)

    if args.cmd == "analyze-convergence":
        report = run_convergence_checks(
            cwd,
            plan_id=args.plan_id,
        )
        if args.format == "text":
            print(format_text(report))
        else:
            print(format_json(report))

        if args.strict and (report.critical_count > 0 or report.high_count > 0):
            return 1
        return 0

    if args.cmd == "validate-traceability":
        plan_id = args.epic_id
        plan_path = Path(cwd) / "memory-bank" / "back" / "plan" / f"plan-{plan_id}.md"
        if not plan_path.is_file():
            print(f"Error: plan file not found: {plan_path}", file=sys.stderr)
            return 2

        decomp_dir = Path(cwd) / "memory-bank" / "back" / "plan" / f"decompose-{plan_id}"
        if not decomp_dir.is_dir():
            print(f"Error: decompose dir not found: {decomp_dir}", file=sys.stderr)
            return 2

        plan_reqs = parse_plan_requirements(plan_path)
        decomp_refs = parse_decompose_refs(decomp_dir)

        impl_dir = Path(cwd) / "memory-bank" / "back" / "implement" / f"implement-{plan_id}"
        impl_ev = parse_implement_evidence(impl_dir) if impl_dir.is_dir() else {}

        tests_dir = Path(cwd) / args.tests_dir if args.tests_dir else None

        report = build_report(
            plan_id,
            plan_reqs,
            decomp_refs,
            impl_ev,
            strict=bool(args.strict),
            tests_dir=tests_dir,
            ac_strict=bool(args.ac_strict),
        )
        formatted = format_report(report, json_mode=bool(args.json))
        print(formatted)

        if report.critical_count > 0:
            return 1
        return 0

    if args.cmd == "formula-render":
        try:
            from formula_render import render_formula
            render_formula(
                formula_id=args.formula,
                epic_id=args.epic_id,
                slug=args.slug,
                out_dir=args.out,
                dry_run=args.dry_run,
                force=args.force,
            )
            return 0
        except ValueError as exc:
            print(f"formula error: {exc}", file=sys.stderr)
            return 2
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    if args.cmd == "formula-list":
        try:
            from formula_render import list_formulas
            formulas_dir = Path(args.formulas_dir) if args.formulas_dir else None
            formulas = list_formulas(formulas_dir=formulas_dir)
            headers = ("ID", "DESCRIPTION", "LEVEL", "STEPS")
            rows = [
                (
                    f.id,
                    f.description or "",
                    f.default_level or "",
                    str(len(f.steps)),
                )
                for f in formulas
            ]
            col_widths = [
                max(len(headers[i]), max((len(r[i]) for r in rows), default=0))
                for i in range(4)
            ]
            header_str = "  ".join(
                headers[i].ljust(col_widths[i]) for i in range(4)
            )
            print(header_str)
            print("  ".join("-" * w for w in col_widths))
            for r in rows:
                print("  ".join(r[i].ljust(col_widths[i]) for i in range(4)))
            return 0
        except ValueError as exc:
            print(f"formula error: {exc}", file=sys.stderr)
            return 2
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    if args.cmd == "janitor-scan":
        from loop.janitor import scan as janitor_scan

        report = janitor_scan(cwd=cwd)
        if args.json:
            print(report.model_dump_json(indent=2))
        else:
            print(
                f"Janitor scan: {report.summary.total_findings} findings "
                f"across {len(report.summary.categories_count)} categories"
            )
            for finding in report.findings[:50]:
                print(f"- [{finding.category}] {finding.target_path}: {finding.description}")
        return 0

    if args.cmd == "janitor-gc":
        from loop.janitor import scan as janitor_scan
        from loop.janitor.gc import GcEngine, GcWhitelistError

        apply = bool(getattr(args, "apply", False))
        dry_run = not apply
        report = janitor_scan(cwd=cwd)
        engine = GcEngine(cwd)
        print(f"Janitor GC ({'apply' if apply else 'dry-run'}): {report.summary.total_findings} findings")
        for finding in report.findings:
            if not finding.actionable:
                continue
            try:
                result = engine.apply_repair(finding, dry_run=dry_run)
            except GcWhitelistError as exc:
                print(f"- skip {finding.target_path}: {exc}")
                continue
            print(
                f"- {result.action} {result.target_path} "
                f"success={result.success} dry_run={result.dry_run}"
            )
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
