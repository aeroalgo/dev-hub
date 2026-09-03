# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-059-harness-claude-agents-sot-complete  
**План:** [plan-T-HUB-059-harness-claude-agents-sot-complete.md](../plan-T-HUB-059-harness-claude-agents-sot-complete.md)  
**Machine index:** [index.yaml](index.yaml) — **канон status**  
**Дата:** 2026-09-03  
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml`.

> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `index.yaml`.** Этот файл в IMPLEMENT не грузить.
> **status SoT = `index.yaml` only.**

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность |

## Requirements coverage (plan → steps)

> **HARD:** каждый AC+ / AC− / FR / NFR → ≥1 шаг, иначе явный `out_of_scope` + `follow_up: T-…`.  
> **FR verbatim (HARD):** колонка **Plan FR text** = дословный текст / nouns из plan.

| Req ID | Plan FR text (verbatim) | sNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | `git mv .claude/commands` → `harness/claude/commands`; заменить `.claude/commands` symlink `../harness/claude/commands` | s01 | |
| FR-002 | `git mv .claude/skills` → `harness/claude/skills`; `.claude/skills` → symlink на harness | s02 | |
| FR-003 | `git mv .claude/rules` → `harness/claude/rules`; `.claude/rules` → symlink на harness | s03 | |
| FR-004 | `git mv .agents/skills` → `harness/skills`; `.agents/skills` → symlink `../harness/skills`; сохранить `.agents/.skill-lock.json` как real files в `.agents/` | s04 | |
| FR-005 | Обновить `bin/hub-link --mode=full`: link product `.claude/{commands,skills,rules}` и `.agents/skills` на **harness** SoT (`$DEV_HUB/harness/claude/…`, `$DEV_HUB/harness/skills`), не на устаревшие real-dir assumptions; refresh idempotent для installer symlinks | s05 | |
| FR-006 | `bin/hub-link --mode=alongside`: default **не** трогает `.agents` / `.claude/commands\|skills\|rules`; добавить `--with-skills` (fail-closed on conflict) создающее только installer-owned link на `harness/skills` — без overwrite user regular tree | s06 | |
| FR-007 | Расширить/добавить pytest: hub layout symlinks (commands/skills/rules + agents skills); full-mode resolve; alongside no-touch `.agents`; negative conflict `--with-skills` | s07 | |
| FR-008 | Обновить `harness/README.md`, `memory-bank/architecture/services.md` (и при необходимости AGENTS.md stub text в hub-link) — SoT paths = harness; `.claude`/`.agents/skills` = shells | s08 | |
| FR-009 | Kind I: grep/docs/tests, требующие real `.claude/commands` или `.agents/skills` как SoT — rewrite на harness paths (кроме исторических archive/memory-bank prose вне runtime) | s08, s09 | s08 docs; s09 purge leftover |
| FR-010 | Финальный purge: нет dual writable SoT; obsolete tests на «`.agents` must be real dir SoT» — delete/rewrite; `test_hub_link_harness.py` / path tests green | s09 | |
| US-001 | IDE shell `.claude/*` — symlink; `readlink -f` → `…/harness/claude/{commands,skills,rules}` | s01, s02, s03 | |
| US-002 | agent skills SoT в `harness/skills/`; `.agents/skills` не второй editable | s04 | |
| US-003 | hub-link full: product shells resolves to harness | s05 | |
| US-004 | alongside без флага: user `.agents` не тронут; `--with-skills` fail-closed при conflict | s06 | |
| US-005 | layout gate: pytest FAIL если `.claude/commands` — real dir | s07 | |
| AC+ #1 | Target layout hub 046 path nodes: `harness/claude/commands\|skills\|rules` + `harness/skills` — **существуют и являются SoT** | s01, s02, s03, s04 | |
| AC+ #2 | `.claude/commands\|skills\|rules` и `.agents/skills` в hub — **symlinks** на harness | s01, s02, s03, s04 | |
| AC+ #3 | `hub-link --mode=full` линкует product на harness SoT | s05 | |
| AC+ #4 | `hub-link --mode=alongside` default не трогает user `.agents` / Claude command trees | s06 | |
| AC+ #5 | pytest layout + hub-link suites green | s07 | |
| AC+ #6 | Docs/architecture отражают harness SoT; Kind I runtime instructions rewritten | s08 | |
| AC− #1 | Real editable `.claude/commands\|skills\|rules` или `.agents/skills` в hub после эпика | s09 (purge verify) | |
| AC− #2 | Dual SoT (копии и в harness, и в `.claude`/`.agents` без symlink) | s09 (purge verify) | |
| AC− #3 | `Notes: deferred` / partial migrate skills «потом» без follow-up ID в queue | s01–s04 cp verify | |
| AC− #4 | alongside default overwrite/replace user `.agents` | s06 negative test | |
| AC− #5 | `hub-link --mode=full` продолжает считать real `.claude/commands` SoT | s05 (rg/replace verify) | |
| AC− #6 | Живые тесты, требующие real-dir SoT на старых путях | s09 (deletes + rg cp) | |
| SC-001 | Все четыре SoT path nodes из Target layout 046 существуют под harness | s01, s02, s03, s04 | |
| SC-002 | Hub shells — symlinks | s01, s02, s03, s04 | |
| SC-003 | full hub-link fixture resolves to harness | s05, s07 | |
| SC-004 | alongside default не мутирует user `.agents` | s06, s07 | |
| SC-005 | Нет dual SoT (real + harness) после эпика | s09 | |
| FR-011 | doctor legacy warn | — | follow_up: T-HUB-044 |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| git mv + symlink: claude/commands | plan §FR-001, Advisory s01 | s01 |
| git mv + symlink: claude/skills | plan §FR-002, Advisory s02 | s02 |
| git mv + symlink: claude/rules | plan §FR-003, Advisory s03 | s03 |
| git mv + symlink: agents/skills | plan §FR-004, Advisory s04 | s04 |
| hub-link full → harness SoT | plan §FR-005, Advisory s05 | s05 |
| hub-link alongside --with-skills | plan §FR-006, Advisory s06 | s06 |
| pytest layout + hub-link suites | plan §FR-007, Advisory s07 | s07 |
| docs + Kind I rewrite | plan §FR-008/009, Advisory s08 | s08 |
| legacy-fallback-purge A+B+C+I | plan §FR-010/Replacement sunset, Advisory s09 | s09 |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Hub maintainer имеет единственный SoT под `harness/claude/` — IDE shell `.claude/*` = symlink | s01, s02, s03 |
| Agent skills SoT перенесён в `harness/skills/` — `.agents/skills` = shell symlink | s04 |
| Operator hub-link full видит product resolve в harness (не устаревший real-dir) | s05, s07 |
| Alongside безопасен: user `.agents` не перезаписан без явного opt-in | s06, s07 |
| CI/layout gate FAIL при возврате real `.claude/commands` | s07 |
| Docs/architecture/instructions отражают новый harness SoT | s08 |
| Нет dual SoT и устаревших тестов после финального purge | s09 |
| Out of scope (не в этой нарезке): FR-011 doctor legacy warn | — / follow_up: T-HUB-044 |

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `.claude/commands` (real dir SoT) | A | `harness/claude/commands` + symlink | s01 (mv), s09 (purge) | no | delete in-epic |
| `.claude/skills` (real dir SoT) | A | `harness/claude/skills` + symlink | s02 (mv), s09 (purge) | no | delete in-epic |
| `.claude/rules` (real dir SoT) | A | `harness/claude/rules` + symlink | s03 (mv), s09 (purge) | no | delete in-epic |
| `.agents/skills` (real dir SoT) | A | `harness/skills` + symlink | s04 (mv), s09 (purge) | no | delete in-epic |
| tests asserting `.agents`/`.claude/commands` must be real SoT dirs | A | rewrite to symlink+harness resolve | s09 | no | delete/rewrite in-epic |
| `hub-link --mode=full` `link_one ".agents" …` SoT assumption | B | `.agents/skills` → harness/skills | s05, s09 | no | delete in-epic |
| `hub-link --mode=full` product links to hub real `.claude/commands` | B | links to `$DEV_HUB/harness/claude/commands` | s05, s09 | no | delete in-epic |
| Makefile/docs implying `.agents` tree SoT | B | harness/skills wording | s08, s09 | no | delete in-epic (docs) |
| «skills stay in .agents if mv hard» silent skip | C | fail-closed / complete mv | s04, s09 | yes | delete in-epic |
| dual keep copy in `.claude` and harness | C | sole harness + symlink | s01–s04, s09 | yes | delete in-epic |
| alongside auto full skills on conflict | C | exit 2 | s06, s09 | yes | delete in-epic |
| README/AGENTS stub «Skills: `.agents/skills`» as SoT | I | `harness/skills/*/SKILL.md` (+ shell note) | s08, s09 | no | delete in-epic |
| architecture/services.md shells omitting claude commands/rules | I | update shells table | s08 | no | delete in-epic |
| harness/README incomplete tree | I | full Target layout section | s08 | no | delete in-epic |
| test comments requiring real `.claude/commands` SoT | I | harness paths | s09 | no | delete in-epic |

## Очередь шагов (BACK)

| step_id | title & files | needs_creative | tdd | next_phase | status |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-mv-claude-commands-harness.yaml](s01-mv-claude-commands-harness.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-mv-claude-skills-harness.yaml](s02-mv-claude-skills-harness.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-mv-claude-rules-harness.yaml](s03-mv-claude-rules-harness.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-mv-agents-skills-harness.yaml](s04-mv-agents-skills-harness.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-hub-link-full-harness-sot.yaml](s05-hub-link-full-harness-sot.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-hub-link-alongside-with-skills.yaml](s06-hub-link-alongside-with-skills.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s07** | [s07-pytest-layout-hub-link-suites.yaml](s07-pytest-layout-hub-link-suites.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s08** | [s08-docs-kind-i-rewrite.yaml](s08-docs-kind-i-rewrite.yaml) | no | no | BACK IMPLEMENT | completed |
| **s09** | [s09-legacy-fallback-purge.yaml](s09-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | completed |