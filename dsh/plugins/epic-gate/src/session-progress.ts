import type { Context } from '@deepseek-ai/cordis';

type JsonObject = Record<string, unknown>;
type SessionEvent = {
  type?: unknown;
  data?: unknown;
};

type ProgressContext = Context & {
  on: (name: string, listener: (session: unknown, event: unknown) => void) => unknown;
};

function asObject(value: unknown): JsonObject {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as JsonObject
    : {};
}

function asText(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function eventData(event: SessionEvent): JsonObject {
  return asObject(event.data);
}

function numberValue(value: unknown): string {
  return typeof value === 'number' ? String(value) : '?';
}

function parseArguments(value: unknown): JsonObject {
  if (typeof value === 'string') {
    try {
      return asObject(JSON.parse(value));
    } catch {
      return {};
    }
  }
  return asObject(value);
}

function clipped(value: string, limit = 140): string {
  const oneLine = value.replace(/\s+/g, ' ').trim();
  return oneLine.length > limit ? `${oneLine.slice(0, limit - 3)}...` : oneLine;
}

function toolDetail(name: string, args: JsonObject): string {
  const key = name.toLowerCase();
  if (key === 'bash' || key === 'shell' || key === 'exec') {
    return clipped(asText(args.command) || asText(args.cmd));
  }
  if (key === 'read' || key === 'write' || key === 'edit' || key === 'multiedit') {
    return clipped(asText(args.file_path) || asText(args.path));
  }
  if (key === 'agent' || key === 'task') {
    return clipped(asText(args.subagent_type) || asText(args.agent_type));
  }
  return '';
}

/** Convert one durable DSH event into a short operator-facing progress line. */
export function formatSessionProgress(rawEvent: unknown): string | undefined {
  const event = asObject(rawEvent) as SessionEvent;
  const data = eventData(event);
  const type = asText(event.type);
  const turn = numberValue(data.turn);
  const step = numberValue(data.step);

  if (type === 'turn/start') return `==> dsh: turn ${turn} started\n`;
  if (type === 'step/start') return `==> dsh: LLM request turn=${turn} step=${step}\n`;
  if (type === 'assistant/chunk') return `==> dsh: LLM streaming turn=${turn} step=${step}\n`;
  if (type === 'llm/retry-started' || type === 'llm/retry') {
    return `==> dsh: LLM retry turn=${turn} step=${step}\n`;
  }
  if (type === 'compaction/start') return `==> dsh: compacting context turn=${turn}\n`;
  if (type === 'tool/call') {
    const name = asText(data.name) || '?';
    const detail = toolDetail(name, parseArguments(data.arguments));
    return `==> dsh: ${name}${detail ? ` ${detail}` : ''}\n`;
  }
  if (type === 'tool/result') {
    const message = asObject(data.message);
    const source = asObject(message.source);
    const callId = asText(data.callId) || asText(source.callId);
    return `==> dsh: tool complete${callId ? ` call=${clipped(callId, 48)}` : ''}\n`;
  }
  if (type === 'turn/end') return `==> dsh: turn ${turn} finished\n`;
  return undefined;
}

function writeProgress(line: string): void {
  try {
    process.stdout.write(line);
  } catch {
    // The outer loop may stop reading after a halt; progress must not break DSH.
  }
}

/** Stream actionable DSH session events while headless-runner waits for idle. */
export function applySessionProgress(ctx: Context): void {
  const eventContext = ctx as ProgressContext;
  const lastStreamNotice = new Map<string, number>();
  eventContext.on('session/event', (_session, event) => {
    const candidate = asObject(event);
    if (candidate.type === 'assistant/chunk') {
      const data = asObject(candidate.data);
      const key = `${numberValue(data.turn)}:${numberValue(data.step)}`;
      const now = Date.now();
      if (now - (lastStreamNotice.get(key) ?? 0) < 5_000) return;
      lastStreamNotice.set(key, now);
    }
    const line = formatSessionProgress(event);
    if (line) writeProgress(line);
  });
}

export const sessionProgressInject = ['sessions'];
