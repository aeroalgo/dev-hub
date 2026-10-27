# BACK BUGFIX — T-HUB-108-loop-board-projection — expose-disabled-reason and validate-mappings

- **Дата:** 2026-10-26
- **Источник:** `memory-bank/back/qa/T-HUB-108-loop-board-projection/qa-20261026-loop-board-projection.yaml`, Items `BF-001`, `BF-002`, `BF-003`
- **Эпик:** `T-HUB-108-loop-board-projection`
- **Статус:** Все элементы очереди выполнены (`BF-001: done`, `BF-002: done`, `BF-003: done`); verification status: pass

---

## 1. BF-001: Expose disabled reason in finish/halt output

### Симптом
QA зафиксировал blocker `BF-001`: `finish discards ProjectionResult.disabled_reason, so missing config/none is not explicit and projection can be silently skipped (loop/kernel/cli.py:1175) · expose disabled reason in finish/halt output.`

### Root cause
Команды CLI `finish` и `halt` в `loop/kernel/cli.py` вызывали `project_after_transition(...)`, но отбрасывали возвращаемый `ProjectionResult`, выводя в терминал/JSON только `{"event": ..., "status": ..., "phase": ..., "step_id": ...}`. В результате статус проекции и причина отключения (`disabled_reason`) не передавались вызывающей стороне.

### Исправление
В `loop/kernel/cli.py` для команд `finish` и `halt` сохранен результат вызова `project_after_transition(...)` в переменную `projection_result`. Если `projection_result` получен, в итоговый словарь вывода добавляются поля `projection_status` и `projection_disabled_reason`. В `loop/tests/test_board_projection_cli.py` добавлены проверки наличия этих полей в выводе CLI `finish` и `halt` при отсутствии конфигурации.

### Проверка исправления
- Targeted: `bin/pytest loop/tests/test_board_projection_cli.py -q --tb=line` — 5 passed in 1.65s

---

## 2. BF-002: Validate stage_map/state_map completeness against phase aliases

### Симптом
QA зафиксировал blocker `BF-002`: `incomplete stage_map/state_map can fall back and report success (loop/board_projection/adapters/bitrix24.py:87, loop/board_projection/adapters/plane.py:92, loop/board_projection/service.py:109) · validate mappings and fail loudly.`

### Root cause
В адаптерах Bitrix24 (`loop/board_projection/adapters/bitrix24.py:87`) и Plane (`loop/board_projection/adapters/plane.py:92`) при создании карточки `ensure_card` происходил молчаливый fallback:
`stage_id = self.resolve_stage_id(phase) or self.config.stage_map.get("backlog")`
и
`state_id = self.resolve_state_id(phase) or self.config.state_map.get("backlog")`.
Если mapping для указанной фазы отсутствовал, карточка создавалась на стадии backlog или без стадии вовсе, возвращался `external_id`, и `service.py:109` фиксировал карточку в sidecar map и возвращал `ProjectionResult(status="success")`. Это приводило к ложному успеху и silent skip корректной стадии при неполной конфигурации.

### Исправление
1. В `Bitrix24Adapter` (`loop/board_projection/adapters/bitrix24.py`) удален fallback на `stage_map.get("backlog")`. При неизвестной фазе / отсутствии маппинга в `ensure_card` возбуждается `AdapterExecutionError(f"Cannot create Bitrix24 task for epic {epic.epic_id}: unknown phase mapping for phase '{phase}'")`. Добавлен метод `validate_mappings()` для валидации полноты `stage_map` относительно `phase_alias`.
2. В `PlaneAdapter` (`loop/board_projection/adapters/plane.py`) удален fallback на `state_map.get("backlog")`. При неизвестной фазе / отсутствии маппинга в `ensure_card` возбуждается `AdapterExecutionError(f"Cannot create Plane work item for epic {epic.epic_id}: unknown phase mapping for phase '{phase}'")`. Добавлен метод `validate_mappings()` для валидации полноты `state_map` относительно `phase_alias`.
3. В `loop/board_projection/service.py` добавлена проверка непустого `external_id` после `ensure_card`.
4. Добавлены регрессионные тесты в `test_board_projection_bitrix24.py` и `test_board_projection_plane.py`.

### Проверка исправления
- Targeted: `bin/pytest loop/tests/test_board_projection_service.py loop/tests/test_board_projection_bitrix24.py loop/tests/test_board_projection_plane.py -q --tb=line` — 26 passed in 1.23s

---

## 3. BF-003: Call validate_mappings() and fail loudly on active provider misconfig

### Симптом
QA зафиксировал blocker `BF-003`: `Misconfig активного provider (битый map/stage) не валидируется при sync_phase и превращается в disabled-success вместо громкой ошибки (loop/board_projection/service.py:44, loop/board_projection/service.py:89) · вызвать validate_mappings() и не превращать активную misconfig в disabled-success.`

### Root cause
В `loop/board_projection/service.py` ошибки загрузки конфигурации (`ProjectionConfigError`), неполный конфиг активного провайдера (`incomplete_provider_config`) и ошибки фабрики адаптера перехватывались и превращались в `status="disabled"` (`disabled-success`), из-за чего CLI и вызывающие сервисы ошибочно считали проекцию легитимно отключенной вместо сигнализации об ошибке конфигурации. Кроме того, метод `validate_mappings()` активного адаптера вообще не вызывался перед проекцией фазы.

### Исправление
1. В `loop/board_projection/service.py`:
   - Сохранены легитимные причины отключения: отсутствие файла конфигурации (`missing_config`), провайдер `provider: none` и ограничение по ролям `role_not_allowed`.
   - Если активный провайдер имеет неполную конфигурацию (`incomplete_provider_config`) или файл содержит синтаксические/схемные ошибки, возбуждается `ProjectionConfigError` (громкая ошибка, не маскирующаяся под `disabled`).
   - Удалено подавление исключений при вызове `get_adapter(config)`.
   - Для активного адаптера добавлен обязательный вызов `active_adapter.validate_mappings()`, валидирующий полноту маппинга фаз (`stage_map`/`state_map`) относительно `phase_alias` и выбрасывающий `AdapterExecutionError` при неполноте.
2. В `loop/board_projection/registry.py` и `loop/board_projection/adapters/__init__.py` обеспечена автоматическая регистрация адаптеров (`bitrix24`, `plane`) при запросе к `get_adapter`.
3. Добавлены регрессионные тесты в `loop/tests/test_board_projection_service.py`:
   - `test_service_real_adapter_incomplete_mapping_fails_loudly`: проверяет выброс `AdapterExecutionError` при неполном `stage_map`.
   - `test_service_active_provider_incomplete_config_raises_explicit_error`: проверяет выброс `ProjectionConfigError` при неполном конфиге активного провайдера.
   - `test_service_active_provider_invalid_yaml_raises_explicit_error`: проверяет выброс `ProjectionConfigError` при поврежденном YAML.
   - `test_service_active_provider_plane_incomplete_mapping_fails_loudly`: проверяет выброс `AdapterExecutionError` при неполном `state_map` в Plane.

### Проверка исправления
- Targeted: `bin/pytest loop/tests/test_board_projection_service.py -q --tb=line` — 10 passed in 1.17s
- All board projection tests: `bin/pytest loop/tests/test_board_projection*.py -q --tb=line` — 40 passed in 1.43s
- Full suite: `bin/pytest -q --tb=line` — 188 passed in 11.26s

---

## Changed Paths

- `loop/kernel/cli.py`
- `loop/board_projection/adapters/bitrix24.py`
- `loop/board_projection/adapters/plane.py`
- `loop/board_projection/adapters/__init__.py`
- `loop/board_projection/registry.py`
- `loop/board_projection/service.py`
- `loop/tests/test_board_projection_cli.py`
- `loop/tests/test_board_projection_bitrix24.py`
- `loop/tests/test_board_projection_plane.py`
- `loop/tests/test_board_projection_service.py`
- `memory-bank/back/bugfix/T-HUB-108-loop-board-projection/bugfix-queue.yaml`
- `memory-bank/back/bugfix/T-HUB-108-loop-board-projection/bugfix-20261026-expose-disabled-reason.md`

## Acceptance Criteria Verification

- [x] **AC+ (Expose disabled reason):** Вывод CLI `finish` и `halt` явно содержит `projection_status` и `projection_disabled_reason` (например, `"missing_config"`, `"provider_none"`).
- [x] **AC+ (Loud failure on missing mappings):** При неполном `stage_map`/`state_map` для требуемой фазы возбуждается `AdapterExecutionError` (`unknown phase mapping`), фиксируется soft-fail и `sync_error`, а ложный успех не возвращается.
- [x] **AC- (Нет silent skip projection):** Проекция не пропускается молчаливо, причина отключения всегда выводится в CLI.
- [x] **AC- (Misconfig активного provider -> loud error, не stub success sync):** Неполный stage/state map или поврежденная конфигурация активного провайдера возбуждает громкую ошибку (`AdapterExecutionError`, `ProjectionConfigError`), не маскируясь под `disabled` статус.
- [x] **§0.11 / Suite:** Полный dev-hub pytest suite зеленый: 188 passed in 11.26s.
