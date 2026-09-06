"""Session loader core for loop/mb_load."""

import hashlib
import re
from pathlib import Path

from harness.hooks.epic.core import (
    extract_load_now,
    fingerprint_context,
    read_active_context,
    validate_active_context_shape,
)
from loop.mb_finish.schemas import LoadNowItem, LoopHandoffMeta
from loop.mb_load.plan_section import load_plan_section
from loop.mb_load.resolver import resolve_bundle_paths
from loop.mb_load.schemas import MbLoadFile, MbLoadRequest, MbLoadResult
from loop.schemas.active_context import parse_handoff_meta


def _parse_load_now_with_optional(text: str) -> dict[str, bool]:
    """Parse load_now entries from activeContext text and return mapping of path -> is_optional.

    Unmarked entries default to required (is_optional = False) for fail-closed behavior.
    Entries marked with (optional), [optional], or optional=true are parsed as is_optional = True.
    """
    m = re.search(r"(?im)^##\s*load_now\s*$", text)
    if not m:
        return {}
    rest = text[m.end() :]
    nxt = re.search(r"(?im)^##\s+", rest)
    body = rest[: nxt.start()] if nxt else rest

    mapping: dict[str, bool] = {}
    for raw_path in extract_load_now(text):
        mapping[raw_path] = False

    for line in body.splitlines():
        line_str = line.strip()
        is_opt = bool(re.search(r"(?i)\boptional\b", line_str))
        if not is_opt:
            continue
        for p in list(mapping.keys()):
            if p in line_str or Path(p).name in line_str:
                mapping[p] = True
    return mapping


def load_session(
    cwd: str | Path = ".",
    plan_section: int | str | None = None,
    max_file_bytes: int = 256 * 1024,
    optional_paths: list[str] | None = None,
) -> MbLoadResult:
    """Reads activeContext.md, validates shape, loads files with size cap, and returns MbLoadResult."""
    cwd_path = Path(cwd).resolve()
    act_text = read_active_context(cwd_path)

    if not act_text:
        return MbLoadResult(
            ok=False,
            status="incomplete",
            diagnostic_codes=["missing_active_context"],
            shape_errors=["activeContext.md does not exist or is empty"],
        )

    shape_errors = validate_active_context_shape(act_text)
    if shape_errors:
        return MbLoadResult(
            ok=False,
            status="incomplete",
            diagnostic_codes=shape_errors,
            shape_errors=shape_errors,
        )

    meta = parse_handoff_meta(act_text)
    meta_model = LoopHandoffMeta.model_validate(meta.model_dump()) if meta else None

    raw_paths = extract_load_now(act_text)
    mode = meta_model.mode if meta_model else None
    step_id = meta_model.step_id if meta_model else None

    resolved_bundle = resolve_bundle_paths(
        cwd=cwd_path,
        mode=mode,
        step_id=step_id,
        load_now_paths=raw_paths,
        epic_id=meta_model.epic_id if meta_model else None,
        role=meta_model.role if meta_model else None,
    )

    load_now_opt_map = _parse_load_now_with_optional(act_text)
    explicit_opt_set = set(optional_paths or [])

    def is_path_optional(p_str: str) -> bool:
        if p_str in explicit_opt_set:
            return True
        return load_now_opt_map.get(p_str, False)

    load_now_items: list[LoadNowItem] = []
    files: list[MbLoadFile] = []
    forbidden_skipped: list[str] = list(resolved_bundle.forbidden_skipped)
    diagnostic_codes: list[str] = list(resolved_bundle.diagnostics)
    required_missing: list[str] = []
    optional_missing: list[str] = []
    read_errors_on_required: list[str] = []

    for path_str in resolved_bundle.resolved_paths:
        file_path = cwd_path / path_str
        opt = is_path_optional(path_str)
        if not file_path.is_file():
            diagnostic_codes.append(f"missing_file:{path_str}")
            if opt:
                optional_missing.append(path_str)
            else:
                required_missing.append(path_str)
            continue

        try:
            raw_bytes = file_path.read_bytes()
            size = len(raw_bytes)
            truncated = False
            if size > max_file_bytes:
                raw_bytes = raw_bytes[:max_file_bytes]
                truncated = True
            content_str = raw_bytes.decode("utf-8", errors="replace")
            sha = hashlib.sha256(raw_bytes).hexdigest()

            files.append(
                MbLoadFile(
                    path=path_str,
                    content=content_str,
                    size_bytes=size,
                    sha256=sha,
                    truncated=truncated,
                )
            )
            load_now_items.append(
                LoadNowItem(path=path_str, description=path_str, optional=opt)
            )
        except Exception:
            diagnostic_codes.append(f"read_error:{path_str}")
            if opt:
                optional_missing.append(path_str)
            else:
                read_errors_on_required.append(path_str)

    plan_section_ok = True
    if plan_section is not None:
        sec_content, sec_err = load_plan_section(cwd=cwd_path, section=plan_section)
        if sec_err:
            diagnostic_codes.append(sec_err)
            plan_section_ok = False
        elif sec_content:
            syn_path = f"plan_section:{plan_section}"
            sec_bytes = sec_content.encode("utf-8")
            files.append(
                MbLoadFile(
                    path=syn_path,
                    content=sec_content,
                    size_bytes=len(sec_bytes),
                    sha256=hashlib.sha256(sec_bytes).hexdigest(),
                    truncated=False,
                )
            )
            load_now_items.append(LoadNowItem(path=syn_path, description=f"Plan section {plan_section}"))

    derived_ok = (
        not required_missing
        and not read_errors_on_required
        and plan_section_ok
    )
    status_str: Literal["complete", "incomplete"] = "complete" if derived_ok else "incomplete"

    fp = fingerprint_context(act_text)

    return MbLoadResult(
        ok=derived_ok,
        status=status_str,
        diagnostic_codes=diagnostic_codes,
        shape_errors=[],
        meta=meta_model,
        load_now=load_now_items,
        files=files,
        required_missing=required_missing,
        optional_missing=optional_missing,
        forbidden_skipped=forbidden_skipped,
        fingerprint=fp,
    )
