import { spawn } from 'node:child_process';
import type { Context } from '@deepseek-ai/cordis';
import type {
  PreToolDecision,
  ToolExecution,
} from '@deepseek-ai/dsh-tools';
import { resolveProjectRoot } from './subagent-start.ts';

type JsonObject = Record<string, unknown>;
type SpawnValidation = {
  deny_reasons?: unknown;
  notes?: unknown;
};

type SpawnValidator = (
  payload: JsonObject,
  cwd: string,
) => Promise<SpawnValidation>;

export interface EpicGateConfig {
  python?: string;
  validator?: string;
}

const TOOL_NAMES = new Set(['Agent', 'Task']);

function asObject(value: unknown): JsonObject {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as JsonObject
    : {};
}

function validatorConfig(config: EpicGateConfig): Required<EpicGateConfig> {
  return {
    python: config.python ?? process.env.PYTHON ?? 'python3',
    validator: config.validator ?? process.env.DSH_SPAWN_VALIDATE ?? '.claude/hooks/spawn_validate.py',
  };
}

function resolveValidatorPath(validator: string, cwd: string): string {
  return validator.startsWith('/') ? validator : `${cwd}/${validator}`;
}

function spawnValidate(
  payload: JsonObject,
  cwd: string,
  config: EpicGateConfig = {},
): Promise<SpawnValidation> {
  const { python, validator } = validatorConfig(config);
  const validatorPath = resolveValidatorPath(validator, cwd);

  return new Promise((resolve, reject) => {
    const child = spawn(python, [validatorPath], {
      cwd,
      env: { ...process.env, PYTHONPATH: `${cwd}/.claude/hooks` },
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (chunk: Buffer | string) => { stdout += String(chunk); });
    child.stderr.on('data', (chunk: Buffer | string) => { stderr += String(chunk); });
    child.once('error', reject);
    child.once('close', (code) => {
      if (code !== 0) {
        reject(new Error(`spawn_validate exited ${code ?? 'unknown'}: ${stderr.trim()}`));
        return;
      }
      try {
        resolve(asObject(JSON.parse(stdout)) as SpawnValidation);
      } catch (error) {
        reject(new Error(`spawn_validate returned invalid JSON: ${String(error)}`));
      }
    });
    child.stdin.end(JSON.stringify(payload));
  });
}

function validationPayload(exec: ToolExecution): JsonObject {
  const input = asObject(exec.arguments);
  const session = exec.agent?.session;
  const root = resolveProjectRoot();
  return {
    tool_name: exec.name,
    tool_input: {
      ...input,
      subagent_type: input.subagent_type ?? input.agent_type,
    },
    session_id: session?.header.id ?? '',
    cwd: root ?? session?.header.cwd ?? process.cwd(),
  };
}

function denyReason(reasons: unknown): string {
  const values = Array.isArray(reasons)
    ? reasons.filter((reason): reason is string => typeof reason === 'string')
    : [];
  return values.length > 0
    ? `epic_gate: ${values.join(' | ')}`
    : 'epic_gate: spawn_validate denied the spawn';
}

export async function preToolUse(
  exec: ToolExecution,
  validate: SpawnValidator = (payload, cwd) => spawnValidate(payload, cwd),
): Promise<PreToolDecision> {
  if (!TOOL_NAMES.has(exec.name)) return { kind: 'allow' };
  const root = resolveProjectRoot();
  const cwd = root ?? exec.agent?.session.header.cwd ?? process.cwd();
  try {
    const result = await validate(validationPayload(exec), cwd);
    const denyReasons = Array.isArray(result.deny_reasons) ? result.deny_reasons : [];
    return denyReasons.length > 0
      ? { kind: 'deny', reason: denyReason(denyReasons) }
      : { kind: 'allow' };
  } catch (error) {
    return {
      kind: 'deny',
      reason: `epic_gate: spawn_validate unavailable (${String(error)}); fail-closed`,
    };
  }
}

export const inject = ['tools'];

export function apply(ctx: Context, config: EpicGateConfig = {}): void {
  ctx.on('tools/pre-execute', async (exec, next) => {
    const decision = await preToolUse(exec, (payload, cwd) => spawnValidate(payload, cwd, config));
    return decision.kind === 'allow' ? next() : decision;
  });
}
