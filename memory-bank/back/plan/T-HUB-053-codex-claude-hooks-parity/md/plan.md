# [T-HUB-053 | codex-claude-hooks-parity] PLAN

**Дата:** 2026-09-02  
**Режим:** BACK PLAN  
**Уровень:** L3–L4  
**Статус:** active  
**Clarify:** Phase 0 skipped — taxonomy clear (chat 2026-09-02 зафиксировал axiom Codex ≡ Claude Code по hooks/agents/gates; inventory Claude vs Codex выполнен)  
**Roadmap:** [roadmap-harness-universal-runtime-epics.md](roadmap-harness-universal-runtime-epics.md)  
**Queue (slug):** [roadmap-harness-universal-runtime-epics.queue.yaml](roadmap-harness-universal-runtime-epics.queue.yaml)  
**Deps:** **hard** T-HUB-043 (manifest + CodexAdapter + hooks generator; done), **T-HUB-057** (loop session JSON contract), **T-HUB-058** (sunset-inventory agent — canon: 054→…→057→058→053). **Soft:** T-HUB-044 (doctor/runbook surface), T-HUB-021 (bash-output-cap structured LLM).

**Skills:** writing-plans · architecture-patterns · python-testing-patterns · diagnosing-bugs

→ [T-HUB-053-codex-claude-hooks-parity/md/decompose-index.md](T-HUB-053-codex-claude-hooks-parity/md/decompose-index.md) — **после DECOMPOSE**

---

## Контекст

### Источник (чат 2026-09-02)

1. Оператор спросил статус `bash-output-cap` (LLM-сокращение Bash stdout) — hook живёт в Claude PostToolUse; на Codex **не** зарегистрирован.
2. Оператор зафиксировал **Technology axiom:** Codex runtime **обязан** работать **идентично** Claude Code по вызовам сабагентов, вердиктам, start/finish gate и всей hook-поверхности вокруг workflow.
3. Задача: BACK PLAN полного паритета; поставить эпик **после T-HUB-045** в очереди universal-runtime / canon.

### As-built gap (sunset inventory, не шаблон)

| Слой | Claude (`.claude/settings.json`) | Codex (`.codex/hooks.json` сейчас) |
|------|----------------------------------|-------------------------------------|
| SessionStart | `session-start.py` | **нет** |
| UserPromptSubmit | `user-prompt.py` | **нет** |
| PreToolUse Agent\|Task | `agent-pretool.py` | есть (без matcher-паритета) |
| PreToolUse Bash | `bash-pretool.py` | **нет** |
| PostToolUse Agent\|Task | `agent-posttool.py` | **нет** |
| PostToolUse Bash | `bash-output-cap.py` (+ `llm_structured`) | **нет** |
| SubagentStart | `subagent-start.py` | **нет** |
| SubagentStop | `subagent-stop.py` | есть |
| Stop | `stop-gate.py` | есть |
| Agents verify*/gate-repair/explorer | materialize `.md` | materialize `.toml` (043) — **оставить**, расширить только если Claude set шире |
| Manifest `hooks:` codex flags | полный Claude shell | только 3 rows: stop-gate, subagent-stop, agent-pretool |
| Generator `EVENT_MAPPING` | — | неполный; нет matcher / nested Claude-shape |

**refs:** `harness/manifest.yaml`, `loop/runtime_materializers/hooks_json.py`, `.claude/settings.json`, `.codex/hooks.json`, `harness/hooks/{session-start,user-prompt,agent-pretool,agent-posttool,bash-pretool,bash-output-cap,subagent-start,subagent-stop,stop-gate}.py`, plan-T-HUB-043, plan-T-HUB-021, docs OpenAI Codex Hooks (SessionStart/SubagentStart/PreToolUse/PostToolUse/Stop — native).

### Зафиксированные решения

| Тема | Решение |
|------|---------|
| Axiom | **Codex ≡ Claude Code** для workflow hooks + agents + gate verdict semantics |
| SoT | Один `harness/hooks/*.py` + `harness/agents/*`; runtime shells только materialize |
| Registration | `.codex/hooks.json` **generated** из manifest (не hand-edit); расширить generator под **полную** Claude event matrix + matchers |
| Unsupported native API | Если конкретный Codex capability (например `updatedToolOutput`) отсутствует — **adapter/bridge emulation** в том же semantics path, **fail-closed** (не silent skip FR) |
| Cursor IDE Codex | **out of scope** (как в 043) — только `EPIC_RUNTIME=codex` / Codex CLI hooks |
| DSH | не цель этого эпика; не регрессить Claude/DSH |
| Queue position | **после T-HUB-045** (canon: после 044, перед 046; soft dep 045) |

**CREATIVE need:** нет (паритет известной поверхности; payload adapter — engineering, не UX).

---

## Technology axiom (replace-not-wrap)

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Hook registration Codex | generated `.codex/hooks.json` from `harness/manifest.yaml` с **полным** Claude event set | hand-maintained subset; «codex не умеет → просто не регистрируем» без bridge epic row |
| Gate / spawn / finish | те же Python hooks + `loop-gate-verdict/v1` JSON fence | отдельная codex-policy / prose VERDICT regex |
| Bash output summary | `bash-output-cap.py` → `llm_structured.LogSummary` (T-HUB-021 path) | urllib free-text dual path; Claude-only registration |
| Event names | Claude/Codex shared lifecycle names (`SessionStart`, `PreToolUse`, …) | invent parallel event ids per runtime |
| Matcher groups | nested Claude-shaped hooks.json (matcher + hooks[]) где Codex schema требует | flat list без matcher, если Claude имеет matcher (разный tool scope) |

---

## Продуктовая спека (WHAT)

### Product probe

| # | Question | Answer | Impact |
|---|----------|--------|--------|
| 1 | Reframe | Operator думает, что `EPIC_RUNTIME=codex` = тот же workflow safety net, что Claude; фактически subset → FINISH/spawn/session/bash-cap расходятся | Полный hooks parity |
| 2 | Wedge | Manifest + generator + regenerated hooks.json + behavior tests на каждый missing Claude hook | Не переписывать hook bodies |
| 3 | Pre-mortem | Generator пишет events, которых Codex schema не принимает / payload drift → hooks silent no-op | Contract tests + doctor check; fail-closed на drift |
| 4 | Adoption | После 044 runbook: sync --apply + pilot checklist строка «hooks parity matrix green» | Docs patch in-epic |
| 5 | Leverage | Codex docs: те же event names; reuse hub Python; 043 already generates hooks.json | Extend EVENT_MAPPING + matchers |
| 6 | Appetite | L3–L4, ~5–8 дней | cut: SessionEnd/PermissionRequest/PreCompact (Claude тоже не использует в settings) |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как parent на `EPIC_RUNTIME=codex`, я хочу stop-gate + spawn-gate + subagent start/stop с теми же deny/allow, что на Claude. | P0 | Fixture: FINISH без verify → deny; spawn verify без HARD RULE → deny; SubagentStart/Stop вызывают harness scripts |
| US-002 | Как parent, я хочу SessionStart inject (mb-load / epic context) на codex так же, как на Claude. | P0 | SessionStart hook registered + smoke inject path non-empty / expected marker |
| US-003 | Как parent, я хочу Bash output-cap (extract → structured LLM → head-tail) на codex PostToolUse Bash. | P0 | Oversized Bash tool_response → updated/capped view + dump path; mode label extract\|structured\|head-tail |
| US-004 | Как maintainer, я хочу `runtime-sync --check` падать, если Codex hooks subset ≠ Claude required matrix. | P0 | Remove one required hook from generated file / manifest flag → check exit ≠ 0 |
| US-005 | Как operator, я хочу в runbook/doctor явную матрицу Claude↔Codex hooks parity. | P1 | Doctor assertion или docs table + test that lists required events |

#### Acceptance Scenarios — US-001

- **Given:** codex runtime session, IMPLEMENT, `need_verify=true`, verify not PASS  
- **When:** Stop / FINISH  
- **Then:** `stop-gate.py` deny (same decision semantics as Claude fixture)

- **Given:** PreToolUse Agent spawn `@verify-implement` without HARD RULE line  
- **When:** agent-pretool runs  
- **Then:** DENY (same as Claude)

#### Acceptance Scenarios — US-002

- **Given:** `EPIC_RUNTIME=codex` SessionStart  
- **When:** session begins  
- **Then:** `session-start.py` runs; inject path consistent with Claude (mb-load / additionalContext)

#### Acceptance Scenarios — US-003

- **Given:** PostToolUse Bash with stdout > soft/hard cap  
- **When:** `bash-output-cap.py` executes  
- **Then:** model-facing output capped; full dump under `.claude/runtime/bash-dumps/` (or runtime-equivalent path); mode in additionalContext

### Functional Requirements

- **FR-001:** Manifest `hooks:` объявляет **все** Claude-settings hooks с `runtimes.codex.hooks_json_entry: true` (или явный `out_of_scope` + follow-up epic уже в queue — по умолчанию **все in-scope**).
- **FR-002:** Required Codex event set ⊇ Claude settings set: SessionStart, UserPromptSubmit, PreToolUse (Agent\|Task + Bash), PostToolUse (Agent\|Task + Bash), SubagentStart, SubagentStop, Stop.
- **FR-003:** `hooks_json.py` генерирует nested Claude-shaped `.codex/hooks.json` с matchers, эквивалентными `.claude/settings.json` (tool/agent matchers).
- **FR-004:** Один Python entrypoint на hook role — path `harness/hooks/<name>.py` (не fork под codex).
- **FR-005:** Payload adapter (если stdin Codex ≠ Claude): **thin** normalize в hook/`_lib` до shared logic; dual business path FORBIDDEN.
- **FR-006:** Bash output-cap на Codex использует тот же `PROJECT_OUTPUT_SUMMARY*` env + structured path (021).
- **FR-007:** Agents set на Codex ⊇ Claude managed agents для loop (verify-*, gate-repair, explorer, analyze-verify); gap → materialize row.
- **FR-008:** `runtime-sync --check` + doctor: parity matrix fail-closed при missing event/command.
- **FR-009:** Integration tests: extend `test_codex_hooks_bridge.py` (+ dedicated parity matrix test) — behavior, не только «ключ в json».
- **FR-010:** Docs: update `docs/runbooks/codex-loop-pilot.md` + architecture/services row — матрица паритета.
- **FR-011:** Timeout policy: Bash PostToolUse timeout ≥ Claude (45s) в generated hooks; прочие как Claude.
- **FR-012:** Out of scope hooks (SessionEnd, PermissionRequest, Pre/PostCompact) — не добавлять, пока нет в Claude settings (не расширять scope «на будущее»).

### Success Criteria

| ID | Измеримый результат | Проверка | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | Generated `.codex/hooks.json` содержит все FR-002 events + matchers | `test_codex_hooks_parity_matrix` | outcome |
| SC-002 | stop/spawn/subagent start-stop behavior parity fixtures green | pytest bridge suite | outcome |
| SC-003 | bash-output-cap invoked path covered for codex registration + unit path | pytest + matrix | outcome |
| SC-004 | `runtime-sync --check` fails on missing required hook | pytest | outcome |
| SC-005 | Doctor/runbook document parity matrix | file assert / doctor test | outcome |

### Assumptions

- Codex CLI version in PATH поддерживает documented lifecycle events (SessionStart, SubagentStart, PostToolUse, …). Pin/min version зафиксировать в AC/doctor если probe покажет drift.
- Nested `hooks` wrapper schema (как в текущем `.codex/hooks.json` и OpenAI docs) — канон; если live CLI требует root-level events — generator emits **одну** schema version + fail-closed probe, не dual emit.
- Payload shape mostly Claude-compatible; normalize only proven deltas.
- T-HUB-044 может быть ещё в BUGFIX; docs FR этого эпика **дополняет** pilot runbook, не ждёт ARCHIVE 044.

### Clarifications

- Session: 2026-09-02 chat (operator axiom + bash-cap discovery).  
- Phase 0 Clarify artifact: **не создавался** — taxonomy Clear по scope/axiom; remaining HOW = Codex schema probe in IMPLEMENT s01.

### [НУЖНО УТОЧНИТЬ]

- нет CRITICAL. Soft defer: exact min Codex CLI version → IMPLEMENT probe + doctor pin (owner: IMPLEMENT s01).

## AC

1. `.codex/hooks.json` после `runtime-sync --apply` содержит полный Claude hooks event matrix (FR-002) с командами на `harness/hooks/*.py`.
2. Behavior tests: stop-gate deny, agent-pretool deny, subagent-start/stop wired, bash-output-cap path registered — green.
3. `runtime-sync --check` + doctor падают на subset drift.
4. Нет hand-edited `.codex/hooks.json` как SoT (GENERATED header / meta hash).
5. Claude settings / DSH не регрессируют.

### AC−

1. Нет второго codex-only spawn/stop policy рядом с harness hooks.
2. Нет «missing event → silent PASS / skip FR».
3. Нет dual LLM summarize path (free-text + structured) для output-cap.
4. Нет prod dual registration (hand json + generated) без purge.
5. Misconfig / unsupported capability without bridge → **fail-closed** (doctor/check), не stub success.

---

## Техника / архитектура (HOW)

- **Стек:** Python 3.12, существующие `harness/hooks`, `loop/runtime_materializers/hooks_json.py`, `bin/runtime-sync`, pydantic-ai output-cap (021), Codex CLI hooks.
- **Модули:**
  - `harness/manifest.yaml` — добавить rows: `session-start`, `user-prompt`, `bash-pretool`, `agent-posttool`, `bash-output-cap`, `subagent-start` (+ сохранить stop/subagent-stop/agent-pretool).
  - `loop/runtime_materializers/hooks_json.py` — расширить `EVENT_MAPPING`; поддержка **matcher** + nested groups; timeouts; не перезаписывать один event несколькими hooks без merge list.
  - Возможно `loop/runtime_materializers/hooks_parity.py` — declarative Claude↔Codex required matrix для check/doctor.
  - Tests: `loop/tests/test_hooks_json_generator.py`, `test_codex_hooks_bridge.py`, new `test_codex_hooks_parity_matrix.py`, bash-output-cap registration assert.
  - Docs: `docs/runbooks/codex-loop-pilot.md`, `memory-bank/architecture/services.md`, roadmap universal-runtime §0.
- **Payload normalize:** если Codex tool names отличаются (`shell` vs `Bash`) — matcher aliases + `_lib` normalize `tool_name` до shared hook logic.
- **Observability:** DEBUG env уже в output-cap; doctor prints missing events list.

## Eng review spine

### Data flow (ASCII)

```text
[Codex CLI event]
    -> [.codex/hooks.json generated]
    -> [python3 harness/hooks/<hook>.py]
    -> [_lib normalize stdin if needed]
    -> [shared gate / cap / inject logic]
    -> [stdout decision | updatedToolOutput | additionalContext]
         sync; fail-closed on deny / misconfig
[runtime-sync --check] -> [parity matrix] -> exit 0|1
[doctor] -> same matrix subset
```

### Failure matrix

| Component / link | Failure | Detection | User/system response | Test ID |
|------------------|---------|-----------|----------------------|---------|
| Missing hooks.json event | subset vs Claude | runtime-sync --check | non-zero; list missing | TM-001 |
| Manifest flag off for required hook | incomplete materialize | parity matrix | check fail | TM-001 |
| stop-gate not fired / wrong path | FINISH without verify PASS | bridge test | deny expected | TM-002 |
| agent-pretool not on PreToolUse | illegal spawn | bridge test | DENY | TM-003 |
| SubagentStart absent | no start contract | matrix + smoke | check fail / test fail | TM-004 |
| bash-output-cap absent | huge stdout floods context | matrix + cap unit | check fail | TM-005 |
| Payload tool_name mismatch | matcher miss | normalize + matcher aliases | fail-closed log / deny miss detected in test | TM-006 |
| Codex CLI too old for event | event ignored | doctor version pin | fail-closed preflight | TM-007 |
| Dual hand-edit hooks.json | drift | meta hash check | --check fail | TM-008 |

### Eng spine self-check

| Dimension | Score 1–5 | Gap / action |
|-----------|-----------|--------------|
| Data flow complete | 5 | — |
| Failure coverage | 5 | version pin in IMPLEMENT |
| Testability | 5 | matrix + behavior fixtures |

## Replacement / sunset (brownfield)

### A. Code / modules

| Устаревает (path / symbol) | Замена | Policy |
| :--- | :--- | :--- |
| Incomplete `EVENT_MAPPING` (только 5 keys) | full Claude matrix mapping + matchers | delete in-epic (replace mapping) |
| Manifest без codex flags на session/bash/post/start hooks | full flags | delete in-epic (extend) |
| Hand-subset mental model «codex partial OK» | parity matrix required | delete in-epic (docs + tests) |

### B. Entrypoints / deploy

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| Operator hand-edit `.codex/hooks.json` to add hooks | `runtime-sync --apply` | delete in-epic (docs forbid) |
| Partial bridge documented as done in 043 for «semantics unchanged» without full matrix | 053 matrix as SoT | delete in-epic (docs update) |

### C. Fallbacks / soft-fail

| Устаревает | Замена (fail-closed) | Policy |
| :--- | :--- | :--- |
| Silent skip missing Codex event | doctor/check non-zero | delete in-epic |
| «partial» ok for PostToolUse Bash on codex | required registration | delete in-epic |

<a id="qa-consumes"></a>
## QA consumes (test plan)

### Scope under test

- Epic surfaces: generated `.codex/hooks.json`, manifest hooks rows, parity check/doctor, stop/spawn/subagent/session/bash-cap wiring for codex.
- Out of scope for QA: Cursor IDE Codex; DSH bridge Gap A; changing Claude hook business logic (regression only).

### Test matrix

| ID | Priority | Scenario | Command / fixture | Expected | Maps FR/AC |
|----|----------|----------|-------------------|----------|------------|
| TM-001 | P0 | Parity matrix: all FR-002 events present after sync | `bin/pytest loop/tests/test_codex_hooks_parity_matrix.py` | PASS | FR-001..003, AC-1, AC-3 |
| TM-002 | P0 | stop-gate deny without verify on codex path | `test_codex_hooks_bridge` stop fixture | deny | US-001, FR-004 |
| TM-003 | P0 | agent-pretool DENY incomplete prompt | bridge / agent hooks test | DENY | US-001 |
| TM-004 | P0 | SubagentStart + SubagentStop registered + callable | parity + smoke invoke | exit 0 / registered | FR-002 |
| TM-005 | P0 | bash-output-cap in PostToolUse Bash + oversized fixture | unit/integration | capped view | US-003, FR-006 |
| TM-006 | P0 | matcher/tool_name alias Bash\|shell | fixture | hook fires | FR-005 |
| TM-007 | P1 | doctor fails on missing event | doctor test | non-zero / assertion | FR-008 |
| TM-008 | P0 | runtime-sync --check drift | touch/remove event | exit 1 | FR-008, US-004 |
| TM-009 | P1 | Claude settings regression unchanged required hooks | settings snapshot test / rg | still present | AC-5 |

### Regression notes

- Не мокать LLM в cap tests по умолчанию — extract/head-tail path; structured path mock `run_log_summary`.
- Ordering: generate hooks → check → behavior invoke.
- Env: `PROJECT_OUTPUT_SUMMARY` для cap tests изолировать.

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| CLARIFY / Product probe | L3 | done | §Product probe (Phase 0 skip — chat axiom) |
| Eng review spine | L2+ | done | §Eng review spine |
| §0.11 counterparts (draft) | yes | done | HOW modules ↔ tests/docs |
| CREATIVE | no | n/a | CREATIVE need: нет |
| qa_consumes draft | L2+ | done | ≥3 TM P0 |
| Plan review batch | L2+ | done | §Plan review batch log |

## Plan review batch log

| Phase | Auto-resolved | Deferred (owner/next) | Taste / CRITICAL surfaced |
|-------|---------------|-------------------------|---------------------------|
| Product | Codex ≡ Claude full hooks; after 045; Cursor out; SessionEnd etc out | Min Codex CLI version pin → IMPLEMENT s01 | none CRITICAL |
| Eng | Extend generator+manifest; thin payload normalize; parity matrix check | Live probe updatedToolOutput support → emulate if needed in-epic | Prefer one schema emit |

## До DECOMPOSE (черновик нарезки)

1. **s01** — Codex hooks schema/probe + document pin; extend `EVENT_MAPPING`/matcher model (TDD red on nested output).
2. **s02** — Manifest: enable all missing hooks for `runtimes.codex`.
3. **s03** — Generator: nested matchers + multi-hook merge + timeouts; regenerate `.codex/hooks.json`.
4. **s04** — Payload normalize (`tool_name` aliases) in `_lib` / hooks as needed; fail-closed.
5. **s05** — Parity matrix module + `runtime-sync --check` + doctor assertion.
6. **s06** — Behavior bridge tests: SessionStart, SubagentStart, bash-pretool, agent-posttool, bash-output-cap registration + stop/spawn regression.
7. **s07** — Docs/runbook/architecture matrix + tasks index note.
8. **s08** — Legacy purge: incomplete mapping comments/docs claiming «partial OK»; forbid hand-edit instructions.

## Appetite

| Поле | Значение | Описание |
| :--- | :--- | :--- |
| `timebox_days` | `6` | Календарный timebox |
| `cut_list` | `['SessionEnd/PermissionRequest extras', 'deep DSH parity']` | Не резать FR-002 Claude settings set |

## Следующий режим

→ **BACK DECOMPOSE** `T-HUB-053-codex-claude-hooks-parity`
