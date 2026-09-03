# [T-HUB-042 | runtime-adapter-framework] PLAN

**Дата:** 2026-09-01  
**Режим:** BACK PLAN  
**Уровень:** L3–L4  
**Статус:** active  
**Roadmap:** [roadmap-harness-universal-runtime-epics.md](roadmap-harness-universal-runtime-epics.md)  
**Queue:** [roadmap-harness-universal-runtime-epics.queue.yaml](roadmap-harness-universal-runtime-epics.queue.yaml)  
**Deps:** **hard** T-HUB-041. **Soft:** T-HUB-006 (DSH as-built), T-HUB-030 (doctor patterns).

**Skills:** writing-plans · architecture-patterns · python-testing-patterns · async-python-patterns

→ [T-HUB-042-runtime-adapter-framework/md/decompose-index.md](T-HUB-042-runtime-adapter-framework/md/decompose-index.md) — **после DECOMPOSE**

---

## Контекст

- **req:** `EPIC_RUNTIME` захардкожен `{claude,dsh}` с if/else в `loop.sh` и `session_resilience.py`. Нужен plug-in **RuntimeAdapter** + registry для claude | dsh | future codex без изменения loop orchestration semantics.
- **deps:** **hard** T-HUB-041 (`harness/` imports). **Soft:** T-HUB-006 DSH behavior parity.
- **refs:** `loop/loop.sh`, `loop/runtime_adapters/dsh.py`, `.claude/hooks/_lib.py`, `.claude/hooks/session_resilience.py`, `loop/context_loop.py`, plan-T-HUB-006.

### Зафиксированные решения

| Тема | Решение |
|------|---------|
| Registry | `loop/runtime_registry.yaml` — id, adapter module, capabilities, binary_env |
| Protocol | `loop/runtime_adapters/base.py` — SessionContext, SessionAnalysis, RuntimeAdapter |
| Dispatch | `loop/runtime/dispatch.py` CLI module; `loop.sh` thin wrapper |
| Default | `EPIC_RUNTIME=claude` unset |
| Invalid runtime | `invalid_runtime_config` fail-closed (extend `_lib.resolve_runtime_config`) |
| analyze_log | adapter method; purge `is_dsh` branches from session_resilience core path |
| prepare JSON | generic `runtime_extras` dict (replace hardcoded `dsh_profile` only in orchestrator consumption) |
| Zero regression | claude path byte-equivalent behavior |

**CREATIVE need:** нет.

---

## Technology axiom (replace-not-wrap)

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Runtime selection | `runtime_registry.yaml` + pydantic/typed loader | `frozenset({"claude","dsh"})` hardcode |
| Session classification | `SessionAnalysis` dataclass from adapter | `if is_dsh:` tree in session_resilience |
| Missing binary | exit 127 + diagnostic | silent fallback to claude |
| New runtime | registry row + adapter class | new `if` branch in loop.sh |

---

## Продуктовая spека (WHAT)

### Product probe

| # | Question | Answer | Impact |
|---|----------|--------|--------|
| 1 | Reframe | Operator wants any CLI runtime without forking loop | Adapter protocol |
| 2 | Wedge | Registry + ClaudeAdapter + DshAdapter refactor; no codex yet | Scope cut codex → 043 |
| 3 | Pre-mortem | Refactor breaks transient retry / stream filter | TDD fixtures from T-HUB-006 |
| 4 | Adoption | `EPIC_RUNTIME=dsh` unchanged for pilots | backward compat AC |
| 5 | Leverage | Extract existing dsh.py + run_claude_session | don't rewrite orchestrator |
| 6 | Appetite | L3–L4, 5–7 days, ≤10 sNN | cut: interactive codex |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как operator, я хочу `EPIC_RUNTIME` из registry, чтобы добавлять runtime без правки loop.sh if/else. | P0 | unknown runtime → exit 2 |
| US-002 | Как loop, я хочу единый `SessionAnalysis`, чтобы retry policy одинакова для всех runtime. | P0 | mock adapter transient → retry |
| US-003 | Как maintainer, я хочу ClaudeAdapter extracted, чтобы claude path тестируется изолированно. | P0 | unit test build_command |
| US-004 | Как DSH pilot, я хочу zero regression на EPIC_RUNTIME=dsh. | P0 | test_dsh_runtime_adapter green |

### Functional Requirements

- **FR-001:** `loop/runtime_registry.yaml` schema `runtime-registry/v1` with claude, dsh entries.
- **FR-002:** `loop/runtime_adapters/base.py` — SessionContext, SessionAnalysis, RuntimeCapabilities, RuntimeAdapter Protocol.
- **FR-003:** `loop/runtime_adapters/claude.py` — extract from `run_claude_session` argv builder + stream filter hook.
- **FR-004:** Refactor `loop/runtime_adapters/dsh.py` — implement RuntimeAdapter (existing functions wrap).
- **FR-005:** `loop/runtime/registry.py` — load registry, `get_runtime_adapter(id)`, capability check.
- **FR-006:** `loop/runtime/dispatch.py` — `build_command`, `run_session` subprocess wrapper (delegates session_resilience).
- **FR-007:** `_lib.resolve_runtime_config` — load runtime id from registry keys, not frozenset.
- **FR-008:** `session_resilience.analyze_session_log` — delegate to adapter; keep shared helpers in `runtime_adapters/common.py`.
- **FR-009:** `context_loop.prepare_session` — emit `runtime_extras` via adapter.prepare_extras(loop_phase).
- **FR-010:** `loop.sh` — replace if dsh/claude with dispatch CLI; keep retry/record-session shell loop.
- **FR-011:** `--runtime` CLI choices generated from registry (context_loop argparse).
- **FR-012:** Unit tests: registry load, invalid runtime, claude+dsh command builders, analyze_log fixtures.

### Success Criteria

| SC-001 | EPIC_RUNTIME unset → claude | test_runtime_config |
| SC-002 | EPIC_RUNTIME=foo → invalid_runtime_config | test_runtime_config |
| SC-003 | DSH fixtures → same SessionAnalysis as before | test_dsh_runtime_adapter |
| SC-004 | No `is_dsh` in analyze_session_log main path | rg audit |

---

## AC+

1. `loop/runtime_registry.yaml` lists claude + dsh with capabilities.
2. `python -m loop.runtime dispatch --dry-run --runtime claude` prints argv.
3. `EPIC_RUNTIME=dsh` + mock → invoke mock with profile (existing test parity).
4. Unknown runtime → loop exit 2 + JSON diagnostic.
5. `pytest loop/tests/test_runtime_config.py loop/tests/test_dsh_runtime_adapter.py loop/tests/test_loop_dsh_dispatch.py -q` green.
6. `rg 'is_dsh' .claude/hooks/session_resilience.py` — only adapter delegation or zero.

### AC−

1. Hardcoded `{claude,dsh}` frozenset in `_lib.py` after epic.
2. `if.*dsh.*run_dsh` dispatch block in loop.sh after epic.
3. Silent fallback missing dsh → claude.
4. Orchestrator (prepare halt matrix) knows dsh_profile field names.

---

## Техника / архитектура (HOW)

### RuntimeAdapter contract

```python
class RuntimeAdapter(Protocol):
    id: str
    capabilities: RuntimeCapabilities

    def resolve_binary(self, env: Mapping[str, str]) -> list[str] | None: ...
    def build_command(self, ctx: SessionContext) -> list[str]: ...
    def stream_filter_argv(self, ctx: SessionContext) -> list[str] | None: ...
    def analyze_log(self, ctx: SessionContext, *, exit_code, attempt, expected_model) -> SessionAnalysis: ...
    def prepare_extras(self, loop_phase: str) -> dict[str, Any]: ...
```

### runtime_registry.yaml (draft)

```yaml
schema: runtime-registry/v1
default: claude
runtimes:
  claude:
    adapter: loop.runtime_adapters.claude:ClaudeAdapter
    binary_env: CLAUDE_BIN
    capabilities:
      headless: true
      interactive: true
      stream_json: true
      managed_subagents: native
  dsh:
    adapter: loop.runtime_adapters.dsh:DshAdapter
    binary_env: DSH_BIN
    capabilities:
      headless: true
      interactive: false
      managed_subagents: bridge
```

### Data flow

```text
[loop.sh] -> [prepare JSON runtime + runtime_extras]
         -> [loop.runtime dispatch]
         -> [Registry.get(claude|dsh)]
         -> [Adapter.build_command]
         -> [session_resilience run-session]
         -> [record-session -> Adapter.analyze_log]
         -> [check-after]  (unchanged)
```

### Files

| Файл | Действие |
|------|----------|
| `loop/runtime_registry.yaml` | new |
| `loop/runtime_adapters/base.py` | new |
| `loop/runtime_adapters/common.py` | new shared detectors |
| `loop/runtime_adapters/claude.py` | new extract |
| `loop/runtime_adapters/dsh.py` | refactor implements adapter |
| `loop/runtime/registry.py` | new |
| `loop/runtime/dispatch.py` | new |
| `loop/runtime/__init__.py` | new |
| `harness/hooks/_lib.py` | registry-based EPIC_RUNTIME |
| `harness/hooks/session_resilience.py` | delegate analyze_log |
| `loop/loop.sh` | thin dispatch |
| `loop/context_loop.py` | runtime_extras, dynamic --runtime choices |
| `loop/tests/test_runtime_registry.py` | new |
| `loop/tests/test_runtime_dispatch.py` | new |

---

## Eng review spine

### Failure matrix

| Component | Failure | Detection | Response | Test ID |
|-----------|---------|-----------|----------|---------|
| registry yaml | malformed | load fail | invalid_runtime_config | TM-001 |
| adapter import | missing module | import error | fail-closed start | TM-002 |
| binary missing | dsh not installed | resolve_binary None | exit 127 | TM-003 |
| capability gap | interactive+dsh | preflight | HALT message | TM-004 |
| analyze_log | unknown log format | SessionAnalysis unknown | no retry infinite | TM-005 |
| claude regression | stream filter break | existing tests | block merge | TM-006 |

---

## Replacement / sunset

### A. Code

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| `_RUNTIME_MODES = frozenset({claude,dsh})` | runtime_registry.yaml | delete in-epic |
| `run_agent_session` if/else in loop.sh | dispatch module | delete in-epic |
| inline `is_dsh` analyze branches | adapter.analyze_log | delete in-epic |
| hardcoded `dsh_profile` in prepare return | runtime_extras | migrate field |

### C. Fallbacks

| Pattern | Replacement | Policy |
|---------|-------------|--------|
| dsh missing → claude | exit 127 | already canon; preserve |

---

<a id="qa-consumes"></a>
## QA consumes

| ID | Priority | Scenario | Command | Expected | Maps |
|----|----------|----------|---------|----------|------|
| TM-001 | P0 | registry load | pytest loop/tests/test_runtime_registry.py | PASS | FR-001 |
| TM-002 | P0 | invalid runtime | pytest loop/tests/test_runtime_config.py -k invalid | PASS | AC-4 |
| TM-003 | P0 | dsh parity | pytest loop/tests/test_dsh_runtime_adapter.py | PASS | US-004 |
| TM-004 | P0 | dispatch dry-run claude | pytest loop/tests/test_runtime_dispatch.py | PASS | FR-006 |
| TM-005 | P1 | loop dsh dispatch shell | pytest loop/tests/test_loop_dsh_dispatch.py | PASS | FR-010 |
| TM-006 | P1 | context_loop prepare extras | pytest loop/tests/test_context_loop.py -k runtime | PASS | FR-009 |

---

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| Product probe | L3 | done | §Product probe |
| Eng spine | L2+ | done | §Eng review spine |
| qa_consumes | L2+ | done | 6 TM |
| Plan review | L2+ | done | batch log below |

## Plan review batch log

| Phase | Auto-resolved | Deferred |
|-------|---------------|----------|
| Eng | reuse T-HUB-006 fixtures | codex → 043 |

---

## До DECOMPOSE

| sNN | Slice |
|-----|-------|
| s01 | base.py + common.py + registry.yaml schema |
| s02 | registry.py loader + validation |
| s03 | ClaudeAdapter extract + tests |
| s04 | DshAdapter implements protocol + tests |
| s05 | dispatch.py + loop.sh wiring |
| s06 | _lib resolve_runtime_config registry |
| s07 | session_resilience delegate analyze_log |
| s08 | context_loop runtime_extras + argparse |
| s09 | purge is_dsh/if dispatch + regression suite |
| s10 | legacy fallback purge sNN |

---

## Appetite

| Поле | Значение |
| :--- | :--- |
| `timebox_days` | 7 |
| `cut_list` | `['capability preflight CLI', 'interactive mode registry flags']` |

---

## Следующий режим

→ BACK DECOMPOSE (after T-HUB-041 IMPLEMENT done)
