# [T-HUB-108 | loop-board-projection] PLAN

**Дата:** 2026-10-26  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** active  
**Clarify:** [clarify-20261026-bitrix-loop-epic-board.md](../../clarify/clarify-20261026-bitrix-loop-epic-board.md)  
**Prompt:** [md/prompt.md](prompt.md) — outcome SoT (абстрактный; не HOW)  
**Roadmap:** `memory-bank/back/roadmap/queue.yaml` · batch `loop-board-projection-20261026` · `kind: feature`  
**Deps:** — (loop kernel finish/transition as-built; no hard queue dep)  
**Skills:** writing-plans · python-testing-patterns · architecture-patterns · grill-me (Phase 0)  
**Источник:** chat BACK PLAN «зеркало эпиков в Б24» + amend «pluggable Bitrix24|Plane adapters»

---

## Контекст

- **req:** Люди должны видеть фазу эпика на внешней доске; агент/loop остаётся SoT. Оператор выбирает трекер: **Bitrix24** или **Plane**.
- **status quo:** Фазы живут в `activeContext` / cursor / `roadmap/queue.yaml`. Пакета `loop/board_sync` (DSH) в текущем tree нет. Отдельного Bitrix/Plane projection adapter нет.
- **gap:** Нет post-finish проекции и нет переключаемого контракта провайдера.
- **refs:** `loop/kernel/engine.py` (`finish` / `_transition_from_result`) · `loop/kernel/cli.py` · `loop/config.py` (`PHASES`) · clarify Q→A · Plane REST work-items/states · Bitrix `tasks.task.add` / `task.stages.movetask`
- **Не в scope:** Frappe CRM sync; Linear; MCP-as-driver; двусторонний sync; DSH resurrect; OAuth Bitrix.

**CREATIVE need:** нет (Protocol + два adapter зафиксированы clarify + Phase 1 amend; UI нет).

---

## Context consumed

| Path | Что вошло в axiom / Deps / FR |
|------|-------------------------------|
| `memory-bank/techContext.md` | Hub Python loop + `bin/pytest`; pydantic settings; runtime state; нет ORM |
| `memory-bank/systemPatterns.md` | SP-H02 context-first; SP-H03 runner owns bounds; SP-H04 fail-closed |
| `memory-bank/projectbrief.md` | Scope = hub tooling (`loop/`); не product app |
| `memory-bank/architecture/index.md` | Loop sessions; file runtime; нет compose в хабе |
| `memory-bank/product/` | n/a — каталога нет |

---

## Clarifications

- Session: 2026-10-26 · [clarify-20261026-bitrix-loop-epic-board.md](../../clarify/clarify-20261026-bitrix-loop-epic-board.md)
- Round 1–2: cloud Bitrix · soft-fail · allowlist · webhook · lazy create · STAGE_MAP YAML · `.loop/` sidecar · opt-in
- Phase 1 amend: **pluggable providers Bitrix24 | Plane**; switch via config `provider`

---

## Delivery closure

| Capability / outcome | Classification | Production entrypoint and caller | Success / failure enforcement | Independent outcome test | Foundation approval / follow-up |
|---|---|---|---|---|---|
| Board projection Protocol + registry | `vertical_slice` | `bin/loop.py finish` / halt path → `project_epic_phase(...)` → `get_adapter(provider)` | unknown provider / incomplete config → explicit disabled|error; finish не зовёт vendor напрямую | Given config provider=X; When finish; Then только adapter X вызывается | `n/a` |
| Bitrix24 adapter | `vertical_slice` | Protocol.create/move → Bitrix REST webhook | REST fail → sync_error loud; не откат cursor; no title match | Fake HTTP: create writes map; move uses stage_map | `n/a` |
| Plane adapter | `vertical_slice` | Protocol.create/move → Plane REST API key | REST fail → sync_error; state update fail-closed (не silent 200 no-op) | Fake HTTP: create work item + PATCH state | `n/a` |
| Provider switch + mapping scope | `vertical_slice` | load map validates `map.provider == config.provider` | mismatch → ProjectionError (не create с чужим id) | Map bitrix + config plane → error | `n/a` |
| Catch-up CLI | `vertical_slice` | `bin/loop.py board-sync` (или `projection sync`) | same Protocol; exit ≠0 on sync_error | CLI against fake → 0 / ≠0 | `n/a` |

---

## Technology axiom (replace-not-wrap)

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Provider SoT | Pydantic config `.loop/board-projection.yaml` поле `provider: Literal["bitrix24","plane","none"]` | hardcode Bitrix-only в finish; stringly if/else без registry |
| Adapter boundary | Protocol `BoardProjectionAdapter` + registry `provider → adapter` | finish импортирует `bitrix_client` / `plane_client` напрямую |
| Phase → column | YAML `phase_map` / per-provider `stage_map`\|`state_map` validate-on-load | prose «колонка Design» как machine input; regex title |
| Identity map | `.loop/board-epic-map.yaml` schema v1: `provider` + `epics[epic_id].external_id` | match по title; общий map без provider scope |
| Enable gate | полный конфиг активного provider **или** `provider: none` → explicit `projection_disabled` | silent skip; soft «если получится» без reason |
| Soft-fail policy | cursor commit **до** projection; projection errors → stderr + `sync_error` в map | откат finish из-за доски; swallow exception |

As-built DSH board_sync = sunset inventory (не resurrect). Bitrix-only draft prompt = superseded этим plan.

---

## Продуктовая спека (WHAT)

Оператор включает проекцию на выбранный таскборд. После успешного finish/halt loop создаёт или двигает карточку эпика в колонку, соответствующую фазе. Смена трекера — смена `provider` в конфиге (с безопасным mapping). Loop остаётся SoT; доска — зеркало для людей.

### Product probe

| # | Question | Answer / Probe | Decision / Impact on PLAN |
|---|----------|----------------|---------------------------|
| 1 | **Reframe** | Не «интеграция с Битрикс», а **projection port** с ≥2 adapters | Protocol + Bitrix + Plane |
| 2 | **Narrowest wedge** | finish → ensure+move для одного provider + fake HTTP tests | Vertical slice |
| 3 | **Pre-mortem** | Hardcode Bitrix в engine → Plane не подключить без rewrite | Registry + Protocol HARD |
| 4 | **Distribution** | `loop/README.md` + example configs | Kind I |
| 5 | **Technical leverage** | Один hook после Transition; adapters тонкие | No second supervisor |
| 6 | **Appetite** | ~3 дня; cut = comments на карточке, multi-group, OAuth | cut_list |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как оператор, я хочу выбрать `provider: plane` или `bitrix24`, чтобы эпики зеркалились на нужную доску. | P0 | Config A vs B → разные HTTP hosts/paths при finish |
| US-002 | Как оператор, я хочу после первого finish увидеть новую карточку, если mapping ещё нет. | P0 | Empty map + finish → create + sidecar write |
| US-003 | Как оператор, я хочу после смены фазы увидеть карточку в другой колонке. | P0 | Existing map + finish new phase → move/PATCH |
| US-004 | Как оператор без конфига, я хочу что finish работает и явно пишет «projection disabled». | P0 | No config → finish OK + disabled reason; no HTTP |
| US-005 | Как оператор при даунтайме доски, я хочу сохранить фазу в loop и увидеть sync_error + догнать позже. | P0 | Fake 500 → cursor advanced + sync_error + CLI retry |
| US-006 | Как оператор, сменивший provider, я хочу отказ при старом mapping, а не порчу чужой задачи. | P0 | map.provider≠config.provider → ProjectionError |

#### Acceptance Scenarios — US-001

- **Given:** `.loop/board-projection.yaml` с `provider: plane` и полным plane-блоком
- **When:** finish успешен
- **Then:** HTTP идёт на Plane base_url; Bitrix webhook не вызывается

#### Acceptance Scenarios — US-002

- **Given:** role в allowlist; полный конфиг; нет epic в map
- **When:** finish
- **Then:** create; map содержит `external_id`; phase записан

#### Acceptance Scenarios — US-003

- **Given:** map с external_id; phase_map для новой фазы
- **When:** finish → новая phase
- **Then:** move/update state; last_phase обновлён; sync_error cleared

#### Acceptance Scenarios — US-004

- **Given:** нет `.loop/board-projection.yaml` или `provider: none`
- **When:** finish
- **Then:** Transition OK; лог/result `projection_disabled: missing_config|provider_none`; 0 HTTP

#### Acceptance Scenarios — US-005

- **Given:** полный конфиг; fake REST 500
- **When:** finish
- **Then:** cursor phase уже новый; map.sync_error непустой; CLI board-sync повторяет move/create

#### Acceptance Scenarios — US-006

- **Given:** map.provider=`bitrix24`, config.provider=`plane`
- **When:** project_epic_phase
- **Then:** ошибка provider_mismatch; HTTP не вызывается; finish soft-fail пишет sync_error

### Functional Requirements (FR-###)

- **FR-001:** Система должна читать конфиг проекции pydantic-ом из `.loop/board-projection.yaml` (или env override path); invalid YAML → ProjectionConfigError (loud).
- **FR-002:** Система должна поддерживать `provider ∈ {none, bitrix24, plane}`; неизвестный provider → fail-closed.
- **FR-003:** Система должна экспонировать Protocol: `ensure_card(epic) -> external_id`, `move_card(external_id, phase) -> None`, `provider_name`.
- **FR-004:** После успешного cursor commit на `finish` / `halt` (и аналог terminal DONE) hot path должен вызывать единый `project_after_transition(transition)` **вне** CursorStore transaction.
- **FR-005:** Если mapping для epic_id отсутствует — lazy create (название/описание включают `epic_id`), затем атомарная запись sidecar. Колонка create: при активной phase → alias этой phase; при ensure без phase / epic только в queue → alias **`backlog`** (колонка обязательна в stage/state map).
- **FR-006:** Если mapping есть и `map.provider == config.provider` — move на column id из map для текущей phase (или сжатый alias → id). Канон aliases: `backlog | design | build | verify | done | blocked`.
- **FR-007:** Bitrix24 adapter: webhook REST `tasks.task.add` + `task.stages.movetask` (group + stageId из конфига).
- **FR-008:** Plane adapter: API key + `BASE_URL`; create work item/issue; update state с fail-closed проверкой что state реально сменился (защита от silent no-op CE/cloud field drift: слать совместимые поля / verify response).
- **FR-009:** Soft-fail: исключение projection не откатывает Transition; пишет stderr + `sync_error` в map (или sidecar errors file); exit code finish остаётся success transition.
- **FR-010:** Неполный конфиг активного provider → `projection_disabled` с reason (не HTTP, не silent).
- **FR-011:** Role allowlist (default `["back"]`); роль вне списка → disabled reason `role_not_allowed`.
- **FR-012:** CLI догона: `bin/loop.py board-sync [--epic ID]` использует тот же Protocol.
- **FR-013:** Lookup карточки **только** по sidecar `external_id`; FORBIDDEN search-by-title.
- **FR-014:** Kind I: `loop/README.md` (или `docs/`) описывает providers, конфиг, soft-fail, switch rules — не MCP-as-primary.

### Success Criteria (SC-###)

| ID | Измеримый результат | Проверка / источник | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | ≥1 targeted test на каждый adapter + registry switch | `bin/pytest loop/tests/test_board_projection*.py` | outcome |
| SC-002 | finish без конфига не делает HTTP | unit with httpx mock assert not called | outcome |
| SC-003 | provider_mismatch детектится до HTTP | unit | outcome |
| SC-004 | soft-fail сохраняет cursor phase | engine+projection integration fixture | outcome |

### Assumptions

- У оператора есть облачный Bitrix24 **или** доступный Plane (cloud/self-host) с API key.
- Колонки/states заведены вручную; в конфиг вписаны id (не автосоздание колонок в v1).
- Один активный provider за раз.
- Plane в «проекте» = внешний инстанс оператора; в дереве hub кода Plane нет — только REST client.

### [НУЖНО УТОЧНИТЬ]

- нет открытых CRITICAL (Plane base_url/workspace/project_id — ops config, не блокирует plan).

---

## AC

1. При полном конфиге `provider=bitrix24` finish без map → задача в группе + sidecar.
2. При полном конфиге `provider=plane` finish без map → work item + sidecar.
3. Finish со сменой phase → move/state update по map.
4. Смена provider при существующем map другого provider → явная ошибка, без HTTP к новому API с чужим id.
5. Нет конфига / `provider: none` → finish OK + explicit disabled.
6. REST ошибка → sync_error + finish не откатывается; `board-sync` чинит.
7. Finish не импортирует vendor clients напрямую (только Protocol/registry).

### AC−

1. Нет dual SoT (доска не пишет в loop).
2. Нет silent skip projection.
3. Нет match по title.
4. Нет hardcode sole Bitrix path в finish без adapter.
5. Нет dual-write в Bitrix и Plane одновременно.
6. Misconfig активного provider (битый map/stage) → loud error, не stub success sync.
7. Нет resurrect DSH `loop/board_sync` как SoT.

---

## Boundary / negative cases

| ID | Class | Input / condition | Expected (fail-closed) | Maps TM / AC |
|----|-------|-------------------|------------------------|--------------|
| BN-001 | empty / missing | нет projection config | disabled reason `missing_config`; 0 HTTP | TM-001 |
| BN-002 | unknown / DENY | `provider: jira` | ProjectionConfigError / disabled invalid | TM-002 |
| BN-003 | misconfig | plane без api_key при provider=plane | disabled/error `incomplete_provider_config` | TM-003 |
| BN-004 | provider mismatch | map bitrix + config plane | ProjectionError `provider_mismatch` | TM-004 |
| BN-005 | duplicate / idempotence | finish дважды same phase | move no-op или idempotent; не второй create | TM-005 |
| BN-006 | external I/O | REST 500 / timeout | sync_error set; cursor kept | TM-006 |
| BN-007 | authz | webhook/api key rejected 401 | sync_error; no silent pass | TM-006 |
| BN-008 | unknown phase | phase нет в stage/state map | sync_error `unknown_phase_mapping` | TM-007 |

Checklist:

| # | Class | Status |
|---|-------|--------|
| 1 | empty / missing required | done BN-001 |
| 2 | unknown key / DENY legacy SoT | done BN-002 |
| 3 | max / overflow / unicode | n/a: epic_id/title bounded by loop ids; unicode titles ok as pass-through |
| 4 | authz / unauthenticated | done BN-007 |
| 5 | duplicate / idempotence | done BN-005 |
| 6 | misconfig fail-closed (не stub) | done BN-003 · BN-004 · BN-008 |

---

## Техника / архитектура (HOW)

### Стек

- Python 3 + pydantic v2 (как loop config)
- HTTP: `httpx` (sync) для Bitrix webhook и Plane REST
- Конфиг/map: YAML validate-on-load
- Тесты: `bin/pytest` + httpx mock / respx / monkeypatch transport

### Layout (target)

```text
loop/board_projection/
  __init__.py
  protocol.py          # BoardProjectionAdapter Protocol + EpicRef + ProjectionResult
  config.py            # BoardProjectionSettings pydantic
  registry.py          # get_adapter(settings) -> adapter
  service.py           # project_after_transition / ensure_and_move
  mapping.py           # load/save .loop/board-epic-map.yaml
  adapters/
    bitrix24.py
    plane.py
  errors.py
loop/kernel/cli.py     # wire after successful finish/halt; subcommand board-sync
.loop/board-projection.yaml.example
.loop/board-epic-map.yaml          # runtime (gitignored pattern documented)
```

### Конфиг (пример)

```yaml
schema: loop-board-projection/v1
provider: plane   # none | bitrix24 | plane
role_allowlist: [back]
# сжатая доска — 6 колонок (обязательный backlog)
# backlog | design | build | verify | done | blocked
phase_alias:
  QUEUED: backlog          # epic в queue / board-sync --ensure без активной phase
  PLAN: design
  CLARIFY: design
  DECOMPOSE: design
  ANALYZE: design
  CREATIVE: design
  IMPLEMENT: build
  SECURITY: build
  AUDIT: build
  QA: verify
  BUGFIX: verify
  CONTEXT_SYNC: verify
  DONE: done
  HALT: blocked
providers:
  bitrix24:
    webhook_url: "https://<portal>.bitrix24.ru/rest/<user>/<code>/"
    group_id: 123
    stage_map:
      backlog: "<stageId>"
      design: "<stageId>"
      build: "<stageId>"
      verify: "<stageId>"
      done: "<stageId>"
      blocked: "<stageId>"
  plane:
    base_url: "https://api.plane.so"   # или self-host
    api_key_env: "PLANE_API_KEY"
    workspace_slug: "my-team"
    project_id: "<uuid>"
    state_map:
      backlog: "<state_uuid>"
      design: "<state_uuid>"
      build: "<state_uuid>"
      verify: "<state_uuid>"
      done: "<state_uuid>"
      blocked: "<state_uuid>"
```

**Backlog:** карточки эпиков, которые уже в `roadmap/queue.yaml`, но ещё не в активной phase (CLI `board-sync --ensure`, будущий queue-hook). Первый `finish` с phase уводит в Design/Build/…. Lazy create на finish с уже известной phase может сразу создать в Design — без обязательной остановки в Backlog.

Оператор может мапить phase→id напрямую без alias — оба режима валидны; DECOMPOSE уточнит одну schema (alias **или** flat phase keys, не dual silent).

### Mapping sidecar

```yaml
schema: loop-board-epic-map/v1
provider: plane
epics:
  T-HUB-108-loop-board-projection:
    external_id: "<uuid-or-task-id>"
    last_phase: IMPLEMENT
    sync_error: null
```

Смена `provider` в конфиге при непустом map с другим provider → **FAIL** до HTTP; оператор чистит map или запускает `board-sync --rebind` (если сделаем; иначе ручной delete map — documented). **cut:** без auto-migrate между провайдерами.

### Wire point (HARD)

1. `CursorStore.transact` / `engine.finish` **завершается успешно**.
2. CLI/`LoopEngine` caller вызывает `project_after_transition(...)`.
3. Projection **не** участвует в rollback cursor.
4. Halt/FAIL → phase alias `blocked` если есть в map.
5. Ensure без phase → alias `backlog` (колонка обязательна в map активного provider).

### Eng review spine

#### Data flow

```text
[Operator finish]
  -> [LoopEngine.finish] --sync txn--> [CursorStore]  (SoT)
  -> [project_after_transition] --sync--> [registry.get_adapter]
       -> [Bitrix24Adapter | PlaneAdapter] --HTTP--> [External board]
       -> [mapping.save] --fs--> [.loop/board-epic-map.yaml]
  soft-fail: errors -> stderr + sync_error (no cursor rollback)
```

#### Failure matrix

| Component / link | Failure | Detection | User/system response | Test ID |
|------------------|---------|-----------|----------------------|---------|
| Config load | missing/invalid | pydantic | disabled or hard error on CLI sync | TM-001 |
| Registry | unknown provider | validate | ConfigError | TM-002 |
| Mapping provider | mismatch | compare fields | ProjectionError; soft-fail finish | TM-004 |
| Bitrix REST | 4xx/5xx/timeout | httpx | sync_error | TM-006 |
| Plane REST | 4xx/5xx / state unchanged | httpx + response assert | sync_error | TM-006 |
| Stage map | phase missing | lookup | sync_error unknown_phase | TM-007 |
| Catch-up CLI | same as above | exit code | operator rerun | TM-008 |

#### Eng spine self-check

| Dimension | Score 1–5 | Gap / action |
|-----------|-----------|--------------|
| Data flow complete | 5 | Protocol + two adapters + wire |
| Failure coverage | 5 | soft-fail + mismatch + maps |
| Testability | 5 | fake transport per adapter |

---

## Replacement / sunset (brownfield)

Greenfield projection package. Sunset только запреты/инструкции.

### A. Code / modules

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| resurrect `loop/board_sync` DSH as SoT | `loop/board_projection/` | keep deleted (already absent); FORBIDDEN reintroduce as dual |
| n/a Bitrix-only finish hook | Protocol registry | n/a greenfield |

### B. Entrypoints / deploy

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| n/a | `finish` + `board-sync` | greenfield |

### C. Fallbacks / soft-fail

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| silent skip «нет битрикса — ок» без reason | explicit `projection_disabled` | delete in-epic (policy in new code) |
| soft «title search if no map» | mapping-only | FORBIDDEN |

### I. Instruction surfaces

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| «подключи MCP и двигай эпики» как primary для board mirror | README: adapter + provider switch | Kind I rewrite in-epic |
| prompt draft Bitrix-only wording | prompt multi-provider | already replaced |

---

<a id="qa-consumes"></a>
## QA consumes (test plan)

### Scope under test

- `loop/board_projection/**`, wire в finish/halt, CLI `board-sync`
- Out of scope: live cloud Bitrix/Plane (optional smoke manual); Frappe; MCP

### Test matrix

| ID | Priority | Scenario | Command / fixture | Expected | Maps FR/AC |
|----|----------|----------|-------------------|----------|------------|
| TM-001 | P0 | no config → disabled | `bin/pytest … -k projection_disabled` | finish OK; 0 HTTP | AC-5 · BN-001 · FR-010 |
| TM-002 | P0 | unknown provider | pytest | ConfigError | BN-002 · FR-002 |
| TM-003 | P0 | incomplete plane config | pytest | incomplete_provider_config | BN-003 · FR-010 |
| TM-004 | P0 | provider mismatch | pytest | ProjectionError; 0 HTTP | AC-4 · BN-004 · FR-006 |
| TM-005 | P0 | lazy create + second finish move | pytest fake HTTP bitrix+plane | create then move; one external_id | AC-1..3 · BN-005 · FR-005/006 |
| TM-006 | P0 | REST 500 soft-fail | pytest | cursor advanced; sync_error set | AC-6 · BN-006/007 · FR-009 |
| TM-007 | P0 | unknown phase mapping | pytest | sync_error unknown_phase | BN-008 · FR-006 |
| TM-008 | P0 | board-sync catch-up | pytest CLI | clears sync_error on success | AC-6 · FR-012 |
| TM-009 | P0 | finish does not import vendor | pytest / `rg` architecture | only protocol/registry from kernel/cli | AC-7 · FR-003/004 |
| TM-010 | P1 | role not in allowlist | pytest | disabled role_not_allowed | FR-011 |

### Regression notes

- Не поднимать live Bitrix/Plane в CI; только fake transport.
- Не путать soft-fail projection с silent skip.

---

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| CLARIFY / Product probe | L3 | done | clarify + §Product probe + Phase 1 amend |
| Eng review spine | L2+ | done | §Eng review spine |
| §0.11 counterparts (draft) | external REST | done | Bitrix methods + Plane work-item/state in HOW |
| Delivery closure | P0 runtime | done | §Delivery closure |
| Boundary / negative cases | L2+ | done | ≥3 BN + checklist |
| CREATIVE | no | n/a | CREATIVE need: нет |
| qa_consumes draft | L2+ | done | ≥3 TM; BN→TM |
| Plan review batch | L2+ | done | §Plan review batch log |

**FINISH PLAN allowed:** yes (no pending Required).

---

## Plan review batch log

| Phase | Auto-resolved | Deferred (owner/next) | Taste / CRITICAL surfaced |
|-------|---------------|-------------------------|---------------------------|
| Product | Multi-provider amend folded into single epic (not multi-epic): оба adapter — одна capability «projection port» | Plane hosting ops ids — operator config | none CRITICAL |
| Eng | Protocol+registry over Bitrix-only; soft-fail outside txn; provider-scoped map | Auto-migrate map between providers — cut | none |

---

## До DECOMPOSE (черновик нарезки)

Hint (Effort probe на DECOMPOSE задаст `sNN_cap`):

1. `s01` — config + mapping schemas + Protocol + registry + errors  
2. `s02` — Bitrix24 adapter + tests  
3. `s03` — Plane adapter + tests (state verify)  
4. `s04` — service ensure/move + soft-fail + provider_mismatch  
5. `s05` — wire finish/halt + CLI board-sync + Kind I README  

---

## Appetite

| Поле | Значение | Описание |
| :--- | :--- | :--- |
| `timebox_days` | `3` | Protocol + 2 adapters + wire |
| `cut_list` | comments on card; auto-create columns; OAuth; dual-provider fanout; auto-migrate map; Linear adapter | вырезать первым при overrun |

---

## Следующий режим

→ **BACK DECOMPOSE** `T-HUB-108-loop-board-projection`
