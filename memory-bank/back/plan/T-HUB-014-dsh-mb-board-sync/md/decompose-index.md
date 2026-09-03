# Реестр шагов (Decompose index) — T-HUB-014

**Plan ID:** T-HUB-014-dsh-mb-board-sync  
**План:** [plan/T-HUB-014-dsh-mb-board-sync/md/plan.md](../plan/T-HUB-014-dsh-mb-board-sync/md/plan.md)  
**Machine index:** [index.yaml](index.yaml) — **канон status**  
**Дата:** 2026-08-28  
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml`.

> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `index.yaml`.** Этот файл в IMPLEMENT не грузить.
> **status SoT = `index.yaml` only.**

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность |
| `brainstorming` | batch-решения уже закрыты в PLAN |

**Per-step:** BACK — skills gate в каждом `sNN` (см. `workflow-decompose.mdc`).

---

## Requirements coverage (plan → steps)

> **HARD:** каждый AC+ / AC− / FR / NFR (или их явный out_of_scope) → ≥1 шаг.

| Req ID | Кратко | sNN | Notes |
| :--- | :--- | :--- | :--- |
| AC+ #1 | Unit: parse workspace.json → WorkspaceRef[] | s02 | |
| AC+ #2 | Unit: scan fixture MB → WorkItems pending/in_progress only | s03 | |
| AC+ #3 | Unit: desired set diff → create/update/archive ops | s05 | |
| AC+ #4 | Unit: FakeClient sync → snapshot has expected mb-* ids | s05 | |
| AC+ #5 | Unit: non-mb task preserved | s05 | |
| AC+ #6 | Unit: dry-run emits ops, FakeClient.write_count==0 | s07 | |
| AC+ #7 | Unit: metadata parse/serialize round-trip (card_kind step + gate) | s01 | |
| AC+ #8 | Unit: gate ANALYZE emitted when decompose exists, 0 completed, no analyze artifact | s04 | |
| AC+ #9 | Unit: post-implement gate uses reduce_epic_lifecycle (mock) — AUDIT before QA | s04 | |
| AC+ #10 | Docs: README explains step vs gate + search by epic_id | s08 | |
| AC+ #11 | CLI --help lists sync/status | s07 | |
| AC− #1 | Не делать board SoT статусов шагов | s03, s05 | guard в doc + no write-back |
| AC− #2 | Не сканировать весь диск / не auto-add workspaces | s02 | only workspace.json |
| AC− #3 | Не удалять non-mb-* cards | s05 | filter by prefix |
| AC− #4 | Не вызывать arm/loop/roadmap-advance | s04, s05 | out_of_scope 015 |
| AC− #5 | Не интегрировать Jira | — | out_of_scope permanently |
| AC− #6 | Не патчить @linxin666 upstream source | s06 | consume API only |
| AC− #7 | Не silent fallback на Claude/agent run | s06 | fail-closed |
| FR-001 | Discover workspaces из workspace.json (--dsh-home override) | s02 | |
| FR-002 | Eligible = path exists ∧ memory-bank/ is dir | s02 | |
| FR-003 | Scan decompose indexes → emit WorkItem[] | s03 | |
| FR-004 | Optional ROADMAP tip card (select_next_epic thin wrapper) | s04 | |
| FR-005 | Upsert board cards by stable id; update title/desc/prompt/status | s05 | |
| FR-006 | Archive mb-cards чьи WorkItems исчезли из desired set | s05 | |
| FR-007 | CLI: sync / sync --dry-run / sync --workspace-id / status | s07 | |
| FR-008 | Machine metadata block mb-board-card/v1 в description; parser round-trip | s01 | |
| FR-009 | TaskBoardClient protocol + FakeClient + HttpHostClient + optional LedgerFileClient | s05, s06 | |
| FR-010 | Sync generation counter; идемпотентность (no-op при unchanged) | s05 | |
| FR-011 | Docs README dsh/ секция | s08 | |
| FR-012 | card_kind step/gate в metadata; парсер round-trip | s01 | |
| FR-013 | Gate emission: scan_gates.py reusing reduce_epic_lifecycle | s04 | |
| FR-014 | Pre-implement gate ANALYZE (0 completed + no analyze / critical>0) | s04 | |
| FR-015 | Pre-implement gate CLARIFY (план с КРИТИЧЕСКИМ НУЖНО УТОЧНИТЬ) | s04 | |
| FR-016 | Pre-implement tips PLAN / DECOMPOSE / ROADMAP | s04 | |
| FR-017 | Post-implement gate (queue empty + lifecycle phase) / DONE → archive all | s04 | |
| FR-018 | Prompt builder: gate → ROLE gate_phase epic_id; step → ROLE IMPLEMENT | s01 | |
| SC-001 | N pending cards == N pending steps (fixture) | s03, s05 | |
| SC-002 | Non-mb cards count unchanged | s05 | |
| SC-003 | Dry-run exit 0 + zero ledger writes | s07 | |
| SC-004 | Corrupt workspace.json → exit≠0 + diagnostic | s02 | |
| SC-005 | All sNN completed + lifecycle QA → exactly 1 gate-QA card | s04, s05 | |
| SC-006 | Pending sNN present → no post-implement gate same epic | s04 | |
| NFR: fail-closed | non-2xx / lock conflict → non-zero + diagnostic | s06 | |
| NFR: idempotent sync | повторный sync без изменений → no-op | s05 | |
| NFR: batch skip | corrupt index.yaml одного проекта → skip project + error list | s03 | |
| NFR: stable id | id scheme mb-{ws}-{role}-{epic}-{step/gate} + sha256 fallback | s01 | |
| NFR: one-way | memory-bank → board only; правки на mb-* карточках перезаписываются | s05 | |
| US-001 | pending sNN → mb-* card с workspaceId | s02, s03, s05 | |
| US-002 | completed step → archived card | s05 | |
| US-003 | --dry-run без записи | s07 | |
| US-004 | non-mb cards не тронуты | s05 | |
| US-005 | all sNN completed → gate QA на board | s04, s05 | |
| US-006 | filter by epic_id via title/metadata | s01 | |

---

## Stages coverage (plan/canon → steps)

> Каждый модульный этап плана (§Модули target layout) → sNN. Не растворять в layout.

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| card_model.py — stable id + metadata v1 + title/prompt builders | plan §Модули + §Card identity | s01 |
| workspaces.py — discover + eligible filter | plan §Модули + FR-001/002 + SC-004 | s02 |
| scan_mb.py — step WorkItems из decompose index.yaml | plan §Модули + FR-003 + SC-001 | s03 |
| scan_gates.py — gate WorkItems (pre/post-implement) + reduce_epic_lifecycle | plan §Модули + FR-013…017 + SC-005/006 | s04 |
| diff.py + sync.py + FakeClient — desired set diff + orchestrate | plan §Модули + FR-005/006/009/010 | s05 |
| client.py HttpHostClient + fail-closed | plan §Модули + HTTP notes + AC− #6/7 | s06 |
| cli.py + bin/hub-board + dry-run/status | plan §Модули + FR-007 + AC+ #11 | s07 |
| dsh/README.md + regression polish | FR-011 + AC+ #10 + test suite polish | s08 |

---

## Outcome map (plan → steps)

> Четыре–двенадцать строк: зачем эпик / user|system outcome → какие sNN закрывают.

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Разработчик видит pending/in_progress sNN любого DSH workspace на Task Board без ручного открытия index.yaml | s01, s02, s03, s05 |
| Completed шаги уходят с активной доски (archive); доска не засоряется | s05 |
| Post-implement фаза (AUDIT/QA/BUGFIX/REFLECT) видна как gate-карточка, когда implement queue пуста | s04, s05 |
| Pre-implement сигналы (PLAN/DECOMPOSE/ANALYZE/CLARIFY) помогают найти следующее действие без loop консоли | s04 |
| Dry-run позволяет проверить mapping до записи; idempotent повтор не создаёт дублей | s05, s07 |
| Ручные (non-mb-*) карточки не затрагиваются синхронизацией | s05 |
| HTTP Host client с fail-closed поведением на ошибках DSH API | s06 |
| CLI hub-board доступна как standalone команда (cron / manual / make) | s07 |
| Документация объясняет step vs gate + поиск по epic_id | s08 |
| Out of scope (arm/loop via board → T-HUB-015) | — / T-HUB-015 |
| Out of scope (Cordis TS companion для UI buttons → T-HUB-015) | — / T-HUB-015 |

---

## Replacement cleanup (plan → steps)

> Greenfield новый пакет `loop/board_sync/` — нет замен существующих поверхностей.

| Устаревает (path / symbol) | Kind | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| n/a — нет замен | — | — | — | — | greenfield пакет loop/board_sync/ |

---

## Очередь шагов (BACK)

| step_id | title & files | needs_creative | tdd | next_phase | status |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-card-model-metadata-stable-id.yaml](s01-card-model-metadata-stable-id.yaml) `loop/board_sync/card_model.py` + test | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-workspaces-discover-eligible-filter.yaml](s02-workspaces-discover-eligible-filter.yaml) `loop/board_sync/workspaces.py` + test | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-scan-mb-step-workitems-from-index-yaml.yaml](s03-scan-mb-step-workitems-from-index-yaml.yaml) `loop/board_sync/scan_mb.py` + test | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-scan-gates-clarify-analyze-tips-lifecycle.yaml](s04-scan-gates-clarify-analyze-tips-lifecycle.yaml) `loop/board_sync/scan_gates.py` + test | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-diff-orchestrator-fake-client-sync.yaml](s05-diff-orchestrator-fake-client-sync.yaml) `loop/board_sync/diff.py` + `sync.py` + `client.py` (Fake) + test | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-http-host-client-fail-closed.yaml](s06-http-host-client-fail-closed.yaml) `loop/board_sync/client.py` HttpHostClient + integration test | no | yes | BACK IMPLEMENT | completed |
| **s07** | [s07-cli-hub-board-dry-run-status.yaml](s07-cli-hub-board-dry-run-status.yaml) `loop/board_sync/cli.py` + `bin/hub-board` + test | no | yes | BACK IMPLEMENT | completed |
| **s08** | [s08-docs-readme-regression-polish.yaml](s08-docs-readme-regression-polish.yaml) `dsh/README.md` + test polish | no | no | BACK IMPLEMENT | completed |
| **s09** | [s09-audit-archive-all.yaml](s09-audit-archive-all.yaml) `loop/board_sync/` DONE lifecycle archive-all remediation (FR-017) | no | yes | BACK IMPLEMENT | completed |
| **s10** | [s10-audit-idempotent-generation.yaml](s10-audit-idempotent-generation.yaml) generation-only update suppression (FR-010) | no | yes | BACK IMPLEMENT | completed |
| **s11** | [s11-audit-roadmap-error-diagnostics.yaml](s11-audit-roadmap-error-diagnostics.yaml) roadmap selector diagnostics (FR-004, MUST-2/5/6) | no | yes | BACK IMPLEMENT | completed |
**needs_creative:** все `no` — никаких открытых CR (CREATIVE не требуется).

## Audit remediation coverage

| Finding | Source refs | Remediation step |
| :--- | :--- | :--- |
| F1 | FR-017 | s09 |
| F2 | FR-010 / NFR: idempotent sync | s10 |
| F3 | FR-004 / FR-016 / Constitution MUST-2/5/6 | s11 |

**Audit rule:** s09–s11 are append-only remediation shards from `audit-20260828-dsh-mb-board-sync.yaml`; they remain `pending` until BACK IMPLEMENT and a repeat BACK AUDIT.
