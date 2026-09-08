# DSH runtime scaffold

Landing zone for the DSH runtime integration. Profile definitions are maintained in T-HUB-007.

> **Related Architecture & Runbooks:**
> - Architectural overview: [`memory-bank/architecture/dsh-runtime.md`](../memory-bank/architecture/dsh-runtime.md)
> - Pilot execution runbook: [`docs/runbooks/dsh-loop-pilot.md`](../docs/runbooks/dsh-loop-pilot.md)
>
> **Note:** DSH Runtime is currently in developer preview and is not the production default.

## Installation

- Node.js **18 or newer** is required.
- Install the pinned CLI version used by this project:

```bash
npm install -g @deepseek-ai/dsh@0.1.1-rc.2
```

The reviewed CLI pin is `0.1.1-rc.2`; install the exact version shown above and review compatibility before upgrading it. The DSH CLI is currently considered unstable, and an unreviewed version upgrade is not a compatible change (NFR-4).

Loop automatically installs all local profiles, the shared `dsh-phase-models`
bundle and its hooks-bridge dependency, the discoverable agent presets, and the
compiled local `epic-gate` plugin when `EPIC_RUNTIME=dsh` is selected. The manual
command below is useful for prewarming or repairing the DSH home:

```bash
dsh/scripts/install-profiles.sh
```

The installer requires `pnpm`, defaults to `DSH_HOME=${DSH_HOME:-$HOME/.dsh}`, replaces an existing profile with the same name, copies every `dsh/profiles/epic-*` directory, installs the shared bundle dependencies, copies the preset roots, builds `epic-gate` to JavaScript, and runs `pnpm install --ignore-scripts` in each installed profile. Use `--link` for symlinks or `--dry-run` to inspect the planned changes without modifying the filesystem. The local bundle and presets are copied to `$DSH_HOME/patches/` and `$DSH_HOME/presets/`; this keeps the `file:../../patches` dependency and preset root valid after installation.

Headless epic profiles emit bounded live progress while the agent is running.
The loop shows the current LLM step and tool action, for example
`==> dsh: LLM request turn=1 step=2` or `==> dsh: Bash pytest ...`; the final
assistant response is printed after the run completes. Long streamed LLM
responses produce a periodic `LLM streaming` notice so the session is visibly
active during model generation.

If profiles were copied manually, provision the shared bundle and local plugin first, then provision each profile:

```bash
(cd "$DSH_HOME/patches" && pnpm install --ignore-scripts)
(cd "$DSH_HOME/plugins/epic-gate" && pnpm install --ignore-scripts && pnpm run build)
for profile in "$DSH_HOME"/profiles/epic-*; do
  (cd "$profile" && pnpm install --ignore-scripts)
done
```

The installer is the preferred path because it copies the local bundle and installs dependencies together.

Mount the Claude Code command-hook bridge into the installed profiles with:

```bash
dsh/scripts/install-cc-hooks.sh
```

This copies `dsh/patches/cc-hooks-bridge.yml` to `$DSH_HOME/patches/cc-hooks-bridge.yml` and mounts it into each installed `epic-*` profile. Dependency installation is performed once by `install-profiles.sh`; the hooks installer does not repeat it. Use `--link` to symlink the fragment or `--dry-run` to inspect the plan without changing the filesystem; profiles missing from `$DSH_HOME/profiles/` are reported and skipped. In headless CI, set `DSH_HOME` to the job-local DSH directory and run the same non-interactive command after `install-profiles.sh`, for example `DSH_HOME="$RUNNER_TEMP/dsh" dsh/scripts/install-cc-hooks.sh`.

> `--link` keeps profile directories linked to this checkout; it still installs dependencies into each profile and therefore requires a writable checkout.

## Environment

Set the API key and runtime explicitly in the product environment:

```bash
export DEEPSEEK_API_KEY=sk-...
export EPIC_RUNTIME=dsh
```

`DSH_BIN` is an optional override containing the path to an executable DSH binary. When it is not set, `dsh/bin/which-dsh.sh` resolves a globally installed `dsh`, then falls back to `npx -y @deepseek-ai/dsh` when `npx` is available.

When the loop runs with `EPIC_RUNTIME=dsh`, it exports `DSH_HOOKS_BRIDGE=1`, sets `CLAUDE_PROJECT_DIR=$PROJECT_ROOT` for the mounted Claude hooks, and keeps `DEV_HUB` pointed at the dev-hub checkout. With the default Claude runtime, `CLAUDE_PROJECT_DIR` remains the hub path used by the loop runner.

The loop also exports the resolved `MODEL` value as `PROJECT_LOOP_DSH_MODEL` and
selects it through DSH's `agent-default-model` service. The DSH settings file is
disabled for loop profiles, so `~/.dsh/settings.yaml` cannot replace the model.

| Environment variable | Value under DSH | Purpose |
|---|---|---|
| `DSH_HOOKS_BRIDGE` | `1` | Signals that the Claude command-hook bridge is active. |
| `CLAUDE_PROJECT_DIR` | `$PROJECT_ROOT` | Product root used by the bridge for `projectDir`, `.claude/settings.json`, and hook paths. |
| `DEV_HUB` | hub checkout | Hub root used by hooks and board tooling. |
| `PROJECT_LOOP_DSH_MODEL` | resolved `MODEL` | Exact model ID selected for the DSH session. |

## Profiles

Profiles live at `dsh/profiles/<name>/` and are composed from `package.json`, `cordis.yml`, and `cordis.patch.yml`. Each loop phase has a matching profile:

| Loop phase | Profile | Presets | Primary model env |
|---|---|---|---|
| DECOMPOSE | `epic-decompose` | `explorer` | `PROJECT_LOOP_DECOMPOSE_MODEL` |
| PLAN | `epic-plan` | — | `PROJECT_LOOP_PLAN_MODEL` |
| ANALYZE | `epic-analyze` | — | `PROJECT_LOOP_ANALYZE_MODEL` |
| CREATIVE | `epic-creative` | — | `PROJECT_LOOP_CREATIVE_MODEL` |
| IMPLEMENT | `epic-implement` | `verify`, `explorer` | `PROJECT_LOOP_IMPLEMENT_MODEL` |
| AUDIT | `epic-audit` | `explorer` | `PROJECT_LOOP_AUDIT_MODEL` |
| QA | `epic-qa` | `reviewer` | `PROJECT_LOOP_QA_MODEL` |
| BUGFIX | `epic-bugfix` | `verify`, `explorer` | `PROJECT_LOOP_BUGFIX_MODEL` |
| REFLECT | `epic-reflect` | — | `PROJECT_LOOP_REFLECT_MODEL` |

The profile selected by the loop is exposed through `EPIC_DSH_PROFILE`; the installer makes all nine phase profiles available under `$DSH_HOME/profiles/`.

## Env bridge

Each profile's `cordis.patch.yml` maps its phase model environment variable to the DSH `llm` service's `model` field. For example, `PROJECT_LOOP_IMPLEMENT_MODEL` is read by `epic-implement/cordis.patch.yml` and applied to the `llm.config.model` row; the same mapping is used for the other `PROJECT_LOOP_<PHASE>_MODEL` variables:

| Environment variable | DSH patch target |
|---|---|
| `PROJECT_LOOP_DECOMPOSE_MODEL` | `llm.config.model` in `epic-decompose/cordis.patch.yml` |
| `PROJECT_LOOP_PLAN_MODEL` | `llm.config.model` in `epic-plan/cordis.patch.yml` |
| `PROJECT_LOOP_ANALYZE_MODEL` | `llm.config.model` in `epic-analyze/cordis.patch.yml` |
| `PROJECT_LOOP_CREATIVE_MODEL` | `llm.config.model` in `epic-creative/cordis.patch.yml` |
| `PROJECT_LOOP_IMPLEMENT_MODEL` | `llm.config.model` in `epic-implement/cordis.patch.yml` |
| `PROJECT_LOOP_AUDIT_MODEL` | `llm.config.model` in `epic-audit/cordis.patch.yml` |
| `PROJECT_LOOP_QA_MODEL` | `llm.config.model` in `epic-qa/cordis.patch.yml` |
| `PROJECT_LOOP_BUGFIX_MODEL` | `llm.config.model` in `epic-bugfix/cordis.patch.yml` |
| `PROJECT_LOOP_REFLECT_MODEL` | `llm.config.model` in `epic-reflect/cordis.patch.yml` |

The patch also passes `DSH_HOME/.credentials.yaml` to the DSH credentials field. If a phase variable is unset, the profile uses the DSH `default` model.

## Smoke test

Without an installed DSH CLI, the smoke test is skipped in CI. After running the installer (or provisioning dependencies for manually copied profiles), run:

```bash
DSH_HOME=${DSH_HOME:-$HOME/.dsh} dsh --profile epic-implement --dump-config
```

The output must include the `agent-instructions` entry restricted to `AGENTS.md`, the `agent-presets` roster, and the `dsh-phase-models` bundle. The `settings`, `skill-filesystem`, and `tool-skill` entries must be disabled. `--dump-config` only serializes the profile; to exercise plugin loading, run a real profile command after credentials are configured, for example `DSH_HOME=${DSH_HOME:-$HOME/.dsh} dsh --profile epic-implement 'diagnostic boot only'`. Repeat the command with each `epic-*` profile to verify the complete phase matrix.

If the command reports `cannot resolve profile bundle "dsh-phase-models"`, the profile dependencies have not been installed; run `dsh/scripts/install-profiles.sh` or the manual `pnpm install --ignore-scripts` loop above.

## Running

From the product root, run the loop with the DSH runtime selected:

```bash
PROJECT_ROOT=/path/to/product EPIC_RUNTIME=dsh make loop ARGS=gpt
```

The loop resolves DSH through `DSH_BIN` or `dsh/bin/which-dsh.sh` and invokes it with the selected profile.

## Hooks bridge

The DSH profiles use the official `@deepseek-ai/dsh-hooks-claude-code@0.0.1-rc.5` bridge to invoke the existing command hooks from `.claude/settings.json`. The bridge mounts the product project directory and keeps the Claude hook scripts as the source of truth; it does not port those scripts into TypeScript or replace the Claude runtime path.

| Hook event | Python hook | Bridge status | Mount action | Gap owner |
|---|---|---|---|---|
| SessionStart | `session-start.py` | bridge-ok: native first-turn injection | mount | self |
| UserPromptSubmit | `user-prompt.py` | ok | mount | self-limit |
| PreToolUse (Agent\|Task) | `agent-pretool.py` | deny works; `updatedInput` unavailable | mount | T-HUB-008 (deferred, Gap A) |
| PreToolUse (Bash) | `bash-pretool.py` | ok | mount | self-limit |
| PostToolUse (Agent\|Task) | `agent-posttool.py` | partial | mount | T-HUB-008 (deferred, Gap B) |
| PostToolUse (Bash) | `bash-output-cap.py` | partial | mount | T-HUB-008 (deferred, Gap B) |
| SubagentStart | `subagent-start.py` | native `subagent/start` maps supported `agent_type`/preset values; Python hook remains authoritative | mount | T-HUB-008 (closed, Gap B) |
| SubagentStop | `subagent-stop.py` | transcript/verdict enrichment | mount | T-HUB-008 (closed, Gap C) |
| Stop | `stop-gate.py` | block→continue; DSH self-limit required | mount | self-limit |

Known bridge limits and their executable coverage are recorded in
`dsh/plugins/epic-gate/README.md`. T-HUB-008 closes the native SubagentStart,
SubagentStop and SessionStart parity paths (Gaps B–D); the DSH API limitation for
`updatedInput` remains explicitly deferred (Gap A). The official bridge
mount, pinned versions, and DSH Stop self-limit remain owned by T-HUB-016. A
misconfigured `configPath` must be treated as a loud bridge warning; required
hooks must not silently fall back to a free-session run.

### Known gaps → T-HUB-008

The gap matrix above is closed/deferred rather than open: see
`dsh/plugins/epic-gate/README.md` for the four-row parity matrix and owners.
T-HUB-008 scope is limited to those rows; SessionStart first-turn semantics are
closed as bridge-ok.


## Version pinning
| Package | Reviewed pin | Installation policy |
|---|---|---|
| `@deepseek-ai/dsh` | `0.1.1-rc.2` | install the exact version; review before upgrading |
| `@deepseek-ai/dsh-hooks-claude-code` | `0.0.1-rc.5` | install the exact version; verify compatibility before upgrading |

Install only reviewed pins, for example:

```bash
npm install -g @deepseek-ai/dsh@0.1.1-rc.2
npm install @deepseek-ai/dsh-hooks-claude-code@0.0.1-rc.5 --save-exact
```

The DSH CLI and bridge are unstable during this landing phase; an unreviewed version upgrade is not a compatible change (NFR-4). The pinned bridge package is recorded in `dsh/patches/package.json` for profile tooling.

For native `subagent/start`, the plugin resolves only explicit `verify`, `reviewer`, or `explorer` identities (including `preset.<type>` and child `agentPreset`). It forwards a canonical `agent_type` plus `preset.<type>` to `.claude/hooks/subagent-start.py`, which remains the contract source of truth. Unknown or `general-purpose` identities are ignored without injection; the adapter resolves the product hook cwd from `EPIC_PROJECT_ROOT` (FR-009 alias), `PROJECT_ROOT`, or `CLAUDE_PROJECT_DIR`, so a hub cwd cannot redirect the bridge. Conflicting project root aliases trigger a fail-closed error.

> `@deepseek-ai/dsh@0.1.1-rc.2` and `@deepseek-ai/dsh-hooks-claude-code@0.0.1-rc.5` were checked with npm registry metadata on 2026-08-29; re-check engines and compatibility before changing either pin.

## Native workflow traversal

DSH starts with the product `AGENTS.md`. Its native `read` tool then follows the
selected role/phase chain through `.cursor/rules/mainrule.mdc`, workflow `@` links,
Gates, the current shard, and only the explicitly declared `SKILL.md` files.
The global `.agents/skills` catalog and Claude Code asset compatibility mount are
not loaded into the DSH system prompt by default. DSH uses native lowercase tool
names: `read`, `write`, `edit`, and `bash`; the IMPLEMENT profile additionally
mounts `@dev-hub/dsh-tool-name-compat`, which registers bounded Claude-name
aliases and delegates `Read`/`Write`/`Edit`/`Bash` calls to the native tools.
Session progress reports failed tool results with their name, call id, and
bounded error text.
