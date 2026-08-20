'use client';

import React, { useState } from 'react';
import type { SubscriptionConfig } from '@/types/WorkflowConfig';
import type { WorkflowState } from '@/lib/api';
import { Ban, ChevronDown, ChevronUp, CircleDollarSign, Pause, Play } from 'lucide-react';
import { formatGenWei, isSameAddress, readStateCount } from '@/lib/workflowState';

interface SubscriptionDashboardProps {
  config: SubscriptionConfig;
  contractAddress?: string;
  deploymentTxHash?: string;
  walletAddress?: string;
  onRecordPayment?: () => void;
  onPause?: () => void;
  onResume?: () => void;
  onCancel?: () => void;
  state?: WorkflowState;
}

export function SubscriptionDashboard({
  config,
  contractAddress,
  deploymentTxHash,
  walletAddress,
  onRecordPayment,
  onPause,
  onResume,
  onCancel,
  state,
}: SubscriptionDashboardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const contractState = state?.state;
  const isCancelled = Boolean(contractState?.cancelled);
  const isActive = Boolean(contractState?.active) && !isCancelled;
  const isPayer = isSameAddress(walletAddress, contractState?.payer);
  const canManage = Boolean(contractState && isPayer && !isCancelled);
  const status = !contractState
    ? 'Awaiting finalized state'
    : isCancelled
      ? 'Cancelled'
      : isActive
        ? 'Active'
        : 'Paused';

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
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          className="text-neutral-400 hover:text-white"
          aria-label={isExpanded ? 'Collapse subscription details' : 'Expand subscription details'}
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
          <span className="text-sm text-neutral-400">Status:</span>
          <span
            className={`text-sm font-medium ${
              isActive ? 'text-emerald-400' : 'text-yellow-400'
            }`}
          >
            {status}
          </span>
        </div>

        {contractState && (
          <>
            <div className="flex justify-between">
              <span className="text-sm text-neutral-400">Finalized payments:</span>
              <span className="text-sm font-medium text-white">{readStateCount(contractState.payment_count)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-neutral-400">Total paid:</span>
              <span className="text-sm font-medium text-emerald-400">{formatGenWei(contractState.total_paid_wei)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-neutral-400">Held by contract:</span>
              <span className="text-sm font-medium text-white">{formatGenWei(contractState.balance_wei)}</span>
            </div>
          </>
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
            type="button"
            onClick={onRecordPayment}
            disabled={!canManage || !isActive}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-45"
            title={!isPayer ? 'Only the payer can record a subscription payment' : undefined}
          >
            <CircleDollarSign size={15} />
            Record Payment
          </button>

          {isActive ? (
            <button
              type="button"
              onClick={onPause}
              disabled={!canManage}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-yellow-600 py-2 text-sm font-medium text-white hover:bg-yellow-700 disabled:cursor-not-allowed disabled:opacity-45"
            >
              <Pause size={15} />
              Pause Subscription
            </button>
          ) : (
            <button
              type="button"
              onClick={onResume}
              disabled={!canManage}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-600 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-45"
            >
              <Play size={15} />
              Resume Subscription
            </button>
          )}

          <button
            type="button"
            onClick={onCancel}
            disabled={!canManage}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-red-600 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-45"
            title={!isPayer ? 'Only the payer can cancel this subscription' : undefined}
          >
            <Ban size={15} />
            Cancel Subscription
          </button>
        </div>
      )}
    </div>
  );
}
