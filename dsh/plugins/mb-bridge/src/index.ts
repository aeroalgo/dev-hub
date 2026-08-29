import { BridgeConfig } from './python-bridge';
import { registerBridgeRoute } from './intercept-run';

export interface CordisContext {
  host?: {
    post: (path: string, handler: (request: unknown) => unknown) => void;
  };
  config?: Record<string, unknown>;
  inject?: (slot: string, component: unknown) => void;
}

export function loadBridgeConfig(raw: Record<string, unknown> = {}): BridgeConfig {
  const section = raw['mb-bridge'];
  if (!section || typeof section !== 'object') return {};
  return section as BridgeConfig;
}

export function apply(ctx: CordisContext): void {
  const config = loadBridgeConfig(ctx.config);
  if (ctx.host) registerBridgeRoute(ctx.host, config);
  ctx.inject?.('task-board.header', 'mb-bridge/board-controls');
  ctx.inject?.('task-board.card-detail.actions', 'mb-bridge/card-actions');
  ctx.inject?.('task-board.stock-run-prompt', 'mb-bridge/deny-stock-run');
}

export default apply;
