# HARD — Agent spawn (Claude Code): overlay gates

Parent **MAY** spawn любых Agent по нужде.  
**Обязательные** gate’ы (когда agent enabled в scope): **explorer** (codebase search) · **verify** (pre-FINISH) · **reviewer** (BACK QA).

| `subagent_type` | Phase / Когда | Обязателен? | Alias compatibility |
|-----------------|---------------|-------------|---------------------|
| `explorer` | codebase search / discovery в code-режимах | **да**, если `MODEL_LOOP=1` (иначе parent: graphify + узкий rg) | — |
| `verify-implement` | IMPLEMENT / REFACTOR / TASK pre-FINISH (`code_changed: yes`) | **да** (если gate active в loop) | `@verify` |
| `verify-bugfix` | BUGFIX pre-FINISH (`code_changed: yes`) | **да** (если gate active в loop) | `@verify` |
| `verify-qa` | BACK QA после suite | **да** (если gate active в loop) | `@reviewer` |
| `verify-decompose` | DECOMPOSE pre-FINISH | **да** (если gate active в loop) | — |
| `analyze-verify` | после fix plan/decompose по ANALYZE findings | нет (gate после CRITICAL fix; packed FINDINGS/COVERAGE/ALLOW) | — |
| `verify` (alias) | pre-FINISH IMPLEMENT / BUGFIX | legacy alias → `verify-implement` / `verify-bugfix` | `@verify` |
| `reviewer` (alias) | BACK QA | legacy alias → `verify-qa` | `@reviewer` |
| built-in / др. | когда parent считает нужным | нет | — |

## Phase → Expected Verify Agent Map

| Phase / Role Mode | Expected Agent | Fallback / Alias |
|-------------------|----------------|------------------|
| BACK/FRONT IMPLEMENT | `verify-implement` | `verify` |
| BACK/FRONT REFACTOR | `verify-implement` | `verify` |
| BACK/FRONT TASK | `verify-implement` | `verify` |
| BACK/FRONT BUGFIX | `verify-bugfix` | `verify` |
| BACK/FRONT QA | `verify-qa` | `reviewer` |
| BACK/FRONT DECOMPOSE | `verify-decompose` | — |
| BACK/FRONT ANALYZE fix | `analyze-verify` | — |

## Политика

| Режим | Поведение |
|-------|-----------|
| IMPLEMENT · REFACTOR · BUGFIX · TASK (code) | перед широким поиском → **`@explorer`**, если managed search agent включён; иначе graphify + узкий rg parent |
| Перед FINISH (`code_changed: yes` IMPLEMENT/REFACTOR/TASK) | **`@verify-implement` ОБЯЗАТЕЛЬНО** (packed; alias `@verify` поддерживается); FAIL/DENY → fix → retry до PASS; после PASS — не повторять |
| Перед FINISH (`code_changed: yes` BUGFIX) | **`@verify-bugfix` ОБЯЗАТЕЛЬНО** (packed; alias `@verify` поддерживается); FAIL/DENY → fix → retry до PASS |
| Перед FINISH DECOMPOSE | **`@verify-decompose` ОБЯЗАТЕЛЬНО** |
| После ANALYZE fix (plan/decompose) | **`@analyze-verify`** (packed); FAIL → fix → retry; PASS → re-ANALYZE или IMPLEMENT gate |
| BACK QA после suite | **`@verify-qa` ОБЯЗАТЕЛЬНО** (packed; alias `@reviewer` поддерживается); pytest — у parent |
| Любой режим | доп. Agent — свободно |

### Generic registry policy

`*_MODEL` — только модель. `*_MODEL_CHAT` / `*_MODEL_LOOP` — **только** boolean selectors (0/1), не model id. Absent selector → `loop=1`, `chat=0`. Disabled → `scope_disabled` / bypass; invalid required gate → fail-closed.

**Search scope (общее):** default = текущий scope шага (ALLOW в prompt). Другие каталоги — **только если действительно нужны** и путь есть в shard/consumes/plan/checkpoint. Широкий repo search «на всякий случай» = FAIL.

**FAIL:** FINISH без `verify-implement`/`verify-bugfix` когда `code_changed: yes`.  
**FAIL:** `@verify-implement` / `@verify-bugfix` повторно после `VERDICT: PASS` (retry только при `FAIL` / spawn DENY).  
**FAIL:** BACK QA FINISH без `Agent`→`verify-qa` (или alias `reviewer`).  
**FAIL:** code-режим сделал широкий codebase search без предшествующего `Agent`→`explorer` в сессии (кроме исключения выше).  
**FAIL:** `isolation=worktree` / `model=` на verify|reviewer|explorer — hooks снимают.  
**FAIL:** spawn verify/reviewer/explorer без packed секций / ALLOW = дерево / >10 файлов / globs `**` в ALLOW.
  ├─ FAIL → parent чинит blockers → снова @verify-implement / @verify-qa
Hooks: `stop-gate` блокирует FINISH при FAIL; `agent-pretool` DENY `@verify-implement` если уже PASS / step missing / no-VERDICT retry исчерпан.

**FAIL:** «проверь шаг» / QA review / search без секций.  
**FAIL:** `ALLOW READ` = дерево / glob `dir/**` (нужны конкретные пути файлов, ≤10).
   **FAIL:** секции без перевода строки / без этих заголовков.

## Gate Verdict Contract (JSON Fenced Block) — machine SoT

Субагенты `verify-implement`, `verify-bugfix`, `verify-qa`, `verify-decompose` (и их алиасы `verify`, `reviewer`) **ОБЯЗАНЫ** включить в финальный ответ fenced JSON:

```json
{
  "schema": "loop-gate-verdict/v1",
  "agent_id": "verify-implement",
  "verdict": "PASS",
  "reason": "AC+ and AC- satisfied",
  "evidence_sha256": "..."
}
```

- Поле **`schema`** (не `schema_version`).
- `verdict`: `PASS` | `FAIL` | `BLOCKED` (BLOCKED только verify-qa/reviewer).
- Текстовая строка `VERDICT: …` — **optional** human summary; **не** machine input (hooks читают JSON fence → sidecar).

Отчёт: на русском.

## Budget (custom overlay)

| Agent | maxTurns | notes |
|-------|----------|-------|
| explorer | 20 | ≤12 Read · ≤6 Bash · ≤8 Grep/Glob; после graphify только `path=`; re-read >1× FORBIDDEN; plan/creative вне ALLOW FORBIDDEN; repo-wide `rg`/`find`/`ls` FORBIDDEN |
| verify-implement / verify-bugfix / verify (alias) | 12 | ≤12 read (цель ≤6) · ≤10 ALLOW · re-read запрещён; fenced JSON `loop-gate-verdict/v1` обязателен; после ≤6 Read — только текст |
| verify-qa / reviewer (alias) | 18 | ≤8 rg · ≤12 read · ≤10 ALLOW · re-read запрещён; финал только текст + fenced JSON `loop-gate-verdict/v1` |
| verify-decompose | 12 | ≤12 read · ≤10 ALLOW · re-read запрещён; fenced JSON `loop-gate-verdict/v1` обязателен |

## Hooks

| Event | Эффект |
|-------|--------|
| PreToolUse Agent | HARD RULE на все Agent; strip worktree/model на overlay; deny неполного prompt на verify/reviewer/explorer |
| SubagentStop | verify-implement/verify-bugfix/verify-qa/verify-decompose без valid JSON fence → block (+ incomplete counter) |
| Stop | FINISH без verify / QA без verify-qa (reviewer) / QA без Handoff → block; **исключение:** no-VERDICT retries исчерпаны + Handoff `NEED_HUMAN: verify_no_verdict` → allow stop |

State: `.claude/runtime/spawn-gate/<session>.json` (gitignore).
