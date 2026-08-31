"""Tests for structured output models in llm_structured.py."""

import os
import sys
from pathlib import Path
from typing import Any
import pytest
from pydantic import ValidationError

HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from llm_structured import (
    AbortClassify,
    HandoffExtract,
    VerdictExtract,
    is_confident,
)


def test_handoff_extract_canonical_fixture():
    model = HandoffExtract(
        handoff_md="## Handoff\n- Test",
        load_now_paths=["back/plan/decompose/s01.yaml"],
        phase="BACK IMPLEMENT",
        confidence=0.95,
    )
    assert model.handoff_md == "## Handoff\n- Test"
    assert model.load_now_paths == ["back/plan/decompose/s01.yaml"]
    assert model.phase == "BACK IMPLEMENT"
    assert model.confidence == 0.95


def test_verdict_extract_null_verdict_allowed():
    model = VerdictExtract(verdict=None, confidence=0.1)
    assert model.verdict is None
    assert model.confidence == 0.1

    model_pass = VerdictExtract(verdict="PASS", confidence=0.9)
    assert model_pass.verdict == "PASS"


def test_verdict_extract_invalid():
    with pytest.raises(ValidationError):
        VerdictExtract(verdict="INVALID", confidence=0.8)


def test_abort_classify_transient_fatal():
    m1 = AbortClassify(kind="transient", reason_short="timeout", confidence=0.85)
    assert m1.kind == "transient"
    assert m1.reason_short == "timeout"

    m2 = AbortClassify(kind="fatal", reason_short="context len exceeded", confidence=0.99)
    assert m2.kind == "fatal"

    with pytest.raises(ValidationError):
        AbortClassify(kind="unknown", reason_short="err", confidence=0.5)


def test_confidence_bounds():
    with pytest.raises(ValidationError):
        HandoffExtract(handoff_md="", load_now_paths=[], phase=None, confidence=-0.1)

    with pytest.raises(ValidationError):
        VerdictExtract(verdict="PASS", confidence=1.1)


def test_is_confident_below_threshold(monkeypatch: Any):
    m = VerdictExtract(verdict="PASS", confidence=0.6)
    assert not is_confident(m, threshold=0.7)
    assert is_confident(m, threshold=0.5)

    monkeypatch.setenv("PROJECT_HOOKS_LLM_CONFIDENCE", "0.8")
    assert not is_confident(m)

    monkeypatch.setenv("PROJECT_HOOKS_LLM_CONFIDENCE", "0.5")
    assert is_confident(m)
