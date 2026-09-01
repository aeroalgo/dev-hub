# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-041-harness-canonical-extract  
**План:** [plan-T-HUB-041-harness-canonical-extract.md](../plan-T-HUB-041-harness-canonical-extract.md)  
**Machine index:** [index.yaml](index.yaml) — **канон status**  
**Дата:** 2026-09-01  
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача. Shard: `sNN-<slug>.yaml`.

> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `index.yaml`.** Этот файл в IMPLEMENT не грузить.  
> **status SoT = `index.yaml` only.**

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность |
| `python-testing-patterns` | TDD харнесс / рег-тесты |

---

## Requirements coverage (plan → steps)

> Каждый AC+ / AC− / FR / NFR → ≥1 шаг или явный out_of_scope.

| Req ID | Кратко | sNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | Create harness/ package layout | s01 | |
| FR-002 | git mv hooks/agents/instructions | s02 | |
| FR-003 | symlinks .claude/* → harness/* | s03 | |
| FR-004 | Update loop/loop.sh + context_loop imports | s04 | |
| FR-005 | bin/hub-link verify/update | s06 | |
| FR-006 | Purge .claude/hooks sys.path in loop hot path | s04, s08 | |
| FR-007 | Update architecture/services.md + systemPatterns.md SP-H05 | s07 | |
| FR-008 | pytest test_harness_paths.py symlink+import smoke | s05 | |
| AC+ #1 | harness/hooks/stop-gate.py exists; .claude/hooks is symlink | s02, s03 | |
| AC+ #2 | loop/loop.sh inserts harness/hooks on sys.path | s04 | |
| AC+ #3 | bin/hub-link product → .claude/hooks usable | s06 | |
| AC+ #4 | pytest loop/tests/ hooks subset green | s05, s08 | |
| AC+ #5 | Architecture doc row for harness layer updated | s07 | |
| AC− #1 | Duplicate writable hooks tree under .claude/hooks | s03 (symlink prevents) | |
| AC− #2 | loop imports .claude/hooks as canonical SoT | s04, s08 | |
| AC− #3 | Breaking product hub-link | s06 | |
| AC− #4 | Moving .cursor/rules into harness | — | out_of_scope по design |
| SC-001 | 0 loop hot-path imports .claude/hooks as SoT | s04, s08 | rg audit cp |
| SC-002 | hub-link product tree resolves hooks | s06 | integration test |
| SC-003 | pytest hooks/loop subset green | s05, s08 | |
| US-001 | Single canonical path for hooks | s01–s03 | |
| US-002 | loop import from harness/ | s04 | |
| US-003 | make hub-link без изменений UX | s06 | |
| US-004 | zero regression on hooks tests | s05, s08 | |
| TM-001 | symlink integrity | s03, s05 | |
| TM-002 | loop import path rg audit | s04, s08 | |
| TM-003 | hooks regression | s05, s08 | |
| TM-004 | hub-link fixture | s06 | |
| TM-005 | git mv broken imports | s02, s05 | |

---

## Stages coverage (plan/canon → steps)

> Каждый этап плана → sNN.

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| Создать harness/ layout (пустой пакет) | plan §Target layout, FR-001 | s01 |
| git mv — переместить файлы | plan FR-002, §Files touch matrix | s02 |
| Создать symlinks .claude → harness | plan FR-003, AC+ #1 | s03 |
| Purge loop/ sys.path — заменить на harness | plan FR-004, FR-006, AC+ #2 | s04 |
| TDD: test_harness_paths + loop/tests patch | plan FR-008, TM-001..005 | s05 |
| hub-link verify/fixture test | plan FR-005, AC+ #3, TM-004 | s06 |
| Docs: architecture/systemPatterns update | plan FR-007, AC+ #5 | s07 |
| Sunset inventory scan + full pytest subset | plan SC-001..003, §Replacement/sunset | s08 |

---

## Outcome map (plan → steps)

> Проблема/outcome → sNN. Не только infra-slug.

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| **US-001**: один canonical path для hooks — новый runtime не копирует .claude/ | s01, s02, s03 |
| **US-002**: loop runner не зависит от Claude layout (import harness/) | s04 |
| **US-003**: make hub-link без изменений UX для оператора | s06 |
| **US-004**: zero regression на hooks tests | s05, s08 |
| **AC+ #1**: stop-gate.py живёт в harness/; .claude/hooks — symlink | s02, s03 |
| **AC+ #2**: loop.sh inserts harness/hooks, не .claude/hooks | s04 |
| **AC+ #3**: hub-link на fixture product resolves hooks | s06 |
| **AC+ #4**: pytest green hooks/loop subset | s05, s08 |
| **AC+ #5**: architecture docs updated | s07 |
| **SC-001**: 0 hot-path .claude/hooks imports | s04, s08 |
| **Failure TM-001** (symlink broken → fail-closed) | s03, s05 |
| **Failure TM-002** (loop old path → CI fail) | s04, s08 |
| Out of scope: harness/schemas (T-HUB-042) | — / follow-up |
| Out of scope: DSH cc-hooks-bridge full verify (TM-004) | — / T-HUB-043 |
| Out of scope: .cursor/rules in harness | — / design decision |

---

## Replacement cleanup (plan → steps)

> Brownfield replace: каждая поверхность plan sunset A/B/C → ≥1 sNN с непустым deletes.

| Устаревает (path / symbol) | Kind | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `.claude/hooks/` real directory (not symlink) | A | `harness/hooks/` + symlink | s02 | no | git mv + rmdir |
| `.claude/agents/` real directory | A | `harness/agents/` + symlink | s02 | no | git mv + rmdir |
| `.claude/instructions/` real directory | A | `harness/instructions/` + symlink | s02 | no | git mv + rmdir |
| `sys.path.insert(… ".claude/hooks")` in loop/loop.sh | A | `harness/hooks` | s04, s08 | no | grep_control: rg audit |
| `sys.path.insert(… ".claude/hooks")` in loop/* (other py) | A | `harness/hooks` | s08 | no | sunset inventory scan |
| implicit `.claude/hooks` if harness missing → fallback | C | fail-closed (import error) | s08 | yes | anti-fallback rg cp |
| loop/tests .claude/hooks path refs (live runtimes) | A | harness/hooks | s05, s08 | no | |
| n/a — B entrypoints | B | — | — | — | greenfield extension (no entrypoint change) |

> **Purge-step:** s08 = `s08-legacy-fallback-purge.yaml` — финальный sunset inventory scan A+C, grep_control, полный pytest subset.

---

## Очередь шагов (BACK)

| step_id | title & files | needs_creative | tdd | next_phase | status |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-harness-layout-create.yaml](s01-harness-layout-create.yaml) — harness/ package + README | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-git-mv-hooks-agents-instructions.yaml](s02-git-mv-hooks-agents-instructions.yaml) — git mv .claude/* → harness/ | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-symlinks-claude-to-harness.yaml](s03-symlinks-claude-to-harness.yaml) — symlinks .claude/* → harness/* | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-loop-import-path-purge.yaml](s04-loop-import-path-purge.yaml) — loop/ sys.path purge → harness/ | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-test-harness-paths.yaml](s05-test-harness-paths.yaml) — test_harness_paths.py + loop/tests patch | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-hub-link-harness-compat.yaml](s06-hub-link-harness-compat.yaml) — hub-link verify + test_hub_link_harness.py | no | yes | BACK IMPLEMENT | completed |
| **s07** | [s07-architecture-docs-update.yaml](s07-architecture-docs-update.yaml) — architecture/services.md + systemPatterns SP-H05 | no | no | BACK IMPLEMENT | completed |
| **s08** | [s08-legacy-fallback-purge.yaml](s08-legacy-fallback-purge.yaml) — sunset inventory scan + full pytest subset | no | yes | BACK IMPLEMENT | completed |
**needs_creative:** все `no` — CREATIVE не требуется (plan зафиксировал: нет CR).
