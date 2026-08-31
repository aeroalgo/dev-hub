# DECOMPOSE T-HUB-020 — dsh-board-epic-loop

**Эпик:** T-HUB-020  
**Роль:** BACK  
**План:** [plan-T-HUB-020-dsh-board-epic-loop.md](../plan-T-HUB-020-dsh-board-epic-loop.md)  
**Дата нарезки:** 2026-08-31  
**Статус:** pending

---

## Шаги

| ID  | Файл | Заголовок | Статус |
|-----|------|-----------|--------|
| s01 | s01-plan-next-parse-write.yaml | plan-next/v1 parser + BACK PLAN FINISH hook | pending |
| s02 | s02-epic-next-action-resolver.yaml | EpicNextAction resolver — pre-implement matrix | pending |
| s03 | s03-resolver-post-implement-override.yaml | Resolver post-implement + plan-next override validation | pending |
| s04 | s04-arm-pre-implement-orchestrator.yaml | arm_pre_implement_context + arm_epic orchestrator | pending |
| s05 | s05-card-kind-epic-stable-id.yaml | card_kind epic + stable_id + EpicCard metadata | pending |
| s06 | s06-scan-epics-sunset-step-cards.yaml | scan_epics + sync sunset step cards + archive migration | pending |
| s07 | s07-board-launch-loop-cli.yaml | board_launch arm_epic + loop.sh --epic-id CLI | pending |
| s08 | s08-mb-bridge-epic-run-roadmap-column.yaml | mb-bridge epic Run + roadmap column rank | pending |
| s09 | s09-integration-tests-docs.yaml | Integration tests + README/WORKFLOW docs | pending |

---

## Requirements coverage

| Requirement | sNN |
|-------------|-----|
| US-001 (plan-next/v1 после PLAN FINISH) | s01 |
| US-002 (resolver → DECOMPOSE) | s02 |
| US-003 (Run → arm_epic → нет step_mismatch) | s04, s07, s08, s09 |
| US-004 (12 pending → 1 epic card) | s05, s06, s09 |
| US-005 (roadmap #1 → running) | s06, s09 |
| US-006 (CLARIFY/ANALYZE arm до decompose) | s02, s04 |
| US-007 (override plan-next/v1 respected) | s01, s02 |
| US-008 (IMPLEMENT → next sNN) | s02, s04, s09 |
| FR-resolver-single-source | s02 |
| FR-arm-epic-entrypoint | s04 |
| FR-arm-pre-implement-context | s04 |
| FR-card-kind-epic | s05 |
| FR-stable-id-epic | s05 |
| FR-scan-epics | s06 |
| FR-sunset-step-cards | s06 |
| FR-board-column-roadmap-rank | s06 |
| FR-loop-cli-epic-id | s07 |
| FR-board-launch-epic-card-arm | s07 |
| FR-mb-bridge-epic-card-metadata | s08 |
| FR-board-filter-epic-run | s08 |
| FR-regression-suite | s09 |
| FR-docs-workflow-epic | s09 |
| NFR-fail-closed-override-conflict | s01, s02, s03 |
| NFR-legacy-arm-compat | s07 |
| NFR-legacy-parse-compat (StepCard/GateCard) | s05 |
| NFR-archive-step-era | s06 |
| plan-next-write hook | s01 |

---

## Stages coverage

| Этап плана | Shards |
|------------|--------|
| plan-next/v1 format + FINISH write | s01 |
| EpicNextAction resolver (pre-implement) | s02 |
| Resolver post-implement + override validation | s03 |
| arm_epic orchestrator | s04 |
| EpicCard model (card_kind, stable_id) | s05 |
| scan_epics + sync sunset + column mapping | s06 |
| board_launch + CLI (loop.sh --epic) | s07 |
| mb-bridge TS epic card + board-filter | s08 |
| Integration regression + docs | s09 |

---

## Outcome map

| Outcome | Shards |
|---------|--------|
| Одна карточка на эпик на доске | s05, s06 |
| Run → arm_epic → правильная фаза | s04, s07, s08 |
| Resolver единый источник «что дальше» | s02, s03 |
| BACK PLAN пишет plan-next/v1 | s01 |
| Sunset step projection (014 era) | s06 |
| roadmap rank → column running/backlog/todo | s06 |
| Legacy совместимость (arm decompose path) | s07 |
| E2E доказано regression suite | s09 |

---

## Replacement cleanup

Brownfield replace:

| Что заменяется | Cutover shard | deletes |
|----------------|--------------|---------|
| scan_gates._pre_gates inline логика → epic_resolver | s02 | inline pre-implement logic in scan_gates |
| sync step-card upsert pipeline → epic upsert | s06 | step upsert in sync.py |
| arm_active_context_from_decompose как единственный arm → arm_epic | s04 | нет удаления (arm_epic добавляет; legacy сохранён) |

Import audit: rg `from.*scan_gates import` и `from.*sync import` после s02 и s06 чтобы убедиться в отсутствии внешних потребителей inline логики.

---

## Порядок реализации

```
s01 (plan-next) → s02 (resolver pre) → s03 (resolver post) → s04 (arm_epic)
↓ (параллельно)
s05 (EpicCard model)
↓
s06 (scan_epics + sync)
↓
s07 (board_launch + CLI)
↓
s08 (mb-bridge TS)
↓
s09 (integration tests + docs)
```

s01 обязателен первым — s02 потребляет parse_plan_next.  
s02 и s05 можно реализовывать параллельно после s01.  
s03 после s02 (post-implement branch resolver).  
s04 после s02–s03 (orchestrator потребляет resolver + arm functions).  
s06 после s04 + s05 (scan_epics потребляет resolver и EpicCard).  
s07 после s04 + s06 (board_launch arm_epic + CLI).  
s08 после s05 (TS card-metadata для EpicCard fields).  
s09 последний — требует s01–s08.

---

## Очередь шагов

| step_id | title & files | next_phase | status |
| :--- | :--- | :--- | :--- |
| **s01** | plan-next/v1 parser + BACK PLAN FINISH hook · [yaml](s01-plan-next-parse-write.yaml) | BACK IMPLEMENT | completed |
| **s02** | EpicNextAction resolver — pre-implement matrix · [yaml](s02-epic-next-action-resolver.yaml) | BACK IMPLEMENT | completed |
| **s03** | Resolver post-implement + plan-next override validation · [yaml](s03-resolver-post-implement-override.yaml) | BACK IMPLEMENT | completed |
| **s04** | arm_pre_implement_context + arm_epic orchestrator · [yaml](s04-arm-pre-implement-orchestrator.yaml) | BACK IMPLEMENT | completed |
| **s05** | card_kind epic + stable_id + EpicCard metadata · [yaml](s05-card-kind-epic-stable-id.yaml) | BACK IMPLEMENT | completed |
| **s06** | scan_epics + sync sunset step cards + archive migration · [yaml](s06-scan-epics-sunset-step-cards.yaml) | BACK IMPLEMENT | completed |
| **s07** | board_launch arm_epic + loop.sh --epic-id CLI · [yaml](s07-board-launch-loop-cli.yaml) | BACK IMPLEMENT | completed |
| **s08** | mb-bridge epic Run + roadmap column rank · [yaml](s08-mb-bridge-epic-run-roadmap-column.yaml) | BACK IMPLEMENT | completed |
| **s09** | Integration tests + README/WORKFLOW docs · [yaml](s09-integration-tests-docs.yaml) | BACK IMPLEMENT | completed |