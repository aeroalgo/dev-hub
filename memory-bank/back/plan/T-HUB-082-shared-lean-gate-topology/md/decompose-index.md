# Реестр шагов (Decompose index)

**Plan ID:** T-HUB-082-shared-lean-gate-topology  
**План:** [plan.md](plan.md)  
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — канон status  
**Дата:** 2026-09-08  
**Режим:** BACK DECOMPOSE  
**Уровень:** L3  
**Granularity:** 5 sNN (advisory band 5–8; equivalence corpus, shared contracts, role patches and purge remain outcome-first; no micro-ladder)

Каждый шаг — атомарная задача для одного topology outcome; shard: `yaml/steps/sNN-<slug>.yaml` по `.cursor/templates/decompose/epic-step.yaml`.

> **Layout v2:** этот файл = `plan/<plan_id>/md/decompose-index.md`; machine status = `yaml/decompose-index.yaml`; shards = `yaml/steps/`. `md/decompose-index.md` не загружается в IMPLEMENT hot path.
> **Canonical ownership:** shared lean contracts own only evidence-proven common behavior. Role patches remain explicit at the boundary where artifact path, permissions, level, or next semantics differ.
> **Ordering:** s01 equivalence corpus → s02 roadmap shared owner → s03 security shared body + role patches → s04 BACK/INTEG VAN shared contract → s05 A+B+C+I purge and regression.

## Skills в контексте

| Skill | Зачем |
|---|---|
| `writing-plans` | структура и атомарность DECOMPOSE-сессии; не входит в `impl:` |
| `tdd` · `python-testing-patterns` · `modern-python` · `python-anti-patterns` | Core(4) для corpus/regression test shard; docs-only contract shards имеют `impl: []` |

**Per-step:** каждый YAML содержит top-level `skills.code_surface` и `skills.impl`; session skill `writing-plans` не копируется в `impl:`. Ситуационные skills не нужны: scope — rule topology, instruction surfaces and corpus tests; нет FastAPI/ORM/async product surface.

## Requirements coverage (plan → steps)

> Каждая строка ниже — дословная формулировка plan FR/AC/AC−/TM либо идентифицируемый outcome. Covered row имеет measurable verify в соответствующем shard; нет deferred без follow-up.

| Req ID | Plan FR / AC text (verbatim) | sNN | Notes / measurable verify |
|---|---|---|---|
| FR-001 | one shared roadmap-merge lean contract serves BACK/FRONT/INTEG. | s02 | Shared owner exists; all three role workflows/gates point to it; checksum/owner test and active-reference `rg`. |
| FR-002 | security has shared body plus named role patches only for real deltas. | s03 | Common body is one owner; BACK/FRONT/INTEG patch markers preserve auth/SQL/deps, XSS/tokens/CSP/bundle/deps, and wire×authz×IDOR×contract. |
| FR-003 | BACK/INTEG VAN common contract is extracted only after fresh equivalence inventory; FRONT remains separate when UI semantics differ. | s01, s04 | s01 proves equivalence/delta inventory; s04 asserts BACK/INTEG shared ownership and FRONT-specific path/artifact semantics remain. |
| FR-004 | active callers use canonical path; topology test reports duplicate, missing patch and dangling old path. | s01, s05 | Corpus exercises duplicate owner, missing role patch, and dangling active reference failure diagnostics. |
| AC+ #1 | Shared update is visible to all intended callers. | s02, s03, s04 | Each shared owner is referenced by every intended role and a targeted corpus command returns all expected edges. |
| AC+ #2 | Role patch preserves artifact path/ownership/next semantics. | s03, s04 | Patch fixture checks role-specific artifact paths, owner labels, permissions/level and next transitions. |
| AC+ #3 | Recreated local copy or absent patch fails test. | s01, s05 | Negative fixture recreates duplicate local source or removes patch and expects non-zero corpus assertion. |
| AC− #1 | No symlink or local fallback copy; no mass merge of unrelated `_lean` files; no change to security permissions or VAN requirements. | s05 | A/B/C/I purge scan rejects symlink/local fallback and checks allowlist; role semantic markers remain unchanged. |
| AC− #2 | No mass merge of unrelated `_lean` files; no change to security permissions or VAN requirements. | s01, s05 | Scope inventory and out-of-scope rows constrain changed paths; regression scan detects unrelated gate churn. |
| TM-082-01 | old local link | s01, s02, s05 | Active caller scan reports old local links and shared canonical path. |
| TM-082-02 | lost role delta | s01, s03, s05 | Security patch fixture fails closed when a required role delta is absent. |
| TM-082-03 | false VAN merge | s01, s04, s05 | BACK/INTEG equivalence passes; FRONT semantic delta remains visible and separate. |
| TM-082-04 | no local fallback | s01, s05 | Local-copy/symlink/fallback scan returns zero active violations. |
| TM-082-05 | `bin/pytest -q --tb=line` | s05 | Full suite is BACK QA consume; implementation shard records targeted topology regression only. |
| NFR-01 | Shared contracts must remain fail-closed and one-owner. | s02, s03, s04, s05 | Duplicate/missing patch/dangling path are executable failures, not warnings or silent fallback. |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
|---|---|---|
| Inventory/red tests for exact duplicate, real delta and active callers | plan §Draft stages #1; FR-003/004; TM-082-01..04 | s01 |
| Extract shared roadmap-merge contract and rewire all three roles | plan §Draft stages #2; FR-001; AC+ #1 | s02 |
| Extract security common body and preserve named role patches | plan §Draft stages #3; FR-002; AC+ #2 | s03 |
| Extract only evidence-approved BACK/INTEG VAN contract; keep FRONT separate | plan §Draft stages #3; FR-003; TM-082-03 | s04 |
| Delete local copies, purge dangling/fallback/instruction surfaces and run regression scan | plan §Draft stages #4; §Replacement / sunset A+B+C+I; TM-082-04/05 | s05 |
| Behavior-first ladder: add → wire → enforce → purge | shared behavior-first §3–§4 | s01 add corpus → s02/s03/s04 wire+enforce → s05 purge |
| Preserve role artifact ownership, permissions and next semantics | plan §FR / AC+ #2; VAN/security lean gates | s03, s04, s05 |
| QA handoff for targeted topology test and full hub suite | plan §QA consumes | s05 (targeted evidence; BACK QA full suite) |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
|---|---|
| One shared roadmap-merge lean contract serves all three roles | s01, s02, s05 |
| Security common body has explicit, minimal role patches | s01, s03, s05 |
| BACK/INTEG VAN share only the proven common contract | s01, s04, s05 |
| FRONT VAN remains separate where UI semantics differ | s01, s04, s05 |
| Active callers resolve canonical shared paths without dangling old links | s01, s02, s03, s04, s05 |
| Duplicate local owner, missing patch or dangling path fails topology test | s01, s05 |
| Artifact path/ownership/next semantics survive extraction | s03, s04, s05 |
| Security permissions and VAN requirements are unchanged | s01, s03, s04, s05 |
| No symlink, fallback copy or unrelated `_lean` merge remains | s05 |
| Full hub suite | s05 → BACK QA consume |

## Replacement cleanup (plan → steps)

> Brownfield replace. Completeness ladder: **add → wire → enforce → purge**. Every A/B/C/I row has an owning step with `deletes:`; final s05 contains `sunset_inventory`/inventory evidence and executable `grep_control`. Security and VAN role semantics are not sunset; they are explicit preserved patches/ownership rows.

| Устаревает (path / symbol) | Kind | Замена | sNN (deletes) | Fallback? | Notes |
|---|:---:|---|---|:---:|---|
| Three copied `isolation_rules/_lean/roadmap-merge.mdc` owners | A | one shared roadmap-merge lean owner + canonical role references | s05 | no | s01–s04 inventory/wire only; s05 owns local-copy deletion. |
| Three copied security gate bodies | A | one shared security common body + named role patches | s05 | no | s03 wires common body/patches; s05 owns duplicated-body purge. |
| BACK/INTEG duplicated VAN gate body | A | one shared VAN common contract + explicit role metadata/patches | s05 | no | s04 wires approved parity; s05 owns duplicated-body purge. |
| Old role-local references to deleted shared source | C | canonical shared owner or explicit role patch | s05 | no | Missing/dangling source is a validation failure; no fallback path. |
| Symlink/local compatibility copy of shared gate | C | no alias; validation failure | s05 | no | Recreated local copy or symlink is a regression. |
| Old workflow/gate references to local owner | I | canonical shared path and patch instruction | s05 | no | s02–s04 wire callers; s05 owns active instruction purge. |
| Obsolete topology assertions for copied owner | A | executable shared-owner/delta/fallback corpus assertions | s05 | no | s01 defines the corpus; s05 rewrites/purges obsolete assertions. |
| Product/runtime/router/skill-selection entrypoints | B | n/a — preserve unchanged | s05 inventory | no | Explicit no-op inventory row; no product entrypoint cutover. |

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
|---|---|---|:---:|:---:|---|---|
| **s01** | [s01-topology-equivalence-corpus.yaml](../yaml/steps/s01-topology-equivalence-corpus.yaml) | [s01](../../implement/T-HUB-082-shared-lean-gate-topology/s01-topology-equivalence-corpus.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-shared-roadmap-merge-contract.yaml](../yaml/steps/s02-shared-roadmap-merge-contract.yaml) | [s02](../../implement/T-HUB-082-shared-lean-gate-topology/s02-shared-roadmap-merge-contract.yaml) | no | no (docs-only) | BACK IMPLEMENT | completed |
| **s03** | [s03-shared-security-contract.yaml](../yaml/steps/s03-shared-security-contract.yaml) | [s03](../../implement/T-HUB-082-shared-lean-gate-topology/s03-shared-security-contract.yaml) | no | no (docs-only) | BACK IMPLEMENT | completed |
| **s04** | [s04-back-integ-van-contract.yaml](../yaml/steps/s04-back-integ-van-contract.yaml) | [s04](../../implement/T-HUB-082-shared-lean-gate-topology/s04-back-integ-van-contract.yaml) | no | no (docs-only) | BACK IMPLEMENT | completed |
| **s05** | [s05-legacy-fallback-purge.yaml](../yaml/steps/s05-legacy-fallback-purge.yaml) | [s05](../../implement/T-HUB-082-shared-lean-gate-topology/s05-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | completed |
`needs_creative`: все `no`; plan не содержит open CR и не требует BACK CREATIVE.  
`TDD`: s01 и s05 держат corpus/regression test red→implementation→green внутри шага; docs-only s02–s04 не являются самостоятельным red-test ladder.  
**Next after DECOMPOSE:** BACK ANALYZE (обязателен; `ANALYZE deferred` запрещён).
