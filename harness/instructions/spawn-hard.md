# HARD — Shared agent collaboration contract

Этот файл — общая политика gate/subagent для Claude Code, Codex, DSH и loop.
Runtime adapter добавляет только транспортный dialect запуска и ожидания
субагента; он не меняет карту gate-агентов, repair-loop или finish-инварианты.

Parent **MAY** spawn любых Agent по нужде.  
**Обязательные** gate’ы (когда agent enabled в scope): **explorer** (codebase search) · **verify** (pre-FINISH) · **reviewer** (BACK QA).

| `subagent_type` | Phase / Когда | Обязателен? | Alias compatibility |
|-----------------|---------------|-------------|---------------------|
| `explorer` | codebase search / discovery в code-режимах | **да**, если `MODEL_LOOP=1` (иначе parent: graphify + узкий rg) | — |
| `verify-implement` | IMPLEMENT / REFACTOR / TASK pre-FINISH (`code_changed: yes`) | **да** (если gate active в loop) | `@verify` |
| `verify-bugfix` | BUGFIX pre-FINISH (`code_changed: yes`) | **да** (если gate active в loop) | `@verify` |
| `bugfix-fix` | BUGFIX swarm — fix **one** queue item | **да** (parent spawn ≤3 parallel) | `@bugfix-fix`, `bugfix` |
| `context-sync` | QA pass — root canon sync + `sync-*.md` | **да** after verify-qa PASS | `@context-sync`, `ctx-sync` |
| `analyze-verify` | Internal DECOMPOSE closure gate | **да** after analyze-*.yaml | — |
| `verify-qa` | BACK/FRONT QA после suite | **да** (если gate active в loop) | `@reviewer` |
| `verify-decompose` | DECOMPOSE structural gate | **да** (если gate active в loop) | — |
| `gate-repair` | после `@verify-*` FAIL/BLOCKED **или actionable QA contract finding** | **да** (если enabled в loop) | — |
| `sunset-inventory` | discovery / scan sunset targets (legacy fallbacks, dual-paths, shims) | **да** (если shard `sunset_scope.required: true`) | `@sunset-inventory`, `sunset` |
| `verify` (alias) | pre-FINISH IMPLEMENT / BUGFIX | legacy alias → `verify-implement` / `verify-bugfix` | `@verify` |
| `reviewer` (alias) | BACK QA | legacy alias → `verify-qa` | `@reviewer` |
| built-in / др. | когда parent считает нужным | нет | — |

## Phase → Expected Verify Agent Map

| Phase / Role Mode | Expected Agent | Fallback / Alias |
|-------------------|----------------|------------------|
| BACK/FRONT IMPLEMENT | `verify-implement` | `verify` |
| BACK/FRONT REFACTOR | `verify-implement` | `verify` |
| BACK/FRONT TASK | `verify-implement` | `verify` |
| BACK/FRONT BUGFIX | `verify-bugfix` (pre-FINISH) + `bugfix-fix`×≤3 (swarm) | `verify` / `bugfix` |
| BACK/FRONT QA | `verify-qa` + `context-sync` (after PASS) | `reviewer` / `ctx-sync` |
| BACK/FRONT DECOMPOSE | `verify-decompose` + `analyze-verify` | — |

## Политика

| Режим | Поведение |
|-------|-----------|
| IMPLEMENT · REFACTOR · BUGFIX · TASK (code) | перед широким поиском → **`@explorer`**, если managed search agent включён; иначе graphify + узкий rg parent |
| Shard с `sunset_scope.required: true` | перед первым prod Write нового SoT → **`@sunset-inventory`** (`subagent_type=sunset-inventory` или alias `sunset`), scan sunset targets → fenced JSON `loop-sunset-inventory/v1` |
| Перед FINISH (`code_changed: yes` IMPLEMENT/REFACTOR/TASK) | **`@verify-implement` ОБЯЗАТЕЛЬНО** (`ALLOW READ`: implement yaml + decompose yaml + code; checklist SoT = decompose; alias `@verify`); FAIL/DENY → fix → retry до PASS; после PASS — не повторять |
| BUGFIX work | parent **spawn `bugfix-fix`≤3** (1 item / child, disjoint files); затем **`@verify-bugfix`** |
| Перед FINISH (`code_changed: yes` BUGFIX) | **`@verify-bugfix` ОБЯЗАТЕЛЬНО** (`ALLOW READ` с bugfix queue + report; queue SoT статусов, report SoT Changes/Verification; alias `@verify`); FAIL/DENY → fix → retry до PASS |
| Перед DECOMPOSE promotion | **`@verify-decompose` ОБЯЗАТЕЛЬНО** (`ALLOW READ`: plan.md + decompose-index.yaml; coverage SoT = shards); PASS оставляет parent в DECOMPOSE |
| После `@verify-*` VERDICT: FAIL или QA contract finding | **`@gate-repair` ОБЯЗАТЕЛЬНО**; repair → retry тот же verify/QA до PASS |
| Перед DECOMPOSE promotion (closure check) | **`@analyze-verify`** после analyze-*.yaml; FAIL → `@gate-repair` → retry; PASS → атомарно продвигает DECOMPOSE и завершает parent |
| После verify-qa PASS | **`@context-sync` ОБЯЗАТЕЛЬНО** → `sync-*.md`; `done` атомарно закрывает QA (parent не вызывает finish) |
| BACK/FRONT QA после suite | **`@verify-qa` ОБЯЗАТЕЛЬНО** (Suite results + ALLOW + Frozen checklist; alias `@reviewer`); pytest — у parent |
| Любой режим | доп. Agent — свободно |

### Generic registry policy

`*_MODEL` — только модель. `*_MODEL_CHAT` / `*_MODEL_LOOP` — **только** boolean selectors (0/1), не model id. Absent selector → `loop=1`, `chat=0`. Disabled → `scope_disabled` / bypass; invalid required gate → fail-closed.

**Search scope (общее):** default = текущий scope шага (ALLOW в prompt). Другие каталоги — **только если действительно нужны** и путь есть в shard/consumes/plan/checkpoint. Широкий repo search «на всякий случай» = FAIL.

**FAIL:** FINISH без `verify-implement`/`verify-bugfix` когда `code_changed: yes`.  
**FAIL:** `@verify-implement` / `@verify-bugfix` повторно после `VERDICT: PASS` (retry только при `FAIL` / spawn DENY).  
**FAIL:** BACK QA FINISH без `Agent`→`verify-qa` (или alias `reviewer`).  
**FAIL:** code-режим сделал широкий codebase search без предшествующего `Agent`→`explorer` в сессии (кроме исключения выше).  
**FAIL:** `isolation=worktree` / `model=` на verify|reviewer|explorer — hooks снимают.  
**FAIL:** spawn `verify-implement`/`verify` без `ALLOW READ` или без implement+decompose yaml paths в ALLOW / path нет на диске; spawn `verify-bugfix` без bugfix queue + report paths; spawn `verify-decompose` без plan.md + decompose-index.yaml; spawn `verify-qa`/`reviewer` без Suite results / ALLOW / freeze; spawn gate-repair без обязательных секций / ALLOW = дерево / >max файлов (10 default; 40 verify-qa) / globs `**` в ALLOW.
**FAIL:** verify-qa fail-fast (FAIL до полного AC+/AC−/§0.11) или partial `## BLOCKERS (complete)`.
  ├─ verify FAIL/BLOCKED/runtime error или QA contract blocker → parent @gate-repair (`- id | path | fix` + ALLOW WRITE + VERIFY) → retry same verify/QA contract
  ├─ gate-repair fail → parent расширяет ALLOW WRITE / уточняет path|fix или чинит сам → retry
Hooks: `stop-gate` блокирует FINISH при verify FAIL/BLOCKED или actionable QA contract finding; `agent-pretool` DENY `@gate-repair` без prior repairable gate blocker; DENY `@verify` если уже PASS.
**FAIL:** `@gate-repair` с голыми blocker id без `| path | fix` или path ∉ ALLOW WRITE.

**FAIL:** «проверь шаг» / QA review / search без секций (для `verify-implement` — без ALLOW READ + обоих yaml).  
**FAIL:** `ALLOW READ` = дерево / glob `dir/**` (нужны конкретные пути файлов; ≤10 default, ≤40 для verify-qa/reviewer).
   **FAIL:** секции без перевода строки / без этих заголовков.

## Codex / parent spawn (HARD)

- `spawn_agent` для gate: `agent_type`/`subagent_type` = canonical gate id **и** `fork_context=false` (self-contained prompt с GATE_IDENTITY + ALLOW READ).
- **FORBIDDEN:** full-history fork вместе с `agent_type` (Codex: «Full-history forked agents inherit the parent agent type»).
- **FORBIDDEN:** invent agent types вне таблицы выше (`parent-driven-audit`, `managed-audit`, ad-hoc names). Для FRONT/BACK QA contract findings принадлежат `verify-qa`; при `fail|blocked` → только `@gate-repair`, без отдельного review-gate.
- Перед новым `spawn_agent`: **close** completed children. `agent thread limit reached` → close → spawn; не крутить wait бесконечно.
- Parent **не** ищет `epic_resolve.py` / hub scripts в product tree; только `python3 $DEV_HUB/bin/loop.py …`.
- Parent **не** гоняет `validate`/`validate-verdict` без `--payload '<json>'` и **не** требует `evidence_sha256`.
- После boundary-accepted `FAIL` → `gate-repair`, не повторный verify «из‑за схемы».
- Для CRM e2e / shared-token FAIL: repair обязан чинить **runtime delivery** (`crm/scripts/e2e-preflight.sh`, `crm/crm/hooks.py` → `frappe-bench/apps/crm`, `bench start`), а не крутить дополнительные gate-сессии.

## Gate Verdict Contract (JSON Fenced Block) — machine SoT

Субагенты `verify-implement`, `verify-bugfix`, `verify-qa`, `verify-decompose`, `analyze-verify` (и алиасы) **ОБЯЗАНЫ**:

1. Bash `validate-verdict` до `valid: true` (пишет pre-emit stamp + `emit_exactly`; без stamp SubagentStop → reject).
2. В финальный ответ — ровно один fenced `` ```json `` = `emit_exactly` (кроме `recorded_at`); **без лишних ключей**. Parent: `handoff REJECTED` ≠ PASS.

```json
{
  "schema": "loop-gate-verdict/v1",
  "agent_id": "verify-implement",
  "verdict": "PASS",
  "step_id": "s01",
  "session_id": "<session_id>",
  "epic_id": "<epic_id>",
  "recorded_at": "<iso8601>"
}
```

- Allowed keys only: `schema`, `agent_id`, `verdict`, `step_id`, `session_id`, `epic_id`, `recorded_at`, optional `evidence_sha256`.
- FORBIDDEN: `evidence`, `blockers`, `touched_paths`, `evidence_id`, `reason`, `findings`, `gate`, `status`, `checkpoints`.
- `verdict`: `PASS` | `FAIL` | `BLOCKED` (BLOCKED только verify-qa/reviewer).
- После fence — **ноль** tool calls.
- gate-repair SoT = `loop-repair-result/v1` fence (`status`, `fixed_blockers`, `remaining_blockers`).

## Budget (custom overlay)

| Agent | maxTurns | notes |
|-------|----------|-------|
| explorer | 20 | ≤12 Read · ≤6 Bash · ≤8 Grep/Glob; после graphify только `path=`; re-read >1× FORBIDDEN; plan/creative вне ALLOW FORBIDDEN; repo-wide `rg`/`find`/`ls` FORBIDDEN |
| verify-implement / verify-bugfix / verify (alias) | 12 | ≤12 read (цель ≤6) · ≤10 ALLOW · re-read запрещён; финал = fenced JSON `loop-gate-verdict/v1` |
| verify-qa / reviewer (alias) | 30 | ≤16 rg · ≤40 read · ≤40 ALLOW · exhaustive AC matrix · полный `## BLOCKERS (complete)` · финал = fenced JSON `loop-gate-verdict/v1` |
| verify-decompose | 12 | ≤12 read · ≤10 ALLOW · re-read запрещён; финал = fenced JSON `loop-gate-verdict/v1` |

## Hooks

| Event | Эффект |
|-------|--------|
| PreToolUse Agent | HARD RULE на все Agent; strip worktree/model на overlay; deny неполного prompt на verify/reviewer/explorer |
| SubagentStop | verify-* / analyze-verify: invalid fence, forbidden keys, или нет matching pre-emit stamp после validate-verdict → block (+ schema retry / halt) |
| Stop | FINISH без verify / QA без verify-qa (reviewer) / QA без Handoff → block; **исключение:** no-VERDICT retries исчерпаны + Handoff `NEED_HUMAN: verify_no_verdict` → allow stop |

State: `.claude/runtime/spawn-gate/<session>.json` (gitignore).
