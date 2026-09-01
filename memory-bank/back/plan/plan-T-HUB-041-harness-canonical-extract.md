# [T-HUB-041 | harness-canonical-extract] PLAN

**Дата:** 2026-09-01  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** active  
**Roadmap:** [roadmap-harness-universal-runtime-epics.md](roadmap-harness-universal-runtime-epics.md)  
**Queue:** [roadmap-harness-universal-runtime-epics.queue.yaml](roadmap-harness-universal-runtime-epics.queue.yaml)  
**Clarify:** Phase 0 skipped — taxonomy clear (harness vs runtime shell зафиксированы в обсуждении 2026-09-01)

**Skills:** writing-plans · architecture-patterns · python-testing-patterns

→ [decompose-T-HUB-041-harness-canonical-extract/index.md](decompose-T-HUB-041-harness-canonical-extract/index.md) — **после DECOMPOSE**

---

## Контекст

- **req:** Поведение loop (hooks, agents, instructions) живёт под `.claude/` — runtime-agnostic logic притворяется Claude-specific. Нужен canonical `harness/` SoT; `.claude/*` — thin symlink shell; `loop/` импортирует `harness/`, не `.claude/hooks`.
- **deps:** **hard** нет. **Soft:** T-HUB-035 (boundaries.yaml должен включить `harness/` после extract).
- **refs:** `.claude/hooks/`, `.claude/agents/`, `.claude/instructions/`, `bin/hub-link`, `loop/loop.sh`, `memory-bank/systemPatterns.md` SP-H05, обсуждение 2026-09-01.

### Зафиксированные решения

| Тема | Решение |
|------|---------|
| Canonical path | `harness/{hooks,agents,instructions}/` — единственный SoT поведения |
| `.claude/` | symlinks → `harness/*` + format-specific files (`settings.json`, `project.env`) |
| Product hub-link | product tree **по-прежнему** видит `.claude/hooks` (symlink chain unchanged для оператора) |
| `loop/` imports | `sys.path` / imports → `harness/hooks`, purge `.claude/hooks` из loop hot path |
| `.cursor/rules` | остаёт IDE layer; не move в harness (mdc format) |
| Runtime state | `.claude/runtime/` — local per product, **не** в harness |

**CREATIVE need:** нет.

---

## Technology axiom (replace-not-wrap)

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Behavior SoT | `harness/hooks/*.py`, `harness/agents/*.md` | duplicate logic under `.claude/hooks` as writable copy |
| Loop import path | `harness.hooks` / `HUB_ROOT/harness/hooks` | `loop/` hard-import `.claude/hooks` as SoT |
| Product link | symlink `.claude/hooks → harness/hooks` | copy-on-link file trees |

---

## Продуктовая спека (WHAT)

### Product probe (office-hours lite)

| # | Question | Answer / Probe | Decision / Impact on PLAN |
|---|----------|----------------|---------------------------|
| 1 | **Reframe:** Какую проблему решаем? | Loop behavior tied to Claude path; Codex/DSH bridges дублируют hooks. | Extract `harness/` — prerequisite для universal runtime. |
| 2 | **Narrowest wedge:** | Move hooks+agents+instructions; symlinks; fix loop imports; zero behavior change. | No adapter work in this epic. |
| 3 | **Pre-mortem:** | Big-bang move breaks pytest paths, hub-link, DSH bridge paths. | TDD: grep audit + symlink integration test + full pytest subset. |
| 4 | **Adoption:** | Transparent — operators still use `.claude/hooks` via symlink. | README note only (full docs → T-HUB-044). |
| 5 | **Leverage:** | Reuse hub-link symlink machinery; git mv not copy. | `git mv` + `ln -sfn` in hub root. |
| 6 | **Appetite:** | L3, ~3–5 дней, 6–8 sNN. | Cut: `harness/schemas/` move (defer to 042 if needed). |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как maintainer, я хочу один canonical path для hooks, чтобы новый runtime не копировал `.claude/`. | P0 | `harness/hooks/stop-gate.py` exists; `.claude/hooks` is symlink |
| US-002 | Как loop runner, я хочу import из `harness/`, чтобы orchestrator не зависел от Claude layout. | P0 | `rg '\.claude/hooks' loop/` → only compat shims or zero |
| US-003 | Как operator продукта, я хочу `make hub-link` без изменений UX. | P0 | hub-link → product `.claude/hooks` resolves to harness |
| US-004 | Как CI, я хочу zero regression на hooks tests. | P0 | pytest loop/tests/test_* hooks subset green |

#### Acceptance Scenarios — US-001

- **Given:** dev-hub checkout with `.claude/hooks/stop-gate.py`
- **When:** epic completes extract
- **Then:** file lives at `harness/hooks/stop-gate.py`; `.claude/hooks` → `../harness/hooks`

### Functional Requirements (FR-###)

- **FR-001:** Create `harness/` package layout: `hooks/`, `agents/`, `instructions/`, `README.md` (index).
- **FR-002:** `git mv` `.claude/hooks` → `harness/hooks`; same for `agents`, `instructions`.
- **FR-003:** Replace `.claude/hooks|agents|instructions` with symlinks to `harness/*`.
- **FR-004:** Update `loop/loop.sh`, `loop/context_loop.py`, `.claude/hooks`-adjacent imports in `loop/tests/` to use `harness/hooks`.
- **FR-005:** Update `bin/hub-link` to link product `.claude/hooks` → hub `harness/hooks` **or** keep link to `.claude/hooks` symlink (either valid; prefer unchanged product paths).
- **FR-006:** Purge direct `.claude/hooks` sys.path inserts in loop hot path (grep audit + fix).
- **FR-007:** Update `memory-bank/architecture/services.md` + `systemPatterns.md` SP-H05 row for harness path.
- **FR-008:** pytest: `test_harness_paths.py` — symlink integrity + import smoke.

### Success Criteria (SC-###)

| ID | Измеримый результат | Проверка | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | 0 loop hot-path imports of `.claude/hooks` as SoT | rg audit | outcome |
| SC-002 | hub-link product tree resolves hooks | integration test | outcome |
| SC-003 | pytest hooks/loop subset green | CI command | outcome |

### Assumptions

- Git symlinks supported on dev/CI Linux (as today for hub-link).
- DSH cc-hooks-bridge resolves hooks via `.claude/settings.json` path — symlink preserves compatibility.

### Clarifications

- Session: 2026-09-01 chat — harness vs runtime shell architecture fixed.
- Open: `harness/schemas/` for phase_registry deferred to T-HUB-042 (optional symlink `harness/schemas → loop/schemas`).

---

## AC+

1. `harness/hooks/stop-gate.py` exists; `.claude/hooks` is symlink to `harness/hooks`.
2. `loop/loop.sh` inserts `harness/hooks` on sys.path (not `.claude/hooks`).
3. `bin/hub-link` on fixture product → `.claude/hooks` usable (file reachable).
4. `pytest loop/tests/test_agent_hooks.py loop/tests/test_runtime_config.py -q` green.
5. Architecture doc row for S-HUB-LINK / harness layer updated.

### AC−

1. Duplicate writable hooks tree under `.claude/hooks` (non-symlink).
2. loop imports `.claude/hooks` as canonical SoT after epic.
3. Breaking product hub-link without migration note.
4. Moving `.cursor/rules` into harness (out of scope).

---

## Техника / архитектура (HOW)

### Target layout

```text
dev-hub/
├── harness/
│   ├── README.md
│   ├── hooks/          ← moved from .claude/hooks
│   ├── agents/         ← moved from .claude/agents
│   └── instructions/   ← moved from .claude/instructions
├── .claude/
│   ├── hooks      → ../harness/hooks
│   ├── agents     → ../harness/agents
│   ├── instructions → ../harness/instructions
│   ├── settings.json
│   └── project.env
└── loop/               ← imports harness.hooks
```

### Files touch matrix

| Файл | Действие |
|------|----------|
| `harness/**` | create via git mv |
| `.claude/hooks`, `agents`, `instructions` | symlink |
| `loop/loop.sh` | sys.path → harness |
| `loop/context_loop.py` | import paths if any |
| `loop/tests/**` | fix paths referencing `.claude/hooks` |
| `bin/hub-link` | verify / optional direct harness link |
| `dsh/patches/cc-hooks-bridge.yml` | verify CLAUDE_PROJECT_DIR still resolves |
| `memory-bank/architecture/services.md` | update |
| `memory-bank/systemPatterns.md` | SP-H05 update |

---

## Eng review spine

### Data flow (ASCII)

```text
[loop/loop.sh] -> sys.path harness/hooks -> [stop-gate.py]
                                              ^
[Claude CLI] ----reads symlink-------------> .claude/hooks -> harness/hooks
[product hub-link] -> .claude/hooks symlink -> hub harness/hooks
```

### Failure matrix

| Component / link | Failure | Detection | Response | Test ID |
|------------------|---------|-----------|----------|---------|
| symlink broken | `.claude/hooks` not directory/link | import smoke | fail-closed pytest | TM-001 |
| loop old path | sys.path .claude/hooks | rg audit | CI fail | TM-002 |
| hub-link product | dest exists non-symlink | hub-link test | exit 2 | TM-003 |
| DSH bridge | settings path wrong | dsh smoke optional | warn in 043 | TM-004 |
| git mv | broken relative imports in hooks | pytest | fix imports | TM-005 |

### Eng spine self-check

| Dimension | Score | Gap / action |
|-----------|-------|--------------|
| Data flow complete | 4 | verify DSH in 043 |
| Failure coverage | 4 | symlink test required |
| Testability | 5 | pytest + rg |

---

## Replacement / sunset

### A. Code / modules

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| `.claude/hooks/` as real directory | `harness/hooks/` + symlink | delete in-epic (mv) |
| `.claude/agents/` real dir | `harness/agents/` + symlink | delete in-epic |
| `.claude/instructions/` real dir | `harness/instructions/` + symlink | delete in-epic |
| loop sys.path `.claude/hooks` | `harness/hooks` | delete in-epic |

### B. Entrypoints

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| n/a | — | greenfield extension |

### C. Fallbacks

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| implicit `.claude/hooks` if harness missing | fail at import | fail-closed |

---

<a id="qa-consumes"></a>
## QA consumes (test plan)

### Scope under test

- harness extract, symlinks, loop import paths, hub-link compatibility.

### Test matrix

| ID | Priority | Scenario | Command / fixture | Expected | Maps FR/AC |
|----|----------|----------|-------------------|----------|------------|
| TM-001 | P0 | symlink integrity | `pytest loop/tests/test_harness_paths.py` | PASS | AC-1 |
| TM-002 | P0 | loop import path audit | `rg '\.claude/hooks' loop/ --glob '!*test*'` | 0 matches or shim only | AC-2 |
| TM-003 | P0 | hooks regression | `pytest loop/tests/test_agent_hooks.py loop/tests/test_stop_gate*.py -q` | PASS | AC-4 |
| TM-004 | P1 | hub-link fixture | `pytest loop/tests/test_hub_link_harness.py` | PASS | AC-3 |
| TM-005 | P1 | runtime config still loads | `pytest loop/tests/test_runtime_config.py -q` | PASS | FR-004 |

---

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| CLARIFY / Product probe | L3 | done | §Product probe 6 rows |
| Eng review spine | L2+ | done | §Eng review spine |
| §0.11 counterparts | if external | n/a | no new external APIs |
| CREATIVE | if flagged | n/a | — |
| qa_consumes draft | L2+ | done | ≥5 TM |
| Plan review batch | L2+ | done | §Plan review batch log |

---

## Plan review batch log

| Phase | Auto-resolved | Deferred | Taste / CRITICAL |
|-------|---------------|----------|------------------|
| Product | harness=behavior, .claude=shell | — | — |
| Eng | git mv + symlink over copy | boundaries.yaml → soft 035 | — |

---

## До DECOMPOSE (черновик нарезки)

| sNN | Slice |
|-----|-------|
| s01 | Create `harness/` layout + README |
| s02 | git mv hooks/agents/instructions |
| s03 | symlinks `.claude/*` → harness |
| s04 | loop/loop.sh + context_loop import path purge |
| s05 | loop/tests path fixes + test_harness_paths |
| s06 | hub-link verify/update |
| s07 | architecture/systemPatterns docs |
| s08 | legacy path purge + full pytest subset |

---

## Appetite

| Поле | Значение |
| :--- | :--- |
| `timebox_days` | 5 |
| `cut_list` | `['harness/schemas symlink', 'optional DSH re-verify']` |

---

## Следующий режим

→ BACK DECOMPOSE (T-HUB-041) · затем T-HUB-042 PLAN already done in roadmap
