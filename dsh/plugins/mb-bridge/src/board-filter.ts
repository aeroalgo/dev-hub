export interface WorkspaceCard {
  metadata?: Record<string, unknown>;
  description?: string;
}

function parseMetadata(card: WorkspaceCard): Record<string, unknown> {
  if (card.metadata) return card.metadata;
  if (!card.description) return {};
  try {
    const parsed: unknown = JSON.parse(card.description);
    return parsed && typeof parsed === 'object' ? parsed as Record<string, unknown> : {};
  } catch {
    return {};
  }
}

/** Return a new card list containing only the selected workspace. */
export function filterCards<T extends WorkspaceCard>(
  cards: readonly T[],
  workspaceId: string | null,
): T[] {
  if (workspaceId === null) return cards.filter(() => true);
  return cards.filter((card) => parseMetadata(card).workspace_id === workspaceId);
}
