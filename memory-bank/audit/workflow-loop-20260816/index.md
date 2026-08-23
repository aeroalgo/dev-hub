# Полный аудит workflow + loop — 2026-08-16

**Scope:** репозиторий `dev-hub` (rules, hooks, agents, `loop/`, dual Cursor↔Claude).  
**Не scope:** продуктовый application-код / product epics (кроме того, как hub на них влияет).  
**Источники:** `memory-bank/architecture/*`, `.cursor/rules`, `.claude/**`, `loop/**`, `bin/**`, spot-check кода.

## Вердикт

Ядро канона (§0.0 load≠write, `load_now`, ONE Handoff, implement yaml + verify/finalize, multi-epic queue) — **solid**.  
Поверх него накопился **тройной слой документации**, **битые ссылки на архив/файлы**, **dead stubs**, и **дыры runner’а** (`check-after` не HALT, dual runtime). Агенты чаще ломаются из‑за выбора неверной копии правила, чем из‑за сложности задачи.

| Метрика | Значение |
|---------|----------|
| Hotspot LOC (`epic/core` + `_lib` + `context_loop`) | ~6730 |
| Claude hooks entrypoints (settings) | 9 |
| Dead re-export `epic/*.py` (кроме core/__init__) | 6 |
| Cursor hooks без `hooks.json` | 4 (no-op / unwired) |
| Dual `role-command` SKILL | diverge |
| `_archive/` в hub | **отсутствует** |
| `.cursor/rules/front-tests-parent-only.mdc` | **отсутствует** |
| `architecture/workers.md` | **битая ссылка** |

## Shards

| Shard | Содержание |
|-------|------------|
| [contradictions.md](contradictions.md) | Противоречия, неоднозначности, битые пути |
| [hooks-legacy.md](hooks-legacy.md) | Hooks/agents: keep / remove / refactor |
| [loop-reliability.md](loop-reliability.md) | Loop: точки отказа, латание дыр, Cursor↔Claude |
| [roadmap.md](roadmap.md) | P0/P1/P2 · что не трогать · что менять |

## Canvas

Интерактивная сводка: [workflow-loop-audit.canvas.tsx](/home/aero/.cursor/projects/home-aero-PyProject-dev-hub/canvases/workflow-loop-audit.canvas.tsx)

## Related

- [architecture/index.md](../../architecture/index.md)
- [projectbrief.md](../../projectbrief.md)
- Session VAN: [back/van/van-20260816.md](../../back/van/van-20260816.md)
