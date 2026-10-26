## Epic

### Outcome
После успешного перехода фазы эпика в loop на выбранном таскборде (Bitrix24 или Plane) появляется или двигается карточка того же эпика. Оператор переключает провайдера конфигом. Источник правды остаётся loop; доска — проекция.

### In
- Единый контракт проекции create/move + provider adapters
- Переключение активного провайдера одним полем конфига
- Явный mapping epic_id ↔ external_id в sidecar (scoped by provider)
- Opt-in конфиг и громкая ошибка синка без отката фазы loop
- Allowlist ролей (по умолчанию только back)

### Out
- Двусторонний sync (доска → loop)
- Синхронизация CRM Frappe ↔ внешний трекер
- MCP как единственный/основной канал движения эпиков
- Одновременная запись в два провайдера
- Bitrix OAuth (webhook-only); Plane OAuth UI (API key)
- Hard-fail finish при падении доски
- Восстановление DSH task-board sync как SoT

### Done when
1. При `provider=bitrix24|plane` и полном конфиге finish без mapping создаёт карточку и пишет sidecar
2. Следующий finish двигает карточку на stage/state из phase map
3. Смена `provider` без remap/clear → явная ошибка (не использовать чужой external_id)
4. Без полного конфига проекция явно disabled; silent skip нет
5. Ошибка REST не откатывает cursor; sync_error + команда догона
6. Hot path finish зовёт только Protocol, не vendor SDK напрямую

### Forbidden after
silent skip · dual SoT · match по title · hard-fail finish из-за зеркала · MCP-only вместо adapter · finish→Bitrix hardcode без Protocol · dual-write в два трекера · optional «модуль есть, finish не зовёт»

### Chat decisions
- Облако Bitrix `*.bitrix24.ru` + webhook
- Soft-fail finish; loud sync_error
- Role allowlist, default back
- Lazy create на первом finish
- Phase→column map в YAML: **6 колонок** backlog | design | build | verify | done | blocked
- Sidecar под `.loop/`
- Opt-in при полном provider-конфиге
- **Pluggable adapters: Bitrix24 и Plane; переключение `provider` в конфиге**

---

## Covering

n/a — single epic
