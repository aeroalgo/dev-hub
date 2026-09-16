# Services and Data Flow — Multi-Runtime Architecture

**Last updated:** 2026-09-16  
**Scope:** Architectural overview of service interaction and data flow for Claude Code and Codex runtime engines.

## Overview

This document unifies the service architecture (`services.md`) and data flow (`data-flow.md`) specs for dev-hub.

## Service Interaction Map

```mermaid
graph TD
    User[User / CLI] -->|loop/loop.sh| LoopSh[Loop Launcher]
    LoopSh -->|EPIC_RUNTIME=claude| CC[Claude Code CLI]
    LoopSh -->|EPIC_RUNTIME=codex| Codex[Codex CLI]
    
    CC -->|subagent/start| CC_Hooks[.claude/hooks/ subagent-start.py]
    CC_Hooks -->|verify / reviewer| Gates[Hook Gates & Hand-off]
    Gates -->|Session State| SessLog[memory-bank/activeContext.md & task logs]
```

## Data Flow Summary

1. **Launcher Dispatch:** `loop/loop.sh` evaluates `EPIC_RUNTIME`. It launches either Claude Code CLI or Codex CLI.
2. **Hook Ingestion:** Lifecycle events are processed via `.claude/hooks/` and `.codex/hooks.json`.
3. **Verdict & State Mirroring:** Session state and verdicts write back to `memory-bank/activeContext.md` and task logs.

## Detailed References

- [`services.md`](services.md) — Main service interaction topology.
- [`data-flow.md`](data-flow.md) — Core data flow pipeline details.
