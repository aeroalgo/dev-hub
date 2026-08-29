import { spawn } from 'node:child_process';

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
  devHub?: string;
  loopBin?: string;
  syncAfterLoop?: boolean;
  defaultRuntime?: BridgeRuntime;
  defaultLoopArgs?: string[];
  workspaceFilterEnabled?: boolean;
  modelPresets?: ModelPreset[];
}

export interface HostExecutionResult {
  status: 'succeeded' | 'failed';
  exitCode: number | null;
  stdout: string;
  stderr: string;
  log: string;
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

export function spawnHubBoard(
  action: BoardAction,
  taskId: string,
  flags: BridgeFlags = {},
  config: BridgeConfig = {},
): Promise<HostExecutionResult> {
  const argv = buildHubBoardArgv(action, taskId, flags, config);
  const command = config.loopBin ?? 'hub-board';
  const cwd = config.devHub;
  const env = { ...process.env };
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
      resolve({
        status: exitCode === 0 ? 'succeeded' : 'failed',
        exitCode,
        stdout,
        stderr,
        log,
      });
    });
  });
}

function appendBounded(current: string, next: string): string {
  const value = current + next;
  const bytes = Buffer.byteLength(value, 'utf8');
  if (bytes <= MAX_LOG_BYTES) return value;
  return Buffer.from(value, 'utf8').subarray(-MAX_LOG_BYTES).toString('utf8');
}
