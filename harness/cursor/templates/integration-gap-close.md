# close-YYYYMMDD-<slug>

**Дата:** YYYY-MM-DD
**Режим:** INTEG GAP CLOSE
**Статус:** blocked | pass | done
**Путь (epic):** `memory-bank/integration/gap/<epic_id>/close-YYYYMMDD-<slug>.md`
**Путь (ad-hoc):** `memory-bank/integration/gap/close-YYYYMMDD-<slug>.md`
**Implement:** [eNN shard](../../implement/<plan_id>/eNN-….yaml)
**Gap:** [gap-YYYYMMDD-….md](gap-YYYYMMDD-….md)
**Element Ref:** eNN

## Follow links

| Layer | Artifact | Decompose index | Result |
|-------|----------|-----------------|--------|
| BACK | plan-BACK-GAP-… / covered_by | `plan/<epic>/yaml/decompose-index.yaml` | N/N steps done |
| FRONT | plan-FRONT-GAP-… | `plan/<epic>/yaml/decompose-index.yaml` \| none | … |

## Gap ID checklist

| Gap ID | Plan step(s) | Index status | Code grep | Verdict |
|--------|--------------|--------------|-----------|---------|
| G-BF01 | | done/pending | ok/fail | closed/blocked |
| G-FB01 | | | | |

## Gate

- [ ] all relevant steps done
- [ ] code grep PASS
- **Verdict:** blocked | PASS → rewire

## Rewire (если PASS)

- Files changed: …
- Tests: …
- Harden: хардкод/mock из gap убран

## Handoff

- **Done:** …
- **Next:** …
- **New chat:** yes
