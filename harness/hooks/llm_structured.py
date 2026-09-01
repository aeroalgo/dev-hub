"""Structured output schemas and sync runner for bash-output-cap using Pydantic v2 and pydantic-ai."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

__all__ = [
    "LogError",
    "LogSummary",
    "make_output_cap_agent",
    "run_log_summary",
]


class LogError(BaseModel):
    """Structured error entry from test runner or command execution output."""

    location: str = ""
    message: str


class LogSummary(BaseModel):
    """Structured summary extracted from tool / CLI command execution logs."""

    exit_code: int | None = None
    failed_tests: list[str] = Field(default_factory=list, max_length=20)
    errors: list[LogError] = Field(default_factory=list, max_length=30)
    root_cause: str = ""
    summary_bullets: list[str] = Field(default_factory=list, max_length=25)


def make_output_cap_agent(
    model: str | None = None,
    *,
    env: dict[str, str] | None = None,
) -> Agent[LogSummary]:
    """Create a Pydantic AI Agent[LogSummary] configured from environment variables."""
    from _lib import load_output_summary_env

    load_output_summary_env()

    env_map = dict(os.environ)
    if env is not None:
        env_map.update(env)

    url = (env_map.get("PROJECT_OUTPUT_SUMMARY_URL") or "http://localhost:20128/v1").rstrip("/")
    model_name = model or env_map.get("PROJECT_OUTPUT_SUMMARY_MODEL") or "free-stack"

    key = env_map.get("PROJECT_OUTPUT_SUMMARY_KEY") or ""
    if not key:
        key_file_str = env_map.get("PROJECT_OUTPUT_SUMMARY_KEY_FILE")
        key_file = (
            Path(key_file_str).expanduser()
            if key_file_str
            else Path.home() / ".codex" / ".omniroute_key"
        )
        if key_file.is_file():
            try:
                key = key_file.read_text(encoding="utf-8").strip()
            except OSError:
                key = ""

    provider = OpenAIProvider(base_url=url, api_key=key or "missing_key")
    chat_model = OpenAIChatModel(model_name, provider=provider)
    return Agent(chat_model, output_type=LogSummary)


def run_log_summary(
    cmd: str,
    sample: str,
    dump_path: Path | str,
    *,
    env: dict[str, str] | None = None,
) -> LogSummary | None:
    """Run structured log summary with timeout, retries, and fallback model chain. Fail-soft."""
    try:
        from _lib import load_output_summary_env

        load_output_summary_env()

        env_map = dict(os.environ)
        if env is not None:
            env_map.update(env)

        if env_map.get("PROJECT_OUTPUT_SUMMARY", "1").strip() in {
            "0",
            "false",
            "no",
            "off",
        }:
            return None

        model = env_map.get("PROJECT_OUTPUT_SUMMARY_MODEL") or "free-stack"
        fallback_raw = env_map.get("PROJECT_OUTPUT_SUMMARY_FALLBACK_MODEL")
        if fallback_raw is None:
            fallback: str | None = "aug/claude-haiku-4.5"
        elif fallback_raw.strip() in {"", "0", "-", "off", "none"}:
            fallback = None
        else:
            fallback = fallback_raw.strip()

        key = env_map.get("PROJECT_OUTPUT_SUMMARY_KEY") or ""
        if not key:
            key_file_str = env_map.get("PROJECT_OUTPUT_SUMMARY_KEY_FILE")
            key_file = (
                Path(key_file_str).expanduser()
                if key_file_str
                else Path.home() / ".codex" / ".omniroute_key"
            )
            if key_file.is_file():
                try:
                    key = key_file.read_text(encoding="utf-8").strip()
                except OSError:
                    key = ""

        if not key:
            return None

        try:
            retries = max(1, int(env_map.get("PROJECT_OUTPUT_SUMMARY_RETRIES", "3")))
        except ValueError:
            retries = 3
        try:
            timeout = float(env_map.get("PROJECT_OUTPUT_SUMMARY_TIMEOUT", "10"))
        except ValueError:
            timeout = 10.0

        models = [model]
        if fallback and fallback != model:
            models.append(fallback)

        prompt = (
            "Сделай краткий summary лога для родительского coding-агента. "
            "Русский. Макс 25 коротких строк/буллетов. "
            "Только факты: exit/status, failed tests, ERROR/Exception file:line, "
            "корневые симптомы. Не выдумывай. Не предлагай rewrite всего. "
            f"Полный лог: {dump_path}\n"
            f"Команда: {str(cmd)[:400]}\n"
            f"Лог:\n{sample}"
        )

        async def _execute() -> LogSummary | None:
            for m in models:
                agent = make_output_cap_agent(model=m, env=env_map)
                for _attempt in range(retries):
                    try:
                        res = await asyncio.wait_for(agent.run(prompt), timeout=timeout)
                        if isinstance(res.data, LogSummary):
                            return res.data
                    except Exception:
                        continue
            return None

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(asyncio.run, _execute())
                return future.result()
        else:
            return asyncio.run(_execute())

    except Exception:
        return None
