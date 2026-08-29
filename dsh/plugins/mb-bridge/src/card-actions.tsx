import { BoardAction, BridgeConfig, HostExecutionResult, spawnHubBoard } from './python-bridge';
import { BoardCard, isMbCard } from './intercept-run';

export interface CardActionProps {
  card: BoardCard;
  config: BridgeConfig;
  onResult?: (result: HostExecutionResult) => void;
}

export function cardActions({ card, config, onResult }: CardActionProps): JSX.Element | null {
  if (!isMbCard(card)) return null;

  const run = (action: BoardAction) => {
    void spawnHubBoard(action, card.id, {}, config).then(onResult);
  };
  return (
    <div data-card-actions="mb-bridge">
      <button type="button" onClick={() => run('arm-loop')}>Arm+Run</button>
      <button type="button" onClick={() => run('arm')}>Arm</button>
      <button type="button" onClick={() => run('loop')}>Run loop</button>
    </div>
  );
}
