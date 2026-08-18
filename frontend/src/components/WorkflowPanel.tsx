'use client';

import React from 'react';
import type { AnyWorkflowConfig } from '@/types/WorkflowConfig';
import type { WorkflowState } from '@/lib/api';
import { ConditionalPaymentDashboard } from './ConditionalPaymentDashboard';
import { EscrowDashboard } from './EscrowDashboard';
import { SubscriptionDashboard } from './SubscriptionDashboard';
import { BountyDashboard } from './BountyDashboard';

interface WorkflowPanelProps {
  config: AnyWorkflowConfig;
  contractAddress?: string;
  deploymentTxHash?: string;
  onAction?: (action: string, data?: unknown) => void;
  state?: WorkflowState;
  walletAddress?: string;
}

export function WorkflowPanel({
  config,
  contractAddress,
  deploymentTxHash,
  onAction,
  state,
  walletAddress,
}: WorkflowPanelProps) {
  const handleAction = (action: string, data?: unknown) => {
    onAction?.(action, data);
  };

  switch (config.workflowType) {
    case 'conditional_payment':
      return (
        <ConditionalPaymentDashboard
          config={config}
          contractAddress={contractAddress}
          deploymentTxHash={deploymentTxHash}
          onViewDetails={() => handleAction('view_details')}
          state={state}
        />
      );

    case 'escrow':
      return (
        <EscrowDashboard
          config={config}
          contractAddress={contractAddress}
          deploymentTxHash={deploymentTxHash}
          walletAddress={walletAddress}
          onApproveRelease={() => handleAction('approve_release')}
          onRaiseDispute={() => handleAction('raise_dispute')}
          onCancelEscrow={() => handleAction('cancel_escrow')}
          state={state}
        />
      );

    case 'subscription':
      return (
        <SubscriptionDashboard
          config={config}
          contractAddress={contractAddress}
          deploymentTxHash={deploymentTxHash}
          walletAddress={walletAddress}
          onRecordPayment={() => handleAction('record_payment')}
          onPause={() => handleAction('pause')}
          onResume={() => handleAction('resume')}
          onCancel={() => handleAction('cancel_subscription')}
          state={state}
        />
      );

    case 'bounty':
      return (
        <BountyDashboard
          config={config}
          contractAddress={contractAddress}
          deploymentTxHash={deploymentTxHash}
          state={state}
        />
      );

    default:
      return (
        <div className="rounded-lg border border-neutral-700 bg-neutral-900 p-4">
          <p className="text-neutral-400">Unknown workflow type</p>
        </div>
      );
  }
}
