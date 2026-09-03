# Harness

`harness/` is the canonical Source of Truth (SoT) for repo hooks, agents, instructions, skills, commands, and rules.

- `harness/` contains the behavior and business logic of execution rules.
- `.claude/` in dev-hub acts as a thin symlink shell referencing `harness/` (`harness/agents/`, `harness/hooks/`, `harness/claude/commands/`, `harness/claude/skills/`, `harness/claude/rules/`).
- `.agents/skills` in dev-hub is a thin symlink shell referencing `harness/skills/`.
- `harness/cursor/rules/` is the canonical Source of Truth for cursor rules; `@.cursor/rules` references remain functional via symlinks.

## Target Layout

| Component | Source of Truth (SoT) | Shell / Consumer symlink (dev-hub & product) |
|---|---|---|
| Claude Commands | `harness/claude/commands/` | `.claude/commands` -> `harness/claude/commands` |
| Claude Skills | `harness/claude/skills/` | `.claude/skills` -> `harness/claude/skills` |
| Claude Rules | `harness/claude/rules/` | `.claude/rules` -> `harness/claude/rules` |
| Agent Skills | `harness/skills/` | `.agents/skills` -> `harness/skills` |
| Claude Agents | `harness/agents/` | `.claude/agents` -> `harness/agents` |
| Claude Hooks | `harness/hooks/` | `.claude/hooks` -> `harness/hooks` |
| Cursor Rules | `harness/cursor/rules/` | `.cursor/rules` -> `harness/cursor/rules` |
| Cursor Templates | `harness/cursor/templates/` | `.cursor/templates` -> `harness/cursor/templates` |

## Install Modes

`bin/hub-link` provides two installation modes for integrating harness tooling into target repositories: `alongside` (default) and `full`.

### 1. Alongside Mode (`--mode alongside`, default)

Non-destructive integration designed for external product repositories. It layers the dev-hub harness alongside existing repository configuration without replacing product files.

```bash
# From dev-hub
./bin/hub-link [/path/to/product]
./bin/hub-link --mode alongside [/path/to/product]

# Unlink / uninstall
./bin/hub-unlink [/path/to/product]
./bin/hub-unlink --mode alongside [/path/to/product]
```

#### What alongside mode does:
- Symlinks `harness/` -> `$DEV_HUB/harness`
- Writes relative path to `$DEV_HUB` in `.dev-hub`
- Places router stub at `.cursor/rules.d/dev-hub-harness-router.mdc`
- Symlinks `CLAUDE.harness.md` -> `$DEV_HUB/harness/claude/CLAUDE.harness.md`
- Patches `CLAUDE.md` using marker blocks (`<!-- dev-hub:harness:start -->` ... `<!-- dev-hub:harness:end -->`) preserving user instructions
- Merges hooks from `harness/claude/settings.harness.json` into `.claude/settings.json` preserving user permissions; hook commands point to `harness/hooks/*.py` (via product `harness/` symlink), not `.claude/hooks/`
- Creates `AGENTS.md` stub if missing

#### What alongside mode does not touch:
- Does not overwrite or replace existing `.cursor/rules`
- Does not replace user `CLAUDE.md` or `.claude/settings.json` permissions

> **Note:** Never run `alongside` mode directly against dev-hub root (`/home/aero/PyProject/dev-hub`). In dev-hub, harness is dogfooded natively.

---

### 2. Full Mode (`--mode full`)

Full replacement mode used for dev-hub dogfooding and complete environment replication. Requires explicit `--mode=full`.

```bash
# Link full environment
./bin/hub-link --mode full [/path/to/product]

# Unlink full environment
./bin/hub-unlink --mode full [/path/to/product]
```

#### What full mode does:
- Symlinks `.cursor/rules`, `.cursor/templates`, `.agents`, `CLAUDE.md`, and `harness/` directly to dev-hub
- Symlinks all `.claude/` subdirectories (`agents`, `hooks`, `skills`, `commands`, `instructions`, `rules`) and root files (`settings.json`, `project.env`)
- Sets up `.claude/runtime` and `.claude/worktrees`
- Replaces configuration with hub-managed symlinks

#### Regression & Testing Note:
- CI and test suites testing full integration fixture layouts must pass `--mode=full` explicitly.
