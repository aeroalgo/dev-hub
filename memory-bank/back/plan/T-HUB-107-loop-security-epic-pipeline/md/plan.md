# [T-HUB-107 | loop-security-epic-pipeline] PLAN

**Дата:** 2026-10-24  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** active  
**Clarify:** [clarify-20261024-loop-security-epic.md](../../clarify/clarify-20261024-loop-security-epic.md)  
**Prompt:** [md/prompt.md](prompt.md) — outcome SoT (абстрактный; не HOW)  
**Roadmap:** `memory-bank/back/roadmap/queue.yaml` · batch `loop-security-epic-20261024` · `kind: feature`  
**Deps:** — (loop kernel v2 / gate agents as-built; no hard queue dep)  
**Skills:** writing-plans · python-testing-patterns · architecture-patterns · grill-me (Phase 0)  
**Источник:** chat BACK PLAN «стандартизировать SECURITY в loop по шагам»

---

## Контекст

- **req:** Loop должен вести SECURITY-эпик по шагам `aNN` (audit findings) машинно: start → DECOMPOSE (если нет index) → SECURITY @a01… → DONE.
- **status quo:** Workflow `BACK SECURITY PLAN|DECOMPOSE|SECURITY` и templates `harness/cursor/templates/security/` существуют; `loop/kernel/index.py` `index_path`/`plan_path` всегда `memory-bank/<role>/plan/<epic>/`; фаза execute = IMPLEMENT (+ REFACTOR в gate map без path); post-queue всегда AUDIT→QA→CONTEXT_SYNC.
- **gap:** `bin/loop.py start --epic <security-id>` не находит `security/plan/<id>`; finish не валидирует `epic-security/v1`; нет `verify-security`; REFACTOR paths тоже feature-only (тот же gap kind).
- **refs (as-built inventory):** `loop/kernel/index.py` · `engine.py` · `cli.py` · `creative.py` · `roadmap.py` · `config.py` · `implement_schema.py` · `model.py` (Cursor) · `harness/agents/verify-implement.md` · `harness/cursor/templates/security/*` · `.cursor/rules/shared/workflow-security-epic.mdc`
- **Не в scope:** содержание product security-аудитов; изменение feature ANALYZE/IMPLEMENT/AUDIT/QA; S one-shot в loop; новые runtimes.

**CREATIVE need:** нет (контракт путей/фаз фиксирован clarify; UI нет).

---

## Context consumed

| Path | Что вошло в axiom / Deps / FR |
|------|-------------------------------|
| `memory-bank/techContext.md` | Hub Python loop + `bin/pytest`; pydantic settings; runtime state в hub |
| `memory-bank/systemPatterns.md` | SP-H02 context-first cursor; SP-H03 runner owns bounds; SP-H04 fail-closed; SP-H07 gate subagents |
| `memory-bank/projectbrief.md` | Scope = hub tooling (`loop/`, agents, rules); не product app code |
| `memory-bank/architecture/index.md` | Loop sessions / workers; нет ORM; boundaries tests |
| `memory-bank/product/` | n/a — каталога нет |

---

## Delivery closure

| Capability / outcome | Classification | Production entrypoint and caller | Success / failure enforcement | Independent outcome test | Foundation approval / follow-up |
|---|---|---|---|---|---|
| Kind-aware plan/index/execute paths | `vertical_slice` | `bin/loop.py start|run|finish` → `resolve_epic_role` / `index_path` / `implement_path` (kind-aware) | ambiguous/missing kind → TransitionError / FileNotFoundError; feature-only hardcode на hot path отсутствует | Given security plan tree; When `start --epic`; Then cursor.phase DECOMPOSE\|SECURITY, paths under `security/plan` | `n/a` |
| SECURITY step loop aNN | `vertical_slice` | `LoopEngine.finish` / `_target` for `kind=security` | finish без findings artifact → TransitionError; last aNN → DONE (не AUDIT) | Given 2 aNN pending; When finish a01 PASS; Then cursor on a02 SECURITY; after a02 → DONE | `n/a` |
| verify-security gate | `vertical_slice` | `_PHASE_GATE_AGENTS["SECURITY"]` + spawn protocol in CLI + agent file discoverable | finish SECURITY без PASS verify-security → deny; wrong agent id → reject | Given SECURITY cursor; When gate agent required; Then `verify-security` | `n/a` |
| Refactor path parity | `vertical_slice` | same kind resolver for `kind=refactor` | `refactor/plan/<id>` start works; execute under `refactor/implement/` | Given refactor plan tree; When start; Then index under refactor/plan | `n/a` |

---

## Technology axiom (replace-not-wrap)

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Epic kind SoT | `Cursor.kind` ∈ {`feature`,`refactor`,`security`} + path layout under `memory-bank/<role>/{,refactor/,security/}plan/<id>/` | hardcode sole `…/plan/<id>/` на start/finish/load_queue hot path; silent default feature при однозначном security/refactor tree |
| SECURITY execute artifact | YAML `schema: epic-security/v1` validate-on-finish (Pydantic, зеркало implement_schema) | prose-only `security-audit-*.md` как FINISH evidence для **эпика**; regex «есть findings» без schema |
| Gate | agent id `verify-security` + `loop-gate-verdict/v1` | reuse `verify-implement` как единственный gate SECURITY; invent parent-driven-security |
| Post-queue security | `_phase_after_queue` / `_target` → `DONE` when kind=security и все aNN complete | force AUDIT/QA/CONTEXT_SYNC для security kind |
| Path API | единый `plan_path`/`index_path`/`execute_path(kind, …)` | dual helpers «feature_index_path» + «security_index_path» без общего kind |

As-built feature path = **sunset inventory** для hardcode, не шаблон «оставить feature-only + optional security flag».

---

## Продуктовая спека (WHAT)

Оператор запускает loop на SECURITY-эпике и получает пошаговое движение по audit-срезам: каждый шаг закрывается только валидным findings-артефактом и gate PASS; после последнего среза эпик завершён. Feature-эпики продолжают прежний хвост AUDIT/QA. One-shot SECURITY без эпика по-прежнему ручной режим вне loop.

### Product probe

| # | Question | Answer / Probe | Decision / Impact on PLAN |
|---|----------|----------------|---------------------------|
| 1 | **Reframe** | Не «новый SECURITY PLAN», а wire loop к уже описанному SECURITY epic | Kind + phase SECURITY + DONE |
| 2 | **Narrowest wedge** | start/finish на fixture security tree + schema + gate id | Vertical slice до README |
| 3 | **Pre-mortem** | Забыть CLI path hardcode → green unit, red operator | Kind I + CLI tests |
| 4 | **Distribution** | `loop/README.md` + workflow-security loop tip | Kind I in-epic |
| 5 | **Technical leverage** | Переиспользовать Queue/Step/finish transaction; не второй supervisor | Extend engine, don't fork |
| 6 | **Appetite** | ~2–3 дня; cut = auto-arm next security from roadmap fancy UX | cut_list below |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как оператор, я хочу `loop.py start --epic <security-id>`, чтобы курсор встал на DECOMPOSE или первый aNN security-эпика. | P0 | Fixture `security/plan/<id>/`; start → phase/step correct; path ≠ feature plan |
| US-002 | Как оператор, я хочу `finish` после verify-security PASS, чтобы index aNN стал completed и курсор перешёл на следующий aNN или DONE. | P0 | Two-step fixture; finish a01 → a02; finish a02 → DONE |
| US-003 | Как gate, я хочу `verify-security`, чтобы FINISH не принимал пустой/невалидный findings YAML. | P0 | Missing/invalid schema → TransitionError; valid → accept |
| US-004 | Как оператор refactor-эпика, я хочу тот же kind-resolve для `refactor/plan/`, чтобы REFACTOR не ломался на feature-only path. | P1 | Fixture refactor plan; start loads index |

#### Acceptance Scenarios — US-001

- **Given:** `memory-bank/back/security/plan/E-SEC/md/plan.md` (+ optional empty/missing index)
- **When:** `LoopEngine.start("E-SEC", "back")` или CLI equivalent
- **Then:** `cursor.kind == security`; phase `DECOMPOSE` если нет index, иначе первый pending → `SECURITY` / `aNN`; `FileNotFoundError` не ссылается на feature `plan/E-SEC` как единственный candiate при существующем security tree

#### Acceptance Scenarios — US-002

- **Given:** security index с a01 pending, a02 pending; a01 findings yaml valid `in_progress`
- **When:** accept verify-security PASS + finish a01
- **Then:** index a01 completed; cursor `SECURITY`/`a02`; после finish a02 → `DONE` (не `AUDIT`)

#### Acceptance Scenarios — US-003

- **Given:** SECURITY cursor на a01 без файла / с wrong schema
- **When:** finish
- **Then:** TransitionError; index status не completed

#### Acceptance Scenarios — US-004

- **Given:** `refactor/plan/E-RF/yaml/decompose-index.yaml`
- **When:** start E-RF
- **Then:** queue loaded from refactor path; execute artifact path under `refactor/implement/`

### Functional Requirements (FR-###)

- **FR-001:** Система должна определять `kind` ∈ {`feature`,`refactor`,`security`} при `start` по layout (и `--kind` при неоднозначности) и сохранять `kind` в cursor state.
- **FR-002:** Система должна резолвить `plan_path` / `index_path` / execute artifact path относительно kind (feature → `plan|implement`; refactor → `refactor/plan|implement`; security → `security/plan|implement`).
- **FR-003:** Для `kind=security` после наличия валидного decompose index система должна назначать execute-фазу `SECURITY` (не `IMPLEMENT`) на pending `aNN`.
- **FR-004:** Для `kind=security` система должна **не** требовать ANALYZE gate перед первым `SECURITY` шагом (DECOMPOSE → SECURITY напрямую).
- **FR-005:** `finish` на `SECURITY` должен pydantic-валидировать execute yaml `epic-security/v1` (step_id, plan_id, status, findings непустой list или явный empty-with-rationale field per template policy — **минимум:** schema + checkpoints + status machine как implement), затем mark index completed.
- **FR-006:** После завершения всех security steps `_target` / `_phase_after_queue` должны возвращать `DONE` (не AUDIT/QA/CONTEXT_SYNC).
- **FR-007:** `_PHASE_GATE_AGENTS["SECURITY"] = "verify-security"`; CLI gate protocol для SECURITY указывает ALLOW READ на security implement + decompose step.
- **FR-008:** Должен существовать agent SoT `harness/agents/verify-security.md` (+ codex/materialize parity как у соседних verify-*), read-only, verdict pass-fail, checklist из security execute yaml.
- **FR-009:** `LOOP_MODEL_SECURITY` / phase model resolution должен знать фазу `SECURITY` (PHASES + settings field).
- **FR-010:** Roadmap advance при `next_kind=security` должен искать plan под `security/plan/<id>/md/plan.md` (не только feature `plan/`).
- **FR-011:** Kind=`refactor` получает тот же path/execute resolve (фаза `REFACTOR` уже есть); post-queue refactor = как feature (AUDIT→…) **или** явно documented same-as-feature — **decision:** refactor сохраняет feature post-queue (code change); только security short-circuits to DONE.
- **FR-012:** S one-shot (`security/security-audit-*.md`) **не** становится loop epic; попытка finish SECURITY без epic index → существующий/ясный error.
- **FR-013:** Kind I: `loop/README.md`, `workflow-security.mdc` / shared security-epic (loop tip), CLI `--role` help / `--kind` — учат kind-aware start; feature-only path wording на hot docs убран.
- **FR-014:** Misconfig (два kind layout для одного epic_id) → fail-closed с требованием `--kind`, не silent pick feature.

### Success Criteria (SC-###)

| ID | Измеримый результат | Проверка / источник | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | start security epic без feature plan tree успешен | targeted pytest | outcome |
| SC-002 | finish aNN → next aNN / DONE | targeted pytest | outcome |
| SC-003 | invalid security yaml блокирует finish | targeted pytest | outcome |
| SC-004 | `_PHASE_GATE_AGENTS` содержит SECURITY→verify-security; agent file exists | unit + path exists | outcome |
| SC-005 | feature epic lifecycle AUDIT/QA **не** регрессирует | existing kernel tests green | outcome |
| SC-006 | Kind I: README/workflow упоминают security loop path | rg / review | outcome |

### Assumptions

- Шаблоны `epic-security/v1` уже канон; эпик добавляет runtime validate, не invent second schema name.
- DECOMPOSE для security по-прежнему пишет `security/plan/<id>/yaml/` (workflow уже так); loop только читает/валидирует дерево kind-aware.
- Feature ANALYZE перед IMPLEMENT остаётся обязательным.
- Cursor schema bump: добавить `kind` с default `feature` для старых cursor.json (migrate-friendly).

### Clarifications

- Session: 2026-10-24 · [clarify-20261024-loop-security-epic.md](../../clarify/clarify-20261024-loop-security-epic.md)
- Решено: DECOMPOSE→SECURITY→DONE; kind trio; verify-security; refactor path in-epic; S out of loop.

### [НУЖНО УТОЧНИТЬ]

- нет CRITICAL open.

## AC

1. `LoopEngine.start` на fixture security plan/index выставляет `kind=security` и корректную фазу.
2. `finish` SECURITY с валидным `epic-security/v1` закрывает step в index и двигает курсор.
3. После последнего aNN `phase=DONE`; AUDIT не требуется.
4. Невалидный/отсутствующий security execute yaml → finish denied.
5. Feature epic tests (IMPLEMENT→AUDIT path) остаются green.
6. `verify-security` agent file + gate map wired; CLI protocol lists security paths.
7. Refactor fixture start резолвит `refactor/plan/`.
8. Docs/README/workflow tip обновлены (Kind I).

### AC−

1. Нет sole hot-path `index_path` → только `…/plan/<epic>/` без kind.
2. Нет silent default `kind=feature` при однозначном security/refactor layout.
3. Нет finish SECURITY через verify-implement как единственный допустимый agent.
4. Нет dual machine path «prose audit md OR yaml» для epic finish.
5. Нет принудительного AUDIT/QA для `kind=security` после полной очереди aNN.
6. Нет optional SoT «security paths if flag» без enforce на start.

## Boundary / negative cases

| ID | Class | Input / condition | Expected (fail-closed) | Maps TM / AC |
|----|-------|-------------------|------------------------|--------------|
| BN-001 | empty / missing | start epic_id без plan ни в одном kind layout | FileNotFoundError с перечислением искавшихся roots | TM-001 |
| BN-002 | unknown / DENY old | finish SECURITY без execute yaml / wrong schema | TransitionError; index не completed | TM-003 |
| BN-003 | misconfig fail-closed | один epic_id существует и как feature, и как security | require `--kind`; без него error, не silent feature | TM-004 |
| BN-004 | wrong gate | SECURITY finish с agent_id verify-implement only | gate reject / TransitionError | TM-005 |
| BN-005 | post-queue | security queue complete | DONE, not AUDIT | TM-002 |

Checklist:

| # | Class | Status |
|---|-------|--------|
| 1 | empty / missing required | done — BN-001 |
| 2 | unknown key / DENY legacy SoT | done — BN-002 |
| 3 | max / overflow / unicode | n/a: epic_id validation already Path.name; no new unicode surface |
| 4 | authz / unauthenticated | n/a: local filesystem loop, no authz boundary |
| 5 | duplicate / idempotence | done — finish_duplicate already; kind ambiguity BN-003 |
| 6 | misconfig fail-closed (не stub) | done — BN-003, BN-004 |

**Notes:** table-driven parametrize kind ∈ {feature, refactor, security} для path resolve.

---

## Техника / архитектура (HOW)

- **Стек:** Python 3 · pydantic · yaml · существующий `CursorStore` transaction · hub `bin/pytest`
- **Модули:**
  - `loop/kernel/index.py` — `EpicKind`, `plan_root(kind)`, kind-aware `plan_path`/`index_path`/`execute_path` (rename/generalize `implement_path`), `discover_epic_kinds`, `resolve_epic_role`(+kind), `load_queue` uses resolved index
  - `loop/kernel/model.py` — `Cursor.kind` field; schema stay `loop-state/v2` with additive field (document default)
  - `loop/kernel/security_schema.py` — Pydantic `epic-security/v1` + `complete_security_artifact` (mirror implement_schema status machine)
  - `loop/kernel/creative.py` — `phase_for_pending_step` accepts kind → SECURITY for security pending (skip CREATIVE unless needs_creative; security templates say no)
  - `loop/kernel/engine.py` — `_PHASE_GATE_AGENTS`; `_target` skip ANALYZE for security; `_phase_after_queue` DONE for security; finish branch SECURITY like IMPLEMENT but security_schema + execute_path
  - `loop/kernel/cli.py` — `--kind`; gate protocol SECURITY; path lists kind-aware; PHASES prompt body
  - `loop/kernel/roadmap.py` — `plan_path` by next_kind
  - `loop/config.py` — PHASES += SECURITY; `security_model` / LOOP_MODEL_SECURITY
  - `harness/agents/verify-security.md` + codex toml/policy materialize as peers
  - Kind I: `loop/README.md`, `.cursor/rules/back_developer/workflow-security.mdc`, shared `workflow-security-epic.mdc` loop tip
- **Наблюдаемость:** existing transition events; add `kind` in status JSON / banner

## Eng review spine

### Data flow (ASCII)

```text
[operator CLI start --epic/--kind]
    -> [resolve kind + role] -> [CursorStore.write kind]
    -> [_target: DECOMPOSE | SECURITY aNN]
         sync
[agent SECURITY session]
    -> [write security/implement/.../aNN.yaml] (findings)
    -> [spawn verify-security] -> [boundary accept PASS]
    -> [loop.py finish]
         -> [security_schema.complete] -> [index status completed]
         -> [_target next aNN | DONE]
```

### Failure matrix

| Component / link | Failure | Detection | User/system response | Test ID |
|------------------|---------|-----------|----------------------|---------|
| kind resolve | ambiguous layouts | start | error ask `--kind` | TM-004 |
| kind resolve | missing all layouts | start | FileNotFoundError | TM-001 |
| security yaml | missing/invalid | finish | TransitionError | TM-003 |
| gate | wrong/missing PASS | finish | TransitionError | TM-005 |
| index write | step missing | finish | TransitionError | TM-002 |
| feature path | regression | pytest suite targeted+existing | fail CI | TM-006 |
| roadmap next | kind=security plan missing | advance | ValueError path security/plan | TM-007 |
| analyze skip | security forced ANALYZE | _target | must not require analyze | TM-002 |

### Eng spine self-check

| Dimension | Score 1–5 | Gap / action |
|-----------|-----------|--------------|
| Data flow complete | 5 | — |
| Failure coverage | 5 | BN+TM linked |
| Testability | 5 | tmp_path fixtures per kind |

## Replacement / sunset (brownfield)

### A. Code / modules

| Устаревает (path / symbol) | Замена | Policy |
| :--- | :--- | :--- |
| `index_path` / `plan_path` hardcode `…/plan/<id>/` only | kind-aware roots | delete in-epic (replace body) |
| `implement_path` sole feature implement/ | `execute_path(kind, …)` (alias keep name calling kind) | delete in-epic dual meaning |
| Engine assumption post-queue always AUDIT | branch on kind | delete in-epic |
| ANALYZE-before-work for all kinds | skip when kind=security | delete in-epic |

### B. Entrypoints / deploy

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| CLI help «discover under …/plan/<epic>» only | mention security/refactor roots + `--kind` | delete in-epic |
| n/a compose | — | n/a |

### C. Fallbacks / soft-fail

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| Silent pick feature when security also exists | require `--kind` | delete in-epic |
| Finish security via implement schema «if looks like yaml» | security_schema only | delete in-epic |

### I. Instruction surfaces

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| `loop/README.md` feature-only arm examples | + security epic arm / DONE rule | delete in-epic |
| `workflow-security.mdc` «Epic loop» prose without kind paths | concrete `bin/loop.py` + kind | delete in-epic |
| shared `workflow-security-epic.mdc` loop tip | same | delete in-epic |

<a id="qa-consumes"></a>
## QA consumes (test plan)

### Scope under test

- Epic: kind resolve, SECURITY finish/advance, verify-security wiring, refactor path, feature non-regression
- Out of scope for QA: actual OWASP audit quality of a product app; S one-shot markdown audits

### Test matrix

| ID | Priority | Scenario | Command / fixture | Expected | Maps FR/AC |
|----|----------|----------|-------------------|----------|------------|
| TM-001 | P0 | start missing all kinds | `bin/pytest loop/tests/ -k security_kind_missing` | FileNotFoundError lists roots | FR-001, BN-001, AC-1 |
| TM-002 | P0 | security two-step finish → DONE | `-k security_finish_advance` | a01→a02→DONE | FR-003–006, BN-005, AC-2,3 |
| TM-003 | P0 | finish invalid security yaml | `-k security_finish_invalid` | TransitionError | FR-005, BN-002, AC-4 |
| TM-004 | P0 | ambiguous feature+security | `-k security_kind_ambiguous` | requires --kind | FR-014, BN-003, AC− |
| TM-005 | P0 | gate map + wrong agent | `-k security_gate_agent` | SECURITY→verify-security; wrong denied | FR-007–008, BN-004, AC-6 |
| TM-006 | P0 | feature IMPLEMENT path untouched | existing `-k` finish implement / audit | green | SC-005, AC-5 |
| TM-007 | P1 | roadmap next_kind security path | `-k roadmap_security_plan` | looks under security/plan | FR-010 |
| TM-008 | P1 | refactor start path | `-k refactor_kind_path` | refactor/plan index | FR-011, US-004 |
| TM-009 | P1 | PHASES / LOOP_MODEL_SECURITY | `-k security_phase_model` | SECURITY in PHASES | FR-009 |

### Regression notes

- Не гонять full suite в IMPLEMENT; QA hub full `bin/pytest -q --tb=line`
- Fixtures изолировать tmp_path memory-bank trees

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| CLARIFY / Product probe | L3 | done | clarify-20261024 + §Product probe |
| Eng review spine | L2+ | done | §Eng review spine |
| §0.11 counterparts (draft) | if external | done | agent file ↔ gate map ↔ CLI protocol |
| Delivery closure | P0 | done | §Delivery closure |
| Boundary / negative cases | L2+ | done | ≥3 BN + checklist |
| CREATIVE | if flagged | n/a | CREATIVE need: нет |
| qa_consumes draft | L2+ | done | ≥3 TM; BN→TM |
| Plan review batch | L2+ | done | §Plan review batch log |

## Plan review batch log

| Phase | Auto-resolved | Deferred (owner/next) | Taste / CRITICAL surfaced |
|-------|---------------|-------------------------|---------------------------|
| Product | Pipeline DONE без QA; S out of loop; single epic | — | none |
| Eng | Additive Cursor.kind; security_schema mirror implement; refactor post-queue = feature | — | none |

## До DECOMPOSE (черновик нарезки)

Hint only (final count = DECOMPOSE Effort probe):

1. **s01** — EpicKind + path resolve + Cursor.kind + discover/ambiguous + tests TM-001/004/008  
2. **s02** — security_schema.py + finish SECURITY complete artifact + tests TM-003  
3. **s03** — engine _target/_phase_after_queue SECURITY + skip ANALYZE + DONE; tests TM-002  
4. **s04** — verify-security agent + gate map + CLI protocol + PHASES/model; tests TM-005/009  
5. **s05** — roadmap next_kind path + Kind I README/workflow-security; tests TM-007  
6. **s06** — legacy-fallback-purge: rg feature-only index_path hardcode on hot path = 0; feature regression TM-006  

## Appetite

| Поле | Значение | Описание |
| :--- | :--- | :--- |
| `timebox_days` | `3` | Kind + SECURITY vertical slice + Kind I |
| `cut_list` | `['auto-suggest kind in doctor UX', 'FRONT/INTEG-specific security prompt skins beyond shared paths', 'migrate historical security-audit md into yaml']` | Вырезать первым при overrun |

## Следующий режим

→ **BACK DECOMPOSE** `T-HUB-107-loop-security-epic-pipeline`
