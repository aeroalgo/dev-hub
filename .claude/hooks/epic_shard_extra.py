"""Epic YAML schemas: QA, REFACTOR, SECURITY (+ shard router)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from epic_yaml import CheckpointProgress, SCHEMA_EPIC_DECOMPOSE, load_yaml_file

SCHEMA_EPIC_QA = "epic-qa/v1"
SCHEMA_EPIC_REFACTOR = "epic-refactor/v1"
SCHEMA_EPIC_SECURITY = "epic-security/v1"

STEP_R_RE = re.compile(r"(?i)^((?:r)\d{2}-[a-z0-9][a-z0-9-]*)$")
STEP_A_RE = re.compile(r"(?i)^((?:a)\d{2}-[a-z0-9][a-z0-9-]*)$")
QA_STEM_RE = re.compile(r"(?i)^qa-\d{8}-[a-z0-9][a-z0-9-]*$")


class FixPlanRow(BaseModel):
    issue: str
    command: str
    subject: str
    scope: str = ""
    verify: str = ""


class IssueRow(BaseModel):
    id: str = ""
    sev: str = ""
    file: str = ""
    msg: str = ""


class EpicQaDoc(BaseModel):
    schema_version: str = Field(alias="schema")
    role: Literal["back", "front", "integ"]
    task_id: str | None = None
    plan_id: str | None = None
    epic_id: str | None = None
    date: str
    reviewer: str
    verdict: Literal["pass", "fail", "blocked"]
    scope: list[str] = Field(default_factory=list)
    checks: list[str] = Field(default_factory=list)
    issues: list[IssueRow] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    fix_plan: list[FixPlanRow] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    suite: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}

    @field_validator("schema_version")
    @classmethod
    def _schema_ok(cls, v: str) -> str:
        if v != SCHEMA_EPIC_QA:
            raise ValueError(f"schema must be {SCHEMA_EPIC_QA!r}")
        return SCHEMA_EPIC_QA


class EpicRefactorDoc(BaseModel):
    schema_version: str = Field(alias="schema")
    role: Literal["back", "front", "integ"]
    step_id: str
    plan_id: str
    title: str
    status: Literal["in_progress", "completed"]
    date: str
    behavior_freeze: str
    decompose_ref: str | None = None
    done: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)
    tests: list[str] = Field(default_factory=list)
    checkpoints: list[CheckpointProgress] = Field(default_factory=list)
    resume_from: str | None = None

    model_config = {"populate_by_name": True}

    @field_validator("schema_version")
    @classmethod
    def _schema_ok(cls, v: str) -> str:
        if v != SCHEMA_EPIC_REFACTOR:
            raise ValueError(f"schema must be {SCHEMA_EPIC_REFACTOR!r}")
        return SCHEMA_EPIC_REFACTOR


class FindingRow(BaseModel):
    id: str
    severity: Literal["critical", "high", "medium", "low", "info"]
    path: str
    note: str

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        return v.strip()


class EpicSecurityDoc(BaseModel):
    schema_version: str = Field(alias="schema")
    role: Literal["back", "front", "integ"]
    step_id: str
    plan_id: str
    title: str
    status: Literal["in_progress", "completed"]
    date: str
    audit_surface: str
    scope_paths: list[str] = Field(default_factory=list)
    threats: list[str] = Field(default_factory=list)
    evidence_commands: list[str] = Field(default_factory=list)
    findings: list[FindingRow] = Field(default_factory=list)
    decompose_ref: str | None = None
    checkpoints: list[CheckpointProgress] = Field(default_factory=list)
    resume_from: str | None = None

    model_config = {"populate_by_name": True}

    @field_validator("schema_version")
    @classmethod
    def _schema_ok(cls, v: str) -> str:
        if v != SCHEMA_EPIC_SECURITY:
            raise ValueError(f"schema must be {SCHEMA_EPIC_SECURITY!r}")
        return SCHEMA_EPIC_SECURITY


def load_qa(path: Path) -> EpicQaDoc:
    return EpicQaDoc.model_validate(load_yaml_file(path))


def load_refactor(path: Path) -> EpicRefactorDoc:
    return EpicRefactorDoc.model_validate(load_yaml_file(path))


def load_security(path: Path) -> EpicSecurityDoc:
    return EpicSecurityDoc.model_validate(load_yaml_file(path))


def validate_qa_yaml(path: Path, *, expected_verdict: str | None = None) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"missing qa yaml: {path}"]
    try:
        doc = load_qa(path)
    except Exception as exc:
        return [f"invalid epic-qa yaml: {exc}"]
    if not doc.scope:
        errors.append("scope: at least one entry required")
    if not doc.checks:
        errors.append("checks: at least one entry required")
    if expected_verdict and doc.verdict != expected_verdict.strip().lower():
        errors.append(
            f"verdict: {doc.verdict!r} ≠ expected {expected_verdict.strip().lower()!r}"
        )
    if doc.verdict in {"fail", "blocked"} and not doc.fix_plan:
        errors.append("fix_plan: required when verdict is fail or blocked")
    return errors


def validate_refactor_yaml(path: Path, *, finish: bool = True) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"missing refactor yaml: {path}"]
    try:
        doc = load_refactor(path)
    except Exception as exc:
        return [f"invalid epic-refactor yaml: {exc}"]
    if finish:
        if not doc.behavior_freeze.strip():
            errors.append("behavior_freeze: required on FINISH")
        if not doc.done:
            errors.append("done: at least one entry required on FINISH")
        if not doc.files:
            errors.append("files: at least one entry required on FINISH")
        if doc.status != "completed":
            errors.append("status must be completed on FINISH")
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


def validate_security_yaml(path: Path, *, finish: bool = True) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"missing security yaml: {path}"]
    try:
        doc = load_security(path)
    except Exception as exc:
        return [f"invalid epic-security yaml: {exc}"]
    if not doc.audit_surface.strip():
        errors.append("audit_surface: required")
    if not doc.evidence_commands:
        errors.append("evidence_commands: at least one entry required")
    # Parity: evidence_commands[] must be clean executable commands (no em-dash
    # trailers / duplicates) — same contract as implement tests / decompose verify.
    seen_ev: set[str] = set()
    for i, raw in enumerate(doc.evidence_commands):
        cmd = (raw or "").strip()
        if not cmd:
            continue
        if re.search(r"[—–]", cmd):
            errors.append(
                f"evidence_commands[{i}]: em-dash forbidden (strip trailer) in {cmd!r}"
            )
        norm = re.sub(r"\s+", " ", cmd.lower())
        if norm in seen_ev:
            errors.append(
                f"evidence_commands[{i}]: duplicates another evidence_command"
            )
        seen_ev.add(norm)
    if finish:
        if doc.status != "completed":
            errors.append("status must be completed on FINISH")
        if not doc.findings:
            errors.append("findings: at least one row required on FINISH (use id=— if none)")
        for cp in doc.checkpoints:
            if cp.status != "done":
                errors.append(f"checkpoint {cp.id} must be done on FINISH")
    return errors


def detect_shard_kind(path: Path) -> str | None:
    norm = str(path).replace("\\", "/")
    name = path.name.lower()
    if "/qa/" in norm and (name.startswith("qa-") or "epic-qa" in norm):
        return "qa"
    if "/refactor/implement/" in norm and name.startswith("r"):
        return "refactor"
    if "/security/implement/" in norm and name.startswith("a"):
        return "security"
    if "/decompose-" in norm and "/plan/" in norm and (
        name.startswith("s") or name.startswith("e")
    ):
        return "decompose"
    if "/implement/implement-" in norm and (
        name.startswith("s") or name.startswith("e")
    ):
        return "implement"
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            data = load_yaml_file(path)
        except Exception:
            return None
        schema = str(data.get("schema") or "")
        if schema == SCHEMA_EPIC_QA:
            return "qa"
        if schema == SCHEMA_EPIC_REFACTOR:
            return "refactor"
        if schema == SCHEMA_EPIC_SECURITY:
            return "security"
        if schema == SCHEMA_EPIC_DECOMPOSE or "decompose" in schema:
            return "decompose"
        if "implement" in schema or "decompose_ref" in data:
            return "implement"
    return None


def validate_epic_shard(
    path: Path,
    *,
    finish: bool = True,
    expected_verdict: str | None = None,
) -> list[str]:
    if path.suffix.lower() == ".md":
        kind = detect_shard_kind(path)
        if kind in {"qa", "refactor", "security", "decompose", "implement"}:
            return [f"Epic shard must be .yaml, not .md: {path}"]
    kind = detect_shard_kind(path)
    if kind == "qa":
        return validate_qa_yaml(path, expected_verdict=expected_verdict)
    if kind == "refactor":
        return validate_refactor_yaml(path, finish=finish)
    if kind == "security":
        return validate_security_yaml(path, finish=finish)
    if kind == "decompose":
        from epic_yaml import validate_decompose_yaml

        return validate_decompose_yaml(path)
    if kind == "implement":
        from epic_yaml import validate_implement_yaml

        return validate_implement_yaml(path, finish=finish)
    return []


def qa_format_spec_lines(*, role: str) -> list[str]:
    r = role.strip().lower()
    return [
        f"FINISH artifact: `.cursor/templates/qa/epic-step.yaml` ({r} YAML):",
        f"schema: {SCHEMA_EPIC_QA}",
        f"role: {r}",
        "verdict: pass|fail|blocked — согласован с Handoff / activeContext",
        "scope[], checks[] — required; fix_plan[] — required if fail/blocked",
        "validate: `python3 .claude/hooks/epic_resolve.py validate-step --path <shard.yaml>`",
    ]


def refactor_format_spec_lines(*, role: str) -> list[str]:
    r = role.strip().lower()
    return [
        f"FINISH artifact: `.cursor/templates/refactor/epic-step.yaml` ({r} YAML):",
        f"schema: {SCHEMA_EPIC_REFACTOR}",
        "behavior_freeze, done, files, tests, checkpoints, status=completed",
        "tests: format (HARD) — wrap cmd in `backticks`; FORBIDDEN command+prose без backticks",
        "  OK: '`.venv/bin/pytest path -q`'; FAIL: 'npm exec tsc -- --noEmit — passed'",
    ]


def security_format_spec_lines(*, role: str) -> list[str]:
    r = role.strip().lower()
    return [
        f"FINISH artifact: `.cursor/templates/security/epic-step.yaml` ({r} YAML):",
        f"schema: {SCHEMA_EPIC_SECURITY}",
        "audit_surface, evidence_commands, findings[], checkpoints, status=completed",
        "code_changed: no — findings only",
    ]


def decompose_format_spec_lines(*, role: str) -> list[str]:
    r = role.strip().lower()
    return [
        f"FINISH artifact: `.cursor/templates/decompose/epic-step.yaml` ({r} YAML):",
        f"schema: {SCHEMA_EPIC_DECOMPOSE}",
        "обязательные: goal · as_built · delta · out_of_scope",
        "checkpoints[]: 2–4 cp с criterion + verify (не mega-cp = весь goal)",
        "needs_creative for BACK/FRONT",
    ]
