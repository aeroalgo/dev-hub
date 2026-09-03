# [T-HUB-018 | loop-incident-autopilot] PLAN

**Дата:** 2026-08-28  
**Режим:** BACK PLAN  
**Уровень:** L4  
**Статус:** active  
**Roadmap:** [roadmap-loop-observability-epics.md](roadmap-loop-observability-epics.md)  
**Queue:** [roadmap-loop-observability-epics.queue.yaml](roadmap-loop-observability-epics.queue.yaml)  
**Deps:** **hard** T-HUB-017. Soft: T-HUB-015 (board Retry incident UI + failed execution status).

**Skills:** writing-plans · architecture-patterns · python-testing-patterns · brainstorming (batch decisions below)

→ [T-HUB-018-loop-incident-autopilot/md/decompose-index.md](T-HUB-018-loop-incident-autopilot/md/decompose-index.md) — **после DECOMPOSE**

---

## Контекст

- **req:** когда Tier-0 (017) исчерпан или diagnostic не в registry, loop должен **автоматически** запустить bounded agent-сессию для починки **orchestration-артефактов** (activeContext, index, implement shard, checkpoint) — без участия человека — и продолжить цикл; при неудаче — эскалация `NEED_HUMAN` + alert.
- **deps:** T-HUB-017 (incident schema, registry, trace, metrics, doctor). Существующий: `loop.sh` session spawn, `verify` subagent, hooks stop-gate, `halt_logic`.
- **refs:** T-HUB-017 plans; `loop/loop.sh`; `loop/context_loop.py`; `.claude/hooks/stop-gate.py`; `.claude/project.env` model presets (T-HUB-007); T-HUB-015 plan §UI intercept (soft).

### Зафиксированные решения (brainstorming batch)

| Тема | Решение |
|------|---------|
| Trigger | `check_after` → tier0 exhausted OR unknown repairable orchestration code → open incident `tier1_eligible: true` → `loop.sh` spawns **incident session** before final halt |
| Session kind | **`BACK BUGFIX loop-incident`** fixed role command; prompt built from template + incident payload + runbook markdown |
| Writable scope | **Allowlist paths only:** `memory-bank/activeContext.md`, `memory-bank/**/plan/decompose-*/index.yaml`, `memory-bank/**/implement/implement-*/sNN-*.yaml`, `runtime/**/epic/checkpoint.json`, `runtime/**/epic/state.json` (last two read+write for checkpoint clear only) |
| Forbidden writes | `loop/**`, `.claude/hooks/**`, product `src/**`, `frontend/**`, `*.py` application code, git operations |
| Max attempts | **`EPIC_INCIDENT_TIER1_MAX`** default 2 per incident_id; global **`EPIC_INCIDENT_TIER1_MAX_PER_SESSION`** default 1 per loop iteration |
| Verify gate | После incident session обязателен **`@verify`** subagent (existing pattern) на orchestration invariants — не product tests |
| Success path | verify PASS → `resolve_incident(tier1)` → emit `incident_resolved` → `decide=continue` |
| Failure path | verify FAIL or max attempts → `escalate_incident` → `NEED_HUMAN: incident_<code>` in Handoff suggestion → alert hook |
| Alert channels | **Primary:** write `runtime/<slug>/epic/NEED_HUMAN` flag file + stderr banner. **Optional:** `EPIC_ALERT_WEBHOOK_URL` POST JSON (no secrets in payload). **Soft 015:** board execution `failed` + metadata `incident_id` |
| CLI parity | `bin/loop incident-retry [--incident-id]` manual re-trigger; `bin/loop incident-status` |
| Model | Use `PROJECT_LOOP_BUGFIX_MODEL` from project.env; **no** free-text model from incident payload |
| Concurrency | Reuse flock — no parallel incident session if runner active |
| Runbooks | Tier-1 reads `loop/incidents/runbooks/<code>.md` (017) as mandatory context |
| CREATIVE | optional only if Cordis board failed-status API unstable at DECOMPOSE — `creative-dsh-incident-board-status.md` |

**CREATIVE need:** optional (defer to DECOMPOSE if T-HUB-015 board API unclear).

---

## Цель

Bounded **Tier-1 incident autopilot**: при orchestration-сбое loop автоматически запускает короткую BUGFIX-сессию с жёстким scope, verify, continue или эскалация с alert — **без** правки product code и **без** silent halt.

---

## Продуктовая спека (WHAT)

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как разработчик, я хочу чтобы loop после tier0 failure сам попытался починить activeContext/index desync, чтобы не вставать ночью. | P0 | Fixture unknown-to-tier0 but orchestration-only → tier1 session → continue |
| US-002 | Как разработчик, я хочу лимит попыток tier1, чтобы не зациклить токены. | P0 | 3 failures → `repair_exhausted` + NEED_HUMAN |
| US-003 | Как разработчик, я хочу webhook при эскалации, чтобы узнать о блокере. | P1 | Mock webhook receives incident payload on escalate |
| US-004 | Как разработчик, я хочу `loop incident-retry` для ручного повтора после фикса env. | P1 | CLI resolves stale incident → spawns tier1 |
| US-005 | Как разработчик, я хочу видеть failed incident на board (если 015 есть). | P2 | Soft integration test with FakeBoardExecution |

#### Acceptance Scenarios — US-001

- **Given:** incident open, `tier0_attempts >= max`, diagnostic `active_context_shape_invalid`, runbook exists
- **When:** loop iteration reaches tier1 gate
- **Then:** spawns incident session; agent edits only allowlisted paths; verify PASS → incident resolved → loop continues

#### Acceptance Scenarios — US-002

- **Given:** tier1 already failed twice for same `incident_id`
- **When:** third tier1 trigger
- **Then:** no spawn; `escalate_incident`; `decide=halt`; `NEED_HUMAN: incident_active_context_shape_invalid`

#### Acceptance Scenarios — US-003

- **Given:** `EPIC_ALERT_WEBHOOK_URL=http://127.0.0.1:9/mock` (test server)
- **When:** escalate
- **Then:** POST body schema `loop-alert/v1` with `incident_id`, `diagnostic_codes`, `project_root`, `epic_id` — no prompt text

#### Acceptance Scenarios — US-004

- **Given:** escalated incident; human fixed env offline
- **When:** `loop incident-retry --incident-id <id>`
- **Then:** reopens incident tier1_eligible, runs one session, respects max attempts

### Functional Requirements (FR-###)

- **FR-001:** `loop/incidents/tier1.py` — eligibility check: orchestration-only diagnostic_codes whitelist; product test failures → **not** tier1 eligible.
- **FR-002:** `loop/incidents/prompt.py` — build tier1 prompt from template: incident + runbook + allowlist + forbidden list.
- **FR-003:** `loop/incidents/scope.py` — pretool hook or session wrapper validates Write paths against allowlist during tier1 session (`EPIC_INCIDENT_SESSION=1`).
- **FR-004:** `loop.sh` branch: after check_after tier0 fail → if tier1 eligible → spawn incident session → re-run check_after → decide.
- **FR-005:** Post-tier1 verify: invoke existing verify subagent with AC = orchestration invariants only (finish_integrity, shape, fingerprint changed).
- **FR-006:** `loop/incidents/alert.py` — `emit_alert(incident, level)` → NEED_HUMAN file + optional webhook.
- **FR-007:** Alert payload schema `loop-alert/v1`; fail-closed if webhook non-2xx (log error, still write local flag).
- **FR-008:** CLI: `incident-retry`, `incident-status` on `context_loop.py` / `bin/loop`.
- **FR-009:** Metrics extension: `tier1_attempts`, `tier1_success`, `tier1_escalations`, `mttr_incident_seconds` (from opened_at to resolved_at).
- **FR-010:** Event kinds: `incident_tier1_started`, `incident_tier1_finished`, `incident_escalated`.
- **FR-011:** Integration soft: if `DSH_MB_BRIDGE` or 015 plugin present, map escalated incident → board task execution failed (metadata only) — **feature-detect**, no hard dep.
- **FR-012:** Docs: `loop/incidents/README.md` § Tier-1 + env vars; `loop/WORKFLOW.md` incident flow diagram.
- **FR-013:** SLO config in registry: `tier1_max_attempts`, `tier1_timeout_seconds` (default 900).
- **FR-014:** Forbidden: tier1 during `EPIC_DONE` / security halt / hook deny.

### Success Criteria (SC-###)

| ID | Измеримый результат | Проверка / источник | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | Tier1 fixture → continue without human | integration test with mock agent | outcome |
| SC-002 | Max attempts → NEED_HUMAN + local flag file | unit | outcome |
| SC-003 | Write outside allowlist → hook deny during tier1 | unit pretool | outcome |
| SC-004 | Webhook POST on escalate (mock server) | unit | outcome |
| SC-005 | `incident-retry` CLI documented + tested | unit --help + retry | outcome |
| SC-006 | No product `src/` writes in tier1 session test | integration | outcome |

### Assumptions

- Tier-1 uses same Claude session infrastructure as normal loop (session_resilience.py).
- Verify subagent already exists; extend prompt slice for orchestration-only AC.
- User may disable tier1: `EPIC_INCIDENT_TIER1=0` → escalate immediately after tier0 fail.

### Clarifications

- Session: 2026-08-28 chat (full autopilot vision).
- Tier-0 scope closed in T-HUB-017; this epic is only Tier-1 + alerts + CLI.

### [НУЖНО УТОЧНИТЬ]

- n/a. Board failed-status mapping — optional at DECOMPOSE; if 015 API unknown → skip sNN board with defer note.

---

## AC

### AC+

1. Unit: tier1 eligibility — orchestration yes, pytest fail no  
2. Unit: scope allowlist denies `loop/context_loop.py` write  
3. Integration: mock tier1 success → incident resolved → continue  
4. Integration: tier1 fail max → escalate + NEED_HUMAN file  
5. Unit: webhook mock receives `loop-alert/v1`  
6. CLI: `incident-retry`, `incident-status`  
7. Metrics: tier1 counters + mttr  
8. Events: tier1_started/finished/escalated  
9. Docs: WORKFLOW.md incident section  
10. Regression: tier0-only path unchanged when `EPIC_INCIDENT_TIER1=0`  

### AC−

1. Не auto-fix product application bugs / failing product pytest  
2. Не modify `loop/**` or `.claude/hooks/**` in tier1 session  
3. Не git commit/push  
4. Не bypass verify after tier1  
5. Не unlimited tier1 retries  
6. Не send full prompts/activeContext to webhook  
7. Не require T-HUB-015 for ship  

---

## Техника / архитектура (HOW)

### Стек

- Python 3.12 + bash loop.sh
- Optional HTTP webhook (stdlib `urllib` or `httpx` if already dep — prefer stdlib)
- Claude session via existing wrapper

### Модули (target layout)

| Файл | Роль |
|------|------|
| `loop/incidents/tier1.py` | Eligibility, attempt budget, orchestration-only classifier |
| `loop/incidents/prompt.py` | Tier1 prompt template |
| `loop/incidents/scope.py` | Allowlist path guard |
| `loop/incidents/alert.py` | NEED_HUMAN file + webhook |
| `loop/incidents/eligibility.yaml` | diagnostic_code → tier1_eligible bool |
| `loop/loop.sh` | Incident session branch + re-check_after |
| `loop/context_loop.py` | incident-retry/status subcommands |
| `.claude/hooks/agent-pretool.py` | Wire scope guard when `EPIC_INCIDENT_SESSION=1` |
| `loop/tests/test_incidents_tier1_*.py` | Suite |
| `loop/tests/fixtures/incidents/tier1/**` | shape invalid, checkpoint drift |
| `loop/WORKFLOW.md` | Flow diagram update |

### Архитектура

```mermaid
flowchart TB
  CA[check_after] --> T0[Tier-0 repairs]
  T0 -->|resolved| CONT[continue loop]
  T0 -->|exhausted / unknown| ELIG{tier1 eligible?}
  ELIG -->|no| ESC[escalate + alert]
  ELIG -->|yes| T1[spawn BUGFIX loop-incident session]
  T1 --> SCOPE[pretool allowlist]
  T1 --> VER[@verify orchestration]
  VER -->|PASS| RES[resolve incident]
  RES --> CONT
  VER -->|FAIL| RETRY{attempts left?}
  RETRY -->|yes| T1
  RETRY -->|no| ESC
  ESC --> FLAG[NEED_HUMAN file]
  ESC --> WH[webhook optional]
  ESC --> HALT[halt loop]
```

### Tier-1 prompt template (outline)

```markdown
BACK BUGFIX loop-incident — orchestration only.

Incident: {incident_id}
Diagnostic: {diagnostic_codes}
Epic: {epic_id} step {step_id}

ALLOWED WRITES (only these):
- memory-bank/activeContext.md
- memory-bank/**/plan/decompose-*/index.yaml
- memory-bank/**/implement/implement-*/sNN-*.yaml
- runtime/**/epic/checkpoint.json (checkpoint clear only)

FORBIDDEN: loop/**, hooks/**, product src/**, *.py product code, git.

Runbook: {runbook_content}

Fix orchestration drift. Update Handoff. Do not run product test suite.
```

### Orchestration-only eligibility (`eligibility.yaml`)

```yaml
version: loop-incident-eligibility/v1
tier1_eligible:
  active_context_shape_invalid: true
  fingerprint_stall_exhausted: true
  checkpoint_drift: true
  mark_index_missing: true  # if tier0 exhausted
  finish_integrity_desync: true
  implement_index_conflict: false  # human — ambiguous intent
  verify_no_verdict: false  # agent quality — escalate human
  product_test_failed: false
  hook_security_deny: false
```

### Alert payload (`loop-alert/v1`)

```json
{
  "schema": "loop-alert/v1",
  "level": "escalation",
  "incident_id": "...",
  "diagnostic_codes": ["..."],
  "project_root": "/abs/path",
  "epic_id": "T-HUB-014-...",
  "step_id": "s04",
  "tier0_attempts": 2,
  "tier1_attempts": 2,
  "runbook_rel": "loop/incidents/runbooks/....md",
  "ts": "2026-08-28T..."
}
```

### Env configuration

| Env | Default | Purpose |
|-----|---------|---------|
| `EPIC_INCIDENT_TIER1` | `1` | Enable tier1 autopilot |
| `EPIC_INCIDENT_TIER1_MAX` | `2` | Per incident_id |
| `EPIC_INCIDENT_TIER1_MAX_PER_SESSION` | `1` | Per loop iteration |
| `EPIC_INCIDENT_TIER1_TIMEOUT` | `900` | Session wall clock sec |
| `EPIC_ALERT_WEBHOOK_URL` | empty | Optional POST on escalate |
| `EPIC_INCIDENT_SESSION` | set by loop.sh | Pretool scope guard |

### SLO targets (documented, not enforced by code in 018)

| SLO | Target |
|-----|--------|
| Tier-0 auto-resolve | >90% known codes (017) |
| Tier-1 auto-resolve | >60% tier1-eligible orchestration incidents |
| Escalation rate | <1/day per active epic |
| MTTR incident (auto) | <15 min wall clock |

### Replacement / sunset (brownfield)

Extends T-HUB-017; no removal of existing halt paths.

#### A. Code / modules

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| n/a | — | greenfield |

#### B. Entrypoints

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| n/a | — | greenfield |

#### C. Fallbacks

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| Silent halt without incident record | Always open incident before halt (017) | delete in-epic (behavior change) |

---

## До DECOMPOSE (черновик нарезки)

| sNN | Slug | Суть |
|-----|------|------|
| s01 | tier1-eligibility-yaml | eligibility.yaml + classifier |
| s02 | tier1-prompt-template | prompt.py + runbook injection |
| s03 | scope-pretool-guard | scope.py + agent-pretool wire |
| s04 | loop-sh-incident-branch | loop.sh spawn + re-check_after |
| s05 | tier1-verify-orchestration | verify AC slice post-tier1 |
| s06 | alert-webhook-need-human | alert.py + NEED_HUMAN file |
| s07 | cli-incident-retry-status | context_loop subcommands |
| s08 | metrics-events-tier1 | tier1 metrics + events |
| s09 | docs-workflow-board-soft | WORKFLOW.md + optional 015 hook stub |
| s10 | regression-suite-polish | full incidents regression |

---

## Следующий режим

→ **BACK DECOMPOSE** T-HUB-018 (после T-HUB-017 QA/REFLECT или queued after 017 in canon)
