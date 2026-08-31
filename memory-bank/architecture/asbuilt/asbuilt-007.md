# As-Built Architecture — T-HUB-007

**Epic ID:** T-HUB-007  
**Title:** DSH Profiles & Installer  
**Date:** 2026-08-30  

## Overview

T-HUB-007 introduced DSH profiles and automated profile installation scripts for dev-hub.

## Key Components

1. **Profiles (`dsh/profiles/`):**
   - Built-in profile definitions (`epic-implement`, `epic-qa`, `epic-plan`, etc.).
   - Model definitions and presets (`dsh-phase-models`).

2. **Installer Script (`dsh/scripts/install-profiles.sh`):**
   - Installs local profiles and preset bundles into `$DSH_HOME/profiles/`.
   - Utility scripts: `sync-agent-md-to-presets.py` for syncing agent instructions.
