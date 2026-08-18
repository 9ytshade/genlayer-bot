'use client';

import React, { useState } from 'react';
import type { EscrowConfig } from '@/types/WorkflowConfig';
import type { WorkflowState } from '@/lib/api';
import { Ban, ChevronDown, ChevronUp, HandCoins, ShieldAlert } from 'lucide-react';
import { formatGenWei, isSameAddress } from '@/lib/workflowState';

interface EscrowDashboardProps {
  config: EscrowConfig;
  contractAddress?: string;
  deploymentTxHash?: string;
  walletAddress?: string;
  onApproveRelease?: () => void;
  onRaiseDispute?: () => void;
  onCancelEscrow?: () => void;
  state?: WorkflowState;
}

export function EscrowDashboard({
  config,
  contractAddress,
  deploymentTxHash,
  walletAddress,
  onApproveRelease,
  onRaiseDispute,
  onCancelEscrow,
  state,
}: EscrowDashboardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const contractState = state?.state;
  const status = !contractState
    ? 'Awaiting finalized state'
    : contractState.cancelled
      ? 'Cancelled'
      : contractState.released
        ? 'Released'
        : contractState.disputed
          ? 'Disputed'
          : contractState.funded
            ? 'Funded'
            : 'Unfunded';
  const isOpen = Boolean(contractState && !contractState.cancelled && !contractState.released);
  const isBuyer = isSameAddress(walletAddress, contractState?.buyer);
  const isSeller = isSameAddress(walletAddress, contractState?.seller);
  const canRelease = Boolean(isBuyer && isOpen && !contractState?.disputed && contractState?.funded);
  const canDispute = Boolean((isBuyer || isSeller) && isOpen && !contractState?.disputed);
  const canCancel = Boolean(isBuyer && isOpen && !contractState?.disputed);

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
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          className="text-neutral-400 hover:text-white"
          aria-label={isExpanded ? 'Collapse escrow details' : 'Expand escrow details'}
          title={isExpanded ? 'Collapse details' : 'Expand details'}
        >
          {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
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
          <span className={`text-sm font-medium ${
            status === 'Funded'
              ? 'text-yellow-400'
              : status === 'Released'
                ? 'text-emerald-400'
                : 'text-neutral-300'
          }`}>
            {status}
          </span>
        </div>

        {contractState && (
          <div className="flex justify-between">
            <span className="text-sm text-neutral-400">Held by contract:</span>
            <span className="text-sm font-medium text-white">{formatGenWei(contractState.balance_wei)}</span>
          </div>
        )}

        {contractState?.released ? (
          <div className="flex justify-between">
            <span className="text-sm text-neutral-400">Paid to seller:</span>
            <span className="text-sm font-medium text-emerald-400">{formatGenWei(contractState.released_amount_wei)}</span>
          </div>
        ) : null}

        {contractState?.cancelled ? (
          <div className="flex justify-between">
            <span className="text-sm text-neutral-400">Refunded to buyer:</span>
            <span className="text-sm font-medium text-emerald-400">{formatGenWei(contractState.refunded_amount_wei)}</span>
          </div>
        ) : null}

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
            type="button"
            onClick={onApproveRelease}
            disabled={!canRelease}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-600 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-45"
            title={!isBuyer ? 'Only the buyer can approve release' : undefined}
          >
            <HandCoins size={15} />
            Approve Release
          </button>

          <button
            type="button"
            onClick={onRaiseDispute}
            disabled={!canDispute}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-orange-600 py-2 text-sm font-medium text-white hover:bg-orange-700 disabled:cursor-not-allowed disabled:opacity-45"
            title={!isBuyer && !isSeller ? 'Only the buyer or seller can raise a dispute' : undefined}
          >
            <ShieldAlert size={15} />
            Raise Dispute
          </button>

          <button
            type="button"
            onClick={onCancelEscrow}
            disabled={!canCancel}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-red-600 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-45"
            title={!isBuyer ? 'Only the buyer can cancel this escrow' : undefined}
          >
            <Ban size={15} />
            Cancel Escrow
          </button>
        </div>
      )}
    </div>
  );
}
