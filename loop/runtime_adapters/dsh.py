from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import os
import shutil
import subprocess
import sys
from loop.runtime_adapters.base import (
    AUTH_BANNED_PATTERNS,
    RuntimeAdapter,
    RuntimePreparationResult,
    SessionAnalysis,
    SessionContext,
)


_REQUESTED_MODEL_RE = re.compile(
    r"\brequested[ _-]model\s*[:=]\s*[\"']?([^\s,;|\"']+)",
    re.IGNORECASE,
)
_ACTUAL_MODEL_RE = re.compile(
    r"\bactual[ _-]model\s*[:=]\s*[\"']?([^\s,;|\"']+)",
    re.IGNORECASE,
)
_MODEL_KEYS = ("requested_model", "actual_model")


def _normalize_model_id(value: str | None) -> str:
    model = (value or "").strip().lower()
    if not model:
        return ""
    model = re.sub(r"\[\d+m\]$", "", model)
    if "/" in model:
        model = model.rsplit("/", 1)[-1]
    return model


def _models_equivalent(left: str | None, right: str | None) -> bool:
    normalized_left = _normalize_model_id(left)
    normalized_right = _normalize_model_id(right)
    if not normalized_left or not normalized_right:
        return True
    return (
        normalized_left == normalized_right
        or normalized_left in normalized_right
        or normalized_right in normalized_left
    )


def _model_pair_from_mapping(value: Any) -> tuple[str, str] | None:
    if not isinstance(value, dict):
        return None
    requested = value.get(_MODEL_KEYS[0])
    actual = value.get(_MODEL_KEYS[1])
    if not isinstance(requested, str) or not isinstance(actual, str):
        return None
    requested = requested.strip()
    actual = actual.strip()
    return (requested, actual) if requested and actual else None


def _model_pair_from_text(value: str) -> tuple[str, str] | None:
    requested = _REQUESTED_MODEL_RE.search(value)
    actual = _ACTUAL_MODEL_RE.search(value)
    if not requested or not actual:
        return None
    return requested.group(1).strip(), actual.group(1).strip()


def _dsh_model_pairs(raw_log: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for line in raw_log.splitlines():
        try:
            event: Any = json.loads(line)
        except (TypeError, ValueError):
            event = None
        if isinstance(event, dict):
            candidates = [event]
            nested_event = event.get("event")
            if isinstance(nested_event, dict):
                candidates.append(nested_event)
            for candidate in candidates:
                pair = _model_pair_from_mapping(candidate)
                if pair:
                    pairs.append(pair)
                for key in ("content", "result"):
                    content = candidate.get(key)
                    if isinstance(content, str):
                        pair = _model_pair_from_text(content)
                        if pair:
                            pairs.append(pair)
                        try:
                            content_data = json.loads(content)
                        except (TypeError, ValueError):
                            content_data = None
                        pair = _model_pair_from_mapping(content_data)
                        if pair:
                            pairs.append(pair)
        pair = _model_pair_from_text(line)
        if pair:
            pairs.append(pair)
    return pairs


DSH_MISSING_EXIT = 127


def _build_dsh_command(
    profile: str, prompt: str, dsh_bin: str = "dsh"
) -> list[str]:
    return [dsh_bin, "--profile", profile, prompt]


def _normalize_dsh_log(raw_log: str) -> str:
    extracted: list[str] = []
    for line in raw_log.splitlines():
        try:
            event: Any = json.loads(line)
        except (TypeError, ValueError):
            return raw_log
        if not isinstance(event, dict):
            return raw_log
        event_type = event.get("type")
        nested_event = event.get("event")
        if isinstance(nested_event, dict):
            event_type = nested_event.get("type", event_type)
            content = nested_event.get("content")
        else:
            content = event.get("content", event.get("result"))
        if event_type in {"session_end", "result"} and isinstance(content, str):
            extracted.append(content)
    return "\n".join(extracted) if extracted else raw_log


_DSH_TRANSIENT_PATTERNS = (
    re.compile(r"(?i)429\s*Too\s*Many\s*Requests"),
    re.compile(r"(?i)503\s*Service\s*Unavailable"),
    re.compile(r"(?i)5[0-9]{2}\s+(?:Server|Service|Gateway)\s+Error"),
    re.compile(r"(?i)Connection\s+(?:refused|reset|timed?\s*out)"),
    re.compile(r"(?i)(?:api[_ ]error|api error).*empty response"),
)

_DSH_PERMANENT_PATTERNS = AUTH_BANNED_PATTERNS + (
    re.compile(r"(?i)API\s+Error:\s*terminated"),
    re.compile(r"(?i)API\s+Error:\s*overloaded"),
    re.compile(r"(?i)API\s+Error:.*rate.?limit"),
    re.compile(r"(?i)Authentication\s+(?:failed|error|invalid)"),
    re.compile(r"(?i)Invalid\s+API\s+key"),
)

_STRUCTURED_MODEL_SUBSTITUTION_RE = re.compile(
    r"(?i)model_substitution:\s*requested=\S+\s+actual=\S+"
)


def is_structured_model_substitution_reason(reason: str | None) -> bool:
    return bool(reason and _STRUCTURED_MODEL_SUBSTITUTION_RE.search(reason))


def _match_patterns(text: str, patterns: tuple[re.Pattern, ...]) -> str | None:
    for pat in patterns:
        m = pat.search(text)
        if m:
            return m.group(0)
    return None


def detect_dsh_abort_in_log(text: str) -> str | None:
    transient = _match_patterns(text or "", _DSH_TRANSIENT_PATTERNS)
    if transient:
        return f"dsh_transient: {transient}"
    permanent = _match_patterns(text or "", _DSH_PERMANENT_PATTERNS)
    if permanent:
        return f"dsh_permanent: {permanent}"
    return None


def _detect_dsh_session_complete(text: str) -> bool:
    last_nonempty = ""
    for line in (text or "").splitlines():
        normalized = line.strip()
        if not normalized:
            continue
        last_nonempty = normalized
        try:
            event = json.loads(normalized)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        candidates = [event]
        nested = event.get("event")
        if isinstance(nested, dict):
            candidates.append(nested)
        for item in candidates:
            if item.get("type") == "session_end" and item.get("status") == "completed":
                return True
    return bool(re.search(r"(?i)(?:FINISH|END)\s*$", last_nonempty))


def detect_dsh_model_mismatch(
    raw_log: str, expected_model: str | None
) -> str | None:
    """Return a fail-closed reason for an explicit DSH model substitution."""
    expected = _normalize_model_id(expected_model)
    if not expected:
        return None
    for requested, actual in _dsh_model_pairs(raw_log):
        if not _models_equivalent(requested, actual) and _models_equivalent(
            requested, expected
        ):
            return (
                f"model_substitution: requested={requested} actual={actual} "
                "(dsh model mismatch; refuse silent downgrade)"
            )
    return None

_detect_dsh_model_mismatch = detect_dsh_model_mismatch


class DshAdapter(RuntimeAdapter):
    """RuntimeAdapter implementation wrapping existing DSH functions."""

    def resolve_binary(self, hub_root: Path | None = None) -> list[str] | None:
        if os.environ.get("DSH_BIN") and os.access(os.environ["DSH_BIN"], os.X_OK):
            return [os.environ["DSH_BIN"]]

        root = Path(hub_root) if hub_root else Path(__file__).resolve().parents[2]
        resolver = os.environ.get("DSH_RESOLVER") or (root / "dsh" / "bin" / "which-dsh.sh")
        if Path(resolver).exists() and os.access(str(resolver), os.X_OK):
            try:
                res = subprocess.run(
                    [str(resolver)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if res.returncode == 0:
                    lines = [l.strip() for l in res.stdout.splitlines() if l.strip()]
                    if lines:
                        exe = lines[0]
                        if "/" not in exe:
                            resolved_which = shutil.which(exe)
                            if resolved_which:
                                exe = resolved_which
                        return [exe] + lines[1:]
            except Exception:
                pass

        which_dsh = shutil.which("dsh")
        if which_dsh:
            return [which_dsh]

        return None

    def validate_profile(
        self,
        profile: str,
        hub_root: Path | None = None,
        dsh_home: Path | None = None,
    ) -> bool:
        if not profile or not isinstance(profile, str):
            return False
        root = Path(hub_root) if hub_root else Path(__file__).resolve().parents[2]
        repo_profile = root / "dsh" / "profiles" / profile
        if repo_profile.exists() and repo_profile.is_dir():
            return True
        home = Path(dsh_home) if dsh_home else Path(os.environ.get("DSH_HOME", Path.home() / ".dsh"))
        home_profile = home / "profiles" / profile
        if home_profile.exists() and home_profile.is_dir():
            return True
        # Allow default epic profiles by convention
        if profile in {
            "epic-plan",
            "epic-implement",
            "epic-creative",
            "epic-reflect",
            "epic-bugfix",
            "epic-decompose",
            "epic-analyze",
            "epic-qa",
            "epic-audit",
        }:
            return True
        return False

    def ensure_profiles(
        self,
        hub_root: Path | None = None,
        dsh_home: Path | None = None,
    ) -> RuntimePreparationResult:
        if os.environ.get("DSH_PROFILES_READY") == "1":
            return RuntimePreparationResult(ok=True)

        root = Path(hub_root) if hub_root else Path(__file__).resolve().parents[2]
        installer = os.environ.get("DSH_PROFILE_INSTALLER") or (root / "dsh" / "scripts" / "install-profiles.sh")
        hooks_installer = os.environ.get("DSH_HOOKS_INSTALLER") or (root / "dsh" / "scripts" / "install-cc-hooks.sh")

        if not Path(installer).exists() or not os.access(str(installer), os.X_OK):
            return RuntimePreparationResult(
                ok=False,
                exit_code=127,
                error=f"dsh profile installer not found or not executable: {installer}",
            )
        if not Path(hooks_installer).exists() or not os.access(str(hooks_installer), os.X_OK):
            return RuntimePreparationResult(
                ok=False,
                exit_code=127,
                error=f"dsh hooks installer not found or not executable: {hooks_installer}",
            )

        env = os.environ.copy()
        if dsh_home:
            env["DSH_HOME"] = str(dsh_home)

        res1 = subprocess.run([str(installer)], env=env, check=False)
        if res1.returncode != 0:
            return RuntimePreparationResult(
                ok=False,
                exit_code=res1.returncode,
                error=f"dsh profile installation failed (exit={res1.returncode})",
            )
        res2 = subprocess.run([str(hooks_installer)], env=env, check=False)
        if res2.returncode != 0:
            return RuntimePreparationResult(
                ok=False,
                exit_code=res2.returncode,
                error=f"dsh hooks installation failed (exit={res2.returncode})",
            )

        os.environ["DSH_PROFILES_READY"] = "1"
        return RuntimePreparationResult(ok=True)

    def resolve_working_directory(
        self,
        project_root: Path,
        hub_root: Path,
        ctx: SessionContext | None = None,
    ) -> Path:
        return Path(project_root)

    def requires_stdin_prompt(self, mode: str = "headless") -> bool:
        return False

    def progress_mode(self) -> str:
        return "stream_bytes"

    def resolve_stream_filter(self, hub_root: Path) -> list[str] | None:
        filter_path = Path(hub_root) / "harness" / "hooks" / "dsh_stream_filter.py"
        if filter_path.exists():
            return [sys.executable, str(filter_path)]
        return None

    def prepare_runtime(
        self,
        hub_root: Path,
        project_root: Path,
        extras: dict[str, Any] | None = None,
    ) -> RuntimePreparationResult:
        bin_cmd = self.resolve_binary(hub_root)
        if not bin_cmd:
            return RuntimePreparationResult(
                ok=False,
                exit_code=127,
                error="dsh binary not found; set DSH_BIN or install @deepseek-ai/dsh",
            )

        profile = (extras or {}).get("dsh_profile") or "epic-implement"
        if not self.validate_profile(profile, hub_root):
            return RuntimePreparationResult(
                ok=False,
                exit_code=127,
                error=f"invalid dsh profile '{profile}'; profile not found",
            )

        prof_res = self.ensure_profiles(hub_root)
        if not prof_res.ok:
            return prof_res

        return RuntimePreparationResult(ok=True, command=bin_cmd)

    def build_command(self, ctx: SessionContext) -> list[str]:
        profile = ctx.extras.get("dsh_profile") or f"epic-{ctx.phase.lower()}"
        dsh_bin = (
            ctx.extras.get("dsh_command")
            or self.resolve_binary(ctx.extras.get("hub_root"))
            or ["dsh"]
        )
        cmd = list(dsh_bin) + ["--profile", profile, ctx.prompt]
        extra_args = ctx.extras.get("extra_args")
        if extra_args:
            if isinstance(extra_args, (list, tuple)):
                cmd.extend(list(extra_args))
        return cmd

    def analyze_log(self, raw_log: str, ctx: SessionContext) -> SessionAnalysis:
        reason = (
            _detect_dsh_model_mismatch(raw_log, ctx.model)
            or detect_dsh_abort_in_log(raw_log)
        )
        if "exit_code" in ctx.extras:
            exit_code = ctx.extras["exit_code"]
            if not reason and exit_code in (0, None) and not _detect_dsh_session_complete(raw_log):
                reason = "dsh incomplete FINISH"
            elif not reason and exit_code not in (0, None):
                reason = f"dsh process exit={exit_code}"

        dsh_abort_kind = None
        if reason and reason.startswith("dsh_transient:"):
            dsh_abort_kind = "transient"
        elif reason and (
            reason.startswith("dsh_permanent:")
            or is_structured_model_substitution_reason(reason)
        ):
            dsh_abort_kind = "fatal"
        elif reason:
            dsh_abort_kind = "unknown"

        normalized = _normalize_dsh_log(raw_log)
        struct_out = {"log": normalized} if normalized != raw_log else None

        return SessionAnalysis(
            reason=reason,
            dsh_abort_kind=dsh_abort_kind,
            structured_output=struct_out,
        )

    def prepare_extras(self, ctx: SessionContext) -> dict[str, Any]:
        return {"dsh_profile": f"epic-{ctx.phase.lower()}"}

    def collaboration_block(self, ctx: SessionContext) -> str:
        from loop.runtime_adapters.collaboration import dsh_collaboration_block
        return dsh_collaboration_block(ctx)

    def parse_session_events(self, raw_log: str, ctx: SessionContext) -> Any:
        from loop.runtime.session_events import parse_session_events
        return parse_session_events(raw_log, ctx.runtime_id)

    def resolve_session_close_identity(self, state: dict[str, Any]) -> Any:
        from loop.session_finalize import resolve_session_close_identity

        return resolve_session_close_identity(state)

    def ownership_expected_step(self, state: dict[str, Any]) -> str:
        from loop.session_finalize import ownership_expected_step

        return ownership_expected_step(state)

    def apply_ownership_identity(self, identity: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        from loop.session_finalize import apply_ownership_identity

        return apply_ownership_identity(identity, state)

    def should_probe_analyze_promotion(self, *, armed_step: Any, active_context_text: str | None = None) -> bool:
        from loop.session_finalize import should_probe_analyze_promotion

        return should_probe_analyze_promotion(
            armed_step=armed_step,
            active_context_text=active_context_text,
        )

    def post_session(self, cwd: Any, log_path: Any, ctx: SessionContext) -> list[dict[str, Any]]:
        return []
