# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-046-harness-alongside-install  
**План:** [plan-T-HUB-046-harness-alongside-install.md](../plan-T-HUB-046-harness-alongside-install.md)  
**Machine index:** [index.yaml](index.yaml) — **канон status**  
**Дата:** 2026-09-03  
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача. Shard: `sNN-<slug>.yaml`.

> **DECOMPOSE-only.** `index.md` в IMPLEMENT не грузить. status SoT = `index.yaml`.

---

## Requirements coverage (plan → steps)

| Req ID | Кратко | sNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | git mv .cursor/rules → harness/cursor/rules; hub .cursor/rules → symlink | s01 | |
| FR-002 | harness/claude/ with CLAUDE.harness.md, settings.harness.json | s02 | commands/skills move deferred |
| FR-003 | harness/skills/ (.agents content) | s02 partial | alongside не symlink .agents без --with-skills (out_of_scope s02) |
| FR-004 | hub-link --mode alongside\|full; alongside fail-closed on conflict | s03 | |
| FR-005 | alongside creates: harness/ symlink, CLAUDE.harness.md, router stub, .dev-hub, AGENTS.md stub | s03 | CLAUDE.md patch via s04 |
| FR-006 | alongside settings merge (hub_settings_merge.py) | s05 | |
| FR-007 | full mode documented in harness/README.md | s09 | |
| FR-008 | hub-unlink --mode alongside; strips artifacts only | s06 | |
| FR-009 | harness cross-refs via symlink chain | s01 | symlink covers @.cursor/refs unchanged |
| FR-010 | pytest test_hub_link_alongside.py; extend test_hub_link_harness.py | s07 | partial stubs from s03/s04/s06 |
| FR-011 | loop doctor legacy detection | — | Out of scope: deferred follow-up |
| AC+ #1 | harness/cursor/rules/ SoT; .cursor/rules → symlink | s01 | |
| AC+ #2 | hub-link default alongside; pre-existing CLAUDE.md not overwritten | s03, s04 | |
| AC+ #3 | --mode=full preserves current dogfood behavior; test_hub_link_harness.py green | s03, s07 | |
| AC+ #4 | Router stub opt-in; harness only on role command prefixes | s02 | |
| AC+ #5 | hub-unlink alongside removes installer artifacts; originals intact | s06 | |
| AC+ #6 | test_hub_link_alongside.py green | s07 | |
| AC- #1 | No silent overwrite existing regular file in alongside | s03 | fail-closed check |
| AC- #2 | Default install not full-replace without explicit --mode=full | s08 | purge implicit default |
| AC- #3 | No dual SoT rules (harness only, .cursor/rules = symlink) | s01 | |
| AC- #4 | Merge settings preserves user permissions without --force-merge | s05 | |
| AC- #5 | hub-unlink does not delete user CLAUDE.md content | s06 | |
| SC-001 | hub-link default=alongside; zero overwrite CLAUDE.md body | s03, s04, s07 | |
| SC-002 | dev-hub full mode unchanged (hooks path resolution) | s03, s07 | |
| SC-003 | Workflow rules SoT only under harness/cursor/ | s01 | |
| SC-004 | No silent fallback alongside→full on error | s08 | |
| US-001 | alongside preserves existing CLAUDE.md | s03, s04 | |
| US-002 | opt-in activation via role command | s02 | |
| US-003 | --mode=full for dev-hub dogfood | s03 | |
| US-004 | hub-unlink alongside removes harness only | s06 | |
| US-005 | settings merge preserves permissions | s05 | |
| US-006 | CI test gate for alongside | s07 | |
| NFR (regression notes) | Tests use tmpdir; never run alongside on dev-hub root | s07, s09 | |

---

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| SoT move: rules/templates → harness/ | plan §FR-001, §Target layout hub | s01 |
| Create harness/claude/ package | plan §FR-002, §Target layout hub | s02 |
| Router stub template | plan §Router stub (sketch), §FR-005 | s02 |
| hub-link --mode flag + alongside install | plan §FR-004, §FR-005 | s03 |
| CLAUDE.md marker-block patch module | plan §CLAUDE.md patch contract, §FR-005 | s04 |
| settings.json merge module | plan §Settings merge, §FR-006 | s05 |
| hub-unlink alongside mode | plan §FR-008 | s06 |
| Test suite: TM-001…TM-007 | plan §Test matrix | s07 |
| Purge implicit full-replace default | plan §Technology axiom FORBIDDEN, AC- #2 | s08 |
| harness/README.md docs | plan §FR-007 | s09 |

---

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Non-destructive install: alongside не перезаписывает user файлы (core adoption blocker) | s03, s04, s06 |
| Single SoT для workflow rules = harness/cursor/rules/ | s01 |
| Opt-in router: harness workflow только на role command prefix | s02 |
| Settings hooks merge без потери user permissions | s05 |
| Clean uninstall: только installer artifacts удаляются | s06 |
| CI gate: alongside test suite green | s07 |
| Implicit full-replace невозможен после эпика | s08 |
| Operator onboarding: README с обоими режимами | s09 |
| FR-011 loop doctor detection | — (deferred; follow-up epic) |

---

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `.cursor/rules` real directory (hub repo) | A | symlink → harness/cursor/rules | s01 | no | git mv; symlink in same step |
| `.cursor/templates` real directory (hub repo) | A | symlink → harness/cursor/templates | s01 | no | git mv |
| `bin/hub-link` implicit full-replace default (no --mode) | B | default alongside; full only explicit | s08 | yes | Fallback: exit 2 on conflict was only guard before |
| `bin/hub-link` behavior: full-replace without flag | C | fail-closed unless --mode=full | s08 | yes | purge code path |

---

## Очередь шагов (BACK)

| step_id | title & file | needs_creative | tdd | next_phase | status |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-harness-cursor-tree-move.yaml](s01-harness-cursor-tree-move.yaml) | no | no | BACK IMPLEMENT | completed |
| **s02** | [s02-harness-claude-tree.yaml](s02-harness-claude-tree.yaml) | no | no | BACK IMPLEMENT | completed |
| **s03** | [s03-hub-link-alongside-mode.yaml](s03-hub-link-alongside-mode.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-claude-md-patch.yaml](s04-claude-md-patch.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-hub-settings-merge.yaml](s05-hub-settings-merge.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-hub-unlink-alongside.yaml](s06-hub-unlink-alongside.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s07** | [s07-hub-link-test-suite.yaml](s07-hub-link-test-suite.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s08** | [s08-legacy-hub-link-full-purge.yaml](s08-legacy-hub-link-full-purge.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s09** | [s09-harness-readme-docs.yaml](s09-harness-readme-docs.yaml) | no | no | BACK IMPLEMENT | completed |