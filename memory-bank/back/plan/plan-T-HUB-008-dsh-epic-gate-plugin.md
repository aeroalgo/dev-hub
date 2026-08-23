# [T-HUB-008 | dsh-epic-gate-plugin] PLAN

**Дата:** 2026-08-22  
**Режим:** BACK PLAN  
**Уровень:** L4  
**Статус:** active  
**Roadmap:** [roadmap-dsh-loop-backend-epics.md](roadmap-dsh-loop-backend-epics.md)  
**Deps:** T-HUB-006, T-HUB-007

**Skills:** writing-plans · architecture-patterns · python-testing-patterns · typescript (Cordis plugin surface)

→ [decompose-T-HUB-008-dsh-epic-gate-plugin/index.md](decompose-T-HUB-008-dsh-epic-gate-plugin/index.md) — **после DECOMPOSE**

---

## Контекст

- **req:** parity Claude hooks (`agent-pretool`, `stop-gate`) для DSH path — block turn end без FINISH evidence; validate subagent spawn (packed prompt); bridge к `epic_resolve.py`.
- **deps:** T-HUB-006 (DSH invoke), T-HUB-007 (presets verify/reviewer/explorer).
- **refs:** `.claude/hooks/agent-pretool.py`, `.claude/hooks/stop-gate.py`, `.claude/instructions/spawn-hard.md`, `.claude/hooks/epic_lib.py` (`mirror_verify_verdict`, `gate_evidence_matches`), DSH extension cookbook (`tools/pre-execute`, `agent/turn-stopping`).

### Зафиксированные решения

| Тема | Решение |
|------|---------|
| Plugin location | `dsh/plugins/epic-gate/` — private package `@dev-hub/dsh-epic-gate`, `private: true` |
| Mount | Profile `cordis.patch.yml` inserts plugin row on all `epic-*` profiles |
| Python bridge | Plugin shell-outs: `python3 "$DEV_HUB/.claude/hooks/epic_resolve.py" --cwd "$PROJECT_ROOT" …` |
| PROJECT_ROOT | Env **`EPIC_PROJECT_ROOT`** passed by `run_dsh_session` (same as loop PROJECT_ROOT) |
| pre-execute | Intercept **subagent** tool calls → packed prompt validation (port logic from agent-pretool) |
| turn-stopping | Before turn close → check finalize-step evidence / verify PASS / NEED_HUMAN rules |
| Verdict capture | On subagent result with `VERDICT:` → call `mirror_verify_verdict` equivalent via CLI or new `epic_resolve record-verdict` |
| FRONT tests rule | Deny vitest/playwright/npm test in child preset tools (already in agent md; enforce in pre-execute for child scope) |
| Claude path | **Unchanged** — plugin only loaded in DSH profiles |

**CREATIVE need:** узкий — mapping Cordis events ↔ epic_resolve CLI (закрыт таблицами ниже; отдельный CREATIVE shard не обязателен).

---

## Цель

DSH session не может «тихо» завершить IMPLEMENT step без validate-step + verify PASS + finalize-step; subagent spawn без packed sections denied; parity checklist vs `loop/tests/test_finish_integrity.py` scenarios.

---

## Требования

### FR

| ID | Требование |
|----|------------|
| FR-1 | Package `dsh/plugins/epic-gate/` with Cordis plugin `apply(ctx)` |
| FR-2 | `tools/pre-execute` on subagent tool: deny if missing AC+, AC−, VERIFY, ALLOW for verify/reviewer; explorer GRAPHIFY/ALLOW rules |
| FR-3 | `agent/turn-stopping`: call Python helper `gate-check-turn.py --cwd PROJECT_ROOT` → allow \| continue \| halt |
| FR-4 | New hook script `.claude/hooks/gate-check-turn.py` (shared DSH + future Cursor) — extracts pure logic from stop-gate |
| FR-5 | Optional: `epic_resolve.py record-verdict --verdict PASS\|FAIL` — if mirror cannot be reused |
| FR-6 | Plugin config: `projectRoot`, `devHub`, `enabledGates[]` |
| FR-7 | Integration test: loop fixture with fake dsh + plugin mounted → incomplete FINISH blocked |
| FR-8 | Parity matrix document in plugin README vs spawn-hard.md |
| FR-9 | `run_dsh_session` exports `EPIC_PROJECT_ROOT`, `DEV_HUB` for plugin |

### NFR

| ID | Требование |
|----|------------|
| NFR-1 | Plugin failure → loud error (misconfiguration fails loud per DSH conventions) |
| NFR-2 | No network from plugin except subprocess to local python |
| NFR-3 | Typecheck passes in plugin package |
| NFR-4 | Pin `@deepseek-ai/cordis` peer dep to dsh version |

### AC+

1. Subagent verify call without AC+ → pre-execute deny with reason `prompt_incomplete:AC+`  
2. Turn stop with code_changed but no verify PASS → turn-stopping forces continue (or halt with NEED_HUMAN)  
3. After verify VERDICT PASS + finalize-step → turn-stopping allow stop  
4. `gate-check-turn.py` unit tests ported from stop-gate scenarios (minimal set)  
5. Plugin listed in `dsh --profile epic-implement --dump-config`  
6. Claude loop path: zero regression (plugin not loaded)  

### AC−

1. Не удалять Claude stop-gate / agent-pretool  
2. Не переносить epic state into TypeScript  
3. Не implement full spawn-hard in TS — delegate validation rules to Python where possible  
4. Не default EPIC_RUNTIME=dsh  

---

## Event → action matrix

| Cordis event | Claude equivalent | Action |
|--------------|-------------------|--------|
| `tools/pre-execute` (subagent) | agent-pretool PreToolUse Agent | Deny/allow packed prompt |
| `agent/turn-stopping` | Stop hook + stop-gate | Run gate-check-turn.py |
| `tools/post-execute` (subagent result) | post-tool hook | Parse VERDICT → mirror_verify |
| `agent/pre-step` | — | Optional: inject spawn-hard reminder section |

---

## Компоненты / файлы

| Файл | Действие |
|------|----------|
| `dsh/plugins/epic-gate/package.json` | Create |
| `dsh/plugins/epic-gate/src/index.ts` | Plugin apply |
| `dsh/plugins/epic-gate/src/pre-execute-subagent.ts` | Packed prompt rules |
| `dsh/plugins/epic-gate/src/turn-stopping-gate.ts` | Bridge to python |
| `.claude/hooks/gate-check-turn.py` | Extract/refactor from stop-gate |
| `.claude/hooks/agent-pretool.py` | Optional: shared validation module import |
| `dsh/profiles/*/cordis.patch.yml` | Add epic-gate plugin row |
| `dsh/scripts/install-plugin.sh` | pnpm link / copy into profile node_modules |
| `loop/loop.sh` | Export EPIC_PROJECT_ROOT for dsh |
| `loop/tests/test_dsh_epic_gate_integration.py` | New (may skip without node) |
| `dsh/plugins/epic-gate/README.md` | Parity matrix |

---

## Архитектура

```mermaid
sequenceDiagram
  participant Parent as DSH parent agent
  participant Sub as subagent preset verify
  participant Plugin as dsh-epic-gate
  participant Py as epic_resolve.py
  participant Loop as loop check-after

  Parent->>Plugin: tools/pre-execute subagent
  Plugin->>Plugin: validate packed prompt
  Parent->>Sub: subagent verify
  Sub-->>Parent: VERDICT PASS
  Plugin->>Py: record-verdict / mirror
  Parent->>Plugin: agent/turn-stopping
  Plugin->>Py: gate-check-turn.py
  Py-->>Plugin: allow stop
  Loop->>Py: check-after fingerprint
```

---

## Replacement / sunset

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| Duplicated stop logic in stop-gate monolith | Shared `gate-check-turn.py` | refactor; stop-gate calls shared |
| n/a | — | additive for DSH |

### B. Entrypoints

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| DSH sessions without gate | epic-gate plugin mounted | configure in-epic |

---

## Стратегия тестирования

1. Python unit: `gate-check-turn.py` scenarios (port from test_finish_integrity)  
2. TS unit: pre-execute prompt validation (pure functions)  
3. Integration: fake dsh + mounted plugin (optional CI node job)  
4. Manual: headless IMPLEMENT step with DSH + verify gate  

---

## Риски

| Риск | Митигация |
|------|-----------|
| DSH API breaking changes | Pin dsh; plugin versioned with hub |
| TS/Python duplication | Max logic in Python; TS thin wrapper |
| turn-stopping semantics differ from Stop hook | Parity matrix + integration tests |
| Plugin load order | Document in cordis.patch row order |

---

## До DECOMPOSE (черновик фаз)

1. **s01 — extract gate-check-turn.py + Python tests (TDD)**  
2. **s02 — epic-gate plugin skeleton + pre-execute subagent**  
3. **s03 — turn-stopping bridge + record-verdict**  
4. **s04 — mount plugin in profiles + install script**  
5. **s05 — loop env exports + integration test**  
6. **s06 — parity README + spawn-hard cross-ref**

---

## Следующий режим

→ **BACK DECOMPOSE T-HUB-008** (after T-HUB-007 QA)
