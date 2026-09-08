import type { Context } from '@deepseek-ai/cordis';
import type { ToolDefinition } from '@deepseek-ai/dsh-tools';

type JsonObject = Record<string, unknown>;

type ToolRuntime = Pick<Context['tools'], 'get' | 'register'>;

type ToolContext = Context & { tools: ToolRuntime };

const TOOL_ALIASES = [
  ['Read', 'read'],
  ['Write', 'write'],
  ['Edit', 'edit'],
  ['Bash', 'bash'],
  ['Glob', 'glob'],
  ['Grep', 'grep'],
] as const;

function parametersFor(alias: string, native: ToolDefinition): ToolDefinition['parameters'] {
  if (!native.parameters) return {};
  const parameters = { ...native.parameters };
  if (alias === 'Bash' && parameters.description) {
    parameters.description = { ...parameters.description as JsonObject, required: false };
  }
  if (alias === 'Grep' && parameters.include) {
    parameters.glob = parameters.include;
    delete parameters.include;
  }
  return parameters as ToolDefinition['parameters'];
}

function argumentsFor(alias: string, args: unknown): unknown {
  if (args === null || typeof args !== 'object' || Array.isArray(args)) return args;
  const object = { ...args as JsonObject };
  if (alias === 'Bash' && !String(object.description ?? '').trim()) {
    object.description = `Run command: ${String(object.command ?? '').slice(0, 80)}`;
  }
  if (alias === 'Grep' && object.glob !== undefined && object.include === undefined) {
    object.include = object.glob;
    delete object.glob;
  }
  return object;
}

export function applyToolNameCompatibility(ctx: Context): void {
  const toolContext = ctx as ToolContext;
  const registered: string[] = [];
  for (const [alias, nativeName] of TOOL_ALIASES) {
    if (toolContext.tools.get(alias)) continue;
    const native = toolContext.tools.get(nativeName);
    if (!native) continue;
    toolContext.tools.register({
      ...native,
      name: alias,
      parameters: parametersFor(alias, native),
      description: `Compatibility alias for the DSH ${nativeName} tool; prefer ${nativeName}.`,
      async execute(args, exec) {
        const current = toolContext.tools.get(nativeName, (exec as unknown as { agent?: object }).agent);
        if (!current) throw new Error(`canonical DSH tool "${nativeName}" is unavailable`);
        return current.execute(argumentsFor(alias, args), exec);
      },
    });
    registered.push(`${alias}->${nativeName}`);
  }
  if (registered.length > 0) {
    ctx.systemPrompt.section({
      name: 'tools:dsh-name-compatibility',
      order: 99,
      text: `Canonical DSH tool names are lowercase. Compatibility aliases are active (${registered.join(', ')}); prefer the lowercase names for new calls.`,
    });
  }
}
