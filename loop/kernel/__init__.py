"""Small, single-cursor loop kernel.

The kernel deliberately has only one mutable runtime document: ``cursor.json``.
The decompose index and step artifacts are product data; activeContext and
session logs are generated views/evidence.
"""

from .engine import LoopEngine, TransitionError
from .model import Cursor, CursorStatus, FailureRecord, RuntimeResult, Transition
from .session import SessionOutcome, SessionRun, SessionSupervisor
from .store import CursorStore, LoopPaths, TransactionPlan

__all__ = [
    "Cursor",
    "CursorStatus",
    "CursorStore",
    "FailureRecord",
    "LoopEngine",
    "LoopPaths",
    "RuntimeResult",
    "SessionOutcome",
    "SessionRun",
    "SessionSupervisor",
    "Transition",
    "TransactionPlan",
    "TransitionError",
]
