# Bugfix: Context Fingerprint and Search Wire Path Alignment
**Epic ID:** T-HUB-100-context-fingerprint-search-wire  
**Date:** 2026-09-15  
**Author:** BACK BUGFIX  
**Source:** memory-bank/back/qa/T-HUB-100-context-fingerprint-search-wire/qa-20260915-context-fingerprint-search-wire.yaml

---

## 1. QA Root Cause Analysis
During BACK QA verification of `T-HUB-100-context-fingerprint-search-wire`, QA flagged an `ac_gap` blocker:
- `is_context_policy_active` in `harness/hooks/context_ledger.py` was looking for context ledger files at `project_root / ".runtime" / "context_ledger"` (with an underscore and non-recursive `*.json`), whereas `ContextLedger.ledger_path` writes to `base_dir / "context-ledger" / safe_proj / safe_sess / f"{safe_inv}.json"` (with a hyphen and nested directories).
- When `EPIC_LOOP` was not explicitly set and `activeContext.md` was missing, `is_context_policy_active` returned `False`, failing to detect active context ledgers and causing the search scope gate in `harness/hooks/pretool_policy.py:475` to be bypassed.

**Root Cause:**
Path convention discrepancy between `ContextLedger.ledger_path` (`context-ledger/`) and `is_context_policy_active` (`context_ledger/`), plus lack of recursive search across canonical runtime base directories (`runtime_epic_dir.parent / context-ledger`, `.runtime/context-ledger`).

---

## 2. Changes Implemented (AC+)
- `harness/hooks/context_ledger.py`: Updated `is_context_policy_active` to resolve canonical `context-ledger` paths from `runtime_dir`, context payload `runtime_dir`, `runtime_epic_dir(project_root).parent / "context-ledger"`, and `.runtime/context-ledger`, recursively checking for active `.json` ledger files.
- `harness/hooks/tests/test_context_scope_policy.py`: Added test assertion ensuring `is_context_policy_active` returns `True` when `activeContext.md` is absent but an active context ledger is present in `.runtime/context-ledger/`.
- `memory-bank/back/bugfix/T-HUB-100-context-fingerprint-search-wire/bugfix-queue.yaml`: Updated item `BF-001` to `done` with targeted test evidence; full suite verification executed and marked `pass` (2945 passed, 4 skipped in 105.39s).
- `is_context_policy_active` now uses direct path resolution, stat, and glob checks; broad exception handlers were removed so path-resolution failures are not silently ignored.

---

## 3. Non-Goals / Fallback Purge (AC−)
- No loose fallback masks or exception silencing introduced.
- Strict search allowlist enforcement outside EPIC_LOOP preserved.
- No changes outside `context_ledger.py`, tests, and bugfix queue/report.

---

## 4. Integration Rule Counterparts (§0.11)
- **API / Protocol:** `is_context_policy_active` signature and return contract maintained.
- **Environment variables:** `EPIC_LOOP` environment detection maintained.
- **Storage & State:** `bugfix-queue.yaml` and `bugfix-20260915-context-fingerprint-search-wire.md` recorded.
- **Orphan check:** Zero dangling references or orphan paths introduced.

---

## 5. Blockers Resolved
- `BF-001`: `active ContextLedger not found due to path mismatch in harness/hooks/context_ledger.py; non-EPIC_LOOP search gate bypassed in harness/hooks/pretool_policy.py:475` — PASS

---

## 6. Verification
- Targeted checks:
  ```bash
  bin/pytest harness/hooks/tests/test_context_ledger.py harness/hooks/tests/test_context_scope_policy.py harness/hooks/tests/test_context_ledger_adapters.py harness/hooks/tests/test_pretool_dispatch.py -q --tb=line
  ```
  Result: 41 passed in 2.24s.
- Full repository test suite (`verification.command`):
  ```bash
  bin/pytest -q --tb=line
  ```
  Result: 2945 passed, 4 skipped in 105.39s.


---

## 7. QA Round 2 Blocker (BF-002) Resolution
**Blocker:** , ,  always allowed outside allowlist in , violating AC−2 and AC−6.

**Root Cause:**
 in  contained hardcoded unconditional bypass for paths starting with , , or . This permitted arbitrary reads and searches inside these directories even when they were not part of the active shard allowlist or backed by graphify exceptions.

**Fix Implemented:**
- : Removed hardcoded prefix checks (, etc.) from .
- : Added test  verifying that , , and  are rejected unless explicitly allowed or permitted via graphify exception.
- : Item  marked , verification status marked  (2946 passed, 4 skipped in 106.33s).


---

## 7. QA Round 2 Blocker (BF-002) Resolution
**Blocker:** `.agents/`, `.claude/`, `.cursor/` always allowed outside allowlist in `harness/hooks/context_scope.py:301-316`, violating AC−2 and AC−6.

**Root Cause:**
`ScopeResolver.is_path_allowed` in `harness/hooks/context_scope.py` contained hardcoded unconditional bypass for paths starting with `.cursor/`, `.claude/`, or `.agents/`. This permitted arbitrary reads and searches inside these directories even when they were not part of the active shard allowlist or backed by graphify exceptions.

**Fix Implemented:**
- `harness/hooks/context_scope.py`: Removed hardcoded prefix checks (`norm.startswith('.cursor/')`, etc.) from `is_path_allowed`.
- `harness/hooks/tests/test_context_scope_policy.py`: Added test `test_dot_directories_not_bypassed_without_allowlist` verifying that `.cursor/`, `.claude/`, and `.agents/` are rejected unless explicitly allowed or permitted via graphify exception.
- `memory-bank/back/bugfix/T-HUB-100-context-fingerprint-search-wire/bugfix-queue.yaml`: Item `BF-002` marked `done`, verification status marked `pass` (2946 passed, 4 skipped in 106.33s).


---

## 8. QA Round 3 Blocker (BF-003) Resolution
**Blocker:** compound Bash commands bypass search enforcement (`cd .agents && rg ...`, `env rg ...`, `bash -c ...`) in `harness/hooks/context_scope.py:97`, `harness/hooks/pretool_policy.py:475`.

**Root Cause:**
`is_search_command_line` and `ScopeResolver.evaluate_search` only parsed simple token lists via `shlex.split()` without decomposing compound commands (such as shell chaining `&&`, `||`, `;`, pipes `|`, wrapper utilities `env`, `nohup`, `time`, `exec`, or subshell invocations `bash -c "..."`). As a result:
1. Chained search commands (e.g. `cd .agents && rg foo`) had `cd` as the leading binary, bypassing `is_search_command_line` detection completely.
2. Wrapper commands (e.g. `env rg foo`) evaluated `env` instead of `rg`.
3. Working directory changes via `cd` were not tracked, leading to incorrect target path resolution relative to project root.

**Fix Implemented:**
- `harness/hooks/context_scope.py`:
  - Implemented `_extract_search_invocations` with shlex tokenization, operator splitting (`&&`, `||`, `;`, `|`, `&`, subshells), wrapper unwrapping (`env`, `nohup`, `nice`, `time`, `exec`, `sudo`, `xargs`), and nested shell command unwrapping (`bash -c`, `sh -c`).
  - Implemented working directory tracking across `cd`/`pushd` steps so search targets are resolved against their effective relative path.
  - Implemented `_extract_targets_from_tokens` handling arguments for `rg`, `grep`, `find`, `cat`, `sed`, `awk`, `git grep`/`log`, and python readers, accounting for piped input.
  - Updated `ScopeResolver.evaluate_search` to fail-closed if compound commands cannot be safely parsed, and evaluate every extracted search invocation and target against the active shard allowlist.
- `harness/hooks/tests/test_context_scope_policy.py`:
  - Added `test_compound_bash_commands_search_enforcement` covering chained commands, wrapper commands, subshell invocations, pipes, and env vars.
  - Added `test_bash_pretool_compound_search_denied_and_allowed` verifying end-to-end `BashPolicyAdapter` pretool enforcement for compound search commands.
- `memory-bank/back/bugfix/T-HUB-100-context-fingerprint-search-wire/bugfix-queue.yaml`: Item `BF-003` marked `done`, verification status marked `pass` (2948 passed, 4 skipped in 131.62s).
