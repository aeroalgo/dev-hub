import { spawn } from 'node:child_process';
import type { Context } from '@deepseek-ai/cordis';

import { createUserMessage } from '@deepseek-ai/dsh-llm/message';

import type { EpicGateConfig } from './pre-tool-use.ts';

type JsonObject = Record<string, unknown>;
type AgentLike = {
  id?: unknown;
  inject?: (message: unknown) => void;
  header?: JsonObject;
  session?: { header?: JsonObject };
};
type SubagentStartEvent = JsonObject & {
  id?: unknown;
  agent_id?: unknown;
  agent_type?: unknown;
  subagent_type?: unknown;
  type?: unknown;
  agentPreset?: unknown;
  preset?: unknown;
  agent?: unknown;
};
type EventContext = Context & {
  on: (name: string, listener: (event: unknown) => void) => unknown;
  get?: (name: string) => unknown;
};
type SubagentStartConfig = EpicGateConfig & {
  subagentStart?: string;
};

const PRESET_BY_AGENT: Record<string, string> = {
  verify: 'verify',
  reviewer: 'reviewer',
  explorer: 'explorer',
  explore: 'explorer',
};

function asObject(value: unknown): JsonObject {
  return value !== null && typeof value === 'object' ? value as JsonObject : {};
}

function stringValue(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value.trim() : undefined;
}

export function resolveProjectRoot(env: Record<string, string | undefined> = process.env): string | undefined {
  const epicRoot = stringValue(env.EPIC_PROJECT_ROOT);
  const projRoot = stringValue(env.PROJECT_ROOT);
  const claudeRoot = stringValue(env.CLAUDE_PROJECT_DIR);

  if (epicRoot && projRoot && epicRoot !== projRoot) {
    throw new Error(`epic-gate: invalid environment: conflicting EPIC_PROJECT_ROOT (${epicRoot}) and PROJECT_ROOT (${projRoot})`);
  }
  return epicRoot ?? projRoot ?? claudeRoot;
}

/** Resolve only an explicitly named supported preset; unknown values fail closed. */
export function normalizeNativeAgentType(value: unknown): string | undefined {
  const raw = stringValue(value)?.toLowerCase();
  if (!raw || raw === 'general-purpose') return undefined;
  const match = raw.match(/(?:^|[./:_-])(verify|reviewer|explorer|explore)$/);
  return PRESET_BY_AGENT[match?.[1] ?? raw];
}

function agentFromContext(ctx: EventContext, event: SubagentStartEvent): AgentLike | undefined {
  const direct = asObject(event.agent);
  if (typeof direct.inject === 'function') return direct as AgentLike;
  const service = ctx.get?.('agents') as { get?: (id: string) => unknown } | undefined;
  const id = stringValue(event.id) ?? stringValue(event.agent_id);
  const agent = id && typeof service?.get === 'function' ? service.get(id) : undefined;
  const candidate = asObject(agent);
  return typeof candidate.inject === 'function' ? candidate as AgentLike : undefined;
}

function agentPreset(agent?: AgentLike): unknown {
  return agent?.header?.agentPreset ?? agent?.session?.header?.agentPreset;
}

/** Prefer a native typed field, then the preset recorded on the child session. */
export function resolveNativeAgentType(
  event: unknown,
  agent?: AgentLike,
): string | undefined {
  const input = asObject(event) as SubagentStartEvent;
  for (const value of [
    input.agent_type,
    input.subagent_type,
    input.agentPreset,
    input.preset,
    input.type,
    agentPreset(agent),
  ]) {
    const type = normalizeNativeAgentType(value);
    if (type) return type;
  }
  return undefined;
}

function sessionHeader(agent?: AgentLike): JsonObject | undefined {
  return agent?.header ?? agent?.session?.header;
}

/** Build the Claude-shaped payload consumed by `.claude/hooks/subagent-start.py`. */
export function nativeSubagentStartPayload(
  event: unknown,
  agent: AgentLike,
  type: string,
): JsonObject {
  const input = asObject(event) as SubagentStartEvent;
  const header = sessionHeader(agent);
  const sessionId = stringValue(input.session_id)
    ?? stringValue(header?.id)
    ?? stringValue(agent.id)
    ?? stringValue(input.id)
    ?? stringValue(input.agent_id)
    ?? '';
  const cwd = resolveProjectRoot() ?? stringValue(input.cwd) ?? stringValue(header?.cwd) ?? process.cwd();
  return {
    ...input,
    hook_event_name: 'SubagentStart',
    session_id: sessionId,
    cwd,
    agent_type: type,
    subagent_type: type,
    agentPreset: type,
    preset: `preset.${type}`,
  };
}

function hookPath(config: SubagentStartConfig, cwd: string): string {
  const configured = config.subagentStart ?? '.claude/hooks/subagent-start.py';
  return configured.startsWith('/') ? configured : `${cwd}/${configured}`;
}

function invokePython(
  payload: JsonObject,
  cwd: string,
  config: SubagentStartConfig,
): Promise<string | undefined> {
  const python = config.python ?? process.env.PYTHON ?? 'python3';
  const path = hookPath(config, cwd);
  return new Promise((resolve, reject) => {
    const child = spawn(python, [path], {
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
        reject(new Error(`subagent-start exited ${code ?? 'unknown'}: ${stderr.trim()}`));
        return;
      }
      if (!stdout.trim()) {
        resolve(undefined);
        return;
      }
      try {
        const output = asObject(JSON.parse(stdout));
        const hookOutput = asObject(output.hookSpecificOutput);
        resolve(stringValue(hookOutput.additionalContext));
      } catch (error) {
        reject(new Error(`subagent-start returned invalid JSON: ${String(error)}`));
      }
    });
    child.stdin.end(JSON.stringify(payload));
  });
}

function startMessage(additionalContext: string) {
  return createUserMessage({
    content: [{ type: 'text', text: additionalContext }],
    source: { kind: 'plugin', plugin: 'epic-gate', form: 'notice', summary: 'epic:subagent' },
  });
}

export function applySubagentStart(
  ctx: Context,
  config: SubagentStartConfig = {},
): void {
  const eventContext = ctx as EventContext;
  eventContext.on('subagent/start', (rawEvent) => {
    const event = { ...asObject(rawEvent) } as SubagentStartEvent;
    const agent = agentFromContext(eventContext, event);
    const type = resolveNativeAgentType(event, agent);
    if (!agent || !type) return;
    const payload = nativeSubagentStartPayload(event, agent, type);
    const cwd = resolveProjectRoot() ?? stringValue(payload.cwd) ?? process.cwd();
    void invokePython(payload, cwd, config)
      .then((additionalContext) => {
        if (additionalContext) agent.inject?.(startMessage(additionalContext));
      })
      .catch((error) => {
        ctx.logger.warn(`epic-gate: subagent-start hook failed: ${String(error)}`);
      });
  });
}

export const inject = ['agents'];
