const TOOL_ALIASES = [
  ['Read', 'read'],
  ['Write', 'write'],
  ['Edit', 'edit'],
  ['Bash', 'bash'],
  ['Glob', 'glob'],
  ['Grep', 'grep'],
];

function parametersFor(alias, native) {
  if (!native.parameters) return {};
  const parameters = { ...native.parameters };
  if (alias === 'Bash' && parameters.description) {
    parameters.description = { ...parameters.description, required: false };
  }
  if (alias === 'Grep' && parameters.include) {
    parameters.glob = parameters.include;
    delete parameters.include;
  }
  return parameters;
}

function argumentsFor(alias, args) {
  if (args === null || typeof args !== 'object' || Array.isArray(args)) return args;
  const object = { ...args };
  if (alias === 'Bash' && !String(object.description ?? '').trim()) {
    object.description = `Run command: ${String(object.command ?? '').slice(0, 80)}`;
  }
  if (alias === 'Grep' && object.glob !== undefined && object.include === undefined) {
    object.include = object.glob;
    delete object.glob;
  }
  return object;
}

export const name = 'tool-name-compat';
export const inject = ['tools', 'systemPrompt'];

export async function apply(ctx) {
  await new Promise((resolve) => setImmediate(resolve));
  const registered = [];
  for (const [alias, nativeName] of TOOL_ALIASES) {
    if (ctx.tools.get(alias)) continue;
    const native = ctx.tools.get(nativeName);
    if (!native) continue;

    ctx.tools.register({
      ...native,
      name: alias,
      parameters: parametersFor(alias, native),
      description: `Claude compatibility alias for the DSH ${nativeName} tool; prefer ${nativeName}.`,
      async execute(args, exec) {
        const agent = exec && typeof exec === 'object' ? exec.agent : undefined;
        const current = ctx.tools.get(nativeName, agent);
        if (!current) throw new Error(`canonical DSH tool "${nativeName}" is unavailable`);
        return current.execute(argumentsFor(alias, args), exec);
      },
    });
    registered.push(`${alias}->${nativeName}`);
  }

  if (registered.length > 0 && ctx.systemPrompt?.section) {
    ctx.systemPrompt.section({
      name: 'tools:dsh-name-compatibility',
      order: 99,
      text: `Canonical DSH tool names are lowercase. Claude compatibility aliases are active (${registered.join(', ')}); prefer the lowercase names for new calls.`,
    });
  }
}

export default { name, inject, apply };
