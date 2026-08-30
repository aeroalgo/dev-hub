# DSH Loop Pilot Runbook

> **⚠️ DEVELOPER PREVIEW**  
> DSH runtime is currently in **developer preview**. The default runtime remains `EPIC_RUNTIME=claude`.  
> DSH is **not** a production default.

---

## 1. Prerequisites

Before running the DSH pilot loop, ensure your environment meets the following requirements:

- **Node.js**: `≥ 22.0.0` (check via `node -v`).
- **DSH CLI / Hooks**: `@deepseek-ai/dsh` or pinned `@deepseek-ai/dsh-hooks-claude-code` (`v0.0.1-rc.5` pinned in `dsh/patches/package.json`).
- **API Credentials**: `DEEPSEEK_API_KEY` set in your environment variables or configured in `~/.dsh/.credentials.yaml`.

---

## 2. Install

Follow these steps to set up DSH profile presets and hooks for your repository:

1. **Install Profiles**:
   Run the profile installer to copy `epic-*` profiles to `DSH_HOME` (default: `~/.dsh`):
   ```bash
   ./dsh/scripts/install-profiles.sh
   ```

2. **Sync Preset Agents**:
   Synchronize subagent definitions from `.claude/agents/*.md` to DSH presets:
   ```bash
   python3 dsh/scripts/sync-agent-md-to-presets.py
   ```

3. **Link Product Repository**:
   Link your product repository with the hub harness by establishing `.dev-hub` symlinks:
   ```bash
   ./bin/hub-link /path/to/target-project
   ```

---

## 3. Environment

Configure environment variables governing DSH execution:

- `EPIC_RUNTIME`: Set to `dsh` to activate the DeepSeek harness (`EPIC_RUNTIME=dsh`). Defaults to `claude`.
- `DEEPSEEK_API_KEY`: API key for DeepSeek LLM endpoints.
- `DSH_HOME`: (Optional) Root directory for DSH configuration, presets, and logs. Defaults to `~/.dsh`.
- `PROJECT_ROOT`: Absolute path to the product repository being operated on.

---

## 4. First Run

Execute the loop runner with `EPIC_RUNTIME=dsh`:

```bash
EPIC_RUNTIME=dsh ./bin/loop /path/to/target-project
```

Or using explicit `PROJECT_ROOT`:

```bash
export PROJECT_ROOT=/path/to/target-project
export EPIC_RUNTIME=dsh
./bin/loop
```

---

## 5. Troubleshooting

| Symptom / Error | Cause | Solution |
| :--- | :--- | :--- |
| `dsh: command not found` (exit 127) | Node.js / DSH CLI missing or not in `$PATH` | Install Node `≥ 22` and install DSH via `npm install -g @deepseek-ai/dsh`. |
| `Profile not found` | Profiles not installed to `DSH_HOME` | Run `./dsh/scripts/install-profiles.sh`. |
| `Verify gate deny` | Step evidence or verification check failed in hooks | Inspect verify hook logs under `.claude/runtime/logs/` and resolve failing criteria. |
| `API 429 Too Many Requests` | DeepSeek API rate limit hit | Rate limit exceeded. Wait or implement backoff/retry in profile parameters. |
| `RuntimeConfigError: EPIC_RUNTIME=invalid` | Invalid runtime specified | Ensure `EPIC_RUNTIME` is set to `dsh` or `claude`. |

---

## 6. Pilot Checklist

Complete the 10-step sign-off checklist below prior to certifying a DSH rollout pilot:

| # | Step | Command / Check | Pass Criteria | Sign-off (Date & Operator) |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Verify Node Version | `node -v` | Output is `≥ v22.0.0` | |
| 2 | Check API Credentials | `echo $DEEPSEEK_API_KEY` | Key is present or credential file exists | |
| 3 | Install Profiles | `./dsh/scripts/install-profiles.sh` | Profiles successfully copied to `~/.dsh/profiles` | |
| 4 | Sync Presets | `python3 dsh/scripts/sync-agent-md-to-presets.py` | Agent markdown files synced without error | |
| 5 | Hub Link Setup | `./bin/hub-link /path/to/target-project` | `.dev-hub` symlink created in target project | |
| 6 | Dry Run Verification | `EPIC_RUNTIME=dsh ./bin/loop /path/to/target-project --dry-run` | Execution plan resolves without config errors | |
| 7 | Active Pilot Loop Run | `EPIC_RUNTIME=dsh ./bin/loop /path/to/target-project` | Loop executes target epic steps using DSH runtime | |
| 8 | Verify Gate Parity Check | Check step implementation & verify output | Verify gate executes and reports PASS on step completion | |
| 9 | Fallback Parity Check | `EPIC_RUNTIME=claude ./bin/loop /path/to/target-project` | Fallback to default `claude` runtime runs without regression | |
| 10 | Final Sign-off | Review logs & artifact output | All 10 checks pass; runbook sign-off recorded | |
