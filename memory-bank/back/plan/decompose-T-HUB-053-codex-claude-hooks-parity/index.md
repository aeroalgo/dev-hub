# decompose-T-HUB-053-codex-claude-hooks-parity / index

**Plan:** [plan-T-HUB-053-codex-claude-hooks-parity.md](../plan-T-HUB-053-codex-claude-hooks-parity.md)  
**Epic:** T-HUB-053-codex-claude-hooks-parity  
**Role:** BACK  
**Next phase:** BACK IMPLEMENT

---

## Steps

| sNN | Slug | Goal |
|-----|------|------|
| s01 | codex-schema-probe-event-mapping | Probe Codex CLI hooks schema + extend EVENT_MAPPING |
| s02 | manifest-codex-hooks-enable | Enable all missing hooks in manifest for runtimes.codex |
| s03 | generator-nested-matchers-timeouts | Generator: nested matchers + multi-hook merge + timeouts; regenerate .codex/hooks.json |
| s04 | payload-normalize-tool-name-aliases | Payload normalize (tool_name aliases) fail-closed |
| s05 | parity-matrix-runtime-sync-check | Parity matrix module + runtime-sync --check + doctor assertion |
| s06 | behavior-bridge-tests | Behavior bridge tests: all events + stop/spawn regression |
| s07 | docs-runbook-matrix | Docs/runbook/architecture matrix update |
| s08 | legacy-partial-parity-purge | Legacy purge: partial-parity docs/comments + forbid hand-edit |

---

## Requirements coverage

| Requirement | Kind | Closes in | Verify |
|-------------|------|-----------|--------|
| FR-001: manifest declares all Claude hooks with runtimes.codex | FR | s02 | pytest parity matrix + rg manifest |
| FR-002: Required Codex event set ⊇ Claude (SessionStart, UserPromptSubmit, PreToolUse, PostToolUse×2, SubagentStart, SubagentStop, Stop) | FR | s03 | test_codex_hooks_parity_matrix |
| FR-003: hooks_json.py generates nested Claude-shaped .codex/hooks.json with matchers | FR | s03 | pytest + cat .codex/hooks.json |
| FR-004: One Python entrypoint per hook role (no codex fork) | FR | s02+s03 | rg "harness/hooks" .codex/hooks.json |
| FR-005: Payload adapter thin normalize; dual business path FORBIDDEN | FR | s04 | test payload normalize fixtures |
| FR-006: bash-output-cap on Codex uses same PROJECT_OUTPUT_SUMMARY* env path | FR | s06 | test_bash_output_cap_codex fixture |
| FR-007: Agents set on Codex ⊇ Claude managed agents | FR | s05 | parity matrix agent_set check |
| FR-008: runtime-sync --check + doctor parity matrix fail-closed | FR | s05 | pytest test_runtime_sync_check |
| FR-009: Integration tests extend test_codex_hooks_bridge.py | FR | s06 | pytest bridge suite green |
| FR-010: Docs update codex-loop-pilot.md + architecture/services row | FR | s07 | rg matrix row in docs |
| FR-011: Bash PostToolUse timeout ≥ Claude (45s) in generated hooks | FR | s03 | assert timeout in generated json |
| FR-012: Out of scope hooks not added (SessionEnd, PermissionRequest, Pre/PostCompact) | FR (AC−) | s02 | rg verify absence |
| US-001: stop-gate + spawn-gate + subagent start/stop parity on EPIC_RUNTIME=codex | US | s06 | bridge stop/spawn fixtures |
| US-002: bash-output-cap registered for Codex | US | s03+s06 | matrix + unit |
| US-003: bash-output-cap same summary path (021) | US | s04+s06 | unit test structured path |
| US-004: runtime-sync --check fail-closed on drift | US | s05 | test drift fixture |
| SC-001: Generated .codex/hooks.json contains all FR-002 events | SC | s03 | test_codex_hooks_parity_matrix |
| SC-002: stop/spawn/subagent behavior fixtures green | SC | s06 | pytest bridge suite |
| SC-003: bash-output-cap path covered for codex | SC | s06 | pytest + matrix |
| SC-004: runtime-sync --check fails on missing hook | SC | s05 | pytest |
| SC-005: Doctor/runbook document parity matrix | SC | s07 | file assert / doctor test |
| NFR-001: No dual business path (single entrypoint per hook) | NFR | s04 | rg dual-path patterns |
| NFR-002: fail-closed (not silent skip) on drift / missing event | NFR | s05 | test_runtime_sync_check non-zero |
| NFR-003: min Codex CLI version pin in doctor | NFR | s01+s05 | doctor assertion test |
| TM-001: Parity matrix all events after sync | TM | s05 | test_codex_hooks_parity_matrix |
| TM-002: stop-gate deny without verify on codex | TM | s06 | test_codex_hooks_bridge stop fixture |
| TM-003: agent-pretool DENY incomplete prompt | TM | s06 | bridge agent hooks test |
| TM-004: SubagentStart+SubagentStop registered+callable | TM | s02+s05 | parity + smoke |
| TM-005: bash-output-cap in PostToolUse Bash | TM | s06 | unit/integration |
| TM-006: matcher/tool_name alias Bash|shell | TM | s04 | fixture |
| TM-007: doctor fails on missing event | TM | s05 | doctor test |
| TM-008: runtime-sync --check drift detect | TM | s05 | exit 1 fixture |
| TM-009: Claude settings regression unchanged | TM | s06 | settings snapshot test |
| AC-1: .codex/hooks.json complete Claude event matrix | AC+ | s03 | parity matrix |
| AC-2: stop/spawn gates same deny/allow as Claude | AC+ | s06 | bridge fixtures |
| AC-3: runtime-sync --check exit 0 clean | AC+ | s05 | pytest |
| AC-4: No separate codex-specific Python entry | AC+ | s04 | rg |
| AC-5: Claude settings.json unchanged | AC− | s06 | snapshot |
| AC-6: Out-of-scope events absent (SessionEnd etc) | AC− | s02 | rg |

---

## Stages coverage

| Stage (plan §Implementation) | sNN |
|-------------------------------|-----|
| Codex hooks schema probe + document min CLI version | s01 |
| Manifest: enable all missing codex hooks | s02 |
| Generator nested matchers + timeouts + regenerate | s03 |
| Payload normalize tool_name aliases | s04 |
| Parity matrix + runtime-sync --check + doctor | s05 |
| Behavior bridge tests (all events, regression) | s06 |
| Docs / runbook / architecture matrix | s07 |
| Legacy purge (partial-parity docs/comments) | s08 |

---

## Outcome map

| Plan Goal | Outcome in sNN | Measurable verify |
|-----------|---------------|-------------------|
| Codex ≡ Claude для всей hook-поверхности | s02+s03: все events зарегистрированы | parity matrix test green |
| fail-closed на drift / misconfig | s05: runtime-sync --check exit 1 | test_runtime_sync_check |
| bash-output-cap на Codex | s03+s06: PostToolUse Bash зарегистрирован, fixture green | unit + bridge test |
| Payload normalize (tool_name aliases) | s04: thin normalize в _lib | test alias fixtures |
| Min Codex CLI version pin | s01: probe + doctor assertion | doctor test |
| Docs matrix | s07: codex-loop-pilot.md + services row updated | rg row presence |
| No legacy partial-parity shims | s08: deletes + rg clean | rg assertions |

---

## Replacement cleanup

| Kind A (removed symbol/path) | Kind B (replaced by) | Kind C (fallback) | Fallback? | Owner sNN |
|------------------------------|---------------------|-------------------|-----------|-----------|
| Inline `EVENT_MAPPING` with missing entries | Extended EVENT_MAPPING with all FR-002 events | n/a | no | s01+s02 |
| Docs/comments claiming «bash-output-cap partial / Codex hooks partial» | Updated docs with full matrix + runbook | n/a | no | s07+s08 |
| Hand-edit instructions for .codex/hooks.json | Generated-only + meta hash drift check | n/a | no | s08 |

> Финальный purge: s08-legacy-partial-parity-purge — inventory scan + rg anti-fallback.

## Очередь шагов

| step_id | title & files | next_phase | status |
| :--- | :--- | :--- | :--- |
| **s01** | Codex hooks schema probe + extend EVENT_MAPPING · [yaml](s01-codex-schema-probe-event-mapping.yaml) |  | completed |
| **s02** | Manifest enable all missing codex hooks · [yaml](s02-manifest-codex-hooks-enable.yaml) |  | completed |
| **s03** | Generator nested matchers + timeouts + regenerate hooks.json · [yaml](s03-generator-nested-matchers-timeouts.yaml) |  | completed |
| **s04** | Payload normalize tool_name aliases fail-closed · [yaml](s04-payload-normalize-tool-name-aliases.yaml) |  | completed |
| **s05** | Parity matrix module + runtime-sync --check + doctor · [yaml](s05-parity-matrix-runtime-sync-check.yaml) |  | completed |
| **s06** | Behavior bridge tests all events + regression · [yaml](s06-behavior-bridge-tests.yaml) |  | completed |
| **s07** | Docs runbook architecture matrix update · [yaml](s07-docs-runbook-matrix.yaml) |  | completed |
| **s08** | Legacy purge partial-parity docs comments + forbid hand-edit · [yaml](s08-legacy-partial-parity-purge.yaml) |  | completed |