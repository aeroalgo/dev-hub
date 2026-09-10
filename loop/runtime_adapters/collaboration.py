from __future__ import annotations

from loop.runtime_adapters.base import SessionContext


def _phase_base(phase: str | None) -> str:
    tokens = [t for t in str(phase or "").upper().split() if t]
    return tokens[-1] if tokens else ""


def shared_collaboration_policy(*, phase: str | None = None) -> str:
    phase_u = _phase_base(phase)
    if phase_u == "QA":
        return """## SHARED GATE COLLABORATION CONTRACT — QA (HARD)
Этот контракт одинаков для всех runtime.
0. Следуй блоку `QA outcome classifier` в prompt (schema `loop-qa-outcome/v1`) — это runner SoT.
1. Ровно **один** suite по `suite_command` из classifier: `bin/pytest -q --tb=line`. FORBIDDEN: повторный full suite, смена `--tb`, `python -m pytest`, targeted вместо suite, thrash-перезапуски.
2. Если suite red, runtime сломан, AC/plan не сходятся, или есть **eligible** blockers → **не** вызывай `verify-qa` и **не** вызывай `gate-repair`. Запиши `qa-*.yaml` с `verdict: fail|blocked`, Handoff `* BUGFIX`, `mb-finish qa`, останови turn. Чинить продукт в QA-сессии запрещено.
3. Если suite green и plan/AC ок → ровно один `verify-qa` (в prompt обязательно `agent_type: verify-qa`). Pack AC = **Frozen QA checklist** 1:1 (anti-ratchet: не усиливать wording). Дождись valid fenced JSON verdict.
4. `verify-qa` PASS (включая PASS с ineligible residuals) → `mb-finish qa` (epic done / DONE). `verify-qa` FAIL/BLOCKED с eligible B* → тот же путь что п.2: qa-*.yaml fail/blocked → BUGFIX, **без** repair-loop и без повторного suite в этом run. Style/naming/comments/«строже plan» → **не** BUGFIX.
5. `gate-repair` в QA запрещён для product/AC дефектов. Он допустим только если сам spawn/wait transport verify-qa сломан (unsupported tool / empty wait) — один retry canonical spawn, иначе NEED_HUMAN.
6. Не создавай `qa_pass`/finish без свежего PASS текущего verify-qa на green path; не выдумывай receipt.
"""
    return """## SHARED GATE COLLABORATION CONTRACT (HARD)
Этот контракт одинаков для всех runtime.
1. Перед FINISH IMPLEMENT/TASK/BUGFIX запусти ровно один соответствующий gate-субагент: `verify-implement` или `verify-bugfix`; дождись завершения и учитывай только valid fenced JSON verdict. В spawn prompt всегда пиши `agent_type: <canonical>`.
2. Перед FINISH DECOMPOSE запусти `verify-decompose`; для ANALYZE fix используй `analyze-verify` по текущему workflow.
3. Если verify возвращает FAIL или BLOCKED, либо запуск verify завершается repairable runtime error, передай BLOCKERS в `gate-repair` с ALLOW WRITE + VERIFY, дождись repair и повтори тот же verify. Это автоматический repair-loop.
4. Лимит repair-loop: максимум **2** цикла `gate-repair → re-verify` на один parent-run. После 2-го FAIL/BLOCKED — **не** NEED_HUMAN и **не** начинай 3-й repair в этом run: заверши сессию с retryable outcome на тот же шаг (runner перезапустит). Не изобретай новые nitpick-blockers.
5. Для `gate-repair` в VERIFY передавай **targeted** pytest по файлам из ALLOW WRITE (path/nodeid/`-k`). Полный `bin/pytest -q --tb=line` — только parent в QA; не требуй full suite внутри `gate-repair`.
6. Не создавай finish без свежего PASS текущего gate-run, не выдумывай receipt/verdict и не редактируй runtime gate state вручную.
7. Если транспорт сабагента недоступен, зафиксируй blocker как repairable, повтори canonical spawn через adapter и затем запусти `gate-repair`; после ограниченных retry только NEED_HUMAN, но не ложный PASS.
"""


def claude_collaboration_block(ctx: SessionContext) -> str:
    return shared_collaboration_policy(phase=ctx.phase) + """
## CLAUDE CODE COLLABORATION ADAPTER (HARD)
1. Для субагентов используй Claude Code `Agent` с canonical `subagent_type`; для gate-run передавай packed BLOCKERS/ALLOW/VERIFY sections.
2. Дождись завершения `Agent` перед разбором verdict. Alias `verify`/`reviewer` разрешён только по общей карте gate-агентов.
3. Вне QA: для FAIL/BLOCKED/runtime error вызови `Agent` с `subagent_type=gate-repair`, затем повтори исходный gate-agent. В QA следуй QA-контракту выше (BUGFIX path, не repair-loop).
"""


def codex_collaboration_block(ctx: SessionContext) -> str:
    return shared_collaboration_policy(phase=ctx.phase) + """
## CODEX NATIVE COLLABORATION ADAPTER (HARD)
Этот запуск выполняется через Codex CLI с включённым native `multi_agent`.
1. Для субагентов используй только каноническую последовательность `multi_agent_v1.spawn_agent` → `multi_agent_v1.wait`; transport adapter принимает также flat aliases и нормализует их до dispatch.
2. Root-модель (`PROJECT_LOOP_<PHASE>_MODEL` или CLI `--model`) может быть произвольной. Child получает managed model из Codex agent config.
3. Для managed child используй модель из `codex/agents.config.toml` (после materialize — из `.codex/agents/<agent>.toml`); модель child не наследуй из root без явного override.
4. В первой строке spawn prompt обязательно `agent_type: <canonical>` (`verify-qa`, `verify-bugfix`, `verify-implement`, `gate-repair`). Без этого label станет unknown.
5. Вне QA: для FAIL/BLOCKED/runtime error сначала повтори точный `spawn_agent`, затем передай blocker в `gate-repair` и снова запусти verify. В QA — BUGFIX path по QA-контракту, не product repair-loop.
6. `reconcile-verify` не является частью обычного IMPLEMENT/BUGFIX/QA finish-chain. Запускай его только для явного текущего режима `BACK RECONCILE` и только с ALLOW READ текущего epic.
"""


def dsh_collaboration_block(ctx: SessionContext) -> str:
    return shared_collaboration_policy(phase=ctx.phase) + """
## DSH COLLABORATION ADAPTER (HARD)
Используй native механизм subagent текущего DSH-профиля и дождись его завершения; имена gate-агентов и repair-loop не меняются. В QA следуй QA-контракту (один suite → BUGFIX или один verify-qa).
"""
