import type { IncomingMessage, ServerResponse } from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import { createBridgeAction } from './intercept-run.ts';

const BODY_LIMIT = 64 * 1024;

interface BridgeActionRequest {
  action: 'arm' | 'loop' | 'arm-loop' | 'sync';
  taskId: string;
  loopArgs?: string;
  runtime?: 'claude' | 'dsh';
  workspaceId?: string;
}

async function readJsonBody(req: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = [];
  let size = 0;
  for await (const chunk of req) {
    const buffer = chunk as Buffer;
    size += buffer.length;
    if (size > BODY_LIMIT) throw new Error('body-too-large');
    chunks.push(buffer);
  }
  if (chunks.length === 0) return {};
  return JSON.parse(Buffer.concat(chunks).toString('utf8'));
}

function writeJson(res: ServerResponse, status: number, body: unknown): void {
  res.statusCode = status;
  res.setHeader('content-type', 'application/json; charset=utf-8');
  res.setHeader('cache-control', 'no-store');
  res.end(JSON.stringify(body));
}

function resolveRequestHostUrl(req: IncomingMessage): string | undefined {
  const host = req.headers.host;
  if (typeof host !== 'string' || host.trim() === '') return undefined;
  const protoHeader = req.headers['x-forwarded-proto'];
  const proto = typeof protoHeader === 'string' && protoHeader !== ''
    ? protoHeader.split(',')[0].trim()
    : 'http';
  return `${proto}://${host}`;
}

function parseBridgeAction(value: unknown): BridgeActionRequest {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new Error('mb-bridge action must be an object');
  }
  const payload = value as Record<string, unknown>;
  const action = payload.action;
  const taskId = payload.taskId;
  if (action !== 'arm' && action !== 'loop' && action !== 'arm-loop' && action !== 'sync') {
    throw new Error('mb-bridge action is invalid');
  }
  if (typeof taskId !== 'string' || taskId.trim() === '') {
    throw new Error('mb-bridge taskId is required');
  }
  const request: BridgeActionRequest = { action, taskId };
  if (typeof payload.loopArgs === 'string') request.loopArgs = payload.loopArgs;
  if (payload.runtime === 'claude' || payload.runtime === 'dsh') request.runtime = payload.runtime;
  if (typeof payload.workspaceId === 'string' && payload.workspaceId !== '') {
    request.workspaceId = payload.workspaceId;
  }
  return request;
}

function resolveDshHome(): string {
  return process.env.DSH_HOME ?? path.join(os.homedir(), '.dsh');
}

function loadWorkspaceOptions(): Array<{ id: string; label: string }> {
  const file = path.join(resolveDshHome(), 'storages/workspace.json');
  const raw = fs.readFileSync(file, 'utf8');
  const doc = JSON.parse(raw) as {
    global?: { workspaceIds?: string[] };
    tables?: { workspaces?: Record<string, { title?: string; path?: string }> };
  };
  const tables = doc.tables?.workspaces;
  if (!tables || typeof tables !== 'object') return [];
  const ids = Array.isArray(doc.global?.workspaceIds) ? doc.global.workspaceIds : Object.keys(tables);
  const items: Array<{ id: string; label: string }> = [];
  for (const id of ids) {
    const row = tables[id];
    if (!row || typeof row !== 'object') continue;
    const title = row.title;
    const rowPath = row.path;
    let label = id.slice(0, 8);
    if (typeof title === 'string' && title.trim() !== '') label = title;
    else if (typeof rowPath === 'string' && rowPath.trim() !== '') label = path.basename(rowPath);
    items.push({ id, label });
  }
  return items;
}

export function makeMbBridgeWorkspacesRoute() {
  return {
    kind: 'exact',
    path: '/api/mb-bridge/workspaces',
    handler: async (req: IncomingMessage, res: ServerResponse) => {
      if (req.method !== 'GET') {
        writeJson(res, 405, { ok: false, error: 'method-not-allowed' });
        return;
      }
      try {
        writeJson(res, 200, { ok: true, items: loadWorkspaceOptions() });
      } catch (error: unknown) {
        const message = error instanceof Error ? error.message : 'workspace list failed';
        writeJson(res, 500, { ok: false, error: message });
      }
    },
  };
}

export function makeMbBridgeRoute(config: Record<string, unknown>) {
  return {
    kind: 'exact',
    path: '/api/mb-bridge/action',
    handler: async (req: IncomingMessage, res: ServerResponse) => {
      if (req.method !== 'POST') {
        writeJson(res, 405, { ok: false, error: 'method-not-allowed' });
        return;
      }
      try {
        const body = await readJsonBody(req);
        const envelope = typeof body === 'object' && body !== null && !Array.isArray(body)
          ? body as Record<string, unknown>
          : {};
        const actionPayload = envelope.action ?? envelope;
        const hostUrl = resolveRequestHostUrl(req);
        const bridge = createBridgeAction(hostUrl ? { ...config, hostUrl } : config);
        const result = await bridge(parseBridgeAction(actionPayload));
        writeJson(res, 200, {
          ok: result.status === 'succeeded',
          status: result.status,
          exitCode: result.exitCode,
          stdout: result.stdout,
          stderr: result.stderr,
          log: result.log,
          modelSource: result.modelSource,
          modelEnv: result.modelEnv,
        });
      } catch (error: unknown) {
        const message = error instanceof Error ? error.message : 'mb-bridge action failed';
        writeJson(res, 400, { ok: false, error: message });
      }
    },
  };
}
