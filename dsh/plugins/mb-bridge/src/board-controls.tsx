import { useEffect, useMemo, useState } from 'react';

import {
  BridgeConfig,
  BridgeRuntime,
  HostExecutionResult,
  ModelPreset,
  spawnHubBoard,
} from './python-bridge';
import { filterCards } from './board-filter';

export const WORKSPACE_FILTER_KEY = 'mb-bridge.workspaceFilter';
export const RUNTIME_KEY = 'mb-bridge.runtime';
export const MODEL_PRESET_KEY = 'mb-bridge.modelPreset';

export interface BoardControlCard {
  metadata?: Record<string, unknown>;
}

export interface WorkspaceOption {
  id: string;
  label?: string;
}

export interface BoardControlsProps<T extends BoardControlCard = BoardControlCard> {
  cards?: readonly T[];
  workspaces?: readonly WorkspaceOption[];
  config: BridgeConfig;
  taskId?: string;
  modelSource?: string;
  onCardsChange?: (cards: T[]) => void;
  onResult?: (result: HostExecutionResult) => void;
  onToast?: (message: string) => void;
}

const ALL_WORKSPACES = '';
const DEFAULT_RUNTIME: BridgeRuntime = 'claude';

function readStorage(key: string, fallback: string): string {
  if (typeof localStorage === 'undefined') return fallback;
  return localStorage.getItem(key) ?? fallback;
}

function saveStorage(key: string, value: string): void {
  if (typeof localStorage !== 'undefined') localStorage.setItem(key, value);
}

function safeRuntime(value: string, fallback: BridgeRuntime): BridgeRuntime {
  return value === 'dsh' || value === 'claude' ? value : fallback;
}

function safePreset(value: string, presets: readonly ModelPreset[]): string {
  return value === '' || presets.some((preset) => preset.id === value) ? value : '';
}

function syncSummary(result: HostExecutionResult): string {
  const summary = result.stdout.match(/(?:upsert|archive|noop)=\d+/g);
  return summary?.join(' ') ?? (result.status === 'succeeded' ? 'sync complete' : 'sync failed');
}

export function BoardControls<T extends BoardControlCard = BoardControlCard>({
  cards = [],
  workspaces = [],
  config,
  taskId,
  modelSource,
  onCardsChange,
  onResult,
  onToast,
}: BoardControlsProps<T>): JSX.Element {
  const presets = useMemo(
    () => (config.modelPresets ?? []).slice(0, 8),
    [config.modelPresets],
  );
  const [workspaceFilter, setWorkspaceFilter] = useState(() =>
    readStorage(WORKSPACE_FILTER_KEY, ALL_WORKSPACES),
  );
  const [runtime, setRuntime] = useState<BridgeRuntime>(() =>
    safeRuntime(readStorage(RUNTIME_KEY, config.defaultRuntime ?? DEFAULT_RUNTIME), config.defaultRuntime ?? DEFAULT_RUNTIME),
  );
  const [modelPreset, setModelPreset] = useState(() =>
    safePreset(readStorage(MODEL_PRESET_KEY, ''), presets),
  );
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    onCardsChange?.(filterCards(cards, workspaceFilter || null));
  }, [cards, onCardsChange, workspaceFilter]);

  const changeWorkspace = (value: string) => {
    setWorkspaceFilter(value);
    saveStorage(WORKSPACE_FILTER_KEY, value);
  };

  const changeRuntime = (value: string) => {
    const next = safeRuntime(value, config.defaultRuntime ?? DEFAULT_RUNTIME);
    setRuntime(next);
    saveStorage(RUNTIME_KEY, next);
  };

  const changePreset = (value: string) => {
    const next = safePreset(value, presets);
    setModelPreset(next);
    saveStorage(MODEL_PRESET_KEY, next);
  };

  const sync = () => {
    setSyncing(true);
    // The bridge maps workspaceId to the hub-board --workspace-id argv token.
    const workspace_id = workspaceFilter || null;
    void spawnHubBoard('sync', taskId ?? 'board', {
      workspaceId: workspace_id,
    }, config).then((result) => {
      setSyncing(false);
      onResult?.(result);
      onToast?.(syncSummary(result));
    }, (error: unknown) => {
      setSyncing(false);
      onToast?.(error instanceof Error ? error.message : 'sync failed');
    });
  };

  return (
    <div data-mb-bridge-controls="true">
      <label>
        Workspace
        <select value={workspaceFilter} onChange={(event) => changeWorkspace(event.target.value)}>
          <option value={ALL_WORKSPACES}>All</option>
          {workspaces.map((workspace) => (
            <option key={workspace.id} value={workspace.id}>{workspace.label ?? workspace.id}</option>
          ))}
        </select>
      </label>
      <label>
        Runtime
        <select value={runtime} onChange={(event) => changeRuntime(event.target.value)}>
          <option value="claude">claude</option>
          <option value="dsh">dsh</option>
        </select>
      </label>
      <label>
        Model
        <select value={modelPreset} onChange={(event) => changePreset(event.target.value)}>
          <option value="">Phase default (env)</option>
          {presets.map((preset) => (
            <option key={preset.id} value={preset.id}>{preset.label}</option>
          ))}
        </select>
      </label>
      {modelSource === 'env' && <span data-model-badge="env overrides">env overrides</span>}
      <button type="button" disabled={syncing} onClick={sync}>Sync</button>
    </div>
  );
}
