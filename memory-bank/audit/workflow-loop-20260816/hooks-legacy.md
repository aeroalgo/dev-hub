# Hooks / agents — legacy и что убрать

## Регистрация Claude (`settings.json`)

SessionStart · UserPromptSubmit · PreToolUse Agent/Task · PreToolUse Bash · PostToolUse Agent/Task · PostToolUse Bash · SubagentStart/Stop · Stop.

**Не в settings, но живые (loop.sh):** `session_resilience.py`, `epic_stream_filter.py`, `epic_resolve.py` (CLI).

## Inventory (кратко)

| Файл / группа | Вердикт |
|---------------|---------|
| 9 entry hooks + `_lib`, `agent_policy`, `agent_registry` | **keep** |
| `epic/core.py` (~3143), `epic_yaml`, `epic_index`, `epic_events`, … | **keep** (hotspot → refactor, не delete) |
| `epic_lib.py` facade | **keep** (тесты/compat) |
| `epic/{checkpoint,context,events,index,io,state}.py` | **remove** — re-export, **0 импортов** `from epic.X` |
| мёртвый `import epic as _epic` в `epic_lib` | **remove** (AST unused) |
| `session_resilience`, `epic_stream_filter` | **keep** (wired в loop) |
| `.cursor/hooks/*.py` (4) без `hooks.json` | **deprecate / remove или wired** — сейчас no-op stub (`continue: true`) |
| agents: `explorer`, `verify`, `reviewer` | **keep** |

## Баги / противоречия policy

1. **`extract_verdict`:** docstring «last match wins», код: `if "VERDICT: PASS" in text: return PASS` → PASS затем FAIL всё равно PASS. Контракт агента содержит подстроку `VERDICT: PASS` → false PASS.
2. **`BLOCKED: verify_no_verdict`** в `agent-pretool` vs **`NEED_HUMAN:`** в spawn-hard/stop-gate; loop auto-strip `BLOCKED:`.
3. **Dual registry:** `_lib._discover_registry` strips process `PROJECT_AGENT_*` (file-wins); часть hooks зовут `discover_registry` напрямую → env vs file расходятся.
4. **`explorer` alias `explore`:** заявлен в md; `ALIAS={}` в `_lib` — не нормализуется.
5. **`agent-posttool` mirror:** `except: pass` — PASS в spawn-state, epic `last_verify_verdict` не обновлён.
6. **Race** `save_state` без lock: posttool ∥ subagent-stop.
7. **Обязательность explorer** в docs vs hooks: stop-gate **не** блокирует FINISH за отсутствие `@explorer`.

## Complexity hotspots

| Файл | LOC | Риск |
|------|-----|------|
| `epic/core.py` | ~3143 | nest≤7, broad except |
| `_lib.py` | ~1486 | spawn-gate monolith |
| `epic_yaml.py` | ~1006 | validate + back-compat |
| `session_resilience.py` | ~906 | nest≤10 |
| `context_loop.py` | ~2101 | runner brain |

## Agents — матрица

| Agent | Когда обязателен (docs) | Enforce hooks |
|-------|-------------------------|---------------|
| explorer | codebase search (code modes) | в основном docs; skip delta_paths |
| verify | pre-FINISH code_changed | pretool + stop-gate |
| reviewer | BACK QA после suite | pretool + stop-gate |

`PROJECT_WORKFLOW_HOOKS=loop` → вне EPIC_LOOP hooks нейтрализуются (chat без loop gates).

## Legacy / compat слой (не удалять вслепую)

- `PolicyReason.COMPATIBILITY` / `LEGACY_DEFAULT`
- `_LEGACY_OVERLAYS` в registry
- `epic_events` migrate legacy event files
- `epic_yaml` back-compat helpers
- docs path `.claude/runtime/epic/` vs hub `runtime/<slug>/`
