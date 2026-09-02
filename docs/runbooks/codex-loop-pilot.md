# Codex Loop Pilot Runbook

> **⚠️ DEVELOPER PREVIEW**  
> Codex runtime is currently in **developer preview**. The default runtime remains `EPIC_RUNTIME=claude`.  
> Codex is **not** a production default.

---

## 1. Prerequisites

Before running the Codex pilot loop, ensure your environment meets the following requirements:

- **Codex CLI**: `codex` binary installed and accessible in `$PATH`.
- **Python**: `≥ 3.12` (for runtime sync and doctor checks).
- **API Credentials / Auth**: Active Codex session / login via `codex login` or `CODEX_API_KEY` set in your environment.
- **Runtime Registry**: `loop/runtime_registry.yaml` containing the `codex` runtime entry.

---

## 2. Install & Auth

Follow these steps to set up Codex CLI and authenticate:

1. **Install Codex CLI**:
   Ensure `codex` binary is installed and present in your system `$PATH`.

2. **Authenticate**:
   Run Codex login to establish active session credentials:
   ```bash
   codex login
   ```
   Or set `CODEX_API_KEY` in your environment.

3. **Link Product Repository**:
   Link your product repository with the hub harness by establishing `.dev-hub` symlinks:
   ```bash
   ./bin/hub-link /path/to/target-project
   ```

---

## 3. Runtime Sync

Before launching the loop with Codex, perform a runtime sync check to verify configuration alignment:

1. **Check Sync Drift**:
   Run the runtime sync verification tool:
   ```bash
   bin/runtime-sync --check --runtime codex
   ```
   Expected Output:
   ```
   No drift detected
   ```

2. **Synchronize Registry / Adapters (if drift detected)**:
   ```bash
   bin/runtime-sync --apply --runtime codex
   ```

   A clean checkout prints `No drift detected` and exits with status `0`. If
   drift is reported, the check exits non-zero by design; apply the sync and
   repeat the check before launching the pilot.

---

## 4. Environment

Configure environment variables governing Codex execution:

- `EPIC_RUNTIME`: Set to `codex` to activate the Codex harness (`EPIC_RUNTIME=codex`). Defaults to `claude`.
- `CODEX_API_KEY`: (Optional) API key for Codex endpoints if not authenticated via CLI session.
- `PROJECT_ROOT`: Absolute path to the product repository being operated on.

---

## 5. Launch

Execute the loop runner with `EPIC_RUNTIME=codex`:

```bash
EPIC_RUNTIME=codex ./bin/loop /path/to/target-project
```

Or using explicit `PROJECT_ROOT`:

```bash
export PROJECT_ROOT=/path/to/target-project
export EPIC_RUNTIME=codex
./bin/loop
```

Or via Make target:

```bash
EPIC_RUNTIME=codex make loop
```

---

## 6. Troubleshooting

| Symptom / Error | Cause | Solution |
| :--- | :--- | :--- |
| `codex: command not found` (exit 127) | Codex binary missing or not in `$PATH` | Install `codex` binary and ensure `$PATH` includes its location. |
| `Runtime sync drift detected` | Registry and runtime adapter definitions out of sync | Run `bin/runtime-sync --apply --runtime codex` to resync. |
| `Doctor preflight failure` | Doctor runtime checks failed during startup | Run `python3 loop/context_loop.py --cwd "$PROJECT_ROOT" doctor --json` to inspect failed runtime assertions. |
| `Authentication error / Token expired` | Codex session unauthenticated or expired | Execute `codex login` or refresh `CODEX_API_KEY`. |
| `RuntimeConfigError: EPIC_RUNTIME=invalid` | Invalid runtime specified | Ensure `EPIC_RUNTIME` is set to `codex`, `dsh`, or `claude`. |

---

## 7. Pilot Checklist

Complete the sign-off checklist below prior to certifying a Codex rollout pilot:

| # | Step | Command / Check | Pass Criteria | Sign-off (Date & Operator) |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Verify Codex Binary | `which codex` | Output points to valid executable | |
| 2 | Check Auth | `codex login` / `echo $CODEX_API_KEY` | Valid active session or key present | |
| 3 | Hub Link Setup | `./bin/hub-link /path/to/target-project` | `.dev-hub` path file created in target project | |
| 4 | Runtime Sync Check | `bin/runtime-sync --check --runtime codex` | Reports sync OK without drift | |
| 5 | Active Pilot Loop Run | `EPIC_RUNTIME=codex ./bin/loop /path/to/target-project` | Loop executes target epic steps using Codex runtime | |
| 6 | Verify Gate Parity Check | Check step implementation & verify output | Verify gate executes and reports PASS on step completion | |
| 7 | Fallback Parity Check | `EPIC_RUNTIME=claude ./bin/loop /path/to/target-project` | Fallback to default `claude` runtime runs without regression | |
| 8 | Final Sign-off | Review logs & artifact output | All checks pass; runbook sign-off recorded | |
