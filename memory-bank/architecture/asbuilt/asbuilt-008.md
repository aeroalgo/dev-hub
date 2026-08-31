# As-Built Architecture — T-HUB-008

**Epic ID:** T-HUB-008  
**Title:** DSH Bridge & Plugins Integration  
**Date:** 2026-08-30  

## Overview

T-HUB-008 implemented the DSH-to-Claude bridge plugin (`mb-bridge`) and Cordis plugin integration.

## Key Components

1. **MB-Bridge Plugin (`dsh/plugins/mb-bridge/`):**
   - Forwards DSH subagent start lifecycle hooks to `.claude/hooks/subagent-start.py`.
   - Normalizes project root directory resolution via `EPIC_PROJECT_ROOT` and `CLAUDE_PROJECT_DIR`.

2. **Verdict Mirror & Gates:**
   - Connects DSH execution verdicts to memory-bank state updates.
