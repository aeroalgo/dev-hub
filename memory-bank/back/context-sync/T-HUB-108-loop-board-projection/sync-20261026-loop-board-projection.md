# CONTEXT SYNC — T-HUB-108-loop-board-projection

**Дата:** 2026-10-26  
**Эпик:** T-HUB-108-loop-board-projection  
**Фаза:** CONTEXT_SYNC  
**Роль:** BACK  
**QA evidence:** `memory-bank/back/qa/T-HUB-108-loop-board-projection/qa-20261026-loop-board-projection.yaml` (verdict: pass)  

---

## Что синхронизировано в канон

1. **`memory-bank/systemPatterns.md`**:
   - Добавлен паттерн `SP-H10`: Board projection: внешний таскборд как зеркало фазы эпика (Bitrix24, Plane). Protocol `BoardProjectionAdapter` + registry; post-finish hook; loop остаётся единственным SoT; soft-fail на REST-ошибках без отката cursor; fail-closed на несовпадении provider в sidecar identity map (`.loop/board-epic-map.yaml`).

2. **`memory-bank/techContext.md`**:
   - Добавлен раздел `## Board projection (T-HUB-108)`:
     - Конфигурация: `.loop/board-projection.yaml` (`provider: "bitrix24" | "plane" | "none"`).
     - Sidecar mapping: `.loop/board-epic-map.yaml` (`schema: board-epic-map/v1`) — связь `epic_id` ↔ `external_id` с изолированным скоупом провайдера.
     - Архитектура: Protocol `BoardProjectionAdapter` + registry провайдеров (`loop/board_projection/`).
     - Адаптеры: `Bitrix24Adapter` (webhook: `tasks.task.add`, `task.stages.movetask`) и `PlaneAdapter` (REST API key: work items, PATCH state).
     - Интеграция в loop: post-finish hook в `loop/kernel/engine.py` после фиксации курсора; soft-fail на REST-ошибках (запись `sync_error` в sidecar без отката курсора).
     - Catch-up CLI: `bin/loop.py board-sync --project <path>`.
     - Targeted тесты: `bin/pytest loop/tests/test_board_projection* -q --tb=short`.

3. **`memory-bank/projectbrief.md`**:
   - In/out границы хаба не изменились (no-op).
