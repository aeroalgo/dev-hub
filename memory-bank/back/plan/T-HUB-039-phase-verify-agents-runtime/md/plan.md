# [T-HUB-039 | phase-verify-agents-runtime] PLAN

**Дата:** 2026-08-31  
**Режим:** BACK PLAN  
**Уровень:** L3–L4  
**Статус:** active  
**Clarify:** Phase 0 skipped — taxonomy clear (dilution gap T-HUB-029 FR-020–024 + T-HUB-028 WHAT; behavior-first HARD уже в rules)  
**Deps:** **hard** T-HUB-029 (phase_registry + `get_verify_agent` уже есть). **Soft:** T-HUB-023 (JSON fence `loop-gate-verdict/v1` / extract path). DSH presets: T-HUB-007/008 as-built.

**Skills:** writing-plans · architecture-patterns · python-testing-patterns · diagnosing-bugs

**Supersedes leftover:** runtime surfaces из [T-HUB-028](plan-T-HUB-028-phase-verify-agents.md) и FR-020–025 [T-HUB-029](plan-T-HUB-029-epic-phase-transition-engine.md), которые остались metadata-only (registry strings без agent files / enforce).

→ [T-HUB-039-phase-verify-agents-runtime/md/decompose-index.md](T-HUB-039-phase-verify-agents-runtime/md/decompose-index.md) — **после DECOMPOSE**

---

## Контекст

- **req:** Phase-specific verify subagents **реально работают** на FINISH: файлы агентов на диске, spawn normalize+contract, stop-gate/pretool enforce по `get_verify_agent(phase)`, DSH presets, spawn-hard/workflow таблицы — не «строка `verify_agent:` в yaml».
- **gap (as-built after T-HUB-029):**
  - `phase_registry.yaml` имеет `verify_agent` rows; `get_verify_agent()` + `AGENT_ALIASES` есть.
  - **Нет** `.claude/agents/verify-{implement,bugfix,decompose,qa}.md`.
  - Живут monolithic `verify.md` / `reviewer.md`; DSH только `verify.prompt.md` / `reviewer.prompt.md`.
  - `agent-pretool.py` читает `expected_verify_agent` и **не использует** (dead assign).
  - `stop-gate` / spawn state: `need_verify` / `need_reviewer`, не per-phase.
  - `_lib.ALIAS` знает только `explore→explorer`; `AGENT_ALIASES` не wired в `normalize_type`.
- **refs:** plan-T-HUB-028; plan-T-HUB-029 FR-020–025; `.claude/agents/{verify,reviewer,analyze-verify,explorer}.md`; `.claude/hooks/{_lib,stop-gate,agent-pretool,subagent-stop,spawn_validate,user-prompt,agent_registry}.py`; `loop/schemas/phase_registry.yaml`; `loop/epic_transition.py`; `dsh/presets/`; `@.cursor/rules/shared/workflow-behavior-first.mdc`.

### Зафиксированные решения

| Тема | Решение |
|------|---------|
| Scope | **Runtime wire only** — registry уже от 029; этот эпик = agent files + enforce + presets + docs + tests |
| Naming | `verify-<phase>` kebab; aliases `verify`→`verify-implement`, `reviewer`→`verify-qa` ≥1 release |
| IMPLEMENT family | `verify-implement` — IMPLEMENT · REFACTOR · TASK |
| BUGFIX | отдельный `verify-bugfix` |
| DECOMPOSE | `verify-decompose` semantic; CLI `validate-decompose-tree` остаётся fail-closed |
| QA | `verify-qa` (ex reviewer); BLOCKED verdict |
| ANALYZE | `analyze-verify` wire optional (`PROJECT_LOOP_ANALYZE_VERIFY`) |
| Behavior-first | каждый FR noun ∈ produces (agent md / preset / enforce branch); surrogate unit alone = FAIL DECOMPOSE |
| CREATIVE need | нет |

---

## Technology axiom (replace-not-wrap)

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Gate verdict | JSON fence `loop-gate-verdict/v1` (T-HUB-023 path) | prose `VERDICT:` как SoT |
| Phase→agent | `get_verify_agent(phase)` + discoverable agent file | dead assign / registry string без файла |
| Spawn alias | `normalize_type` → `AGENT_ALIASES` | dual undocumented names без alias |
| Per-phase need_* | state keys from registry | только legacy `need_verify` без mirror |

---

## Продуктовая спека (WHAT)

### Product probe (office-hours lite)

| # | Question | Answer / Probe | Decision / Impact on PLAN |
|---|----------|----------------|---------------------------|
| 1 | **Reframe:** Какую реальную проблему решаем? | Operator думает что phase verify есть; FINISH всё ещё на monolithic `@verify`/`@reviewer`; агентов нет на диске. | Эпик = runtime surfaces, не ещё один registry refactor. |
| 2 | **Narrowest wedge:** | Файлы `verify-implement` + alias + pretool **uses** `get_verify_agent` + stop-gate для IMPLEMENT. | s01–s02 must ship behavior smoke; не «все docs сначала». |
| 3 | **Pre-mortem:** | Снова dilution: step «wire aliases» без `.md` файлов; AUDIT satisfied на unit. | Behavior-first HARD + TM на Path.exists + enforce. |
| 4 | **Adoption:** | spawn-hard + finish-block + lean workflows меняют `@verify` → `@verify-implement` (alias keeps old). | Docs in-epic; in-flight epics keep alias. |
| 5 | **Leverage:** | Reuse 028 contracts + 029 registry; не rewrite transition engine. | Out of scope: epic_transition API redesign. |
| 6 | **Appetite:** | L3–L4, ~6–8 дней, ≤10 sNN + purge. | Cut: verify-audit / verify-plan defer. |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как parent IMPLEMENT, я хочу spawn `verify-implement` (или legacy `verify`), чтобы FINISH шёл только после PASS этого агента. | P0 | Файл `.claude/agents/verify-implement.md` exists; `discover_registry` contains id; spawn `verify` normalizes; stop-gate blocks FINISH без PASS |
| US-002 | Как parent BUGFIX, я хочу `verify-bugfix` с bugfix artifact в ALLOW. | P0 | Agent file exists; spawn без bugfix path → DENY/FAIL |
| US-003 | Как parent DECOMPOSE, я хочу `verify-decompose` после schema CLI, чтобы semantic coverage ловилась до IMPLEMENT. | P0 | Agent file exists; stop-gate: schema CLI **and** verify-decompose when enabled; FAIL на coverage gap |
| US-004 | Как BACK QA, я хочу `verify-qa` (ex reviewer) с BLOCKED. | P0 | Agent file exists; alias `reviewer`; BLOCKED → FINISH allowed with BUGFIX Handoff |
| US-005 | Как operator после ANALYZE fix, я хочу optional `analyze-verify`. | P1 | Env on → need flag; PASS closes; env off → no hard block |
| US-006 | Как DSH/loop operator, я хочу presets для всех verify-* на диске. | P0 | `dsh/presets/verify-*.prompt.md` exist; epic-gate map resolves ids |
| US-007 | Как auditor, я хочу: нет dead assign `get_verify_agent`; parity matrix в docs. | P0 | `rg` pretool uses expected agent; README + architecture row |

#### Acceptance Scenarios — US-001

- **Given:** implement step evidence ready, agent file on disk  
- **When:** parent spawn `subagent_type=verify`  
- **Then:** normalize → `verify-implement`; packed contract; PASS → `finalize-step` allowed; без PASS stop-gate DENY FINISH

#### Acceptance Scenarios — US-003

- **Given:** `validate-decompose-tree` exit 0, Outcome map hole  
- **When:** FINISH DECOMPOSE with packed `@verify-decompose`  
- **Then:** gate FAIL / GAPS; stop-gate blocks until PASS (when gate enabled)

#### Acceptance Scenarios — US-004

- **Given:** QA suite green, packed verify-qa  
- **When:** JSON verdict BLOCKED  
- **Then:** stop-gate allows FINISH + Handoff BUGFIX; не protocol FAIL

### Functional Requirements (FR-###)

#### Agent files (runtime nouns)

- **FR-001:** Create `.claude/agents/verify-implement.md` (content from current `verify.md`, `name: verify-implement`); `verify.md` → thin alias/redirect stub (≥1 release).
- **FR-002:** Create `.claude/agents/verify-bugfix.md` — sections: AC+ · AC− · §0.11 · VERIFY · BUGFIX ARTIFACT · ALLOW; pytest allowed.
- **FR-003:** Create `.claude/agents/verify-decompose.md` — COVERAGE · PLAN EXCERPT · AC+ · AC− · ALLOW; **FORBIDDEN** pytest/product code paths; verdict PASS/FAIL (GAPS→FAIL for stop-gate).
- **FR-004:** Create `.claude/agents/verify-qa.md` from `reviewer.md`; BLOCKED; `reviewer.md` → alias stub.
- **FR-005:** Shared fragment `.claude/agents/_fragments/gate-ac-matrix.md` (DRY AC+/AC−/§0.11); included by implement/bugfix/qa.
- **FR-006:** Align `.claude/agents/analyze-verify.md` + wire into section contracts / presets.

#### Hooks enforce (use registry, not dead code)

- **FR-007:** `_lib.normalize_type` / `ALIAS` merges `AGENT_ALIASES` (`verify`→`verify-implement`, `reviewer`→`verify-qa`, `explore`→`explorer`).
- **FR-008:** `gates_from_phase` / spawn state: per-phase `need_verify_implement|bugfix|decompose|qa` (+ optional `need_analyze_verify`); mirror legacy `need_verify`/`need_reviewer` during alias period.
- **FR-009:** `agent-pretool.py` — **uses** `get_verify_agent(phase)`: wrong type DENY; double PASS DENY; step/bugfix path checks; no dead assign.
- **FR-010:** `stop-gate.py` — FINISH blocks by registry verify_agent + need_* ; DECOMPOSE: CLI schema **AND** verify-decompose when enabled; QA BLOCKED allowed.
- **FR-011:** `subagent-stop.py` + `spawn_validate.py` — per-agent verdict fields; backward compat `verify_verdict` / `reviewer_verdict`.
- **FR-012:** `user-prompt.py` / finish inject — phase→correct need_* ; DECOMPOSE does not blanket-disable all verify.

#### DSH + docs + workflow

- **FR-013:** DSH presets on disk: `verify-implement`, `verify-bugfix`, `verify-decompose`, `verify-qa`, `analyze-verify`; epic-gate + profiles map.
- **FR-014:** `spawn-hard.md` + `_lean/{implement,decompose,qa,bugfix}.mdc` + `finish-block.mdc` + `context_loop` finish strings — agent×phase table; parent packs correct type.
- **FR-015:** Docs: `loop/README.md` / `WORKFLOW.md` §Phase verify agents; `memory-bank/architecture/services.md` S-AGENTS; migration note aliases.

#### Tests + extract

- **FR-016:** `loop/tests/test_phase_verify_gates.py` — matrix phase→required agent file exists + normalize + stop-gate need_*.
- **FR-017:** Extend `test_agent_hooks.py` — pretool uses get_verify_agent; alias spawn; no dead assign regression.
- **FR-018:** Verdict extract / T-HUB-023 path recognizes all verify-* + aliases.
- **FR-019:** Purge: remove dead `expected_verify_agent` unused pattern; sunset monolithic canonical names after alias docs; final `*-legacy-fallback-purge` sNN.

### Success Criteria (SC-###)

| ID | Результат | Проверка | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | All four verify-* agent files + analyze-verify discoverable | `Path.is_file` + registry discover test | outcome |
| SC-002 | Legacy `@verify` / `@reviewer` spawn works via alias | hook normalize + pretool allow | outcome |
| SC-003 | IMPLEMENT FINISH blocked without verify-implement PASS | stop-gate test | outcome |
| SC-004 | DECOMPOSE: CLI + verify-decompose when enabled | stop-gate test | outcome |
| SC-005 | QA BLOCKED not protocol FAIL | subagent-stop + stop-gate | outcome |
| SC-006 | DSH presets exist for all verify-* | epic-gate / file exists tests | outcome |
| SC-007 | Zero dead assign of get_verify_agent in pretool | rg + unit | outcome |

### Assumptions

- T-HUB-029 registry `verify_agent` rows remain SoT for phase→name; this epic does not redesign Transition Engine.
- Products symlink `.claude/agents` via hub-link.
- Feature flag optional: `PROJECT_GATE_PHASE_VERIFY=0` restores legacy single-flag debug (default on when agents present).

### Clarifications

- Session: 2026-08-31 — user: BACK PLAN after T-HUB-034; base 029 leftover verify agents; behavior-first rules already landed.
- No CRITICAL markers.

### [НУЖНО УТОЧНИТЬ]

- n/a CRITICAL. **Defer:** `verify-audit`, `verify-plan` — out_of_scope (optional future epic).

---

## AC

### AC+

1. Files exist: `verify-implement.md`, `verify-bugfix.md`, `verify-decompose.md`, `verify-qa.md`, fragment + analyze-verify wired.
2. Aliases work ≥1 release; `normalize_type` uses AGENT_ALIASES.
3. `agent-pretool` **enforces** `get_verify_agent(phase)` (DENY mismatch); no unused assign.
4. `stop-gate` enforces per-phase need_* from registry; DECOMPOSE CLI + semantic gate; QA BLOCKED OK.
5. DSH presets on disk + mapping green.
6. spawn-hard + finish-block + lean workflows updated.
7. Tests green: `.venv/bin/pytest loop/tests/test_phase_verify_gates.py loop/tests/test_agent_hooks.py -q` (+ dsh epic-gate gaps if present).
8. Docs + architecture S-AGENTS updated.
9. Purge step: legacy canonical-only paths / dead code removed or shim-documented.

### AC−

1. Не удалять `validate-decompose-tree` / `verify-decompose-creative`.
2. Не merge verify-qa и verify-implement в один prompt file.
3. Не ломать T-HUB-018 tier1 pytest orchestration.
4. Не требовать verify subagent для PLAN/VAN/CREATIVE/REFLECT.
5. Не default-hard analyze-verify без env flag.
6. Не port hooks to TypeScript.
7. Не rename `explorer` into verify family.
8. Не «закрывать» FR только registry string / unit lookup (behavior-first).
9. Не rewrite `epic_transition` API (029 SoT).

---

## Техника / архитектура (HOW)

### Agent matrix (target)

| Phase | subagent_type | Mandatory (loop) | Runs pytest | Verdicts | CLI co-gate |
|-------|---------------|------------------|-------------|----------|-------------|
| DECOMPOSE | `verify-decompose` | yes (when enabled) | no | PASS/FAIL | `validate-decompose-tree` |
| IMPLEMENT / REFACTOR / TASK | `verify-implement` | yes | yes | PASS/FAIL | `validate-step` |
| BUGFIX | `verify-bugfix` | yes | yes | PASS/FAIL | bugfix md |
| QA | `verify-qa` | yes | no | PASS/BLOCKED/FAIL | parent suite |
| ANALYZE fix | `analyze-verify` | optional | no | PASS/FAIL | — |
| Search | `explorer` | conditional | no | none | graphify |

### Prompt sections (packed)

| Section | implement | bugfix | decompose | qa | analyze-verify |
|---------|-----------|---------|-----------|-----|----------------|
| AC+ | ✓ | ✓ | ✓ | ✓ | — |
| AC− | ✓ | ✓ | ✓ | ✓ | — |
| §0.11 | ✓ | ✓ | optional | ✓ | — |
| VERIFY | ✓ | ✓ | — | — | — |
| Suite results | — | — | — | ✓ | — |
| COVERAGE | — | — | ✓ | — | ✓ |
| PLAN EXCERPT | — | — | ✓ | — | — |
| FINDINGS | — | — | — | — | ✓ |
| BUGFIX ARTIFACT | — | ✓ | — | — | — |
| ALLOW READ | ≤10 | ≤10 | ≤10 | ≤10 | ≤10 |

### Data flow (ASCII)

```text
[Parent FINISH]
  -> [phase_registry.verify_agent]
  -> [get_verify_agent(phase)]
  -> [normalize_type / AGENT_ALIASES]
  -> [agent-pretool: file discover + packed sections + DENY mismatch]
  -> [Subagent verify-* : JSON fence verdict]
  -> [subagent-stop: need_*_done + verdict]
  -> [stop-gate: allow finalize / block]
         sync; fail-closed on missing agent file or FAIL verdict
```

### Failure matrix

| Component / link | Failure | Detection | User/system response | Test ID |
|------------------|---------|-----------|----------------------|---------|
| Agent file missing | discover miss | pretool / test_phase_verify | DENY spawn; FAIL closed | TM-001 |
| Wrong subagent_type vs phase | mismatch get_verify_agent | pretool | DENY + reason | TM-002 |
| Legacy alias | spawn `verify` | normalize_type | maps to verify-implement | TM-003 |
| Double PASS | re-spawn after PASS | pretool | DENY | TM-004 |
| DECOMPOSE schema red | validate-decompose-tree ≠0 | stop-gate | block FINISH | TM-005 |
| DECOMPOSE semantic FAIL | verify-decompose FAIL | stop-gate | block until PASS | TM-006 |
| QA BLOCKED | verdict BLOCKED | stop-gate | allow FINISH + BUGFIX handoff | TM-007 |
| analyze-verify off | env unset | gates_from_phase | no hard need_* | TM-008 |
| DSH preset missing | file absent | epic-gate / pytest | fail-closed map | TM-009 |
| Dead assign regression | unused get_verify_agent | rg + unit | FAIL purge | TM-010 |

### Eng spine self-check

| Dimension | Score 1–5 | Gap / action |
|-----------|-----------|--------------|
| Data flow complete | 5 | registry → spawn → verdict → stop |
| Failure coverage | 5 | matrix ≥10 rows |
| Testability | 5 | phase_verify_gates + hooks |

### Компоненты (touch list)

| Path | Action |
|------|--------|
| `.claude/agents/verify-implement.md` | Create |
| `.claude/agents/verify-bugfix.md` | Create |
| `.claude/agents/verify-decompose.md` | Create |
| `.claude/agents/verify-qa.md` | Create |
| `.claude/agents/verify.md` | Alias stub |
| `.claude/agents/reviewer.md` | Alias stub |
| `.claude/agents/_fragments/gate-ac-matrix.md` | Create |
| `.claude/agents/analyze-verify.md` | Align + wire |
| `.claude/hooks/_lib.py` | ALIAS merge; CONTRACTS; _SECTION_PATTERNS |
| `.claude/hooks/agent-pretool.py` | **use** get_verify_agent |
| `.claude/hooks/stop-gate.py` | per-phase need_* |
| `.claude/hooks/subagent-stop.py` | multi verdict |
| `.claude/hooks/spawn_validate.py` | all verify-* |
| `.claude/hooks/user-prompt.py` | phase→need_* |
| `.claude/instructions/spawn-hard.md` | matrix |
| `.cursor/rules/shared/finish-block.mdc` | naming |
| `.cursor/rules/**/_lean/{implement,decompose,qa,bugfix}.mdc` | spawn types |
| `dsh/presets/verify-*.prompt.md` | Create |
| `dsh/plugins/epic-gate/**` | Map |
| `loop/context_loop.py` | finish inject |
| `loop/tests/test_phase_verify_gates.py` | Create |
| `loop/tests/test_agent_hooks.py` | Extend |
| `loop/README.md` · `WORKFLOW.md` · architecture/services.md | Docs |

### Integration §0.11

- Each agent md ↔ spawn-hard ↔ subagent-start preset ↔ DSH preset path.
- `get_verify_agent` return value ∈ discover_registry ids.
- `context_loop` finish strings match stop-gate flags.
- T-HUB-023 extract list includes verify-*.

---

## Replacement / sunset (brownfield)

### A. Code / modules

| Устаревает (path / symbol) | Замена | Policy |
| :--- | :--- | :--- |
| Canonical-only `verify` / `reviewer` as SoT names | `verify-implement` / `verify-qa` + alias stubs | shim+alias ≥1 release then purge stub body in late sNN |
| Dead `expected_verify_agent = …` unused in agent-pretool | branch that DENY/allow on mismatch | delete in-epic |
| Single `need_verify` bool as only flag | per-phase need_* + legacy mirror | shim during alias; purge mirror in purge sNN if safe |
| Blanket «DECOMPOSE → all verify OFF» | implement/qa off; decompose gate on | delete in-epic behavior |

### B. Entrypoints / deploy

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| DSH `verify` / `reviewer` as only preset ids | `verify-implement` / `verify-qa` (+ aliases in map) | shim+alias ≥1 release |
| n/a compose | — | — |

### C. Fallbacks / soft-fail

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| Silent skip when agent file missing | fail-closed DENY / stop-gate message | delete in-epic |
| Metadata-only «verify_agent set» as done | require file + enforce | delete in-epic |

---

## Eng review spine

(See Data flow + Failure matrix above.)

---

<a id="qa-consumes"></a>
## QA consumes (test plan)

### Scope under test

- Epic surfaces: `.claude/agents/verify-*.md`, hooks pretool/stop-gate/normalize, DSH presets, spawn-hard strings.
- Out of scope: Transition Engine redesign; tier1 incident pytest module; frontend suites.

### Test matrix

| ID | Priority | Scenario | Command / fixture | Expected | Maps FR/AC |
|----|----------|----------|-------------------|----------|------------|
| TM-001 | P0 | Agent files exist + discover | `.venv/bin/pytest loop/tests/test_phase_verify_gates.py -k agent_files -q` | PASS | FR-001–004, AC+1 |
| TM-002 | P0 | Phase→agent + pretool enforce | `-k pretool_get_verify_agent` | PASS / DENY mismatch | FR-009, AC+3 |
| TM-003 | P0 | Alias verify→verify-implement | `-k alias_verify` | PASS | FR-007, US-001 |
| TM-004 | P0 | Stop-gate IMPLEMENT need | `-k stop_gate_implement` | block without PASS | FR-010, SC-003 |
| TM-005 | P0 | DECOMPOSE CLI+semantic | `-k stop_gate_decompose` | dual gate | FR-010, US-003 |
| TM-006 | P0 | QA BLOCKED allow FINISH | `-k qa_blocked` | allow | FR-010, US-004 |
| TM-007 | P0 | DSH presets on disk | `-k dsh_verify_presets` or file assert | PASS | FR-013, US-006 |
| TM-008 | P1 | analyze-verify optional | `-k analyze_verify_optional` | no hard gate off | FR-006, US-005 |
| TM-009 | P0 | No dead assign regression | `rg` + unit | PASS | FR-019, SC-007 |
| TM-010 | P0 | Hooks suite regression | `.venv/bin/pytest loop/tests/test_agent_hooks.py -q` | PASS | FR-017 |

### Regression notes

- Alias period: both legacy and new names must pass.
- Do not run frontend tests from verify agents.

---

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| CLARIFY / Product probe | L3: one of done | done | §Product probe (Phase 0 skipped taxonomy clear) |
| Eng review spine | L2+ | done | §Data flow + Failure matrix |
| §0.11 counterparts (draft) | if external refs | done | §Integration §0.11 |
| CREATIVE | if flagged | n/a | CREATIVE need: нет |
| qa_consumes draft | L2+ | done | §QA consumes ≥3 TM (10 rows) |
| Plan review batch | L2+ | done | §Plan review batch log |

## Plan review batch log

| Phase | Auto-resolved | Deferred (owner/next) | Taste / CRITICAL surfaced |
|-------|---------------|-------------------------|---------------------------|
| Product | Scope = leftover 028/029 runtime; queue after 035 | — | none |
| Eng | Reuse registry; no transition rewrite | verify-audit / verify-plan | none |
| Taste | Independent Tests = behavior (file+enforce) | — | none |

---

## Risks

| Risk | Mitigation |
|------|------------|
| Dilution again (metadata steps) | behavior-first + TM Path.exists + enforce |
| State key explosion | namespaced need_* + legacy mirror helper |
| In-flight epics on `@verify` | alias ≥1 release |
| Double DECOMPOSE gate flaky | CLI fail-closed first; semantic mandatory when flag on |
| DSH map drift | file-exists + epic-gate tests |

---

## До DECOMPOSE (черновик s01–s10) — advisory floor

1. **s01** — verify-implement agent file + alias stub verify.md + normalize ALIAS merge + tests file exists  
2. **s02** — verify-bugfix + verify-qa files + reviewer stub + fragment gate-ac-matrix  
3. **s03** — verify-decompose + analyze-verify align  
4. **s04** — agent-pretool **uses** get_verify_agent + spawn_validate CONTRACTS/sections  
5. **s05** — stop-gate + user-prompt per-phase need_* + subagent-stop verdicts  
6. **s06** — DSH presets + epic-gate mapping  
7. **s07** — spawn-hard + finish-block + lean workflows + context_loop finish  
8. **s08** — test_phase_verify_gates matrix + hooks regression  
9. **s09** — docs README/WORKFLOW/architecture  
10. **s10** — legacy-fallback-purge (dead assign, dual-path leftovers)

**Appetite:** timebox ~6–8 дней; cut_list: verify-audit, verify-plan, hard analyze-verify default.

---

## Handoff

- **Next:** `BACK DECOMPOSE T-HUB-039-phase-verify-agents-runtime` (новый чат).  
- **Queue:** after T-HUB-035 in canon `roadmap-epics.queue.yaml`.  
- **Hard dep:** T-HUB-029 (registry). Soft: T-HUB-023.
