import { spawnHubBoard } from './python-bridge.ts';
import { BoardCard, isMbCard } from './intercept-run.ts';

export interface CardActionProps {
  card: BoardCard;
  config: Record<string, unknown>;
  onResult?: (result: Awaited<ReturnType<typeof spawnHubBoard>>) => void;
}

export function cardActions({ card, config, onResult }: CardActionProps): JSX.Element | null {
  if (!isMbCard(card)) return null;

  const run = (action: 'arm' | 'loop' | 'arm-loop') => {
    void spawnHubBoard(action, card.id, {}, config).then(onResult);
  };

  return (
    <div data-card-actions="mb-bridge">
      <button type="button" onClick={() => run('arm')}>Arm</button>
      <button type="button" onClick={() => run('loop')}>Run loop</button>
      <button type="button" onClick={() => run('arm-loop')}>Arm+Run</button>
    </div>
  );
}

export default cardActions;
