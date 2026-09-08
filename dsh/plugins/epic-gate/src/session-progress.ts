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
  if (key === 'str_replace_editor') {
    const command = asText(args.command);
    const path = asText(args.path);
    return [command, path].filter(Boolean).join(' ');
  }
  if (key === 'agent' || key === 'task') {
    return clipped(asText(args.subagent_type) || asText(args.agent_type));
  }
  return '';
}

function nestedText(value: unknown): string {
  if (typeof value === 'string') return value.trim();
  if (Array.isArray(value)) {
    for (const item of value) {
      const text = nestedText(item);
      if (text) return text;
    }
    return '';
  }
  if (value !== null && typeof value === 'object') {
    const object = value as JsonObject;
    if (typeof object.text === 'string') return object.text.trim();
    for (const key of ['content', 'message', 'error']) {
      const text = nestedText(object[key]);
      if (text) return text;
    }
  }
  return '';
}

function toolError(data: JsonObject): string {
  const error = asObject(data.error);
  const message = asText(error.message);
  if (message) return message;

  const content = asObject(data.message).content;
  const contentText = nestedText(content);
  if (contentText) return contentText;

  const code = asText(error.code);
  const name = asText(error.name);
  if (name || code) return [name, code].filter(Boolean).join(' / ');
  return data.isError === true ? 'tool execution failed' : '';
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
    const name = asText(data.name);
    const error = toolError(data);
    if (error) {
      return `==> dsh: tool failed${name ? ` name=${name}` : ''}${callId ? ` call=${clipped(callId, 48)}` : ''} error=${clipped(error)}\n`;
    }
    return `==> dsh: tool complete${name ? ` name=${name}` : ''}${callId ? ` call=${clipped(callId, 48)}` : ''}\n`;
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
  const calls = new Map<string, { name: string }>();
  eventContext.on('session/event', (_session, event) => {
    const candidate = asObject(event);
    if (candidate.type === 'tool/call') {
      const data = asObject(candidate.data);
      const callId = asText(data.callId);
      const name = asText(data.name);
      if (callId && name) calls.set(callId, { name });
    }
    if (candidate.type === 'assistant/chunk') {
      const data = asObject(candidate.data);
      const key = `${numberValue(data.turn)}:${numberValue(data.step)}`;
      const now = Date.now();
      if (now - (lastStreamNotice.get(key) ?? 0) < 5_000) return;
      lastStreamNotice.set(key, now);
    }
    let formattedEvent: JsonObject = candidate;
    if (candidate.type === 'tool/result') {
      const data = asObject(candidate.data);
      const message = asObject(data.message);
      const source = asObject(message.source);
      const callId = asText(data.callId) || asText(source.callId);
      const call = callId ? calls.get(callId) : undefined;
      if (call && !asText(data.name)) {
        formattedEvent = { ...candidate, data: { ...data, name: call.name } };
      }
      if (callId) calls.delete(callId);
    }
    const line = formatSessionProgress(formattedEvent);
    if (line) writeProgress(line);
  });
}

export const sessionProgressInject = ['sessions'];
