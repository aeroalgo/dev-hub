import { parse as parseYaml } from 'yaml';

export const FOOTER_DELIMITER = '\n---\nmb-board-card/v1\n';

export interface StepCard {
  schema: 'mb-board-card/v1';
  card_kind: 'step';
  project_root: string;
  workspace_id: string;
  role: string;
  epic_id: string;
  step_id: string;
  decompose_rel: string;
  phase: string;
  sync_generation: number;
  hub_dev?: string | null;
}

export interface GateCard {
  schema: 'mb-board-card/v1';
  card_kind: 'gate';
  project_root: string;
  workspace_id: string;
  role: string;
  epic_id?: string | null;
  gate_phase: string;
  decompose_rel?: string | null;
  phase: string;
  sync_generation: number;
  reason_code?: string | null;
  hub_dev?: string | null;
}

export interface EpicCard {
  schema: 'mb-board-card/v1';
  card_kind: 'epic';
  project_root: string;
  workspace_id: string;
  role: string;
  epic_id: string;
  next_command: string;
  next_step_id?: string | null;
  progress_summary: string;
  roadmap_rank: number;
  sync_generation: number;
  hub_dev?: string | null;
}

export type ParsedCardMetadata = StepCard | GateCard | EpicCard | (Record<string, unknown> & { card_kind?: unknown });

export function extractMetadata(description?: string): Record<string, unknown> {
  if (!description) {
    return {};
  }

  try {
    if (description.includes(FOOTER_DELIMITER)) {
      const parts = description.split(FOOTER_DELIMITER);
      const footerText = parts[parts.length - 1];
      const parsed: unknown = parseYaml(footerText);
      if (parsed && typeof parsed === 'object') {
        return parsed as Record<string, unknown>;
      }
      return {};
    }

    // Legacy JSON fallback
    const parsedJson: unknown = JSON.parse(description);
    if (parsedJson && typeof parsedJson === 'object') {
      return parsedJson as Record<string, unknown>;
    }
    return {};
  } catch {
    return {};
  }
}

export function parseCardMetadata(description?: string): ParsedCardMetadata {
  const meta = extractMetadata(description);
  if (meta.schema !== 'mb-board-card/v1') {
    return meta;
  }
  if (meta.card_kind === 'step') {
    return meta as unknown as StepCard;
  }
  if (meta.card_kind === 'gate') {
    return meta as unknown as GateCard;
  }
  if (meta.card_kind === 'epic') {
    return meta as unknown as EpicCard;
  }
  return meta;
}
