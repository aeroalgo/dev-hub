import { spawn } from 'node:child_process';
import type { Context } from '@deepseek-ai/cordis';
import { resolveProjectRoot } from './subagent-start.ts';

import type { EpicGateConfig } from './pre-tool-use.ts';

type JsonObject = Record<string, unknown>;
type Verdict = 'PASS' | 'FAIL' | 'BLOCKED';

type SubagentStopEvent = JsonObject & {
  id?: unknown;
  agent_id?: unknown;
  agent_type?: unknown;
  subagent_type?: unknown;
  type?: unknown;
  agentPreset?: unknown;
  preset?: unknown;
  lastAssistantMessage?: unknown;
  last_assistant_message?: unknown;
  last_message?: unknown;
  output?: unknown;
  transcript?: unknown;
  transcript_path?: unknown;
};

type AgentSession = {
  id?: unknown;
  header?: JsonObject;
  session?: { header?: JsonObject; events?: unknown };
};

export type SubagentStopHook = (payload: JsonObject, cwd: string) => Promise<void>;

export interface SubagentStopConfig extends EpicGateConfig {
  subagentStop?: string;
}

type EventContext = Context & {
  on: (name: string, listener: (event: unknown) => void) => unknown;
  get?: (name: string) => unknown;
};

const VERDICT_LINE = /^VERDICT:\s*(PASS|FAIL|BLOCKED)\b/gim;
const PRESET_BY_AGENT: Record<string, string> = {
  verify: 'verify',
  reviewer: 'reviewer',
  explorer: 'explorer',
  explore: 'explorer',
};

function asObject(value: unknown): JsonObject {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as JsonObject
    : {};
}

function stringValue(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value : undefined;
}

/** Flatten DSH assistant output/content blocks without assuming a provider shape. */
export function outputText(value: unknown): string {
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return value.map(outputText).join('');
  if (value === null || typeof value !== 'object') return '';
  const object = asObject(value);
  if (typeof object.text === 'string') return object.text;
  for (const key of ['content', 'message', 'lastAssistantMessage', 'last_assistant_message', 'last_message', 'output']) {
    const text = outputText(object[key]);
    if (text) return text;
  }
  return '';
}

/** Match the final line-start VERDICT, just like the Python hook. */
export function extractVerdict(value: unknown): Verdict | null {
  const text = outputText(value);
  let verdict: Verdict | null = null;
  for (const match of text.matchAll(VERDICT_LINE)) verdict = match[1] as Verdict;
  return verdict;
}

function normalizeAgentType(value: unknown): string | undefined {
  const raw = stringValue(value)?.toLowerCase();
  if (!raw || raw === 'general-purpose') return undefined;
  const match = raw.match(/(?:^|[./:_-])(verify|reviewer|explorer|explore)$/);
  return PRESET_BY_AGENT[match?.[1] ?? raw];
}

function agentIdentity(agent?: AgentSession): string | undefined {
  return stringValue(agent?.header?.agentPreset)
    ?? stringValue(agent?.session?.header?.agentPreset);
}

function eventIdentity(event: SubagentStopEvent): string | undefined {
  return stringValue(event.runId) ?? stringValue(event.id) ?? stringValue(event.agent_id);
}

function rememberAgentType(
  identities: Map<string, string>,
  event: SubagentStopEvent,
  agent?: AgentSession,
): void {
  const type = normalizeAgentType(agentIdentity(agent));
  const identity = eventIdentity(event);
  if (type && identity) identities.set(identity, type);
  const id = stringValue(event.id) ?? stringValue(event.agent_id);
  if (type && id) identities.set(id, type);
}

function agentFromContext(ctx: EventContext, event: SubagentStopEvent): AgentSession | undefined {
  const service = ctx.get?.('agents');
  const id = stringValue(event.id) ?? stringValue(event.agent_id);
  const registry = service as { get?: (id: string) => unknown } | undefined;
  const agent = id && typeof registry?.get === 'function' ? registry.get(id) : undefined;
  return agent && typeof agent === 'object' ? agent as AgentSession : undefined;
}

function outputFromAgent(agent?: AgentSession): unknown {
  const events = agent?.session && (agent.session as { events?: unknown }).events;
  if (!Array.isArray(events)) return undefined;
  for (const event of [...events].reverse()) {
    const candidate = asObject(event);
    if (candidate.type === 'assistant/message') return candidate.message ?? candidate;
  }
  return undefined;
}

function eventOutput(event: SubagentStopEvent, agent?: AgentSession): unknown {
  return event.lastAssistantMessage
    ?? event.last_assistant_message
    ?? event.last_message
    ?? event.output
    ?? outputFromAgent(agent);
}

function agentType(ctx: EventContext, event: SubagentStopEvent, agent?: AgentSession): string | undefined {
  for (const value of [
    event.agent_type,
    event.subagent_type,
    event.type,
    event.agentPreset,
    event.preset,
    agent?.header?.agentPreset,
    agent?.session?.header?.agentPreset,
  ]) {
    const type = normalizeAgentType(value);
    if (type) return type;
  }
  return undefined;
}

function sessionHeader(agent?: AgentSession): JsonObject | undefined {
  return agent?.header ?? agent?.session?.header;
}

function hookPath(config: EpicGateConfig, cwd: string): string {
  const configured = (config as EpicGateConfig & { subagentStop?: string }).subagentStop
    ?? '.claude/hooks/subagent-stop.py';
  return configured.startsWith('/') ? configured : `${cwd}/${configured}`;
}

function invokePython(
  payload: JsonObject,
  cwd: string,
  config: EpicGateConfig,
): Promise<void> {
  const python = config.python ?? process.env.PYTHON ?? 'python3';
  const path = hookPath(config, cwd);
  return new Promise((resolve, reject) => {
    const child = spawn(python, [path], {
      cwd,
      env: { ...process.env, PYTHONPATH: `${cwd}/.claude/hooks` },
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    let stderr = '';
    child.stderr.on('data', (chunk: Buffer | string) => { stderr += String(chunk); });
    child.once('error', reject);
    child.once('close', (code) => {
      if (code !== 0) {
        reject(new Error(`subagent-stop exited ${code ?? 'unknown'}: ${stderr.trim()}`));
        return;
      }
      resolve();
    });
    child.stdin.end(JSON.stringify(payload));
  });
}

/** Build the Claude-shaped payload consumed by `.claude/hooks/subagent-stop.py`. */
export function enrichSubagentStopPayload(
  ctx: EventContext,
  rawEvent: unknown,
): JsonObject {
  const event = { ...asObject(rawEvent) } as SubagentStopEvent;
  const agent = agentFromContext(ctx, event);
  const header = sessionHeader(agent);
  const output = eventOutput(event, agent);
  const text = outputText(output);
  const transcript = outputText(event.transcript);
  const verdict = extractVerdict((event as JsonObject).verdict ?? output ?? transcript);
  const root = resolveProjectRoot();
  const cwd = stringValue(event.cwd) ?? stringValue(header?.cwd) ?? root ?? process.cwd();
  const sessionId = stringValue(event.session_id)
    ?? stringValue(header?.id)
    ?? stringValue(event.id)
    ?? '';
  const type = agentType(ctx, event, agent);

  return {
    ...event,
    session_id: sessionId,
    cwd,
    ...(type ? { agent_type: type } : {}),
    ...(text ? { last_assistant_message: text, last_message: text, output: text } : {}),
    ...(transcript ? { transcript } : {}),
    ...(verdict ? { verdict } : {}),
  };
}

export function applySubagentStop(
  ctx: Context,
  config: EpicGateConfig = {},
): void {
  const eventContext = ctx as EventContext;
  eventContext.on('subagent/end', (rawEvent) => {
    const payload = enrichSubagentStopPayload(eventContext, rawEvent);
    const cwd = stringValue(payload.cwd) ?? process.cwd();
    void invokePython(payload, cwd, config).catch((error) => {
      ctx.logger.warn(`epic-gate: subagent-stop hook failed: ${String(error)}`);
    });
  });
}

export const inject = ['agents'];
