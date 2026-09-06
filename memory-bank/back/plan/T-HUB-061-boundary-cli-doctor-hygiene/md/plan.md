# [T-HUB-061 | boundary-cli-doctor-hygiene] PLAN

**Дата:** 2026-09-04  
**Режим:** BACK PLAN  
**Уровень:** L2–L3  
**Статус:** active  
**Prompt:** [md/prompt.md](prompt.md) — `## Epic` + `## Covering`  
**Clarify:** Phase 0 skipped — taxonomy clear (чат 2026-09-04 audit plan↔runtime: три конкретных drift’а с воспроизводимым evidence; product ambiguity нет)  
**Roadmap:** `memory-bank/back/roadmap/queue.yaml` · batch `harness-ops-hygiene`  
**Deps:** soft T-HUB-057 (JSON session boundaries), T-HUB-053/059 (agent materialize), T-HUB-044 (doctor). Hard deps нет — эпик чинит leftover после закрытых.  
**Skills:** writing-plans · python-testing-patterns · grill-me (Phase 0 skip → mini grill §Product probe)  
**Источник:** chat audit 2026-09-04 + canvas `plan-runtime-parity-audit.canvas.tsx`

→ [T-HUB-061-boundary-cli-doctor-hygiene/md/decompose-index.md](T-HUB-061-boundary-cli-doctor-hygiene/md/decompose-index.md) — **после DECOMPOSE**

---

## Контекст

- **req:** После T-HUB-057/053/044 machine path для gate/repair/doctor заявлен рабочим, но операторский audit 2026-09-04 нашёл **три косяка**, ломающих pre-emit validate и doctor boundary scan, плюс leftover prose-fallback в repair extract.
- **gap (as-built evidence):**
  1. **CLI drift `--raw-json`:** `harness/agents/{gate-repair,verify-* ,analyze-verify}.md`, `harness/hooks/_lib.py` CONTRACT strings, materialized `.codex/agents/*.toml`, `dsh/presets/*.prompt.md` учат  
     `validate-boundary --schema-id … --raw-json '…'`.  
     CLI (`harness/hooks/epic_resolve.py`) принимает только `--json` / `--payload` (+ alias `--schema`/`--schema-id`). Copy-paste из agent → `unrecognized arguments: --raw-json`. Рабочий вызов проверен: `--json` → `valid: true`.
  2. **Doctor boundary kwargs:** `loop/incidents/doctor.py` зовёт `check_boundaries(root_dir=…, yaml_file=…)`.  
     `tests/architecture/check_boundaries.check_boundaries` signature = `(root_dir, boundaries_yaml_path)`.  
     Live `EPIC_RUNTIME=codex … doctor --json` → checklist `boundary_violations` status=`warn`, detail=`Check failed: check_boundaries() got an unexpected keyword argument 'yaml_file'`. Не blocker, но **маскирует** architecture scan.
  3. **Repair prose leftover:** `harness/hooks/_lib.extract_repair_result` после JSON+pydantic всё ещё:
     - soft-accept payload при exception pydantic, если есть `status ∈ {done,partial,fail}`;
     - regex `^REPAIR:\s*(done|partial|fail)` → synthetic dict без validate.  
     Тест `test_extract_repair_result_from_repair_line_fallback` **требует** prose path. SubagentStop дополнительно валидирует fence через `validate_boundary`, но helper dual-path нарушает axiom T-HUB-057 «JSON fence = sole extract SoT».
- **refs:** audit chat 2026-09-04; `loop/schemas/repair_result.py`; `loop/schemas/boundary_registry.py`; `harness/hooks/subagent-stop.py` gate-repair branch; `harness/manifest.yaml` materialize; T-HUB-057 plan §B-REPAIR; T-HUB-044 doctor.

**CREATIVE need:** нет.

---

## Technology axiom (replace-not-wrap)

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| validate-boundary CLI flag | `--json '<payload>'` или `--payload <path>` | `--raw-json` в любом instruction/agent/preset/contract string; **не** добавлять dual alias «на совместимость» без follow-up purge в том же эпике |
| Agent SoT | `harness/agents/*.md` → materialize `.claude` / `.codex` / dsh presets | правки только `.claude`/`.codex` в обход harness SoT |
| Repair extract SoT | fenced JSON → `RepairResultRecord.model_validate` | prose `REPAIR:` как extract success; soft return invalid payload после pydantic fail |
| Doctor ↔ architecture | `check_boundaries(root_dir, boundaries_yaml_path=…)` (или positional) | `yaml_file=` kwargs; monkeypatch-тесты, которые **кодируют** битый kwargs и зеленеют при сломанном prod |

As-built `--raw-json` / `REPAIR:` / `yaml_file=` — **sunset inventory**, не шаблон «добавим alias рядом».

---

## Продуктовая спека (WHAT)

Оператор и subagents получают:

1. **Один рабочий** pre-emit CLI snippet во всех agent/contract поверхностях: copy-paste из `gate-repair` / `verify-*` → `valid: true` без ручной правки флага.
2. **Doctor**, который реально вызывает architecture boundary checker: при чистом дереве `boundary_violations=pass` (или честный warn с count), **не** exception-string про `yaml_file`.
3. **Repair extract** без prose machine path: только JSON fence + pydantic; prose-only → `None` / schema-retry path как при missing fence.
4. Materialized Claude/Codex/dsh surfaces **синхронны** harness SoT после `runtime-sync` / materialize (нет дрейфа `--raw-json` в `.codex/agents`).

### Product probe (office-hours lite)

| # | Question | Answer / Probe | Decision / Impact on PLAN |
|---|----------|----------------|---------------------------|
| 1 | **Reframe:** | Agents «работают», но pre-emit CLI из промпта падает; doctor врёт про boundaries | Hygiene epic = fix teaching + call site + purge leftover |
| 2 | **Narrowest wedge:** | Replace `--raw-json`→`--json` в SoT+materialize; fix doctor kwargs; delete REPAIR fallback + obsolete test | 5–6 sNN |
| 3 | **Pre-mortem:** | Добавим `--raw-json` alias «чтобы не трогать agents» → dual CLI forever | AC− forbid alias-without-purge; axiom = fix teaching |
| 4 | **Adoption:** | `runtime-sync` / materialize после harness edit; doctor `--json` checklist | SC + enforce rg |
| 5 | **Leverage:** | T-HUB-057/053 materialize pipeline уже есть | Не новый runtime; только sync |
| 6 | **Appetite:** | 1–2 дня | cut: mid-turn JSON; MCP live Cursor; SessionEnd hooks |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как gate-repair/verify subagent, я хочу чтобы команда validate-boundary из моего prompt запускалась без ошибки argparse, чтобы pre-emit реально проверял JSON. | P0 | Скопировать snippet из `harness/agents/gate-repair.md` после фикса → CLI exit 0 + `valid: true` на валидном payload; `rg --raw-json harness/agents` = 0 |
| US-002 | Как operator `doctor --json`, я хочу честный `boundary_violations` pass/warn/skip без TypeError kwargs, чтобы видеть architecture violations. | P0 | Live `python loop/context_loop.py doctor --json`: checklist item `boundary_violations` detail **не** содержит `unexpected keyword argument 'yaml_file'`; при empty contracts → `pass` или `skipped` по правилам |
| US-003 | Как loop/hooks, я хочу чтобы `extract_repair_result` принимал только валидный JSON fence, чтобы prose `REPAIR:` не был machine SoT. | P0 | `extract_repair_result("REPAIR: fail\nno json") is None`; valid fence → pydantic dump; obsolete fallback test удалён или переписан на deny |
| US-004 | Как Codex/Claude operator, я хочу чтобы materialized agents не содержали `--raw-json` после sync. | P1 | После materialize: `rg --raw-json .codex/agents .claude/agents dsh/presets` = 0 (или только documented allowlist empty) |

#### Acceptance Scenarios — US-001

- **Given:** обновлённый `harness/agents/gate-repair.md` с `--json`
- **When:** выполнить snippet CLI с валидным `loop-repair-result/v1`
- **Then:** stdout JSON `valid: true`; нет `unrecognized arguments`

#### Acceptance Scenarios — US-002

- **Given:** repo с `tests/architecture/boundaries.yaml`
- **When:** `run_doctor(cwd)` / `doctor --json`
- **Then:** нет exception в detail; при 0 violations → `pass`; monkeypatch-тесты используют `boundaries_yaml_path` (или positional), совпадающий с prod call

#### Acceptance Scenarios — US-003

- **Given:** текст только с `REPAIR: done` без json fence
- **When:** `extract_repair_result(text)`
- **Then:** `None` (или equivalent miss); SubagentStop уходит в schema-retry / NEED_HUMAN, не `repair_done` от prose

### Functional Requirements (FR-###)

- **FR-001:** Во всех файлах `harness/agents/*.md`, содержащих `validate-boundary`, флаг `--raw-json` заменён на `--json` (тот же payload).
- **FR-002:** В `harness/hooks/_lib.py` CONTRACT / hint strings для gate-repair и verify больше нет `--raw-json`.
- **FR-003:** После правки SoT выполнен materialize/sync так, что `.claude/agents/*.md`, `.codex/agents/*.toml`, `dsh/presets/*verify*.prompt.md` и `gate-repair` preset (если есть) не содержат `--raw-json`.
- **FR-004:** `loop/incidents/doctor.py` вызывает `check_boundaries` с корректной сигнатурой (`boundaries_yaml_path` или positional args).
- **FR-005:** `loop/tests/test_incidents_doctor.py` monkeypatch/lambdas обновлены под реальную сигнатуру; добавлен/сохранён тест, который ловит kwargs mismatch (не зеленеет при `yaml_file=`).
- **FR-006:** Из `extract_repair_result` удалены: (a) prose `REPAIR:` regex success path; (b) soft-return invalid payload после pydantic `Exception` без `model_validate` success.
- **FR-007:** `harness/hooks/tests/test_gate_repair.py::test_extract_repair_result_from_repair_line_fallback` удалён **или** переписан на assert `is None` / schema miss (policy delete|rewrite в implement).
- **FR-008:** Enforce scan в implement/QA: `rg -n -- '--raw-json' harness/agents harness/hooks/_lib.py .claude/agents .codex/agents dsh/presets` → 0 matches (исключения только если явно в cut_list — сейчас пусто).
- **FR-009:** Документировать в implement done: команда rematerialize (`bin/runtime-sync` / `python -m loop… materialize`) фактически прогнанная в эпике.

### Non-Functional Requirements (NFR-###)

- **NFR-001:** Fail-closed: mis-taught CLI / broken doctor check → явная ошибка или честный warn, не silent skip как «всё ок».
- **NFR-002:** Не расширять scope на mid-turn JSON, MCP Cursor live, SessionEnd/PreCompact (остаются cut T-HUB-057/053).
- **NFR-003:** Rematerialize идемпотентен; alongside layout (T-HUB-046/059) не ломается.

### Success Criteria (SC-###)

| ID | Измеримый результат | Проверка / источник | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | 0× `--raw-json` в SoT+materialized instruction surfaces | `rg` FR-008 | outcome |
| SC-002 | gate-repair snippet CLI `valid: true` | targeted shell / pytest CLI test | outcome |
| SC-003 | doctor `boundary_violations` без `yaml_file` TypeError | `doctor --json` + unit tests | outcome |
| SC-004 | prose-only REPAIR не extract-success | `test_gate_repair` + optional subagent-stop semantic | outcome |
| SC-005 | Targeted suite green | `bin/pytest` paths ниже | outcome |

### Assumptions

- Harness agents = SoT; `.claude`/`.codex` — materialized copies (T-HUB-041/053/059). Правки начинаются с `harness/agents`.
- Добавление CLI alias `--raw-json` **не** является решением (appetite cut / AC−), кроме если DECOMPOSE явно выберет «alias + same-epic purge всех callers» — предпочтение: **только** fix teaching.
- 049 QA / workflow-pack queue продолжаются отдельно; этот эпик — ops hygiene, может идти параллельно по смыслу, но activeContext после PLAN → DECOMPOSE 061.
- CREATIVE не нужен.

### Clarifications

- Session: Phase 0 skipped — taxonomy clear (chat audit).
- Решено: не multi-epic (один bounded hygiene slice: CLI teaching + doctor call + repair extract purge).

## AC

1. Все validate-boundary snippets в harness agents используют `--json`.
2. Materialized Claude/Codex/dsh surfaces без `--raw-json`.
3. Doctor boundary check вызывает реальную `check_boundaries` без kwargs TypeError.
4. `extract_repair_result` prose-only → miss; JSON+pydantic only.
5. Obsolete fallback test удалён/rewritten.
6. Targeted pytest suite PASS.
7. Enforce `rg --raw-json` = 0 на instruction surfaces.

### AC−

1. Нет dual CLI (`--raw-json` + `--json`) как «совместимость навсегда» без same-epic purge.
2. Нет soft pydantic bypass в extract_repair_result.
3. Нет prose `REPAIR:` machine success path.
4. Нет тестов, которые monkeypatch’ом **закрепляют** битый `yaml_file=` как контракт prod.
5. Нет правок только `.codex` без обновления `harness/agents` SoT.
6. Нет расширения scope на новые boundary schemas / mid-turn JSON.

---

## Техника / архитектура (HOW)

- **Стек:** argparse CLI `epic_resolve.py validate-boundary`; pydantic `RepairResultRecord`; doctor `run_doctor`; architecture `check_boundaries`; runtime materializers agents/codex.
- **Стратегия:**  
  1) doctor call-site + tests (быстрый fail-closed observability);  
  2) harness agents + `_lib` strings;  
  3) materialize/sync + dsh presets;  
  4) purge repair extract + rewrite tests;  
  5) enforce rg + pytest matrix.
- **Наблюдаемость:** `doctor --json` checklist; CLI validate-boundary stdout; `rg` gate в implement step.

## Eng review spine

### Data flow (ASCII)

```text
[agent prompt snippet]
  -> epic_resolve validate-boundary --schema-id S --json '{…}'
  -> BOUNDARY_REGISTRY[S].model_validate
  -> {valid:true|false}

[gate-repair final text]
  -> JSON fence loop-repair-result/v1
  -> extract_repair_result (pydantic only)
  -> subagent-stop validate_boundary + state.repair_*

[doctor]
  -> check_boundaries(root_dir, boundaries_yaml_path=boundaries.yaml)
  -> checklist boundary_violations pass|warn|skipped
```

### Failure matrix

| Component / link | Failure | Detection | User/system response | Test ID |
|------------------|---------|-----------|----------------------|---------|
| Agent учит `--raw-json` | argparse error | CLI / rg | fix SoT + rematerialize | TM-001 |
| Doctor `yaml_file=` | TypeError swallowed as warn | doctor --json detail | fix kwargs + tests | TM-002 |
| Prose REPAIR only | false repair_done | extract unit + stop path | purge fallback | TM-003 |
| Materialize stale | .codex всё ещё `--raw-json` | rg after sync | rematerialize in-epic | TM-004 |
| Soft pydantic bypass | invalid JSON accepted | unit | delete except-return | TM-005 |

### Eng spine self-check

| Dimension | Score 1–5 | Gap / action |
|-----------|-----------|--------------|
| Data flow complete | 5 | — |
| Failure coverage | 5 | — |
| Testability | 5 | targeted TM |

## Replacement / sunset (brownfield)

### A. Code / modules

| Устаревает (path / symbol) | Замена | Policy |
| :--- | :--- | :--- |
| `--raw-json` в `harness/agents/*.md`, `_lib.py` CONTRACT | `--json` | delete/replace in-epic |
| `--raw-json` в `.claude/agents`, `.codex/agents`, `dsh/presets` | rematerialize / sync from harness | delete in-epic |
| `extract_repair_result` regex `^REPAIR:` success | JSON fence + pydantic only | delete in-epic |
| soft `except Exception: return payload` в extract_repair_result | re-raise miss / continue next fence | delete in-epic |
| `test_extract_repair_result_from_repair_line_fallback` requiring prose success | assert miss **или** delete file test | delete/rewrite in-epic |
| `doctor.py` `yaml_file=` | `boundaries_yaml_path=` / positional | replace in-epic |
| doctor tests `lambda root_dir, yaml_file:` | `boundaries_yaml_path` / `*args` matching prod | rewrite in-epic |

### B. Entrypoints / deploy

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| «ручной edit только .codex» | harness SoT → `runtime-sync` / materialize | delete habit in-epic (FR-009) |

### C. Fallback / dual-path

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| dual accept prose OR json для repair extract | json-only | delete in-epic |
| CLI alias `--raw-json` «для совместимости» | не вводить; teaching = `--json` | forbid (AC−) |

### I. Instruction surfaces (Kind I)

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| Agent/preset CONTRACT с `--raw-json` | `--json` | purge in-epic |
| Любые finish-block / spawn-hard упоминания `--raw-json` (если появятся при rg) | `--json` | purge in-epic |

## Outline steps (advisory для DECOMPOSE)

| Step | Intent | Primary files |
|------|--------|---------------|
| s01 | Fix doctor `check_boundaries` call + rewrite doctor tests to real signature; live doctor assert | `loop/incidents/doctor.py`, `loop/tests/test_incidents_doctor.py` |
| s02 | Replace `--raw-json`→`--json` in `harness/agents/*.md` + `_lib.py` contracts | `harness/agents/*`, `harness/hooks/_lib.py` |
| s03 | Rematerialize/sync `.claude` / `.codex` + fix `dsh/presets` leftovers; FR-009 command recorded | materializers, presets |
| s04 | Purge repair prose/soft fallback; rewrite/delete `test_gate_repair` fallback | `harness/hooks/_lib.py`, `harness/hooks/tests/test_gate_repair.py` |
| s05 | Enforce rg `--raw-json`==0 + targeted pytest matrix (doctor, validate-boundary, gate_repair, optional spawn) | tests + implement evidence |

Target band: **5** sNN (не раздувать).

## Risks

| Risk | Mitigation |
|------|------------|
| Materialize пропущен → Codex снова учит `--raw-json` | FR-003/008/009 + SC-001 |
| SubagentStop полагался на prose в edge case | schema-retry уже есть; AC+ prose→None |
| Doctor tests зелёные при сломанном prod | rewrite monkeypatch signature + optional unpatched call |
| Широкий `rg` затронет docs вне scope | limit paths FR-008; docs-only leftovers → same purge if instruction |

## Test strategy

- Unit: extract_repair_result json-only; doctor boundary kwargs.
- CLI: validate-boundary `--json` from agent snippet.
- Integration-ish: `doctor --json` checklist detail.
- Enforce: rg gates in implement verification_results.
- **Forbidden:** «чинить» prod под `test_extract_repair_result_from_repair_line_fallback` — тест удалить/rewrite.

### #qa-consumes

| TM | Command / assert | Maps |
|----|------------------|------|
| TM-001 | `rg -n -- '--raw-json' harness/agents harness/hooks/_lib.py .claude/agents .codex/agents dsh/presets` → empty | FR-001..003, SC-001 |
| TM-002 | `bin/pytest loop/tests/test_incidents_doctor.py -q` + doctor `--json` no yaml_file TypeError | FR-004/005, SC-003 |
| TM-003 | `bin/pytest harness/hooks/tests/test_gate_repair.py loop/tests/test_validate_boundary.py -q` | FR-006/007, SC-002/004 |
| TM-004 | Optional: `bin/pytest harness/hooks/tests/test_spawn_validate.py -k repair -q` | regression spawn |

## Review readiness

| Item | Status | Notes |
|------|--------|-------|
| Product probe | done | Phase 0 skip + mini grill |
| Technology axiom | done | no dual CLI alias |
| Sunset A+B+C+I | done | tables above |
| Eng spine | done | data flow + failure matrix |
| QA consumes ≥3 TM | done | TM-001..004 |
| CRITICAL open | none | — |
| CREATIVE | not needed | — |

### Plan review batch log

| Pass | Result |
|------|--------|
| Product | Hygiene only; cut mid-turn/MCP/IDE |
| Eng | Single epic; doctor tests were encoding the bug — must rewrite |
| Auto-resolve defer | Alias `--raw-json` → **reject** (AC−); keep in cut_list as forbidden |

## Appetite

- **Timebox:** 1–2 дня implement+QA  
- **cut_list:** mid-turn JSON; MCP live Cursor; SessionEnd/PreCompact; adding permanent `--raw-json` alias; workflow-pack 050–052; T-HUB-049 QA (отдельный поток)

## Decompose input map

| Plan ref | Expected sNN theme |
|----------|-------------------|
| FR-004/005, US-002 | s01 doctor |
| FR-001/002, US-001 | s02 harness SoT |
| FR-003/009, US-004 | s03 materialize |
| FR-006/007, US-003 | s04 repair purge |
| FR-008, SC-* | s05 enforce + matrix |

## Next

**BACK DECOMPOSE** `T-HUB-061-boundary-cli-doctor-hygiene`  
(не ROADMAP MERGE; 049 QA может быть продолжен отдельной командой после/параллельно по решению оператора — activeContext после этого PLAN указывает на 061)
