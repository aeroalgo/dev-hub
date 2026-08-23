#!/usr/bin/env python3
"""PostToolUse Bash — hybrid output cap: signal extract → optional cheap LLM → head/tail.

Full dump always saved under `.claude/runtime/bash-dumps/` when capped.

Config file (auto-loaded by ./loop/loop.sh at start + by this hook as fallback;
process env wins if already set):
  `.claude/project.env`
  `.claude/project.env.local` (optional overrides, gitignored)

Env (optional):
  PROJECT_OUTPUT_SUMMARY=0          disable LLM step
  PROJECT_OUTPUT_SUMMARY_URL        default http://localhost:20128/v1
  PROJECT_OUTPUT_SUMMARY_MODEL      default free-stack
  PROJECT_OUTPUT_SUMMARY_FALLBACK_MODEL  default aug/claude-haiku-4.5 (after primary retries)
  PROJECT_OUTPUT_SUMMARY_KEY_FILE   default ~/.codex/.omniroute_key
  PROJECT_OUTPUT_SUMMARY_KEY        inline key (overrides file)
  PROJECT_OUTPUT_SUMMARY_RETRIES    default 3
  PROJECT_OUTPUT_SUMMARY_TIMEOUT    default 10 (sec per attempt)
  PROJECT_OUTPUT_SUMMARY_BACKOFF    default 0.8 (sec * attempt)
  PROJECT_OUTPUT_SUMMARY_DEBUG=1    log give-up reason to stderr
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import emit, load_output_summary_env, product_cwd, read_stdin  # noqa: E402

MAX_CHARS = 12_000
SOFT_NOISY = 4_000
HEAD = 4_000
TAIL = 2_500
EXTRACT_MAX_LINES = 40
EXTRACT_MAX_CHARS = 4_000
EXTRACT_MAX_UNIQUE = 12
EXTRACT_CONTEXT = 1  # lines around first occurrence of a fingerprint
LLM_INPUT_MAX = 24_000
LLM_TIMEOUT_SEC = 30
LLM_RETRIES = 3  # attempts total
LLM_BACKOFF_SEC = 0.8
# Keep sum(timeouts)+backoff under PostToolUse Bash hook timeout (45s).

_NOISY = re.compile(
    r"(?i)(pytest|docker\s+compose\s+logs|journalctl|dmesg|"
    r"tail\s+-n\s+[5-9]\d{2,}|--tail[= ]?[5-9]\d{2,})"
)
_SIGNAL = re.compile(
    r"(?i)("
    r"\bFAILED\b|\bFAILURES\b|\bERRORS\b|\bERROR\b|Traceback|AssertionError|"
    r"ModbusException|ExceptionResponse|"
    r"^=+\s*\d+\s+(failed|passed|error)|"
    r"EXIT(_STATUS)?=\d+|exit_code|short test summary|"
    r"poll group .*crash|already exists|last_run_started_at|"
    r"^\s*E\s+\S"  # pytest longrepr lines only
    r")"
)

# Noise that makes "same" log lines look unique
_FINGERPRINT_SUBS = [
    (re.compile(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:\s*UTC)?"), "<TS>"),
    (re.compile(r"^\s*\d+[:-]"), ""),  # rg line prefixes "12:" / "12-"
    (re.compile(r"\bauto_\d+\b"), "auto_*"),
    (re.compile(r"\b_hyper_\d+_\d+_chunk\b"), "_hyper_*_chunk"),
    (re.compile(r"\bcompress_hyper_\d+_\d+_chunk\b"), "compress_hyper_*_chunk"),
    (re.compile(r"\bpid=\d+\b"), "pid=*"),
    (re.compile(r"\[\d+\]"), "[*]"),  # postgres [58291]
    (re.compile(r"\b0x[0-9a-fA-F]+\b"), "0x*"),
]


def _fingerprint(line: str) -> str:
    s = line.strip()
    for pat, repl in _FINGERPRINT_SUBS:
        s = pat.sub(repl, s)
    s = re.sub(r"\s+", " ", s)
    return s[:240]


def _as_text(resp: object) -> tuple[str, str, dict]:
    if isinstance(resp, dict):
        out = dict(resp)
        stdout = str(out.get("stdout") or out.get("output") or "")
        stderr = str(out.get("stderr") or "")
        if not stdout and not stderr and "content" in out:
            stdout = str(out.get("content") or "")
        return stdout, stderr, out
    if isinstance(resp, str):
        return resp, "", {
            "stdout": resp,
            "stderr": "",
            "interrupted": False,
            "isImage": False,
        }
    s = str(resp or "")
    return s, "", {
        "stdout": s,
        "stderr": "",
        "interrupted": False,
        "isImage": False,
    }


def _dump_dir(cwd: str) -> Path:
    root = Path(cwd or os.getcwd())
    d = root / ".claude" / "runtime" / "bash-dumps"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save_dump(cwd: str, session_id: str, cmd: str, text: str) -> Path:
    h = hashlib.sha1(f"{time.time_ns()}:{cmd[:80]}".encode()).hexdigest()[:10]
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", session_id or "nosession")[:40]
    path = _dump_dir(cwd) / f"{safe}-{h}.log"
    header = f"# cmd: {cmd[:500]}\n# chars: {len(text)}\n\n"
    path.write_text(header + text, encoding="utf-8", errors="replace")
    return path


def extract_signals(text: str, max_lines: int = EXTRACT_MAX_LINES) -> tuple[str, bool]:
    """Return (extract_text, good_enough) with fingerprint dedupe of spam lines."""
    lines = text.splitlines()

    # fingerprint -> {count, first_idx, sample_line}
    groups: dict[str, dict] = {}
    order: list[str] = []

    for i, line in enumerate(lines):
        if not _SIGNAL.search(line):
            continue
        fp = _fingerprint(line)
        if not fp:
            continue
        if fp not in groups:
            groups[fp] = {"count": 1, "first_idx": i, "sample": line.rstrip()}
            order.append(fp)
        else:
            groups[fp]["count"] += 1

    out: list[str] = []
    unique_kept = 0
    for fp in order:
        if unique_kept >= EXTRACT_MAX_UNIQUE:
            skipped = len(order) - unique_kept
            if skipped > 0:
                more = sum(groups[f]["count"] for f in order[unique_kept:])
                out.append(
                    f"… [{skipped} more unique signal patterns, {more} lines total — see full dump]"
                )
            break
        g = groups[fp]
        idx = g["first_idx"]
        # small context only for first occurrence
        for j in range(max(0, idx - EXTRACT_CONTEXT), min(len(lines), idx + EXTRACT_CONTEXT + 1)):
            if j == idx:
                continue
            ctx = lines[j].rstrip()
            if ctx and not _SIGNAL.search(ctx):
                # skip context that is itself another signal (will appear as own group)
                out.append(ctx)
        sample = g["sample"]
        if g["count"] > 1:
            out.append(f"{sample}  [×{g['count']} same]")
        else:
            out.append(sample)
        unique_kept += 1
        if len(out) >= max_lines:
            break

    # pytest / exit footer (unique lines only)
    footer = lines[-25:] if len(lines) > 25 else lines
    footer_added = 0
    for line in footer:
        if not (
            _SIGNAL.search(line)
            or line.startswith("=")
            or "passed" in line.lower()
            or "failed" in line.lower()
        ):
            continue
        fp = _fingerprint(line)
        # avoid re-adding spam already summarized
        if fp in groups and groups[fp]["count"] > 1:
            continue
        if line.rstrip() in out:
            continue
        out.append(line.rstrip())
        footer_added += 1
        if footer_added >= 8 or len(out) >= max_lines:
            break

    # hard char cap
    body_lines: list[str] = []
    size = 0
    for line in out:
        add = len(line) + 1
        if size + add > EXTRACT_MAX_CHARS and body_lines:
            body_lines.append(
                f"… [extract truncated at {EXTRACT_MAX_CHARS} chars; see full dump]"
            )
            break
        body_lines.append(line)
        size += add

    body = "\n".join(body_lines).strip()
    good = bool(body) and (
        unique_kept >= 1
        or bool(
            re.search(
                r"(?i)(failed|error|traceback|modbusexception|exit(_status)?=)",
                body,
            )
        )
    )
    return body, good


def _head_tail(text: str, head: int = HEAD, tail: int = TAIL) -> str:
    if len(text) <= MAX_CHARS:
        return text
    omitted = len(text) - head - tail
    return (
        text[:head]
        + f"\n\n… [truncated {omitted} chars] …\n\n"
        + text[-tail:]
    )


def _llm_enabled() -> bool:
    load_output_summary_env()
    return os.environ.get("PROJECT_OUTPUT_SUMMARY", "1").strip() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _llm_config() -> tuple[str, str, str, str | None]:
    load_output_summary_env()
    url = (
        os.environ.get("PROJECT_OUTPUT_SUMMARY_URL")
        or "http://localhost:20128/v1"
    ).rstrip("/")
    model = (
        os.environ.get("PROJECT_OUTPUT_SUMMARY_MODEL")
        or "free-stack"
    )
    fallback_raw = os.environ.get("PROJECT_OUTPUT_SUMMARY_FALLBACK_MODEL")
    if fallback_raw is None:
        fallback: str | None = "aug/claude-haiku-4.5"
    elif fallback_raw.strip() in {"", "0", "-", "off", "none"}:
        fallback = None
    else:
        fallback = fallback_raw.strip()
    key = os.environ.get("PROJECT_OUTPUT_SUMMARY_KEY") or ""
    if not key:
        key_file = Path(
            os.environ.get("PROJECT_OUTPUT_SUMMARY_KEY_FILE")
            or Path.home() / ".codex" / ".omniroute_key"
        ).expanduser()
        if key_file.is_file():
            key = key_file.read_text(encoding="utf-8").strip()
    return url, model, key, fallback


def _retry_settings() -> tuple[int, float, float]:
    load_output_summary_env()
    try:
        retries = max(1, int(os.environ.get("PROJECT_OUTPUT_SUMMARY_RETRIES", LLM_RETRIES)))
    except ValueError:
        retries = LLM_RETRIES
    try:
        timeout = float(os.environ.get("PROJECT_OUTPUT_SUMMARY_TIMEOUT", LLM_TIMEOUT_SEC))
    except ValueError:
        timeout = float(LLM_TIMEOUT_SEC)
    try:
        backoff = float(os.environ.get("PROJECT_OUTPUT_SUMMARY_BACKOFF", LLM_BACKOFF_SEC))
    except ValueError:
        backoff = LLM_BACKOFF_SEC
    return retries, timeout, backoff


def _http_chat(url: str, key: str, model: str, payload: dict, timeout: float) -> str | None:
    body = dict(payload)
    body["model"] = model
    req = urllib.request.Request(
        f"{url}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
            "Connection": "close",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    data = json.loads(raw)
    content = (
        ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    ).strip()
    return content or None


def _should_retry(exc: BaseException) -> bool:
    if isinstance(exc, TimeoutError):
        return True
    if isinstance(exc, urllib.error.HTTPError):
        # 408/429/5xx — retry; 4xx client errors — no
        return exc.code in {408, 425, 429} or exc.code >= 500
    if isinstance(exc, urllib.error.URLError):
        return True
    if isinstance(exc, (ConnectionError, BrokenPipeError, OSError)):
        return True
    if isinstance(exc, json.JSONDecodeError):
        return True
    return False


def llm_summarize(cmd: str, text: str, dump_path: Path) -> str | None:
    if not _llm_enabled():
        return None
    url, model, key, fallback = _llm_config()
    if not key:
        return None

    sample = text
    if len(sample) > LLM_INPUT_MAX:
        sample = (
            sample[: LLM_INPUT_MAX // 2]
            + "\n…\n"
            + sample[-LLM_INPUT_MAX // 2 :]
        )

    prompt = (
        "Сделай краткий summary лога для родительского coding-агента. "
        "Русский. Макс 25 коротких строк/буллетов. "
        "Только факты: exit/status, failed tests, ERROR/Exception file:line, "
        "корневые симптомы. Не выдумывай. Не предлагай rewrite всего. "
        f"Полный лог: {dump_path}\n"
        f"Команда: {cmd[:400]}\n"
        f"Лог:\n{sample}"
    )
    payload = {
        "messages": [
            {
                "role": "system",
                "content": "Ты сжатый суммаризатор логов. Только факты.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "max_tokens": 700,
        "stream": False,
    }

    retries, timeout, backoff = _retry_settings()
    models = [model]
    if fallback and fallback != model:
        models.append(fallback)

    last_err: str | None = None
    attempt = 0
    for m in models:
        for i in range(retries):
            attempt += 1
            try:
                content = _http_chat(url, key, m, payload, timeout)
                if content:
                    return content
                last_err = f"{m}: empty content"
            except Exception as exc:  # noqa: BLE001 — hook must never crash parent
                last_err = f"{m}: {type(exc).__name__}: {exc}"
                if not _should_retry(exc) or i >= retries - 1:
                    break
                time.sleep(backoff * (i + 1))
                continue
            # empty content — retry same model
            if i < retries - 1:
                time.sleep(backoff * (i + 1))
        # next fallback model
    if last_err and os.environ.get("PROJECT_OUTPUT_SUMMARY_DEBUG"):
        print(f"output-cap llm give-up after {attempt}: {last_err}", file=sys.stderr)
    return None


def build_view(cmd: str, combined: str, dump_path: Path) -> tuple[str, str]:
    """Return (stdout_for_model, mode_label)."""
    extract, good = extract_signals(combined)
    if good:
        view = (
            f"[output-cap:extract] full dump → {dump_path}\n"
            f"cmd: {cmd[:300]}\n\n"
            f"=== signal extract (deduped) ===\n{extract}\n"
        )
        # Do not append raw tail for spammy docker logs — reintroduces Modbus floods.
        # Only add a tiny pytest-style footer if extract has no repeat markers.
        if "[×" not in extract and re.search(r"(?i)pytest|FAILED|passed in", combined[-2000:] or ""):
            existing = set(extract.splitlines())
            footer = [
                ln
                for ln in combined.splitlines()[-12:]
                if (
                    _SIGNAL.search(ln)
                    or ln.startswith("=")
                    or "passed" in ln.lower()
                )
                and ln.rstrip() not in existing
            ]
            if footer:
                view += "\n=== footer ===\n" + "\n".join(footer[-8:]) + "\n"
        return view, "extract"

    summary = llm_summarize(cmd, combined, dump_path)
    if summary:
        return (
            f"[output-cap:llm-summary] full dump → {dump_path}\n"
            f"cmd: {cmd[:300]}\n\n"
            f"{summary}\n",
            "llm",
        )

    capped = _head_tail(combined)
    return (
        f"[output-cap:head-tail] full dump → {dump_path}\n"
        f"cmd: {cmd[:300]}\n\n"
        f"{capped}\n",
        "head-tail",
    )


def main() -> None:
    data = read_stdin()
    if data.get("tool_name") != "Bash":
        return

    cmd = str((data.get("tool_input") or {}).get("command") or "")
    resp = data.get("tool_response")
    stdout, stderr, shaped = _as_text(resp)
    combined = stdout if not stderr else f"{stdout}\n--- stderr ---\n{stderr}"
    total = len(combined)
    noisy = bool(_NOISY.search(cmd))
    soft = SOFT_NOISY if noisy else MAX_CHARS
    if total <= soft:
        return

    cwd = str(product_cwd(data.get("cwd") or os.getcwd()))
    session_id = data.get("session_id") or ""
    dump_path = _save_dump(cwd, session_id, cmd, combined)
    view, mode = build_view(cmd, combined, dump_path)

    shaped["stdout"] = view
    shaped["stderr"] = ""
    shaped.setdefault("interrupted", False)
    shaped.setdefault("isImage", False)

    emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "updatedToolOutput": shaped,
                "additionalContext": (
                    f"output-cap:{mode} ({total}→{len(view)} chars). "
                    f"Full: {dump_path}. "
                    "Prefer pytest -q --tb=line; docker logs --tail=80; rg dump."
                ),
            }
        }
    )


if __name__ == "__main__":
    main()
