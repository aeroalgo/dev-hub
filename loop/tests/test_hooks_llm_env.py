"""Unit tests for hooks LLM env configuration and helpers."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import _lib


def test_load_hooks_llm_env_applies_project_env():
    with patch.dict("os.environ", {}, clear=True):
        keys = _lib.load_hooks_llm_env()
        assert isinstance(keys, list)
        assert "EPIC_PERMISSION_MODE" in os.environ or len(keys) > 0


def test_hooks_llm_enabled_all_off_by_default():
    with patch.dict("os.environ", {}, clear=True):
        assert _lib.hooks_llm_enabled("handoff") is False
        assert _lib.hooks_llm_enabled("verdict") is False
        assert _lib.hooks_llm_enabled("abort") is False


def test_hooks_llm_min_chars_not_checked_in_env_loader():
    env_state = {
        "PROJECT_HOOKS_LLM_FALLBACK": "1",
        "PROJECT_HOOKS_LLM_HANDOFF": "1",
        "PROJECT_HOOKS_LLM_MIN_CHARS": "500",
    }
    with patch.dict("os.environ", env_state, clear=True):
        assert _lib.hooks_llm_enabled("handoff") is True
        cfg = _lib.hooks_llm_config()
        assert cfg.min_chars == 500


def test_hooks_llm_config_defaults_and_overrides():
    with patch.dict("os.environ", {"PROJECT_OUTPUT_SUMMARY_MODEL": "test-summary-model"}, clear=True):
        cfg = _lib.hooks_llm_config()
        assert cfg.fallback_on is False
        assert cfg.handoff_on is False
        assert cfg.verdict_on is False
        assert cfg.abort_on is False
        assert cfg.min_chars == 200
        assert cfg.confidence_min == 0.7
        assert cfg.timeout_sec == 30
        assert cfg.model == "test-summary-model"
        assert cfg.debug is False

    overrides = {
        "PROJECT_HOOKS_LLM_FALLBACK": "1",
        "PROJECT_HOOKS_LLM_HANDOFF": "1",
        "PROJECT_HOOKS_LLM_VERDICT": "0",
        "PROJECT_HOOKS_LLM_ABORT": "1",
        "PROJECT_HOOKS_LLM_MIN_CHARS": "300",
        "PROJECT_HOOKS_LLM_CONFIDENCE": "0.85",
        "PROJECT_HOOKS_LLM_TIMEOUT": "45",
        "PROJECT_HOOKS_LLM_MODEL": "custom-model",
        "PROJECT_HOOKS_LLM_DEBUG": "1",
    }
    with patch.dict("os.environ", overrides, clear=True):
        cfg = _lib.hooks_llm_config()
        assert cfg.fallback_on is True
        assert cfg.handoff_on is True
        assert cfg.verdict_on is False
        assert cfg.abort_on is True
        assert cfg.min_chars == 300
        assert cfg.confidence_min == 0.85
        assert cfg.timeout_sec == 45
        assert cfg.model == "custom-model"
        assert cfg.debug is True

        assert _lib.hooks_llm_enabled("handoff") is True
        assert _lib.hooks_llm_enabled("verdict") is False
        assert _lib.hooks_llm_enabled("abort") is True


def test_hooks_llm_master_switch_overrides_domain():
    env_state = {
        "PROJECT_HOOKS_LLM_FALLBACK": "0",
        "PROJECT_HOOKS_LLM_HANDOFF": "1",
    }
    with patch.dict("os.environ", env_state, clear=True):
        assert _lib.hooks_llm_enabled("handoff") is False
