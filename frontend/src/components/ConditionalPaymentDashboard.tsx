'use client';

import React, { useState } from 'react';
import type { ConditionalPaymentConfig } from '@/types/WorkflowConfig';

interface ConditionalPaymentDashboardProps {
  config: ConditionalPaymentConfig;
  contractAddress?: string;
  deploymentTxHash?: string;
  onCancel?: () => void;
  onViewDetails?: () => void;
}

export function ConditionalPaymentDashboard({
  config,
  contractAddress,
  deploymentTxHash,
  onCancel,
  onViewDetails,
}: ConditionalPaymentDashboardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="rounded-lg border border-neutral-700 bg-neutral-900 p-4">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-white">
            Conditional Payment
          </h3>
          <p className="mt-1 text-sm text-neutral-400">
            Payment scheduled when condition is met
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
          <span className="text-sm text-neutral-400">Condition:</span>
          <span className="text-sm font-medium text-white">
            {config.condition}
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

      {isExpanded && (
        <div className="mt-4 space-y-3 border-t border-neutral-700 pt-4">
          <h4 className="text-sm font-semibold text-white">Actions</h4>

          {contractAddress && (
            <>
              <button
                onClick={onViewDetails}
                className="w-full rounded-lg bg-blue-600 py-2 text-sm font-medium text-white hover:bg-blue-700"
              >
                View Details
              </button>

              <button
                onClick={onCancel}
                className="w-full rounded-lg bg-red-600 py-2 text-sm font-medium text-white hover:bg-red-700"
              >
                Cancel Contract
              </button>
            </>
          )}

          {!contractAddress && (
            <div className="text-sm text-neutral-400">
              Deploy the contract to enable actions.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
