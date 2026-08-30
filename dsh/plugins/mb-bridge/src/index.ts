import type { Context } from '@deepseek-ai/cordis';
import type {} from '@deepseek-ai/dsh-host-webserver';

import { makeMbBridgeRoute, makeMbBridgeWorkspacesRoute } from './host-routes.ts';
import {
  createStockRunAdapter,
  STOCK_RUN_SLOT,
} from './intercept-run.ts';
import { validateBridgeConfig } from './python-bridge.ts';
import {
  createWorkspaceListAdapter,
  type WorkspaceListHost,
} from './workspace-list.ts';

interface BridgeContext extends Context, WorkspaceListHost {
  inject?: (slot: string, value: unknown) => void;
}

export const inject = ['webServer'];

export function loadBridgeConfig(raw: Record<string, unknown> = {}): Record<string, unknown> {
  const section = raw['mb-bridge'] ?? raw;
  if (section === undefined) return {};
  if (typeof section !== 'object' || section === null || Array.isArray(section)) {
    throw new Error('mb-bridge config must be a mapping');
  }
  return validateBridgeConfig(section as Record<string, unknown>);
}

export function apply(ctx: Context, rawConfig?: Record<string, unknown>): void {
  const config = loadBridgeConfig(rawConfig ?? {});
  if (config.enabled === false) return;
  const bridgeContext = ctx as BridgeContext;
  ctx.webServer.register(makeMbBridgeRoute(config));
  ctx.webServer.register(makeMbBridgeWorkspacesRoute());
  ctx.inject?.(STOCK_RUN_SLOT, createStockRunAdapter(config));
  ctx.inject?.('workspace.list', createWorkspaceListAdapter(bridgeContext));
}

export default { inject, apply };
