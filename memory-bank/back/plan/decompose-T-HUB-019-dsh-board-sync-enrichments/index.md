# DECOMPOSE T-HUB-019 — dsh-board-sync-enrichments

**Эпик:** T-HUB-019  
**Роль:** BACK  
**План:** [plan-T-HUB-019-dsh-board-sync-enrichments.md](../plan-T-HUB-019-dsh-board-sync-enrichments.md)  
**Дата нарезки:** 2026-08-31  
**Статус:** pending

---

## Шаги

| ID  | Файл | Заголовок | Статус |
|-----|------|-----------|--------|
| s01 | s01-description-compose-footer.yaml | description compose/split + card_model footer parser | pending |
| s02 | s02-step-shard-body-loader.yaml | step shard body loader + WorkItem shard_rel | pending |
| s03 | s03-plan-md-body-extractor.yaml | plan markdown body extractor (gate/plan backlog) | pending |
| s04 | s04-status-map-diff-wiring.yaml | status_map + diff wiring (backlog для DECOMPOSE/PLAN gates) | pending |
| s05 | s05-http-client-move.yaml | HttpHostClient move after upsert + FakeClient status | pending |
| s06 | s06-mb-bridge-card-metadata.yaml | mb-bridge card-metadata.ts + board-filter fix | pending |
| s07 | s07-integration-regression-docs.yaml | integration sync regression + docs README | pending |

---

## Requirements coverage

| FR/NFR | Шаги |
|--------|------|
| FR-001 Two-part description (body + footer delimiter) | s01 (compose/parse), s02 (step body), s03 (gate body) |
| FR-002 Gate body extractor (plan.md → Цель+Контекст+UserStories) | s03 |
| FR-003 Step body loader (shard goal/delta/files, fail-soft missing) | s02 |
| FR-004 Status mapping: in_progress/active/blocked → running | s04 |
| FR-005 Status mapping: PLAN/DECOMPOSE/CLARIFY/ANALYZE gates → backlog | s04 |
| FR-006 Status mapping: ROADMAP gate → backlog | s04 |
| FR-007 HTTP move after upsert (fail-closed on 4xx) | s05 |
| FR-008 mb-bridge board-filter: footer YAML parser (не JSON.parse) | s06 |
| NFR-001 fail-soft missing shard → diagnostic в report, не abort | s02 |
| NFR-002 fail-soft missing plan → reason_code fallback | s03 |
| NFR-003 body ≤ 4000 символов, обрезка с … | s02 |
| NFR-004 move 4xx → graceful, failed_id в report | s05 |
| NFR-005 legacy description (pure YAML без delimiter) → parse_metadata fallback | s01 |
| NFR-006 regression: сквозной тест через FakeClient | s07 |
| NFR-007 docs: footer/backlog/move-after-upsert в README | s07 |

---

## Stages coverage

Все 7 этапов плана §«До DECOMPOSE»:

| Этап плана | Шаг |
|------------|-----|
| description compose/split + card_model footer parse | s01 |
| step shard body loader + WorkItem shard_rel | s02 |
| plan markdown body extractor (gate/plan backlog) | s03 |
| status_map + diff wiring (backlog for DECOMPOSE/PLAN gates) | s04 |
| HttpHostClient move after upsert + FakeClient status | s05 |
| mb-bridge card-metadata.ts + board-filter fix | s06 |
| integration sync regression + docs README | s07 |

---

## Outcome map

| Outcome | Шаги |
|---------|------|
| `BoardTask.description` содержит читаемый markdown body + footer YAML | s01 + s02 + s03 |
| Карточки шагов в колонках running/todo (не застревают в todo при in_progress) | s04 + s05 |
| Gate DECOMPOSE/PLAN → колонка `backlog` на board | s04 + s05 |
| `filterCards` в mb-bridge не ломается на footer YAML | s06 |
| Сквозной regression suite зелёный | s07 |
| README описывает новый формат | s07 |

---

## Replacement cleanup

Brownfield — заменяются существующие реализации:

| Что заменяется | Где | Шаг | deletes |
|----------------|-----|-----|---------|
| `serialize_metadata` (pure YAML) → `compose_description` (footer) | card_model.py | s01 | обновляется внутри файла; старые тесты migrate |
| `JSON.parse(description)` → `extractMetadata` | board-filter.ts | s06 | JSON.parse строка удаляется |
| `status="todo"` hard-coded в gate_card | diff.py | s04 | заменяется `status_for_gate()` |
| `status="running" if in_progress` (неполный) в work_item_card | diff.py | s04 | заменяется `status_for_work_item()` |

Greenfield (нет заменяемого кода):
- `body_loaders.py` — новый модуль (s02, s03)
- `card-metadata.ts` — новый TS файл (s06)
- `move()` метод в HttpHostClient / FakeClient / Protocol (s05)
- Integration regression tests в test_board_sync_sync.py (s07)

---

## Зависимости между шагами

```
s01 → s02 → s03 → s07
s01 → s04
s04 → s05 → s07
s06 (независим; параллельно с s02-s05)
```

s01 должен быть первым (compose_description нужен всем).  
s02 и s03 можно реализовывать параллельно после s01.  
s06 полностью независим от Python-шагов.  
s07 последний — требует s01-s06.

## Очередь шагов

| step_id | title & files | next_phase | status |
| :--- | :--- | :--- | :--- |
| **s01** | Two-part description — compose_description + footer parse round-trip · [yaml](s01-description-compose-footer.yaml) | BACK IMPLEMENT | completed |
| **s02** | Step body: shard goal/delta/files → markdown body, WorkItem.shard_rel · [yaml](s02-step-shard-body-loader.yaml) | BACK IMPLEMENT | completed |
| **s03** | Gate body: plan.md Цель+Контекст+UserStories → backlog card body · [yaml](s03-plan-md-body-extractor.yaml) | BACK IMPLEMENT | completed |
| **s04** | Status mapping: active/blocked→running, PLAN/DECOMPOSE gates→backlog · [yaml](s04-status-map-diff-wiring.yaml) | BACK IMPLEMENT | completed |
| **s05** | HttpHostClient.move after upsert — fail-closed, FakeClient.moves log · [yaml](s05-http-client-move.yaml) | BACK IMPLEMENT | completed |
| **s06** | mb-bridge card-metadata.ts + board-filter footer YAML fix · [yaml](s06-mb-bridge-card-metadata.yaml) | BACK IMPLEMENT | completed |
| **s07** | Regression suite (FakeClient e2e) + README Board sync enrichments · [yaml](s07-integration-regression-docs.yaml) | BACK IMPLEMENT | completed |