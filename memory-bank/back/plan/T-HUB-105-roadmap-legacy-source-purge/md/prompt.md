## Epic

### Outcome
Canon roadmap queue имеет один live discovery/path-map owner: legacy scan `plan/roadmap-*-epics.queue.yaml` и `.md→.queue.yaml` map не маскируют SoT; silent `loop.epic_paths` import в orchestrator не глотает ошибку.

### In
- Purge dead live plan-dir source discovery (archive-only leftovers)
- Narrow or delete legacy `.md` roadmap path mapping with proof
- Fix orchestrator `epic_dir` import to canonical owner; remove silent swallow on that path

### Out
- Event schema
- Plan-path classifiers / board_sync helper extract
- Смена merge semantics для `roadmap/batches/*.yaml` (если ещё live)

### Done when
1. Live merge не сканирует `plan/roadmap-*-epics.queue.yaml`; `.md` map не является live SoT без ошибки или удалён
2. Orchestrator trace/tier1 path импортирует существующий `epic_dir` owner; ImportError не silent-pass

### Forbidden after
restore plan-dir slug-queue scan · silent `except: pass` вокруг broken import · dual queue SoT

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
