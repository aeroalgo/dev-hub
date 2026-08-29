# `@dev-hub/dsh-mb-bridge`

Cordis Path B bridge for `mb-*` memory-bank cards.

## Behavior

- `POST /api/mb-bridge/action` is the Host route for `arm`, `loop`, and `arm-loop`.
- `mb-*` cards never fall through to the stock free-session runner; the explicit error is `mb_card_requires_loop_run`.
- Non-`mb-*` cards retain the stock run handler.
- Card detail exposes `Arm`, `Run loop`, and primary `Arm+Run` actions.

## Configuration

```yaml
mb-bridge:
  enabled: true
  devHub: /path/to/dev-hub
  loopBin: hub-board
  syncAfterLoop: true
  allowRoadmapAdvance: false
  interceptMbStockRun: true
  defaultRuntime: claude
  defaultLoopArgs: []
  workspaceFilterEnabled: true
  modelPresets: []
```

The bridge passes a fixed argument vector to `hub-board`; it never invokes a shell and never accepts a browser-supplied binary or prompt. `taskId`, action, loop arguments, and runtime are validated before spawning.
