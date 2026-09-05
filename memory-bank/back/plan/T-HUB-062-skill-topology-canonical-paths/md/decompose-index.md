# Реестр шагов (Decompose index)

**Plan ID:** T-HUB-062-skill-topology-canonical-paths  
**План:** [plan.md](plan.md)  
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**  
**Дата:** 2026-09-05  
**Режим:** BACK DECOMPOSE  
**Уровень:** L3  
**Granularity:** 5 sNN (band 5–8; advisory floor плана = 5; не micro-ladder)

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml` — `.cursor/templates/decompose/epic-step.yaml`.

> **Path (layout v2 HARD):** этот файл = `plan/T-HUB-062-skill-topology-canonical-paths/md/decompose-index.md`. Machine = `yaml/decompose-index.yaml`. Shards = `yaml/steps/`.  
> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `yaml/decompose-index.yaml`.** Этот файл в IMPLEMENT не грузить.  
> **status SoT = `decompose-index.yaml` only.**  
> **Ladder:** s01 add (checker) → s02 wire (FS cutover) → s03 enforce (missing = `skill_ref_missing`) → s04 enforce (no dual resolver + Kind I) → s05 purge.

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность (сессия DECOMPOSE, не `impl:`) |
| `tdd` / `python-testing-patterns` / `modern-python` / `python-anti-patterns` | Core(4) в каждом code sNN |

**Per-step:** skills gate в каждом `sNN` (`skills-gate-situational.mdc`). Session skills (`writing-plans`, `brainstorming`) **FORBIDDEN** в `impl:`.

## Requirements coverage (plan → steps)

> **HARD:** каждый AC+ / AC− / FR / NFR / US / SC → ≥1 шаг, иначе `out_of_scope` + `follow_up:` уже в `memory-bank/back/roadmap/queue.yaml`.  
> Колонка **Plan FR text** = дословно из `plan.md`. Covered row ⇒ measurable `verify` (не map-only).

| Req ID | Plan FR text (verbatim) | sNN | Notes / measurable verify |
| :--- | :--- | :--- | :--- |
| FR-001 | Канонический FS: `.agents/skills/<name>/SKILL.md` для каждого skill, на который ссылаются active `.cursor/rules/**` и `.claude/skills/**` / `harness/claude/skills/**`. | s02 | `test -f .agents/skills/writing-plans/SKILL.md`; `bin/pytest loop/tests/test_skill_literal_refs.py -q --tb=line` |
| FR-002 | Перенос из `.agents/skills/skills/<name>/` → канон (move или symlink канон→content). Nested dir не остаётся вторым SoT. | s02, s05 | s02 move/symlink; s05 leftover hash/rg |
| FR-003 | Если `.agents/skills/<name>` уже существует как другой skill — merge plan в DECOMPOSE, не overwrite молча. | s02 | cp: collision inventory; no silent overwrite |
| FR-004 | То же для `harness/skills/` если nested `skills/skills` существует (inventory на IMPLEMENT). | s02, s05 | `.agents/skills` → `harness/skills`; nested = `harness/skills/skills/` |
| FR-005 | Статический checker: парсит literal `@.agents/skills/<name>/SKILL.md` и `@.agents/skills/<name>/` из allowlisted corpora. | s01 | parser unit + collect pytest |
| FR-006 | Checker corpora: `.cursor/rules/**/*.mdc`, `.claude/skills/**/*.md`, `harness/claude/skills/**/*.md`, `harness/claude/rules/**/*.md`. Exclude: `_archive/**`, `.cursor/templates/**` (кроме если template обещает real path). | s01, s03 | allowlist/exclude tests |
| FR-007 | Missing path → fail с machine code `skill_ref_missing` + list. | s03 | fixture pytest fail + code in message |
| FR-008 | Zero missing на production corpus после эпика (`bin/pytest` named file green). | s02, s03 | corpus green after cutover |
| FR-009 | Kind I: workflow-plan.mdc и role-command SKILL продолжают писать канон `.agents/skills/<name>/SKILL.md` (не nested). | s04 | `rg` nested instruction = 0 in those files |
| FR-010 | Документировать канон одной строкой в `memory-bank/systemPatterns.md` **не** обязательно; test + tree = SoT. Optional README в `.agents/skills/README.md` если уже есть — обновить, не плодить. | s04 | README update iff exists; no new systemPatterns mandate |
| FR-011 | `bin/runtime-sync` / doctor **не** обязан чинить skills в этом эпике (это 067), но checker должен быть вызываем как pytest. | s01 | `out_of_scope` doctor + `follow_up: T-HUB-067-pack-doctor-executable-graph` |
| FR-012 | Не добавлять runtime resolver «search both paths». | s04, s05 | `rg` dual-search in `loop/` `harness/hooks/` |
| US-001 | Как parent на BACK PLAN, я хочу `Read .agents/skills/writing-plans/SKILL.md` успешен, чтобы не гадать nested path. | s02 | Path.exists writing-plans + grill-me |
| US-002 | Как CI, я хочу падение suite если workflow ссылается на несуществующий skill path. | s03 | fixture `@.agents/skills/no-such/SKILL.md` → `skill_ref_missing` |
| US-003 | Как operator, я хочу один канон, чтобы harness/claude и .agents не расходились. | s02, s05 | nested empty or symlink-only; no second hash |
| US-004 | Как pack author, я хочу templates с dummy `@` не ломали checker. | s03 | templates excluded; real workflow not in allowlist |
| SC-001 | 0 missing canonical skill refs в production corpus | s02, s03 | named pytest |
| SC-002 | `writing-plans`, `grill-me`, `python-testing-patterns` открываются по канону | s02 | Path.exists ×3 |
| SC-003 | Нет silent dual-path resolver в Python | s04 | `rg -n "skills/skills" loop/ harness/hooks/` — только sunset/tests |
| SC-004 | Fixture broken ref fails | s03 | pytest negative |
| AC+1 | Канонические skill paths существуют для всех production `@.agents/skills/<name>/SKILL.md`. | s02 | corpus pytest PASS |
| AC+2 | Named pytest checker зелёный на corpus и красный на fixture missing. | s01, s03 | red s01; green corpus + red fixture s03 |
| AC+3 | Nested `skills/skills` не является SoT (удалён или symlink-only). | s02, s05 | leftover purge |
| AC+4 | Нет Python fallback, который ищет оба пути и прячет 404. | s04, s05 | dual-resolver rg + test |
| AC−1 | Нет второго entrypoint на тот же skill name с другим содержимым. | s05 | hash compare nested vs canon |
| AC−2 | Нет soft default «если нет файла — skip skill». | s04, s05 | Kind C rg |
| AC−3 | Misconfig (ссылка на missing) → **fail test/CI**, не warning. | s03 | fixture fail-closed |
| AC−4 | Нет prod dual-path nested+canonical без follow-up в queue. | s05 | leftover = 0 or documented symlink |
| AC−5 | Нет dual machine path «resolver or literal» на одной границе. | s04 | no `resolve_skill` dual search |
| NFR-01 | Содержимое SKILL.md не переписываем «для качества» — только layout. | s02 | delta = move/symlink; no body rewrite |
| NFR-02 | Checker ходит только по **referenced** names, не по всему vendor catalog. | s01 | unit: unreferenced nested name not required |
| NFR-03 | Symlink on Windows N/A (hub = linux). | s02 | linux Path.exists follow_symlinks |
| NFR-04 | Targeted pytest = checker file; полный suite → QA. | s01–s05 | `bin/pytest loop/tests/test_skill_literal_refs.py` |
| TM-001 | corpus zero missing | s02, s03 | `bin/pytest loop/tests/test_skill_literal_refs.py -q --tb=line` |
| TM-002 | writing-plans exists | s02 | Path.exists |
| TM-003 | fixture missing fails | s03 | tmp rule missing |
| TM-004 | no dual resolver | s04 | rg loop/hooks |
| TM-005 | grill-me + python-testing-patterns exist | s02 | Path.exists ×2 |
| TM-006 | templates excluded | s03 | dummy `@` in templates not corpus fail |
| TM-007 | Symlink loop | s05 | checker exists follow_symlinks; loop → fail |
| Out of scope | MCP skill catalog UI; graphify skill nodes; rewrite skill bodies | — | Appetite `cut_list` (не epic) |
| Out of scope | `bin/runtime-sync` / doctor graph кроме skill-ref check | — | follow_up: `T-HUB-067-pack-doctor-executable-graph` (уже в queue) |
| Out of scope | video routes; T-HUB-060 REFLECT; T-HUB-048 pack registry FS | — | plan §Контекст «Не этот эпик» |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| Inventory nested vs canonical; failing checker (red) | plan §До DECOMPOSE #1 · HOW parser · FR-005/006 | s01 |
| Move/symlink skills на канон; green corpus for referenced names | plan §До DECOMPOSE #2 · FR-001–004 · US-001/003 · AC+1 | s02 |
| Negative fixture + diagnostic `skill_ref_missing` | plan §До DECOMPOSE #3 · FR-007/008 · US-002 · AC+2 · AC−3 | s03 |
| Kind I docs/refs; forbid dual resolver | plan §До DECOMPOSE #4 · FR-009/010/012 · AC+4 · AC−5 · SC-003 | s04 |
| Purge nested SoT leftover + inventory scan A+B+C+I | plan §До DECOMPOSE #5 · Replacement / sunset · AC+3 · AC−1/2/4 | s05 |
| Add → Wire → Enforce → Purge (behavior-first §3) | workflow-behavior-first | s01 add · s02 wire · s03+s04 enforce · s05 purge |
| Technology axiom: one FS layout, literal `@` exists, no nested fallback | plan §Technology axiom | s02 + s04 + s05 |
| QA consumes TM-001…006 (targeted) | plan §QA consumes | s02–s04 (QA full suite later) |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Parent `Read .agents/skills/writing-plans/SKILL.md` (и grill-me / python-testing-patterns) открывает файл, не 404 | s02 |
| Статический checker в suite: broken `@.agents/skills/…` = красный тест с `skill_ref_missing` | s01 (add red), s03 (fixture + code) |
| Один канонический layout; nested не второй SoT | s02 (cutover), s05 (purge leftover) |
| Templates dummy `@` не ломают corpus | s03 |
| Нет Python dual-path resolver / silent nested fallback | s04, s05 |
| Kind I: workflow/role-command учат канон, не `skills/skills/` | s04 |
| Doctor/MCP/graphify/skill-body rewrite | — follow_up T-HUB-067 / cut_list |
| Independent Test PASS: Read канон + corpus green + fixture red | s02 + s03 |
| Independent Test FAIL dilution: «resolver returns nested path string» без файла на каноне | s04 AC− (не done) |

## Replacement cleanup (plan → steps)

> Brownfield replace. Completeness: **add → wire → enforce → purge**. Kind A|B|C|I. Финальный `s05-legacy-fallback-purge` с `sunset_inventory` + `grep_control`.

| Устаревает (path / symbol) | Kind | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `.agents/skills/skills/<name>/` as SoT (`harness/skills/skills/<name>/SKILL.md`) | A | `.agents/skills/<name>/SKILL.md` | s02 (move), s05 (leftover) | no | after move nested empty or README-only |
| any `resolve_skill(name)` dual search (if added historically) | A | literal path only | s04, s05 | no | forbid adding; delete if found |
| n/a Python if none exists | A | keep none | s05 | no | inventory scan still required |
| compose/CLI entrypoint nested skills | B | n/a — checker pytest is greenfield | s05 | no | plan B = n/a; scan still documents n/a |
| «попробуй nested если 404» | C | raise / pytest fail | s04, s05 | yes | FORBIDDEN add |
| skip missing skill in workflow load | C | fail Read / CI | s03, s05 | yes | fail-closed |
| docs saying skills live under `skills/skills/` | I | канон `.agents/skills/<name>/` | s04, s05 | no | |
| role-command if it mentions nested | I | canonical | s04, s05 | no | |
| obsolete tests asserting nested SoT as required layout | A | rewrite to canonical | s05 | no | |

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-skill-refs-checker-red.yaml](../yaml/steps/s01-skill-refs-checker-red.yaml) | [s01](../../implement/T-HUB-062-skill-topology-canonical-paths/s01-skill-refs-checker-red.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-canonical-skill-fs-cutover.yaml](../yaml/steps/s02-canonical-skill-fs-cutover.yaml) | [s02](../../implement/T-HUB-062-skill-topology-canonical-paths/s02-canonical-skill-fs-cutover.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-skill-ref-missing-fixture.yaml](../yaml/steps/s03-skill-ref-missing-fixture.yaml) | [s03](../../implement/T-HUB-062-skill-topology-canonical-paths/s03-skill-ref-missing-fixture.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-kind-i-no-dual-resolver.yaml](../yaml/steps/s04-kind-i-no-dual-resolver.yaml) | [s04](../../implement/T-HUB-062-skill-topology-canonical-paths/s04-kind-i-no-dual-resolver.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-legacy-fallback-purge.yaml](../yaml/steps/s05-legacy-fallback-purge.yaml) | [s05](../../implement/T-HUB-062-skill-topology-canonical-paths/s05-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | completed |
**needs_creative:** все `no` (plan: CREATIVE need нет).  
**Next after DECOMPOSE:** BACK ANALYZE (FORBIDDEN ANALYZE deferred).
