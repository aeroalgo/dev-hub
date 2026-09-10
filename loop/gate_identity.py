"""GateIdentity SoT — canonical gate identity service (Claude/Codex).

Provides atomic freeze, expected identity resolution (ignoring mid-session armed
drift), injection text generation, spawn-gate mirror binding, and fence assertion/binding.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any

GATE_IDENTITY_SCHEMA = "loop-gate-identity/v1"
SESSION_START_IDENTITY_SCHEMA = "loop-session-start-identity/v1"


class GateOwnershipMismatchError(ValueError):
    """Raised when a gate fence fails ownership assertions under strict policy."""

    def __init__(self, message: str, mismatches: list[str] | None = None) -> None:
        super().__init__(message)
        self.mismatches = list(mismatches or [])


@dataclass(frozen=True)
class GateIdentity:
    """Canonical SoT representation of gate ownership identity."""

    schema: str = GATE_IDENTITY_SCHEMA
    session_id: str = ""
    epic_id: str = ""
    step_id: str = ""
    role: str = ""
    phase: str = ""
    phase_run_id: str = ""
    projection_hash: str = ""
    phase_epoch: Any = ""
    event_digest: str = ""
    authority: str = "manual"

    @property
    def step(self) -> str:
        return self.step_id

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["step"] = self.step_id
        return data

    def get(self, key: str, default: Any = None) -> Any:
        if key == "step":
            return self.step_id or default
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:
        val = self.get(key)
        if val is None and not hasattr(self, key) and key != "step":
            raise KeyError(key)
        return val

    @classmethod
    def from_mapping(cls, raw: Any) -> GateIdentity | None:
        if not isinstance(raw, dict):
            return None
        step = str(raw.get("step_id") or raw.get("step") or "").strip()
        proj_hash = str(raw.get("projection_hash") or "").strip()
        phase_epoch = raw.get("phase_epoch") or ""
        authority = str(
            raw.get("authority")
            or ("autonomous" if proj_hash and phase_epoch else "manual")
        ).strip()
        return cls(
            schema=str(raw.get("schema") or GATE_IDENTITY_SCHEMA),
            session_id=str(raw.get("session_id") or "").strip(),
            epic_id=str(raw.get("epic_id") or raw.get("epic") or "").strip(),
            step_id=step,
            role=str(raw.get("role") or raw.get("armed_role") or "").strip(),
            phase=str(raw.get("phase") or raw.get("loop_phase") or "").strip(),
            phase_run_id=str(raw.get("phase_run_id") or "").strip(),
            projection_hash=proj_hash,
            phase_epoch=phase_epoch,
            event_digest=str(raw.get("event_digest") or "").strip(),
            authority=authority,
        )

    @classmethod
    def freeze(
        cls,
        state: dict[str, Any],
        *,
        phase: str | None = None,
        step_id: str | None = None,
        session_id: str | None = None,
        phase_run_id: str | None = None,
        epic_id: str | None = None,
        role: str | None = None,
    ) -> GateIdentity:
        """Freeze prepare-time session identity into state.session_start_identity."""
        from loop.session_finalize import freeze_session_start_identity

        freeze_session_start_identity(
            state,
            phase=phase,
            step_id=step_id,
            session_id=session_id,
            phase_run_id=phase_run_id,
        )
        if epic_id is not None or role is not None:
            raw = dict(state.get("session_start_identity") or {})
            if epic_id is not None:
                raw["epic_id"] = str(epic_id).strip()
            if role is not None:
                raw["role"] = str(role).strip()
            state["session_start_identity"] = raw
        return cls.expected(state, session_id=session_id)

    @classmethod
    def expected(
        cls,
        state: dict[str, Any] | None,
        session_id: str | None = None,
    ) -> GateIdentity:
        """Read expected ownership identity, preferring frozen session_start_identity."""
        st = dict(state or {})
        start_raw = st.get("session_start_identity")
        start = cls.from_mapping(start_raw) if isinstance(start_raw, dict) else None

        if start and start.step_id:
            step_id = start.step_id
        else:
            step_id = str(
                st.get("armed_step")
                or st.get("last_finished_step")
                or st.get("step")
                or ""
            ).strip()

        if start and start.epic_id:
            epic_id = start.epic_id
        else:
            epic_id = str(st.get("armed_epic") or st.get("epic") or "").strip()

        if start and start.role:
            role = start.role
        else:
            role = str(st.get("role") or st.get("armed_role") or "").strip()

        if start and start.phase:
            phase = start.phase
        else:
            phase = str(st.get("loop_phase") or st.get("phase") or step_id or "").strip()

        if start and start.session_id:
            resolved_session = start.session_id
        else:
            resolved_session = str(
                session_id
                or st.get("session_id")
                or os.environ.get("EPIC_RUNNER_SESSION_ID")
                or ""
            ).strip()

        if start and start.phase_run_id:
            phase_run_id = start.phase_run_id
        else:
            phase_run_id = str(st.get("phase_run_id") or "").strip()

        projection = st.get("projection")
        proj_dict = projection if isinstance(projection, dict) else {}
        proj_hash = str(proj_dict.get("projection_hash") or st.get("projection_hash") or "").strip()
        phase_epoch = proj_dict.get("phase_epoch") or st.get("phase_epoch") or ""
        event_digest = str(proj_dict.get("event_digest") or st.get("event_digest") or "").strip()
        authority = "autonomous" if proj_hash and phase_epoch else "manual"

        return cls(
            schema=GATE_IDENTITY_SCHEMA,
            session_id=resolved_session,
            epic_id=epic_id,
            step_id=step_id,
            role=role,
            phase=phase,
            phase_run_id=phase_run_id,
            projection_hash=proj_hash,
            phase_epoch=phase_epoch,
            event_digest=event_digest,
            authority=authority,
        )

    @classmethod
    def bind_spawn_gate(
        cls,
        state: dict[str, Any],
        identity: GateIdentity | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Mirror SoT identity into state.gate_identity and top-level fields."""
        if identity is None:
            ident_obj = cls.expected(state)
        elif isinstance(identity, GateIdentity):
            ident_obj = identity
        else:
            ident_obj = cls.from_mapping(identity) or cls.expected(state)

        id_dict = ident_obj.to_dict()
        state["gate_identity"] = dict(id_dict)
        for key in (
            "session_id",
            "epic_id",
            "role",
            "step",
            "projection_hash",
            "phase_epoch",
            "event_digest",
            "authority",
        ):
            if key in id_dict and id_dict[key]:
                state[key] = id_dict[key]
        return state["gate_identity"]

    @classmethod
    def inject_text(
        cls,
        identity: GateIdentity | dict[str, Any],
    ) -> str:
        """Format markdown/text GATE_IDENTITY block for prompt / additionalContext."""
        if isinstance(identity, GateIdentity):
            sess = identity.session_id
            epic = identity.epic_id
            step = identity.step_id
        elif isinstance(identity, dict):
            sess = str(identity.get("session_id") or "").strip()
            epic = str(identity.get("epic_id") or "").strip()
            step = str(identity.get("step_id") or identity.get("step") or "").strip()
        else:
            sess = ""
            epic = ""
            step = ""
        return (
            f"GATE_IDENTITY session_id={sess} epic_id={epic} step_id={step}\n"
            "Fence MUST use these exact IDs for session_id, epic_id, and step_id.\n"
        )

    @classmethod
    def assert_fence(
        cls,
        fence: dict[str, Any],
        expected: GateIdentity | dict[str, Any] | None = None,
        *,
        policy: str = "strict",
        agent_type: str | None = None,
    ) -> list[str]:
        """Validate fence fields against expected SoT identity."""
        if expected is None:
            raise ValueError("expected identity must be provided for assert_fence")
        if isinstance(expected, GateIdentity):
            exp_obj = expected
        elif isinstance(expected, dict):
            exp_obj = cls.from_mapping(expected) or cls.expected(expected)
        else:
            raise TypeError(f"Invalid expected identity type: {type(expected)}")

        fence_step = str(fence.get("step_id") or fence.get("step") or "").strip()
        fence_epic = str(fence.get("epic_id") or fence.get("epic") or "").strip()
        fence_session = str(fence.get("session_id") or fence.get("session") or "").strip()
        fence_agent = str(fence.get("agent_id") or fence.get("agent_type") or "").strip()

        exp_step = exp_obj.step_id
        exp_epic = exp_obj.epic_id
        exp_session = exp_obj.session_id
        exp_agent = str(agent_type or exp_obj.role or "").strip()

        mismatches: list[str] = []

        if fence_agent and exp_agent:
            from loop.mb_finish.verify_hint import record_agent_key

            if record_agent_key(fence_agent) != record_agent_key(exp_agent):
                mismatches.append(f"agent_id mismatch (got {fence_agent!r}, expected {exp_agent!r})")

        if policy == "strict":
            if exp_step and fence_step and fence_step != exp_step:
                mismatches.append(f"step_id mismatch (got {fence_step!r}, expected {exp_step!r})")
            if exp_epic and fence_epic and fence_epic != exp_epic:
                mismatches.append(f"epic_id mismatch (got {fence_epic!r}, expected {exp_epic!r})")
            if exp_session and fence_session and fence_session != exp_session:
                mismatches.append(f"session_id mismatch (got {fence_session!r}, expected {exp_session!r})")

        if mismatches:
            raise GateOwnershipMismatchError(
                f"semantic_ownership_mismatch: {', '.join(mismatches)}",
                mismatches=mismatches,
            )
        return []

    @classmethod
    def bind_fence(
        cls,
        fence: dict[str, Any],
        expected: GateIdentity | dict[str, Any],
        *,
        policy: str = "transport_bind",
        agent_type: str | None = None,
    ) -> dict[str, Any]:
        """Bind fence fields to SoT identity according to policy."""
        if isinstance(expected, GateIdentity):
            exp_obj = expected
        elif isinstance(expected, dict):
            exp_obj = cls.from_mapping(expected) or cls.expected(expected)
        else:
            raise TypeError(f"Invalid expected identity type: {type(expected)}")

        if policy == "transport_bind":
            cls.assert_fence(fence, exp_obj, policy="transport_bind", agent_type=agent_type)
            if exp_obj.session_id:
                fence["session_id"] = exp_obj.session_id
            if exp_obj.epic_id:
                fence["epic_id"] = exp_obj.epic_id
            if exp_obj.step_id:
                fence["step_id"] = exp_obj.step_id
        elif policy == "strict":
            cls.assert_fence(fence, exp_obj, policy="strict", agent_type=agent_type)
        else:
            raise ValueError(f"Unknown fence binding policy: {policy}")
        return fence


freeze = GateIdentity.freeze
expected = GateIdentity.expected
inject_text = GateIdentity.inject_text
bind_spawn_gate = GateIdentity.bind_spawn_gate
assert_fence = GateIdentity.assert_fence
bind_fence = GateIdentity.bind_fence
