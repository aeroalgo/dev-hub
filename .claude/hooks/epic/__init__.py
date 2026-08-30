"""Curated epic package API backing the legacy epic_lib facade."""

from .core import _event_log_path, logger, INDEX_IMPLEMENT_CONFLICT, MARK_INDEX_MISSING, FINISH_INTEGRITY_DECOMPOSE_MISSING, FINISH_INTEGRITY_DIAGNOSTIC_CODES, atomic_write_text, checkpoint_path, checkpoint_lock_path, clear_runner_checkpoint, validate_checkpoint, load_checkpoint, commit_checkpoint, checkpoint_lifecycle, resolve_checkpoint_resume, checkpoint_resume, utc_now, default_state, load_epic_state, save_epic_state, effective_phase, gates_from_phase, rebuild_epic_projection, reconcile_epic_events, reconcile_current_epic_events, halt_epic, read_active_context, extract_handoff_block, handoff_post_implement_phase, extract_load_now, fingerprint_context, validate_active_context_shape, session_start_payload, mirror_verify_verdict, verify_pass_step_blockers, coerce_verify_verdict, gate_evidence_matches, load_decompose_steps_fail_closed, mark_index_step_status, finalize_step, validate_index_vs_implement, validate_finish_integrity, repair_finish_desync, repair_index_mirror, repair_fingerprint_stall, sync_cursor_from_index, validate_finish_integrity_with_repair, latest_qa_pass_artifact_for_reference, find_qa_pass_artifact, find_reflection_artifact, reduce_epic_lifecycle, post_implement_phase, resolve_pipeline_identity, discover_epic_for_pipeline, epic_complete_allowed, build_post_implement_active_context, find_next_decompose_step, find_next_decompose_step_from_queue, clear_reserved_role_arm, arm_active_context_from_decompose, _decompose_index_path, _append_event, _matching_reflection_artifacts, _declared_artifacts
from epic_paths import is_reserved_role_epic_id, role_from_decompose_path
from epic_index import index_yaml_path, load_index_yaml, parse_steps_from_md


def discover_epic_for_pipeline(cwd):
    """Resolve through this facade so legacy monkeypatching remains effective."""
    identity = resolve_pipeline_identity(cwd)
    if identity.get("status") != "resolved":
        return None
    return {key: identity[key] for key in ("epic_id", "role", "role_dir", "decompose")}


def mark_index_step_status(cwd, decompose, step_id, status, *, sync_checklist=True):
    """Backward-compatible facade preserving a patchable atomic writer."""
    from . import core

    original = core.atomic_write_text
    core.atomic_write_text = atomic_write_text
    try:
        return core.mark_index_step_status(
            cwd, decompose, step_id, status, sync_checklist=sync_checklist
        )
    finally:
        core.atomic_write_text = original


_mark_index_step_status_impl = mark_index_step_status


def _facade_mark_index_step_status(cwd, decompose, step_id, status, *, sync_checklist=True):
    return _mark_index_step_status_impl(
        cwd, decompose, step_id, status, sync_checklist=sync_checklist
    )


mark_index_step_status = _facade_mark_index_step_status
from _lib import gate_identity

__all__ = ['_event_log_path', 'logger', 'INDEX_IMPLEMENT_CONFLICT', 'MARK_INDEX_MISSING', 'FINISH_INTEGRITY_DECOMPOSE_MISSING', 'FINISH_INTEGRITY_DIAGNOSTIC_CODES', 'atomic_write_text', 'checkpoint_path', 'checkpoint_lock_path', 'clear_runner_checkpoint', 'validate_checkpoint', 'load_checkpoint', 'commit_checkpoint', 'checkpoint_lifecycle', 'resolve_checkpoint_resume', 'checkpoint_resume', 'utc_now', 'default_state', 'load_epic_state', 'save_epic_state', 'effective_phase', 'gates_from_phase', 'rebuild_epic_projection', 'reconcile_epic_events', 'reconcile_current_epic_events', 'halt_epic', 'read_active_context', 'extract_handoff_block', 'handoff_post_implement_phase', 'extract_load_now', 'fingerprint_context', 'validate_active_context_shape', 'session_start_payload', 'mirror_verify_verdict', 'verify_pass_step_blockers', 'coerce_verify_verdict', 'gate_evidence_matches', 'load_decompose_steps_fail_closed', 'mark_index_step_status', 'finalize_step', 'validate_index_vs_implement', 'validate_finish_integrity', 'repair_finish_desync', 'repair_index_mirror', 'repair_fingerprint_stall', 'sync_cursor_from_index', 'validate_finish_integrity_with_repair', 'latest_qa_pass_artifact_for_reference', 'find_qa_pass_artifact', 'find_reflection_artifact', 'reduce_epic_lifecycle', 'post_implement_phase', 'resolve_pipeline_identity', 'discover_epic_for_pipeline', 'epic_complete_allowed', 'build_post_implement_active_context', 'find_next_decompose_step', 'find_next_decompose_step_from_queue', 'clear_reserved_role_arm', 'arm_active_context_from_decompose', '_decompose_index_path', '_append_event', '_matching_reflection_artifacts', '_declared_artifacts', 'is_reserved_role_epic_id', 'role_from_decompose_path', 'index_yaml_path', 'load_index_yaml', 'parse_steps_from_md', 'gate_identity']
