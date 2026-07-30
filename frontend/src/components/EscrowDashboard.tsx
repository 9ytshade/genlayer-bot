'use client';

import React, { useState } from 'react';
import type { EscrowConfig } from '@/types/WorkflowConfig';

interface EscrowDashboardProps {
  config: EscrowConfig;
  contractAddress?: string;
  deploymentTxHash?: string;
  onApproveRelease?: () => void;
  onRaiseDispute?: () => void;
  onCancelEscrow?: () => void;
}

export function EscrowDashboard({
  config,
  contractAddress,
  deploymentTxHash,
  onApproveRelease,
  onRaiseDispute,
  onCancelEscrow,
}: EscrowDashboardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const status = 'funded';

  return (
    <div className="rounded-lg border border-neutral-700 bg-neutral-900 p-4">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-white">Escrow Service</h3>
          <p className="mt-1 text-sm text-neutral-400">
            Secure funds until agreement is met
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
          <span className="text-sm text-neutral-400">Buyer Address:</span>
          <span className="truncate text-sm font-medium font-mono text-emerald-400">{config.buyer}</span>
        </div>

        <div className="flex justify-between">
          <span className="text-sm text-neutral-400">Seller Address:</span>
          <span className="truncate text-sm font-medium font-mono text-emerald-400">
            {config.seller}
          </span>
        </div>

        <div className="flex justify-between">
          <span className="text-sm text-neutral-400">Amount:</span>
          <span className="text-sm font-medium text-white">
            {config.amount} {config.token}
          </span>
        </div>

        <div className="flex justify-between">
          <span className="text-sm text-neutral-400">Status:</span>
          <span className={`text-sm font-medium capitalize ${
            status === 'funded'
              ? 'text-yellow-400'
              : status === 'released'
                ? 'text-emerald-400'
                : 'text-red-400'
          }`}>
            {status}
          </span>
        </div>

        {config.description && (
          <div className="border-t border-neutral-700 pt-3">
            <span className="text-sm text-neutral-400">Description:</span>
            <p className="mt-1 text-sm text-white">{config.description}</p>
          </div>
        )}

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

          <button
            onClick={onApproveRelease}
            className="w-full rounded-lg bg-emerald-600 py-2 text-sm font-medium text-white hover:bg-emerald-700"
          >
            Approve Release
          </button>

          <button
            onClick={onRaiseDispute}
            className="w-full rounded-lg bg-orange-600 py-2 text-sm font-medium text-white hover:bg-orange-700"
          >
            Raise Dispute
          </button>

          <button
            onClick={onCancelEscrow}
            className="w-full rounded-lg bg-red-600 py-2 text-sm font-medium text-white hover:bg-red-700"
          >
            Cancel Escrow
          </button>
        </div>
      )}
    </div>
  );
}
