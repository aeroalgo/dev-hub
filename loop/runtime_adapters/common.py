from __future__ import annotations

import threading
from typing import Any

from loop.runtime.registry import InvalidRuntimeConfig, get_runtime_adapter
from loop.runtime_adapters.base import (
    GateLaunchRequest,
    GateLaunchResult,
    RuntimeAdapter,
    SessionContext,
)


_RUNTIME_ALIASES = {
    "claude-code": "claude",
    "claude_cli": "claude",
    "claude-cli": "claude",
}


def get_adapter_for_runtime(runtime_id: str) -> RuntimeAdapter:
    """Factory creating RuntimeAdapter instance for given runtime_id using registry."""
    runtime_id = _RUNTIME_ALIASES.get(str(runtime_id).strip().lower(), runtime_id)
    try:
        obj = get_runtime_adapter(runtime_id)
    except InvalidRuntimeConfig as e:
        raise ValueError(f"Unknown runtime: {runtime_id}") from e

    if isinstance(obj, type):
        return obj()

    # Module loaded from registry
    attr_name = f"{runtime_id.capitalize()}Adapter"
    if hasattr(obj, attr_name):
        cls = getattr(obj, attr_name)
        return cls()

    # Fallback scan module attributes for RuntimeAdapter subclass/implementation
    for name in dir(obj):
        if name.endswith("Adapter") and name != "RuntimeAdapter":
            cls = getattr(obj, name)
            if isinstance(cls, type):
                return cls()

    raise ValueError(f"No RuntimeAdapter implementation found in adapter module for runtime '{runtime_id}'")


def create_invocation_context(
    session_id: str,
    phase: str,
    step: str,
    role: str,
    epoch: int = 0,
    prompt: str = "",
    model: str | None = None,
    runtime_id: str = "claude",
    owner: str = "orchestrator",
    extras: dict[str, Any] | None = None,
    reducer: Any = None,
) -> tuple[SessionContext, str, bool]:
    """Create a SessionContext bound to an idempotent invocation record.

    Returns (context, invocation_id, is_new_launch).
    """
    from loop.lifecycle import InvocationKey, create_or_get_invocation

    key = InvocationKey(
        session=session_id,
        phase=phase,
        step=step,
        role=role,
        epoch=epoch,
    )
    record, is_new = create_or_get_invocation(key, owner=owner, reducer=reducer)

    ctx = SessionContext(
        prompt=prompt,
        phase=phase,
        model=model,
        runtime_id=runtime_id,
        session_id=session_id,
        step=step,
        role=role,
        epoch=epoch,
        invocation_id=record.invocation_id,
        extras=extras or {},
    )
    return ctx, record.invocation_id, is_new


class IdempotentGateDispatcher:
    """Thread-safe orchestrator dispatcher guaranteeing single execution per verifier identity and epoch."""

    def __init__(self, reducer: Any = None) -> None:
        from loop.lifecycle import get_default_reducer

        self.reducer = reducer if reducer is not None else get_default_reducer()
        self._lock = threading.RLock()
        self._inflight: dict[str, threading.Event] = {}
        self._worker_errors: dict[str, Exception] = {}

    def dispatch(
        self,
        request: GateLaunchRequest,
        worker_fn: Any | None = None,
    ) -> GateLaunchResult:
        """Dispatch a gate verifier request idempotently.

        If a verifier with this identity is already running or completed:
        - If completed, returns existing result/receipt immediately.
        - If in-flight, waits for completion and returns the shared result.
        - If new, atomically registers CREATED -> RUNNING, executes worker_fn, transitions to PASSED/FAILED, and signals waiters.
        """
        from loop.lifecycle import (
            GateReceipt,
            InvocationKey,
            create_or_get_invocation,
        )

        key = InvocationKey(
            session=request.session_id,
            phase=request.phase,
            step=request.step,
            role=request.role,
            epoch=request.epoch,
        )

        with self._lock:
            record, is_new = create_or_get_invocation(
                key,
                owner=request.owner,
                reducer=self.reducer,
            )

            if record.is_terminal:
                return GateLaunchResult(
                    invocation_id=record.invocation_id,
                    key=record.key.key,
                    state=record.state.value,
                    is_new_launch=False,
                    receipt=record.receipt,
                    status_view=record.status_view,
                    first_action_taken=record.first_action_taken,
                )

            if not is_new and record.invocation_id in self._inflight:
                event = self._inflight[record.invocation_id]
                is_worker_owner = False
            else:
                event = threading.Event()
                self._inflight[record.invocation_id] = event
                is_worker_owner = True

        if not is_worker_owner:
            event.wait(timeout=60.0)
            with self._lock:
                if record.invocation_id in self._worker_errors:
                    exc = self._worker_errors[record.invocation_id]
                    raise RuntimeError(f"Gate worker failed with: {exc}") from exc

                latest = self.reducer.get_invocation(record.invocation_id)
                if latest is None:
                    raise RuntimeError(f"Invocation '{record.invocation_id}' not found after execution")
                return GateLaunchResult(
                    invocation_id=latest.invocation_id,
                    key=latest.key.key,
                    state=latest.state.value,
                    is_new_launch=False,
                    receipt=latest.receipt,
                    status_view=latest.status_view,
                    first_action_taken=latest.first_action_taken,
                )

        try:
            self.reducer.start(record.key, actor=request.owner)

            receipt_output = None
            if worker_fn is not None:
                ctx = SessionContext(
                    prompt=request.prompt,
                    phase=request.phase,
                    model=request.model,
                    runtime_id=request.runtime_id,
                    session_id=request.session_id,
                    step=request.step,
                    role=request.role,
                    epoch=request.epoch,
                    invocation_id=record.invocation_id,
                    extras=request.extras,
                )
                receipt_output = worker_fn(ctx, record.invocation_id)

            verdict_val = "PASS"
            if isinstance(receipt_output, dict):
                verdict_val = str(receipt_output.get("verdict", "PASS")).upper()
                enriched = dict(receipt_output)
                if "invocation_id" not in enriched:
                    enriched["invocation_id"] = record.invocation_id
                if "epoch" not in enriched:
                    enriched["epoch"] = record.key.epoch
                receipt_output = enriched
            elif isinstance(receipt_output, GateReceipt):
                verdict_val = str(receipt_output.verdict).upper()
            elif hasattr(receipt_output, "verdict"):
                verdict_val = str(getattr(receipt_output, "verdict")).upper()

            if verdict_val == "PASS":
                updated = self.reducer.pass_invocation(
                    record.key,
                    actor=request.owner,
                    receipt=receipt_output,
                )
            else:
                updated = self.reducer.fail_invocation(
                    record.key,
                    actor=request.owner,
                    reason=f"Gate verifier returned verdict {verdict_val}",
                )

            return GateLaunchResult(
                invocation_id=updated.invocation_id,
                key=updated.key.key,
                state=updated.state.value,
                is_new_launch=True,
                receipt=updated.receipt,
                status_view=updated.status_view,
                first_action_taken=updated.first_action_taken,
            )

        except Exception as exc:
            with self._lock:
                self._worker_errors[record.invocation_id] = exc
            self.reducer.mark_infrastructure_failure(
                record.key,
                actor=request.owner,
                reason=str(exc),
            )
            raise
        finally:
            with self._lock:
                event.set()
                self._inflight.pop(record.invocation_id, None)


def dispatch_gate_verifier(
    request: GateLaunchRequest,
    worker_fn: Any | None = None,
    *,
    dispatcher: IdempotentGateDispatcher | None = None,
    reducer: Any = None,
) -> GateLaunchResult:
    """Convenience helper to dispatch a gate verifier via IdempotentGateDispatcher."""
    if dispatcher is None:
        dispatcher = IdempotentGateDispatcher(reducer=reducer)
    return dispatcher.dispatch(request, worker_fn=worker_fn)
