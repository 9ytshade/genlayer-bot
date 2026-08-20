'use client';

import React, { useState } from 'react';
import type { BountyConfig } from '@/types/WorkflowConfig';
import type { WorkflowState } from '@/lib/api';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { formatGenWei, readStateCount } from '@/lib/workflowState';

interface BountyDashboardProps {
  config: BountyConfig;
  contractAddress?: string;
  deploymentTxHash?: string;
  submissionCount?: number;
  state?: WorkflowState;
}

export function BountyDashboard({
  config,
  contractAddress,
  deploymentTxHash,
  submissionCount = 0,
  state,
}: BountyDashboardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const contractState = state?.state;
  const onChainSubmissionCount = contractState
    ? readStateCount(contractState.submission_count)
    : String(submissionCount);
  const isOpen = contractState?.open === true;
  const status = !contractState
    ? 'Awaiting finalized state'
    : contractState.winner_selected
      ? 'Winner selected'
      : isOpen
        ? (contractState.funded ? 'Open and funded' : 'Open and unfunded')
        : 'Closed';

  return (
    <div className="rounded-lg border border-neutral-700 bg-neutral-900 p-4">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-white">Bounty</h3>
          <p className="mt-1 text-sm text-neutral-400">
            {config.title} - legacy issuer-managed workflow
          </p>
        </div>
        <button
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          className="text-neutral-400 hover:text-white"
          aria-label={isExpanded ? 'Collapse bounty details' : 'Expand bounty details'}
          title={isExpanded ? 'Collapse details' : 'Expand details'}
        >
          {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </button>
      </div>

      <div className="space-y-3 rounded-lg bg-neutral-800 p-4">
        <div className="flex justify-between">
          <span className="text-sm text-neutral-400">Reward:</span>
          <span className="text-sm font-medium text-white">
            {config.reward} {config.token}
          </span>
        </div>

        <div className="flex justify-between">
          <span className="text-sm text-neutral-400">Submissions:</span>
          <span className="text-sm font-medium text-white">
            {onChainSubmissionCount}
          </span>
        </div>

        <div className="flex justify-between">
          <span className="text-sm text-neutral-400">Status:</span>
          <span
            className={`text-sm font-medium ${
              isOpen
                ? 'text-emerald-400'
                : 'text-neutral-400'
            }`}
          >
            {status}
          </span>
        </div>

        {contractState && (
          <>
            <div className="flex justify-between">
              <span className="text-sm text-neutral-400">Held by contract:</span>
              <span className="text-sm font-medium text-white">{formatGenWei(contractState.balance_wei)}</span>
            </div>
            {contractState.winner_selected ? (
              <div className="flex justify-between">
                <span className="text-sm text-neutral-400">Paid to winner:</span>
                <span className="text-sm font-medium text-emerald-400">{formatGenWei(contractState.paid_amount_wei)}</span>
              </div>
            ) : null}
            {!contractState.winner_selected && !contractState.open ? (
              <div className="flex justify-between">
                <span className="text-sm text-neutral-400">Refunded to issuer:</span>
                <span className="text-sm font-medium text-emerald-400">{formatGenWei(contractState.refunded_amount_wei)}</span>
              </div>
            ) : null}
          </>
        )}

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
          <h4 className="text-sm font-semibold text-white">Read-only status</h4>

          {isOpen && (
            <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200">
              Review, winner selection, and closure are disabled until GenLayer validators judge
              qualitative completion with structured insufficient-evidence support.
            </p>
          )}

          {!isOpen && (
            <div className="text-sm text-neutral-400">
              Bounty is {status}. No further actions available.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
