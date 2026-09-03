# [T-HUB-046 | harness-alongside-install] PLAN

**Дата:** 2026-09-02  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** active  
**Roadmap:** [roadmap-harness-universal-runtime-epics.md](roadmap-harness-universal-runtime-epics.md)  
**Queue:** [roadmap-harness-universal-runtime-epics.queue.yaml](roadmap-harness-universal-runtime-epics.queue.yaml)  
**Clarify:** Phase 0 skipped — taxonomy clear (обсуждение 2026-09-02: additive install, не перезапись чужого workflow)

**Skills:** writing-plans · architecture-patterns · python-testing-patterns

→ [T-HUB-046-harness-alongside-install/md/decompose-index.md](T-HUB-046-harness-alongside-install/md/decompose-index.md) — **после DECOMPOSE**

---

## Контекст

- **req:** Сегодня `bin/hub-link` **заменяет** целые деревья продукта (`.cursor/rules`, `CLAUDE.md`, `.claude/settings.json`) symlink-ами на hub и **падает** (`exit 2`), если у человека уже есть свои rules/settings. Это ломает adoption: harness «захватывает» workflow вместо того, чтобы лечь **рядом** и активироваться opt-in (role command `BACK IMPLEMENT`, …).
- **gap (as-built):**
  - T-HUB-041 вынес hooks/agents/instructions в `harness/`, но зафиксировал «`.cursor/rules` остаёт IDE layer» — workflow prose всё ещё живёт в корневом `.cursor/`, а `hub-link` symlink-ит его целиком в продукт.
  - `CLAUDE.md` продукта полностью подменяется hub-версией.
  - Нет режима install «только указатели + harness symlink».
  - Нет machine API для patch/merge существующих файлов пользователя.
- **deps:** **hard** [T-HUB-041](plan-T-HUB-041-harness-canonical-extract.md) (`harness/` package exists). **Soft:** [T-HUB-044](plan-T-HUB-044-runtime-sync-doctor-docs.md) (operator docs/runbook), [T-HUB-043](plan-T-HUB-043-runtime-bridge-codex.md) (`harness/manifest.yaml` может ссылаться на `harness/cursor/` после этого эпика).
- **refs:** `bin/hub-link`, `bin/hub-unlink`, `loop/tests/test_hub_link_harness.py`, обсуждение 2026-09-02, [plan-T-HUB-041](plan-T-HUB-041-harness-canonical-extract.md) §Target layout (amend).

**CREATIVE need:** нет (router stub + patch markers — детерминированы в plan).

---

## Technology axiom (replace-not-wrap)

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Install mode | `Literal["alongside", "full"]` CLI flag; default `alongside` | implicit full-replace без флага |
| User file patch | Marker block `<!-- dev-hub:harness:begin -->` … `<!-- dev-hub:harness:end -->` в `CLAUDE.md` | silent overwrite целого `CLAUDE.md` |
| Settings merge | `settings.harness.json` + deterministic `jq` merge schema; exit ≠0 on conflict keys без `--force-merge` | symlink замена `settings.json` в `alongside` |
| Cursor activation | Real file stub `dev-hub-harness-router.mdc` с opt-in trigger (role command prefix) | symlink всего `.cursor/rules/` в `alongside` |
| Workflow SoT path | `harness/cursor/rules/**`, `harness/cursor/templates/**` | editable copies под `.cursor/rules` в hub как SoT |
| Uninstall | `hub-unlink --mode alongside` удаляет только artifacts installer | ручное удаление user files |

DECOMPOSE → purge-step на каждый legacy path из колонки FORBIDDEN.

---

## Продуктовая spека (WHAT)

### Product probe (office-hours lite)

| # | Question | Answer / Probe | Decision / Impact on PLAN |
|---|----------|----------------|---------------------------|
| 1 | **Reframe:** Какую проблему решаем? | Adoption: люди боятся ставить hub, потому что он перетирает их CLAUDE.md / Cursor rules. | Фокус = **non-destructive install**, не новые workflow-фичи. |
| 2 | **Narrowest wedge:** | `hub-link --mode=alongside`: symlink `harness/` + thin router stub + `CLAUDE.harness.md`; не трогать существующие rules/settings. | Phase 1 без manifest/runtime-sync (→ T-HUB-043). |
| 3 | **Pre-mortem:** | Router `alwaysApply:true` всё равно мешает; merge settings ломает hooks; git mv rules ломает dev-hub dogfood. | Router с узким триггером; merge только `hooks` section; dev-hub остаётся `--mode=full`. |
| 4 | **Distribution:** | README + `make hub-link` + doctor warn если product на legacy full без осознанного выбора. | Docs pointer → T-HUB-044 soft. |
| 5 | **Leverage:** | Reuse `hub-link` `link_one`/`rel_or_abs`; reuse T-HUB-041 harness tree; patch markers как FINISH doc-router pattern. | Не новый installer binary — расширение `bin/hub-link`. |
| 6 | **Appetite:** | L3, ~4–6 дней, 8–10 sNN. | Cut: `.agents` bulk move (можно оставить symlink только в `full`); Codex materialize paths. |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как maintainer чужого репо, я хочу `hub-link` без перезаписи моего `CLAUDE.md`, чтобы сохранить свой workflow. | P0 | Product fixture с existing `CLAUDE.md` → `hub-link` exit 0; original bytes preserved outside marker block |
| US-002 | Как maintainer, я хочу opt-in activation harness по role command, чтобы обычный чат в Cursor не менял поведение. | P0 | Message без `BACK ` prefix → harness rules не referenced; с `BACK IMPLEMENT` → router loads `harness/cursor/rules/mainrule.mdc` |
| US-003 | Как operator dev-hub, я хочу `--mode=full` для self-dogfood, чтобы hub repo работал как сейчас. | P0 | `hub-link --mode=full` на clean fixture → `.cursor/rules` symlink; pytest green |
| US-004 | Как operator, я хочу `hub-unlink --mode=alongside` убрать только добавленное harness, не трогая мои файлы. | P1 | unlink removes stub + harness symlink + marker block; user `CLAUDE.md` body intact |
| US-005 | Как Claude Code user с existing `settings.json`, я хочу merge hooks из harness, не заменяя permissions. | P1 | merge preserves user `permissions`; adds harness `hooks` paths to `harness/hooks/*.py` |
| US-006 | Как CI, я хочу тест «existing file not overwritten» как gate. | P0 | `pytest loop/tests/test_hub_link_alongside.py` PASS |

#### Acceptance Scenarios — US-001

- **Given:** empty product dir with pre-existing `CLAUDE.md` containing `# My Project`
- **When:** `DEV_HUB=… ./bin/hub-link /product --mode=alongside`
- **Then:** exit 0; `CLAUDE.md` still contains `# My Project`; file has `<!-- dev-hub:harness:begin -->` section; `CLAUDE.harness.md` symlink exists; `harness/` symlink exists

#### Acceptance Scenarios — US-002

- **Given:** product linked `alongside`, stub at `.cursor/rules.d/dev-hub-harness-router.mdc`
- **When:** agent receives user message `explain this function` (no role prefix)
- **Then:** harness router instructs ignore (no load of `harness/cursor/rules/mainrule.mdc`)

- **When:** user message `BACK IMPLEMENT continue`
- **Then:** router instructs Read `@harness/cursor/rules/mainrule.mdc` and role chain

#### Acceptance Scenarios — US-005

- **Given:** product `.claude/settings.json` with custom `permissions.deny`
- **When:** `hub-link --mode=alongside` runs settings merge
- **Then:** `permissions.deny` unchanged; `hooks.SessionStart` includes harness hook command pointing to `$PROJECT_ROOT/harness/hooks/session-start.py`

### Functional Requirements (FR-###)

- **FR-001:** `git mv` `.cursor/rules` → `harness/cursor/rules`; `.cursor/templates` → `harness/cursor/templates`; dev-hub `.cursor/rules` → symlink `../harness/cursor/rules` (SoT single path).
- **FR-002:** Create `harness/claude/` with `CLAUDE.harness.md`, `settings.harness.json`, and move (or symlink policy) for `commands/`, `skills/role-command/`, `rules/` parity subset from `.claude/`.
- **FR-003:** Create `harness/skills/` (or document `.agents` → `harness/skills` move); `full` mode links `.agents` → `harness/skills`; `alongside` mode **не** symlink `.agents` unless `--with-skills`.
- **FR-004:** Extend `bin/hub-link` with `--mode alongside|full` (default `alongside`); `alongside` never replaces existing regular files (fail-closed on conflict except idempotent refresh of installer-owned stubs).
- **FR-005:** `alongside` creates: `harness/` symlink; `CLAUDE.harness.md` symlink; patch/append marker block in existing `CLAUDE.md` or create minimal `CLAUDE.md` only if missing; `.cursor/rules.d/dev-hub-harness-router.mdc` from template; `.dev-hub` pointer; optional `AGENTS.md` stub if missing.
- **FR-006:** `alongside` settings: if `.claude/settings.json` exists → `python3 -m loop.hub_settings_merge` (new module) merges `hooks` from `harness/claude/settings.harness.json`; else symlink/copy harness settings.
- **FR-007:** `full` mode preserves current hub-link behavior (symlink `.cursor/rules`, `CLAUDE.md`, `.claude/*` shells) for dev-hub dogfood; document in `harness/README.md`.
- **FR-008:** Extend `bin/hub-unlink` with `--mode alongside|full`; `alongside` removes installer artifacts only (marker block strip, stub, harness symlink, merged hooks rollback if snapshot exists).
- **FR-009:** Update internal `@.cursor/rules/**` cross-refs in harness copy to use `harness/cursor/rules/...` paths where needed OR keep `@.cursor/rules/...` via symlink chain (prefer symlink so refs unchanged).
- **FR-010:** pytest suite `loop/tests/test_hub_link_alongside.py` covering US-001, US-003, US-005, US-006; extend `test_hub_link_harness.py` for `--mode=full` regression.
- **FR-011:** `loop doctor` (soft warn): detect product with legacy full symlink of `CLAUDE.md` to hub and suggest `hub-unlink` + `hub-link --mode=alongside` migration.

### Success Criteria (SC-###)

| ID | Измеримый результат | Проверка | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | `hub-link` default = alongside, zero overwrite of pre-existing user `CLAUDE.md` body | TM-001 pytest | outcome |
| SC-002 | dev-hub self-dogfood `full` mode unchanged for hooks path resolution | TM-003 pytest | outcome |
| SC-003 | Workflow rules SoT only under `harness/cursor/` | `test -L .cursor/rules && readlink` → harness | outcome |
| SC-004 | No silent fallback from alongside → full on error | TM-005 negative test | outcome |

### Assumptions

- Cursor загружает `.cursor/rules.d/*.mdc` (или эквивалент subdirectory) наряду с `rules/` — если нет, stub кладётся в `.cursor/rules/dev-hub-harness-router.mdc` с `alwaysApply: true` и узким триггером (document fallback in s02).
- `jq` доступен на машине operator (уже используется в hub tooling) или merge реализован на Python stdlib+json (prefer Python for portability → no jq hard dep).
- Product repo может не иметь `memory-bank/` (greenfield) — install всё равно succeeds with WARN (как сейчас).

### Clarifications

- Session: 2026-09-02 chat — additive install model agreed.
- T-HUB-041 decision «`.cursor/rules` не move» **superseded** этим эпиком для hub SoT; product install **не** symlink rules в alongside.

### [НУЖНО УТОЧНИТЬ]

- n/a (Phase 0 skipped)

---

## AC

1. `harness/cursor/rules/` и `harness/cursor/templates/` — SoT; dev-hub `.cursor/rules` → symlink на harness.
2. `bin/hub-link` default `--mode=alongside`; pre-existing `CLAUDE.md` не перезаписывается (только marker block).
3. `bin/hub-link --mode=full` сохраняет текущее поведение для dev-hub dogfood; `test_hub_link_harness.py` green.
4. Router stub opt-in: harness workflow только на role command prefixes.
5. `hub-unlink --mode=alongside` удаляет installer artifacts; user originals сохранены.
6. pytest `test_hub_link_alongside.py` green.

### AC−

1. Silent overwrite любого существующего regular file пользователя в `alongside` mode.
2. Default install остаётся full-replace (без explicit `--mode=full`).
3. Dual SoT: editable workflow rules и в `.cursor/rules` hub, и в `harness/cursor/rules` без symlink.
4. Merge settings затирает user `permissions` без `--force-merge`.
5. `hub-unlink` удаляет user-authored `CLAUDE.md` content.

---

## Техника / архитектура (HOW)

### Target layout (hub = dev-hub repo)

```text
dev-hub/
├── harness/
│   ├── README.md
│   ├── hooks/                    # T-HUB-041 ✓
│   ├── agents/                   # T-HUB-041 ✓
│   ├── instructions/             # T-HUB-041 ✓
│   ├── cursor/                   # NEW SoT
│   │   ├── rules/                # git mv from .cursor/rules
│   │   ├── templates/            # git mv from .cursor/templates
│   │   └── stubs/
│   │       └── dev-hub-harness-router.mdc
│   ├── claude/                   # NEW
│   │   ├── CLAUDE.harness.md
│   │   ├── settings.harness.json
│   │   ├── commands/
│   │   ├── skills/
│   │   └── rules/
│   └── skills/                   # NEW (.agents/skills content)
│
├── .cursor/
│   ├── rules → ../harness/cursor/rules      # symlink (hub dogfood)
│   ├── templates → ../harness/cursor/templates
│   ├── hooks/                      # Cursor-native IDE hooks (NOT harness)
│   └── schemas/
│
├── .claude/
│   ├── hooks → ../harness/hooks
│   ├── agents → ../harness/agents
│   ├── instructions → ../harness/instructions
│   ├── settings.json               # hub dogfood (full)
│   └── runtime/                    # local ephemeral
│
└── bin/
    ├── hub-link                    # --mode alongside|full
    └── hub-unlink                  # --mode alongside|full
```

### Target layout (product repo, `alongside`)

```text
my-product/
├── CLAUDE.md                       # USER file + dev-hub marker section
├── CLAUDE.harness.md → harness/claude/CLAUDE.harness.md
├── AGENTS.md                       # stub if missing (optional)
├── .dev-hub                        # path to hub
├── harness/ → $DEV_HUB/harness
│
├── .cursor/
│   ├── rules/                      # USER rules — UNTOUCHED
│   └── rules.d/
│       └── dev-hub-harness-router.mdc   # installer-owned stub
│
└── .claude/
    ├── settings.json               # USER merged (hooks added)
    ├── settings.harness.json → harness/claude/settings.harness.json  # reference
    └── runtime/                    # local
```

### Target layout (product repo, `full` — legacy / dev-hub style)

```text
my-product/
├── CLAUDE.md → $DEV_HUB/CLAUDE.md   # or hub CLAUDE that points harness
├── .cursor/rules → $DEV_HUB/harness/cursor/rules
├── .cursor/templates → $DEV_HUB/harness/cursor/templates
├── .agents → $DEV_HUB/harness/skills
├── harness/ → $DEV_HUB/harness
└── .claude/{hooks,agents,settings.json,...} → hub shells
```

### Router stub (sketch)

```markdown
---
description: "dev-hub harness opt-in router"
alwaysApply: true
---
# dev-hub harness (opt-in)

Если сообщение **не** начинается с `BACK ` / `FRONT ` / `INTEG ` / `IDEA PIPELINE` — **игнорируй** этот файл.

Иначе:
1. Read @harness/cursor/rules/mainrule.mdc
2. Follow role workflow chain from harness (not local rules)
3. Artifacts: only this repo `memory-bank/`
```

### CLAUDE.md patch contract

```markdown
<!-- dev-hub:harness:begin -->
## dev-hub harness (optional)

Workflow commands (`BACK` / `FRONT` / `INTEG`): see [CLAUDE.harness.md](./CLAUDE.harness.md).
Install: `DEV_HUB=… ./bin/hub-link . --mode=alongside`
<!-- dev-hub:harness:end -->
```

Installer: if markers exist → replace inner block only; if file missing → create with block; never delete user content outside markers.

### Settings merge (Python module)

New: `loop/hub_settings_merge.py`

| Key | Merge policy |
|-----|----------------|
| `hooks` | deep-merge by event name; harness hook commands append if not duplicate path |
| `permissions` | **preserve user**; harness permissions only if `--force-merge` |
| `$schema` | preserve user if set |

Pre-merge snapshot: `.claude/settings.json.hub-backup` (one generation) for `hub-unlink` rollback.

### Files touch matrix

| Файл | Действие |
|------|----------|
| `harness/cursor/rules/**` | git mv from `.cursor/rules` |
| `harness/cursor/templates/**` | git mv from `.cursor/templates` |
| `harness/cursor/stubs/dev-hub-harness-router.mdc` | new template |
| `harness/claude/**` | new / git mv from `.claude` subset |
| `harness/skills/**` | git mv from `.agents/skills` (or partial) |
| `harness/README.md` | install modes doc |
| `.cursor/rules`, `.cursor/templates` | symlink → harness |
| `bin/hub-link` | `--mode`, alongside logic, patch markers |
| `bin/hub-unlink` | `--mode`, marker strip, backup restore |
| `loop/hub_settings_merge.py` | new |
| `loop/tests/test_hub_link_alongside.py` | new |
| `loop/tests/test_hub_link_harness.py` | extend full mode |
| `loop/tests/test_hub_settings_merge.py` | new |
| `CLAUDE.md` (hub root) | update pointers to harness paths |
| `memory-bank/architecture/services.md` | layer diagram update |
| T-HUB-044 plan | soft: add alongside install to docs scope |

---

## Eng review spine

### Data flow (ASCII)

```text
[Operator] --> bin/hub-link --mode=alongside
                  |
                  +--> symlink harness/ --> $DEV_HUB/harness
                  |
                  +--> patch CLAUDE.md (markers only)
                  |
                  +--> write .cursor/rules.d/dev-hub-harness-router.mdc
                  |
                  +--> loop.hub_settings_merge(existing settings.json, harness/claude/settings.harness.json)
                  |
                  v
[User chat] --no role prefix--> local .cursor/rules only
[User chat] --BACK IMPLEMENT--> router --> harness/cursor/rules/mainrule.mdc --> memory-bank/
                  |
                  v
[loop.sh] --> harness/hooks/stop-gate.py (unchanged path via harness symlink)
```

### Failure matrix

| Component / link | Failure | Detection | Response | Test ID |
|------------------|---------|-----------|----------|---------|
| `hub-link` alongside + existing `.cursor/rules` symlink | would overwrite | preflight `[[ -e ]]` | skip rules link; exit 0 | TM-001 |
| `CLAUDE.md` not writable | patch fails | write error | exit 2 + message | TM-002 |
| settings merge conflict | duplicate hook same event | merge validator | exit 2; suggest `--force-merge` | TM-003 |
| broken `harness/` symlink | hooks missing | pytest resolve | fail-closed | TM-004 |
| `hub-unlink` without backup | can't restore settings | missing backup file | warn; manual fix doc | TM-005 |
| dev-hub full mode regression | `.claude/hooks` not harness | test_hub_link_harness | CI fail | TM-006 |
| marker block manually deleted | re-run link | grep markers | re-append block | TM-007 |

### Eng spine self-check

| Dimension | Score 1–5 | Gap / action |
|-----------|-----------|--------------|
| Data flow complete | 5 | — |
| Failure coverage | 4 | Cursor rules.d loading fallback → s02 spike |
| Testability | 5 | fixture-based pytest |

---

## Replacement / sunset

### A. Code / modules

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| `.cursor/rules` as writable SoT in hub | `harness/cursor/rules` + symlink | delete in-epic (mv) |
| `hub-link` implicit full replace default | `--mode=alongside` default | delete in-epic |
| `link_one ".cursor/rules"` unconditional in default path | only in `--mode=full` | delete in-epic |
| `link_one "CLAUDE.md"` unconditional | patch markers / `CLAUDE.harness.md` in alongside | delete in-epic |
| T-HUB-041 note «cursor rules stay IDE layer» | harness/cursor/ SoT | supersede in docs |

### B. Entrypoints

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| `make hub-link` without mode flag | `make hub-link MODE=alongside` (default) | document in README |
| `hub-unlink` without mode | `hub-unlink --mode=alongside` | extend |

### C. Fallbacks

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| silent skip when `CLAUDE.md` exists | fail or patch-only | fail-closed on unexpected conflict |
| auto full mode on alongside error | explicit `--mode=full` | delete in-epic |

---

<a id="qa-consumes"></a>
## QA consumes (test plan)

### Scope under test

- `bin/hub-link` / `bin/hub-unlink` modes
- `loop/hub_settings_merge.py`
- harness/cursor SoT move
- dev-hub full mode regression

### Out of scope

- Codex runtime-sync (T-HUB-043)
- `mb-load` session API (T-HUB-045)

### Test matrix

| ID | Priority | Scenario | Command / fixture | Expected | Maps FR/AC |
|----|----------|----------|-------------------|----------|------------|
| TM-001 | P0 | alongside preserves CLAUDE.md | `pytest loop/tests/test_hub_link_alongside.py::test_alongside_preserves_claude` | PASS | US-001, AC-2 |
| TM-002 | P0 | alongside existing rules untouched | same file `test_alongside_skips_cursor_rules` | PASS | AC-2 |
| TM-003 | P0 | full mode regression | `pytest loop/tests/test_hub_link_harness.py` | PASS | US-003, AC-3 |
| TM-004 | P0 | settings merge preserves permissions | `pytest loop/tests/test_hub_settings_merge.py` | PASS | US-005 |
| TM-005 | P0 | no silent full fallback | `test_alongside_fails_on_conflict` | PASS | SC-004 |
| TM-006 | P1 | unlink removes stub only | `test_alongside_unlink` | PASS | US-004 |
| TM-007 | P1 | harness cursor SoT symlink | `pytest loop/tests/test_harness_paths.py` | PASS | SC-003 |

### Regression notes

- Run hub-link tests in temp dirs only; never run alongside against dev-hub root.
- dev-hub CI uses `--mode=full` fixture explicitly.

---

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| CLARIFY / Product probe | L3 | done | §Product probe 6 rows |
| Eng review spine | L2+ | done | §Eng review spine |
| §0.11 counterparts | if external | n/a | no external APIs |
| CREATIVE | if flagged | n/a | — |
| qa_consumes draft | L2+ | done | ≥7 TM |
| Plan review batch | L2+ | done | §Plan review batch log |

**FINISH PLAN allowed:** all Required rows done.

---

## Plan review batch log

| Phase | Auto-resolved | Deferred (owner/next) | Taste / CRITICAL |
|-------|---------------|-------------------------|------------------|
| Product | default=alongside; opt-in router | — | — |
| Eng | Python merge not jq (portability) | Cursor `rules.d` vs `rules/` placement → s02 verify | — |
| Legacy | T-HUB-041 cursor decision superseded | T-HUB-044 docs | — |

---

## До DECOMPOSE (черновик нарезки)

| sNN | Slice |
|-----|-------|
| s01 | `git mv` cursor rules/templates → `harness/cursor/`; hub symlinks |
| s02 | `harness/claude/` + `harness/skills/` layout; `CLAUDE.harness.md` |
| s03 | Router stub template `harness/cursor/stubs/` |
| s04 | `hub-link --mode` parser + alongside symlink harness |
| s05 | CLAUDE.md marker patch/unpatch helpers |
| s06 | `loop/hub_settings_merge.py` + backup/restore |
| s07 | `hub-unlink --mode alongside` |
| s08 | pytest `test_hub_link_alongside.py` + settings merge tests |
| s09 | full mode regression + dev-hub README |
| s10 | legacy purge: default full-replace removed; architecture doc |

---

## Appetite

| Поле | Значение |
| :--- | :--- |
| `timebox_days` | 6 |
| `cut_list` | `['--with-skills flag', 'doctor migration warn', 'jq optional path']` |

---

## Следующий режим

→ BACK DECOMPOSE (T-HUB-046)
