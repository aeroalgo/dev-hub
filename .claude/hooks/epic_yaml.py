#!/usr/bin/env python3
"""Epic step YAML — single source for BACK/FRONT (sNN) and INTEG (eNN)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

SCHEMA_EPIC_IMPLEMENT = "epic-implement/v1"
SCHEMA_EPIC_DECOMPOSE = "epic-decompose/v1"
# Read-time alias only (@model_validator before); files must store epic-* schema.
SCHEMA_DECOMPOSE_LEGACY = "integ-decompose/v1"
SCHEMA_IMPLEMENT_LEGACY = "integ-implement/v1"

STEP_S_RE = re.compile(r"(?i)^((?:s)\d{2}-[a-z0-9][a-z0-9-]*)$")
STEP_E_RE = re.compile(r"(?i)^((?:e)\d{2}-[a-z0-9][a-z0-9-]*)$")
_EPIC_MD_ARTIFACT = re.compile(
    r"(?i)(memory-bank/(?:back|front|integration)/(?:"
    r"implement/implement-[^/]+/(?:[sera]\d{2}-[a-z0-9-]+)|"
    r"qa/[^/]+/qa-\d{8}-[a-z0-9-]+|"
    r"(?:refactor|security)/implement/implement-[^/]+/(?:[ra]\d{2}-[a-z0-9-]+)|"
    r"plan/decompose-[^/]+/(?:[se]\d{2}-[a-z0-9-]+)"
    r"))\.md$"
)


class GrepRow(BaseModel):
    back: str = ""
    front: str = ""


class CheckpointSpec(BaseModel):
    id: str
    criterion: str
    verify: str | None = None

    @field_validator("id")
    @classmethod
    def _id_format(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^cp\d+$", v):
            raise ValueError(f"checkpoint id must be cpN, got {v!r}")
        return v


class CheckpointProgress(BaseModel):
    id: str
    criterion: str
    status: Literal["pending", "done"] = "pending"
    done_at: str | None = None
    notes: str | None = None

    @field_validator("id")
    @classmethod
    def _id_format(cls, v: str) -> str:
        return v.strip().lower()


class EpicImplementDoc(BaseModel):
    schema_version: str = Field(alias="schema")
    role: Literal["back", "front", "integ"]
    step_id: str
    plan_id: str
    title: str
    status: Literal["in_progress", "completed"]
    implement_index: str = ""
    date: str
    decompose_ref: str | None = None
    element_ref: str | None = None
    task_id: str | None = None
    level: str | None = None
    skills_used: list[str] = Field(default_factory=list)
    discovery: list[str] = Field(default_factory=list)
    gaps: dict[str, Any] | str = Field(default_factory=lambda: {"status": "none"})
    done: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)
    deletes: list[str] = Field(default_factory=list)
    tests: list[str] = Field(default_factory=list)
    integration_check: list[str] = Field(default_factory=list)
    grep_control: list[GrepRow] = Field(default_factory=list)
    verification_results: list[str] = Field(default_factory=list)
    checkpoints: list[CheckpointProgress] = Field(default_factory=list)
    resume_from: str | None = None

    model_config = {"populate_by_name": True}

    @model_validator(mode="before")
    @classmethod
    def _normalize_schema(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        out = dict(data)
        schema = str(out.get("schema") or "")
        if schema == SCHEMA_IMPLEMENT_LEGACY:
            out["schema"] = SCHEMA_EPIC_IMPLEMENT
            out.setdefault("role", "integ")
        if schema == SCHEMA_EPIC_IMPLEMENT and "role" not in out:
            sid = str(out.get("step_id") or "")
            out["role"] = "integ" if sid.lower().startswith("e") else "back"
        if schema == SCHEMA_IMPLEMENT_LEGACY and "decompose_ref" not in out:
            if out.get("element_ref"):
                out["decompose_ref"] = out["element_ref"]
        return out

    @field_validator("schema_version")
    @classmethod
    def _schema_ok(cls, v: str) -> str:
        if v != SCHEMA_EPIC_IMPLEMENT:
            raise ValueError(f"schema must be {SCHEMA_EPIC_IMPLEMENT!r}")
        return SCHEMA_EPIC_IMPLEMENT


class EpicDecomposeDoc(BaseModel):
    schema_version: str = Field(alias="schema")
    role: Literal["back", "front", "integ"]
    step_id: str
    plan_id: str
    title: str
    next_phase: str
    needs_creative: str | None = None
    goal: str | None = None
    element_id: str | None = None
    ui: dict[str, Any] = Field(default_factory=dict)
    data_need: str | list[str] | None = None
    api_today: list[dict[str, str]] = Field(default_factory=list)
    contract: dict[str, Any] = Field(default_factory=dict)
    db: str | None = None
    back: list[str] = Field(default_factory=list)
    front: list[str] = Field(default_factory=list)
    grep_control: list[GrepRow] = Field(default_factory=list)
    verify: list[str] = Field(default_factory=list)
    tdd: list[str] = Field(default_factory=list)
    checkpoints: list[CheckpointSpec] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    skills: dict[str, Any] = Field(default_factory=dict)
    as_built: list[str] = Field(default_factory=list)
    delta: list[str] = Field(default_factory=list)
    deletes: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}

    @model_validator(mode="before")
    @classmethod
    def _normalize_schema(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        out = dict(data)
        schema = str(out.get("schema") or "")
        if schema == SCHEMA_DECOMPOSE_LEGACY:
            out["schema"] = SCHEMA_EPIC_DECOMPOSE
            out.setdefault("role", "integ")
        if schema == SCHEMA_EPIC_DECOMPOSE and "role" not in out:
            sid = str(out.get("step_id") or "")
            out["role"] = "integ" if sid.lower().startswith("e") else "back"
        return out

    @field_validator("schema_version")
    @classmethod
    def _schema_ok(cls, v: str) -> str:
        if v != SCHEMA_EPIC_DECOMPOSE:
            raise ValueError(f"schema must be {SCHEMA_EPIC_DECOMPOSE!r}")
        return SCHEMA_EPIC_DECOMPOSE


def step_stem(name: str) -> str | None:
    stem = Path(name).stem.lower()
    if STEP_S_RE.match(stem) or STEP_E_RE.match(stem):
        return stem
    return None


def step_prefix(step_id: str) -> str:
    return "e" if step_id.strip().lower().startswith("e") else "s"


def role_from_path(path: str | Path) -> str | None:
    norm = str(path).replace("\\", "/")
    if "/memory-bank/back/" in norm or norm.startswith("memory-bank/back/"):
        return "back"
    if "/memory-bank/front/" in norm or norm.startswith("memory-bank/front/"):
        return "front"
    if "/memory-bank/integration/" in norm or norm.startswith("memory-bank/integration/"):
        return "integ"
    return None


def role_dir(role: str) -> str:
    r = role.strip().lower()
    if r == "integ":
        return "integration"
    return r


def coerce_epic_artifact_path(
    cwd: str | Path,
    artifact: str | None,
) -> tuple[str | None, str | None]:
    if not artifact:
        return artifact, None
    norm = artifact.replace("\\", "/")
    for pat in (_EPIC_MD_ARTIFACT,):
        m = pat.search(norm)
        if m:
            yaml_rel = f"{m.group(1)}.yaml"
            if (Path(cwd) / yaml_rel).is_file():
                return yaml_rel, f"artifact {artifact!r}→{yaml_rel!r} (epic yaml canonical)"
    return artifact, None


def load_yaml_file(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected mapping at root: {path}")
    return data


def load_implement(path: Path) -> EpicImplementDoc:
    return EpicImplementDoc.model_validate(load_yaml_file(path))


def load_decompose(path: Path) -> EpicDecomposeDoc:
    return EpicDecomposeDoc.model_validate(load_yaml_file(path))


def compute_resume_from(checkpoints: list[CheckpointProgress]) -> str | None:
    for cp in checkpoints:
        if cp.status == "pending":
            return cp.id
    return None


def all_checkpoints_done(checkpoints: list[CheckpointProgress]) -> bool:
    if not checkpoints:
        return True
    return all(cp.status == "done" for cp in checkpoints)


def seed_implement_checkpoints(
    decompose: EpicDecomposeDoc,
    existing: list[CheckpointProgress] | None = None,
) -> list[CheckpointProgress]:
    by_id = {cp.id: cp for cp in (existing or [])}
    out: list[CheckpointProgress] = []
    for spec in decompose.checkpoints:
        prev = by_id.get(spec.id)
        if prev:
            out.append(prev)
        else:
            out.append(
                CheckpointProgress(id=spec.id, criterion=spec.criterion, status="pending")
            )
    return out


def _is_hub_epic_id(epic_id: str | None) -> bool:
    return str(epic_id or "").strip().startswith("T-HUB-")


def _resolve_decompose_under_cwd(
    root: Path,
    decompose_rel: str,
) -> tuple[Path, str] | dict[str, Any]:
    rel = decompose_rel.strip().replace("\\", "/")
    if not rel:
        return {"ok": False, "error": "empty decompose path"}
    candidate = Path(rel).expanduser()
    dec_path = candidate.resolve() if candidate.is_absolute() else (root / rel).resolve()
    if not dec_path.is_file():
        return {"ok": False, "error": f"missing {rel}"}
    try:
        dec_ref = dec_path.relative_to(root).as_posix()
    except ValueError:
        return {
            "ok": False,
            "error": f"decompose outside --cwd (anti-mix): {dec_path}",
            "decompose": str(dec_path),
            "cwd": str(root),
        }
    return dec_path, dec_ref


def _validate_seed_implement_anti_mix(
    root: Path,
    *,
    folder_epic: str | None,
    plan_id: str | None,
) -> dict[str, Any] | None:
    from _lib import hub_root

    hub = hub_root().resolve()
    if root == hub:
        return None
    for epic_id in (folder_epic, plan_id):
        if _is_hub_epic_id(epic_id):
            return {
                "ok": False,
                "error": (
                    f"hub epic {epic_id!r} must seed implement in dev-hub memory-bank, "
                    "not product --cwd (anti-mix)"
                ),
                "cwd": str(root),
                "hub_root": str(hub),
            }
    return None


def seed_implement_from_decompose(
    cwd: str | Path,
    decompose_rel: str,
    *,
    force: bool = False,
    date: str | None = None,
) -> dict[str, Any]:
    """Create implement YAML (in_progress, cp=pending) from a decompose shard.

    Idempotent: existing file → skipped unless force (and not completed).
    Filename mirrors decompose basename under implement-<folder-epic-id>/
    (plan_id is an alias hub if it already has the shard).
    """
    from datetime import date as date_cls

    root = Path(cwd).resolve()
    resolved = _resolve_decompose_under_cwd(root, decompose_rel)
    if isinstance(resolved, dict):
        return resolved
    dec_path, dec_ref = resolved
    try:
        dec = load_decompose(dec_path)
    except Exception as exc:
        return {"ok": False, "error": f"invalid decompose: {exc}"}

    from epic_paths import epic_id_from_decompose_path

    folder_epic = epic_id_from_decompose_path(dec_ref) or dec.plan_id
    anti_mix = _validate_seed_implement_anti_mix(
        root,
        folder_epic=folder_epic,
        plan_id=dec.plan_id,
    )
    if anti_mix is not None:
        return anti_mix
    found = None
    impl_dir_rel = ""
    for hub_id in implement_hub_ids(folder_epic, dec.plan_id):
        cand_dir = f"memory-bank/{role_dir(dec.role)}/implement/implement-{hub_id}"
        found = _find_shard_file(cwd, cand_dir, dec.step_id)
        if found is not None:
            impl_dir_rel = cand_dir
            break
    if found is None:
        impl_dir_rel = (
            f"memory-bank/{role_dir(dec.role)}/implement/implement-{folder_epic}"
        )
        impl_dir = root / impl_dir_rel
        out_path = impl_dir / dec_path.name
    else:
        impl_dir = found.parent
        out_path = found
    out_rel = str(out_path.relative_to(root)).replace("\\", "/")

    existing_doc: EpicImplementDoc | None = None
    if out_path.is_file():
        try:
            existing_doc = load_implement(out_path)
        except Exception as exc:
            if not force:
                return {
                    "ok": False,
                    "error": f"existing implement invalid: {exc}",
                    "path": out_rel,
                }
        if existing_doc is not None and existing_doc.status == "completed" and not force:
            return {
                "ok": True,
                "path": out_rel,
                "skipped": True,
                "reason": "already_completed",
            }
        if existing_doc is not None and not force:
            return {
                "ok": True,
                "path": out_rel,
                "skipped": True,
                "reason": "already_exists",
                "status": existing_doc.status,
            }
        if existing_doc is not None and existing_doc.status == "completed" and force:
            return {
                "ok": False,
                "error": "refuse --force on completed implement (would wipe evidence)",
                "path": out_rel,
            }

    checkpoints = seed_implement_checkpoints(
        dec, existing_doc.checkpoints if existing_doc else None
    )
    if not checkpoints and dec.checkpoints:
        checkpoints = seed_implement_checkpoints(dec, None)
    resume = compute_resume_from(checkpoints)
    day = date or date_cls.today().isoformat()
    title = dec.title.strip()
    if "IMPLEMENT" not in title.upper():
        title = f"{dec.step_id} — {title} IMPLEMENT"

    doc = EpicImplementDoc.model_validate(
        {
            "schema": SCHEMA_EPIC_IMPLEMENT,
            "role": dec.role,
            "step_id": dec.step_id,
            "plan_id": dec.plan_id,
            "title": title,
            "status": "in_progress",
            "date": day,
            "decompose_ref": dec_ref,
            "element_ref": dec_ref if dec.role == "integ" else None,
            "checkpoints": [cp.model_dump(mode="python") for cp in checkpoints],
            "resume_from": resume,
            "gaps": {"status": "none"} if dec.role == "integ" else {"status": "none"},
            "done": [],
            "files": list(dec.context.get("files") or []) if isinstance(dec.context, dict) else [],
            "deletes": list(dec.deletes or []),
            "tests": [],
            "integration_check": [],
            "grep_control": [
                g.model_dump(mode="python") for g in dec.grep_control
            ]
            if dec.role == "integ"
            else [],
            "verification_results": [],
            "skills_used": [],
        }
    )
    impl_dir.mkdir(parents=True, exist_ok=True)
    payload = doc.model_dump(mode="python", by_alias=True, exclude_none=True)
    if not payload.get("implement_index"):
        payload.pop("implement_index", None)
    out_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return {
        "ok": True,
        "path": out_rel,
        "skipped": False,
        "status": "in_progress",
        "checkpoints": len(checkpoints),
        "resume_from": resume,
    }


def _find_shard_file(cwd: str | Path, directory: str, step_id: str) -> Path | None:
    root = Path(cwd)
    d = root / directory
    if not d.is_dir():
        return None
    sid = step_id.strip().lower()
    prefix = "e" if sid.startswith("e") else "s"
    m = re.match(rf"^({prefix}\d{{2}})(?:-.*)?$", sid)
    short = m.group(1) if m else sid
    for ext in (".yaml", ".yml"):
        exact = d / f"{sid}{ext}"
        if exact.is_file():
            return exact
        if m:
            matches = sorted(d.glob(f"{short}-*{ext}"))
            if matches:
                return matches[0]
        exact_short = d / f"{short}{ext}"
        if exact_short.is_file():
            return exact_short
    return None


def implement_hub_ids(epic_id: str, plan_id: str | None = None) -> list[str]:
    """Decompose-folder epic id first; shard/index plan_id as alias hub."""
    ids: list[str] = []
    for value in (epic_id, plan_id):
        text = str(value or "").strip()
        if text and text not in ids:
            ids.append(text)
    return ids


def resolve_implement_path(
    cwd: str | Path,
    role: str,
    epic_id: str,
    step_id: str,
    *,
    plan_id: str | None = None,
) -> str:
    """Resolve implement yaml. Prefer folder epic hub, then plan_id alias hub."""
    for hub_id in implement_hub_ids(epic_id, plan_id):
        rel_dir = f"memory-bank/{role_dir(role)}/implement/implement-{hub_id}"
        found = _find_shard_file(cwd, rel_dir, step_id)
        if found:
            return str(found.relative_to(Path(cwd))).replace("\\", "/")
    stem = step_id.strip().lower()
    p = (
        Path(cwd)
        / f"memory-bank/{role_dir(role)}/implement/implement-{epic_id}"
        / f"{stem}.yaml"
    )
    return str(p.relative_to(Path(cwd))).replace("\\", "/")


def resolve_decompose_path(
    cwd: str | Path,
    role: str,
    epic_id: str,
    step_id: str,
) -> str:
    sub = "plan" if role != "integ" else "plan"
    rel_dir = f"memory-bank/{role_dir(role)}/{sub}/decompose-{epic_id}"
    found = _find_shard_file(cwd, rel_dir, step_id)
    if found:
        return str(found.relative_to(Path(cwd))).replace("\\", "/")
    stem = step_id.strip().lower()
    p = Path(cwd) / rel_dir / f"{stem}.yaml"
    return str(p.relative_to(Path(cwd))).replace("\\", "/")


def find_implement_doc(cwd: str | Path, rel_or_abs: str) -> EpicImplementDoc | None:
    root = Path(cwd)
    p = Path(rel_or_abs)
    if not p.is_absolute():
        p = root / p
    if p.suffix.lower() not in {".yaml", ".yml"} or not p.is_file():
        return None
    try:
        return load_implement(p)
    except Exception:
        return None


def _gaps_ok(gaps: dict[str, Any] | str) -> bool:
    if isinstance(gaps, str):
        return gaps.strip().lower() in {"нет", "none", "no"}
    return str(gaps.get("status", "")).lower() in {"none", "no", "closed"}


def validate_implement_yaml(path: Path, *, finish: bool = True) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"missing implement file: {path}"]
    try:
        doc = load_implement(path)
    except Exception as exc:
        return [f"invalid epic-implement yaml: {exc}"]

    if doc.role == "integ":
        if not doc.grep_control:
            errors.append("grep_control: at least one row required")
        if not doc.verification_results:
            errors.append("verification_results: at least one entry required")
        if not _gaps_ok(doc.gaps):
            errors.append("gaps: status must be none/нет or {status: none}")
    else:
        if finish and not doc.done:
            errors.append("done: at least one entry required on FINISH")
        if finish and not doc.files:
            errors.append("files: at least one entry required on FINISH")
        if finish and not doc.integration_check:
            errors.append("integration_check: at least one entry required on FINISH")

    if doc.role == "integ" and not doc.checkpoints:
        errors.append("checkpoints: at least one checkpoint required for integ")

    if finish:
        if doc.status not in {"in_progress", "completed"}:
            errors.append("status must be in_progress or completed on FINISH")
        for cp in doc.checkpoints:
            if cp.status != "done":
                errors.append(f"checkpoint {cp.id} must be done on FINISH")
        try:
            from tests_format import validate_tests_entries

            errors.extend(
                validate_tests_entries(doc.tests, finish=True, require_executable=True)
            )
        except Exception as exc:
            errors.append(f"tests: validate failed ({exc})")

    return errors


# Template markers → tdd/out_of_scope WARN (copy-paste placeholders, not bugs).
_TEMPLATE_MARKERS = (
    "<placeholder",
    "todo:",
    "tbd",
    "lorem ipsum",
    "example.com",
    "…",
)


def _entry_has_template(entry: str) -> bool:
    low = (entry or "").strip().lower()
    return any(m in low for m in _TEMPLATE_MARKERS)


def _has_em_dash(cmd: str) -> bool:
    return bool(re.search(r"[—–]", cmd or ""))


def validate_decompose_full(
    path: Path,
) -> tuple[list[str], list[str]]:
    """Decompose v1 validation with FAIL errors + WARN warnings.

    FAIL (halt): D1 dup global verify, D2 dup cp verify, D7 em-dash,
    missing required, non-runnable/placeholder verify.
    WARN (lint, →FAIL under --strict): D3 cp==global verify,
    D4 context.files↔delta mismatch, D5 template tdd/out_of_scope,
    D6 deletes without rg/import-audit cp (or deletes basename missing from delta).
    """
    errors: list[str] = []
    warnings: list[str] = []
    if not path.is_file():
        return [f"missing decompose file: {path}"], []
    try:
        doc = load_decompose(path)
    except Exception as exc:
        return [f"invalid epic-decompose yaml: {exc}"], []

    if not (doc.goal or "").strip():
        errors.append("goal: required (1–2 lines outcome)")
    if not doc.delta:
        errors.append("delta: at least one entry required")
    if not doc.out_of_scope:
        warnings.append("out_of_scope: empty (optional, but prefer 1–2 lines)")

    if not doc.checkpoints:
        errors.append("checkpoints: at least one checkpoint required")
    ids = [cp.id for cp in doc.checkpoints]
    if len(ids) != len(set(ids)):
        errors.append("checkpoints: duplicate id")

    verify_hints = (
        ".venv/bin/pytest ",
        "cd frontend && npm ",  # канон
        "npm --prefix frontend ",  # runner переписывает под капотом
        "npm exec vitest",
        "npm test",
        "npx vitest",
        "npx playwright",
        "npm exec playwright",
        "rg ",
    )

    # D1 — global verify[] duplicates + D7 em-dash.
    seen_global: set[str] = set()
    for i, raw in enumerate(doc.verify):
        v = (raw or "").strip()
        if not v:
            continue
        if _has_em_dash(v):
            errors.append(
                f"verify[{i}]: em-dash forbidden (strip trailer) in {v!r}"
            )
        norm = re.sub(r"\s+", " ", v.lower())
        if norm in seen_global:
            errors.append(f"verify[{i}]: duplicates another global verify — {v!r}")
        seen_global.add(norm)

    global_norm = {re.sub(r"\s+", " ", (v or "").strip().lower()) for v in doc.verify}

    # D2/D3/D7 — checkpoints.verify.
    seen_cp: set[str] = set()
    cp_verifies: list[str] = []
    for cp in doc.checkpoints:
        v = (cp.verify or "").strip()
        if not v:
            errors.append(f"checkpoint {cp.id}: verify required")
            continue
        cp_verifies.append(v)
        if not any(h in v for h in verify_hints):
            errors.append(
                f"checkpoint {cp.id}: verify must be runnable "
                f"(pytest/vitest/playwright/rg), got {v!r}"
            )
        if re.search(r"e\d+:(?:v|cp)\d+", v):
            errors.append(
                f"checkpoint {cp.id}: verify is placeholder marker {v!r} — "
                "replace with real pytest/vitest/rg command"
            )
        # D7 em-dash in cp.verify.
        if _has_em_dash(v):
            errors.append(
                f"checkpoint {cp.id}: em-dash forbidden in verify {v!r}"
            )
        norm = re.sub(r"\s+", " ", v.lower())
        if norm in seen_cp:
            errors.append(
                f"checkpoint {cp.id}: verify duplicates another cp — "
                "each cp needs distinct verify"
            )
        seen_cp.add(norm)
        # D3 — cp.verify == a global verify verbatim (cp adds no value).
        if global_norm and norm in global_norm:
            warnings.append(
                f"checkpoint {cp.id}: verify identical to a global verify — "
                "checkpoint adds no distinct check"
            )

    # D4 — context.files ↔ delta cross-reference consistency.
    ctx = doc.context or {}
    ctx_files_raw = ctx.get("files")
    ctx_files: list[str] = []
    if isinstance(ctx_files_raw, list):
        ctx_files = [str(x) for x in ctx_files_raw if str(x).strip()]
    elif isinstance(ctx_files_raw, str) and ctx_files_raw.strip():
        ctx_files = [ctx_files_raw.strip()]
    delta_blob = " ".join(str(x) for x in doc.delta).lower()
    if ctx_files:
        unmentioned = [
            f for f in ctx_files if Path(f).name.lower() not in delta_blob
        ]
        if unmentioned:
            warnings.append(
                "context.files not referenced in any delta: "
                + ", ".join(unmentioned[:5])
            )

    # D5 — template markers in tdd / out_of_scope (copy-paste, not blockers).
    for field, entries in (("tdd", doc.tdd), ("out_of_scope", doc.out_of_scope)):
        templ = [str(e) for e in entries if _entry_has_template(str(e))]
        if templ:
            warnings.append(
                f"{field}: template/placeholder markers present "
                f"({len(templ)} entry/ies) — replace with real content"
            )

    # D6 — deletes: require rg/import-audit cp + mention in delta.
    deletes = [str(x).strip() for x in (doc.deletes or []) if str(x).strip()]
    if deletes:
        verify_blob = " ".join(cp_verifies + [str(v) for v in doc.verify]).lower()
        has_delete_audit = (
            "rg " in verify_blob
            or "import-audit" in verify_blob
            or "import audit" in verify_blob
        )
        if not has_delete_audit:
            warnings.append(
                "deletes: non-empty but no checkpoint/global verify with "
                "`rg`/import-audit — add cp that old path/symbol has no callers"
            )
        unmentioned_del = [
            d for d in deletes if Path(d).name.lower() not in delta_blob
            and d.lower() not in delta_blob
        ]
        if unmentioned_del:
            warnings.append(
                "deletes not referenced in any delta: "
                + ", ".join(unmentioned_del[:5])
            )

    return errors, warnings


def validate_decompose_yaml(path: Path) -> list[str]:
    """Back-compat errors-only (FAIL) view of validate_decompose_full."""
    errors, _warnings = validate_decompose_full(path)
    return errors


def validate_shard_yaml(path: Path, *, finish: bool = True, expected_verdict: str | None = None) -> list[str]:
    """Errors-only (FAIL) validation — back-compat for all consumers."""
    errs, _warns = validate_shard_yaml_full(
        path, finish=finish, expected_verdict=expected_verdict
    )
    return errs


def validate_shard_yaml_full(
    path: Path,
    *,
    finish: bool = True,
    expected_verdict: str | None = None,
) -> tuple[list[str], list[str]]:
    """Unified shard validator → (errors, warnings).

    errors halt the loop (FAIL). warnings are lint (→FAIL under --strict).
    Decompose yields warnings (D3/D4/D5); other kinds return errors only.
    """
    from epic_shard_extra import detect_shard_kind, validate_epic_shard

    kind = detect_shard_kind(path)
    if kind == "decompose":
        return validate_decompose_full(path)
    if kind:
        return validate_epic_shard(path, finish=finish, expected_verdict=expected_verdict), []
    norm = str(path).replace("\\", "/")
    if "/implement/implement-" in norm:
        return validate_implement_yaml(path, finish=finish), []
    if "/decompose-" in norm and "/plan/" in norm:
        return validate_decompose_full(path)
    name = path.name.lower()
    if name.startswith("e") or name.startswith("s"):
        if path.suffix.lower() in {".yaml", ".yml"}:
            data = load_yaml_file(path)
            schema = str(data.get("schema") or "")
            if "implement" in schema or "decompose_ref" in data or "done" in data:
                return validate_implement_yaml(path, finish=finish), []
            return validate_decompose_full(path)
    return [f"unknown epic yaml path: {path}"], []


def build_step_context_payload(
    dec: EpicDecomposeDoc,
    impl: EpicImplementDoc | None = None,
) -> dict[str, Any]:
    """Lean JSON payload for IMPLEMENT prompt — facts from pydantic, not prose."""
    status_by = {cp.id: cp.status for cp in (impl.checkpoints if impl else [])}
    resume = None
    if impl is not None:
        resume = impl.resume_from or compute_resume_from(impl.checkpoints)

    payload = dec.model_dump(
        mode="json",
        include={
            "role",
            "step_id",
            "plan_id",
            "title",
            "goal",
            "as_built",
            "delta",
            "deletes",
            "out_of_scope",
            "contract",
            "grep_control",
        },
    )
    for key in ("as_built", "delta", "deletes", "out_of_scope", "contract", "grep_control", "goal"):
        val = payload.get(key)
        if val in (None, [], {}, ""):
            payload.pop(key, None)

    checkpoints: list[dict[str, Any]] = []
    for spec in dec.checkpoints:
        if impl is not None and spec.id not in status_by:
            raise ValueError(
                f"implement checkpoint missing for decompose {spec.id!r} "
                f"(step_id={dec.step_id})"
            )
        if not (spec.verify or "").strip():
            raise ValueError(
                f"decompose {dec.step_id} checkpoint {spec.id}: verify обязателен"
            )
        checkpoints.append(
            {
                "id": spec.id,
                "criterion": spec.criterion,
                "verify": spec.verify,
                "status": status_by[spec.id] if impl is not None else "pending",
            }
        )
    if not checkpoints:
        raise ValueError(f"decompose {dec.step_id}: checkpoints[] пуст")
    payload["checkpoints"] = checkpoints

    if resume:
        payload["resume_from"] = resume
    if impl is not None:
        payload["implement_status"] = impl.status
    return payload


def step_context_prompt_lines(
    dec: EpicDecomposeDoc,
    impl: EpicImplementDoc | None = None,
    *,
    shard_rel: str | None = None,
) -> list[str]:
    """Short pointer to work shard — full goal/delta/cp stay on disk."""
    payload = build_step_context_payload(dec, impl)
    pending = [c["id"] for c in payload["checkpoints"] if c.get("status") == "pending"]
    done = [c["id"] for c in payload["checkpoints"] if c.get("status") == "done"]
    lines = [
        "",
        "## step",
        f"- step_id: `{dec.step_id}`",
        f"- role: `{dec.role}`",
        f"- plan_id: `{dec.plan_id}`",
    ]
    if shard_rel:
        lines.append(f"- shard: `{shard_rel}`")
    if payload.get("implement_status"):
        lines.append(f"- implement_status: `{payload['implement_status']}`")
    if payload.get("resume_from"):
        lines.append(f"- resume_from: `{payload['resume_from']}`")
    if pending:
        lines.append(f"- pending: {', '.join(pending)}")
    if done:
        lines.append(f"- done: {', '.join(done)}")
    lines.append("Прочитай shard (goal/delta/checkpoints/verify).")
    return lines


def checkpoint_prompt_lines(doc: EpicImplementDoc) -> list[str]:
    """Legacy alias — prefer step_context_prompt_lines with implement doc."""
    resume = doc.resume_from or compute_resume_from(doc.checkpoints)
    pending = [cp.id for cp in doc.checkpoints if cp.status == "pending"]
    done = [cp.id for cp in doc.checkpoints if cp.status == "done"]
    lines = ["", "## checkpoints"]
    if resume and doc.status != "completed":
        lines.append(f"- resume_from: `{resume}`")
    if pending:
        lines.append(f"- pending: {', '.join(pending)}")
    if done:
        lines.append(f"- done: {', '.join(done)}")
    return lines


def seed_checkpoint_bootstrap_lines(decompose_rel: str) -> list[str]:
    """When implement YAML missing — instruct seed before work/flush."""
    return [
        "",
        "## checkpoints",
        "Implement YAML нет. Сразу:"
        f" `python3 .claude/hooks/epic_resolve.py seed-implement --decompose {decompose_rel}`",
    ]


def format_spec_lines(*, role: str) -> list[str]:
    r = role.strip().lower()
    base = [
        f"FINISH artifact: `.cursor/templates/implement/epic-step.yaml` ({r} YAML):",
        f"schema: {SCHEMA_EPIC_IMPLEMENT}",
        f"role: {r}",
        "обязательные: step_id, plan_id, title, status, date, decompose_ref",
        "checkpoints: [{id, criterion, status: pending|done, done_at?, notes?}, ...]",
        "до finalize-step: status=in_progress + все cp done + done/files/tests",
        "status=completed пишет только finalize-step (вместе с index)",
        "Самопроверка: `python3 .claude/hooks/epic_resolve.py validate-step --path <shard.yaml>`",
        "",
        "tests: format (HARD) — loop after assert запускает эти строки как shell:",
        "  OK:   - '`.venv/bin/pytest path -q` — PASS'",
        "  OK:   - '`cd frontend && npm exec vitest -- run src/x.test.tsx`'",
        "  OK:   - '`cd frontend && npm exec tsc -- --noEmit`'",
        "  OK:   - '`npm --prefix frontend exec vitest -- run src/x.test.tsx`'  (runner перепишет)",
        "  FAIL: - 'npm exec tsc -- --noEmit — passed'  (prose без backticks)",
        "  FAIL: - {command: …, result: …}  (mapping запрещён)",
        "  result/PASS/counts → verification_results (не в tests).",
        "  ≥1 executable: .venv/bin/pytest | cd frontend && npm exec vitest|tsc …",
        "  Bash: cwd=repo root; одноразовый `cd frontend && cmd` разрешён. "
        "FORBIDDEN: working_directory=frontend.",
    ]
    if r == "integ":
        base.extend(
            [
                "integ also: element_ref, grep_control, verification_results, gaps",
                "integ FINISH: tests (≥1 executable) обязательны",
            ]
        )
    else:
        base.extend(
            [
                f"{r}: done, files, tests, integration_check — обязательны на FINISH",
                "task_id, level — recommended",
            ]
        )
    return base


def write_implement_doc(path: Path, doc: EpicImplementDoc) -> None:
    payload = doc.model_dump(mode="python", by_alias=True, exclude_none=True)
    if not payload.get("implement_index"):
        payload.pop("implement_index", None)
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def set_implement_status(path: Path, status: str) -> dict[str, Any]:
    status_l = (status or "").strip().lower()
    if status_l not in {"in_progress", "completed"}:
        return {
            "ok": False,
            "error": f"status must be in_progress|completed, got {status!r}",
        }
    try:
        doc = load_implement(path)
    except Exception as exc:
        return {"ok": False, "error": f"invalid implement: {exc}"}
    previous = doc.status
    if previous == status_l:
        return {
            "ok": True,
            "changed": False,
            "previous": previous,
            "status": status_l,
            "path": str(path),
        }
    updated = doc.model_copy(update={"status": status_l})
    write_implement_doc(path, updated)
    return {
        "ok": True,
        "changed": True,
        "previous": previous,
        "status": status_l,
        "path": str(path),
    }


def implement_ready_for_finalize_doc(doc: EpicImplementDoc) -> list[str]:
    errors: list[str] = []
    if not all_checkpoints_done(doc.checkpoints):
        pending = [cp.id for cp in doc.checkpoints if cp.status != "done"]
        errors.append(f"checkpoints not done: {', '.join(pending) or '(unknown)'}")
    if doc.role == "integ":
        if not doc.grep_control:
            errors.append("grep_control: at least one row required")
        if not doc.verification_results:
            errors.append("verification_results: at least one entry required")
        if not _gaps_ok(doc.gaps):
            errors.append("gaps: status must be none/нет or {status: none}")
        if not doc.checkpoints:
            errors.append("checkpoints: at least one checkpoint required for integ")
    else:
        if not doc.done:
            errors.append("done: at least one entry required")
        if not doc.files:
            errors.append("files: at least one entry required")
        if not doc.integration_check:
            errors.append("integration_check: at least one entry required")
    try:
        from tests_format import validate_tests_entries

        errors.extend(
            validate_tests_entries(doc.tests, finish=True, require_executable=True)
        )
    except Exception as exc:
        errors.append(f"tests: validate failed ({exc})")
    return errors


def implement_ready_for_finalize(cwd: str | Path, rel: str) -> bool:
    p = Path(cwd) / rel
    if not p.is_file() or p.suffix.lower() not in {".yaml", ".yml"}:
        return False
    try:
        doc = load_implement(p)
        return not implement_ready_for_finalize_doc(doc)
    except Exception:
        return False


def implement_completed(cwd: str | Path, rel: str) -> bool:
    p = Path(cwd) / rel
    if not p.is_file() or p.suffix.lower() not in {".yaml", ".yml"}:
        return False
    try:
        doc = load_implement(p)
        return doc.status == "completed" and all_checkpoints_done(doc.checkpoints)
    except Exception:
        return False
