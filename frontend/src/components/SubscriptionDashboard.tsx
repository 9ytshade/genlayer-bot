'use client';

import React, { useState } from 'react';
import type { SubscriptionConfig } from '@/types/WorkflowConfig';

interface SubscriptionDashboardProps {
  config: SubscriptionConfig;
  contractAddress?: string;
  deploymentTxHash?: string;
  onPause?: () => void;
  onResume?: () => void;
  onCancel?: () => void;
}

export function SubscriptionDashboard({
  config,
  contractAddress,
  deploymentTxHash,
  onPause,
  onResume,
  onCancel,
}: SubscriptionDashboardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const isPaused = false;

  return (
    <div className="rounded-lg border border-neutral-700 bg-neutral-900 p-4">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-white">
            Subscription Payments
          </h3>
          <p className="mt-1 text-sm text-neutral-400">
            Recurring payment to {config.recipient}
          </p>
        </div>
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="text-neutral-400 hover:text-white"
        >
          {isExpanded ? '-' : '+'}
        </button>
      </div>

      <div className="space-y-3 rounded-lg bg-neutral-800 p-4">
        <div className="flex justify-between">
          <span className="text-sm text-neutral-400">Recipient Address:</span>
          <span className="truncate text-sm font-medium font-mono text-emerald-400">
            {config.recipient}
          </span>
        </div>

        <div className="flex justify-between">
          <span className="text-sm text-neutral-400">Amount:</span>
          <span className="text-sm font-medium text-white">
            {config.amount} {config.token}
          </span>
        </div>

        <div className="flex justify-between">
          <span className="text-sm text-neutral-400">Frequency:</span>
          <span className="text-sm font-medium text-white capitalize">
            {config.frequency}
          </span>
        </div>

        <div className="flex justify-between">
          <span className="text-sm text-neutral-400">Next Payment:</span>
          <span className="text-sm font-medium text-white">
            {config.nextPaymentDate || 'Not scheduled'}
          </span>
        </div>

        <div className="flex justify-between">
          <span className="text-sm text-neutral-400">Status:</span>
          <span
            className={`text-sm font-medium ${
              isPaused ? 'text-yellow-400' : 'text-emerald-400'
            }`}
          >
            {isPaused ? 'Paused' : 'Active'}
          </span>
        </div>

        {contractAddress && (
          <div className="flex justify-between">
            <span className="text-sm text-neutral-400">Contract:</span>
            <span className="truncate text-sm font-medium text-emerald-400">
              {contractAddress}
            </span>
          </div>
        )}

        {deploymentTxHash && (
          <div className="flex justify-between">
            <span className="text-sm text-neutral-400">Tx Hash:</span>
            <span className="truncate text-sm font-medium text-blue-400">
              {deploymentTxHash}
            </span>
          </div>
        )}
      </div>

      {isExpanded && contractAddress && (
        <div className="mt-4 space-y-3 border-t border-neutral-700 pt-4">
          <h4 className="text-sm font-semibold text-white">Actions</h4>

          {!isPaused ? (
            <button
              onClick={onPause}
              className="w-full rounded-lg bg-yellow-600 py-2 text-sm font-medium text-white hover:bg-yellow-700"
            >
              Pause Subscription
            </button>
          ) : (
            <button
              onClick={onResume}
              className="w-full rounded-lg bg-emerald-600 py-2 text-sm font-medium text-white hover:bg-emerald-700"
            >
              Resume Subscription
            </button>
          )}

          <button
            onClick={onCancel}
            className="w-full rounded-lg bg-red-600 py-2 text-sm font-medium text-white hover:bg-red-700"
          >
            Cancel Subscription
          </button>
        </div>
      )}
    </div>
  );
}
