import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { BountyDashboard } from './BountyDashboard';
import { ConditionalPaymentDashboard } from './ConditionalPaymentDashboard';

describe('workflow truthfulness', () => {
  it('keeps legacy conditional payments read-only', () => {
    render(
      <ConditionalPaymentDashboard
        config={{
          workflowType: 'conditional_payment',
          recipient: '0x2222222222222222222222222222222222222222',
          amount: '1',
          token: 'GEN',
          condition: 'Evidence demonstrates delivery.',
          validated: true,
          errors: [],
        }}
        contractAddress="0x1111111111111111111111111111111111111111"
      />,
    );

    expect(screen.getByText(/legacy deterministic workflow/i)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /expand conditional payment details/i }));
    expect(screen.getByText(/settlement actions are disabled/i)).toBeTruthy();
    expect(screen.queryByRole('button', { name: /mark condition satisfied/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /cancel payment/i })).toBeNull();
    expect(screen.getByRole('button', { name: /view details/i })).toBeTruthy();
  });

  it('keeps legacy bounties read-only', () => {
    render(
      <BountyDashboard
        config={{
          workflowType: 'bounty',
          title: 'Qualitative completion',
          reward: '1',
          token: 'GEN',
          description: 'Validators judge whether the work is complete.',
          validated: true,
          errors: [],
        }}
        contractAddress="0x1111111111111111111111111111111111111111"
        state={{
          contract_address: '0x1111111111111111111111111111111111111111',
          network: 'studionet',
          workflow_type: 'bounty',
          state: {
            open: true,
            funded: true,
            winner_selected: false,
            submission_count: 1,
            balance_wei: '1000000000000000000',
          },
          transaction_hash_variant: 'latest-final',
        }}
      />,
    );

    expect(screen.getByText(/legacy issuer-managed workflow/i)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /expand bounty details/i }));
    expect(screen.getByText(/validators judge qualitative completion/i)).toBeTruthy();
    expect(screen.queryByRole('button', { name: /review submission/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /select winner/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /close bounty/i })).toBeNull();
  });
});
