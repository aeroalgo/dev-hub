# [T-HUB-016 | dsh-cc-hooks-bridge] PLAN

**Дата:** 2026-08-27  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** active  
**Roadmap:** [roadmap-dsh-loop-backend-epics.md](roadmap-dsh-loop-backend-epics.md)  
**Queue:** [roadmap-dsh-loop-backend-epics.queue.yaml](roadmap-dsh-loop-backend-epics.queue.yaml)  
**Deps:** hard T-HUB-006, T-HUB-007. Soft: pin `@deepseek-ai/dsh` совместимый с `dsh-hooks-claude-code`.

**Skills:** writing-plans · architecture-patterns · python-testing-patterns

→ [decompose-T-HUB-016-dsh-cc-hooks-bridge/index.md](decompose-T-HUB-016-dsh-cc-hooks-bridge/index.md) — **после DECOMPOSE**

---

## Контекст

- **req:** использовать workflow hooks/skills/agents **с минимумом переписывания** при `EPIC_RUNTIME=dsh`: официальный Claude Code hooks bridge + (опционально) `.claude/` compat; не дублировать всю логику `stop-gate` / `agent-pretool` в TypeScript.
- **deps:** T-HUB-006 (DSH invoke из loop); T-HUB-007 (epic-* profiles, куда монтировать bridge).
- **refs:** `.claude/settings.json` `hooks`; `.claude/hooks/*.py`; `.claude/agents/{verify,reviewer,explorer}.md`; `@deepseek-ai/dsh-hooks-claude-code` README; community `dsh-claude-compat`; [plan-T-HUB-008](plan-T-HUB-008-dsh-epic-gate-plugin.md) (revision: gap-fill only); chat 2026-08-27 gap analysis.

### Зафиксированные решения

| Тема | Решение |
|------|---------|
| Primary path | **`@deepseek-ai/dsh-hooks-claude-code`** → `configPath: $PROJECT_ROOT/.claude/settings.json` (или symlink/copy hooks key) |
| projectDir | Session workspace = `$PROJECT_ROOT`; `CLAUDE_PROJECT_DIR` = same (loop already cwd=PROJECT_ROOT) |
| Python hooks | **Reuse as-is** command hooks; no rewrite of epic_resolve / epic_lib |
| Skills/rules/commands | Optional mount **`dsh-claude-compat`** (or equivalent) — enableSkills/Rules/Commands; agents.md **не** считать настоящими subagents |
| Real subagents | Остаются **T-HUB-007 presets** verify/reviewer/explorer (не compat skill-shim) |
| Gaps bridge | Документировать + отдать **T-HUB-008**: `updatedInput` rewrite, typed `agent_type`, transcript/verdict enrichment, stop self-limit |
| Stop loop-guard | В 016: минимальный **self-limit** в `stop-gate.py` (или wrapper) когда `stop_hook_active` всегда false под DSH — без бесконечного continue |
| Pin versions | Зафиксировать compatible `@deepseek-ai/dsh` + `@deepseek-ai/dsh-hooks-claude-code` в `dsh/README.md` / package pins |
| Claude path | Zero change — bridge только в DSH profiles |
| Fail-closed | Misconfigured configPath → loud warning documented; для epic-* **fail boot** если hooks plugin required flag true |

**CREATIVE need:** нет.

---

## Цель

На DSH epic-* profiles: существующие command hooks из `.claude/settings.json` реально вызываются (PreToolUse/Stop/…); skills/rules доступны без миграции; известные дыры bridge зафиксированы и закрываются в T-HUB-008, а не вторым полным портом hooks.

---

## Продуктовая спека (WHAT)

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как разработчик, я хочу чтобы `stop-gate.py` срабатывал в DSH-сессии loop, чтобы нельзя было тихо закончить шаг без FINISH evidence. | P0 | Fixture: Stop hook invoked under fake/real profile dump + hook/result log |
| US-002 | Как разработчик, я хочу чтобы `agent-pretool` / bash hooks вызывались без копипаста в TS. | P0 | PreToolUse matcher fires command hooks |
| US-003 | Как разработчик, я хочу skills/commands/rules из `.claude/` в DSH. | P1 | compat plugin lists skill from fixture `.claude/skills` |
| US-004 | Как разработчик, я хочу явный список «что bridge не даёт», чтобы 008 не гадал. | P0 | Gap matrix в README совпадает с AC− bridge |

#### Acceptance Scenarios — US-001

- **Given:** epic-implement profile с mounted `dsh-hooks-claude-code`, `configPath` → settings с Stop→stop-gate.py
- **When:** agent пытается stop без FINISH evidence (в test harness / recorded)
- **Then:** turn-stopping / steer continue (или эквивалент block→continue); hook process exit logged

### Functional Requirements (FR-###)

- **FR-001:** Pin + install `@deepseek-ai/dsh-hooks-claude-code` в hub (`dsh/plugins/` vendor note или profile `dsh plugin add` script).
- **FR-002:** Shared patch fragment `dsh/patches/cc-hooks-bridge.yml` (или row in each epic-* `cordis.patch.yml`) с `configPath` / `projectDir` contract.
- **FR-003:** `install-profiles` / new `install-cc-hooks.sh` применяет fragment ко всем `epic-*` (+ document headless).
- **FR-004:** Env: `CLAUDE_PROJECT_DIR`/`projectDir` = PROJECT_ROOT; `DEV_HUB` available for hooks that need hub paths when product ≠ hub.
- **FR-005:** Optional `dsh-claude-compat` mount (feature flag `DSH_CC_COMPAT=1` default on for epic-implement).
- **FR-006:** Gap matrix doc: updatedInput · agent_type · SubagentStop transcript · stop_hook_active · SessionStart first-turn — owner T-HUB-008 / self-limit.
- **FR-007:** Python: stop-gate (or thin `stop-gate-dsh-shim`) self-limits consecutive blocks under DSH (detect via env `EPIC_RUNTIME=dsh` or `DSH_HOOKS_BRIDGE=1` set by loop).
- **FR-008:** Smoke: `dsh --profile epic-implement --dump-config` lists hooks-claude-code; unit test config fragment present.
- **FR-009:** Regression: Claude `settings.json` hooks unchanged; Claude loop path green.
- **FR-010:** Docs in `dsh/README.md`: how bridge works, pin versions, known gaps → 008.

### Success Criteria (SC-###)

| ID | Измеримый результат | Проверка | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | hooks-claude-code в dump-config epic-implement | smoke script | outcome |
| SC-002 | Gap matrix ≥ 5 rows with owner epic | README | outcome |
| SC-003 | stop self-limit unit under fake consecutive blocks | pytest | outcome |
| SC-004 | Claude path tests unchanged green | pytest subset | outcome |

### Assumptions

- Official package name remains `@deepseek-ai/dsh-hooks-claude-code` (verify pin at IMPLEMENT).
- Product repos use hub-linked `.claude/hooks` + local or linked `settings.json` hooks key.
- `dsh-claude-compat` may lag DSH version — optional, fail soft with doc if unavailable.

### Clarifications

- Session: 2026-08-27 (user: минимум переписывания hooks для DSH).
- Pivot: 008 больше не «полный порт», а gap-fill после 016.

### [НУЖНО УТОЧНИТЬ]

- n/a CRITICAL. Soft: точный npm version pin — зафиксировать при IMPLEMENT по `npm view` + dsh engines.

---

## AC

### AC+

1. Patch fragment + install script mounts bridge on epic-implement  
2. `--dump-config` contains `@deepseek-ai/dsh-hooks-claude-code`  
3. Gap matrix documents updatedInput / agent_type / stop_hook_active → T-HUB-008  
4. Unit: consecutive Stop blocks under DSH env self-limit after N (configurable, default 8)  
5. README pin table dsh + hooks-claude-code (+ optional compat)  
6. Claude settings.json hooks block byte-stable (no rewrite required)  

### AC−

1. Не портировать stop-gate / agent-pretool целиком в TS (→ 008 только gaps)  
2. Не считать dsh-claude-compat замену presets verify/reviewer/explorer  
3. Не default EPIC_RUNTIME=dsh  
4. Не ломать Claude Code hooks path  
5. Не решать board sync (014/015)  

---

## Техника / архитектура (HOW)

### Стек

- DSH Cordis profile patches (YAML)
- Official npm `@deepseek-ai/dsh-hooks-claude-code` (+ peer `dsh-hook-protocol`)
- Optional community `dsh-claude-compat`
- Existing Python hooks under `.claude/hooks/`
- Loop env export `DSH_HOOKS_BRIDGE=1` when runtime=dsh

### Layout

| Path | Action |
|------|--------|
| `dsh/patches/cc-hooks-bridge.yml` | Create — plugin row template |
| `dsh/scripts/install-cc-hooks.sh` | Create — add plugin + merge patch into profiles |
| `dsh/profiles/epic-*/cordis.patch.yml` | Modify — include bridge (after 007 exists) |
| `loop/loop.sh` / `run_dsh_session` | Modify — export `DSH_HOOKS_BRIDGE=1`, ensure PROJECT_ROOT |
| `.claude/hooks/stop-gate.py` or shim | Modify — self-limit when bridge env |
| `dsh/README.md` | Modify — bridge + gaps |
| `loop/tests/test_dsh_cc_hooks_bridge.py` | Create — fragment + self-limit |
| `dsh/docs/cc-hooks-gap-matrix.md` | Create — owner map |

### Архитектура

```mermaid
flowchart TB
  LOOP[loop run_dsh_session]
  PROF[epic-implement profile]
  BR[@deepseek-ai/dsh-hooks-claude-code]
  SET[.claude/settings.json hooks]
  PY[.claude/hooks/*.py]
  GAP[T-HUB-008 native gaps]
  PRE[T-HUB-007 presets]
  LOOP --> PROF
  PROF --> BR
  PROF --> PRE
  BR --> SET
  SET --> PY
  GAP -.->|updatedInput agent_type verdict| PROF
```

### Event coverage (ваши hooks)

| Event | Hook script | Bridge | 016 action | 008 action |
|-------|-------------|--------|------------|------------|
| SessionStart | session-start.py | partial | mount | optional first-turn if needed |
| UserPromptSubmit | user-prompt.py | ok | mount | — |
| PreToolUse Agent\|Task | agent-pretool.py | deny ok; **no updatedInput** | mount | native rewrite / pre-validate |
| PreToolUse Bash | bash-pretool.py | ok | mount | — |
| PostToolUse Agent\|Task | agent-posttool.py | partial | mount | verdict mirror if broken |
| PostToolUse Bash | bash-output-cap.py | partial | mount | — |
| SubagentStart | subagent-start.py | **agent_type broken** | mount + doc | inject by preset id |
| SubagentStop | subagent-stop.py | **partial** | mount + doc | transcript/verdict path |
| Stop | stop-gate.py | block→continue; no loop-guard | **self-limit** | gate-check-turn share if needed |

### Relationship to T-HUB-007 / 008 / 009

| Epic | Role after this PLAN |
|------|----------------------|
| 007 | Presets + profiles; **must include** cc-hooks patch fragment (cross-ref FR) |
| **016 (this)** | Official bridge + compat + self-limit + gap matrix |
| 008 | **Only** gaps: updatedInput, typed subagent identity, verdict/transcript, thin native |
| 009 | Rollout docs include bridge pin + gap checklist |

---

## Replacement / sunset

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| Assumption «008 = full TS port of all hooks» | Bridge 016 + thin 008 | delete in-epic (plan revision) |
| Silent infinite Stop continue under DSH | self-limit | delete in-epic |

A/B/C greenfield additive otherwise → n/a modules.

---

## До DECOMPOSE (черновик нарезки)

1. **s01 — pin research + gap matrix doc**  
2. **s02 — cc-hooks-bridge patch fragment + install script**  
3. **s03 — mount into epic-* profiles + dump-config smoke**  
4. **s04 — loop env DSH_HOOKS_BRIDGE + PROJECT_DIR contract**  
5. **s05 — stop-gate self-limit under DSH (TDD)**  
6. **s06 — optional dsh-claude-compat mount + docs**  
7. **s07 — README + regression Claude path**  

---

## Следующий режим

→ **BACK DECOMPOSE T-HUB-016** после MERGE и после/вместе с готовностью 007 profiles (hard deps).  
→ Затем IMPLEMENT 016 → DECOMPOSE/IMPLEMENT revised 008.
