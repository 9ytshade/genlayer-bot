import type { ConsensusStatusResult, Intent, MessageData, MessageStatus } from './api';

export interface ConsensusPresentation {
  messageStatus: MessageStatus;
  content: string;
  exposeDeploymentAddresses: boolean;
}

export function getConsensusPresentation(
  intent: Intent | undefined,
  result: ConsensusStatusResult
): ConsensusPresentation;

export function shouldPollConsensus(
  message: Pick<MessageData, 'intent' | 'consensusTxId' | 'txHash' | 'consensusTerminal'>
): boolean;
