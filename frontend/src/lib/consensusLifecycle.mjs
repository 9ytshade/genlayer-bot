const TERMINAL_FAILURE_STATUSES = new Set([
  'UNDETERMINED',
  'CANCELED',
  'VALIDATORS_TIMEOUT',
  'LEADER_TIMEOUT',
]);

function successfulContent(intent) {
  if (intent?.action === 'deploy_contract') {
    return 'Intelligent Contract deployment finalized and executed successfully on GenLayer.';
  }
  if (intent?.action === 'contract_call') {
    return `Workflow action '${intent.method || 'contract call'}' finalized and executed successfully on GenLayer.`;
  }
  return 'Transaction finalized and executed successfully on GenLayer.';
}

function executionFailureContent(intent) {
  if (intent?.action === 'deploy_contract') {
    return 'GenLayer consensus finalized, but the Intelligent Contract deployment failed during GenVM execution. No deployable contract address is available.';
  }
  if (intent?.action === 'contract_call') {
    return `GenLayer consensus finalized, but workflow action '${intent.method || 'contract call'}' failed during GenVM execution. Contract state was not changed.`;
  }
  return 'GenLayer consensus finalized, but the transaction failed during GenVM execution. Contract state was not changed.';
}

function terminalFailureContent(status) {
  switch (status) {
    case 'UNDETERMINED':
      return 'GenLayer validators did not reach a final outcome. The transaction did not complete.';
    case 'CANCELED':
      return 'The GenLayer consensus transaction was canceled and did not complete.';
    case 'VALIDATORS_TIMEOUT':
      return 'Validator consensus timed out. The transaction did not complete.';
    case 'LEADER_TIMEOUT':
      return 'The consensus leader timed out. The transaction did not complete.';
    default:
      return 'The GenLayer consensus transaction ended without a successful result.';
  }
}

function provisionalContent(result) {
  switch (result.status) {
    case 'ACCEPTED':
      return 'GenLayer consensus accepted this transaction provisionally. It is not final while the appeal window remains open.';
    case 'READY_TO_FINALIZE':
      return 'Consensus completed and the transaction is ready to finalize, but finality has not been recorded yet.';
    case 'APPEAL_REVEALING':
    case 'APPEAL_COMMITTING':
      return 'An appeal round is in progress. The prior accepted result remains provisional.';
    default:
      return `GenLayer consensus is ${result.status.toLowerCase().replaceAll('_', ' ')}. The wallet receipt confirms submission only.`;
  }
}

export function getConsensusPresentation(intent, result) {
  if (result.zeroRoundNoMajority || result.protocolResult === 'NO_MAJORITY') {
    return {
      messageStatus: 'error',
      content: 'Studionet finalized this transaction without assigning validators (0 rounds, NO_MAJORITY). No contract was deployed and the wallet retry safety gate is active.',
      exposeDeploymentAddresses: false,
    };
  }

  if (TERMINAL_FAILURE_STATUSES.has(result.status)) {
    return {
      messageStatus: 'error',
      content: terminalFailureContent(result.status),
      exposeDeploymentAddresses: false,
    };
  }

  if (result.final) {
    if (result.executionStatus === 'FINISHED_WITH_RETURN') {
      return {
        messageStatus: 'success',
        content: successfulContent(intent),
        exposeDeploymentAddresses: true,
      };
    }
    if (result.executionStatus === 'FINISHED_WITH_ERROR') {
      return {
        messageStatus: 'error',
        content: executionFailureContent(intent),
        exposeDeploymentAddresses: false,
      };
    }
    return {
      messageStatus: 'finalized',
      content: 'GenLayer consensus is finalized, but the GenVM execution result is not available yet. Verification will continue.',
      exposeDeploymentAddresses: false,
    };
  }

  return {
    messageStatus: 'submitted',
    content: provisionalContent(result),
    exposeDeploymentAddresses: false,
  };
}

export function shouldPollConsensus(message) {
  if (message.intent?.action === 'transfer' || message.intent?.action === 'check_balance') {
    return false;
  }
  return Boolean((message.consensusTxId || message.txHash) && message.consensusTerminal !== true);
}
