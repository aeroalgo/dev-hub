export interface WorkspaceOption {
  id: string;
  label: string;
}

export interface WorkspaceListHost {
  workspace?: {
    list: (request: Record<string, never>) => Promise<unknown>;
  };
}

export type WorkspaceListState =
  | { status: 'ready'; options: WorkspaceOption[] }
  | { status: 'unavailable' | 'invalid'; options: []; error: string };

export class WorkspaceListValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'WorkspaceListValidationError';
  }
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === 'object' ? value as Record<string, unknown> : undefined;
}

function unwrapWorkspaceListResponse(value: unknown): unknown {
  const response = asRecord(value);
  const result = asRecord(response?.result) ?? response;
  if (!result || result.ok !== true) {
    throw new Error('Host workspace.list request failed');
  }
  return result.value;
}

export function parseWorkspaceListResponse(value: unknown): WorkspaceOption[] {
  const response = asRecord(unwrapWorkspaceListResponse(value));
  const items = response?.items;
  if (!Array.isArray(items)) {
    throw new WorkspaceListValidationError('Host workspace.list returned no items array');
  }

  const seen = new Set<string>();
  return items.map((item, index) => {
    const workspace = asRecord(item);
    const id = workspace?.workspaceId;
    const label = workspace?.title;
    if (typeof id !== 'string' || id.trim() === '') {
      throw new WorkspaceListValidationError(`Host workspace.list item ${index} has an invalid workspace id`);
    }
    if (typeof label !== 'string' || label.trim() === '') {
      throw new WorkspaceListValidationError(`Host workspace.list item ${index} has an invalid workspace label`);
    }
    if (seen.has(id)) {
      throw new WorkspaceListValidationError(`Host workspace.list contains duplicate workspace id: ${id}`);
    }
    seen.add(id);
    return { id, label };
  });
}

export function createWorkspaceListAdapter(
  host?: WorkspaceListHost,
): () => Promise<WorkspaceListState> {
  return async () => {
    if (!host?.workspace?.list) {
      return {
        status: 'unavailable',
        options: [],
        error: 'Host workspace.list capability is unavailable',
      };
    }

    try {
      const response = await host.workspace.list({});
      return { status: 'ready', options: parseWorkspaceListResponse(response) };
    } catch (error: unknown) {
      if (error instanceof WorkspaceListValidationError) {
        return { status: 'invalid', options: [], error: error.message };
      }
      return {
        status: 'unavailable',
        options: [],
        error: error instanceof Error ? error.message : 'Host workspace.list request failed',
      };
    }
  };
}
