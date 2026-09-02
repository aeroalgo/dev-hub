# [T-HUB-045 | harness-workflow-session-load-api] PLAN

**Дата:** 2026-09-02  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** active  
**Roadmap:** [roadmap-harness-maturity-borrowings-epics.md](roadmap-harness-maturity-borrowings-epics.md)  
**Queue:** [roadmap-harness-maturity-borrowings-epics.queue.yaml](roadmap-harness-maturity-borrowings-epics.queue.yaml)  
**Deps:** **hard** T-HUB-040 (`loop/mb_finish` schemas + CLI/MCP pattern). **Soft:** T-HUB-022 (done — `loop-handoff/v1`), T-HUB-008 (session-start hook bridge).

**Skills:** writing-plans · architecture-patterns · python-testing-patterns · fastapi-templates (MCP transport only)

→ [decompose-T-HUB-045-harness-workflow-session-load-api/index.md](decompose-T-HUB-045-harness-workflow-session-load-api/index.md) — **после DECOMPOSE**

---

## Контекст

- **req:** Сократить ошибки LLM при **старте** workflow-сессии: агент вручную читает `activeContext.md`, парсит `load_now`, делает 3–6 вызовов `Read`, иногда пропускает shard, тянет полный `plan-*.md` или файлы из `done — do NOT load`.
- **gap (as-built):**
  - `extract_load_now()`, `validate_active_context_shape()`, `fingerprint_context()` есть в `harness/hooks/epic/core.py`, но **нет** единого runtime API, который собирает bundle.
  - `session_start_payload()` инжектит только короткую подсказку, **без содержимого** артефактов.
  - Session start описан prose в `context-session-economy.mdc` / workflow rules — исполняется LLM, не runtime.
  - T-HUB-040 закрывает **mutation** (FINISH / `mb-finish`); **query** (START) остаётся на усмотрение модели.
  - Нет аудита «что именно загрузил агент» (fingerprint bundle vs handoff fingerprint).
- **refs:** чат 2026-09-02 (идея `mb-load` как зеркало `mb-finish`); `harness/hooks/session-start.py`; `.cursor/rules/shared/context-session-economy.mdc` §3; `loop/mb_finish/schemas.py` (`LoopHandoffMeta`, `LoadNowItem`).

**CREATIVE need:** нет.

---

## Technology axiom (replace-not-wrap)

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Session load request | Pydantic model → JSON CLI args | LLM сам парсит `load_now` как primary path |
| Session load response | JSON `{ok, meta, files[], fingerprint, diagnostic_codes[]}` | prose «я прочитал shard» без machine bundle |
| Path resolution | `extract_load_now` + mode validators | ad-hoc glob «прочитай plan» |
| Forbidden paths | runtime denylist (`done`, full `plan-*.md` вне PLAN/DECOMPOSE) | silent skip или загрузка запрещённого |
| MCP (optional) | thin wrapper над те же pydantic models | второй resolver с иной семантикой |

DECOMPOSE → purge-step: prose «прочитай activeContext → load_now» в workflow rules заменить на «вызови `mb-load session`».

---

## Продуктовая спека (WHAT)

### Product probe (Phase 0 skipped — taxonomy clear)

| # | Question | Answer / Probe | Decision / Impact |
|---|----------|----------------|-------------------|
| 1 | **Reframe:** Какую проблему решаем? | Harness ломается на **prose START** — агент не загружает work shard / тянет лишнее | Фокус = query API, не новый doc router |
| 2 | **Narrowest wedge:** Минимальный slice? | `load_session` — activeContext + load_now files + shape check | Phase 1 до plan_section / MCP |
| 3 | **Pre-mortem:** Провал через месяц? | Mega-bundle тащит весь plan → token bloat | Enforce lean load + size cap per file |
| 4 | **Distribution:** Кто вызывает? | Parent agent / loop runner / session-start hook | Не отдельный daemon |
| 5 | **Technical leverage:** Что переиспользовать? | `extract_load_now`, `validate_active_context_shape`, `LoopHandoffMeta` из mb_finish | Один пакет `loop/mb_load`, shared schemas import |
| 6 | **Appetite:** Стоит ли? | Да — симметрия с T-HUB-040, −2–4 tool calls на сессию | L3, ~6–8 sNN |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как parent IMPLEMENT, я хочу один CLI вызов в начале сессии, чтобы получить work shard + index.yaml без ручных Read. | P0 | `mb-load session` → JSON `ok:true`, files содержат sNN yaml + index.yaml |
| US-002 | Как operator, я хочу fail-closed если activeContext shape invalid, чтобы агент не работал на битом cursor. | P0 | shape errors → `ok:false`, `diagnostic_codes` содержит коды validator |
| US-003 | Как platform, я хочу denylist forbidden paths, чтобы агент не загрузил `done` или полный plan вне PLAN. | P0 | load_now с plan.md в IMPLEMENT → skipped + diagnostic |
| US-004 | Как parent QA/BUGFIX, я хочу тот же API с mode-specific bundle (qa/bugfix shard). | P1 | pytest matrix QA/BUGFIX fixtures |
| US-005 | Как parent, я хочу опциональный `plan_section` jump из Consumes, не весь plan. | P1 | `--plan-section N` → только §N body |
| US-006 | Как loop runner (EPIC_LOOP), я хочу session-start inject bundle fingerprint, чтобы первый turn был warm. | P1 | session-start hook при EPIC_LOOP=1 |
| US-007 | Как Cursor user, я хочу MCP `load_session` с CLI parity. | P2 | MCP descriptor test = CLI JSON |
| US-008 | Как auditor, я хочу fingerprint bundle в ответе для сверки с stop-gate / episode package. | P1 | fingerprint stable для same inputs |

#### Acceptance Scenarios — US-001

- **Given:** activeContext IMPLEMENT s05, load_now lists decompose s05 + index.yaml, shape valid
- **When:** `python3 harness/hooks/epic_resolve.py mb-load session --cwd $PROJECT_ROOT`
- **Then:** JSON `ok:true`, `meta.step_id=s05`, `files` ≥2 entries with paths and content, `fingerprint` non-empty

#### Acceptance Scenarios — US-003

- **Given:** load_now accidentally lists completed s03 path or full `plan-*.md` in IMPLEMENT mode
- **When:** same command
- **Then:** forbidden paths in `forbidden_skipped[]`, not in `files[]`; `ok:true` if remaining bundle valid OR `ok:false` if nothing left to load

### Functional Requirements (FR-###)

- **FR-001:** Модуль `loop/mb_load/` — pydantic request/response (`mb-load-request/v1`, `mb-load-result/v1`); reuse `LoopHandoffMeta` from `loop/mb_finish/schemas.py` (import, не дублировать).
- **FR-002:** `load_session(cwd, plan_section: int | None = None)` — read activeContext, parse frontmatter, `extract_load_now`, validate shape, load files with per-file size cap (configurable default, e.g. 512KiB).
- **FR-003:** Forbidden policy: paths matching `done — do NOT load` section; full `plan-*.md` when `mode ∉ {PLAN, DECOMPOSE}`; `index.md` when `index.yaml` canon exists for IMPLEMENT.
- **FR-004:** CLI `epic_resolve.py mb-load session [--cwd] [--plan-section N] [--json]` → stdout JSON, exit 0 только при `ok:true`.
- **FR-005:** Response fields: `meta`, `handoff` (body text), `files: [{path, content, sha256}]`, `fingerprint`, `forbidden_skipped`, `diagnostic_codes`.
- **FR-006:** `load_plan_section(cwd, section: int)` — optional subcommand; extract single `##` section from plan by epic_id in meta; fail if plan missing.
- **FR-007:** Mode matrix helpers: IMPLEMENT auto-resolve implement yaml by `step_id` if missing from load_now (read-only, add to bundle).
- **FR-008:** Extend `session_start_payload()` (or delegate) — when `EPIC_LOOP=1`, append bundle summary + fingerprint to `additionalContext` (not full files if too large — link + fingerprint + file list).
- **FR-009:** Workflow rules + `context-session-economy.mdc`: session start → «вызови `mb-load session`»; purge prose multi-Read instructions.
- **FR-010:** (P2) MCP server tools `load_session`, `load_plan_section` — thin wrapper, zero duplicate logic.
- **FR-011:** Hub vs product cwd guard (same as mb-finish).
- **FR-012:** pytest matrix: IMPLEMENT, QA, BUGFIX, TASK, shape invalid, forbidden paths, plan_section.

### Success Criteria

| ID | Измеримый результат | Проверка | Type |
|----|---------------------|----------|------|
| SC-001 | Session start без prose «прочитай load_now» в workflow-implement | rg "load_now" workflow-implement → mb-load instruction | outcome |
| SC-002 | 0 false loads of full plan in IMPLEMENT matrix | pytest forbidden policy | outcome |
| SC-003 | Bundle fingerprint stable | pytest same cwd twice | outcome |
| SC-004 | session-start inject when EPIC_LOOP | pytest session_start | outcome |

### Assumptions

- `.cursor/rules/` остаётся отдельной загрузкой (role command chain); bundle = memory-bank artifacts only.
- Parent может передать subset bundle subagent в spawn prompt — out of scope v1 automation.
- Size cap prevents token blow-up; oversized file → `diagnostic_codes: ['file_too_large']` + path in skipped, not content.

### Clarifications

- Session: идея из чата 2026-09-02; taxonomy clear (symmetric to T-HUB-040).
- T-HUB-040 must ship schemas/render pattern first; mb_load imports shared types.

---

## AC

1. `loop/mb_load/` с pydantic models + `load_session` + forbidden policy.
2. CLI `mb-load session` (+ optional `plan-section` subcommand).
3. Integration: workflow rules session start → mb-load call.
4. session-start hook inject (EPIC_LOOP path).
5. pytest matrix: modes, shape, forbidden, fingerprint, plan_section.
6. (P2) MCP thin wrapper + parity test.
7. Sunset: rules не инструктируют LLM вручную парсить load_now как primary path.

### AC− (brownfield replace)

1. Нет второго resolver load_now кроме `extract_load_now` + mb_load orchestration.
2. Нет silent load full plan in IMPLEMENT — fail-closed or skip with diagnostic.
3. Misconfig (bad cwd, missing activeContext) → JSON error, не partial bundle.
4. Нет dual path «mb-load OR ручные Read» в rules после эпика.
5. Нет regex extract step_id из prose Handoff как machine input — frontmatter `step_id` или load_now paths.

---

## Техника / HOW

### Модули

| Path | Role |
|------|------|
| `loop/mb_load/schemas.py` | `LoadSessionRequest`, `LoadSessionResult`, `LoadedFile` (reuse `LoopHandoffMeta`) |
| `loop/mb_load/session.py` | `load_session`, forbidden policy, size cap |
| `loop/mb_load/plan_section.py` | `load_plan_section` — §N extract |
| `loop/mb_load/resolver.py` | implement yaml auto-resolve by step_id |
| `harness/hooks/epic_resolve.py` | `mb-load` subparser → dispatch |
| `harness/hooks/session-start.py` | optional bundle inject delegate |
| `loop/mb_load/mcp_server.py` | (P2) MCP tool registration |
| `.cursor/rules/shared/context-session-economy.mdc` | §3 session start → mb-load |
| `.cursor/rules/**/workflow-*.mdc` | START steps shortened |

### Data flow (ASCII)

```text
[Parent LLM / loop runner]
    | role command recognized
    v
[mb-load CLI] session [--plan-section N]
    | read activeContext.md
    v
[parse frontmatter] --> LoopHandoffMeta
    | extract_load_now + validate_active_context_shape
    v
[forbidden filter] --> skip done / full plan (mode-aware)
    | read files (size cap)
    v
[optional resolver] --> add implement yaml if IMPLEMENT gap
    | compute fingerprint (handoff + loaded paths + sha256s)
    v
JSON stdout {ok:true, meta, handoff, files[], fingerprint, ...}
    |
    v
[Agent uses bundle] — no manual Read for load_now set
```

### Failure matrix

| Component / link | Failure | Detection | User/system response | Test ID |
|------------------|---------|-----------|----------------------|---------|
| mb-load request | invalid pydantic | ValidationError | JSON `ok:false`, exit 2 | TM-001 |
| activeContext | missing / shape invalid | `validate_active_context_shape` | no files loaded, diagnostics | TM-002 |
| load_now path | file missing | stat fail | diagnostic `missing_artifact`, ok:false or partial per policy | TM-003 |
| forbidden path | plan in IMPLEMENT | policy engine | `forbidden_skipped`, not in files | TM-004 |
| file size | > cap | len(content) | skip content, diagnostic | TM-005 |
| wrong cwd | hub vs product | path guard | fail-closed JSON | TM-006 |
| plan_section | invalid N | parser | ok:false | TM-007 |
| MCP wrapper (P2) | schema drift | parity test | CI fail | TM-008 |

### Eng spine self-check

| Dimension | Score 1–5 | Gap / action |
|-----------|-----------|--------------|
| Data flow complete | 5 | — |
| Failure coverage | 4 | missing file policy explicit in s02 |
| Testability | 5 | matrix per mode |

---

## Replacement / sunset (brownfield)

### A. Code / modules

| Устаревает | Замена | Policy |
|------------|--------|--------|
| Prose-only session start in rules | `mb-load session` one-liner | delete in-epic multi-Read steps |
| Ad-hoc «read these 3 files» in context_loop prompts | mb-load bundle | shorten prompts |

### B. Entrypoints / deploy

| Устаревает | Замена | Policy |
|------------|--------|--------|
| Manual Read load_now chain | `epic_resolve.py mb-load session` | delete in-epic (rules) |

### C. Fallbacks / soft-fail

| Устаревает | Замена | Policy |
|------------|--------|--------|
| «если неясно — прочитай весь plan» | `load_plan_section N` | delete in-epic |
| silent skip shape errors at start | fail-closed mb-load | delete in-epic |

---

<a id="qa-consumes"></a>
## QA consumes (test plan)

### Scope under test

- Epic: T-HUB-045 — `loop/mb_load/*`, CLI, session-start delegate.
- Out of scope: MCP live Cursor integration (P2 smoke only); subagent auto-inject.

### Test matrix

| ID | Priority | Scenario | Command / fixture | Expected | Maps FR/AC |
|----|----------|----------|-------------------|----------|------------|
| TM-001 | P0 | load_session IMPLEMENT happy | pytest tmp_path | ok:true, sNN + index in files | FR-002, US-001 |
| TM-002 | P0 | shape invalid → fail | pytest bad activeContext | ok:false, diagnostics | FR-002, US-002 |
| TM-003 | P0 | forbidden full plan IMPLEMENT | pytest | plan skipped | FR-003, US-003 |
| TM-004 | P1 | QA mode bundle | pytest | qa shard loaded | FR-007, US-004 |
| TM-005 | P1 | plan_section extract | pytest --plan-section 3 | §3 only | FR-006, US-005 |
| TM-006 | P1 | fingerprint stable | pytest 2x | same hash | US-008 |
| TM-007 | P1 | session-start inject EPIC_LOOP | pytest | additionalContext has fingerprint | FR-008 |
| TM-008 | P1 | implement yaml auto-resolve | pytest load_now without implement | implement yaml added | FR-007 |
| TM-009 | P2 | MCP parity CLI | pytest | same JSON | FR-010 |

### Regression notes

- mb_load must not import mb_finish phase handlers (read-only shared schemas only).
- Token cap: default conservative; env override for hub tests.

---

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| CLARIFY / Product probe | L3: one of done | skip+reason | §Product probe table (6 rows) |
| Eng review spine | L2+ | done | §Техника / HOW + failure matrix |
| §0.11 counterparts (draft) | if external refs | done | epic_resolve, session-start, extract_load_now, mb_finish schemas — in-repo |
| CREATIVE | if flagged | n/a | — |
| qa_consumes draft | L2+ | done | §QA consumes ≥9 TM |
| Plan review batch | L2+ | done | §Plan review batch log |

---

## Plan review batch log

| Phase | Auto-resolved | Deferred (owner/next) | Taste / CRITICAL surfaced |
|-------|---------------|-------------------------|---------------------------|
| Product | Wedge = load_session first; plan_section P1; MCP P2 | session-start full content vs summary — cap in s06 | — |
| Eng | `loop/mb_load` sibling to `mb_finish`; shared schemas import; CLI before MCP | Episode package (031) can record load fingerprint later | — |

---

## Где ещё применимо (beyond START)

| Surface | Сейчас | С tool API |
|---------|--------|------------|
| **Episode packages (T-HUB-031)** | snapshot reads files ad-hoc | manifest includes `session_load_fingerprint` |
| **analyze-convergence (T-HUB-032)** | drift reports | detect «session without mb-load» as finding |
| **Doctor / incidents** | shape repair post-factum | recommend mb-load before work |
| **Subagent spawn** | parent copies prose | parent passes `files[]` subset from bundle |
| **mb-finish (T-HUB-040)** | FINISH mutation | symmetric START query; same fingerprint family |

---

## До DECOMPOSE (черновик нарезки)

| sNN | Slice |
|-----|-------|
| s01 | `loop/mb_load/schemas.py` + `session.py` core + shape/forbidden tests |
| s02 | CLI `mb-load session` + cwd guard + JSON stdout |
| s03 | `resolver.py` implement yaml auto-resolve + mode matrix tests |
| s04 | `load_plan_section` subcommand + §N parser |
| s05 | `session-start.py` inject delegate (EPIC_LOOP) |
| s06 | workflow rules + context-session-economy purge prose START |
| s07 | (P2) MCP thin wrapper + parity tests |
| s08 | legacy purge: dual manual Read instructions in rules/context_loop |

**Advisory floor:** 8 steps · **timebox_days:** 4 · **cut_list:** `['MCP server', 'plan_section polish', 'episode package wire']`

---

## Appetite

| Поле | Значение |
|------|----------|
| `timebox_days` | 4 |
| `cut_list` | MCP P2, episode package fingerprint wire, extra modes if 040 unstable |

---

## Следующий режим

→ **BACK DECOMPOSE** T-HUB-045 (после T-HUB-040 IMPLEMENT + QA в canon)
