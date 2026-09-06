# [T-HUB-070 | phase-policy-overlay-sole-sot] PLAN

**Дата:** 2026-09-06  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** active  
**Clarify:** `memory-bank/back/clarify/clarify-20260906-loop-session-architecture.md`  
**Roadmap:** `memory-bank/back/roadmap/queue.yaml` · batch `loop-session-architecture-20260906`  
**Deps:** нет hard. Soft T-HUB-060 (REFLECT удалён из lifecycle, overlay ещё учит REFLECT). Soft T-HUB-065 (duplicate hooks — другой leftover). Soft spawn-hard / `phase_registry.yaml` (уже называют `verify-decompose` / QA без REFLECT).  
**Skills:** writing-plans · python-testing-patterns · architecture-patterns  
**Источник:** `memory-bank/audit/loop-session-architecture-20260905.md` Variant A P0.1+P0.5; `claude-sessions-20260905-last15.md` §6; as-built `harness/hooks/user-prompt.py`

→ [decompose-index.md](decompose-index.md) · [decompose-index.yaml](../yaml/decompose-index.yaml) — status SoT = yaml; index = sole tracker (не дублировать чеклист шагов здесь).

---

## Контекст

- **req:** Единственный machine SoT фазы и spawn-gates = `loop/schemas/phase_registry.yaml` (`phase-registry/v1`) через `gates_from_phase` / `get_verify_agent`. UserPromptSubmit overlay **не** имеет права:
  1. писать `QA FINISH → REFLECT`;
  2. при `armed_step=DECOMPOSE` выключать `need_verify` / писать `promote DECOMPOSE→IMPLEMENT`;
  3. выбирать mode regex’ом по user prompt, когда projection/state armed.
- **gap (as-built 2026-09-06):**
  1. `harness/hooks/user-prompt.py` L149–157: при `FINISH_RE` + `mode==qa` inject `Handoff → REFLECT`. T-HUB-060 удалил REFLECT из POST_IMPLEMENT (`IMPLEMENT → AUDIT → QA → DONE`).
  2. Тот же файл L159–172: **после** `projection_authoritative` блока, если `armed_step==DECOMPOSE`, принудительно `need_verify=False`, `need_reviewer=False`, текст `verify/reviewer OFF (docs-only)` + `promote DECOMPOSE→IMPLEMENT на prepare`. Registry: `DECOMPOSE.verify_agent: verify-decompose`. Workflow-decompose 7a: next = ANALYZE only.
  3. Regex fallback (`QA_RE` / `IMPL_RE` / `BUGFIX_RE` / `FINISH_RE`) остаётся, когда projection нет — допустим только как **миграционный** слой с drift counter, не как SoT при armed state.
  4. Spawn-hard и loop DECOMPOSE prompt требуют `@verify-decompose` PASS; overlay это отменяет → stop-gate ложный green docs-only FINISH.
- **refs:** `harness/hooks/user-prompt.py`; `loop/schemas/phase_registry.yaml`; `loop/epic_transition.py` `gates_from_phase`; `.claude/instructions/spawn-hard.md`; T-HUB-060 plan; architecture §1.2 D, §2.4, §8 DECOMPOSE/QA; session audit §6.
- **Не этот эпик:** identity COMMAND lock (071); inline plan / `ok=true` (072); 401 classifier (073); finish_qa re-QA yaml (074, но 074 **hard-deps** этот эпик); duplicate realpath hooks (065); sunset registry (063); fence ownership (066).

**CREATIVE need:** нет.

---

## Technology axiom (replace-not-wrap)

> **HARD.** As-built overlay prose читается как **sunset (что удалить)**, не как шаблон нового поведения.

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Phase gates | `gates_from_phase(phase)` из `phase_registry.yaml` | hardcoded `need_verify=False` для DECOMPOSE в overlay |
| QA next | registry + `finish_qa` next BUGFIX/DONE | overlay строка `→ REFLECT` |
| DECOMPOSE verify | `verify_agent: verify-decompose` → `need_verify` **true** если registry так говорит (или отдельное поле finish_gates; **сейчас** finish_gates_dict.need_verify=false **и** verify_agent set — **этот эпик обязан согласовать**: overlay не OFF, stop-gate смотрит registry verify_agent **или** finish_gates синхронизированы с verify_agent) | «docs-only OFF» override |
| Mode when armed | `state.armed_step` / `projection.phase` | `QA_RE.search(prompt)` перекрывает armed |
| Overlay text | generated from registry fields **or** deleted | второй командный канал прозой |

**Согласование registry (обязательное решение этого плана):**  
Сейчас DECOMPOSE имеет `verify_agent: verify-decompose` **и** `finish_gates_dict.need_verify: false`. Это внутренняя дыра registry, которую overlay эксплуатирует. **Axiom:** если `verify_agent` не null → overlay **не** имеет права ставить `need_verify=False`. Stop-gate / spawn-state для DECOMPOSE = ON для `verify-decompose`. Если `finish_gates_dict.need_verify` остаётся false, его **надо выровнять** в этом эпике (`need_verify: true` для DECOMPOSE) **или** stop-gate читать `verify_agent`, не только spawn `need_verify`. Выбранный wedge: **выровнять `finish_gates_dict.need_verify: true` для DECOMPOSE** + удалить overlay override. Не оставлять два поля, которые врут друг другу.

---

## Продуктовая спека (WHAT)

1. После эпика UserPromptSubmit **не содержит** подстроки `REFLECT` как next после QA FINISH.
2. При `armed_step=DECOMPOSE` spawn-gate `need_verify=true` (verify-decompose), `need_reviewer=false`; additionalContext **не** говорит verify OFF и **не** говорит promote IMPLEMENT.
3. `phase_registry.yaml` DECOMPOSE: `finish_gates` / `finish_gates_dict.need_verify` согласованы с `verify_agent: verify-decompose` (true).
4. Когда `projection.phase` или `state.armed_step` заданы — regex по prompt **не** меняет `st["mode"]` / gates (уже частично так для projection; DECOMPOSE override — удалить).
5. Kind I: spawn-hard, workflow-qa, любые hook comments — QA next ≠ REFLECT; DECOMPOSE verify ON.
6. Тесты: fixture armed DECOMPOSE → need_verify true; fixture QA FINISH prompt → context без REFLECT; registry load DECOMPOSE need_verify true.

### Product probe

| # | Question | Answer / Probe | Decision / Impact on PLAN |
|---|----------|----------------|---------------------------|
| 1 | **Reframe** | Overlay врёт фазу громче registry | Delete overlay policy; registry wins |
| 2 | **Narrowest wedge** | Удалить L156 REFLECT + L164–172 DECOMPOSE block + align registry need_verify | P0 |
| 3 | **Pre-mortem** | Выровняют registry, overlay override останется | FR: overlay block **удалён**, не «if registry» |
| 4 | **Adoption** | Все loop UserPromptSubmit | Kind I spawn-hard already ON — overlay was the liar |
| 5 | **Leverage** | `gates_from_phase` уже вызывается при projection | Не новый YAML DSL |
| 6 | **Appetite** | 3 дня | cut: generate overlay text from AST; Event projector |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как DECOMPOSE-агент, я хочу spawn-gate требовать `@verify-decompose`, а не OFF. | P0 | unit: armed_step=DECOMPOSE → `need_verify is True`; context не содержит `verify/reviewer OFF` |
| US-002 | Как QA-агент, я не вижу «FINISH → REFLECT» после T-HUB-060. | P0 | unit: QA FINISH prompt → additionalContext не содержит `REFLECT` |
| US-003 | Как operator, я не хочу overlay promote DECOMPOSE→IMPLEMENT. | P0 | context не содержит `promote DECOMPOSE→IMPLEMENT`; registry/promotable не читается overlay’ем как IMPLEMENT |
| US-004 | Как CI, я хочу registry DECOMPOSE.need_verify == bool(verify_agent). | P0 | pytest load_phase_registry: DECOMPOSE finish_gates_dict.need_verify is True |
| US-005 | Как loop, при armed projection regex не перебивает mode. | P1 | armed BUGFIX + prompt «BACK QA» → mode/gates from projection (071 расширит identity halt; здесь — overlay не QA-ит) |

#### Acceptance Scenarios — US-001

- **Given:** epic loop env, `load_epic_state` armed_step=`DECOMPOSE`, projection.phase=`DECOMPOSE`
- **When:** `user-prompt.main()` with prompt `BACK DECOMPOSE`
- **Then:** `st["need_verify"] is True`; `st["need_reviewer"] is False`; additionalContext **не** match `verify/reviewer OFF`; **не** match `promote DECOMPOSE→IMPLEMENT`

#### Acceptance Scenarios — US-002

- **Given:** `st["mode"]=="qa"` after projection or regex, prompt contains FINISH
- **When:** UserPromptSubmit
- **Then:** additionalContext may mention `@verify-qa` / reviewer / Handoff; **не** содержит `REFLECT` как обязательный next

#### Acceptance Scenarios — US-004

- **Given:** `loop/schemas/phase_registry.yaml` after epic
- **When:** `get_phase_config("DECOMPOSE")`
- **Then:** `verify_agent == "verify-decompose"` AND `finish_gates_dict.need_verify is True` (same for `finish_gates` if present)

### Functional Requirements

- **FR-001:** Delete `armed_step=="DECOMPOSE"` override block in `user-prompt.py` (L159–172 as-built). No equivalent «docs-only» branch.
- **FR-002:** Delete QA FINISH `→ REFLECT` string. Replace with registry-true next: QA → BUGFIX/DONE (prose may say `mb-finish qa`; **not** REFLECT).
- **FR-003:** Align `phase_registry.yaml` DECOMPOSE `finish_gates` + `finish_gates_dict.need_verify: true`. Keep `need_reviewer: false`. Keep `verify_agent: verify-decompose`.
- **FR-004:** `gates_from_phase("DECOMPOSE")` returns `need_verify: true` after change; tests on this function, not only yaml text.
- **FR-005:** Overlay when `projection_authoritative`: **only** apply `gates_from_phase`; never a second policy table in Python.
- **FR-006:** Regex path (`not projection_authoritative`) remains for IDE sessions without loop; **must not** mention REFLECT; **must not** special-case DECOMPOSE OFF. Drift: increment existing `gate_verdict_regex_fallback`-style counter if one exists, or add `overlay_regex_mode` diagnostic in spawn state (optional P1).
- **FR-007:** Kind I rewrite: any comment/test expecting DECOMPOSE verify OFF or QA→REFLECT — delete/rewrite in-epic. Search: `REFLECT обязател`, `verify/reviewer OFF`, `promote DECOMPOSE→IMPLEMENT`.
- **FR-008:** spawn-hard.md already requires verify-decompose — **keep**. Do not weaken spawn-hard to match old overlay.
- **FR-009:** ANALYZE/IMPLEMENT promote remains `mb-finish decompose` / transition engine — overlay **не** promote. `promotable_after_finish: true` на DECOMPOSE в registry = prepare may promote **to ANALYZE** (canon), not IMPLEMENT. If prepare currently jumps IMPLEMENT, that is **074/transition leftover** — **out** unless one-line rg shows overlay-only. Confirm in DECOMPOSE: `finish_decompose` already ANALYZE (068/060). This epic does not rewrite `finish_decompose`.
- **FR-010:** Tests live under `harness/hooks/tests/` (user-prompt) and/or `loop/tests/` (registry). Independent Test = behavior of hook+registry, не «yaml field exists» alone (behavior-first §5).
- **FR-011:** Do not add a second `phase_policy.py` mega-module (Appetite: thin adapter). Max: small helper `overlay_gates(phase) -> dict` wrapping `gates_from_phase` if needed to avoid copy-paste.
- **FR-012:** FRONT/INTEG prefixes: overlay regex already role-agnostic; REFLECT/DECOMPOSE strings apply to all. Fix once.
- **FR-013:** `POST_IMPLEMENT_CHAIN` / finish-block: if they still mention REFLECT as gate — Kind I in this epic **only** for hook overlay + tests that encode overlay. Broader workflow-qa REFLECT leftovers that 060 missed in **hooks** are in-scope; `.cursor/rules/**` rewrite only if shard later lists them — PLAN WHAT: overlay + registry + hook tests. Rules mention: if `rg` finds REFLECT as QA next in `user-prompt` comments only.
- **FR-014:** Stop-gate must honor DECOMPOSE need_verify after registry align. If stop-gate special-cases docs-only DECOMPOSE — delete that special case in this epic (wire-complete).
- **FR-015:** No feature flag `PROJECT_LOOP_DECOMPOSE_VERIFY` default off.

### Success Criteria

| ID | Измеримый результат | Проверка | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | DECOMPOSE overlay need_verify true | pytest hook | outcome |
| SC-002 | no REFLECT in QA FINISH inject | pytest + `rg` user-prompt.py | outcome |
| SC-003 | registry DECOMPOSE need_verify true | pytest get_phase_config | outcome |
| SC-004 | no DECOMPOSE→IMPLEMENT overlay string | `rg` user-prompt.py | outcome |
| SC-005 | stop-gate DECOMPOSE requires verify sidecar if need_verify | pytest or rg stop-gate | outcome |

### Assumptions

- `gates_from_phase` implementation in `epic.core` читает `finish_gates_dict`; aligning yaml is sufficient for projection path.
- T-HUB-060 code path already omits REFLECT from `finish_qa`; leftover is **instruction overlay** + tests.
- IDE sessions without projection still need regex; they must not resurrect REFLECT.

### Clarifications

- Session: 2026-09-06 / clarify-20260906-loop-session-architecture.md
- Решённые: Variant A; overlay delete not wrap; registry need_verify align in this epic.

### [НУЖНО УТОЧНИТЬ]

- нет CRITICAL. DECOMPOSE `promotable_after_finish: true` target phase = ANALYZE (existing finish_decompose) — accepted.

## AC

1. Overlay не выключает verify на DECOMPOSE.
2. Overlay не требует REFLECT после QA.
3. Registry DECOMPOSE.need_verify согласован с verify_agent.
4. Тесты красные на старом override, зелёные на новом.
5. Kind I: rg по запрещённым строкам в `harness/hooks/user-prompt.py` = 0.

### AC−

1. Нет dual policy: overlay vs registry на DECOMPOSE verify.
2. Нет soft flag default off для decompose verify.
3. Нет «preferred registry but overlay wins if armed».
4. Нет живых тестов, assert’ящих verify OFF на DECOMPOSE или QA→REFLECT.
5. Нет второго Python таблицы фаз рядом с yaml.
6. Misconfig registry (verify_agent set, need_verify false) → **этот эпик чинит**, не «документирует drift».

---

## Техника / архитектура (HOW)

- **Стек:** Python 3.12 hooks; YAML phase-registry/v1; pytest.
- **Модули:** `harness/hooks/user-prompt.py` (thin adapter); `loop/schemas/phase_registry.yaml`; `harness/hooks/epic/core.py` `gates_from_phase` (verify behavior); possibly `harness/hooks/stop-gate.py` DECOMPOSE special-case.
- **Паттерн:** Adapter — hook не содержит политики. Strategy = registry row.
- **Наблюдаемость:** additionalContext одна строка `PROJECTION phase=… gates from registry`; без второго command.
- **Ограничения:** не генерировать CONTRACTS/README (069); не identity halt (071).

Sunset inventory (as-built to **delete**):

- String `QA FINISH detected → @reviewer · qa-*.yaml (verdict) · Handoff → REFLECT.`
- Block `armed_step=DECOMPOSE → verify/reviewer OFF` + promote IMPLEMENT.
- Tests/fixtures expecting those strings.
- Registry `need_verify: false` on DECOMPOSE.

---

## Eng review spine

### Data flow (ASCII)

```text
[UserPromptSubmit stdin]
    -> [load_epic_state / projection.phase]     sync
    -> [gates_from_phase(phase)]                sync, fail-closed if unknown phase
    -> [st.mode / need_verify / need_reviewer]  no overlay table
    -> [emit additionalContext]                 no REFLECT, no verify OFF
    -> [stop-gate reads spawn state]            DECOMPOSE requires verify sidecar
```

Hops: stdin → state → registry → spawn-state → emit → stop-gate (≥3, sync, fail-closed unknown phase).

### Failure matrix

| Component / link | Failure | Detection | User/system response | Test ID |
|------------------|---------|-----------|----------------------|---------|
| Overlay DECOMPOSE OFF leftover | verify skipped | pytest US-001 | FAIL epic | TM-001 |
| REFLECT string leftover | wrong next | pytest + rg | FAIL | TM-002 |
| registry need_verify false | gates_from_phase lies | pytest SC-003 | FAIL | TM-003 |
| stop-gate ignores need_verify | docs-only FINISH | pytest/rg | FAIL | TM-004 |
| regex path resurrect REFLECT | IDE session | pytest FINISH_RE | FAIL | TM-005 |
| unknown phase | KeyError swallow | gates_from_phase | fail-closed diagnostic | TM-006 |
| dual UserPromptSubmit (065) | double inject | out of scope 065 | n/a this epic | TM-007 (note only) |
| Kind I spawn-hard vs overlay | contradict | rg both | overlay deleted | TM-008 |

### Eng spine self-check

| Dimension | Score 1–5 | Gap / action |
|-----------|-----------|--------------|
| Data flow complete | 5 | registry → spawn → stop |
| Failure coverage | 5 | overlay, registry, stop-gate, regex, Kind I |
| Testability | 5 | hook main() with stub state |

---

## Replacement / sunset (brownfield)

### A. Code / modules

| Устаревает (path / symbol) | Замена | Policy |
| :--- | :--- | :--- |
| `user-prompt.py` DECOMPOSE armed override | `gates_from_phase` only | delete in-epic |
| `user-prompt.py` REFLECT QA FINISH sentence | QA FINISH → reviewer + mb-finish qa (no REFLECT) | delete in-epic |
| `phase_registry.yaml` DECOMPOSE `need_verify: false` | `true` | delete in-epic (replace value) |
| tests expecting OFF/REFLECT overlay | rewrite | delete in-epic |

### B. Entrypoints / deploy

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| n/a (same UserPromptSubmit hook) | — | n/a |

### C. Fallbacks / soft-fail

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| «docs-only DECOMPOSE» | verify-decompose required | delete in-epic |
| overlay wins if registry missing | fail-closed unknown phase | delete in-epic |

### I. Instruction surfaces

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| overlay `QA FINISH → REFLECT` | DONE/BUGFIX | delete in-epic |
| overlay `verify OFF` + `promote IMPLEMENT` | verify-decompose ON; next ANALYZE via mb-finish | delete in-epic |
| comments in user-prompt.py | registry comment | delete in-epic |

---

## NFR

| ID | Requirement |
|----|-------------|
| NFR-1 | Overlay policy table size → 0 special cases for DECOMPOSE/REFLECT |
| NFR-2 | Hook still <200 LOC target (thin); no new framework |
| NFR-3 | Fail-closed: missing registry phase ≠ silent OFF |
| NFR-4 | Kind I rg = 0 hits on forbidden strings in user-prompt.py |

---

## QA consumes (test plan)

<a id="qa-consumes"></a>

### Scope under test

- Epic surfaces: UserPromptSubmit overlay, phase_registry DECOMPOSE/QA gates, stop-gate DECOMPOSE verify.
- Out of scope: duplicate hooks (065), identity COMMAND (071), mb-load (072).

### Test matrix

| ID | Priority | Scenario | Command / fixture | Expected | Maps FR/AC |
|----|----------|----------|-------------------|----------|------------|
| TM-001 | P0 | armed DECOMPOSE → need_verify true | pytest user-prompt | PASS | US-001 FR-001 |
| TM-002 | P0 | QA FINISH context without REFLECT | pytest + rg | PASS | US-002 FR-002 |
| TM-003 | P0 | registry DECOMPOSE need_verify true | pytest get_phase_config | PASS | US-004 FR-003 |
| TM-004 | P0 | stop-gate respects need_verify DECOMPOSE | pytest stop-gate | PASS | FR-014 |
| TM-005 | P0 | regex FINISH QA no REFLECT | pytest | PASS | FR-006 |
| TM-006 | P1 | unknown phase fail-closed | unit | PASS | FR-011 |
| TM-007 | P1 | Kind I rg user-prompt | `rg -n 'REFLECT\|verify/reviewer OFF\|promote DECOMPOSE→IMPLEMENT' harness/hooks/user-prompt.py` | 0 | FR-007 AC-5 |
| TM-008 | P1 | gates_from_phase DECOMPOSE | pytest | need_verify true | FR-004 |

### Regression notes

- Dual hook fire (065) may run overlay twice — tests should be idempotent.
- T-HUB-060 tests may still import finish_reflect — **074/060**, не этот эпик, unless they encode overlay strings.

---

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| CLARIFY / Product probe | L3 | done | clarify-20260906 + §Product probe |
| Eng review spine | L2+ | done | §Eng review spine |
| §0.11 counterparts | if external | done | overlay ↔ registry ↔ stop-gate |
| CREATIVE | if flagged | n/a | — |
| qa_consumes draft | L2+ | done | ≥3 P0 TM |
| Plan review batch | L2+ | done | §Plan review batch log |

## Plan review batch log

| Phase | Auto-resolved | Deferred (owner/next) | Taste / CRITICAL surfaced |
|-------|---------------|-------------------------|---------------------------|
| Product (brainstorming) | Overlay delete; registry align; no mega PhasePolicy class | Event projector → B | none |
| Eng (architecture-patterns) | Adapter+Registry; need_verify sync | generate overlay from AST | none |

---

## До DECOMPOSE (черновик нарезки)

1. s01 — failing tests for overlay DECOMPOSE OFF + REFLECT (TDD red).
2. s02 — delete overlay blocks; QA FINISH prose without REFLECT.
3. s03 — align phase_registry DECOMPOSE need_verify + gates_from_phase tests.
4. s04 — stop-gate DECOMPOSE special-case purge if any.
5. s05 — Kind I rg + rewrite tests expecting old strings.
6. s06 — purge leftover comments / `legacy-fallback-purge`.

Advisory band 5–8; не cap.

---

## Appetite

| Поле | Значение | Описание |
| :--- | :--- | :--- |
| `timebox_days` | `3` | календарь |
| `cut_list` | `['generate overlay from AST', 'Variant B event projector', 'rewrite all workflow-qa mdc REFLECT if any outside hooks']` | scope cut, не меньше sNN |

## Independent Test

- PASS: hook DECOMPOSE need_verify true; QA inject без REFLECT; registry aligned; rg 0.
- FAIL: «удалили комментарий» / «projection_authoritative уже есть» без удаления L164–172.

## Следующий режим

→ BACK DECOMPOSE T-HUB-070 (после queue head; hard deps none). Queue order: после 062…069 или вставлен с deps — см. queue.yaml.

**CREATIVE need:** нет.
