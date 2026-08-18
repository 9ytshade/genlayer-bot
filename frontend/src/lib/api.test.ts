import { describe, expect, it, vi } from 'vitest';

import { buildAppealTx, confirmAction, parseTransactionDiagnostics } from './api';
import type { Intent } from './api';

const txHash = '0x' + 'ab'.repeat(32);
const intentHash = '0x' + 'cd'.repeat(32);
const preparedTransactionId = 'prepared-transaction-1';
const intent = { action: 'deploy_contract' } as Intent;

describe('parseTransactionDiagnostics', () => {
  it('supports legacy string details', () => {
    expect(parseTransactionDiagnostics('RPC unavailable')).toEqual({ message: 'RPC unavailable' });
  });

  it('normalizes structured backend details', () => {
    expect(parseTransactionDiagnostics({
      code: 'wallet_mismatch',
      message: 'Submitted wallet does not match.',
      tx_hash: txHash,
      prepared_transaction_id: preparedTransactionId,
      intent_hash: intentHash,
      field: 'wallet',
      expected: '0xExpected',
      actual: '0xActual',
    })).toEqual({
      message: 'Submitted wallet does not match.',
      diagnostics: {
        code: 'wallet_mismatch',
        message: 'Submitted wallet does not match.',
        txHash,
        preparedTransactionId,
        intentHash,
        field: 'wallet',
        expected: '0xExpected',
        actual: '0xActual',
        retriable: undefined,
        retryAttempts: undefined,
      },
    });
  });
});

describe('confirmAction failure recovery', () => {
  it('preserves broadcast identifiers for a structured wallet mismatch', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: {
        code: 'wallet_mismatch',
        message: 'Submitted transaction wallet does not match the reviewed wallet.',
        tx_hash: txHash,
        prepared_transaction_id: preparedTransactionId,
        intent_hash: intentHash,
        field: 'wallet',
        expected: '0xExpected',
        actual: '0xActual',
      },
    }), { status: 400, headers: { 'Content-Type': 'application/json' } })));

    const result = await confirmAction(
      intent,
      '0xExpected',
      undefined,
      txHash,
      'studionet',
      preparedTransactionId,
      intentHash,
    );

    expect(result).toMatchObject({
      txHash,
      preparedTransactionId,
      intentHash,
      error: 'Submitted transaction wallet does not match the reviewed wallet.',
      transactionDiagnostics: {
        code: 'wallet_mismatch',
        field: 'wallet',
        expected: '0xExpected',
        actual: '0xActual',
      },
    });
  });

  it('marks an RPC visibility outage as safely retriable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: {
        code: 'transaction_not_visible',
        message: 'Submitted transaction is not visible on the configured network.',
        retriable: true,
        retry_attempts: 5,
      },
    }), { status: 502, headers: { 'Content-Type': 'application/json' } })));

    const result = await confirmAction(
      intent,
      '0xExpected',
      undefined,
      txHash,
      'studionet',
      preparedTransactionId,
      intentHash,
    );

    expect(result).toMatchObject({
      txHash,
      preparedTransactionId,
      intentHash,
      transactionDiagnostics: {
        code: 'transaction_not_visible',
        retriable: true,
        retryAttempts: 5,
      },
    });
  });

  it('preserves identifiers when the backend cannot be reached', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));

    const result = await confirmAction(
      intent,
      '0xExpected',
      undefined,
      txHash,
      'studionet',
      preparedTransactionId,
      intentHash,
    );

    expect(result).toMatchObject({
      txHash,
      preparedTransactionId,
      intentHash,
      transactionDiagnostics: {
        code: 'backend_unreachable',
        retriable: true,
      },
    });
  });
});


describe('buildAppealTx', () => {
  it('maps authoritative appeal metadata and prepared intent', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      to: '0x' + '12'.repeat(20), data: '0x8b5de1bc' + '34'.repeat(32), value: '123456', chain_id: 61999,
      nonce: 8, gas_limit: 90000, gas_price: '1', prepared_transaction_id: preparedTransactionId,
      intent_hash: intentHash, prepared_intent: { action: 'appeal_transaction', consensus_tx_id: txHash },
      expires_at: '2026-08-07T22:00:00Z', consensus_tx_id: txHash, consensus_status: 'ACCEPTED',
      appeal_window_open: true, appeal_window_status: 'open', minimum_appeal_bond_wei: '123456',
      appeal_bond_wei: '123456', appeal_round: 2, appeal_status_code: 5,
      appeal_window_source: 'protocol_can_appeal', minimum_appeal_bond_source: 'protocol_calculate_min_appeal_bond',
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })));
    const result = await buildAppealTx(txHash, '0xExpected', 'studionet', { action: 'appeal_transaction' } as Intent);
    expect(result).toMatchObject({
      value: BigInt(123456), consensusTxId: txHash, appealWindowOpen: true, minimumAppealBondWei: '123456',
      appealRound: 2, appealStatusCode: 5, minimumAppealBondSource: 'protocol_calculate_min_appeal_bond',
      preparedTransactionId, intentHash,
    });
  });
});
