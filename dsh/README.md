# DSH runtime scaffold

Landing zone for the DSH runtime integration. Profile definitions are maintained in T-HUB-007.

## Installation

- Node.js **18 or newer** is required.
- Install the pinned CLI version used by this project:

```bash
npm install -g @deepseek-ai/dsh@VERSION
```

Replace `VERSION` with the reviewed project pin before installation. The DSH CLI is currently considered unstable; verify the pinned version before upgrading it. Keep the `@deepseek-ai/dsh@VERSION` placeholder pinned to the reviewed release; an unreviewed upgrade is not a compatible change (NFR-4).

To install all local profiles and their local `dsh-phase-models` bundle into `$DSH_HOME/profiles/`:

```bash
dsh/scripts/install-profiles.sh
```

The installer requires `pnpm`, defaults to `DSH_HOME=${DSH_HOME:-$HOME/.dsh}`, replaces an existing profile with the same name, copies every `dsh/profiles/epic-*` directory, and runs `pnpm install --ignore-scripts` in each installed profile. Use `--link` for symlinks or `--dry-run` to inspect the planned changes without modifying the filesystem. The local bundle is copied to `$DSH_HOME/patches/`, which keeps the `file:../../patches` dependency valid after installation.

If profiles were copied manually, provision their dependencies before running DSH:

```bash
for profile in "$DSH_HOME"/profiles/epic-*; do
  (cd "$profile" && pnpm install --ignore-scripts)
done
```

The installer is the preferred path because it copies the local bundle and installs dependencies together.

> `--link` keeps profile directories linked to this checkout; it still installs dependencies into each profile and therefore requires a writable checkout.

## Environment

Set the API key and runtime explicitly in the product environment:

```bash
export DEEPSEEK_API_KEY=sk-...
export EPIC_RUNTIME=dsh
```

`DSH_BIN` is an optional override containing the path to an executable DSH binary. When it is not set, `dsh/bin/which-dsh.sh` resolves a globally installed `dsh`, then falls back to `npx -y @deepseek-ai/dsh` when `npx` is available.

## Profiles

Profiles live at `dsh/profiles/<name>/` and are composed from `package.json`, `cordis.yml`, and `cordis.patch.yml`. Each loop phase has a matching profile:

| Loop phase | Profile | Presets | Primary model env |
|---|---|---|---|
| DECOMPOSE | `epic-decompose` | `explorer` | `PROJECT_LOOP_DECOMPOSE_MODEL` |
| PLAN | `epic-plan` | — | `PROJECT_LOOP_PLAN_MODEL` |
| CREATIVE | `epic-creative` | — | `PROJECT_LOOP_CREATIVE_MODEL` |
| IMPLEMENT | `epic-implement` | `verify`, `explorer` | `PROJECT_LOOP_IMPLEMENT_MODEL` |
| AUDIT | `epic-audit` | `explorer` | `PROJECT_LOOP_AUDIT_MODEL` |
| QA | `epic-qa` | `reviewer` | `PROJECT_LOOP_QA_MODEL` |
| BUGFIX | `epic-bugfix` | `verify`, `explorer` | `PROJECT_LOOP_BUGFIX_MODEL` |
| REFLECT | `epic-reflect` | — | `PROJECT_LOOP_REFLECT_MODEL` |

The profile selected by the loop is exposed through `EPIC_DSH_PROFILE`; the installer makes all eight phase profiles available under `$DSH_HOME/profiles/`.

## Env bridge

Each profile's `cordis.patch.yml` maps its phase model environment variable to the DSH `llm` service's `model` field. For example, `PROJECT_LOOP_IMPLEMENT_MODEL` is read by `epic-implement/cordis.patch.yml` and applied to the `llm.config.model` row; the same mapping is used for the other `PROJECT_LOOP_<PHASE>_MODEL` variables:

| Environment variable | DSH patch target |
|---|---|
| `PROJECT_LOOP_DECOMPOSE_MODEL` | `llm.config.model` in `epic-decompose/cordis.patch.yml` |
| `PROJECT_LOOP_PLAN_MODEL` | `llm.config.model` in `epic-plan/cordis.patch.yml` |
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

The output must include the `verify` preset and the `dsh-phase-models` bundle. Repeat the command with each `epic-*` profile to verify the complete phase matrix.

If the command reports `cannot resolve profile bundle "dsh-phase-models"`, the profile dependencies have not been installed; run `dsh/scripts/install-profiles.sh` or the manual `pnpm install --ignore-scripts` loop above.

## Running

From the product root, run the loop with the DSH runtime selected:

```bash
PROJECT_ROOT=/path/to/product EPIC_RUNTIME=dsh make loop ARGS=gpt
```

The loop resolves DSH through `DSH_BIN` or `dsh/bin/which-dsh.sh` and invokes it with the selected profile.

## Memory-bank board sync

`bin/hub-board sync` projects eligible work from registered product workspaces into the DSH task board. It reads the workspace registry at `$DSH_HOME/storages/workspace.json`; a workspace is eligible when its path contains a `memory-bank/` directory. Run it from the hub checkout, or pass an absolute path to the hub wrapper:

```bash
DSH_HOME=$HOME/.dsh ./bin/hub-board sync
```

Use `--dry-run` to inspect the desired changes without writing them. `--workspace-id ID` limits a run to one registered workspace. For local development or tests without a DSH Host, use `--offline-ledger PATH`; `LedgerFileClient` is a dev/test and offline-only fallback, not the production Host transport:

```bash
./bin/hub-board sync \
  --dsh-home "$DSH_HOME" \
  --offline-ledger /tmp/dev-hub-board.json \
  --dry-run
```

The board contains two kinds of cards:

- **Step cards** represent a concrete `sNN` implement step. Their title includes the role, `epic_id`, and `step_id`, and their prompt is the corresponding `BACK IMPLEMENT` command.
- **Gate cards** represent lifecycle gates such as `CLARIFY`, `ANALYZE`, `TIPS`, or `ROADMAP`. Their title identifies the gate phase and, when applicable, the `epic_id`; their prompt is the matching role command.

In the DSH UI, filter the task board by the card metadata field `epic_id` to see all step and gate cards for one epic. A step card and a gate card are separate board items even when they belong to the same epic, so use the card kind and gate phase when distinguishing them.

For a periodic development sync, keep the job scoped to the checkout and log output for review:

```cron
*/15 * * * * cd /home/aero/PyProject/dev-hub && DSH_HOME=$HOME/.dsh ./bin/hub-board sync >>$HOME/.cache/hub-board-sync.log 2>&1
```

The live default uses the DSH Host API at `DSH_TASK_BOARD_HOST_URL` (or `http://127.0.0.1:5173`). Use `--host-url URL` when a one-off sync needs an explicit Host endpoint; the offline ledger option should not be used as a substitute for the live Host in production automation.

## Board Arm/Loop (T-HUB-015)

The `mb-*` board flow is deliberately explicit and fail-closed:

```text
sync → filter workspace → choose model preset → Arm+Run
  └─ arm writes the product activeContext, then loop runs PROJECT_ROOT
       └─ optional syncAfterLoop refreshes the board (including failed runs)
```

Install the local Cordis bridge into the DSH plugins directory with `DEV_HUB` pointing at this checkout:

```bash
DEV_HUB=/home/aero/PyProject/dev-hub \
  DSH_HOME=${DSH_HOME:-$HOME/.dsh} \
  dsh/scripts/install-mb-bridge.sh
```

The bridge copies `dsh/plugins/mb-bridge` to `$DSH_HOME/plugins/mb-bridge`; it does not publish a package or execute browser-supplied shell commands. A missing or invalid `DEV_HUB`, source plugin, or destination layout stops installation.

### Model precedence

| Priority | Source | Behavior |
|---|---|---|
| 1 | Product `.claude/project.env` — `PROJECT_LOOP_<PHASE>_MODEL` | Non-empty phase override wins; an empty value does not override anything. |
| 2 | Board model preset | Validated preset arguments are appended to the loop argv. |
| 3 | Bridge `defaultLoopArgs` | Used when no env model or preset is selected. |
| 4 | Bare loop argv | Used when none of the above supplies model arguments. |

Use the workspace dropdown to select a `workspace_id`, or choose `All` to show cards from every eligible registered product workspace. The selection is stored in `localStorage` as `mb-bridge.workspaceFilter`; the model and runtime controls are independent, and `Sync` refreshes the current board projection.

### Troubleshooting

| Symptom | Resolution |
|---|---|
| `flock` / `another loop runner is already active` | Only one loop may run for a product root. Wait for the existing run to finish, then retry; do not bypass the lock. |
| `step_mismatch` | The arm response does not match the card `step_id`. Refresh with `Sync`, verify the card metadata and active step, then arm again. |
| Missing `DEV_HUB` / `DEV_HUB is required` | Export `DEV_HUB` as the absolute dev-hub checkout before running `hub-board arm`, `loop`, `arm-loop`, or the installer. |
| `mb_card_requires_loop_run` | The mb-bridge is not handling stock run. Install/enable `@dev-hub/dsh-mb-bridge`; never fall back to a free-session stock run for `mb-*` cards. |

## Version pinning

Keep `@deepseek-ai/dsh@VERSION` pinned in installation instructions and review changes deliberately. The DSH CLI is unstable during this landing phase; do not treat an unreviewed version upgrade as a compatible change.
