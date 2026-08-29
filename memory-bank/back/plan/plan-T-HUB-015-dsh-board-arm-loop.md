# [T-HUB-015 | dsh-board-arm-loop] PLAN

**Дата:** 2026-08-27  
**Режим:** BACK PLAN  
**Уровень:** L4  
**Статус:** active  
**Roadmap:** [roadmap-dsh-mb-board-epics.md](roadmap-dsh-mb-board-epics.md)  
**Queue:** [roadmap-dsh-mb-board-epics.queue.yaml](roadmap-dsh-mb-board-epics.queue.yaml)  
**Deps:** **hard** T-HUB-014. Soft recommend: T-HUB-006 (DSH runtime), T-HUB-007/008 (profiles/gates) для production DSH path.

**Skills:** writing-plans · architecture-patterns · python-testing-patterns · brainstorming (batch decisions below)

→ [decompose-T-HUB-015-dsh-board-arm-loop/index.md](decompose-T-HUB-015-dsh-board-arm-loop/index.md) — **единственный трекер статуса шагов**

---

## Контекст

- **req:** с DSH Task Board уметь **arm** задачи (шага эпика) в `memory-bank/activeContext.md` и **запускать loop** (`dev-hub/bin/loop` / `make loop`) для pinned workspace — без превращения stock `kind:run` (agent free-session) в обход prepare/FINISH gates.
- **deps:** T-HUB-014 даёт `mb-*` cards + `mb-board-card/v1` metadata (`card_kind`, `project_root`, `epic_id`, `step_id` optional, `gate_phase`, `decompose_rel`, `workspace_id`).
- **refs:** `loop/context_loop.py` (`arm`, `prepare`, `arm_session`, `arm_roadmap_entry`); `dev-hub/bin/loop`; `make/product.mk` `loop:`; Task Board `HostExecutionRunner.launch` (sessions.create + prompt) — **не** SoT executor для mb-cards; T-HUB-008 pattern (Cordis → Python shell-out); [roadmap §канон](roadmap-dsh-mb-board-epics.md).

### Зафиксированные решения (brainstorming batch)

| Тема | Решение |
|------|---------|
| Primary executor | **`PROJECT_ROOT=<card.project_root> DEV_HUB=<hub> bin/loop`** (или `make -C product loop`). Loop сам делает `prepare` → agent session → `record-session` → `check-after` |
| Stock Task Board `kind:run` для `mb-*` | **Intercept / deny-as-primary:** Cordis plugin `@dev-hub/dsh-mb-bridge` перехватывает run mb-cards и **перенаправляет** на `loop-run` pipeline; если plugin disabled → **fail-closed** loud error в Host (не тихий agent prompt) |
| Arm | Host/CLI вызывает `python3 loop/context_loop.py --cwd "$PROJECT_ROOT" arm --epic "$decompose_rel_or_id"` **до** loop. Для ROADMAP tip cards → `roadmap-advance` **запрещён** с доски без явного `allow_roadmap_advance=true` config (default false) — вместо этого arm конкретного epic из metadata или `arm --epic decompose-…` |
| Step targeting | **step:** после arm JSON `step_id` == metadata `step_id` → fail-closed `step_mismatch`. **gate:** `step_id` absent; arm по `decompose_rel` + projection phase (`BACK QA` …); **не** проверять step_id; **не** вызывать `roadmap-advance` для ROADMAP gate (default) |
| Hub location | Env `DEV_HUB` required for loop-run; default resolve: sibling heuristic documented; misconfig → fail |
| Concurrency | Один loop на `project_root` (flock уже в loop). Повторный loop-run while flock held → fail with clear message |
| UI | Plugin **mb-bridge** client: кнопки **Arm** · **Run loop** · **Arm+Run** (primary CTA на `mb-*`) · **Sync**; header **workspace filter** + **runtime** + **model preset** (whitelist). Stock Run на `mb-*` intercept/deny. Non-mb cards — stock run |
| Workspace filter | **Client-side** filter по `metadata.workspace_id` / `project_root` (stock board search не фильтрует workspace). Dropdown «All workspaces» + entries из DSH `workspace.list` ∩ карточки на board. **Не** mutates ledger — только видимость колонок |
| Model / runtime control | **Канон:** product `.claude/project.env` `PROJECT_LOOP_<PHASE>_MODEL` + `prepare` phase key. **Board override (one run):** whitelist `modelPresets[]` → extra argv после `PROJECT_ROOT` **или** env `LOOP_CLI_MODEL` (single token, validated). **DSH:** config `defaultRuntime: claude|dsh` → spawn env `EPIC_RUNTIME=dsh` (profiles T-HUB-007). **FORBIDDEN:** free-text model из browser; stock card `mode` preset **не** primary для `mb-*` |
| Model preset UX | Dropdown в board header (mb-bridge): «Phase default (env)» · presets из config · optional per-run only. Label показывает effective source: `env:PROJECT_LOOP_IMPLEMENT_MODEL` vs `preset:gpt` |
| CLI parity | `hub-board arm|loop|arm-loop --task-id` · `--loop-args gpt` · `--runtime dsh|claude` · `sync --workspace-id` (reuse 014) |
| Prompt на mb-card | После 015 sync (014 hook or 015 update): prompt = точная команда роли из phase (`BACK IMPLEMENT` / `BACK QA` …) **информативно**; исполнение всё равно через loop, не через sessions.prompt alone |
| Observability | Loop stdout/stderr → Host-visible execution record: plugin wraps subprocess, maps exit codes to board execution `succeeded|failed`; sessionId optional (`loop` state dir path in error/result text) |
| Security | Browser never sends shell. Only Host plugin spawns fixed argv: `python3`, `bin/loop`, fixed flags. No user-controlled executable path field |
| Jira | Out of scope |
| CREATIVE | узкий mapping Cordis events ↔ CLI — закрыт таблицами; отдельный creative shard optional if DECOMPOSE finds API ambiguity |

**CREATIVE need:** optional (только если при DECOMPOSE Cordis intercept API нестабилен — тогда `creative-dsh-mb-bridge-hooks.md`).

---

## Цель

С карточки `mb-*` на Task Board: arm step/gate, loop с контролируемым runtime/model override, workspace-фильтр в UI, кнопки Arm/Run/Arm+Run/Sync — fail-closed, без stock agent bypass.

---

## Продуктовая спека (WHAT)

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как разработчик, я хочу нажать Arm на карточке шага, чтобы `activeContext` продукта указал на этот step. | P0 | CLI arm на fixture → activeContext load_now содержит step shard |
| US-002 | Как разработчик, я хочу запустить loop с доски, чтобы пошёл тот же pipeline, что `make loop`. | P0 | Fake loop binary invoked with PROJECT_ROOT; prepare not skipped |
| US-003 | Как разработчик, я хочу Arm+Run одной кнопкой. | P1 | arm-loop CLI order: arm ok then loop |
| US-004 | Как разработчик, я не хочу чтобы Run на mb-card запускал «голый» agent в обход loop. | P0 | Intercept test: stock run path denied/redirected |
| US-005 | Как разработчик, я хочу понятную ошибку если step на card устарел. | P0 | step_mismatch → non-zero + diagnostic |
| US-006 | Как разработчик, я хочу фильтр workspace на доске, чтобы видеть только dev-hub или только product. | P1 | UI filter hides other `workspace_id`; ledger unchanged |
| US-007 | Как разработчик, я хочу выбрать model preset перед Arm+Run, без правки `.env` на каждый клик. | P1 | Preset `gpt` → loop argv contains `gpt`; phase env still wins if set |
| US-008 | Как разработчик, я хочу кнопку Sync после loop, чтобы карточки обновились без CLI. | P1 | Sync button → `hub-board sync --workspace-id` for filtered ws |

#### Acceptance Scenarios — US-006

- **Given:** board has cards for workspace A and B; filter = A
- **When:** user opens task board with mb-bridge mounted
- **Then:** column cards only `metadata.workspace_id=A`; B hidden; clearing filter shows both

#### Acceptance Scenarios — US-007

- **Given:** config `modelPresets: [{id:gpt, args:[gpt]}]`; product has `PROJECT_LOOP_IMPLEMENT_MODEL` unset
- **When:** user selects preset `gpt` and Arm+Run on IMPLEMENT step card
- **Then:** subprocess argv = `bin/loop PROJECT_ROOT gpt` (exact test); if `PROJECT_LOOP_IMPLEMENT_MODEL` set → env wins, UI shows warning «phase env overrides preset»

#### Acceptance Scenarios — US-001

- **Given:** mb-card metadata `project_root=P`, `decompose_rel=…/decompose-T-X`, `step_id=s02`, и s02 pending в index
- **When:** `hub-board arm --task-id <id>`
- **Then:** `P/memory-bank/activeContext.md` Handoff/load_now указывает s02; epic state armed

#### Acceptance Scenarios — US-002

- **Given:** card armed successfully (or arm-loop)
- **When:** `hub-board loop --task-id <id>` with `LOOP_BIN` stub
- **Then:** stub called once with cwd/env `PROJECT_ROOT=P`; board execution record `succeeded` if exit 0

#### Acceptance Scenarios — US-004

- **Given:** plugin mounted; user triggers stock run on mb-card
- **When:** Host processes run
- **Then:** либо redirect на loop-run, либо explicit error `mb_card_requires_loop_run` — **не** `sessions.prompt` с freeform implement

### Functional Requirements (FR-###)

- **FR-001:** Parse `mb-board-card/v1`; require `card_kind`; invalid → fail-closed.
- **FR-001b:** `card_kind=gate` → arm epic for phase command (no `step_mismatch`); `card_kind=step` → existing step rules.
- **FR-002:** `arm_from_card(task) →` call `context_loop.arm` with `--cwd project_root --epic decompose…`; verify resulting `step_id` matches metadata (or document allow_any_pending flag default **false**).
- **FR-003:** `loop_from_card(task) →` spawn `DEV_HUB/bin/loop "$PROJECT_ROOT" $ARGS` with env; capture exit code.
- **FR-004:** `arm_loop_from_card` = FR-002 then FR-003; stop if arm fails.
- **FR-005:** Cordis plugin `@dev-hub/dsh-mb-bridge`: Host-side handlers for arm / loop-run; intercept mb-* stock run.
- **FR-006:** CLI commands on `bin/hub-board`: `arm`, `loop`, `arm-loop` (+ flags `--dry-run`, `--task-id`, `--ledger`/`--from-state` for tests).
- **FR-007:** Execution recording: update board task executions (via Host API or client) with result + truncated log path.
- **FR-008:** Config: `devHub`, `loopBin`, `allowRoadmapAdvance`, `defaultLoopArgs`, `defaultRuntime`, `modelPresets[]`, `workspaceFilterEnabled`, `syncAfterLoop`, `enabled` (see §Plugin config).
- **FR-009:** Docs: runbook «sync → filter → preset → arm+loop»; model precedence table; troubleshooting flock / step_mismatch / missing DEV_HUB.
- **FR-010:** Tests: pure arm matching; subprocess argv builder; plugin unit with fake; workspace filter; preset validation.
- **FR-011:** After loop — auto `hub-board sync --workspace-id` when `syncAfterLoop=true` (default **true**) or manual Sync button.
- **FR-012:** **Workspace filter (client):** mb-bridge injects board header dropdown; options from Host `workspace.list` + «All»; filter key = `workspace_id` on parsed mb metadata; persist selection in `localStorage` key `mb-bridge.workspaceFilter`.
- **FR-013:** **Sync button:** invokes Host → `hub-board sync` with `--workspace-id` when filter ≠ All, else full sync; shows last sync summary (counts upsert/archive) in toast or board meta line.
- **FR-014:** **Model preset whitelist:** config `modelPresets: [{id, label, args: string[]}]` — max 8 entries; `args` = loop CLI tokens after `PROJECT_ROOT`; validate `^[a-zA-Z0-9._/-]+$` per token; reject unknown preset id from UI.
- **FR-015:** **`build_loop_argv` precedence:** (1) phase env `PROJECT_LOOP_<PHASE>_MODEL` in product `.claude/project.env` → prepare canon (**no** preset argv; UI badge «env»); (2) else UI preset → `preset.args`; (3) else `defaultLoopArgs`; (4) else bare `bin/loop PROJECT_ROOT`.
- **FR-016:** **Runtime toggle:** config `defaultRuntime: claude|dsh` + UI override (`localStorage`); spawn sets `EPIC_RUNTIME` for subprocess only; does not edit product files.
- **FR-017:** **Card detail actions (mb-* only):** primary **Arm+Run**; secondary Arm · Run loop. Stock Run hidden/replaced on mb-* detail.
- **FR-018:** **FORBIDDEN:** browser raw shell, arbitrary model string, stock `task.mode` as loop model for mb-*.

### Success Criteria (SC-###)

| ID | Измеримый результат | Проверка | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | Arm меняет activeContext только в `project_root` карточки | unit fixture | outcome |
| SC-002 | Loop argv содержит abs project root + hub bin | unit | outcome |
| SC-003 | mb stock-run не создаёт ordinary agent prompt path | plugin test | outcome |
| SC-004 | step_mismatch → exit ≠ 0 | unit | outcome |
| SC-005 | Non-mb card stock run unchanged | plugin test | outcome |
| SC-006 | Workspace filter hides non-matching cards client-side | plugin/dom test | outcome |
| SC-007 | Preset argv appended when phase env unset | unit build_loop_argv | outcome |
| SC-008 | Phase env set → preset not appended; diagnostic in result | unit | outcome |

### Assumptions

- T-HUB-014 cards already on board with valid metadata.
- Product may use Claude or DSH via existing `EPIC_RUNTIME` — board launch не форсирует dsh.
- User понимает: loop может быть long-running; board UI остаётся async view (как stock runner).

### Clarifications

- Session: 2026-08-27. Locked: loop = executor; arm via context_loop; intercept stock run for mb-*.
- Session: 2026-08-27. Locked: workspace filter client-side; model via env > preset > defaultLoopArgs; UI buttons Arm/Run/Arm+Run/Sync; DSH runtime toggle.

### [НУЖНО УТОЧНИТЬ]

- n/a CRITICAL. Soft: точный Cordis hook name для перехвата `task-board` run (зависит от версии plugin API) — spike в s01 DECOMPOSE; если API нет → Host wrapper route `/api/mb-bridge/*` + UI buttons without intercept (stock run disabled by emptying prompt + announce).

---

## AC

### AC+

1. Unit: `parse_card_metadata` valid/invalid  
2. Unit: `build_arm_argv` / `build_loop_argv` exact lists  
3. Unit: arm_from_card happy path updates fixture activeContext  
4. Unit: step_mismatch fails  
5. Unit: arm-loop short-circuits on arm failure (loop not called)  
6. Unit/Fake: loop stub exit 0 → execution succeeded  
7. Plugin/config: mb run intercepted (or alternate UI path documented + tested)  
8. Non-mb run passthrough  
9. Docs runbook in `dsh/README.md`  
10. `hub-board arm|loop|arm-loop --help`  
11. Unit: workspace filter logic (metadata.workspace_id)  
12. Unit: model preset whitelist validation rejects bad tokens  
13. Plugin: header controls render; Sync calls hub-board  
14. Docs: model precedence table + workspace filter + runtime toggle  

### AC−

1. Не делать board SoT  
2. Не вызывать произвольный shell из browser payload  
3. Не `roadmap-advance` с доски по умолчанию  
4. Не требовать Jira  
5. Не заменять `finalize-step` / verify gates  
6. Не запускать frontend tests из plugin  
7. Не silent fallback stock agent run for mb-cards  
8. Не использовать stock `task.mode` как model path для mb-* loop  
9. Не allow free-text model input from browser (whitelist only)  
10. Не mutate ledger при workspace filter (view-only)  

---

## Техника / архитектура (HOW)

### Стек

- Python: extend `loop/board_sync` → `loop/board_bridge/` or `loop/board_sync/launch.py` (prefer `loop/board_launch/` package to keep 014 sync pure)
- TypeScript: `dsh/plugins/mb-bridge/` private package `@dev-hub/dsh-mb-bridge` (mirror T-HUB-008 layout)
- Subprocess Host → Python only

### Модули

| Path | Action | Role |
|------|--------|------|
| `loop/board_launch/__init__.py` | Create | |
| `loop/board_launch/metadata.py` | Create | Reuse/import card_model from board_sync |
| `loop/board_launch/arm.py` | Create | arm_from_card |
| `loop/board_launch/loop_run.py` | Create | argv + subprocess + model precedence |
| `loop/board_launch/loop_argv.py` | Create | `build_loop_argv(project_root, phase, preset_id, config)` |
| `loop/board_launch/pipeline.py` | Create | arm_loop + optional syncAfterLoop |
| `bin/hub-board` | Modify | subcommands arm/loop/arm-loop |
| `dsh/plugins/mb-bridge/package.json` | Create | |
| `dsh/plugins/mb-bridge/src/index.ts` | Create | Cordis apply |
| `dsh/plugins/mb-bridge/src/intercept-run.ts` | Create | mb-* run redirect |
| `dsh/plugins/mb-bridge/src/python-bridge.ts` | Create | spawn hub-board |
| `dsh/plugins/mb-bridge/src/board-controls.tsx` | Create | workspace filter + runtime + model preset header |
| `dsh/plugins/mb-bridge/src/card-actions.tsx` | Create | Arm / Run / Arm+Run / Sync on mb detail |
| `dsh/plugins/mb-bridge/src/board-filter.ts` | Create | client filter by workspace_id |
| `dsh/plugins/mb-bridge/cordis.patch.yml` | Create | |
| `dsh/scripts/install-mb-bridge.sh` | Create | |
| `loop/tests/test_board_launch_*.py` | Create | |
| `dsh/README.md` | Modify | Arm/loop section |
| `dsh/plugins/mb-bridge/README.md` | Create | Parity / security |

### Архитектура

```mermaid
sequenceDiagram
  participant UI as Task Board UI
  participant Host as DSH Host + mb-bridge
  participant Py as hub-board / board_launch
  participant CL as context_loop arm
  participant Loop as bin/loop
  participant MB as PROJECT_ROOT/memory-bank

  UI->>Host: Arm / Run loop (mb-card)
  Host->>Py: fixed argv hub-board arm-loop --task-id
  Py->>Py: parse mb-board-card/v1
  Py->>CL: arm --cwd PROJECT_ROOT --epic decompose-…
  CL->>MB: rewrite activeContext + epic state
  CL-->>Py: ok + step_id
  Py->>Py: assert step_id matches card
  Py->>Loop: bin/loop PROJECT_ROOT
  Loop->>MB: prepare / session / finalize path
  Loop-->>Py: exit code
  Py-->>Host: result for executions[]
  Host-->>UI: snapshot revision
```

### Argv contracts (fail-closed)

```bash
# Arm
python3 "$DEV_HUB/loop/context_loop.py" --cwd "$PROJECT_ROOT" arm --epic "$DECOMPOSE_REL_OR_ID"

# Loop — preset wins only if phase env unset (see Model precedence)
"$DEV_HUB/bin/loop" "$PROJECT_ROOT" "${LOOP_EXTRA_ARGS[@]}"
# env: PROJECT_ROOT, DEV_HUB, EPIC_RUNTIME (claude|dsh), optional LOOP_CLI_MODEL audit in logs
```

**CLI flags (hub-board):**

```bash
hub-board loop --task-id ID [--loop-args gpt] [--runtime dsh|claude] [--dry-run]
hub-board arm-loop --task-id ID [--loop-args sonnet] [--runtime claude]
hub-board sync [--workspace-id WS]   # reuse 014
```

**FORBIDDEN argv patterns:** `shell=True`, user-supplied binary, interpolated raw prompt as bash, arbitrary model string not in whitelist.

### Model precedence (канон для README)

| Priority | Source | Effect |
|----------|--------|--------|
| 1 | `PROJECT_LOOP_<PHASE>_MODEL` in product `.claude/project.env` | `prepare` picks model; **ignore** UI preset argv for that iteration |
| 2 | UI **model preset** (`modelPresets[].args`) | Extra tokens after `PROJECT_ROOT` |
| 3 | Config `defaultLoopArgs` | Fallback argv |
| 4 | Bare `bin/loop PROJECT_ROOT` | No model token |

**DSH path:** `EPIC_RUNTIME=dsh` (config/UI) → loop uses `dsh --profile epic-<phase>`; model inside profile / `phase-models.yml` (T-HUB-007). UI preset **не** заменяет DSH profile LLM row — only switches runtime family.

**Stock Task Board `task.mode`:** agent preset for **non-mb** stock run only; mb-bridge **не** читает `mode` для loop.

### Board UI controls (mb-bridge client)

Inject into Task Board view (Cordis client patch / slot adjacent to board header — same pattern as T-HUB-008):

```
┌─────────────────────────────────────────────────────────────────┐
│ [Workspace ▼ All | dev-hub | test_project]  [Runtime ▼ claude|dsh] │
│ [Model ▼ Phase default | gpt | sonnet | …]     [Sync] [⚙]        │
├─────────────────────────────────────────────────────────────────┤
│  kanban columns (filtered cards only)                             │
└─────────────────────────────────────────────────────────────────┘

Card detail (mb-*):
  [ Arm+Run ]  [Arm]  [Run loop]     ← primary = Arm+Run
  workspace: read-only from metadata (pinned)
  Model: badge env / preset / default
```

| Control | Behavior |
|---------|----------|
| Workspace filter | Client filter by `workspace_id`; «All» = no filter; ledger unchanged |
| Runtime | `claude` = default; `dsh` = `EPIC_RUNTIME=dsh` on subprocess env |
| Model preset | Maps to `--loop-args`; badge «env overrides» when phase env set |
| Sync | `hub-board sync --workspace-id` when filtered; else full sync |
| Arm+Run | Primary button; uses filter + preset + runtime |

**Persistence:** `localStorage` `mb-bridge.workspaceFilter`, `mb-bridge.runtime`, `mb-bridge.modelPreset`.

### Plugin config (cordis) — full schema

```yaml
mb-bridge:
  enabled: true
  devHub: /path/to/dev-hub
  loopBin: bin/loop
  syncAfterLoop: true
  allowRoadmapAdvance: false
  interceptMbStockRun: true
  defaultRuntime: claude
  defaultLoopArgs: []
  workspaceFilterEnabled: true
  modelPresets:
    - id: gpt
      label: "GPT (loop default)"
      args: ["gpt"]
    - id: sonnet
      label: "Claude Sonnet"
      args: ["sonnet"]
```

### step_mismatch rules

**Применяется только `card_kind=step`.**

1. After arm JSON `step_id` read  
2. Compare to card metadata `step_id` (case-sensitive sNN)  
3. Mismatch → exit 2, `diagnostic_code=step_mismatch`, do not start loop  
4. Optional override `--force-armed-step` **only** on CLI with explicit flag (not exposed in UI v1)

### gate arm rules (`card_kind=gate`)

1. `gate_phase` ∈ `{CLARIFY, ANALYZE, AUDIT, QA, BUGFIX, REFLECT, PLAN, DECOMPOSE}` → `arm --epic decompose_rel` (если decompose exists) **или** arm roadmap entry для PLAN-only gate.  
2. `gate_phase=ROADMAP` → **не** `roadmap-advance` по умолчанию; arm explicit epic from metadata или fail `roadmap_advance_denied`.  
3. Loop `prepare` выбирает phase model по `gate_phase` / projection (`PROJECT_LOOP_QA_MODEL` …). UI preset subject to §Model precedence.  
4. **FORBIDDEN:** `step_mismatch` check на gate cards.

### Interaction with T-HUB-008

- epic-gate остаётся ответственным за FINISH/verify внутри agent session  
- mb-bridge **не** дублирует gate logic; только arm+spawn loop  
- Order: mb-bridge launches loop → loop prepare → dsh/claude session → epic-gate (if dsh) 

### Post-loop sync

If `syncAfterLoop=true`: invoke `hub-board sync --workspace-id <id>` after loop exit (any code) to refresh cards; sync failure → warning in execution error text, не rewrite loop exit code (or configurable).

---

## Replacement / sunset (brownfield)

Не replace loop. Частичный replace UX stock run for mb-cards:

### A. Code / modules

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| Использование stock `HostExecutionRunner.launch` как primary для `mb-*` | mb-bridge loop-run | delete in-epic (intercept) |
| Stub prompt «T-HUB-015 later» как единственный CTA | Arm/Run loop UI + CLI | delete in-epic |

### B. Entrypoints / deploy

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| Manual only `make loop` without board path | board + `hub-board arm-loop` | keep (оба валидны) |

### C. Fallbacks / soft-fail

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| Silent stock agent run when bridge misconfigured | fail-closed error on mb run | delete in-epic |
| Soft ignore step_mismatch | hard fail | delete in-epic |

---

## Тест-стратегия

1. Python TDD first (metadata, arm match, argv, pipeline)  
2. Fake subprocess for loop binary  
3. Plugin: unit-test intercept decision table (mb vs non-mb) with mocked Host  
4. Manual smoke: sync (014) → arm-loop on real board (docs checklist)  
5. `timeout 300s .venv/bin/pytest loop/tests/test_board_launch_*.py loop/tests/test_board_sync_*.py -q` regression  

---

## Риски

| Риск | Митигация |
|------|-----------|
| Cordis cannot intercept task-board run | Alternate `/api/mb-bridge/action` + UI buttons; disable prompt run for mb via sync prompt + announce |
| Arm races with live IMPLEMENT other epic | flock + step_mismatch + document single active epic per project |
| Long loop blocks Host | async execution record like stock runner; do not block HTTP forever — background job + SSE (mirror task-board patterns) |
| DEV_HUB wrong on machine | fail-closed; config + env |
| 014 metadata schema drift | shared module import; contract test |
| User expects board `mode` = loop model | README + UI badge; mb ignores `task.mode` |
| Preset vs env confusion | dry-run shows effective argv; UI «env overrides» badge |

---

## Нарезка (DECOMPOSE s01–s10)

Трекер: [decompose-T-HUB-015-dsh-board-arm-loop/index.yaml](decompose-T-HUB-015-dsh-board-arm-loop/index.yaml)

| sNN | Slug | next_phase |
|-----|------|------------|
| s01 | spike-cordis-intercept-api-decision | BACK IMPLEMENT |
| s02 | board-launch-metadata-card-model | BACK IMPLEMENT |
| s03 | loop-argv-model-precedence | BACK IMPLEMENT |
| s04 | arm-from-card-step-mismatch | BACK IMPLEMENT |
| s05 | loop-run-subprocess-execution-result | BACK IMPLEMENT |
| s06 | arm-loop-pipeline-sync-after-loop | BACK IMPLEMENT |
| s07 | cli-hub-board-arm-loop-arm-loop | BACK IMPLEMENT |
| s08 | dsh-plugin-mb-bridge-host-bridge | BACK IMPLEMENT |
| s09 | board-controls-ui-workspace-filter-model-preset | BACK IMPLEMENT |
| s10 | docs-install-regression-suite | BACK IMPLEMENT |

---

## Следующий режим

→ После QA/REFLECT **T-HUB-014**: **BACK DECOMPOSE** `T-HUB-015`  
→ CREATIVE only if s01 spike требует design shard  
→ IMPLEMENT.
