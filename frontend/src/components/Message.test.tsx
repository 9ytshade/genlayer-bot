import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import Message from './Message';
import type { Intent, MessageData } from '@/lib/api';

const txHash = '0x' + 'ab'.repeat(32);

describe('Message failed transaction diagnostics', () => {
  it('shows the broadcast hash, wallet mismatch, prepared envelope, and retry action', () => {
    const onConfirm = vi.fn();
    const msg: MessageData = {
      id: '1723028400000',
      role: 'bot',
      content: 'Execution failed: Submitted transaction wallet does not match the reviewed wallet.',
      status: 'error',
      intent: { action: 'deploy_contract' } as Intent,
      txHash,
      preparedTransactionId: 'prepared-transaction-1',
      intentHash: '0x' + 'cd'.repeat(32),
      transactionDiagnostics: {
        code: 'wallet_mismatch',
        message: 'Submitted transaction wallet does not match the reviewed wallet.',
        field: 'wallet',
        expected: '0xExpectedWallet',
        actual: '0xActualWallet',
      },
    };

    render(
      <Message
        msg={msg}
        onConfirm={onConfirm}
        onCancel={vi.fn()}
        onUpdateIntent={vi.fn()}
        onWorkflowAction={vi.fn()}
        onNotaryAction={vi.fn()}
      />,
    );

    expect(screen.getByText(`HASH: ${txHash}`)).toBeTruthy();
    expect(screen.getByText('Code: wallet_mismatch')).toBeTruthy();
    expect(screen.getByText('Prepared transaction: prepared-transaction-1')).toBeTruthy();
    expect(screen.getByText('Expected: 0xExpectedWallet')).toBeTruthy();
    expect(screen.getByText('Submitted: 0xActualWallet')).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: /retry transaction/i }));
    expect(onConfirm).toHaveBeenCalledWith(msg.id);
  });
});
