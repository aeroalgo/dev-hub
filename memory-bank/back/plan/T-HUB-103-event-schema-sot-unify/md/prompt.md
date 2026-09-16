## Epic

### Outcome
Канон loop-event/v2 имеет одного schema/validate owner: orphan Pydantic-копия не существует рядом с live `epic_events`, а тестовая поверхность не держит два несовместимых набора kinds.

### In
- Удаление orphan `LoopEvent` schema без prod callers
- Выравнивание kind/constants с live validate owner
- Consolidate event schema tests на один freeze-oracle path

### Out
- Offline `adapt_v1_event` / DAG migrate (другая ось)
- Смена live event semantics / writer contract
- Plan-path classifiers и roadmap merge sources

### Done when
1. `loop.schemas.event.LoopEvent` нельзя импортировать как live SoT (модуль удалён или re-export thin к epic_events без второй kind-таблицы)
2. Targeted event validate + characterization green; dual-kind drift невозможен

### Forbidden after
parallel EVENT_KINDS · schema-only model без wire к writer/reader · restore orphan ради obsolete tests

### Chat decisions
- User override: BACK PLAN REFACTOR без REPLAN; scope loop+harness leftover twins

---

## Covering

### Outcome
После cadence refactor-нарезки leftover twin/shim owners в loop/harness нельзя использовать как второй SoT; net LOC и net owners ≤ 0 при behavior freeze.

### Axes
- Event schema/validate sole owner
- Plan-path classifier + board_sync resolve helper sole owner
- Roadmap legacy source scan / .md queue map / silent broken import purge

### Invariants
- Behavior freeze (нет смены user/API семантики)
- Delete/merge только с proof (rg/import/callers)
- Production merge и test consolidate в одном эпике
- Kind I surfaces переписываются в том же эпике

### Out
- Feature/bugfix behavior change
- Full-tree unrelated packs
- Cadence REPLAN pair outcomes (отдельный gate; user forced refactor phase)

### Done when
1. Старый twin/shim нельзя без ошибки на своей оси
2. Эпик не закрывает чужую ось «заодно»

### Forbidden after
склеить оси · mega-plan · этот Covering как SoT REPLAN · читать соседние `plan/`

### Chat decisions
- Scan scope B: `loop/` + `harness/` leftover consolidation; multi-epic by meaning cluster
