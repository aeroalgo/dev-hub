from __future__ import annotations

from loop.runtime_adapters.base import SessionContext


def shared_collaboration_policy() -> str:
    return """## SHARED GATE COLLABORATION CONTRACT (HARD)
Этот контракт одинаков для всех runtime.
1. Перед FINISH IMPLEMENT/TASK/BUGFIX/QA запусти ровно один соответствующий gate-субагент: `verify-implement`, `verify-bugfix` или `verify-qa`; дождись завершения и учитывай только valid fenced JSON verdict.
2. Перед FINISH DECOMPOSE запусти `verify-decompose`; для ANALYZE fix используй `analyze-verify` по текущему workflow.
3. Если verify возвращает FAIL или BLOCKED, либо запуск verify завершается repairable runtime error, передай BLOCKERS в `gate-repair` с ALLOW WRITE + VERIFY, дождись repair и повтори тот же verify. Это автоматический repair-loop.
4. Не создавай finish/qa_pass без свежего PASS текущего gate-run, не выдумывай receipt/verdict и не редактируй runtime gate state вручную.
5. Если транспорт сабагента недоступен, зафиксируй blocker как repairable, повтори canonical spawn через adapter и затем запусти `gate-repair`; после ограниченных retry только NEED_HUMAN, но не ложный PASS.
"""


def claude_collaboration_block(ctx: SessionContext) -> str:
    return shared_collaboration_policy() + """
## CLAUDE CODE COLLABORATION ADAPTER (HARD)
1. Для субагентов используй Claude Code `Agent` с canonical `subagent_type`; для gate-run передавай packed BLOCKERS/ALLOW/VERIFY sections.
2. Дождись завершения `Agent` перед разбором verdict. Alias `verify`/`reviewer` разрешён только по общей карте gate-агентов.
3. Для FAIL/BLOCKED/runtime error вызови `Agent` с `subagent_type=gate-repair`, затем повтори исходный gate-agent.
"""


def codex_collaboration_block(ctx: SessionContext) -> str:
    return shared_collaboration_policy() + """
## CODEX NATIVE COLLABORATION ADAPTER (HARD)
Этот запуск выполняется через Codex CLI с включённым native `multi_agent`.
1. Для субагентов используй только нативную последовательность `spawn_agent` → `wait`.
2. `multi_agent_v1_spawn_agent` — устаревший идентификатор; его вызов запрещён.
3. Для managed child используй модель из `codex/agents.config.toml` (после materialize — из `.codex/agents/<agent>.toml`); root-модель (`PROJECT_LOOP_<PHASE>_MODEL` или CLI `--model`) от этого не меняй.
4. Для FAIL/BLOCKED/runtime error сначала повтори точный `spawn_agent`, затем передай blocker в `gate-repair` и снова запусти verify.
5. `reconcile-verify` не является частью обычного IMPLEMENT/BUGFIX/QA finish-chain. Запускай его только для явного текущего режима `BACK RECONCILE` и только с ALLOW READ текущего epic.
"""


def dsh_collaboration_block(ctx: SessionContext) -> str:
    return shared_collaboration_policy() + """
## DSH COLLABORATION ADAPTER (HARD)
Используй native механизм subagent текущего DSH-профиля и дождись его завершения; имена gate-агентов и repair-loop не меняются.
"""

