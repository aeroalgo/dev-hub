from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
RESILIENCE = HOOKS / "session_resilience.py"
sys.path.insert(0, str(HOOKS))


def _load() -> object:
    spec = importlib.util.spec_from_file_location("session_resilience_fsd", RESILIENCE)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


SR = _load()
filter_step_dirty = SR.filter_step_dirty  # type: ignore[attr-defined]

DIRTY = [
    "memory-bank/back/implement/implement-T-035-loop-state-prod-hardening/s03-session-classification-resume.yaml",
    "memory-bank/back/implement/implement-T-036-crash-cycle-fix/s03-set-vs-dict-status-telemetry.yaml",
    "memory-bank/back/plan/decompose-T-034-loop-agent-scopes/s03-pretool-managed-deny-allow-model-pin.yaml",
    "memory-bank/back/plan/decompose-T-035-loop-state-prod-hardening/s03-session-classification-resume.yaml",
    "memory-bank/back/plan/decompose-T-036-crash-cycle-fix/s03-set-vs-dict-status-telemetry.yaml",
    "memory-bank/back/plan/decompose-T-036-session-checkpoint-resume/s03-dirty-resume-extend.yaml",
    "frontend/src/app/page.tsx",
    "apps/api/main.py",
    "unrelated/file.txt",
]


def test_epic_id_filters_cross_epic_memory_bank() -> None:
    result = filter_step_dirty(DIRTY, step_id="s03", epic_id="T-036-crash-cycle-fix")
    mb = [p for p in result if p.startswith("memory-bank/")]
    assert all("t-036-crash-cycle-fix" in p.lower() for p in mb), mb
    assert not any("t-035" in p.lower() for p in mb)
    assert not any("t-034" in p.lower() for p in mb)
    assert not any("t-036-session" in p.lower() for p in mb)


def test_epic_id_keeps_correct_epic_files() -> None:
    result = filter_step_dirty(DIRTY, step_id="s03", epic_id="T-036-crash-cycle-fix")
    paths = set(result)
    assert "memory-bank/back/implement/implement-T-036-crash-cycle-fix/s03-set-vs-dict-status-telemetry.yaml" in paths
    assert "memory-bank/back/plan/decompose-T-036-crash-cycle-fix/s03-set-vs-dict-status-telemetry.yaml" in paths


def test_no_epic_id_returns_all_step_matches() -> None:
    result = filter_step_dirty(DIRTY, step_id="s03", epic_id=None)
    mb = [p for p in result if p.startswith("memory-bank/")]
    assert len(mb) == 6


def test_frontend_apps_included_without_epic_filter() -> None:
    result = filter_step_dirty(DIRTY, step_id="s03", epic_id="T-036-crash-cycle-fix", delta_paths=["frontend/src/app/page.tsx"])
    assert "frontend/src/app/page.tsx" in result


def test_unrelated_files_excluded() -> None:
    result = filter_step_dirty(DIRTY, step_id="s03", epic_id="T-036-crash-cycle-fix")
    assert "unrelated/file.txt" not in result
