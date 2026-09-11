"""Runtime-neutral subagent contract adapter."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from loop.schemas.gate_verdict import GateVerdictRecord, SCHEMA_LOOP_GATE_VERDICT


_JSON_FENCE_RE = re.compile(r"```\s*json[^\n`]*\n(.*?)\n\s*```", re.DOTALL | re.IGNORECASE)

_GATE_JSON_HARD = (
    "HARD: prompt обязан содержать блок "
    "`GATE_IDENTITY session_id=<id> epic_id=<epic> step_id=<step>` "
    "(SoT; session_id/epic_id из него же в fence). "
    "HARD: финальный ответ содержит fenced ```json``` блок "
    '({"schema":"loop-gate-verdict/v1","agent_id":"<id>","verdict":"PASS|FAIL|BLOCKED",'
    '"step_id":"<step_id>","epic_id":"<epic_id>","session_id":"<session_id>",'
    '"recorded_at":"<iso8601>"}). '
    "Fence language = только `json` (FORBIDDEN info-string `json loop-gate-verdict/v1`). "
    "Schema id — поле `schema` внутри JSON. "
    "Перед emit подставь реальные agent_id/step_id/session_id/epic_id, "
    "один фактический verdict и текущий ISO 8601 recorded_at; "
    "литеральные плейсхолдеры и строка `PASS|FAIL|BLOCKED` запрещены. "
    "Перед emit (последний Bash, единственное исключение из Bash allowlist): "
    "`python harness/hooks/epic_resolve.py validate-boundary "
    "--schema-id loop-gate-verdict/v1 --json '…'` → `valid:true`; "
    "иначе правь по diagnostic_codes и повтори. "
    "Строка VERDICT: — optional human summary, не machine input. "
    "После последнего validate-boundary — только финальный отчёт, ноль tool calls. "
    "Ответ без valid JSON fence = протокольный FAIL."
)


UNIVERSAL_CONTRACTS: dict[str, str] = {
    "verify": (
        "CONTRACT verify: нужен ALLOW READ с implement yaml + decompose yaml. "
        "Checklist SoT = decompose (ac_quotes/out_of_scope/deletes); evidence = implement. "
        + _GATE_JSON_HARD
        + " Не edit. Без isolation=worktree. "
        "Канон: activeContext + decompose step + implement step."
    ),
    "verify-implement": (
        "CONTRACT verify-implement: нужен ALLOW READ с implement yaml + decompose yaml. "
        "Checklist SoT = decompose shard; evidence SoT = implement yaml; "
        "parent-packed AC+/AC−/§0.11/VERIFY не SoT. "
        + _GATE_JSON_HARD
        + " Не edit. Без isolation=worktree. "
        "Канон: activeContext + decompose step + implement step. "
        "HARD scope SoT = touch-ledger (runtime/.../touch-ledger.json), не whole-repo git. "
        "Сначала: `python3 harness/hooks/epic_resolve.py scope-check`. "
        "Empty ledger = оправдание (нет правок шага) → ignore scope/git dirty FAIL. "
        "Проверяй только ALLOW ∩ touched paths; чужой dirty вне ledger — ignore. "
        "FORBIDDEN: git status / whole-repo dirty как FAIL; discard foreign dirty."
    ),
    "verify-bugfix": (
        "CONTRACT verify-bugfix: нужен ALLOW READ с bugfix artifact "
        "`memory-bank/**/bugfix/**/bugfix-*.md`. "
        "Checklist SoT = bugfix artifact (Changes/Verification); "
        "parent-packed AC+/VERIFY не SoT. "
        + _GATE_JSON_HARD
        + " Не edit. Без isolation=worktree."
    ),
    "verify-qa": (
        "CONTRACT verify-qa: нужен Suite results · ALLOW READ · Frozen QA checklist. "
        "AC matrix SoT = freeze checklist_sha256; parent-packed AC вне freeze не SoT. "
        + _GATE_JSON_HARD
        + " Не pytest. Не Plan Mode / plan-файлы. Без isolation=worktree."
    ),
    "verify-decompose": (
        "CONTRACT verify-decompose: нужен ALLOW READ с plan.md + "
        "yaml/decompose-index.yaml (+ shards). "
        "Coverage SoT = ALLOW artifacts; packed COVERAGE/PLAN EXCERPT не SoT. "
        + _GATE_JSON_HARD
        + " FORBIDDEN pytest. Без isolation=worktree."
    ),
    "analyze-verify": (
        "CONTRACT analyze-verify: нужен FINDINGS · COVERAGE · ALLOW READ. "
        + _GATE_JSON_HARD
        + " Не edit. Не pytest. Без isolation=worktree."
    ),
    "verify-script": (
        "CONTRACT verify-script: нужен AC+ · AC− · §0.11 · VERIFY · ALLOW READ. "
        + _GATE_JSON_HARD
        + " Не edit. Без isolation=worktree."
    ),
    "verify-edit": (
        "CONTRACT verify-edit: нужен AC+ · AC− · §0.11 · VERIFY · ALLOW READ. "
        + _GATE_JSON_HARD
        + " Не edit. Без isolation=worktree."
    ),
    "verify-publish": (
        "CONTRACT verify-publish: нужен AC+ · AC− · §0.11 · VERIFY · ALLOW READ. "
        + _GATE_JSON_HARD
        + " Не edit. Без isolation=worktree."
    ),
    "reviewer": (
        "CONTRACT reviewer: нужен Suite results · ALLOW READ · Frozen QA checklist. "
        "AC matrix SoT = freeze; parent-packed AC вне freeze не SoT. "
        + _GATE_JSON_HARD
        + " Не pytest. Не Plan Mode / plan-файлы. Без isolation=worktree."
    ),
    "explorer": (
        "CONTRACT explorer: graphify first, затем узкий Grep/rg только внутри ALLOW из prompt. "
        "Budget: ≤12 Read · ≤6 Bash · re-read >1× FORBIDDEN. "
        "FORBIDDEN: repo-wide rg/find/ls; Read/search вне ALLOW без явной ссылки in Цель/shard/plan. "
        "Не edit. Не Plan Mode — только file:line отчёт на русском. "
        "Без isolation=worktree."
    ),
    "sunset-inventory": (
        "CONTRACT sunset-inventory: только чтение и as-built инвентаризация устаревшего кода в scope/ALLOW. "
        "HARD: финальный ответ содержит fenced ```json``` блок "
        '({"schema":"loop-sunset-inventory/v1",...items...}). '
        "Fence language = только `json`; schema id внутри JSON. "
        "Перед emit: validate-boundary --schema-id loop-sunset-inventory/v1. "
        "Правила: mark=REPLACE, excerpt≤40 строк. "
        "FORBIDDEN: design/HOW предложения, dual-path, edit/write, Plan Mode. Без isolation=worktree."
    ),
    "gate-repair": (
        "CONTRACT gate-repair: нужен BLOCKERS · ALLOW WRITE · VERIFY. "
        "BLOCKERS только `- <id> | <path> | <concrete_fix>` (path ∈ ALLOW WRITE). "
        "HARD: prompt содержит `GATE_IDENTITY session_id=<id> epic_id=<epic> step_id=<step>` "
        "(SoT; parent_evidence_id / context из него же). "
        "HARD: финальный ответ содержит fenced ```json``` блок "
        '({"schema":"loop-repair-result/v1","status":"done|partial|fail",...}). '
        "Fence language = только `json`. "
        "Перед emit: `python harness/hooks/epic_resolve.py validate-boundary "
        "--schema-id loop-repair-result/v1 --json '…'` → `valid:true`. "
        "Write/Edit только ALLOW WRITE; чини ровно path|fix из BLOCKERS. "
        "После fix — команда из VERIFY. "
        "FORBIDDEN: spawn Agent/verify, FINISH, finalize-step, угадывание path, "
        "правки вне ALLOW WRITE, status=done при незакрытых blockers. "
        "Ответ без JSON fence = status fail."
    ),
    "reconcile-verify": (
        "CONTRACT reconcile-verify: read-only reconciliation gate. Проверь только ALLOW READ: "
        "activeContext.md, текущий decompose plan/index.yaml, текущий implement/qa artifact "
        "и runtime diagnostics. Укажи каждый drift как file:line → observed → canonical → next action. "
        "Не редактируй исходные plan/decompose/implement/code; единственная допустимая запись — "
        "reconcile artifact через canonical CLI. Не запускай Agent, не создавай gate verdict "
        "и не утверждай repair/pass. "
        "Без isolation=worktree."
    ),
}

CONTRACTS_SHA256: dict[str, str] = {
    agent_id: hashlib.sha256(contract.encode("utf-8")).hexdigest()
    for agent_id, contract in UNIVERSAL_CONTRACTS.items()
}


@dataclass(frozen=True)
class AgentContractAdapter:
    """Apply the same subagent contract at any runtime transport boundary."""

    runtime_id: str = "universal"

    def contract(self, agent_id: str | None) -> str:
        return UNIVERSAL_CONTRACTS.get(str(agent_id or "").strip(), "")

    def contract_hash(self, agent_id: str | None) -> str | None:
        return CONTRACTS_SHA256.get(str(agent_id or "").strip())

    def check_drift(self, agent_id: str | None) -> tuple[bool, str]:
        normalized = str(agent_id or "").strip()
        contract = self.contract(normalized)
        if not normalized or not contract:
            return True, ""
        expected = self.contract_hash(normalized)
        actual = hashlib.sha256(contract.encode("utf-8")).hexdigest()
        if expected and actual != expected:
            return False, (
                f"agent_contract_drift: CONTRACTS['{normalized}'] sha256 mismatch "
                f"(actual={actual}, expected={expected})"
            )
        return True, ""

    @staticmethod
    def extract_json_fence(text: str | None) -> dict[str, Any] | None:
        if not isinstance(text, str):
            return None
        last: dict[str, Any] | None = None
        for match in _JSON_FENCE_RE.finditer(text):
            try:
                data = json.loads(match.group(1))
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(data, dict):
                last = data
        return last

    @staticmethod
    def validate_gate_verdict(payload: dict[str, Any]) -> Any:
        from loop.validate_boundary import validate_boundary

        return validate_boundary(SCHEMA_LOOP_GATE_VERDICT, payload)

    def parse_gate_verdict(self, text: str | None) -> GateVerdictRecord | None:
        payload = self.extract_json_fence(text)
        if not payload:
            return None
        result = self.validate_gate_verdict(payload)
        if not result.valid:
            return None
        try:
            return GateVerdictRecord.model_validate(payload)
        except Exception:
            return None


def get_agent_contract_adapter(runtime_id: str | None = None) -> AgentContractAdapter:
    """Return the runtime-neutral contract adapter for Claude, Codex, or DSH."""
    return AgentContractAdapter(runtime_id=(str(runtime_id or "universal").strip().lower() or "universal"))
