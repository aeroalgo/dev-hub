# [T-HUB-062 | skill-topology-canonical-paths] PLAN

**Дата:** 2026-09-05  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** active  
**Clarify:** `memory-bank/back/clarify/clarify-20260905-workflow-loop-audit.md`  
**Roadmap:** `memory-bank/back/roadmap/queue.yaml` · batch `workflow-loop-20260905`  
**Deps:** hard нет. Unlocks T-HUB-067 (doctor `@` graph). Не зависит от T-HUB-060.  
**Skills:** writing-plans · python-testing-patterns · architecture-patterns · grill-me (Phase 0 done)  
**Источник:** `memory-bank/audit/workflow-loop-20260905/index.md` P0 + `02-workflow-pack-and-rules.md` §skill topology

→ [decompose-index.md](decompose-index.md) · [decompose-index.yaml](../yaml/decompose-index.yaml) — **DECOMPOSE 2026-09-05** (5 sNN, next BACK ANALYZE)

---

## Контекст

- **req:** Каждый literal `@.agents/skills/<name>/SKILL.md` из workflow/role chain обязан резолвиться в **существующий** файл. Сейчас канон в rules — `.agents/skills/<name>/SKILL.md`, а реальные файлы лежат в `.agents/skills/skills/<name>/SKILL.md` (и зеркала harness). Главный read-contract workflow не исполняется: агент получает ошибку чтения или начинает угадывать skill.
- **gap (as-built 2026-09-05):**
  1. Workflow/skills refs: `@.agents/skills/writing-plans/SKILL.md`, `grill-me`, `python-testing-patterns`, `architecture-patterns` — пути **без** вложенного `skills/`.
  2. On-disk: `.agents/skills/skills/writing-plans/SKILL.md` (и аналоги). Корневой `.agents/skills/writing-plans/` **отсутствует** (Read в этой сессии PLAN → File does not exist).
  3. Аудит: большинство `@.agents/skills/<name>/SKILL.md` не существует.
  4. Нет CI/pytest, который падает на missing literal `@` skill path. Doctor/parity не покрывает skill graph.
  5. Nested `harness/skills/skills/*` (если есть) дублирует ту же ошибку.
- **refs:** audit `02-workflow-pack-and-rules.md` P0.2; `.cursor/rules/back_developer/workflow-plan.mdc` skills list; `.claude/skills/role-command/SKILL.md`; `.agents/skills/skills/*/SKILL.md`; T-HUB-048 pack registry (не чинит skill FS).
- **Не этот эпик:** video routes (064); pack doctor graph кроме skill-ref check (067 потребляет checker); T-HUB-060 REFLECT.

**CREATIVE need:** нет.

---

## Technology axiom (replace-not-wrap)

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Canonical skill path | `.agents/skills/<name>/SKILL.md` (один FS layout) | dual layout `skills/skills/<name>` **и** `<name>` без redirect; silent fallback «попробуй nested» |
| Workflow `@` refs | literal path exists on disk | prose «skill лежит где-то в catalog» |
| Checker | pytest/CI: parse `@` from `.cursor/rules/**` + `.claude/**` + `harness/claude/**` → Path.exists | snapshot, который игнорирует missing; exclude без allowlist |
| SoT copy | один канон; остальные — symlink или generated | две независимые копии SKILL.md с drift |

As-built nested `skills/skills/` — **sunset inventory**, не «добавим resolver который ищет в обоих».

---

## Продуктовая спека (WHAT)

Оператор и parent на любой role command получают:

1. `Read` skill path из workflow **открывает файл** (exit/tool success), без угадывания вложенного каталога.
2. Статический checker в suite: любой новый broken `@.agents/skills/…` = красный тест, не «прочитаем позже».
3. Один канонический layout. Второй путь либо symlink на первый, либо удалён.
4. Templates, которые содержат пример-пути, либо исключены allowlist-ом checker’а, либо сами валидны.

### Product probe (office-hours lite)

| # | Question | Answer / Probe | Decision / Impact on PLAN |
|---|----------|----------------|---------------------------|
| 1 | **Reframe:** | Workflow chain врёт: «прочитай skill» → 404 | Канон FS + checker, не ещё один index.md |
| 2 | **Narrowest wedge:** | Переложить/синхронизировать skills на `.agents/skills/<name>/` + тест на writing-plans/grill-me | P0 = эти два + python-testing-patterns; полный catalog в том же эпике |
| 3 | **Pre-mortem:** | Silent fallback на nested path → drift вернётся | FORBIDDEN fallback; checker fail-closed |
| 4 | **Adoption:** | Следующий BACK PLAN/DECOMPOSE просто Read-ит канон | Kind I: обновить workflow refs если меняем канон |
| 5 | **Leverage:** | Уже есть файлы в nested dir — move/symlink, не rewrite skills | Не редактировать содержимое SKILL кроме path docs |
| 6 | **Appetite:** | 2–3 дня | cut: MCP skill registry UI; graphify index skills |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как parent на BACK PLAN, я хочу `Read .agents/skills/writing-plans/SKILL.md` успешен, чтобы не гадать nested path. | P0 | Path.exists; Read не File does not exist |
| US-002 | Как CI, я хочу падение suite если workflow ссылается на несуществующий skill path. | P0 | fixture rule с `@.agents/skills/no-such/SKILL.md` → pytest fail с кодом `skill_ref_missing` |
| US-003 | Как operator, я хочу один канон, чтобы harness/claude и .agents не расходились. | P0 | `rg` nested `skills/skills/` либо 0, либо только symlink targets documented |
| US-004 | Как pack author, я хочу templates с dummy `@` не ломали checker. | P1 | allowlist templates; real workflow files не в allowlist |

#### Acceptance Scenarios — US-001

- **Given:** fresh clone / current worktree after эпика
- **When:** parent Read `.agents/skills/writing-plans/SKILL.md` и `.agents/skills/grill-me/SKILL.md`
- **Then:** оба файла существуют; frontmatter `name:` совпадает; nested dual copy не является вторым SoT

#### Acceptance Scenarios — US-002

- **Given:** test fixture directory with a `.mdc` containing `@.agents/skills/missing-skill/SKILL.md`
- **When:** `bin/pytest loop/tests/test_skill_literal_refs.py -q --tb=line`
- **Then:** fail, diagnostic `skill_ref_missing`, path listed; production rules corpus = 0 missing

#### Acceptance Scenarios — US-003

- **Given:** `.agents/skills/` listing
- **When:** `ls .agents/skills/` and `ls .agents/skills/skills/` (if any)
- **Then:** canonical names at first level; `skills/skills` empty or only README pointing to canonical; no second SKILL.md with different hash

### Functional Requirements (FR-###)

- **FR-001:** Канонический FS: `.agents/skills/<name>/SKILL.md` для каждого skill, на который ссылаются active `.cursor/rules/**` и `.claude/skills/**` / `harness/claude/skills/**`.
- **FR-002:** Перенос из `.agents/skills/skills/<name>/` → канон (move или symlink канон→content). Nested dir не остаётся вторым SoT.
- **FR-003:** Если `.agents/skills/<name>` уже существует как другой skill — merge plan в DECOMPOSE, не overwrite молча.
- **FR-004:** То же для `harness/skills/` если nested `skills/skills` существует (inventory на IMPLEMENT).
- **FR-005:** Статический checker: парсит literal `@.agents/skills/<name>/SKILL.md` и `@.agents/skills/<name>/` из allowlisted corpora.
- **FR-006:** Checker corpora: `.cursor/rules/**/*.mdc`, `.claude/skills/**/*.md`, `harness/claude/skills/**/*.md`, `harness/claude/rules/**/*.md`. Exclude: `_archive/**`, `.cursor/templates/**` (кроме если template обещает real path).
- **FR-007:** Missing path → fail с machine code `skill_ref_missing` + list.
- **FR-008:** Zero missing на production corpus после эпика (`bin/pytest` named file green).
- **FR-009:** Kind I: workflow-plan.mdc и role-command SKILL продолжают писать канон `.agents/skills/<name>/SKILL.md` (не nested).
- **FR-010:** Документировать канон одной строкой в `memory-bank/systemPatterns.md` **не** обязательно; test + tree = SoT. Optional README в `.agents/skills/README.md` если уже есть — обновить, не плодить.
- **FR-011:** `bin/runtime-sync` / doctor **не** обязан чинить skills в этом эпике (это 067), но checker должен быть вызываем как pytest.
- **FR-012:** Не добавлять runtime resolver «search both paths».

### Success Criteria (SC-###)

| ID | Измеримый результат | Проверка / источник | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | 0 missing canonical skill refs в production corpus | named pytest | outcome |
| SC-002 | `writing-plans`, `grill-me`, `python-testing-patterns` открываются по канону | Path.exists + Read | outcome |
| SC-003 | Нет silent dual-path resolver в Python | `rg -n "skills/skills" loop/ harness/hooks/` — только sunset/tests | outcome |
| SC-004 | Fixture broken ref fails | pytest negative | outcome |

### Assumptions

- Канон path = то, что уже написано в workflow (`@.agents/skills/<name>/SKILL.md`), не nested. Менять все workflow на nested = больший blast; **не** делаем.
- Содержимое SKILL.md не переписываем «для качества» — только layout.
- `_archive/` может содержать stale `@` — exclude.

### Clarifications

- Session: 2026-09-05 Phase 0 `clarify-20260905-workflow-loop-audit.md`, Grill auto_resolved.
- Решённые: T-HUB-060 не в этом батче; silent fallback FORBIDDEN.

### [НУЖНО УТОЧНИТЬ]

- нет CRITICAL.

## AC

1. Канонические skill paths существуют для всех production `@.agents/skills/<name>/SKILL.md`.
2. Named pytest checker зелёный на corpus и красный на fixture missing.
3. Nested `skills/skills` не является SoT (удалён или symlink-only).
4. Нет Python fallback, который ищет оба пути и прячет 404.

### AC− (обязательны при brownfield replace / cutover)

1. Нет второго entrypoint на тот же skill name с другим содержимым.
2. Нет soft default «если нет файла — skip skill».
3. Misconfig (ссылка на missing) → **fail test/CI**, не warning.
4. Нет prod dual-path nested+canonical без follow-up в queue.
5. Нет dual machine path «resolver or literal» на одной границе.

## Техника / архитектура (HOW)

- Стек: FS layout + pytest parser (stdlib pathlib + regex на `@.agents/skills/[-a-z0-9]+/SKILL.md`).
- Модули: новый `loop/workflow/skill_refs.py` (или `tests/architecture/check_skill_refs.py` рядом с `check_boundaries`) + `loop/tests/test_skill_literal_refs.py`.
- Не тащить graphify. Не JSON schema.
- Observability: pytest assertion message = missing list.
- Ограничение: не ходить в `.agents/` vendor skills catalog целиком для «всех skills мира» — только **referenced** names.

### Inventory (as-built sunset)

| Path | Role after |
|------|------------|
| `.agents/skills/skills/<name>/SKILL.md` | move to `.agents/skills/<name>/SKILL.md` or replace with symlink |
| `.agents/skills/<name>/SKILL.md` | canonical create |
| `harness/skills/skills/*` | same if present |
| workflow `@.agents/skills/<name>/SKILL.md` | keep literals; they start working |

## Eng review spine

### Data flow (ASCII)

```text
[workflow.mdc @skill] -> [checker parse literals] -> [Path.exists .agents/skills/<name>/SKILL.md]
         sync                 fail-closed                no nested fallback
[parent Read] ---------------> [file bytes] ------------> [skill instructions]
```

Hops: workflow → checker → FS; parent → FS. Sync. Retry: n/a. Fail-closed: missing = pytest fail / Read error (честный), не silent skip.

### Failure matrix

| Component / link | Failure | Detection | User/system response | Test ID |
|------------------|---------|-----------|----------------------|---------|
| Canonical file missing | Read 404 | checker + parent | halt PLAN skill step; CI red | TM-001 |
| Nested leftover SoT | two hashes | rg + hash compare | purge nested | TM-002 |
| Broken new `@` in rule | commit | pytest | fail PR | TM-003 |
| Template dummy `@` | false CI red | allowlist | exclude templates | TM-004 |
| Resolver dual-path added | silent 404 hide | rg skills/skills in loop/ | AC− fail | TM-005 |
| Partial move (some skills only) | mixed layout | checker still red | не FINISH | TM-006 |
| Symlink loop | Read fail | checker exists follow_symlinks | fail | TM-007 |

### Eng spine self-check

| Dimension | Score 1–5 | Gap / action |
|-----------|-----------|--------------|
| Data flow complete | 5 | FS-only |
| Failure coverage | 5 | 7 rows |
| Testability | 5 | fixture + corpus |

## Replacement / sunset (brownfield)

### A. Code / modules

| Устаревает (path / symbol) | Замена | Policy |
| :--- | :--- | :--- |
| `.agents/skills/skills/<name>/` as SoT | `.agents/skills/<name>/SKILL.md` | delete in-epic (after move) |
| any `resolve_skill(name)` dual search (if added historically) | literal path only | delete in-epic |
| n/a Python if none exists | — | keep none |

### B. Entrypoints / deploy

| Устаревает (compose service / CMD / CLI) | Замена | Policy |
| :--- | :--- | :--- |
| n/a | checker pytest | greenfield checker |

### C. Fallbacks / soft-fail

| Устаревает (pattern / default / stub) | Замена (fail-closed) | Policy |
| :--- | :--- | :--- |
| «попробуй nested если 404» | raise / pytest fail | delete in-epic (forbid adding) |
| skip missing skill in workflow load | fail Read / CI | delete in-epic |

### I. Instruction surfaces

| Устаревает (prompt / rule / finish-block / spawn text) | Замена (инструкция нового SoT) | Policy |
| :--- | :--- | :--- |
| docs saying skills live under `skills/skills/` | канон `.agents/skills/<name>/` | delete in-epic |
| role-command if it mentions nested | canonical | delete in-epic |

## QA consumes (test plan)

<a id="qa-consumes"></a>

### Scope under test

- Epic / surfaces: `.agents/skills/` layout, literal `@` parser, pytest checker
- Out of scope for QA: skill content quality; video pack; hooks

### Test matrix

| ID | Priority | Scenario | Command / fixture | Expected | Maps FR/AC |
|----|----------|----------|-------------------|----------|------------|
| TM-001 | P0 | corpus zero missing | `bin/pytest loop/tests/test_skill_literal_refs.py -q --tb=line` | PASS | AC-1, FR-008 |
| TM-002 | P0 | writing-plans exists | python Path.exists `.agents/skills/writing-plans/SKILL.md` | True | US-001 |
| TM-003 | P0 | fixture missing fails | tmp rule `@.agents/skills/nope/SKILL.md` | fail `skill_ref_missing` | US-002 |
| TM-004 | P0 | no dual resolver | `rg -n "skills/skills" loop harness/hooks --glob '*.py'` | 0 prod hits or only comments | AC− |
| TM-005 | P1 | grill-me + python-testing-patterns exist | Path.exists ×2 | True | FR-001 |
| TM-006 | P1 | templates excluded | checker on `.cursor/templates` dummy | not fail corpus | US-004 |

### Regression notes

- Не запускать полный suite как AC IMPLEMENT (QA full). Targeted = checker file.
- Symlink on Windows N/A (hub = linux).

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| CLARIFY / Product probe | L3: one of done | done | clarify-20260905 + §Product probe |
| Eng review spine | L2+ | done | §Eng review spine filled |
| §0.11 counterparts (draft) | if external refs in HOW | n/a | no storage keys |
| CREATIVE | if flagged | n/a | нет |
| qa_consumes draft | L2+ | done | ≥3 P0 TM |
| Plan review batch | L2+ | done | §Plan review batch log |

## Plan review batch log

| Phase | Auto-resolved | Deferred (owner/next) | Taste / CRITICAL surfaced |
|-------|---------------|-------------------------|---------------------------|
| Product (brainstorming) | Канон = существующий workflow path, не nested | — | — |
| Eng (architecture-patterns) | Checker в tests/architecture или loop/tests; no runtime resolver | graphify skills index → cut_list | — |

## До DECOMPOSE (черновик нарезки)

1. s01 — inventory nested vs canonical; failing checker test (red).
2. s02 — move/symlink skills на канон; green corpus for referenced names.
3. s03 — negative fixture + diagnostic code `skill_ref_missing`.
4. s04 — Kind I docs/refs; forbid dual resolver (rg + test).
5. s05 — purge nested SoT leftover + `sNN-legacy-fallback-purge`.

Advisory floor 5 sNN (L3). Не checkbox.

## Appetite

| Поле | Значение / пример | Описание |
| :--- | :--- | :--- |
| `timebox_days` | `3` | layout + checker |
| `cut_list` | `['MCP skill catalog UI', 'graphify skill nodes', 'rewrite skill bodies']` | scope cut, не меньше sNN |

## Independent Test (behavior-first)

- PASS: parent Read канон-файла возвращает skill body; pytest corpus green; fixture missing red.
- FAIL dilution: «resolver returns nested path string» без файла на каноне; «module imports».

## Следующий режим

→ BACK DECOMPOSE `T-HUB-062-skill-topology-canonical-paths` (queue[0] этого батча после merge; если queue уже содержит более ранние leftover из done-only — этот id первый **нового** batch).

**CREATIVE need:** нет.
