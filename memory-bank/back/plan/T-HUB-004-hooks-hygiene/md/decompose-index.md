# [T-HUB-004 | hooks-hygiene] DECOMPOSE index

**Plan:** [plan/T-HUB-004-hooks-hygiene/md/plan.md](../plan/T-HUB-004-hooks-hygiene/md/plan.md)  
**Status canon:** index.yaml  
**Created:** 2026-08-22  

---

## Requirements coverage (plan → steps)

> **HARD:** каждый AC+ / AC− / FR / NFR → ≥1 шаг, иначе явный out_of_scope.

| Req ID | Кратко | sNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-1 | `extract_verdict("… VERDICT: PASS … VERDICT: FAIL")` → `FAIL` | s01 | last-match wins |
| FR-2 | `extract_verdict` на тексте контракта с `VERDICT: PASS` в инструкции, финал FAIL → `FAIL` | s01 | contract substring |
| FR-3 | Тесты на last-match wins; удалить/исправить тесты, закреплявшие PASS short-circuit | s01 | test_stop_gate.py |
| FR-4 | `agent-pretool` messages: `NEED_HUMAN: verify_no_verdict` only | s02 | BLOCKED → NEED_HUMAN |
| FR-5 | `spawn-hard.md` + stop-gate messaging согласованы с FR-4 | s02 | docs sync |
| FR-6 | Единый registry discovery helper для pretool/posttool/user-prompt/stop-gate | s03 | _discover_registry only |
| FR-7 | `ALIAS["explore"]="explorer"` работает в agent-pretool normalization | s04 | normalize_type |
| FR-8 | Delete 6 dead epic re-export modules; facade `epic/__init__.py` + `epic_lib` остаются | s05 | delete stubs |
| FR-9 | `agent-posttool`: no bare `except: pass` на mirror; ошибка видна | s06 | mirror errors |
| FR-10 | `save_state` / load_state: защита от lost-update (lock или atomic+retry) | s06 | spawn-state lock |
| NFR-1 | Не менять набор registered hooks в `settings.json` без нужды | all | no settings.json changes |
| NFR-2 | Не ослаблять stop-gate FINISH integrity | s02, s06 | preserve gates |
| NFR-3 | TDD обязателен для extract_verdict + alias + registry file-wins | s01, s03, s04 | red→green |
| NFR-4 | Do Not Touch: agents md overlay schema (кроме alias claim), session_resilience | all | explicit out_of_scope |
| AC+ 1 | Pytest: parametrized extract_verdict last-wins (PASS→FAIL, FAIL→PASS, BLOCKED) | s01 | test_stop_gate |
| AC+ 2 | Pytest: contract-like blob with instructional `VERDICT: PASS` substring + final FAIL → FAIL | s01 | contract test |
| AC+ 3 | `rg -n 'BLOCKED: verify_no_verdict' .claude/hooks/agent-pretool.py` → 0 | s02 | pretool cleaned |
| AC+ 4 | `rg -n 'from epic\\.(checkpoint\|context\|events\|index\|io\|state)'` → 0; файлы отсутствуют | s05 | stubs deleted |
| AC+ 5 | Registry: при process env `PROJECT_AGENT_VERIFY_MODEL_LOOP=0` и file `=1` → file wins во всех entry hooks | s03 | file-wins test |
| AC+ 6 | Alias: spawn type `explore` нормализуется к `explorer` | s04 | alias test |
| AC+ 7 | Targeted: `timeout 300s … pytest` на hooks/loop tests затронутых | s07 | suite smoke |
| AC− 1 | Не удалять `epic/core.py` / `epic_lib` facade | s05 | explicit keep |
| AC− 2 | Не менять `loop.sh` halt (003) | all | out_of_scope |
| AC− 3 | Не vendor archive / CLAUDE (002) | all | out_of_scope |
| AC− 4 | Не делать большой split monolith | all | out_of_scope |

## Stages coverage (plan/canon → steps)

> Каждый этап/фаза плана и канон-дока → sNN. Не растворять в layout.

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| s01 — extract_verdict TDD fix | plan §До DECOMPOSE | s01 |
| s02 — NEED_HUMAN messaging sweep (pretool/spawn-hard/stop) | plan §До DECOMPOSE | s02 |
| s03 — unified registry discovery | plan §До DECOMPOSE | s03 |
| s04 — ALIAS explore | plan §До DECOMPOSE | s04 |
| s05 — delete dead epic re-exports + epic_lib cleanup | plan §До DECOMPOSE | s05 |
| s06 — posttool mirror + save_state lock | plan §До DECOMPOSE | s06 |
| s07 — targeted suite + import smoke | plan §До DECOMPOSE | s07 |

## Outcome map (plan → steps)

> **HARD (BACK/FRONT):** не ужимать Goal/NFR плана до infra-slug.  
> **Map ≠ замена шагов:** каждый критичный outcome должен иметь sNN в очереди.

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Gate-агенты дают честный last-VERDICT (не false PASS от short-circuit) | s01 |
| stop/pretool говорят один язык (`NEED_HUMAN`, не BLOCKED) | s02 |
| Registry policy не зависит от порядка env vs file (file-wins везде) | s03 |
| Alias `explore` → `explorer` работает (md claim ↔ code) | s04 |
| Мёртвый код epic re-export удалён (6 файлов) | s05 |
| Mirror ошибки видимы; spawn-state не теряет update | s06 |
| Targeted suite + import smoke подтверждают hygiene | s07 |
| AC+ 1, 2 (extract_verdict last-wins + contract) | s01 |
| AC+ 3 (BLOCKED: verify_no_verdict → 0) | s02 |
| AC+ 4 (epic stubs deleted, no imports) | s05 |
| AC+ 5 (file-wins registry helper test) | s03 |
| AC+ 6 (alias explore normalizes) | s04 |
| AC+ 7 (targeted pytest) | s07 |

## Replacement cleanup (plan → steps)

> **HARD (brownfield replace):** каждая поверхность plan sunset **A/B/C** → ≥1 `sNN` с непустым `deletes:`.

| Устаревает (path / symbol) | Kind (A\|B\|C) | Замена | sNN\|eNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| PASS short-circuit в `extract_verdict` | A | last regex match | s01 | no | delete logic |
| `BLOCKED: verify_no_verdict` в pretool | A | `NEED_HUMAN: verify_no_verdict` | s02 | no | replace string |
| 6× `epic/{checkpoint,context,events,index,io,state}.py` | A | imports via `epic.core` / package | s05 | no | delete files |
| unused `_epic` import в epic_lib.py | A | — | s05 | no | delete import |
| silent `except: pass` mirror в posttool | A | log + fail-visible | s06 | no | replace except |
| dual discover_registry call styles | A | `_discover_registry` only | s03 | no | replace calls |
| n/a — нет замен | — | — | — | — | greenfield (нет) |

---

## Steps

- **s01** — extract_verdict: remove short-circuit, last-match wins, TDD tests
- **s02** — NEED_HUMAN messaging: pretool BLOCKED→NEED_HUMAN, spawn-hard sync
- **s03** — Unified registry discovery: all hooks use _discover_registry (file-wins)
- **s04** — ALIAS explore: add `ALIAS["explore"]="explorer"`, test normalization
- **s05** — Delete dead epic re-exports: rm 6 stubs, rm unused import, verify rg=0
- **s06** — Posttool mirror + save_state lock: remove bare except, add lock/atomic
- **s07** — Targeted suite + import smoke: pytest on affected + import epic after delete

## Очередь шагов

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-extract-verdict-tdd.yaml](s01-extract-verdict-tdd.yaml) | [s01…](../../implement/T-HUB-004-hooks-hygiene/yaml/steps/s01-extract-verdict-tdd.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-need-human-messaging.yaml](s02-need-human-messaging.yaml) | [s02…](../../implement/T-HUB-004-hooks-hygiene/yaml/steps/s02-need-human-messaging.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-unified-registry-discovery.yaml](s03-unified-registry-discovery.yaml) | [s03…](../../implement/T-HUB-004-hooks-hygiene/yaml/steps/s03-unified-registry-discovery.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-alias-explore.yaml](s04-alias-explore.yaml) | [s04…](../../implement/T-HUB-004-hooks-hygiene/yaml/steps/s04-alias-explore.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-delete-epic-reexports.yaml](s05-delete-epic-reexports.yaml) | [s05…](../../implement/T-HUB-004-hooks-hygiene/yaml/steps/s05-delete-epic-reexports.yaml) | no | no | BACK IMPLEMENT | completed |
| **s06** | [s06-posttool-mirror-lock.yaml](s06-posttool-mirror-lock.yaml) | [s06…](../../implement/T-HUB-004-hooks-hygiene/yaml/steps/s06-posttool-mirror-lock.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s07** | [s07-targeted-suite-smoke.yaml](s07-targeted-suite-smoke.yaml) | [s07…](../../implement/T-HUB-004-hooks-hygiene/yaml/steps/s07-targeted-suite-smoke.yaml) | no | no | BACK IMPLEMENT | completed |
**needs_creative:** `no` | `yes (CR-…)` | `yes (CR-…) ✅` (= shard `yes (CR-…) — **closed**`)  
**FORBIDDEN:** `yes (done)` без CR-ID · `no (CR-… closed)`
