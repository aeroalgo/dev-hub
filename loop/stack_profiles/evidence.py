"""Atomic persistence and strict verification for capability execution evidence."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Optional

from loop.stack_profiles.execution import (
    CapabilityCheckSpec,
    CapabilityExecutionEvidence,
    compute_declaration_fingerprint,
)


def get_evidence_relative_path(
    role: str,
    epic_id: str,
    step_id: str,
    fingerprint: str,
) -> Path:
    """Return canonical relative path for capability execution evidence sidecar."""
    return Path(
        f"memory-bank/{role.strip()}/execution/{epic_id.strip()}/{step_id.strip()}/capability-{fingerprint.strip()}.json"
    )


def write_capability_evidence(
    project_root: Path,
    evidence: CapabilityExecutionEvidence,
) -> Path:
    """Atomically persist CapabilityExecutionEvidence to deterministic fingerprint path."""
    rel_path = get_evidence_relative_path(
        role=evidence.role,
        epic_id=evidence.epic_id,
        step_id=evidence.step_id,
        fingerprint=evidence.declaration_fingerprint,
    )
    dest_path = project_root / rel_path
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    # Validate model serialization
    payload_dict = evidence.model_dump(by_alias=True, exclude_none=True)
    serialized = json.dumps(payload_dict, indent=2, sort_keys=True)

    # Atomic write via temporary file in the same directory
    fd, tmp_file = tempfile.mkstemp(
        dir=dest_path.parent,
        prefix=f".tmp-capability-{evidence.declaration_fingerprint}-",
        suffix=".json",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(serialized)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_file, dest_path)
    except Exception:
        if os.path.exists(tmp_file):
            os.unlink(tmp_file)
        raise

    return dest_path


def read_capability_evidence(
    project_root: Path,
    role: str,
    epic_id: str,
    step_id: str,
    declaration: CapabilityCheckSpec,
) -> Optional[CapabilityExecutionEvidence]:
    """Read and validate capability execution evidence for the specified scope and declaration."""
    expected_fp = compute_declaration_fingerprint(
        role=role,
        epic_id=epic_id,
        step_id=step_id,
        declaration=declaration,
    )
    rel_path = get_evidence_relative_path(
        role=role,
        epic_id=epic_id,
        step_id=step_id,
        fingerprint=expected_fp,
    )
    target_path = project_root / rel_path
    if not target_path.is_file():
        return None

    try:
        raw_text = target_path.read_text(encoding="utf-8")
        data = json.loads(raw_text)
        evidence = CapabilityExecutionEvidence.model_validate(data)

        # Strict checks against scope and declaration
        if (
            evidence.role != role
            or evidence.epic_id != epic_id
            or evidence.step_id != step_id
            or evidence.declaration_fingerprint != expected_fp
            or evidence.target != declaration.target
            or evidence.capability != (declaration.capability if isinstance(declaration.capability, str) else declaration.capability.value)
        ):
            return None

        return evidence
    except Exception:
        return None
