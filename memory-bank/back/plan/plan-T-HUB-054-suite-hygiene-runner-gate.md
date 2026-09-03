# [T-HUB-054 | suite-hygiene-runner-gate] PLAN

**Дата:** 2026-09-02  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** done  
**Clarify:** Phase 0 skipped — taxonomy clear (fail-list + implement axioms из T-HUB-023/039/004; нет product ambiguity)  
**Roadmap:** [roadmap-suite-hygiene-epics.md](roadmap-suite-hygiene-epics.md) · queue sibling  
**Baseline suite:** `19 failed, 1551 passed` (`/tmp/pytest-full-fresh.txt`, 2026-09-02)

→ [decompose-T-HUB-054-suite-hygiene-runner-gate/index.md](decompose-T-HUB-054-suite-hygiene-runner-gate/index.md) — **после DECOMPOSE**

## Контекст

- req: full suite снова доверенный gate для BACK QA; T-HUB-044 закрыли targeted suite при известном `bin/pytest` FAIL
- deps: soft на завершённые T-HUB-023, T-HUB-039, T-HUB-004, T-HUB-041 (paths `.claude`↔`harness`)
- refs: `roadmap-suite-hygiene-epics.md` §анализ; implement `T-HUB-023/s04,s08,s13`; `T-HUB-039` phase agents; `@.cursor/rules/shared/test-timeout.mdc`

## Technology axiom (replace-not-wrap)

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Gate verdict | fenced JSON `loop-gate-verdict/v1` (+ sidecar via `read_gate_verdict`) | prose `VERDICT: PASS` как machine path; regex last-wins в `extract_verdict` |
| Phase agents SoT | `verify-implement` / `verify-qa` / `verify-*` | fixtures/assert на удалённые `verify.md` / `reviewer.md` |
| Per-test timeout | `pytest-timeout` + `bin/pytest` 300s process | «timeout в pytest.ini» без плагина; hang process живёт после suite |

As-built (`extract_verdict` sidecar-only, agents rename) — **sunset inventory**, не шаблон «вернуть regex».

## Продуктовая спека (WHAT)

Оператор и loop должны получать **однозначный** результат полного тестового прогона хаба: либо зелёный suite, либо короткий fail-list с классами LEGACY/REGRESSION/PROD. Gate-контракт (JSON verdict + phase agents) не должен снова открывать дверь prose-`VERDICT` через устаревшие тесты. Runner обязан убивать зависшие тесты по item-timeout, иначе один hang маскирует десятки ложных FAIL в следующих чанках.

## Product probe (office-hours lite)

| # | Question | Answer / Probe | Decision / Impact on PLAN |
|---|----------|----------------|---------------------------|
| 1 | **Reframe:** Какую реальную проблему решаем? | QA/loop лгут «pass», пока full suite red; leftover тесты тянут удалённый контракт | Epic = hygiene + gate leftover only |
| 2 | **Narrowest wedge:** | Установить `pytest-timeout` + починить 3 gate-related FAIL из fresh list | s01 runner → s02–s04 gate tests/prod |
| 3 | **Pre-mortem:** | Вернём `VERDICT:` в prod «чтобы green» | AC− + sunset A forbid restore regex |
| 4 | **Adoption:** | `bin/pytest` / BACK QA full suite | SC = 0 fail в gate cluster + plugin loaded |
| 5 | **Leverage:** | Не чинить board/doctor здесь | cut → T-HUB-055/056 |
| 6 | **Appetite:** | 2–3 дня | cut_list: docs polish, расширенный hang catalog |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как BACK QA, я хочу чтобы `bin/pytest` не зависал бесконечно на одном item, чтобы fail-list был полным за ≤300s process. | P0 | После установки плагина: `pytest --help` показывает `--timeout`; заведомо sleeping-тест убивается item-timeout’ом (наблюдаемый non-pass), не hang suite. |
| US-002 | Как parent/loop, я хочу чтобы packed prompt / agents требовали `loop-gate-verdict/v1`, а не prose VERDICT, чтобы stop-gate читал один machine path. | P0 | `rg 'loop-gate-verdict/v1' loop/context_loop.py` ≥1; `test_gate_structured_purge.py` PASS; `test_agent_pretool_injects_verdict_first_line` либо удалён, либо переписан на JSON-inject (не VERDICT-first). |
| US-003 | Как implementer, я хочу чтобы тесты не требовали удалённые stub agents/symbols phase-verify, чтобы suite не требовал restore legacy. | P0 | `test_phase_verify_gates.py::test_legacy_stubs_removed` PASS против текущего registry/files. |

#### Acceptance Scenarios — US-001

- **Given:** `pytest-timeout` в dev deps, `pytest.ini` `timeout=300`
- **When:** `bin/pytest -q --tb=no`
- **Then:** нет warning `Unknown config option: timeout`; suite завершается ≤300s внешнего timeout

#### Acceptance Scenarios — US-002

- **Given:** контракт T-HUB-023 s08/s13
- **When:** читаем `loop/context_loop.py` и gate agents
- **Then:** machine instruction = JSON schema name; нет `` `VERDICT: PASS` `` как self-standing machine instruction

### Functional Requirements (FR-###)

- **FR-001:** В `requirements-dev.txt` (или канон deps) есть `pytest-timeout`; `pytest.ini` опции реально применяются.
- **FR-002:** `loop/context_loop.py` содержит явную ссылку на `loop-gate-verdict/v1` в operator/prompt packing (восстановление AC T-HUB-023 s08), без возврата prose VERDICT machine lines.
- **FR-003:** Тест `test_agent_pretool_injects_verdict_first_line` либо удалён (`deletes`), либо rewrite на inject JSON fence / sidecar contract (T-HUB-023 s07/s09).
- **FR-004:** `test_phase_verify_gates.py::test_legacy_stubs_removed` отражает фактический sunset stubs (T-HUB-039), не absent files wrong paths.
- **FR-005:** Method lock: каждый FAIL этого эпика трассируется к implement yaml; решение delete|rewrite|fix-prod записано в implement step `done:`.
- **FR-006:** Документ fail-list protocol: путь артефакта `memory-bank/back/qa/` или `loop/README` секция — как снимать fresh fail-list (`bin/pytest -q --tb=no` + `rg '^FAILED '`).

### Success Criteria (SC-###)

| ID | Измеримый результат | Проверка / источник | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | Нет PytestConfigWarning timeout | suite warnings summary | outcome |
| SC-002 | Gate cluster green | `bin/pytest loop/tests/test_gate_structured_purge.py loop/tests/test_phase_verify_gates.py::test_legacy_stubs_removed -q` → 0 failed; `test_agent_pretool_injects_verdict_first_line` удалён в s03 (collected=0) | outcome |
| SC-003 | Fresh full suite не содержит 3 gate nodeids из baseline | `rg` fail-list | outcome |

### Assumptions

- Fresh fail-list (19) — SoT; старые 59/67 не расширяют scope без нового full run.
- `harness/hooks` и `.claude/hooks` symlink/parity — читать оба при rg (T-HUB-041).
- CREATIVE не нужен.

### Clarifications

- Session: Phase 0 skipped — taxonomy clear.
- Решено из implement: sidecar-only extract_verdict; phase agents SoT; sc006 = restore string в context_loop, не delete test.

## AC

1. `pytest-timeout` установлен и применяется.
2. `test_sc006_context_loop_no_verdict_machine_instruction` PASS.
3. `test_agent_pretool_injects_verdict_first_line` PASS или удалён с записью в sunset A + `deletes`.
4. `test_legacy_stubs_removed` PASS.
5. Implement steps содержат mapping FAIL→action.
6. Full suite больше не падает на этих трёх nodeids.

### AC−

1. Нет возврата `re.finditer(VERDICT)` / prose machine VERDICT в `extract_verdict`.
2. Нет dual assert «JSON или VERDICT».
3. Misconfig плагина → явный fail install/docs, не silent ignore.
4. Нет тестов, требующих `verify.md`/`reviewer.md` как живые gate agents.
5. Нет «skip» маркеров на broken gate tests без deletes.

## Техника / архитектура (HOW)

- Стек: pytest, pytest-timeout, hub hooks (`harness/hooks/_lib.py`, `agent-pretool.py`), `loop/context_loop.py`, `.claude/agents/verify-*.md`
- Стратегия: сначала runner (чтобы последующие эпики имели честный suite), затем точечный restore/rewrite по implement
- Наблюдаемость: warnings summary + fail-list artifact в QA step

## Eng review spine

### Data flow (ASCII)

```text
[bin/pytest] -> [pytest-timeout item kill] -> [test process exit]
[agent output] -> [JSON fence loop-gate-verdict/v1] -> [extract_verdict/read_gate_verdict] -> [stop-gate allow/deny]
[context_loop pack prompt] -> [instruction: JSON schema] -> [subagent]  sync; fail-closed if no sidecar/fence
```

### Failure matrix

| Component / link | Failure | Detection | User/system response | Test ID |
|------------------|---------|-----------|----------------------|---------|
| pytest-timeout missing | hang item | Unknown config warning / suite wall | install plugin | TM-001 |
| context_loop без schema string | sc006 fail | assert | restore instruction per s08 | TM-002 |
| pretool VERDICT-first leftover | stop_gate fail | assert inject | rewrite pretool test/prod to JSON | TM-003 |
| legacy stub paths | phase_verify fail | assert files | align test to T-HUB-039 deletes | TM-004 |
| restore regex «для green» | dual path | rg VERDICT in extract_verdict | FAIL AC− | TM-005 |

### Eng spine self-check

| Dimension | Score 1–5 | Gap / action |
|-----------|-----------|--------------|
| Data flow complete | 5 | — |
| Failure coverage | 4 | hang catalog → cut_list |
| Testability | 5 | targeted TM commands |

## Replacement / sunset (brownfield)

### A. Code / modules

| Устаревает (path / symbol) | Замена | Policy |
| :--- | :--- | :--- |
| `test_stop_gate.py::test_agent_pretool_injects_verdict_first_line` asserts на prose first-line VERDICT | JSON fence inject / sidecar assert | delete in-epic **или** rewrite |
| Любые fixtures `_ensure_gate_agents` → `verify.md`/`reviewer.md` в scope правок | `verify-implement.md` / `verify-qa.md` | delete in-epic |
| Ghost nodeids inventory: `test_sync_verify_preset_contains_ac_plus` и т.п. (уже нет в collect) | уже renamed; не restore | keep (gone) |
| `extract_verdict` regex machine path | sidecar-only (уже) | keep — **forbid restore** |

### B. Entrypoints / deploy

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| «pytest.ini timeout без плагина» как ложная защита | `pytest-timeout` + `bin/pytest` | delete in-epic (ложная вера) |

### C. Fallbacks / soft-fail

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| try JSON except regex VERDICT | только JSON/sidecar; иначе None/FAIL | delete in-epic |
| skip gate test «временно» | fix or delete | delete in-epic |

<a id="qa-consumes"></a>
## QA consumes (test plan)

### Scope under test

- Epic surfaces: pytest runner config, gate structured purge, stop_gate pretool inject, phase_verify stubs
- Out of scope: board_sync, doctor, epic_id stem (055/056)

### Test matrix

| ID | Priority | Scenario | Command / fixture | Expected | Maps FR/AC |
|----|----------|----------|-------------------|----------|------------|
| TM-001 | P0 | timeout plugin active | `bin/pytest --help \| rg timeout` / suite warnings | no Unknown config | FR-001 |
| TM-002 | P0 | sc006 | `bin/pytest loop/tests/test_gate_structured_purge.py -q` | PASS | FR-002 AC-2 |
| TM-003 | P0 | pretool inject | `bin/pytest loop/tests/test_stop_gate.py::test_agent_pretool_injects_verdict_first_line -q` | PASS or collected=0 after delete | FR-003 |
| TM-004 | P0 | legacy stubs | `bin/pytest loop/tests/test_phase_verify_gates.py::test_legacy_stubs_removed -q` | PASS | FR-004 |
| TM-005 | P0 | full suite без 3 gate F | `bin/pytest -q --tb=no` + rg fail-list | gate nodeids absent | SC-003 |

### Regression notes

- Suite pollution: после timeout plugin переснять fail-list перед 055/056.
- Не запускать параллельно десятки zombie pytest (окружение).

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| CLARIFY / Product probe | L3 | done | §Product probe |
| Eng review spine | L2+ | done | §Eng review spine |
| §0.11 counterparts (draft) | if external refs | done | context_loop ↔ agents ↔ _lib |
| CREATIVE | if flagged | n/a | — |
| qa_consumes draft | L2+ | done | ≥5 TM |
| Plan review batch | L2+ | done | §Plan review batch log |

## Plan review batch log

| Phase | Auto-resolved | Deferred (owner/next) | Taste / CRITICAL surfaced |
|-------|---------------|-------------------------|---------------------------|
| Product | sc006 = restore context_loop string per s08; VERDICT-first test = rewrite/delete | hang catalog extras → cut | none CRITICAL open |
| Eng | pytest-timeout must be real dep; harness+_lib paths | board/doctor → 055/056 | — |

## До DECOMPOSE (черновик нарезки)

1. **s01** — add `pytest-timeout`; verify warnings gone; optional tiny hang-smoke  
2. **s02** — restore `loop-gate-verdict/v1` instruction in `context_loop.py` (s08 AC); sc006 green  
3. **s03** — rewrite/delete `test_agent_pretool_injects_verdict_first_line` + align pretool if prod still injects VERDICT-first  
4. **s04** — align `test_legacy_stubs_removed` to T-HUB-039 filesystem  
5. **s05** — fail-list protocol note + targeted gate suite + full suite gate-nodeids check  
6. **s06-legacy-fallback-purge** — rg no VERDICT machine in extract_verdict; no verify.md SoT asserts in touched tests

## Appetite

| Поле | Значение | Описание |
| :--- | :--- | :--- |
| `timebox_days` | `2` | runner + 3 FAIL |
| `cut_list` | `['extended hang catalog', 'docs beyond README note']` | |

## Следующий режим

→ BACK DECOMPOSE `T-HUB-054-suite-hygiene-runner-gate`
