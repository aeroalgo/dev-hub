import { extractMetadata, parseCardMetadata, ParsedCardMetadata } from './card-metadata.js';

export interface WorkspaceCard {
  metadata?: Record<string, unknown>;
  description?: string;
  step_id?: string;
  allowRun?: boolean;
  roadmap_rank?: number;
}

function parseMetadata(card: WorkspaceCard): Record<string, unknown> {
  if (card.metadata) return card.metadata;
  return extractMetadata(card.description);
}

/** Return a new card list containing only the selected workspace. */
export function filterCards<T extends WorkspaceCard>(
  cards: readonly T[],
  workspaceId: string | null,
): T[] {
  if (workspaceId === null) return cards.filter(() => true);
  return cards.filter((card) => parseMetadata(card).workspace_id === workspaceId);
}

/**
 * Filter or enrich cards for board execution logic.
 * For card_kind === 'epic':
 * - Skip step_id validation.
 * - allowRun is set to true unless next_command === 'epic_done'.
 * - roadmap_rank is propagated from EpicCard metadata.
 */
export function filterBoardCard<T extends WorkspaceCard>(
  card: T,
  expectedStepId?: string | null,
): { card: T; isValid: boolean; allowRun: boolean; roadmapRank?: number } {
  const meta: ParsedCardMetadata = card.metadata
    ? (card.metadata as ParsedCardMetadata)
    : parseCardMetadata(card.description);

  if (meta && typeof meta === 'object' && 'card_kind' in meta && meta.card_kind === 'epic') {
    const epicMeta = meta as import('./card-metadata.js').EpicCard;
    const allowRun = epicMeta.next_command !== 'epic_done';
    return {
      card: {
        ...card,
        allowRun,
        roadmap_rank: epicMeta.roadmap_rank,
      },
      isValid: true,
      allowRun,
      roadmapRank: epicMeta.roadmap_rank,
    };
  }

  // Non-epic card: step_id validation applies if expectedStepId is provided
  let isValid = true;
  if (expectedStepId && card.step_id && card.step_id !== expectedStepId) {
    isValid = false;
  }

  const allowRun = isValid && (card.allowRun ?? true);

  return {
    card,
    isValid,
    allowRun,
  };
}
