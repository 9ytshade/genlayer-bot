'use client';

import React from 'react';
import type { AnyWorkflowConfig } from '@/types/WorkflowConfig';
import { ConditionalPaymentDashboard } from './ConditionalPaymentDashboard';
import { EscrowDashboard } from './EscrowDashboard';
import { SubscriptionDashboard } from './SubscriptionDashboard';
import { BountyDashboard } from './BountyDashboard';

interface WorkflowPanelProps {
  config: AnyWorkflowConfig;
  contractAddress?: string;
  deploymentTxHash?: string;
  onAction?: (action: string, data?: unknown) => void;
}

export function WorkflowPanel({
  config,
  contractAddress,
  deploymentTxHash,
  onAction,
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
          onCancel={() => handleAction('cancel_contract')}
          onViewDetails={() => handleAction('view_details')}
        />
      );

    case 'escrow':
      return (
        <EscrowDashboard
          config={config}
          contractAddress={contractAddress}
          deploymentTxHash={deploymentTxHash}
          onApproveRelease={() => handleAction('approve_release')}
          onRaiseDispute={() => handleAction('raise_dispute')}
          onCancelEscrow={() => handleAction('cancel_escrow')}
        />
      );

    case 'subscription':
      return (
        <SubscriptionDashboard
          config={config}
          contractAddress={contractAddress}
          deploymentTxHash={deploymentTxHash}
          onPause={() => handleAction('pause')}
          onResume={() => handleAction('resume')}
          onCancel={() => handleAction('cancel_subscription')}
        />
      );

    case 'bounty':
      return (
        <BountyDashboard
          config={config}
          contractAddress={contractAddress}
          deploymentTxHash={deploymentTxHash}
          onReviewSubmission={() => handleAction('review_submission')}
          onSelectWinner={() => handleAction('select_winner')}
          onCloseBounty={() => handleAction('close_bounty')}
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
