# As-Built Architecture — T-HUB-006

**Epic ID:** T-HUB-006  
**Title:** Loop Launcher Dual-Runtime Support (`EPIC_RUNTIME=dsh`)  
**Date:** 2026-08-30  

## Overview

T-HUB-006 implemented dual-runtime execution support in the `loop/loop.sh` launcher script and Python hooks (`.claude/hooks/_lib.py`).

## Key Components

1. **Loop Launcher (`loop/loop.sh`):**
   - Added support for `EPIC_RUNTIME` environment variable (`claude` default, `dsh` opt-in).
   - When `EPIC_RUNTIME=dsh`, delegates session execution to `dsh --profile <profile>`.

2. **Runtime Configuration (`.claude/hooks/_lib.py`):**
   - Implemented `RuntimeConfig` for runtime detection and environment validation.
   - Preserves compatibility with existing Claude Code session lifecycles.
