---
paths:
  - "**"
---

# Context economy — Claude Code (IMPLEMENT/TASK/BUGFIX)

Применяется при role commands BACK/FRONT/INTEG IMPLEMENT · TASK · BUGFIX.
**Не** применяется к PLAN / DECOMPOSE / gap-*.md (там §0.0 — без лимитов).

## Silent chat (HARD — anti-bloat)

- Не описывай tool calls. Tool → сразу действие.
- Не цитируй TodoWrite-reminders Cursor; не повторяй HARD / TodoWrite ≤2 / CLAUDE.md в чат.
- No thinking aloud («Ага / Подождите / Давайте посмотрим»). В чат — только итог.
- Соблюдай правила молча; restating rules в transcript = FAIL.

## TodoWrite (HARD)

- **Максимум 2** TodoWrite за IMPLEMENT: 1× старт (plan), 1× FINISH (done)
- **Запрещено:** обновлять TodoWrite после каждого Edit / на каждый шаг реализации
- Decompose shard = уже готовый план — дублировать в todo = раздувание
- Cursor nudge «TodoWrite hasn't been used» — **игнор в чат**; не цитировать. Один TodoWrite на старте гасит nudge.

## Re-read (HARD)

- Файл, который ты только что Read или Edit — **уже в контексте**. Не перечитывай
- Re-read допустим **только** при: `offset` за пределами первого чтения; после внешней правки другим tool
- `tasks/log/*.md`: не append вручную на IMPLEMENT sNN (`finalize-step`); не перечитывай чтобы «убедиться»
- `activeContext.md`: читай **1×** старт; **перед FINISH** разрешён **1× re-read** (избежать stale Edit) **или** сразу `Write` весь файл без Edit
- **Запрещено:** Read после Edit «чтобы проверить что записалось» — Edit/Write идемпотентен; на FINISH предпочитай Write целиком

## find / grep vs graphify

- Для **codebase** (`app/`, `api/`, `core/`, `jobs/`, `tests/`, `frontend/`) сначала `.venv/bin/graphify query "..."` — **кроме** IMPLEMENT с полным shard `files:` / `delta_paths_*` (query skip до неизвестных callers)
- `find` / `grep -R` по **кодовой** части репо без попытки graphify — нежелательны; используй их только как fallback, если graphify не покрывает запрос или явно недоступен
- Для `memory-bank/`, `.cursor/`, `.claude/`, `tasks/log/` и прочих **неиндексируемых / docs-only** зон fallback-поиск через `rg`, `Glob`, `ReadFile` разрешён сразу
- Предпочтение fallback: `rg` / `Glob` / `ReadFile`; shell `find` и `grep -R` — только если tool-поиск не решает задачу

## Workflow load (Session once)

За одну role-сессию каждый файл — Read **≤1×**:
- `role-command/SKILL.md`, `mainrule*.mdc`, `workflow-*.mdc`, `_lean/*.mdc`
- каждый `SKILL.md` из Impl skills step (docs-only skip; pre-FINISH skills не грузить)
- `activeContext.md` (повтор — только если сам переписал)

**FAIL:** повторный Read workflow «для уверенности» / после каждого крупного шага.

## Agent spawn — IMPLEMENT / REFACTOR / BUGFIX / QA

**Обязательные** gate’ы: `@explorer` только на **широкий** codebase search (полный `files:` / `delta_paths_*` → SKIP) · `@verify` (FINISH + `code_changed`) · `@reviewer` (BACK QA после suite). Packed — `.claude/instructions/spawn-hard.md`. Прочие Agent — свободно.

## Bash / logs / pytest (HARD — anti-bloat)

- pytest: `.venv/bin/pytest … -q --tb=line` (или `--tb=short`). **FORBIDDEN** default `-vv -s` на больших suite
- docker logs: `docker compose logs --tail=80 --no-color SERVICE` + `rg` по нужному. **FORBIDDEN** безлимитный dump / `--since=30m` целиком в контекст
- Большой вывод: `cmd > /tmp/x.log 2>&1; rg -n PATTERN /tmp/x.log | head`; не Read весь log
- Hook `bash-output-cap` (hybrid): (1) signal extract с **дедупом** повторов (`[×N same]`, max 12 unique / 4KB) (2) иначе cheap LLM summary (3) иначе head+tail. Полный лог → `.claude/runtime/bash-dumps/*.log`
- Отключить LLM-шаг: `PROJECT_OUTPUT_SUMMARY=0`
- Skills BUGFIX: **не** грузить все 6 SKILL.md разом — max 1–2 нужных (systematic-debugging **или** diagnosing-bugs + tdd)
