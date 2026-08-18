'use client';

import React, { useState } from 'react';
import type { ConditionalPaymentConfig } from '@/types/WorkflowConfig';
import type { WorkflowState } from '@/lib/api';
import { ChevronDown, ChevronUp, RefreshCw } from 'lucide-react';
import { formatGenWei } from '@/lib/workflowState';

interface ConditionalPaymentDashboardProps {
  config: ConditionalPaymentConfig;
  contractAddress?: string;
  deploymentTxHash?: string;
  onViewDetails?: () => void;
  state?: WorkflowState;
}

export function ConditionalPaymentDashboard({
  config,
  contractAddress,
  deploymentTxHash,
  onViewDetails,
  state,
}: ConditionalPaymentDashboardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const contractState = state?.state;
  const status = !contractState
    ? 'Awaiting finalized state'
    : contractState.cancelled
      ? 'Cancelled'
      : contractState.executed
        ? 'Executed'
        : contractState.funded
          ? 'Funded'
          : 'Unfunded';
  return (
    <div className="rounded-lg border border-neutral-700 bg-neutral-900 p-4">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-white">
            Conditional Payment
          </h3>
          <p className="mt-1 text-sm text-neutral-400">
            Legacy deterministic workflow - GenLayer condition adjudication is not available
          </p>
        </div>
        <button
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          className="text-neutral-400 hover:text-white"
          aria-label={isExpanded ? 'Collapse conditional payment details' : 'Expand conditional payment details'}
          title={isExpanded ? 'Collapse details' : 'Expand details'}
        >
          {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
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
          <span className="text-sm text-neutral-400">Status:</span>
          <span className="text-sm font-medium text-white">{status}</span>
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

        {contractState && (
          <div className="flex justify-between">
            <span className="text-sm text-neutral-400">Held by contract:</span>
            <span className="text-sm font-medium text-white">{formatGenWei(contractState.balance_wei)}</span>
          </div>
        )}

        {contractState?.executed ? (
          <div className="flex justify-between">
            <span className="text-sm text-neutral-400">Paid:</span>
            <span className="text-sm font-medium text-emerald-400">{formatGenWei(contractState.paid_amount_wei)}</span>
          </div>
        ) : null}

        {contractState?.cancelled ? (
          <div className="flex justify-between">
            <span className="text-sm text-neutral-400">Refunded:</span>
            <span className="text-sm font-medium text-emerald-400">{formatGenWei(contractState.refunded_amount_wei)}</span>
          </div>
        ) : null}

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
          <h4 className="text-sm font-semibold text-white">Read-only status</h4>

          {contractAddress && (
            <>
              <button
                type="button"
                onClick={onViewDetails}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 py-2 text-sm font-medium text-white hover:bg-blue-700"
              >
                <RefreshCw size={15} />
                View Details
              </button>

              <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200">
                Settlement actions are disabled until evidence evaluation, structured abstention,
                and deterministic GEN settlement are rebuilt and proven.
              </p>
            </>
          )}

          {!contractAddress && (
            <div className="text-sm text-neutral-400">
              New conditional-payment deployment is currently unavailable.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
