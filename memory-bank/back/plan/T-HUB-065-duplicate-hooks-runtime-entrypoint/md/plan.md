# [T-HUB-065 | duplicate-hooks-runtime-entrypoint] PLAN

**Дата:** 2026-09-05  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** active  
**Clarify:** `memory-bank/back/clarify/clarify-20260905-workflow-loop-audit.md`  
**Roadmap:** `memory-bank/back/roadmap/queue.yaml` · batch `workflow-loop-20260905`  
**Deps:** soft T-HUB-053 (Codex≡Claude hooks parity planned). Hard нет — leftover **duplicate realpath** + **inject runtime**.  
**Skills:** writing-plans · python-testing-patterns · architecture-patterns  
**Источник:** audit `06-drift-and-contradictions.md` P1 duplicate hooks · `03-start-finish-inject.md` runtime lost · Claude hash mismatch

---

## Контекст

- **req:** Один hook command на (event, matcher, realpath). SessionStart inject обязан передавать `EPIC_RUNTIME` в `build_prompt_scope`, чтобы Codex получил `AGENTS.md`, а не `CLAUDE.md`. `mainrule.mdc` не должен требовать читать чужой entrypoint.
- **gap:**
  1. `.claude/settings.json` SessionStart (и другие) регистрирует **два** command: `.claude/hooks/session-start.py` **и** `harness/hooks/session-start.py`. Если это symlink same realpath — hook runs **twice** (retry counters, duplicate state writes, races).
  2. Generator/installer, не только JSON, должен не эмитить duplicates.
  3. `session_start_payload()` → `build_prompt_scope()` без `runtime` → default claude-code.
  4. `mainrule.mdc` HARD: читать `CLAUDE.md` даже в Codex.
  5. `bin/runtime-sync --runtime claude --check` → `hash_mismatch: CLAUDE.md`.
- **refs:** `.claude/settings.json` (Read this session: dual SessionStart); `harness/hooks/session-start.py`; `loop` prompt_builder; `.cursor/rules/mainrule.mdc`; T-HUB-044 doctor; T-HUB-053.
- **Не:** full Codex event matrix (053); transactional finish (068); schema fence (066).

### CREATIVE need

**нет**

---

## Technology axiom

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Hook registration | one realpath per event/matcher | dual symlink entries |
| Prompt scope entrypoint | `EPIC_RUNTIME` → AGENTS.md / CLAUDE.md / DSH.md | default claude when Codex |
| Instruction chain | current runtime entrypoint only | «always Read CLAUDE.md» in Codex |
| settings.json | generated from manifest | hand-edit dual keep «на всякий» |

---

## Продуктовая спека (WHAT)

1. Claude settings after generate: 0 duplicate realpath commands.
2. Codex session start additionalContext entrypoint = AGENTS.md.
3. Claude session start entrypoint = CLAUDE.md.
4. mainrule / role-command: «читай current runtime entrypoint», не hardcoded CLAUDE для всех.
5. runtime-sync claude either green or intentional generated marker — no silent stale copy.

### Product probe

| # | Question | Answer | Impact |
|---|----------|--------|--------|
| 1 | Reframe | Hooks ×2 ломают counters; Codex читает Claude docs | Dedup + pass runtime |
| 2 | Wedge | settings unique realpath + one test EPIC_RUNTIME=codex | P0 |
| 3 | Pre-mortem | Починят JSON руками, generator снова дублирует | FR generator |
| 4 | Adoption | materialize/settings gen | |
| 5 | Leverage | realpath() compare | |
| 6 | Appetite | 3 days | cut: Cursor hooks.json failClosed true (mention, optional) |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как Claude runtime, я хочу SessionStart один раз. | P0 | unique realpath test on settings.json |
| US-002 | Как Codex loop, я хочу inject AGENTS.md. | P0 | unit session_start_payload monkeypatch env |
| US-003 | Как parent Codex, я не хочу rule «читай CLAUDE.md». | P0 | rg mainrule after rewrite; test or snapshot |
| US-004 | Как CI, я хочу duplicate registration fail. | P0 | fixture dual commands → fail `hook_duplicate_realpath` |

#### Acceptance Scenarios — US-001

- **Given:** generated `.claude/settings.json`
- **When:** group hooks by (event, matcher, Path.resolve)
- **Then:** each group size == 1

#### Acceptance Scenarios — US-002

- **Given:** `EPIC_RUNTIME=codex`
- **When:** `session_start_payload(...)`
- **Then:** PromptScope.entrypoint == `AGENTS.md` (or pack equivalent), not CLAUDE.md

### Functional Requirements

- **FR-001:** Dedup function: canonicalize command path via realpath relative to project dir.
- **FR-002:** Generator/installer emits unique commands; pytest on committed settings.json.
- **FR-003:** If `.claude/hooks/*.py` symlink to harness — register **only harness** or **only .claude**, not both (choose harness SoT — matches manifest).
- **FR-004:** `session_start_payload` passes runtime from `EPIC_RUNTIME` / payload into `build_prompt_scope`.
- **FR-005:** Tests both runtimes.
- **FR-006:** Rewrite `.cursor/rules/mainrule.mdc` chain step 0 / HARD RULE: current entrypoint only (Kind I). role-command SKILL same if it forces CLAUDE.md for Codex.
- **FR-007:** runtime-sync: CLAUDE.md either regenerated from `harness/instructions/main.md` or documented generated header; hash_mismatch = fail CI unless allow.
- **FR-008:** Pre/Post tool duplicate same treatment as SessionStart.
- **FR-009:** Cursor `.cursor/hooks.json` failClosed false = **out of scope** unless one-line note in Appetite cut.
- **FR-010:** Do not change hook Python semantics except idempotency if double-fire still possible mid-migrate (guard).

### Success Criteria

| ID | Result | Check | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | 0 duplicate realpaths | pytest | outcome |
| SC-002 | Codex inject AGENTS.md | unit | outcome |
| SC-003 | mainrule no unconditional CLAUDE.md for Codex | rg + review | outcome |
| SC-004 | generator regression fixture | pytest | outcome |

### Assumptions

- Symlink topology remains allowed **if** settings lists one path.
- DSH.md third runtime if EPIC_RUNTIME=dsh — handle or explicit n/a.

## AC

1. Unique hook realpaths in generated Claude settings.
2. Runtime passed to prompt scope.
3. Instruction chain runtime-specific.
4. Tests prevent reintroduction.

### AC−

1. Нет dual SessionStart same script.
2. Нет default claude entrypoint on Codex inject.
3. Нет «Read CLAUDE.md» as universal HARD for Codex.
4. Нет hand-maintained second settings copy that re-adds dual.
5. Нет warning-only on hash_mismatch.

## HOW

- Files: `.claude/settings.json` (generated), `loop/runtime_materializers/hooks` or installer, `harness/hooks` session-start / epic_lib session_start_payload, `prompt_builder`, `mainrule.mdc`, `role-command/SKILL.md`, tests.

## Eng review spine

### Data flow

```text
[manifest hooks] -> [generator] -> [settings.json unique realpath]
[SessionStart] -> [session_start_payload] -> [build_prompt_scope(runtime=EPIC_RUNTIME)]
                 -> [entrypoint AGENTS|CLAUDE|DSH]  fail-closed if unknown runtime
```

### Failure matrix

| Component | Failure | Detection | Response | Test ID |
|-----------|---------|-----------|----------|---------|
| dual realpath | ×2 hook | pytest | generator fix | TM-001 |
| missing runtime arg | CLAUDE on Codex | unit | pass env | TM-002 |
| unknown EPIC_RUNTIME | wrong docs | fail-closed or documented default | TM-003 |
| mainrule stale | Codex reads CLAUDE | rg | Kind I | TM-004 |
| hash_mismatch ignored | drift | runtime-sync --check | fail | TM-005 |
| only SessionStart deduped | other events dual | all events scan | FR-008 | TM-006 |
| generator skip | manual JSON regress | CI on settings | fail | TM-007 |

### Eng spine self-check

| Dimension | Score | Gap |
|-----------|-------|-----|
| Data flow complete | 5 | |
| Failure coverage | 5 | |
| Testability | 5 | |

## Replacement / sunset

### A

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| second settings command same realpath | single | delete in-epic |
| `build_prompt_scope()` default used for Codex | explicit runtime | delete in-epic |

### B

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| installer that appends both .claude and harness | one | delete in-epic |

### C

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| catch Exception continue on preflight as success | typed warning vs fail | partial: start inject runtime is this epic; swallow → 067/068 |
| hash_mismatch warning-only | fail check | delete in-epic for claude target |

### I

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| mainrule «Read CLAUDE.md» always | current entrypoint | delete in-epic |
| role-command same | runtime entrypoint | delete in-epic |

## QA consumes

<a id="qa-consumes"></a>

| ID | Priority | Scenario | Command | Expected | Maps |
|----|----------|----------|---------|----------|------|
| TM-001 | P0 | unique realpath settings | pytest hooks parity | PASS | US-001 |
| TM-002 | P0 | dual fixture fails | pytest | hook_duplicate_realpath | US-004 |
| TM-003 | P0 | EPIC_RUNTIME=codex entrypoint | unit | AGENTS.md | US-002 |
| TM-004 | P0 | EPIC_RUNTIME=claude | unit | CLAUDE.md | FR-005 |
| TM-005 | P1 | all hook events unique | scan | 0 dup | FR-008 |
| TM-006 | P1 | mainrule rg CLAUDE unconditional | rg policy test | 0 bad hits | FR-006 |

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| CLARIFY / Product probe | L3 | done | |
| Eng review spine | L2+ | done | |
| §0.11 | n/a | n/a | |
| CREATIVE | n/a | n/a | |
| qa_consumes | L2+ | done | |
| Plan review batch | L2+ | done | |

## Plan review batch log

| Phase | Auto-resolved | Deferred |
|-------|---------------|----------|
| Product | Register harness path only | Cursor failClosed |
| Eng | Pass EPIC_RUNTIME | full 053 event matrix |

## До DECOMPOSE

1. s01 — red test duplicate realpath + Codex entrypoint.
2. s02 — generator/settings unique; choose SoT path.
3. s03 — pass runtime into build_prompt_scope + tests.
4. s04 — Kind I mainrule/role-command.
5. s05 — runtime-sync hash policy.
6. s06 — purge dual entries leftover all events.

## Appetite

| Поле | Значение | Описание |
| :--- | :--- | :--- |
| `timebox_days` | `3` | |
| `cut_list` | `['Cursor hooks.json failClosed', 'DSH full inject matrix polish']` | |

## Independent Test

- PASS: settings unique; Codex inject AGENTS.md; dual fixture red.
- FAIL: «symlinks exist» without unique registration.

## Следующий режим

→ BACK ANALYZE T-HUB-065 (decompose index = sole tracker).

**Decompose:** [md/decompose-index.md](decompose-index.md) · [yaml/decompose-index.yaml](../yaml/decompose-index.yaml) · 5 sNN.

### CREATIVE need

**нет**
