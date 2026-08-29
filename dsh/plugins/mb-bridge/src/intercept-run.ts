import {
  BoardAction,
  BridgeConfig,
  HostExecutionResult,
  spawnHubBoard,
} from './python-bridge';

// s01 decision: PATH_B (Host-route fallback), not a Cordis stock-run hook.
export const INTERCEPT_PATH = 'PATH_B' as const;
export const MB_STOCK_RUN_ERROR = 'mb_card_requires_loop_run';
export const MB_BRIDGE_ROUTE = '/api/mb-bridge/action';

export interface BoardCard {
  id: string;
  metadata?: Record<string, unknown>;
}

export interface BridgeActionRequest {
  action: BoardAction;
  taskId: string;
  loopArgs?: string;
  runtime?: 'claude' | 'dsh';
}

export type StockRunHandler = (card: BoardCard) => Promise<HostExecutionResult>;
export type StockRunAdapter = (
  card: BoardCard,
  stockRun: StockRunHandler,
) => Promise<HostExecutionResult>;

export const STOCK_RUN_SLOT = 'task-board.stock-run';

export function isMbCard(card: BoardCard): boolean {
  return card.id.startsWith('mb-');
}

export function createStockRunAdapter(config: BridgeConfig): StockRunAdapter {
  const bridge = createBridgeAction(config);
  return (card, stockRun) => interceptStockRun(card, bridge, stockRun);
}

export function interceptStockRun(
export function isMbCard(card: BoardCard): boolean {
  return card.id.startsWith('mb-');
}

export function interceptStockRun(
  card: BoardCard,
  bridge: (request: BridgeActionRequest) => Promise<HostExecutionResult>,
  stockRun?: (card: BoardCard) => Promise<HostExecutionResult>,
): Promise<HostExecutionResult> {
  if (!isMbCard(card)) {
    if (!stockRun) throw new Error('stock run handler is required for non-mb cards');
    return stockRun(card);
  }
  return bridge({ action: 'arm-loop', taskId: card.id });
}

export function denyStockRun(card: BoardCard): never {
  if (isMbCard(card)) throw new Error(MB_STOCK_RUN_ERROR);
  throw new Error('denyStockRun is only valid for mb-* cards');
}

export function createBridgeAction(
  config: BridgeConfig,
): (request: BridgeActionRequest) => Promise<HostExecutionResult> {
  return (request) => spawnHubBoard(request.action, request.taskId, request, config);
}

export function registerBridgeRoute(
  host: { post: (path: string, handler: (request: BridgeActionRequest) => unknown) => void },
  config: BridgeConfig,
): void {
  host.post(MB_BRIDGE_ROUTE, createBridgeAction(config));
}
