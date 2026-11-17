# [T-HUB-109 | runtime-hub] PLAN

**Дата:** 2026-11-06  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** active  
**Clarify:** [clarify-20261106-runtime-hub.md](../../clarify/clarify-20261106-runtime-hub.md)  
**Prompt:** [md/prompt.md](prompt.md)  
**Roadmap:** `memory-bank/back/roadmap/queue.yaml` · batch `runtime-hub-20261106` · `kind: feature`  
**Deps:** — (standalone; loop wire deferred)  
**Skills:** writing-plans · python-testing-patterns · architecture-patterns · grill-me (Phase 0)  
**Источник:** chat BACK PLAN Runtime Hub / multi-runtime orchestrator in dev-hub

---

## Контекст

- **req:** Одна точка управления профилями официальных agent runtimes (Codex / Claude / Antigravity) с изоляцией аккаунтов и низким риском бана (spawn native CLI, не OAuth spoof).
- **status quo:** `EPIC_RUNTIME=claude|codex` в loop; Codex часто через `codex/bin/codex-omniroute.sh`; ручное переключение аккаунтов; нет единого profile switcher.
- **gap:** Нет `runtime_hub` модуля, CLI `hub-runtime`, isolated profile homes, policy «native Codex default».
- **refs:** `LOOP-RUNTIMES.md` · `codex/bin/codex-omniroute.sh` · `loop/` CodexRuntime · clarify Round 1–2
- **Не в scope этого эпика:** UI/Cursor extension (см. intent T-HUB-110); loop SoT cutover; agy HTTP-bridge; удаление OmniRoute файлов; product neftegaz; отдельная Electron/Tauri IDE.
- **North star (зафиксировано):** после CLI-ядра — **Cursor extension** для parallel projects (окно = проект + чат + profile). Intent: `memory-bank/back/intent/intent-20261106-runtime-hub-cursor-extension.md`.

**CREATIVE need:** нет (CLI surface + Protocol adapters зафиксированы clarify).

**Route recommendation:** L3 → next **`BACK DECOMPOSE`**, затем `BACK IMPLEMENT sNN`.

---

## Context consumed

| Path | Что вошло в axiom / Deps / FR |
|------|-------------------------------|
| `memory-bank/techContext.md` | Hub Python tooling; `.venv`/pytest; Claude/Codex CLI как runtimes; нет ORM |
| `memory-bank/systemPatterns.md` | SP-H01 hub vs product; SP-H04 fail-closed |
| `memory-bank/projectbrief.md` | Scope = hub tooling (`bin/`, `loop/`); не product app |
| `memory-bank/architecture/index.md` | Hub = rules/hooks/loop; frontend absent; file runtime |
| `memory-bank/product/` | n/a — каталога нет |

---

## Clarifications

- Session: 2026-11-06 · [clarify-20261106-runtime-hub.md](../../clarify/clarify-20261106-runtime-hub.md)
- Round 1: CLI-only · Codex+Claude+agy · isolated dirs · loop later
- Round 2: OmniRoute explicit · agy spawn-only · `~/.dev-hub/runtime-hub/` · fail-closed
- Deferred from 109: loop opt-in; agy bridge; OmniRoute file purge; Tauri/Electron IDE
- **Committed next UI:** Cursor extension (T-HUB-110 candidate) — intent-20261106-runtime-hub-cursor-extension.md

---

## PLAN review passes

| Pass | Status | Notes |
|------|--------|-------|
| Product | done | Operator hub; wedge CLI; anti-scope UI/loop/spoof |
| Design | skip | No UI in MVP |
| DX | done | CLI verbs use/status/run/doctor/list; example profiles template in repo |
| Eng | done | Protocol adapters; fail-closed; OmniRoute policy; tests |

### Ownership matrix

| Area | Owner | Contract | Rollback | Independent check |
|------|-------|----------|----------|-------------------|
| Profile SoT + activate | BACK | profiles.yaml schema + active pointer | delete active file / `use` other | unit: activate writes pointer + env map |
| Codex/Claude/agy adapters | BACK | RuntimeAdapter Protocol | disable profile | unit: fake binary spawn argv/env |
| OmniRoute policy | BACK | default native; named profile only | revert profile yaml | test: default profile executable ≠ omniroute wrapper |
| Docs / Kind I | BACK | README + example yaml | revert docs | doctor lists example path |
| Loop wire | deferred | n/a this epic | — | — |
| UI | deferred | n/a | — | — |

---

## Delivery closure

| Capability / outcome | Classification | Production entrypoint | Success / failure enforcement | Independent outcome test | Foundation / follow-up |
|---|---|---|---|---|---|
| Profile registry + activate | `vertical_slice` | `bin/hub-runtime use\|list\|status` | unknown profile → exit≠0; no create silent global home | Given profiles.yaml; When use X; Then active=X + env map for X.home | n/a |
| Spawn Codex/Claude/agy | `vertical_slice` | `bin/hub-runtime run [-- args]` | missing binary → exit≠0 + reason | Fake PATH binary; assert argv + CODEX_HOME/CLAUDE_*/agy home | n/a |
| Fail-closed conflicts | `vertical_slice` | `use` without `--force` | active dirty/conflict → exit≠0 | Active set; use other without force → error | n/a |
| OmniRoute non-default | `vertical_slice` | Codex adapter resolve_executable | default profile → real `codex`; omniroute only if profile.runtime_opts say so | assert resolve path | sunset default omniroute for Hub users |
| Example + doctor | `vertical_slice` | `hub-runtime doctor` + `runtime_hub/profiles.example.yaml` | doctor reports missing bins/homes | doctor exit 0/≠0 by fixture | Kind I |

---

## Technology axiom (replace-not-wrap)

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Module home | Python package `runtime_hub/` + entry `bin/hub-runtime` | логика только в bash one-off без package |
| Profile SoT | `RUNTIME_HUB_HOME` default `~/.dev-hub/runtime-hub/` · `profiles.yaml` · `active` · `profiles/<id>/` | tracked secrets in git; SoT в `loop/` state |
| Runtime boundary | Protocol `RuntimeAdapter` (`name`, `resolve_executable`, `build_env`, `build_argv`) + registry | `if runtime==` размазан по CLI без registry |
| Codex default egress | native `codex` on PATH (or profile.executable); OmniRoute wrapper **только** explicit profile field | Hub default → `codex-omniroute.sh` |
| Auth model | spawn official CLI; login state внутри profile home | extract OAuth → HTTP client / spoof headers |
| agy MVP | spawn-only + env/home isolation + model flag passthrough | OpenAI-compatible bridge в этом эпике |
| Errors | fail-closed non-zero + structured reason | warn+fallback на `~/.codex` / `~/.claude` |
| Loop | out of MVP | `EPIC_RUNTIME` читает Hub как SoT в этом эпике |

---

## Продуктовая спека (WHAT)

Оператор описывает именованные profiles (runtime, model, home_dir, optional executable). CLI активирует профиль и запускает соответствующий официальный агент с изолированным state. Несколько аккаунтов = несколько homes. OmniRoute остаётся доступен как отдельный Codex-profile, но не default.

### Product probe

| # | Question | Answer | Impact |
|---|----------|--------|--------|
| 1 | Reframe | Orchestrator of official runtimes, not LLM proxy | No bridge MVP |
| 2 | Narrowest wedge | CLI + 3 spawn adapters + fail-closed | Single epic L3 |
| 3 | Pre-mortem | Silent OmniRoute default + shared `~/.codex` | Q5=B Q8=A HARD |
| 4 | Distribution | example yaml in repo; homes outside repo | Kind I |
| 5 | Appetite | ~2–3 дня; cut = UI, loop, agy bridge | cut_list |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как оператор, я хочу `list`/`use` профилей, чтобы переключать аккаунт/runtime одной командой. | P0 | use → status показывает profile id + runtime |
| US-002 | Как оператор, я хочу `run` под активным профилем Codex native. | P0 | env содержит profile CODEX_HOME; executable ≠ omniroute |
| US-003 | Как оператор, я хочу отдельный profile Claude с своим config dir. | P0 | build_env выставляет Claude home/config; не Codices |
| US-004 | Как оператор, я хочу profile Antigravity spawn `agy` с isolated state. | P0 | argv[0]=agy (или configured); no localhost bridge started |
| US-005 | Как оператор, я хочу явный Codex-OmniRoute profile, не default. | P0 | only that profile resolves to omniroute script |
| US-006 | Как оператор при ошибке, я хочу non-zero и причину, не тихий fallback. | P0 | missing bin / unknown id / conflict → ≠0 + stderr reason |

#### Acceptance Scenarios

- **US-001 Given** profiles.yaml with `gpt-work` **When** `hub-runtime use gpt-work` **Then** active file = gpt-work; `status` OK
- **US-002 Given** active Codex native profile **When** `run -- --version` (or dry-run) **Then** env CODEX_HOME under runtime-hub profiles; executable basename `codex`
- **US-003 Given** Claude profile **When** build_env **Then** Claude-specific home set; CODEX_HOME unset or not required
- **US-004 Given** agy profile **When** run dry-run **Then** no process listens as OpenAI proxy; spawn argv for agy only
- **US-005 Given** profile `codex-omniroute` with executable wrapper **When** resolve **Then** path ends with `codex-omniroute.sh`; default profile does not
- **US-006 Given** unknown id **When** use **Then** exit≠0; no active mutation

### Functional Requirements (FR-###)

- **FR-001:** `RUNTIME_HUB_HOME` (default `~/.dev-hub/runtime-hub`) содержит `profiles.yaml`, `active`, `profiles/<id>/`.
- **FR-002:** Schema profile: `id`, `runtime ∈ {codex,claude,agy}`, `model` (optional), `home` (relative under profiles/ or absolute), `executable` (optional), `env` map (optional), `notes` (optional).
- **FR-003:** CLI: `list` · `use <id> [--force]` · `status` · `run [--] [args…]` · `doctor`.
- **FR-004:** `use` пишет active pointer атомарно; без `--force` отказывает при политике конфликта (active exists and different + optional lock flag) — минимум: отказ перезаписать если `HUB_RUNTIME_REQUIRE_FORCE=1` или если doctor marks dirty; канон MVP: отказ если active уже другой id без `--force`.
- **FR-005:** Registry RuntimeAdapter для `codex`, `claude`, `agy`.
- **FR-006:** Codex adapter: default executable `codex` on PATH; sets `CODEX_HOME` to profile home; does not prepend omniroute unless `executable` points to wrapper.
- **FR-007:** Claude adapter: sets documented config/home env for official Claude Code CLI (investigate as-built var names in IMPLEMENT; fail-closed if undocumented — store in adapter const). 
- **FR-008:** agy adapter: resolve `agy` or `executable`; set isolated home/state env if officially supported else chdir/HOME override documented in adapter; **no** HTTP server.
- **FR-009:** `run` requires active profile; merges adapter env; exec/spawn foreground; propagate exit code.
- **FR-010:** `doctor`: checks binaries, homes exist/writable, active validity, warns if default would have been omniroute (informational).
- **FR-011:** Ship `runtime_hub/profiles.example.yaml` + short `runtime_hub/README.md` (commands + anti-spoof policy).
- **FR-012:** Unit tests with fake binaries via tmp_path; no network.
- **FR-013:** Secrets: never write API keys into repo; optional `env_file` path outside repo referenced by profile (optional MVP stretch — if not shipped, document env-only).

### Non-goals / cut_list

- Cursor extension / Tauri UI  
- `loop.py` reads Hub active as SoT  
- agy OpenAI bridge  
- Delete `codex/bin/codex-omniroute.sh`  
- Multi-machine sync of profiles  

### Appetite

- Timebox: 2–3 engineer-days  
- Outline sNN hint (DECOMPOSE finalizes; L3 cap 3):  
  - s01 — schema + store + CLI use/list/status + fail-closed  
  - s02 — adapters Codex/Claude/agy + run + doctor  
  - s03 — OmniRoute explicit profile policy + example/README + tests polish  

---

## Boundary / negative cases

| ID | Case | Expected |
|----|------|----------|
| BN-001 | `use` unknown profile id | exit≠0; active unchanged; reason `unknown_profile` |
| BN-002 | `run` without active | exit≠0; reason `no_active_profile` |
| BN-003 | `run` when binary missing | exit≠0; reason `binary_not_found`; no fallback global home |
| BN-004 | `use` other profile without `--force` while active set | exit≠0; reason `active_conflict` |
| BN-005 | Codex default profile must not resolve to `codex-omniroute.sh` | assert in tests |
| BN-006 | agy profile must not start HTTP bridge | no server thread/process in adapter |
| BN-007 | profiles.yaml invalid YAML / missing required field | exit≠0 on any command; loud error |

---

## #qa-consumes

| TM | Maps | Behavior check |
|----|------|----------------|
| TM-001 | BN-001, US-006 | unknown profile → ≠0 |
| TM-002 | BN-002, BN-003 | run fail-closed missing active/bin |
| TM-003 | BN-004 | use conflict without force |
| TM-004 | BN-005, US-005 | native vs omniroute executable resolve |
| TM-005 | BN-006, US-004 | agy spawn-only |
| TM-006 | FR-001–003 | list/use/status roundtrip on tmp RUNTIME_HUB_HOME |

---

## HOW (sketch)

```text
bin/hub-runtime → runtime_hub.cli
                     ├─ store.py (load profiles, active)
                     ├─ adapters/
                     │    ├─ base.py Protocol
                     │    ├─ codex.py
                     │    ├─ claude.py
                     │    └─ agy.py
                     └─ doctor.py
```

Tests: `runtime_hub/tests/` or `tests/runtime_hub/` + `bin/pytest`.

---

## Replacement / sunset

| Axis | Inventory |
|------|-----------|
| **A — keep** | `codex/bin/codex-omniroute.sh` files remain for explicit profiles / legacy loop paths until follow-up |
| **B — entrypoints** | Hub Codex **default profile** must not use omniroute wrapper; document in README |
| **C — fallback** | FORBIDDEN: Hub silently falls back to OmniRoute or `~/.codex` when profile home missing |
| **I — independent test** | TM-004: default profile executable ≠ omniroute script path |

Greenfield module + brownfield policy on OmniRoute default — not full delete.

---

## Eng review spine

- **Architecture:** engine-first package; CLI thin; adapters registry (PhotoCraft-like command surface lite).  
- **Patterns:** SP-H01 / SP-H04; Protocol+registry as T-HUB-108 style.  
- **Code surface:** new `runtime_hub/`, `bin/hub-runtime`; touch OmniRoute only via docs/tests policy (no mandatory loop edit).  
- **Risks:** Claude/agy env var names drift — pin in adapter + doctor; PATH shadowing — doctor warns.

---

## Review readiness

| Item | Status |
|------|--------|
| Product pass | done |
| Design pass | skip — no UI |
| DX pass | done |
| Eng pass | done |
| Boundary / negative cases | done (≥3 BN) |
| QA consumes ≥3 TM | done |
| prompt.md ## Epic | done |
| CRITICAL open | none |
| Context consumed | done |

---

## Handoff (PLAN)

- Artifacts: clarify done · queue row · `plan/T-HUB-109-runtime-hub/md/plan.md` · `md/prompt.md`
- **Next:** `BACK DECOMPOSE` T-HUB-109-runtime-hub
- Follow-up epics (not this PLAN):
  1. **T-HUB-110-runtime-hub-cursor-extension** (committed direction) — workspace-scoped profile picker в Cursor; parallel windows = parallel projects; см. `memory-bank/back/intent/intent-20261106-runtime-hub-cursor-extension.md`
  2. loop opt-in wire
  3. agy HTTP-bridge (optional)
  4. OmniRoute default purge in loop tests
- **FORBIDDEN drift:** не подменять Cursor-направление отдельным Electron/Tauri multi-chat IDE без явного revisit clarify
