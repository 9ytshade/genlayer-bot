import assert from 'node:assert/strict';
import test from 'node:test';

import {
  getConsensusPresentation,
  shouldPollConsensus,
} from './consensusLifecycle.mjs';

function consensusResult(overrides = {}) {
  return {
    consensusTxId: '0xconsensus',
    status: 'PENDING',
    statusCode: 1,
    executionStatus: 'NOT_VOTED',
    final: false,
    appealable: false,
    terminal: false,
    contractAddress: null,
    derivedAddresses: [],
    ...overrides,
  };
}

test('all provisional lifecycle states render as submitted', () => {
  const statuses = [
    'UNINITIALIZED',
    'PENDING',
    'PROPOSING',
    'COMMITTING',
    'REVEALING',
    'ACCEPTED',
    'APPEAL_REVEALING',
    'APPEAL_COMMITTING',
    'READY_TO_FINALIZE',
    'UNKNOWN',
  ];

  for (const status of statuses) {
    const presentation = getConsensusPresentation(
      { action: 'deploy_contract' },
      consensusResult({ status })
    );
    assert.equal(presentation.messageStatus, 'submitted', status);
    assert.equal(presentation.exposeDeploymentAddresses, false, status);
  }
});

test('accepted, appealed, and ready-to-finalize copy remains provisional', () => {
  assert.match(
    getConsensusPresentation(undefined, consensusResult({ status: 'ACCEPTED' })).content,
    /provisionally/i
  );
  assert.match(
    getConsensusPresentation(undefined, consensusResult({ status: 'APPEAL_COMMITTING' })).content,
    /appeal round/i
  );
  assert.match(
    getConsensusPresentation(undefined, consensusResult({ status: 'READY_TO_FINALIZE' })).content,
    /not been recorded/i
  );
});

test('finalized successful execution renders success and exposes deployment addresses', () => {
  const presentation = getConsensusPresentation(
    { action: 'deploy_contract' },
    consensusResult({
      status: 'FINALIZED',
      statusCode: 7,
      executionStatus: 'FINISHED_WITH_RETURN',
      final: true,
      terminal: true,
    })
  );

  assert.equal(presentation.messageStatus, 'success');
  assert.equal(presentation.exposeDeploymentAddresses, true);
  assert.match(presentation.content, /executed successfully/i);
});

test('finalized failed execution renders an error without deployment addresses', () => {
  const presentation = getConsensusPresentation(
    { action: 'contract_call', method: 'release' },
    consensusResult({
      status: 'FINALIZED',
      statusCode: 7,
      executionStatus: 'FINISHED_WITH_ERROR',
      final: true,
      terminal: true,
    })
  );

  assert.equal(presentation.messageStatus, 'error');
  assert.equal(presentation.exposeDeploymentAddresses, false);
  assert.match(presentation.content, /failed during GenVM execution/i);
  assert.match(presentation.content, /state was not changed/i);
});

test('finalized unknown or not-voted execution renders a pollable finalized state', () => {
  for (const executionStatus of ['UNKNOWN', 'NOT_VOTED']) {
    const result = consensusResult({
      status: 'FINALIZED',
      statusCode: 7,
      executionStatus,
      final: true,
      terminal: false,
    });
    const presentation = getConsensusPresentation(undefined, result);

    assert.equal(presentation.messageStatus, 'finalized', executionStatus);
    assert.equal(presentation.exposeDeploymentAddresses, false, executionStatus);
    assert.match(presentation.content, /verification will continue/i);
    assert.equal(
      shouldPollConsensus({
        consensusTxId: result.consensusTxId,
        consensusTerminal: result.terminal,
        consensusFinal: result.final,
      }),
      true,
      executionStatus
    );
  }
});

test('all terminal non-final outcomes render errors instead of permanent spinners', () => {
  const statuses = [
    'UNDETERMINED',
    'CANCELED',
    'VALIDATORS_TIMEOUT',
    'LEADER_TIMEOUT',
  ];

  for (const status of statuses) {
    const presentation = getConsensusPresentation(
      undefined,
      consensusResult({ status, terminal: true, appealable: status === 'UNDETERMINED' })
    );
    assert.equal(presentation.messageStatus, 'error', status);
    assert.equal(presentation.exposeDeploymentAddresses, false, status);
    assert.match(presentation.content, /did not complete|timed out/i, status);
  }
});

test('poll eligibility depends on terminal state, not consensus finality', () => {
  assert.equal(
    shouldPollConsensus({
      consensusTxId: '0xfinalized-unverified',
      consensusFinal: true,
      consensusTerminal: false,
    }),
    true
  );
  assert.equal(
    shouldPollConsensus({
      consensusTxId: '0xterminal',
      consensusFinal: false,
      consensusTerminal: true,
    }),
    false
  );
  assert.equal(
    shouldPollConsensus({
      consensusTxId: '0xpending',
      consensusTerminal: undefined,
    }),
    true
  );
  assert.equal(shouldPollConsensus({ consensusTerminal: false }), false);
});


test('zero-round NO_MAJORITY is terminal error and does not expose deployment addresses', () => {
  const presentation = getConsensusPresentation({ action: 'deploy_contract' }, consensusResult({
    protocolResult: 'NO_MAJORITY',
    zeroRoundNoMajority: true,
    final: true,
    terminal: true,
    executionStatus: 'NOT_VOTED',
  }));
  assert.equal(presentation.messageStatus, 'error');
  assert.equal(presentation.exposeDeploymentAddresses, false);
  assert.match(presentation.content, /without assigning validators/i);
});

test('poll recovery accepts an EVM tx hash when consensus id is missing', () => {
  assert.equal(shouldPollConsensus({ txHash: '0x' + 'ab'.repeat(32), consensusTerminal: false }), true);
});


test('plain transfers do not enter intelligent-contract consensus polling', () => {
  assert.equal(shouldPollConsensus({
    intent: { action: 'transfer' },
    txHash: '0xtransfer',
    consensusTxId: '0xtransfer',
    consensusTerminal: false,
  }), false);
});
