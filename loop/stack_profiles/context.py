"""Pure project verification context classifier."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Union

from loop.stack_profiles.resolver import MANIFEST_FILENAME, load_project_manifest

ProjectVerificationContext = Literal["hub", "managed"]


def classify_project_verification_context(
    project_root: Union[str, Path]
) -> ProjectVerificationContext:
    """Classify project verification context as either 'hub' or 'managed'.

    Strictly inspects the project root for dev-hub.project.yaml:
    - If no manifest file exists at project_root, returns 'hub'.
    - If manifest file exists and validates successfully, returns 'managed'.
    - If manifest file exists but fails parsing or validation, raises ValueError (fail-closed).
    """
    root_path = Path(project_root)
    manifest_path = root_path / MANIFEST_FILENAME
    if not manifest_path.is_file():
        return "hub"

    manifest, diag = load_project_manifest(root_path)
    if diag is not None or manifest is None:
        diag_msg = diag.message if diag else "Manifest validation failed"
        raise ValueError(
            f"Project verification context cannot be resolved: manifest exists but is invalid ({diag_msg})"
        )

    return "managed"
