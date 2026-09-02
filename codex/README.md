# Codex Integration Engine

Codex CLI integration contract for `loop/runtime_adapters/codex.py`.

## Installation & Authentication

1. **Installation:**
   ```bash
   npm i -g @openai/codex
   ```

2. **OmniRoute (recommended for this hub):**
   ```bash
   ./codex/bin/setup-omniroute.sh
   ./codex/bin/codex-omniroute.sh exec --ephemeral --dangerously-bypass-approvals-and-sandbox "say hi"
   ```

   Setup writes:
   - `~/.codex/config.toml` — `model_provider = "omniroute"`, `base_url = http://localhost:20128/v1`
   - `~/.codex/.omniroute_key` — API key (same source as Claude Code / hooks)

   Default model: `cx/gpt-5.6-luna-xhigh` (OmniRoute id, not native ChatGPT slug).

   Disable wrapper routing: `CODEX_USE_OMNIROUTE=0 codex …`

3. **Direct ChatGPT login (without OmniRoute):**
   ```bash
   codex login
   ```
   Use native slugs only: `gpt-5.6-luna` + `model_reasoning_effort=xhigh`. Prefix `cx/` fails on ChatGPT auth.

4. **Environment Override:**
   ```bash
   export CODEX_BIN="/path/to/custom/codex"
   export OMNIROUTE_API_KEY_FILE=~/.codex/.omniroute_key
   ```

## Usage with Loop

To run the loop with Codex runtime:

1. Synchronize manifest hooks and materializers for Codex:
   ```bash
   bin/runtime-sync --apply --runtime codex
   ```

2. Configure OmniRoute (once):
   ```bash
   ./codex/bin/setup-omniroute.sh
   ```

3. Invoke loop with `EPIC_RUNTIME=codex` and OmniRoute model ids:
   ```bash
   EPIC_RUNTIME=codex PROJECT_LOOP_IMPLEMENT_MODEL=cx/gpt-5.6-luna-xhigh make loop
   # or directly via CLI:
   bin/loop --runtime codex /path/to/product
   ```

   `which-codex.sh` auto-selects `codex-omniroute.sh` when `~/.codex/config.toml` contains the OmniRoute provider and key file exists.
