# T-HUB-022 Field Inventory & Gap Analysis Matrix

**Дата:** 2026-08-31  
**Статус:** Completed (s01)  
**Назначение:** Полный статический инвентарь machine-readable границ `loop`, структур полей и расхождений (gaps) с Pydantic spike-моделями (`loop/schemas/*.py`).

---

## 1. Overview of Loop Machine-Readable Boundaries

| Граница (Boundary) | Формат / Файл | Текущая схема / Валидатор | Pydantic схема (Target) |
|---|---|---|---|
| **State persistence** | `.claude/runtime/epic/state.json` | `default_state()`, dict setdefault in `core.py` | `EpicState` (`loop-state/v2`) |
| **Checkpoint persistence** | `.claude/runtime/epic/checkpoint.json` | `validate_checkpoint()` dict checking in `core.py` | `CheckpointRecord` (`loop-checkpoint/v1`) |
| **Event log** | `.claude/runtime/epic/events.jsonl` | `validate_event()` dict validation in `epic_events.py` | `LoopEvent` (`loop-event/v2`) |
| **Handoff transition** | `memory-bank/activeContext.md` (frontmatter) | Regex fallback (`## Handoff ...`) / `parse_frontmatter()` | `LoopHandoffFrontmatter` (`loop-handoff/v1`) |
| **Gate sidecar** | `.claude/runtime/epic/gates/{agent_id}.json` | Transcript regex fallback / `read_gate_verdict()` | `GateVerdictRecord` (`loop-gate-verdict/v1`) |
| **Board sync cards** | MindBreeze card payload (HTTP API) | `StepCard`, `GateCard` dataclasses in `card_model.py` | `BoardCardMetadata` (`mb-board-card/v1`) |
| **Decompose index** | `memory-bank/.../decompose-.../index.yaml` | `EpicDecomposeIndex` in `epic_yaml.py` | `index.yaml` single write SoT; `index.md` mirror |

---

## 2. Inventory & Field Matrix per Section

### 2.1 state.json (`loop-state/v2`)

- **Location:** `.claude/runtime/epic/state.json`
- **As-Built Fields (`epic/core.py`):**
  - `active` (`bool`): активен ли текущий эпик.
  - `status` (`str`): "idle", "running", "halted", "completed", "error", "blocked".
  - `started_at` (`str | None`): ISO 8601 timestamp запуска.
  - `updated_at` (`str | None`): ISO 8601 timestamp обновления.
  - `halt_reason` (`str | None`): причина останова.
  - `model` (`str | None`): используемая модель.
  - `last_verify_verdict` (`str | None`): "PASS" / "FAIL" / "BLOCKED".
  - `last_verify_at` (`str | None`): timestamp последнего вызова `@verify`.
  - `pending_fingerprint_before` (`str | None`): слепок контекста до выполнения.
  - `load_now_before` (`str | None`): содержимое `load_now`.
  - `state_schema_version` (`str`): версия схемы `"loop-state/v2"`.
  - `runtime` (`dict`): вложенный объект с runtime snapshot (`active`, `status`, `context_degraded`, `degraded_count`, `retry_count`, `resume_dirty`).
  - `dag` (`dict`): объект управления DAG (`pipeline_id`, `cursor`, `done`).
  - `gate_snapshot` (`list[str]`): список активных гейтов.
  - `diagnostic_codes` (`list[str]`): списки кодов мнемоник диагностики.
- **Drift Counters Gap (cp3 requirement):**
  - **`drift_counters` absent gap:** В текущей реализации `default_state()` **отсутствует** поле `drift_counters`. В `EpicState` будет добавлена вложенная модель `DriftCounters` (`handoff_projected`, `index_mirror_repair`, `fingerprint_stall_repair`, `gate_verdict_regex_fallback`, `schema_invalid`).

---

### 2.2 checkpoint.json (`loop-checkpoint/v1`)

- **Location:** `.claude/runtime/epic/checkpoint.json`
- **As-Built Fields (`_checkpoint_record` in `epic/core.py`):**
  - `schema` (`str`): `"loop-checkpoint/v1"`.
  - `checkpoint_seq` (`int`): порядковый номер контрольной точки (>= 1).
  - `checkpoint_id` (`str`): идентификатор ("cp1", "cp2", ...).
  - `session_id` (`str`): идентификатор сессии Claude/Loop.
  - `runner_id` (`str | None`): идентификатор раннера.
  - `identity` (`dict`): объект контекста (`role`, `epic_id`, `step_id`, `phase`, `next_phase`).
  - `step_id` (`str`): шаг эпика ("s01", "s02", ...).
  - `phase` (`str`): фаза выполнения ("BACK IMPLEMENT", ...).
  - `phase_epoch` (`int`): эпоха смены фазы.
  - `projection_hash` (`str | None`): хэш текущей проекции.
  - `stage` (`str`): стадия выполнения ("prepared", "dispatched", "interrupted", "evidence_recorded", "handoff_validated", "step_finalized").
  - `status` (`str`): статус чекпоинта ("pending", "active", "completed", "failed").
  - `next_action` (`str`): следующее действие ("dispatch", "continue", "verify", "handoff", "stop").
  - `resume_policy` (`str`): политика возобновления ("rerun_step", "resume_checkpoint", "escalate").
  - `context_fingerprint` (`str | None`): фингерпринт activeContext.
  - `index_fingerprint` (`str | None`): фингерпринт index.yaml.
  - `retry_count` (`int`): счётчик повторных попыток.
  - `degraded_count` (`int`): счётчик деградации контекста.
  - `reason` (`str | None`): текстовое объяснение причины.
  - `metadata` (`dict | None`): дополнительные метаданные.
  - `updated_at` (`str`): timestamp обновления.
- **Gap vs Spike:**
  - Валидация выполняется функциями на словарях (`validate_checkpoint()`). Перевод на Pydantic `CheckpointRecord` в `loop/schemas/checkpoint.py`.

---

### 2.3 events.jsonl (`loop-event/v2`)

- **Location:** `.claude/runtime/epic/events.jsonl`
- **As-Built Fields (`epic_events.py`):**
  - `schema` (`str`): `"loop-event/v2"`.
  - `event_id` (`str`): глобально уникальный ID события.
  - `event_seq` (`int`): строго возрастающий номер события.
  - `prev_event_hash` (`str`): SHA256 предыдущего события в цепочке.
  - `event_hash` (`str`): SHA256 текущего события.
  - `timestamp` (`str`): ISO 8601 UTC timestamp.
  - `epic_id` (`str`): ID эпика.
  - `step_id` (`str | None`): ID шага.
  - `phase` (`str`): текущая фаза loop.
  - `event_kind` (`str`): тип события (`audit_done`, `qa_pass`, `qa_fail`, `bugfix_done`, `reflection_done`, `incident_opened`, `incident_resolved`, `repair_applied`, `tier1_spawn`, `tier1_verify_pass`, `tier1_verify_fail`, `tier1_escalated`).
  - `actor` (`str`): компонент/агент, сгенерировавший событие.
  - `reason_code` (`str | None`): код причины.
  - `metadata` (`dict`): ключ-значение со строгими ограничениями на размер и секреты.
- **Gap vs Spike:**
  - Валидация в `epic_events.py` на `EventValidation` и dict. Нужна Pydantic модель `LoopEvent` в `loop/schemas/event.py`.

---

### 2.4 Handoff Frontmatter (`loop-handoff/v1`)

- **Location:** `memory-bank/activeContext.md` (YAML frontmatter в начале файла)
- **Spike Fields (`loop/schemas/handoff.py`):**
  - `schema` (`str`): `"loop-handoff/v1"`.
  - `role` (`str`): "BACK" | "FRONT" | "INTEG".
  - `mode` (`str`): "AUDIT" | "QA" | "REFLECT" | "BUGFIX" | "DECOMPOSE" | "IMPLEMENT".
  - `epic_id` (`str`): ID текущего эпика.
  - `step_id` (`str | None`): ID шага.
  - `reason_code` (`str | None`): код причины handoff.
  - `projection_hash` (`str | None`): хэш проекции.
- **As-Built vs Spike Gap:**
  - `activeContext.md` часто создаётся без YAML frontmatter (`---`), что заставляет runner парсить прозу (`## Handoff ...`). При включении `PROJECT_LOOP_HANDOFF_STRICT=1` FINISH блокируется при отсутствии фронтматтера.

---

### 2.5 Gate Sidecar (`loop-gate-verdict/v1`)

- **Location:** `.claude/runtime/epic/gates/{agent_id}.json`
- **Spike Fields (`loop/schemas/gate_verdict.py`):**
  - `schema` (`str`): `"loop-gate-verdict/v1"`.
  - `agent_id` (`str`): имя агента (например, "verify", "reviewer").
  - `verdict` (`str`): "PASS" | "FAIL" | "BLOCKED".
  - `step_id` (`str | None`): ID шага.
  - `session_id` (`str | None`): ID сессии.
  - `epic_id` (`str | None`): ID эпика.
  - `recorded_at` (`str`): ISO 8601 timestamp.
  - `evidence_sha256` (`str | None`): хэш улик/артефактов.
- **As-Built vs Spike Gap:**
  - Раньше `stop-gate.py` читал вердикт из regex по транскрипту. Sidecar файлы создаются через `write_gate_verdict()`, но требуется строгая проверка `read_gate_verdict()` с fallback на regex только с записью `drift_counters.gate_verdict_regex_fallback`.

---

### 2.6 Board Sync Metadata (`mb-board-card/v1`)

- **Location:** `loop/board_sync/card_model.py`
- **As-Built Fields (Dataclasses `StepCard` / `GateCard`):**
  - `StepCard`: `card_id`, `epic_id`, `step_id`, `title`, `phase`, `status`, `assigned_to`, `updated_at`, `payload_hash`.
  - `GateCard`: `card_id`, `epic_id`, `agent_id`, `verdict`, `recorded_at`, `payload_hash`.
- **Gap vs Spike:**
  - Датаклассы не выполняют Pydantic-валидацию перед отправкой на board HTTP API. Перевод на `BoardCardMetadata` (`mb-board-card/v1`).

---

## 3. Requirements & User Stories Coverage Matrix

| Requirement / User Story | Секция / Граница | Затронутые файлы и функции | Описание покрытия в инвентаре |
|---|---|---|---|
| **US-001** | `state.json` | `.claude/hooks/epic/core.py` (`load_epic_state`, `_state_diagnostics`) | Выявление `state_schema_invalid` при невалидном `state.json` с предоставлением безопасных дефолтов `default_state()`. |
| **US-002** | `checkpoint.json` | `.claude/hooks/epic/core.py` (`validate_checkpoint`, `_checkpoint_record`) | Гарантия единого контракта `CheckpointRecord` и кодов ошибок валидации. |
| **US-003** | Board metadata | `loop/board_sync/card_model.py` (`StepCard`, `GateCard`) | Валидация перед HTTP upsert в MindBreeze. |
| **US-004** | All boundaries | `loop/schemas/*.py` | Обязательное наличие `schema` / `schema_version` у каждого артефакта. |
| **US-005** | Handoff frontmatter | `loop/schemas/active_context.py`, `loop/schemas/handoff.py` | Фаза из reducer проецируется в frontmatter `loop-handoff/v1`. |
| **US-006** | Gate sidecar | `.claude/hooks/stop-gate.py`, `loop/schemas/gate_verdict.py` | Чтение typed sidecar `.claude/runtime/epic/gates/{agent_id}.json` приоритетнее regex. |
| **US-007** | Handoff frontmatter | `.claude/hooks/stop-gate.py` | `PROJECT_LOOP_HANDOFF_STRICT=1` блокирует FINISH при отсутствии frontmatter. |
| **US-008** | `state.json` | `.claude/hooks/epic/core.py` (`drift_counters`) | Инкремент счётчиков `drift_counters` при каждом вызове legacy repair/fallback. |
| **US-009** | Decompose index | `epic_yaml.py`, `epic/core.py` | `index.yaml` единственная точка записи; `index.md` генерируемое зеркало. |

---

## 4. Summary of Functional Requirements (FR-001 .. FR-007)

- **FR-001:** `EpicState` Pydantic модель с поддержкой `state_schema_version: loop-state/v2` и fail-soft при чтении.
- **FR-002:** `DriftCounters` модель вложенная в `EpicState` с полями `handoff_projected`, `index_mirror_repair`, `fingerprint_stall_repair`, `gate_verdict_regex_fallback`, `schema_invalid`.
- **FR-003:** `CheckpointRecord` Pydantic модель, покрывающая все 21 полей `validate_checkpoint`.
- **FR-004:** `LoopEvent` Pydantic модель для канонической записи строк `events.jsonl`.
- **FR-005:** `LoopHandoffFrontmatter` валидация и парсинг YAML frontmatter в `activeContext.md`.
- **FR-006:** `GateVerdictRecord` Pydantic модель валидации JSON sidecar вердиктов гейтов.
- **FR-007:** `BoardCardMetadata` Pydantic модели валидации карточек для MindBreeze sync.
