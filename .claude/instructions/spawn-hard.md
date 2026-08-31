# HARD — Agent spawn (Claude Code): overlay gates

Parent **MAY** spawn любых Agent по нужде.  
**Обязательные** gate’ы (когда agent enabled в scope): **explorer** (codebase search) · **verify** (pre-FINISH) · **reviewer** (BACK QA).

| `subagent_type` | Когда | Обязателен? |
|-----------------|-------|-------------|
| `explorer` | codebase search / discovery в code-режимах | **да**, если `MODEL_LOOP=1` (иначе parent: graphify + узкий rg) |
| `verify` | pre-FINISH при `code_changed: yes` | **да** (если gate active в loop) |
| `analyze-verify` | после fix plan/decompose по ANALYZE findings | нет (gate после CRITICAL fix; packed FINDINGS/COVERAGE/ALLOW) |
| `reviewer` | BACK QA после suite | **да** (если gate active в loop) |
| built-in / др. | когда parent считает нужным | нет |

## Политика

| Режим | Поведение |
|-------|-----------|
| IMPLEMENT · REFACTOR · BUGFIX · TASK (code) | перед широким поиском → **`@explorer`**, если managed search agent включён; иначе graphify + узкий rg parent |
| Перед FINISH (`code_changed: yes`) | **`@verify` ОБЯЗАТЕЛЬНО** (packed); FAIL/DENY → fix → retry до PASS; после PASS — не повторять |
| После ANALYZE fix (plan/decompose) | **`@analyze-verify`** (packed); FAIL → fix → retry; PASS → re-ANALYZE или IMPLEMENT gate |
| BACK QA после suite | **`@reviewer` ОБЯЗАТЕЛЬНО** (packed); pytest — у parent |
| Любой режим | доп. Agent — свободно |

### Generic registry policy

Agent статус → только index.yaml; index.md генерируется runner.

Managed agents из `.claude/agents/*.md` автоматически обнаруживаются registry и участвуют в policy по `overlay` (frontmatter). Для нового агента: frontmatter `overlay` + `PROJECT_AGENT_<NAME>_MODEL` (+ опц. `*_MODEL_CHAT` / `*_MODEL_LOOP`). Не нужно править `.claude/settings.json`.

`*_MODEL` — только модель. `*_MODEL_CHAT` / `*_MODEL_LOOP` — **только** boolean selectors (0/1), не model id. Absent selector → `loop=1`, `chat=0`. Disabled → `scope_disabled` / bypass; invalid required gate → fail-closed.

### Search gate (`explorer`) — HARD

**Триггер (любой):** import/ownership audit · «где X» · multi-file map · поиск по `apps/`/`tests/` · неизвестные paths за пределами явного file list шага.

**Порядок (если explorer enabled):**
1. Read shard / plan (docs) — у parent
2. **Один раз** `Agent`→`explorer` (packed: Цель · GRAPHIFY · ALLOW ≤10)
3. Дальше parent работает по отчёту explorer (+ Read только названных file:line)

**Если explorer выключен** (`MODEL_LOOP=0` / нет agent): parent делает graphify → узкий rg/Grep с `path=`. Не вызывать `@explorer`.

**FORBIDDEN parent до/вместо explorer (когда enabled):** серия `rg` / `grep -R` / широкий listing по `apps/` · `tests/` · `frontend/` как замена discovery.

**FORBIDDEN parent после explorer:** rediscovery — повторная серия `rg`/Grep/широкий Read по `frontend/`|`apps/` «уточнить»; повторный `@explorer` в той же сессии.

**FORBIDDEN:** `TaskOutput` / mid-poll пока Agent running — дождись completion summary/VERDICT один раз; mid-run timeout dump игнорируй.

**Исключение (explorer не нужен):** шаг правит **только** файлы из явного file list shard’а, discovery не требуется (1–few known paths, без audit/search).

**Исключение `delta_paths_exist` (HARD skip):** в prompt `delta_paths_exist: yes` (пути из shard `files:` / `consumes` / `produces` — **все** на диске, ≥2) → **`@explorer` SKIP**. Parent: только ALLOW из prompt (`search_scope`).

**Исключение `delta_paths_scoped` (HARD skip, greenfield):** `delta_paths_scoped: yes` (≥2 явных paths, файлы могут ещё не существовать) → **`@explorer` SKIP**. Parent: shard + `context.consumes` + listed targets; пиши `files:`/`produces:`. **ALLOW = paths + parent dirs**; вне ALLOW — только явная ссылка в shard/plan §N.

**Search scope (общее):** default = текущий scope шага (ALLOW в prompt). Другие каталоги — **только если действительно нужны** и путь есть в shard/consumes/plan/checkpoint. Широкий repo search «на всякий случай» = FAIL.

**Канон type:** project overlay `explorer` (не built-in `Explore`) — graphify first, затем Grep/Glob/`rg` fallback до ответа.

**FAIL:** FINISH без `verify` когда `code_changed: yes`.  
**FAIL:** `@verify` повторно после `VERDICT: PASS` (retry только при `FAIL` / spawn DENY).  
**FAIL:** BACK QA FINISH без `Agent`→`reviewer`.  
**FAIL:** code-режим сделал широкий codebase search без предшествующего `Agent`→`explorer` в сессии (кроме исключения выше).  
**FAIL:** `isolation=worktree` / `model=` на verify|reviewer|explorer — hooks снимают.  
**FAIL:** spawn verify/reviewer/explorer без packed секций / ALLOW = дерево / >10 файлов / globs `**` в ALLOW.

### Verify retry (HARD)

```
seed-implement (in_progress) → flush cp during work → suite →
evidence (status остаётся in_progress) → validate-step → Handoff → @verify
  ├─ PASS → finalize-step (atomic implement+index completed) / stop
  ├─ FAIL → parent чинит blockers → снова @verify
  ├─ spawn DENY (stub / incomplete prompt / step missing) → починить → снова @verify
  └─ завершение без VERDICT → макс. 1 retry @verify; иначе Handoff
     `NEED_HUMAN: verify_no_verdict` и stop (stop-gate **разрешает** stop; не плодить 3-й @verify)
```

**DENY ≠ второй subagent:** `agent-pretool` отклоняет spawn до запуска; в логе может быть два `Agent verify` подряд — первый DENY, второй retry с packed prompt. Один успешный spawn = один verify.

**no-VERDICT exhausted:** `agent-pretool` DENY дальнейший `@verify`; parent пишет `NEED_HUMAN: verify_no_verdict` в Handoff и stop. `stop-gate` не требует ещё один spawn.  
**ВАЖНО:** писать именно `NEED_HUMAN:`, не `BLOCKED:`. `BLOCKED:` автоматически очищается loop'ом при следующем запуске (потеря сигнала); `NEED_HUMAN:` требует явного вмешательства человека.

**Step template (verify §6):** все роли — `.cursor/templates/implement/epic-step.yaml` (`schema: epic-implement/v1`, `role`, `checkpoints`; INTEG + `grep_control` · `verification_results` · `gaps`).

**Pre-FINISH validate-step:** `python3 .claude/hooks/epic_resolve.py validate-step --path <implement shard>` — exit 0 до `@verify` (evidence ready, status ещё `in_progress`).

**FORBIDDEN:** `@verify` до существования `implement-*/sNN-*.yaml` или `implement-*/eNN-*.yaml`.  
**FORBIDDEN:** писать `status: completed` руками — только `finalize-step` после PASS.  
**FORBIDDEN:** `artifact:` = `plan/decompose-*` (только implement step path).  
**FORBIDDEN:** `@verify` пока предыдущий verify running; parallel managed spawn; два Agent на одну model сразу (`managed_in_flight` / `model_in_flight` — enforce в `agent-pretool`); `## FINISH` / mark-index completed до `VERDICT: PASS`.

Hooks: `stop-gate` блокирует FINISH при FAIL; `agent-pretool` DENY `@verify` если уже PASS / step missing / no-VERDICT retry исчерпан.

Built-in Agent types hooks не блокируют и не переименовывают.

## Parent packs context — gate’ы

| Блок | explorer | verify | reviewer |
|------|----------|--------|----------|
| **Цель** | да | да | да |
| **GRAPHIFY** | да (query/path/explain) | — | — |
| **Suite results** | — | — | да |
| **AC+** | — | да | да |
| **AC−** | — | да (≥1) | да (≥1) |
| **§0.11** | — | да (≥1) | да (≥1) |
| **VERIFY** | — | да (имена pytest) | — |
| **ALLOW READ** | ≤10 | ≤10 | ≤10 |
| **FORBID** | edit; role-command; plan | edit; role-command; plan | edit; pytest; role-command; plan |

**FAIL:** «проверь шаг» / QA review / search без секций.  
**FAIL:** `ALLOW READ` = дерево / glob `dir/**` (нужны конкретные пути файлов, ≤10).

## Как вызывать (gate)

1. Tool `Agent`, `subagent_type` = `explorer` | `verify` | `reviewer`
2. На custom overlay: не передавай `isolation` / `model` (pin в frontmatter)
3. Секции с **новой строки** + HARD RULE front-tests + «отчёт на русском».  
   Канон: `AC+:` / `AC-:` (ASCII `-` достаточно; Unicode `−` тоже). Допустимо `# AC+`.  
   **FAIL:** секции без перевода строки / без этих заголовков.
4. Дождись summary

### Пример explorer (search gate)

```
Цель: import/ownership audit — где apps/api и collector тянут domain/FastAPI.
GRAPHIFY: query "apps/api app.telemetry collector.domain plugins FastAPI imports"
ALLOW READ: apps/api/app/main.py, apps/edge/collector/src/collector/domain/interfaces.py
Отчёт: file:line + кто импортирует. На русском. Без plan-файла / Plan Mode.
Budget: ≤12 Read · узкий path= · без repo-wide rg.
```

### Пример verify (pre-FINISH)

```
Цель: pre-FINISH gate s08.
AC+:
- compute_official_ts prefer source when skew ok
AC-:
- не трогать quarantine / второй alembic head
0.11:
- clock_shift event ↔ EventsRepo
VERIFY:
- .venv/bin/pytest tests/storage/test_time_axis.py::test_compute_official_ts -q
ALLOW READ: apps/edge/storage/time_axis.py, tests/storage/test_time_axis.py, apps/edge/storage/events_repo.py, memory-bank/back/implement/implement-<plan>/sNN-<slug>.yaml
FORBID: edit/write; role-command; plan.
Отчёт: первая строка ровно `VERDICT: PASS` или `VERDICT: FAIL`. На русском.
```

Эквивалентно (markdown ATX): `# AC+` · `# AC-` · `# 0.11` · `# VERIFY` · `# ALLOW READ`.

INTEG `eNN`: step shape — `epic-step.yaml` (`role: integ`). ALLOW READ: `memory-bank/integration/implement/implement-<plan>/eNN-<slug>.yaml`.
Канон: `activeContext.md` + `plan/decompose-*/index.yaml` + implement step.

### Пример reviewer (BACK QA)

```
Цель: BACK QA review после suite (read-only).
Suite results:
- .venv/bin/pytest tests/storage/ -q → 65 passed
AC+:
- storage contracts + suite green
AC-:
- не объявлять full suite green если не завершён
0.11:
- DATABASE_URL ↔ docker-compose.yml
ALLOW READ: apps/edge/storage/writer.py, tests/storage/test_storage_contracts.py, pyproject.toml, docker-compose.yml, memory-bank/back/qa/<epic>/qa-YYYYMMDD-<slug>.yaml
FORBID: edit/write; pytest; .cursor/rules/**; Plan Mode / plan-файлы.
Отчёт: VERDICT PASS|BLOCKED|FAIL. На русском.
```

**FAIL parent QA:** suite есть, FINISH без `@reviewer` или без `## Handoff BACK QA` в `activeContext`.

## Budget (custom overlay)

| Agent | maxTurns | notes |
|-------|----------|-------|
| explorer | 20 | ≤12 Read · ≤6 Bash · ≤8 Grep/Glob; после graphify только `path=`; re-read >1× FORBIDDEN; plan/creative вне ALLOW FORBIDDEN; repo-wide `rg`/`find`/`ls` FORBIDDEN |
| verify | 12 | ≤12 read (цель ≤6) · ≤10 ALLOW · re-read запрещён; **первая строка финала = `VERDICT:`**; после ≤6 Read — только текст |
| reviewer | 18 | ≤8 rg · ≤12 read · ≤10 ALLOW · re-read запрещён; финал только текст |

## Hooks

| Event | Эффект |
|-------|--------|
| PreToolUse Agent | HARD RULE на все Agent; strip worktree/model на overlay; deny неполного prompt на verify/reviewer/explorer |
| SubagentStop | verify/reviewer без `VERDICT:` → block (+ incomplete counter) |
| Stop | FINISH без verify / QA без reviewer / QA без Handoff → block; **исключение:** no-VERDICT retries исчерпаны + Handoff `NEED_HUMAN: verify_no_verdict` → allow stop |

State: `.claude/runtime/spawn-gate/<session>.json` (gitignore).
