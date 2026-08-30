import { createUserMessage } from '@deepseek-ai/dsh-llm/message';
import type { Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';

import {
  apply as applyPreToolUse,
  inject as preToolUseInject,
  type EpicGateConfig,
} from './pre-tool-use.ts';

export type SessionStartContext = {
  additionalContext: string;
  sessionTitle?: string;
};

export function sessionStartMessage(context: SessionStartContext) {
  return createUserMessage({
    content: [{ type: 'text', text: context.additionalContext }],
    source: { kind: 'plugin', plugin: 'epic-gate', form: 'notice', summary: context.sessionTitle ?? 'epic:context' },
  });
}

export function applySessionStart(ctx: Context, getContext: () => SessionStartContext | undefined): void {
  ctx.on('agent/session-start', ({ agent }: { agent: Agent }) => {
    const context = getContext();
    if (context?.additionalContext) agent.inject(sessionStartMessage(context));
  });
}
import {
  applySubagentStart,
  inject as subagentStartInject,
} from './subagent-start.ts';
import {
  applySubagentStop,
  inject as subagentStopInject,
} from './subagent-stop.ts';

export const name = 'epic-gate';
export const inject = [...new Set([...preToolUseInject, ...subagentStartInject, ...subagentStopInject])];

export function apply(ctx: Context, config: EpicGateConfig = {}): void {
  applyPreToolUse(ctx, config);
  applySubagentStart(ctx, config);
  applySubagentStop(ctx, config);
  applySessionStart(ctx, () => {
    const additionalContext = process.env.EPIC_SESSION_START_CONTEXT?.trim();
    if (!additionalContext) return undefined;
    return {
      additionalContext,
      sessionTitle: process.env.EPIC_SESSION_TITLE?.trim() || undefined,
    };
  });
}

export const sessionStartInject = ['agents'];

export {
  enrichSubagentStopPayload,
  extractVerdict,
  outputText,
} from './subagent-stop.ts';
export type { EpicGateConfig } from './pre-tool-use.ts';

export default { name, inject, apply };
