'use client';

import React, { useState } from 'react';
import type { BountyConfig } from '@/types/WorkflowConfig';

interface BountyDashboardProps {
  config: BountyConfig;
  contractAddress?: string;
  deploymentTxHash?: string;
  submissionCount?: number;
  onReviewSubmission?: () => void;
  onSelectWinner?: () => void;
  onCloseBounty?: () => void;
}

export function BountyDashboard({
  config,
  contractAddress,
  deploymentTxHash,
  submissionCount = 0,
  onReviewSubmission,
  onSelectWinner,
  onCloseBounty,
}: BountyDashboardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const status = 'open';

  return (
    <div className="rounded-lg border border-neutral-700 bg-neutral-900 p-4">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-white">Bounty</h3>
          <p className="mt-1 text-sm text-neutral-400">{config.title}</p>
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
          <span className="text-sm text-neutral-400">Reward:</span>
          <span className="text-sm font-medium text-white">
            {config.reward} {config.token}
          </span>
        </div>

        <div className="flex justify-between">
          <span className="text-sm text-neutral-400">Submissions:</span>
          <span className="text-sm font-medium text-white">
            {submissionCount}
          </span>
        </div>

        <div className="flex justify-between">
          <span className="text-sm text-neutral-400">Status:</span>
          <span
            className={`text-sm font-medium capitalize ${
              status === 'open'
                ? 'text-emerald-400'
                : status === 'completed'
                  ? 'text-blue-400'
                  : 'text-neutral-400'
            }`}
          >
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

          {status === 'open' && (
            <>
              <button
                onClick={onReviewSubmission}
                className="w-full rounded-lg bg-blue-600 py-2 text-sm font-medium text-white hover:bg-blue-700"
              >
                Review Submission
              </button>

              <button
                onClick={onSelectWinner}
                className="w-full rounded-lg bg-emerald-600 py-2 text-sm font-medium text-white hover:bg-emerald-700"
              >
                Select Winner
              </button>

              <button
                onClick={onCloseBounty}
                className="w-full rounded-lg bg-neutral-600 py-2 text-sm font-medium text-white hover:bg-neutral-700"
              >
                Close Bounty
              </button>
            </>
          )}

          {status !== 'open' && (
            <div className="text-sm text-neutral-400">
              Bounty is {status}. No further actions available.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
