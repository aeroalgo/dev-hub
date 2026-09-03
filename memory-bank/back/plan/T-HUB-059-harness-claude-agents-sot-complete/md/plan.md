# [T-HUB-059 | harness-claude-agents-sot-complete] PLAN

**Дата:** 2026-09-03  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** active  
**Roadmap:** [roadmap-harness-universal-runtime-epics.md](roadmap-harness-universal-runtime-epics.md)  
**Queue:** [roadmap-harness-universal-runtime-epics.queue.yaml](roadmap-harness-universal-runtime-epics.queue.yaml)  
**Clarify:** Phase 0 skipped — taxonomy clear (чат 2026-09-03: добить Target layout T-HUB-046 без dilution; layout_dilution gate уже в workflow)

**Skills:** writing-plans · architecture-patterns · python-testing-patterns

→ [T-HUB-059-harness-claude-agents-sot-complete/md/decompose-index.md](T-HUB-059-harness-claude-agents-sot-complete/md/decompose-index.md) — **DECOMPOSE done; next: BACK ANALYZE**

---

## Контекст

- **req:** Эпик [T-HUB-046](plan-T-HUB-046-harness-alongside-install.md) зафиксировал Target layout hub с полным SoT под `harness/claude/{commands,skills,rules}` и `harness/skills/` (из `.agents/skills`), но DECOMPOSE/IMPLEMENT **сузили** FR-002/FR-003: созданы только `CLAUDE.harness.md` + `settings.harness.json`; real dirs `.claude/commands|skills|rules` и `.agents/skills` остались вне harness. Это **layout_dilution** относительно плана 046 — follow-up с полным доведением дерева, без повторного Cut.
- **gap (as-built 2026-09-03):**
  - `harness/cursor/{rules,templates,stubs}` + `.cursor/*` symlinks — **done** (046 s01).
  - `harness/hooks|agents|instructions` + `.claude/{hooks,agents,instructions}` symlinks — **done** (041).
  - `harness/claude/CLAUDE.harness.md`, `settings.harness.json` — **done**; hooks paths → `harness/hooks/` — **done** (hotfix).
  - **MISSING:** `harness/claude/commands/`, `harness/claude/skills/`, `harness/claude/rules/`.
  - **MISSING:** `harness/skills/` (SoT agent skills).
  - **LEFTOVER real dirs:** `.claude/commands` (~101 files), `.claude/skills` (`role-command/`), `.claude/rules` (8 md), `.agents/skills` (~1485 files / ~19M).
  - `bin/hub-link --mode=full` всё ещё `link_one ".agents" "$DEV_HUB/.agents"` и `.claude/{commands,skills,rules}` → **hub `.claude` real dirs**, не `harness/claude/*` / `harness/skills`.
- **deps:** **hard** [T-HUB-046](plan-T-HUB-046-harness-alongside-install.md) (alongside/full installer + harness/cursor). Soft: [T-HUB-041](plan-T-HUB-041-harness-canonical-extract.md), [T-HUB-044](plan-T-HUB-044-runtime-sync-doctor-docs.md) (docs/doctor — FR-011 046 не входит в этот эпик как P0; doctor warn остаётся soft на 044).
- **refs:** plan-T-HUB-046 §Target layout (hub) строки 156–191; chat 2026-09-03; `bin/hub-link`; `loop/tests/test_hub_link_harness.py`; `loop/tests/test_harness_paths.py`.

**CREATIVE need:** нет (git mv + symlink policy детерминированы Target layout 046).

---

## Technology axiom (replace-not-wrap)

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Claude commands SoT | дерево файлов только под `harness/claude/commands/` | editable real dir `.claude/commands/` в hub |
| Claude CC skills SoT | `harness/claude/skills/` (вкл. `role-command/`) | real `.claude/skills/` |
| Claude rules SoT | `harness/claude/rules/` | real `.claude/rules/` |
| Agent skills SoT | `harness/skills/` (= бывший `.agents/skills`) | real `.agents/skills/` как второй SoT |
| Hub dogfood shell | `.claude/{commands,skills,rules}` и `.agents/skills` = **symlinks** на harness | dual writable copies |
| `hub-link --mode=full` | link product shells → **harness** paths (или hub shells, которые уже symlink → harness) | link на устаревшие real dirs как SoT |
| `hub-link --mode=alongside` | **не** symlink `.agents` / `.claude/commands` по умолчанию; opt-in `--with-skills` → только `harness/skills` pointer без overwrite user `.agents` | silent full skills dump в product |

DECOMPOSE → purge-step на каждый legacy real-dir SoT из колонки FORBIDDEN; **запрещён** `Notes: deferred` без epic ID в queue (layout_dilution).

---

## Продуктовая спека (WHAT)

### Product probe (office-hours lite)

| # | Question | Answer / Probe | Decision / Impact on PLAN |
|---|----------|----------------|---------------------------|
| 1 | **Reframe:** Какую проблему решаем? | Hub SoT для Claude commands/rules и agent skills всё ещё размазан: installer/docs говорят `harness/`, диск держит real `.claude/*` / `.agents/skills`. | Эпик = **complete extract**, не новый installer mode. |
| 2 | **Narrowest wedge:** | `git mv` трёх `.claude` деревьев + `.agents/skills` → harness; symlinks; hub-link full переключить на harness SoT; pytest path/layout. | Без redesign alongside. |
| 3 | **Pre-mortem:** | Большой `git mv` skills ломает CI/paths; dual SoT если symlink забыли; alongside начнёт трогать user `.agents`. | Тесты symlink+resolve; alongside default без `.agents`; `--with-skills` fail-closed. |
| 4 | **Distribution:** | `harness/README.md` + hub dogfood; soft pointer T-HUB-044. | Docs in-epic. |
| 5 | **Leverage:** | Паттерн 041/046: mv + symlink + test_harness_paths / hub-link suite. | Не новый binary. |
| 6 | **Appetite:** | L3, ~3–5 дней, ~8–10 sNN. **Нет Cut**, противоречащего Target layout: все path nodes из layout 046 (commands/skills/rules + harness/skills) **in-epic**. | Out of scope только: FR-011 doctor (→ soft 044), Codex materialize, workflow-pack epics. |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как maintainer hub, я хочу единственный SoT Claude commands/rules/skills под `harness/claude/`, чтобы IDE shell `.claude/*` был только symlink. | P0 | `test -L .claude/commands && readlink -f` → `…/harness/claude/commands`; то же для `skills`, `rules`; real dir отсутствует |
| US-002 | Как maintainer, я хочу agent skills SoT в `harness/skills/`, чтобы `.agents/skills` не был вторым editable деревом. | P0 | `test -L .agents/skills && readlink -f` → `…/harness/skills`; sample `SKILL.md` открывается через обе пути |
| US-003 | Как operator `hub-link --mode=full`, я хочу product shells на harness SoT, чтобы product не зависел от устаревших real dirs hub. | P0 | fixture full-link: product `.claude/commands` и `.agents/skills` resolve в hub `harness/…`; pytest green |
| US-004 | Как maintainer чужого репо на `alongside`, я не хочу автозамены моего `.agents`, пока не попрошу `--with-skills`. | P0 | alongside без флага: user `.agents` не тронут; с `--with-skills`: только installer-owned link/fail-closed, без overwrite regular dir |
| US-005 | Как CI, я хочу layout gate, который падает при возврате real `.claude/commands` в hub. | P0 | `pytest loop/tests/test_harness_paths.py` (или новый layout test) FAIL если not symlink |

#### Acceptance Scenarios — US-001

- **Given:** hub после эпика
- **When:** `ls -la .claude/commands .claude/skills .claude/rules`
- **Then:** каждый path — symlink; `readlink -f` оканчивается на `harness/claude/{commands,skills,rules}`; содержимое role-command / commands доступно через shell

#### Acceptance Scenarios — US-002

- **Given:** hub после эпика
- **When:** `test -f harness/skills/<any>/SKILL.md` и `test -f .agents/skills/<same>/SKILL.md`
- **Then:** оба true; inode/target один SoT (`harness/skills`)

#### Acceptance Scenarios — US-003

- **Given:** clean product fixture + `hub-link --mode=full`
- **When:** resolve product `.claude/commands` и `.agents/skills`
- **Then:** targets under `$DEV_HUB/harness/claude/commands` и `$DEV_HUB/harness/skills` (напрямую или через hub shell symlink)

#### Acceptance Scenarios — US-004

- **Given:** product с pre-existing `.agents/skills` regular dir
- **When:** `hub-link --mode=alongside` без `--with-skills`
- **Then:** exit 0; `.agents` bytes/tree unchanged
- **When:** `hub-link --mode=alongside --with-skills` и `.agents` уже regular conflict
- **Then:** exit ≠0 fail-closed; user tree not replaced

### Functional Requirements (FR-###)

- **FR-001:** `git mv .claude/commands` → `harness/claude/commands`; заменить `.claude/commands` symlink `../harness/claude/commands`.
- **FR-002:** `git mv .claude/skills` → `harness/claude/skills`; `.claude/skills` → symlink на harness.
- **FR-003:** `git mv .claude/rules` → `harness/claude/rules`; `.claude/rules` → symlink на harness.
- **FR-004:** `git mv .agents/skills` → `harness/skills`; `.agents/skills` → symlink `../harness/skills`; сохранить `.agents/.skill-lock.json` (и прочие non-skills файлы) как real files в `.agents/` (не требовать symlink всего `.agents`).
- **FR-005:** Обновить `bin/hub-link --mode=full`: link product `.claude/{commands,skills,rules}` и `.agents/skills` на **harness** SoT (`$DEV_HUB/harness/claude/…`, `$DEV_HUB/harness/skills`), не на устаревшие real-dir assumptions; refresh idempotent для installer symlinks.
- **FR-006:** `bin/hub-link --mode=alongside`: default **не** трогает `.agents` / `.claude/commands|skills|rules`; добавить `--with-skills` (fail-closed on conflict) создающее только installer-owned link на `harness/skills` **или** документированный pointer — без overwrite user regular tree.
- **FR-007:** Расширить/добавить pytest: hub layout symlinks (commands/skills/rules + agents skills); full-mode resolve; alongside no-touch `.agents`; negative conflict `--with-skills`.
- **FR-008:** Обновить `harness/README.md`, `memory-bank/architecture/services.md` (и при необходимости AGENTS.md stub text в hub-link) — SoT paths = harness; `.claude`/`.agents/skills` = shells.
- **FR-009:** Kind I: grep/docs/tests, требующие real `.claude/commands` или `.agents/skills` как SoT — rewrite на harness paths (кроме исторических archive/memory-bank prose вне runtime).
- **FR-010:** Финальный purge: нет dual writable SoT; obsolete tests на «`.agents` must be real dir SoT» — delete/rewrite; `test_hub_link_harness.py` / path tests green.

### Success Criteria (SC-###)

| ID | Измеримый результат | Проверка | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | Все четыре SoT path nodes из Target layout 046 существуют под harness | `test -d harness/claude/{commands,skills,rules} && test -d harness/skills` | outcome |
| SC-002 | Hub shells — symlinks | `test -L` ×4 (commands, skills, rules, agents/skills) | outcome |
| SC-003 | full hub-link fixture resolves to harness | pytest TM-003 | outcome |
| SC-004 | alongside default не мутирует user `.agents` | pytest TM-004 | outcome |
| SC-005 | Нет dual SoT (real + harness) после эпика | `rg`/layout test; real dir at shell path = FAIL | outcome |

### Assumptions

- Claude Code читает `.claude/commands|skills|rules` через symlink (как уже для hooks/agents).
- Cursor/agents consumers читают `.agents/skills` через symlink.
- Размер `.agents/skills` (~19M) допустим для `git mv` в одном эпике; не дробить на «partial skills migrate».
- `.agents/.skill-lock.json` остаётся в `.agents/` (не SoT skills tree).

### Clarifications

- Session: 2026-09-03 — complete 046 Target layout; no Appetite Cut against layout paths.
- Parent epic 046 audit PASS при неполном layout = process bug; этот эпик — remediation продукта + layout.

### [НУЖНО УТОЧНИТЬ]

- n/a

---

## AC

1. Target layout hub 046 path nodes: `harness/claude/commands|skills|rules` + `harness/skills` — **существуют и являются SoT**.
2. `.claude/commands|skills|rules` и `.agents/skills` в hub — **symlinks** на harness.
3. `hub-link --mode=full` линкует product на harness SoT (прямо или через hub shell symlink).
4. `hub-link --mode=alongside` default не трогает user `.agents` / Claude command trees.
5. pytest layout + hub-link suites green.
6. Docs/architecture отражают harness SoT; Kind I runtime instructions rewritten.

### AC−

1. Real editable `.claude/commands|skills|rules` или `.agents/skills` в hub после эпика.
2. Dual SoT (копии и в harness, и в `.claude`/`.agents` без symlink).
3. `Notes: deferred` / partial migrate skills «потом» без follow-up ID в queue.
4. alongside default overwrite/replace user `.agents`.
5. `hub-link --mode=full` продолжает считать real `.claude/commands` SoT.
6. Живые тесты, требующие real-dir SoT на старых путях.

---

## Техника / архитектура (HOW)

### Target layout (hub) — канон после эпика

```text
dev-hub/
├── harness/
│   ├── hooks/                 # 041 ✓
│   ├── agents/                # 041 ✓
│   ├── instructions/          # 041 ✓
│   ├── cursor/                # 046 ✓
│   │   ├── rules/
│   │   ├── templates/
│   │   └── stubs/
│   ├── claude/
│   │   ├── CLAUDE.harness.md          # 046 ✓
│   │   ├── settings.harness.json      # 046 ✓ (hooks → harness/hooks)
│   │   ├── commands/                  # THIS EPIC ← .claude/commands
│   │   ├── skills/                    # THIS EPIC ← .claude/skills (role-command)
│   │   └── rules/                     # THIS EPIC ← .claude/rules
│   └── skills/                        # THIS EPIC ← .agents/skills
│
├── .cursor/
│   ├── rules → ../harness/cursor/rules          # 046 ✓
│   └── templates → ../harness/cursor/templates  # 046 ✓
│
├── .claude/
│   ├── hooks → ../harness/hooks                 # 041 ✓
│   ├── agents → ../harness/agents               # 041 ✓
│   ├── instructions → ../harness/instructions   # 041 ✓
│   ├── commands → ../harness/claude/commands    # NEW
│   ├── skills → ../harness/claude/skills        # NEW
│   ├── rules → ../harness/claude/rules          # NEW
│   ├── settings.json                            # hub dogfood (full) — keep
│   └── runtime/                                 # local ephemeral
│
├── .agents/
│   ├── .skill-lock.json                         # keep real
│   └── skills → ../harness/skills               # NEW
│
└── bin/hub-link · hub-unlink
```

### Target layout (product `full`)

```text
.agents/skills → $DEV_HUB/harness/skills
.claude/commands → $DEV_HUB/harness/claude/commands   # (or via hub .claude shell)
.claude/skills → $DEV_HUB/harness/claude/skills
.claude/rules → $DEV_HUB/harness/claude/rules
(+ existing harness/, hooks/agents/instructions links)
```

### Target layout (product `alongside`)

Без изменений политики 046 для user trees: **не** symlink `.claude/commands|skills|rules` и **не** `.agents` по умолчанию.  
`--with-skills`: только installer-owned artifact на `harness/skills` (symlink path, fail-closed если conflict с regular user dir).

### Files touch matrix

| Файл / дерево | Действие |
|---------------|----------|
| `harness/claude/commands/` | git mv from `.claude/commands` |
| `harness/claude/skills/` | git mv from `.claude/skills` |
| `harness/claude/rules/` | git mv from `.claude/rules` |
| `harness/skills/` | git mv from `.agents/skills` |
| `.claude/commands\|skills\|rules` | replace with symlinks |
| `.agents/skills` | replace with symlink |
| `bin/hub-link` | full → harness SoT; alongside `--with-skills` |
| `bin/hub-unlink` | unlink installer-owned skills link if added |
| `loop/tests/test_harness_paths.py` | extend layout asserts |
| `loop/tests/test_hub_link_harness.py` | full mode resolve harness |
| `loop/tests/test_hub_link_alongside.py` | no-touch + `--with-skills` |
| `harness/README.md` | document SoT trees |
| `memory-bank/architecture/services.md` | shells table update |

### §0.11 counterparts (draft)

| External / shell ref | Counterpart |
|----------------------|-------------|
| `.claude/commands/*` | `harness/claude/commands/*` |
| `.claude/skills/role-command` | `harness/claude/skills/role-command` |
| `.claude/rules/*.md` | `harness/claude/rules/*.md` |
| `.agents/skills/*/SKILL.md` | `harness/skills/*/SKILL.md` |
| hub-link full product links | harness paths above |

---

## Eng review spine

### Data flow (ASCII)

```text
[Maintainer] --> git mv trees --> harness/claude/{commands,skills,rules}
                                --> harness/skills
         |
         +--> ln -s shells .claude/* .agents/skills
         |
[Operator] --> hub-link --mode=full
         |         |
         |         +--> product .claude/{commands,skills,rules} --> harness/claude/...
         |         +--> product .agents/skills --> harness/skills
         |
         +--> hub-link --mode=alongside [--with-skills]
                   |
                   +--> default: no .agents / no .claude command trees
                   +--> --with-skills: fail-closed link OR exit 2

[Claude Code] --> reads .claude/commands via symlink --> harness SoT
[Agent runtime] --> reads .agents/skills via symlink --> harness/skills
```

### Failure matrix

| Component / link | Failure | Detection | Response | Test ID |
|------------------|---------|-----------|----------|---------|
| git mv partial (skills only) | dual SoT | layout test | FAIL CI; complete mv | TM-001 |
| forgot symlink `.claude/commands` | real dir leftover | `test -L` | FAIL layout | TM-001 |
| hub-link full still links old real path | product on dead SoT | resolve pytest | exit fail / test FAIL | TM-003 |
| alongside touches user `.agents` | overwrite | pytest | FAIL | TM-004 |
| `--with-skills` + user regular dir | would replace | preflight `-e` not symlink | exit 2 | TM-005 |
| broken symlink after mv | missing target | `test -e` via shell | fail-closed | TM-002 |
| docs still teach `.agents` as SoT | Kind I | instruction_rg | rewrite | TM-006 |

### Eng spine self-check

| Dimension | Score 1–5 | Gap / action |
|-----------|-----------|--------------|
| Data flow complete | 5 | — |
| Failure coverage | 5 | — |
| Testability | 5 | fixture + layout tests |

---

## Replacement / sunset

### A. Code / modules

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| `.claude/commands` (real dir SoT) | `harness/claude/commands` + symlink | delete in-epic (mv) |
| `.claude/skills` (real dir SoT) | `harness/claude/skills` + symlink | delete in-epic (mv) |
| `.claude/rules` (real dir SoT) | `harness/claude/rules` + symlink | delete in-epic (mv) |
| `.agents/skills` (real dir SoT) | `harness/skills` + symlink | delete in-epic (mv) |
| tests asserting `.agents` / `.claude/commands` must be real SoT dirs | rewrite to symlink+harness resolve | delete/rewrite in-epic |
| hub-link full `link_one ".agents" "$DEV_HUB/.agents"` as SoT assumption | link `.agents/skills` → harness/skills (and claude trees → harness/claude) | delete in-epic |

### B. Entrypoints / deploy

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| `hub-link --mode=full` product links to hub real `.claude/commands` | links to `$DEV_HUB/harness/claude/commands` (or hub shell symlink) | delete in-epic |
| `hub-link --mode=full` `link_one ".agents" …` treating whole `.agents` as skills SoT | `.agents/skills` → harness/skills | delete in-epic |
| Makefile/`make hub-link` docs implying `.agents` tree SoT | harness/skills wording | delete in-epic (docs) |

### C. Fallbacks / soft-fail

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| «skills stay in .agents if mv hard» silent skip | fail-closed / complete mv | delete in-epic |
| dual keep copy in `.claude` and harness | sole harness + symlink | delete in-epic |
| alongside auto full skills on conflict | exit 2 | delete in-epic |

### I. Instruction surfaces

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| README/AGENTS stub «Skills: `.agents/skills`» as SoT | `harness/skills/*/SKILL.md` (+ shell note) | delete in-epic |
| architecture/services.md shells omitting claude commands/rules | update shells table | delete in-epic |
| harness/README incomplete tree | full Target layout section | delete in-epic |
| test comments requiring real `.claude/commands` SoT | harness paths | delete in-epic |

---

<a id="qa-consumes"></a>
## QA consumes (test plan)

### Scope under test

- Hub layout symlinks for `.claude/{commands,skills,rules}`, `.agents/skills`
- Existence of `harness/claude/{commands,skills,rules}`, `harness/skills`
- `bin/hub-link` full + alongside (+ `--with-skills`)
- Docs SoT wording (spot check)

### Out of scope for QA

- FR-011 doctor legacy warn (T-HUB-044)
- Codex/runtime adapters
- Content correctness of individual SKILL.md / command md bodies (только path/SoT)

### Test matrix

| ID | Priority | Scenario | Command / fixture | Expected | Maps FR/AC |
|----|----------|----------|-------------------|----------|------------|
| TM-001 | P0 | hub shells are symlinks to harness | `bin/pytest loop/tests/test_harness_paths.py -q` (+ extended cases) | PASS; `-L` + resolve | US-001, US-002, AC-1/2, SC-001/002 |
| TM-002 | P0 | sample files reachable via shell and harness | same / targeted asserts | PASS | FR-001..004 |
| TM-003 | P0 | full hub-link resolves to harness | `bin/pytest loop/tests/test_hub_link_harness.py -q` | PASS | US-003, FR-005, SC-003 |
| TM-004 | P0 | alongside leaves user `.agents` untouched | `bin/pytest loop/tests/test_hub_link_alongside.py -k agents -q` | PASS | US-004, FR-006, SC-004 |
| TM-005 | P0 | `--with-skills` conflict fail-closed | new negative test | exit ≠0; tree intact | US-004, AC−4 |
| TM-006 | P1 | no dual SoT leftover | layout rg / pytest | 0 real-dir SoT at shell paths | SC-005, AC−1/2 |
| TM-007 | P1 | README/architecture mention harness SoT | file asserts / manual spot | wording OK | FR-008, FR-009 |

### Regression notes

- Run hub-link tests only in temp fixtures; never alongside against hub root.
- Large skills tree: prefer path existence smoke, not full file hash of 1485 skills.

---

## Advisory step sketch (не трекер; DECOMPOSE нарежет)

| Sketch | Intent |
|--------|--------|
| s01 | git mv `.claude/commands` → `harness/claude/commands` + symlink |
| s02 | git mv `.claude/skills` → `harness/claude/skills` + symlink |
| s03 | git mv `.claude/rules` → `harness/claude/rules` + symlink |
| s04 | git mv `.agents/skills` → `harness/skills` + symlink; keep `.skill-lock.json` |
| s05 | hub-link `--mode=full` → harness SoT links |
| s06 | hub-link alongside `--with-skills` + unlink |
| s07 | pytest layout + hub-link suites |
| s08 | docs/architecture/Kind I rewrite |
| s09 | legacy-fallback-purge (dual SoT + obsolete tests) |

---

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| CLARIFY / Product probe | L3 | done | Phase 0 skipped — taxonomy clear; §Product probe filled |
| Eng review spine | L2+ | done | §Eng review spine |
| §0.11 counterparts (draft) | yes | done | §0.11 table in HOW |
| CREATIVE | if flagged | n/a | no |
| qa_consumes draft | L2+ | done | ≥3 TM in §QA consumes |
| Plan review batch | L2+ | done | §Plan review batch log |

## Plan review batch log

| Topic | Decision | Rationale |
|-------|----------|-----------|
| Scope vs 046 | Remediative complete of Target layout only | Avoid reopening alongside rewrite |
| Appetite Cut | **None** against layout paths | layout_dilution HARD |
| `.agents` whole vs `skills` | Symlink only `.agents/skills`; keep `.skill-lock.json` | Matches SoT noun harness/skills |
| Doctor FR-011 | Soft → T-HUB-044 | Not layout blocker |
| Skills volume | Single epic git mv | Partial migrate = dilution |

---

## Нарезка (advisory floor)

Черновик s01–s09 выше — **floor**. DECOMPOSE добавляет sNN при дырах coverage; **запрещено** выносить `harness/skills` или `harness/claude/commands` в follow-up без ID в queue.
