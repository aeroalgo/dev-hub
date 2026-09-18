"""Small, single-cursor loop kernel.

The kernel deliberately has only one mutable runtime document: ``cursor.json``.
The decompose index and step artifacts are product data; activeContext and
session logs are generated views/evidence.
"""

from .engine import LoopEngine, TransitionError
from .model import Cursor, CursorStatus, RuntimeResult, Transition
from .store import LoopPaths, CursorStore

__all__ = [
    "Cursor",
    "CursorStatus",
    "CursorStore",
    "LoopEngine",
    "LoopPaths",
    "RuntimeResult",
    "Transition",
    "TransitionError",
]
