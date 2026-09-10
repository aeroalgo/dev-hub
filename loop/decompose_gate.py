"""Runtime-neutral structural gate for decompose phase phase transitions."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable


def missing_decompose_shards(
    index_path: str | Path,
    steps: Iterable[dict[str, Any]],
) -> list[str]:
    """Return index entries whose referenced decompose shard is absent.

    Layout v2 stores shards under ``yaml/steps`` while legacy indexes store
    them beside the index.  The index reference is authoritative in both
    layouts; status or an analyze artifact cannot substitute for the file.
    """
    index = Path(index_path)
    parent = index.parent
    steps_dir = parent / "steps"
    missing: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        step_id = str(step.get("id") or step.get("step_id") or "?").strip()
        href = str(step.get("file") or "").strip()
        if not href:
            # Legacy indexes may carry only queue/status fields.  Their
            # compatibility path has no shard reference to resolve here;
            # v2 indexes are checked by validate-decompose-tree at FINISH.
            continue

        filename = Path(href).name
        candidates = [steps_dir / filename, parent / filename, parent / href]
        if not any(candidate.is_file() for candidate in candidates):
            missing.append(f"{step_id}: {href}")
    return missing


def decompose_shards_diagnostic(
    index_path: str | Path,
    steps: Iterable[dict[str, Any]],
) -> str | None:
    """Render a bounded diagnostic for the structural decompose gate."""
    missing = missing_decompose_shards(index_path, steps)
    if not missing:
        return None
    return "missing decompose shards: " + ", ".join(missing[:20])


def decompose_verify_pass_ready(cwd: str | Path, state: dict[str, Any] | None = None) -> dict[str, Any]:
    """DECOMPOSE specialization of phase_verify_pass_ready."""
    return phase_verify_pass_ready(cwd, "DECOMPOSE", state)


def phase_verify_pass_ready(
    cwd: str | Path,
    phase: str,
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Bound verify PASS for a phase that declares need_verify + verify_agent.

    Structural readiness alone must not advance the phase. Repair-loop
    exhaustion and prepare_session retries stay on the same phase until this
    gate passes (or the phase does not require verify).
    """
    from pathlib import Path as _Path

    cwd_p = _Path(cwd).resolve()
    st = state
    if st is None:
        try:
            from epic.core import load_epic_state

            st = load_epic_state(cwd_p)
        except Exception:
            st = {}
    st = st or {}

    try:
        from loop.epic_transition import get_phase_config, normalize_registry_phase

        phase_key = normalize_registry_phase(phase)
        cfg = get_phase_config(phase_key)
    except Exception:
        phase_key = str(phase or "").strip().upper()
        cfg = {}

    gates = cfg.get("finish_gates_dict") or cfg.get("finish_gates") or {}
    need_verify = bool(gates.get("need_verify"))
    verify_agent = str(cfg.get("verify_agent") or "").strip().lower()
    if not need_verify or not verify_agent:
        return {"ok": True, "diagnostic": "verify_not_required", "phase": phase_key}

    verdict = str(st.get("last_verify_verdict") or "").strip().upper()
    evidence = st.get("last_verify_evidence") or st.get("last_verify_receipt") or {}
    if not isinstance(evidence, dict):
        evidence = {}
    agent_id = str(evidence.get("agent_id") or "").strip().lower()
    session_key = verify_agent.replace("-", "_") + "_verdict"
    session_verdict = str(st.get(session_key) or "").strip().upper()
    # Legacy keys used by record_verdict for known agents.
    if verify_agent == "verify-decompose":
        session_verdict = session_verdict or str(
            st.get("verify_decompose_verdict") or ""
        ).strip().upper()
    elif verify_agent == "verify-implement":
        session_verdict = session_verdict or str(st.get("verify_verdict") or "").strip().upper()
    elif verify_agent in {"verify-qa", "reviewer"}:
        session_verdict = session_verdict or str(
            st.get("reviewer_verdict") or st.get("last_reviewer_verdict") or ""
        ).strip().upper()

    if verdict != "PASS" and session_verdict != "PASS":
        return {
            "ok": False,
            "diagnostic": f"{verify_agent}_pass_missing",
            "reason": f"{phase_key} promotion/finish requires {verify_agent} PASS",
            "phase": phase_key,
            "verify_agent": verify_agent,
        }
    if agent_id and agent_id != verify_agent and session_verdict != "PASS":
        return {
            "ok": False,
            "diagnostic": f"{verify_agent}_pass_missing",
            "reason": (
                f"last verify agent_id={agent_id!r} is not {verify_agent}; "
                f"cannot leave {phase_key}"
            ),
            "phase": phase_key,
            "verify_agent": verify_agent,
        }
    if evidence:
        try:
            from epic.core import gate_evidence_matches

            matched, diagnostic = gate_evidence_matches(cwd_p, evidence)
        except Exception as exc:
            return {
                "ok": False,
                "diagnostic": "gate_evidence_invalid",
                "reason": f"{verify_agent} evidence check failed: {exc}",
                "phase": phase_key,
                "verify_agent": verify_agent,
            }
        if not matched:
            return {
                "ok": False,
                "diagnostic": diagnostic or "gate_evidence_mismatch",
                "reason": f"{verify_agent} evidence rejected: {diagnostic}",
                "phase": phase_key,
                "verify_agent": verify_agent,
            }
    return {
        "ok": True,
        "diagnostic": f"{verify_agent}_pass",
        "phase": phase_key,
        "verify_agent": verify_agent,
    }
