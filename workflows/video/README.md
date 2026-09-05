# Video Production Workflow Pack (`workflows/video/`)

Operator documentation and reference guide for the `video-production` workflow pack in `dev-hub`.

## Activation

The video production pack can be activated in two ways:

### 1. Environment Variable
Set `WORKFLOW_PACK` before running loop or dev-hub commands:
```bash
export WORKFLOW_PACK=video-production
```

### 2. Project Configuration (`project.yaml`)
Specify `workflow_pack` in `project.yaml` at project root:
```yaml
workflow_pack: video-production
```

When activated, `dev-hub` uses the roles `[script, visual, post]`, command prefixes `[SCRIPT, VISUAL, POST]`, and phase registry `workflows/video/phase_registry.yaml`.

---

## Phases Overview

The video workflow defines a 6-phase pipeline:

```
BRIEF ──► SCRIPT ──► STORYBOARD ──► SHOOT ──► EDIT ──► PUBLISH
```

| Phase | Mode | Verify Agent | External Gates | Description |
|---|---|---|---|---|
| `BRIEF` | `pre_implement` | — | — | Creative brief, goals, constraints |
| `SCRIPT` | `pre_implement` | `verify-script` | — | Script writing and scene breakdown |
| `STORYBOARD` | `pre_implement` | — | — | Storyboarding and visual planning |
| `SHOOT` | `implement` | — | — | Footage gathering / asset preparation |
| `EDIT` | `implement` | `verify-edit` | `render` (`RenderCheckAdapter`) | Video assembly, audio, effects, render |
| `PUBLISH` | `implement` | `verify-publish` | — | Final export, distribution, metadata |

---

## External Gates

### EDIT Phase: `render_check`
The `EDIT` phase enforces an external tool gate `render` configured in `manifest.yaml`:
- **Adapter**: `workflows/video/tools/render_check.py` (`RenderCheckAdapter`)
- **Expected artifact path**: `outputs/final.mp4`
- **Checks performed**:
  1. Verifies that `outputs/final.mp4` exists and is a regular file (`render_output_missing`).
  2. Probes video duration via `ffprobe` (or checks file size > 0 bytes as fallback if `ffprobe` is not installed), ensuring duration/size is greater than 0 (`render_duration_zero`).

---

## Verify Agents

The video pack provides dedicated verification agent contracts in `harness/agents/`:
- **`verify-script`**: Read-only verification for `SCRIPT` phase artifacts, scene checklist, and outline structure.
- **`verify-edit`**: Read-only verification for `EDIT` phase artifacts, checking render output presence and duration.
- **`verify-publish`**: Read-only verification for `PUBLISH` phase, validating distribution artifacts or target URL destinations.

---

## Cursor Rules

Rules skeleton is located under `.cursor/rules/video/`:
- `mainrule.mdc`: Entrypoint rule for video pack commands and roles (`SCRIPT`, `VISUAL`, `POST`).
- `workflow-plan.mdc`, `workflow-implement.mdc`, `workflow-qa.mdc`: Workflow step rules.
- `_lean/`: Minimal lean subrules for role isolation.

*Note*: Symlinking / installing pack rules via `hub-link` into user environments is tracked under Deferred task T-HUB-052.
