# `@dev-hub/dsh-epic-gate`

Native DSH gate for the Claude-compatible epic workflow. The plugin keeps the
existing Python hooks authoritative and adds only the DSH-native event wiring:
Agent/Task pre-execution validation, SubagentStop payload enrichment, and the
first-turn SessionStart injection.

## Parity matrix

| Gap | Claude contract | DSH implementation | Status | Owner |
|---|---|---|---|---|
| Gap A | `PreToolUse` may rewrite `updatedInput` for an Agent/Task spawn | DSH `tools/pre-execute` exposes an allow/deny decision only; `spawn_validate.py` remains fail-closed | deferred | T-HUB-008 |
| Gap B | `SubagentStart` receives the typed `agent_type` field | Native `subagent/start` resolves explicit `agent_type`/`subagent_type`/preset metadata to `verify`, `reviewer`, or `explorer`, then injects the matching Python contract; unknown or `general-purpose` values are ignored (fail-closed) | closed | T-HUB-008 |

The native adapter is intentionally thin: `.claude/hooks/subagent-start.py` remains the
contract source of truth. It forwards only a canonical supported type and the matching
`preset.<type>` marker, so an unknown child never receives a guessed contract.

The adapter relies on the DSH child `agentPreset` metadata when a typed event field is
not present. If neither a supported typed field nor supported preset metadata is
available, the native event is preserved without injection; the bridge's constant
`general-purpose` identity therefore cannot accidentally select a gate contract.

Bounded smoke coverage exercises all three supported mappings and the unknown-type
fail-closed path in `loop/tests/test_dsh_epic_gate_gaps.py`.

| Gap C | `SubagentStop` forwards transcript/output and the final `VERDICT` line | `subagent/end` is normalized to the Claude hook payload, including transcript, output, and `PASS|FAIL|BLOCKED` | closed | T-HUB-008 |
| Gap D | `SessionStart` injects context exactly at the first turn for startup and resume | `agent/session-start` calls `agent.inject()` once for the native event; both sources are covered by integration smoke | closed | T-HUB-008 |

The deferred rows are explicit DSH API limitations, not silent parity failures.
Gap C and Gap D are closed by the native plugin and their executable smoke
coverage. The official command-hook bridge mount and the DSH Stop self-limit
remain documented in `dsh/README.md` and owned by T-HUB-016.

## Mount contract

Every `dsh/profiles/epic-*/cordis.patch.yml` mounts `cc-hooks-bridge` before
`epic-gate`. The bridge invokes the existing `.claude/settings.json` hooks;
the native plugin then supplies the DSH-only gate behavior. Keep this order so
an unavailable bridge cannot silently turn an Agent/Task spawn into an
ungated free-session run.

## Verification

From the repository root:

```bash
timeout 300s .venv/bin/pytest loop/tests/test_dsh_epic_gate_gaps.py -q --tb=line
timeout 300s .venv/bin/pytest loop/tests/test_stop_gate.py loop/tests/test_board_launch_cli.py -q --tb=line
```
