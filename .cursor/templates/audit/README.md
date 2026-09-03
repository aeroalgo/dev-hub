# `epic-audit/v2`

Шаблон `.cursor/templates/audit/epic-audit.yaml` хранит результат сравнения intent из plan/spec/constitution с фактическим кодом и implement evidence. Версия v2 добавляет `findings[]`, `intent_checked` и `converged`, не ломая legacy-массивы v1.

## Changelog v1 → v2

- `schema` изменён с `epic-audit/v1` на `epic-audit/v2`.
- Добавлены `summary.findings`, `intent_checked`, `findings[]` и `converged`.
- Сохранены `implemented[]`, `not_implemented[]`, `deviations[]`, `legacy_surfaces_remaining`, `fallback_remaining`, `purge_step_present` и `blocked_reason`.
- Старые YAML без `findings` остаются читаемыми: потребители должны трактовать отсутствующий массив как пустой (`[]`), а отсутствующий `converged` — как legacy-артефакт без v2-метрики.

## Findings

Каждая запись `findings[]` содержит:

| Поле | Значение |
| --- | --- |
| `id` | стабильный идентификатор finding, например `F1` |
| `gap_type` | `missing`, `partial`, `contradicts` или `unrequested` |
| `severity` | `CRITICAL`, `HIGH`, `MEDIUM` или `LOW` |
| `source_ref` | трассировка к FR/SC/US/AC/plan/Constitution/step |
| `evidence` | наблюдаемое доказательство: файл, область или implement evidence |
| `remaining_work` | remediation или решение по review; для `unrequested` — только review/justify/remove decision |

### Gap types

- **`missing`** — требуемой работы нет в коде.
- **`partial`** — работа есть, но не полностью выполняет требование или acceptance criterion.
- **`contradicts`** — код противоречит intent или обязательному принципу Constitution.
- **`unrequested`** — код содержит работу, которой нет в spec, plan или tasks. Это finding для awareness: AUDIT не удаляет такой код автоматически.

### Severity и порядок

Finding-ы записываются в порядке `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, затем по стабильному `id`. `CRITICAL` применяется при нарушении обязательного принципа Constitution либо при `missing`/`contradicts`, блокирующем baseline-функциональность P1 user story. `P1 missing` следует помечать `CRITICAL`; missing/contradicts на core requirement обычно `HIGH`, partial вторичного требования — `MEDIUM`, мелкая partial или низкорисковая `unrequested` — `LOW`.

## Intent metrics

`intent_checked` фиксирует покрытие проверки: `fr_total`, `fr_satisfied`, `sc_checked` и `constitution_checked`. Даже при пропуске Constitution поле остаётся явным (`false`), а причина отражается в audit evidence или handoff.

`converged: true` допустим только при отсутствии actionable findings и leftover-поверхностей. При brownfield replace дополнительно: **`sunset_inventory_scan` выполнен**, все rows `result: pass`, `legacy_surfaces_remaining[]` / `fallback_remaining[]` / `instruction_remaining[]` пусты, **`sot_enforce_scan` pass** на boundary FR. При наличии хотя бы одного actionable finding или scan fail значение должно быть `false`.

## Source references

Используйте один из стабильных форматов:

- `FR-###` — functional requirement;
- `SC-###` — success criterion;
- `US#/AC#` — user story и acceptance criterion;
- `plan:<decision>` — конкретное решение из plan;
- `Constitution <principle>` — обязательный принцип Constitution;
- `step:sNN` — decompose/implement step.

Пример: `US1/AC2`, `plan: append-only tasks`, `Constitution II`, `step:s03`.

## Dual-write mapping для v1-потребителей

| `findings[].gap_type` | Legacy-массив | Правило |
| --- | --- | --- |
| `missing` | `not_implemented[]` | actionable missing work получает новый audit/decompose shard |
| `partial` | `deviations[]` | зафиксировать plan intent, actual и impact |
| `contradicts` | `deviations[]` | зафиксировать конфликт и его impact; при необходимости добавить remediation shard |
| `unrequested` | только `findings[]` | не создавать `not_implemented[]` автоматически и не удалять код |

`implemented[]` и legacy leftover-поля продолжают заполняться по прежним правилам. Mapping additive и не заменяет step_id/element_id матрицу.

## Example finding row

```yaml
findings:
  - id: F1
    gap_type: missing
    severity: HIGH
    source_ref: FR-009
    evidence: "app/tasks.py: append path has no convergence task emission"
    remaining_work: "Добавить append-only task для remediation и покрыть его smoke-проверкой"
```

Для `unrequested` `remaining_work` должен описывать review/justify/remove decision; AUDIT не выполняет автоудаление.

## Ограничения

- `unrequested` — finding only (non-delete): converge не удаляет код автоматически.
- CRITICAL findings идут первыми и требуют remediation до закрытия соответствующего эпика.
- AUDIT не запускает suite; frontend-тесты (Vitest/Playwright/npm test/e2e) неизменно запускает только parent-агент.
- Legacy `legacy_surfaces_remaining`, `fallback_remaining`, `instruction_remaining`, `purge_step_present`, **`sunset_inventory_scan`**, **`sot_enforce_scan`** сохраняются для brownfield cleanup gates. Пустой leftover без scan = audit FAIL (см. `workflow-legacy-fallback-cleanup.mdc` §4–§5).
