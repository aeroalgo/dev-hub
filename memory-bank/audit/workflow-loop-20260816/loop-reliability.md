# Loop — надёжность, точки отказа, Cursor↔Claude

## Архитектура (as-built)

```
bin/loop → loop/loop.sh → context_loop (arm/prepare/check-after)
                       → session_resilience + Claude CLI (cwd=hub, --add-dir=product)
                       → hooks stop-gate / epic_resolve
                       → runtime/<slug>/epic/ (hub state)
```

Канон курсора агента: `PROJECT_ROOT/memory-bank/activeContext.md` + decompose `index.yaml` — **не** `state.json`.

## Точки отказа (P0)

### 1. `check-after` не HALT

- `prepare` `halt=1` → runner **HALT** (ok)
- `check-after` fail / stop≠EPIC_DONE → `WARN` + **outer retry** до MAX_ITER  
  Spot-check `loop.sh` ~641–647: retry, не exit.

**Риск:** дорогие сессии при integrity desync / NEED_HUMAN после сессии.

### 2. Dual runtime

| Данные | Где |
|--------|-----|
| state / checkpoint / runner | hub `runtime/<slug>/epic/` |
| `last-session.json` (часто) | product `.claude/runtime/epic/` |

Docs «смотри last-session рядом со state» — врут. Recovery по инструкции ломается.

### 3. Асимметрия halt-сигналов

- `BLOCKED:` на prepare → **auto-clear**, continue  
- `NEED_HUMAN:` на prepare → complete/stop  
- После сессии NEED_HUMAN → check-after complete + **retry**, не HALT

### 4. Cursor обходит epic gates

Loop integrity = **только Claude** hooks.  
`.cursor/hooks/` без `hooks.json` → ручной Cursor IMPLEMENT без stop-gate / verify enforce.

## Латание дыр (намеренный resilience — опасен при сбое shell)

- `repair_fingerprint_stall`, `repair_finish_desync`, auto-rollback `completed→in_progress`
- auto-strip `BLOCKED:`
- soft-filter несуществующих `load_now`
- `neutralize_state` на chat stop
- legacy event/DAG adapters

Паттерн: «не молчать о DONE, чинить и крутить» — хорошо при здоровом halt; плохо когда shell игнорирует fail-closed.

## Прочие gaps

| Gap | Деталь |
|-----|--------|
| `make loop` всегда `hub-link` | побочный эффект на product tree |
| Нет `.venv`/`pyproject` в hub | pytest/graphify claims невоспроизводимы из коробки |
| `projects/` пуст | overrides не используются |
| `architecture/workers.md` | в index — файла нет |
| `tests/` / `test_ports_browser` в MB | orphaned claims |
| SPOF | Claude CLI + model provider |

## Sync Cursor ↔ Claude

| Риск | Суть |
|------|------|
| SoT rules vs mirror | process = `.cursor/rules`; CC overlay = `.claude/rules` + instructions — дрейф |
| Hooks | FINISH gates только CC |
| Runtime path docs | всё ещё учат `.claude/runtime/epic/` |
| hub-link + multi-root + plugin | три способа «увидеть» hub; cwd решает куда state |
| CLAUDE.md vs AGENTS.md stub | разные entry при chat vs loop |

## Keep (loop)

- `bin/loop` + `loop.sh` + `context_loop`
- flock, phase models, model_substitution HALT
- Claude gates + `loop/tests` (canary / finish integrity)
- Opt-in roadmap chain / DAG fanout
