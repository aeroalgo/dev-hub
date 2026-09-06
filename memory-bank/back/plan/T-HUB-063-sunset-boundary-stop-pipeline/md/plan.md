# [T-HUB-063 | sunset-boundary-stop-pipeline] PLAN

**Дата:** 2026-09-05  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** active  
**Prompt:** [md/prompt.md](prompt.md) — `## Epic` + `## Covering`  
**Clarify:** `memory-bank/back/clarify/clarify-20260905-workflow-loop-audit.md`  
**Roadmap:** `memory-bank/back/roadmap/queue.yaml` · batch `workflow-loop-20260905`  
**Deps:** soft T-HUB-058 (agent+schema model already planned/partially present), T-HUB-057 (JSON fence SoT). Hard нет на 058 — leftover **runtime pipeline** можно закрыть на текущем as-built `SunsetReport`.  
**Skills:** writing-plans · python-testing-patterns · architecture-patterns  
**Источник:** audit `04-schemas-validation.md` P0 · `05-repair-and-verdict.md` · `01-subagents-prompts.md` sunset

→ decompose-index — [md/decompose-index.md](decompose-index.md) · [yaml/decompose-index.yaml](../yaml/decompose-index.yaml)

---

## Контекст

- **req:** `sunset-inventory` заявляет machine JSON `loop-sunset-inventory/v1`. Этот schema_id обязан проходить тот же pipeline, что gate/repair: registry → parse fence → pydantic → ownership → sidecar/state → parent consume. Сейчас модель есть, registry и SubagentStop branch — нет → `schema_unknown_schema_id` на валидном payload.
- **gap (as-built 2026-09-05):**
  1. `loop/schemas/sunset_inventory.py` определяет `SunsetReport`; `BOUNDARY_REGISTRY` содержит только mb-load, gate, repair, validate-result (4 ids).
  2. `validate_boundary("loop-sunset-inventory/v1", payload)` → `schema_unknown_schema_id`.
  3. `SubagentStop` не имеет sunset validation branch (08 matrix: sunset start partial, stop no, schema none).
  4. Tests: `SunsetReport.model_validate` unit only, не e2e boundary/hook.
  5. T-HUB-058 plan обещает schema+agent; **не гарантирует** registry+stop (аудит после плана 058). Этот эпик = leftover **wire**, не rewrite agent prompt.
- **refs:** `loop/schemas/boundary_registry.py`; `loop/schemas/sunset_inventory.py`; `harness/hooks/subagent-stop.py`; `harness/agents/sunset-inventory.md`; plan T-HUB-058; audit 04 §2, 08 §2–3.
- **Не этот эпик:** skill FS (062); video agents (064); ownership v2 для gate (066, но sunset должен получить **минимум** schema+agent_id+scope); transactional finish (068).

**CREATIVE need:** нет.

---

## Technology axiom (replace-not-wrap)

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Sunset report | fenced JSON `schema: loop-sunset-inventory/v1` → registry model | free-text inventory как SoT; `validate_boundary` unknown id |
| Stop path | SubagentStop branch для `sunset-inventory` same parser as gate | skip validation because «search agent» |
| Missing fence | protocol FAIL / retry policy documented | accept payload `data.verdict` analog / prose |
| Optional sunset | **нет**: если agent managed — pipeline обязателен | «schema есть, hook потом» |

As-built unknown schema_id — sunset inventory (дыра), не шаблон «unit model_validate достаточно».

---

## Продуктовая спека (WHAT)

1. Valid sunset JSON проходит CLI `validate-boundary --schema-id loop-sunset-inventory/v1 --json '…'` → `valid: true`.
2. Malformed / extra / unknown id → fail-closed diagnostic, не silent.
3. SubagentStop для `sunset-inventory` парсит fence, валидирует, persist sidecar или typed result parent может прочитать.
4. Нет пути «модель зелёная, hook не знает schema».

### Product probe

| # | Question | Answer / Probe | Decision / Impact on PLAN |
|---|----------|----------------|---------------------------|
| 1 | **Reframe:** | Sunset agent врёт, что JSON проверяется | Registry + stop, не ещё один prompt |
| 2 | **Narrowest wedge:** | Register schema + stop branch + 1 pos + 1 neg test | P0 |
| 3 | **Pre-mortem:** | Регистрируют schema, stop всё ещё skip | FR на hook branch + matrix row |
| 4 | **Adoption:** | Parent 058 spawn начинает получать validate errors честно | Kind I agent prompt если CLI flag drift |
| 5 | **Leverage:** | Copy gate/repair stop pattern | Не новый validator framework |
| 6 | **Appetite:** | 3 дня | cut: auto-write sunset tables into plan.md |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как parent, я хочу `validate_boundary` принять корректный SunsetReport. | P0 | CLI/pytest valid:true |
| US-002 | Как hook, я хочу SubagentStop отвергнуть sunset без fence. | P0 | fixture transcript no fence → retry/block, не persist |
| US-003 | Как parent, я хочу sidecar/result после valid sunset, чтобы строить deletes. | P0 | file or state key exists with schema_id |
| US-004 | Как CI, я хочу unknown schema_id больше не быть единственным ответом на valid sunset. | P0 | before/after pytest |

#### Acceptance Scenarios — US-001

- **Given:** payload with `schema: loop-sunset-inventory/v1` and required SunsetReport fields, `extra` forbid
- **When:** `validate_boundary` / CLI `--json`
- **Then:** `valid: true`; extra field → fail; wrong id → `schema_unknown` only for truly unknown ids

#### Acceptance Scenarios — US-002

- **Given:** sunset-inventory subagent completion text without JSON fence
- **When:** SubagentStop
- **Then:** not recorded as success; retry or NEED_HUMAN per policy; no sidecar «ok»

### Functional Requirements (FR-###)

- **FR-001:** `BOUNDARY_REGISTRY[SCHEMA_LOOP_SUNSET_INVENTORY] = SunsetReport` (или WireSunsetReport с required schema).
- **FR-002:** Export schema id constant used by agent prompt **and** registry (one string).
- **FR-003:** `validate_boundary` positive/negative tests in `loop/tests/test_boundary_registry.py` / `test_validate_boundary.py`.
- **FR-004:** SubagentStop: agent id `sunset-inventory` → extract fence → validate_boundary sunset schema.
- **FR-005:** Persist result (sidecar path convention same family as gate, documented) **or** explicit typed in-memory + parent-readable file; not log-only.
- **FR-006:** Malformed → schema retry count documented (0 or 1; sunset is search — prefer 1 retry then NEED_HUMAN). Semantic empty inventory is **valid** (zero items).
- **FR-007:** Prompt `harness/agents/sunset-inventory.md` schema_id совпадает с registry (Kind I if drift).
- **FR-008:** 08 matrix row sunset: Start inject yes, Stop parse yes, Schema sunset, sidecar yes.
- **FR-009:** Codex collab parser, если отдельный — same schema id (soft: если 066 owns collab, минимум registry shared).
- **FR-010:** Не удалять sunset machine contract; «удалить schema из prompt» = только если registry path rejected — **не** выбран (audit preferred include).

### Success Criteria (SC-###)

| ID | Измеримый результат | Проверка | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | registry contains sunset id | pytest | outcome |
| SC-002 | valid payload CLI valid true | CLI | outcome |
| SC-003 | stop without fence ≠ success | hook test | outcome |
| SC-004 | 08-style matrix row green | test or doc+test | outcome |

### Assumptions

- `SunsetReport` fields already good enough to register; if Wire needs required `schema`, add wrapper in-epic.
- Agent file already in manifest (as-built manifest **has** sunset-inventory). Gap is registry+stop, not materialize.

### Clarifications

- Phase 0 done. Leftover vs 058: this epic **wires** pipeline even if 058 DECOMPOSE not started.

## AC

1. `loop-sunset-inventory/v1` in BOUNDARY_REGISTRY.
2. CLI validate success on fixture report (zero and non-zero items).
3. SubagentStop validates sunset; no-fence fails.
4. Parent-readable persisted result.

### AC−

1. Нет dual path unit-only validate vs hook skip.
2. Нет silent `schema_unknown` на каноническом id.
3. Misconfig (wrong schema id in prompt) → fail validate, не prose accept.
4. Нет optional SoT «модель есть, hook нет».
5. Нет extra=ignore на sunset wire.

## Техника / архитектура (HOW)

- Files: `loop/schemas/boundary_registry.py`, `loop/schemas/sunset_inventory.py`, `harness/hooks/subagent-stop.py`, tests `loop/tests/test_validate_boundary.py`, `harness/hooks/tests/` sunset stop.
- Pattern: copy repair/gate branch structure; sunset not a finish agent (`VERIFY_MB_FINISH` не включать).
- Sidecar: `.claude/runtime/epic/sunset-<session>-<step>.json` or existing evidence dir — DECOMPOSE pick one existing convention.

## Eng review spine

### Data flow (ASCII)

```text
[sunset-inventory agent] -> [JSON fence] -> [SubagentStop extract]
         sync                  fail-closed        -> [validate_boundary sunset]
                                                   -> [sidecar] -> [parent deletes]
```

### Failure matrix

| Component / link | Failure | Detection | Response | Test ID |
|------------------|---------|-----------|----------|---------|
| unknown schema_id leftover | CLI unknown | pytest registry | register | TM-001 |
| extra fields | pydantic extra=forbid | validate | fail | TM-002 |
| no fence | stop skip historically | stop test | retry/NEED_HUMAN | TM-003 |
| empty items valid | false fail | fixture zero items | valid true | TM-004 |
| persist fail | IO | hook | fail-closed not swallow | TM-005 |
| wrong agent id | mapped to gate schema | mapping test | sunset branch only | TM-006 |
| Codex collab extra=ignore | silent extra | 066/this | forbid or follow-up 066 | TM-007 |

### Eng spine self-check

| Dimension | Score 1–5 | Gap / action |
|-----------|-----------|--------------|
| Data flow complete | 5 | |
| Failure coverage | 5 | |
| Testability | 5 | fixtures no LLM |

## Replacement / sunset

### A. Code / modules

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| BOUNDARY_REGISTRY without sunset | + SunsetReport | delete in-epic (the gap) |
| Stop path that ignores sunset agent | dedicated branch | delete in-epic |
| tests only model_validate | e2e validate_boundary + stop | rewrite in-epic |

### B. Entrypoints / deploy

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| `validate-boundary` unknown for sunset | known id | delete in-epic |

### C. Fallbacks / soft-fail

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| skip sunset because not verify | validate anyway | delete in-epic |
| swallow persist exception | raise/NEED_HUMAN | delete in-epic |

### I. Instruction surfaces

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| prompt «schema validated» while registry missing | truthful pipeline | delete in-epic |
| audit 08 matrix «currently no» | update after green (docs optional) | keep audit historical |

## QA consumes

<a id="qa-consumes"></a>

### Scope

- registry, validate_boundary, SubagentStop sunset, sidecar
- Out: skill layout; video; finish_handoff

### Test matrix

| ID | Priority | Scenario | Command | Expected | Maps |
|----|----------|----------|---------|----------|------|
| TM-001 | P0 | registry has sunset | `bin/pytest loop/tests/test_boundary_registry.py -q --tb=line -k sunset` | PASS | FR-001 |
| TM-002 | P0 | valid zero items | validate-boundary CLI | valid true | US-001 |
| TM-003 | P0 | extra field | CLI | valid false | AC− |
| TM-004 | P0 | stop no fence | hook test | not success | US-002 |
| TM-005 | P0 | valid stop persist | hook test | sidecar exists | US-003 |
| TM-006 | P1 | non-zero items | fixture | valid true | FR-003 |

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| CLARIFY / Product probe | L3 | done | clarify + probe |
| Eng review spine | L2+ | done | filled |
| §0.11 | n/a | n/a | |
| CREATIVE | n/a | n/a | |
| qa_consumes | L2+ | done | ≥3 P0 |
| Plan review batch | L2+ | done | below |

## Plan review batch log

| Phase | Auto-resolved | Deferred | Taste |
|-------|---------------|----------|-------|
| Product | Include pipeline, don't delete schema | auto-write plan tables | |
| Eng | Copy gate stop pattern | collab extra=ignore → 066 | |

## До DECOMPOSE

1. s01 — registry + red tests unknown→known.
2. s02 — validate_boundary pos/neg fixtures.
3. s03 — SubagentStop branch + no-fence.
4. s04 — persist sidecar + parent read helper if missing.
5. s05 — Kind I prompt schema_id + purge skip-path.
6. s06 — purge leftover comments/tests that encode unknown id as expected for canonical sunset.

## Appetite

| Поле | Значение | Описание |
| :--- | :--- | :--- |
| `timebox_days` | `3` | |
| `cut_list` | `['auto-fill plan sunset tables', 'MCP sunset tool']` | |

## Independent Test

- PASS: CLI valid true; stop no-fence fails; sidecar present.
- FAIL: «SunsetReport.model_validate in unit» only.

## Следующий режим

→ BACK DECOMPOSE after 062 (deps: none hard; queue order 062 then 063).

**CREATIVE need:** нет.
