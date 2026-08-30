import { spawn } from 'node:child_process';
import os from 'node:os';
import path from 'node:path';

export type BoardAction = 'arm' | 'loop' | 'arm-loop' | 'sync';
export type BridgeRuntime = 'claude' | 'dsh';

export interface BridgeFlags {
  loopArgs?: string;
  modelPreset?: string;
  runtime?: BridgeRuntime;
  workspaceId?: string | null;
}

const SAFE_TOKEN = /^[A-Za-z0-9._/-]+$/;
const MAX_LOG_BYTES = 100_000;

function validateToken(value: string, name: string): void {
  if (!SAFE_TOKEN.test(value)) throw new Error(`${name} contains an unsafe token`);
}

function validatePreset(config: BridgeConfig, presetId: string): void {
  const preset = config.modelPresets?.find((entry) => entry.id === presetId);
  if (!preset) throw new Error(`unknown model preset: ${presetId}`);
  validateToken(preset.id, 'model preset');
  preset.args.forEach((token) => validateToken(token, 'model preset'));
}

function appendWorkspaceArg(argv: string[], workspaceId: string | null | undefined): void {
  if (workspaceId) {
    validateToken(workspaceId, 'workspaceId');
    argv.push('--workspace-id', workspaceId);
  }
}

export interface ModelPreset {
  id: string;
  label: string;
  args: string[];
}

export interface BridgeConfig {
  enabled?: boolean;
  devHub?: string;
  loopBin?: string;
  hostUrl?: string;
  syncAfterLoop?: boolean;
  allowRoadmapAdvance?: boolean;
  defaultRuntime?: BridgeRuntime;
  defaultLoopArgs?: string[];
  workspaceFilterEnabled?: boolean;
  modelPresets?: ModelPreset[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function validateBridgeConfig(section: Record<string, unknown>): BridgeConfig {
  if (section.enabled !== undefined && typeof section.enabled !== 'boolean') {
    throw new Error('mb-bridge.enabled must be a boolean');
  }
  if (section.allowRoadmapAdvance !== undefined && typeof section.allowRoadmapAdvance !== 'boolean') {
    throw new Error('mb-bridge.allowRoadmapAdvance must be a boolean');
  }
  if (section.syncAfterLoop !== undefined && typeof section.syncAfterLoop !== 'boolean') {
    throw new Error('mb-bridge.syncAfterLoop must be a boolean');
  }
  if (section.devHub !== undefined && typeof section.devHub !== 'string') {
    throw new Error('mb-bridge.devHub must be a string');
  }
  if (section.loopBin !== undefined && typeof section.loopBin !== 'string') {
    throw new Error('mb-bridge.loopBin must be a string');
  }
  if (section.defaultRuntime !== undefined && section.defaultRuntime !== 'claude' && section.defaultRuntime !== 'dsh') {
    throw new Error('mb-bridge.defaultRuntime must be claude or dsh');
  }
  if (section.defaultLoopArgs !== undefined && (
    !Array.isArray(section.defaultLoopArgs)
    || !section.defaultLoopArgs.every((token) => typeof token === 'string' && SAFE_TOKEN.test(token))
  )) {
    throw new Error('mb-bridge.defaultLoopArgs must contain safe strings');
  }
  if (section.modelPresets !== undefined && (
    !Array.isArray(section.modelPresets)
    || !section.modelPresets.every((preset) => (
      isRecord(preset)
      && typeof preset.id === 'string'
      && typeof preset.label === 'string'
      && Array.isArray(preset.args)
      && preset.args.every((token) => typeof token === 'string' && SAFE_TOKEN.test(token))
    ))
  )) {
    throw new Error('mb-bridge.modelPresets must contain valid presets');
  }
  return section as BridgeConfig;
}

export type ModelSource = 'env' | 'preset' | 'default' | 'bare' | 'arm';

export interface HostExecutionResult {
  status: 'succeeded' | 'failed';
  exitCode: number | null;
  stdout: string;
  stderr: string;
  log: string;
  modelSource?: ModelSource;
  modelEnv?: string;
}

function parseModelSource(output: string): Pick<HostExecutionResult, 'modelSource' | 'modelEnv'> {
  const source = output.match(/(?:^|\n)model_source=([a-z]+)(?:\n|$)/)?.[1];
  const env = output.match(/(?:^|\n)model_env=([A-Z0-9_]+)(?:\n|$)/)?.[1];
  if (source !== 'env' && source !== 'preset' && source !== 'default' && source !== 'bare' && source !== 'arm') {
    return {};
  }
  return { modelSource: source, ...(env ? { modelEnv: env } : {}) };
}

function withModelSource(result: HostExecutionResult): HostExecutionResult {
  return { ...result, ...parseModelSource(`${result.stdout}\n${result.stderr}`) };
}

export function parseHostExecutionResult(result: HostExecutionResult): HostExecutionResult {
  return withModelSource(result);
}

const ACTIONS = new Set<BoardAction>(['arm', 'loop', 'arm-loop', 'sync']);

export function buildHubBoardArgv(
  action: BoardAction,
  taskId: string,
  flags: BridgeFlags = {},
  config: BridgeConfig = {},
): string[] {
  if (!ACTIONS.has(action)) throw new Error(`unsupported board action: ${action}`);
  if (action !== 'sync') validateToken(taskId, 'taskId');

  const argv = action === 'sync' ? [action] : [action, '--task-id', taskId];
  if (flags.modelPreset !== undefined && action === 'sync') {
    throw new Error('model preset is only valid for loop actions');
  }
  if (flags.loopArgs !== undefined) {
    validateToken(flags.loopArgs, 'loopArgs');
    argv.push('--loop-args', flags.loopArgs);
  }
  if (flags.modelPreset !== undefined) {
    validatePreset(config, flags.modelPreset);
    argv.push('--loop-args', flags.modelPreset);
  }
  appendWorkspaceArg(argv, flags.workspaceId);
  if (flags.runtime !== undefined) {
    if (flags.runtime !== 'claude' && flags.runtime !== 'dsh') {
      throw new Error('runtime must be claude or dsh');
    }
    argv.push('--runtime', flags.runtime);
  }
  return argv;
}

function resolveLoopBin(config: BridgeConfig): string {
  const loopBin = config.loopBin ?? 'bin/hub-board';
  if (path.isAbsolute(loopBin)) return loopBin;
  const hub = config.devHub;
  if (hub === undefined || hub.trim() === '') {
    throw new Error('mb-bridge.devHub is required to resolve loopBin');
  }
  return path.join(hub, loopBin);
}

function applyHostEnv(env: NodeJS.ProcessEnv, config: BridgeConfig): void {
  if (config.devHub) env.DEV_HUB = config.devHub;
  if (!env.DSH_HOME) env.DSH_HOME = process.env.DSH_HOME ?? path.join(os.homedir(), '.dsh');
  const hostUrl = config.hostUrl ?? process.env.DSH_TASK_BOARD_HOST_URL ?? process.env.DSH_WEB_URL;
  if (hostUrl !== undefined && hostUrl !== '') {
    env.DSH_TASK_BOARD_HOST_URL = hostUrl;
  }
}

export function spawnHubBoard(
  action: BoardAction,
  taskId: string,
  flags: BridgeFlags = {},
  config: BridgeConfig = {},
): Promise<HostExecutionResult> {
  const argv = buildHubBoardArgv(action, taskId, flags, config);
  const command = resolveLoopBin(config);
  const cwd = config.devHub;
  const env = { ...process.env };
  applyHostEnv(env, config);
  const runtime = flags.runtime ?? config.defaultRuntime;
  if (runtime === 'dsh') env.EPIC_RUNTIME = 'dsh';

  return new Promise((resolve, reject) => {
    const child = spawn(command, argv, {
      cwd,
      env,
      shell: false,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    let stdout = '';
    let stderr = '';
    child.stdout?.on('data', (chunk: Buffer | string) => {
      stdout = appendBounded(stdout, String(chunk));
    });
    child.stderr?.on('data', (chunk: Buffer | string) => {
      stderr = appendBounded(stderr, String(chunk));
    });
    child.once('error', reject);
    child.once('close', (exitCode) => {
      const log = appendBounded(`${stdout}${stderr}`, '');
      resolve(parseHostExecutionResult({
        status: exitCode === 0 ? 'succeeded' : 'failed',
        exitCode,
        stdout,
        stderr,
        log,
      }));
    });
  });
}

function appendBounded(current: string, next: string): string {
  const value = current + next;
  const bytes = Buffer.byteLength(value, 'utf8');
  if (bytes <= MAX_LOG_BYTES) return value;
  return Buffer.from(value, 'utf8').subarray(-MAX_LOG_BYTES).toString('utf8');
}
