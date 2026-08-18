'use client';

import React, { useState } from 'react';
import { Check, Copy, ExternalLink, Settings2 } from 'lucide-react';
import type { ConsensusStatus, ExecutionStatus, Intent, MessageStatus } from '../lib/api';

interface DeployContractPanelProps {
  intent: Intent;
  disabled?: boolean;
  txHash?: string;
  consensusTxId?: string;
  consensusStatus?: ConsensusStatus;
  executionStatus?: ExecutionStatus;
  contractAddress?: string;
  derivedAddresses?: string[];
  status?: MessageStatus;
  onChange: (patch: Partial<Intent>) => void;
}

function DeploymentValue({
  label,
  value,
  fallback,
  explorerUrl,
  copiedKey,
  onCopy,
}: {
  label: string;
  value?: string;
  fallback: string;
  explorerUrl?: string | null;
  copiedKey?: string | null;
  onCopy: (key: string, value: string) => void;
}) {
  return (
    <>
      <span className="uppercase tracking-[0.08em] text-text-muted">{label}</span>
      <span className={`flex min-w-0 items-center justify-end gap-2 text-right ${value ? 'text-text-primary' : 'text-text-muted'}`}>
        <span className="min-w-0 break-all">{value || fallback}</span>
        {value && (
          <span className="flex shrink-0 items-center gap-1">
            <button
              type="button"
              onClick={() => onCopy(label, value)}
              className="control-button flex h-6 w-6 items-center justify-center rounded-[6px]"
              title={`Copy ${label}`}
            >
              {copiedKey === label ? <Check size={11} className="text-accent-success" /> : <Copy size={11} />}
            </button>
            {explorerUrl && (
              <a
                href={explorerUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="control-button flex h-6 items-center gap-1 rounded-[6px] px-2 text-[9px] text-accent-success"
                title="View transaction in GenLayer explorer"
              >
                <ExternalLink size={10} />
                Check in explorer
              </a>
            )}
          </span>
        )}
      </span>
    </>
  );
}

export default function DeployContractPanel({
  intent,
  disabled = false,
  txHash,
  consensusTxId,
  consensusStatus,
  executionStatus,
  contractAddress,
  derivedAddresses = [],
  status,
  onChange,
}: DeployContractPanelProps) {
  const sourceName = intent.source_file_name || `${intent.contract_name || 'contract'}.py`;
  const hasBroadcast = Boolean(
    txHash
    || consensusTxId
    || contractAddress
    || derivedAddresses.length > 0
    || status === 'success'
    || status === 'finalized'
  );
  const statusLabel = status === 'success'
    ? 'execution successful'
    : status === 'finalized'
      ? 'finalized, verifying execution'
      : status === 'error'
        ? (
            executionStatus === 'FINISHED_WITH_ERROR'
              ? 'execution failed'
              : (consensusStatus || 'failed').replaceAll('_', ' ').toLowerCase()
          )
    : status === 'submitted'
      ? (consensusStatus || 'submitted').replaceAll('_', ' ').toLowerCase()
      : status === 'executing'
        ? 'broadcasting'
        : 'not broadcast';
  const statusTone = status === 'success'
    ? 'border-accent-success/45 bg-accent-success/5 text-accent-success'
    : status === 'error'
      ? 'border-accent-danger/45 bg-accent-danger/5 text-accent-danger'
      : status === 'executing' || status === 'submitted'
        ? 'border-accent-primary/45 bg-accent-primary/5 text-accent-primary'
        : 'border-accent-warning/45 bg-accent-warning/5 text-accent-warning';
  const detailsTone = status === 'error'
    ? 'border-accent-danger/35 bg-accent-danger/10'
    : status === 'finalized'
      ? 'border-accent-warning/35 bg-accent-warning/10'
      : 'border-accent-success/35 bg-accent-success/10';
  const contractAddressFallback = status === 'error'
    ? 'Unavailable because deployment did not complete successfully.'
    : status === 'finalized'
      ? 'Consensus finalized; waiting for a verified GenVM execution result.'
      : status === 'success'
        ? 'Execution succeeded, but no contract address was returned.'
        : hasBroadcast
          ? 'Available after finalized successful execution.'
          : 'Generated after deploy when available.';
  const derivedAddressesFallback = status === 'error'
    ? 'Unavailable because deployment did not complete successfully.'
    : status === 'finalized'
      ? 'Waiting for a verified GenVM execution result.'
      : status === 'success'
        ? 'No derived deployment addresses were returned.'
        : hasBroadcast
          ? 'Available after finalized successful execution.'
          : 'Shown after deploy when available.';
  const configuredTxExplorerBase = process.env.NEXT_PUBLIC_EXPLORER_TX_URL;
  const txExplorerBase = configuredTxExplorerBase || 'https://explorer-studio.genlayer.com/tx/';
  const txExplorerUrl = txHash && /^0x[a-fA-F0-9]{64}$/.test(txHash) ? `${txExplorerBase}${txHash}` : null;
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const handleCopy = (key: string, value: string) => {
    navigator.clipboard.writeText(value);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 1800);
  };

  return (
    <div className="data-card mt-3 overflow-hidden rounded-[12px]">
      <div className="flex items-start justify-between gap-3 border-b border-border-default px-4 py-4">
        <div>
          <div className="mb-2 flex items-center gap-2 text-accent-primary">
          <Settings2 size={14} />
            <span className="micro-label text-accent-primary">Deploy Contract</span>
          </div>
          <h3 className="font-display text-[18px] font-semibold leading-tight text-text-primary">
            {sourceName}
          </h3>
        </div>
        <span className={`status-pill ${statusTone}`}>
          {statusLabel}
        </span>
      </div>

      <div className="grid gap-3 p-4 md:grid-cols-2">
        <label className="flex flex-col gap-1">
          <span className="micro-label">Contract Name</span>
          <input
            type="text"
            value={intent.contract_name || ''}
            disabled={disabled}
            onChange={(event) => onChange({ contract_name: event.target.value })}
            className="field-input px-3 py-2 font-mono text-[11px]"
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="micro-label">Source File</span>
          <div className="field-input px-3 py-2 font-mono text-[11px] text-text-secondary">
            {sourceName}
          </div>
        </label>

        <div className="flex min-w-0 flex-col gap-1 md:col-span-2">
          <span className="micro-label">Reviewed Source SHA-256</span>
          <div className="field-input min-w-0 break-all px-3 py-2 font-mono text-[10px] text-text-secondary">
            {intent.source_hash || 'Source must be generated or validated again.'}
          </div>
        </div>

        <label className="flex flex-col gap-1 md:col-span-2">
          <span className="micro-label">Constructor Args JSON Array</span>
          <textarea
            rows={3}
            value={intent.constructor_args_text || '[]'}
            disabled={disabled}
            onChange={(event) => onChange({ constructor_args_text: event.target.value })}
            className="field-input min-h-20 resize-y px-3 py-2 font-mono text-[11px]"
          />
        </label>

        <label className="flex flex-col gap-1 md:col-span-2">
          <span className="micro-label">Constructor Kwargs JSON Object</span>
          <textarea
            rows={3}
            value={intent.constructor_kwargs_text || '{}'}
            disabled={disabled}
            onChange={(event) => onChange({ constructor_kwargs_text: event.target.value })}
            className="field-input min-h-20 resize-y px-3 py-2 font-mono text-[11px]"
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="micro-label">Initial Value in GEN</span>
          <input
            type="number"
            min="0"
            step="0.0001"
            value={intent.deploy_value_text || '0'}
            disabled={disabled}
            onChange={(event) => onChange({ deploy_value_text: event.target.value })}
            className="field-input px-3 py-2 font-mono text-[11px]"
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="micro-label">Gas Limit</span>
          <input
            type="number"
            min="21000"
            step="1"
            value={intent.gas_limit_text || ''}
            disabled={disabled}
            onChange={(event) => onChange({ gas_limit_text: event.target.value })}
            className="field-input px-3 py-2 font-mono text-[11px]"
            placeholder="Auto"
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="micro-label">Consensus Rotations</span>
          <input
            type="number"
            min="1"
            step="1"
            value={intent.consensus_max_rotations_text || ''}
            disabled={disabled}
            onChange={(event) => onChange({ consensus_max_rotations_text: event.target.value })}
            className="field-input px-3 py-2 font-mono text-[11px]"
            placeholder="Default"
          />
        </label>

        <label className="flex items-center gap-3 rounded-[8px] border border-border-subtle bg-bg-base/55 px-3 py-2">
          <input
            type="checkbox"
            checked={Boolean(intent.leader_only)}
            disabled={disabled}
            onChange={(event) => onChange({ leader_only: event.target.checked })}
            className="h-3.5 w-3.5 accent-[var(--color-accent-primary)]"
          />
          <span className="font-mono text-[10px] font-bold text-text-primary">Leader-only execution</span>
        </label>

        <div className="md:col-span-2 flex flex-wrap gap-2">
          <span className="status-pill border-accent-success/45 bg-accent-success/5 text-accent-success">source hash bound</span>
          <span className="status-pill border-accent-success/45 bg-accent-success/5 text-accent-success">GenVM runtime pinned</span>
          <span className="status-pill border-accent-primary/45 bg-accent-primary/5 text-accent-primary">
            validator recorded
          </span>
        </div>

        <div className={`md:col-span-2 rounded-[10px] border p-4 font-mono text-[10px] text-text-secondary ${detailsTone}`}>
          <div className="grid gap-2 sm:grid-cols-[150px_minmax(0,1fr)]">
            <DeploymentValue
              label="EVM Tx Hash"
              value={txHash}
              fallback={hasBroadcast ? 'Not returned by wallet/backend confirmation.' : 'Awaiting wallet broadcast.'}
              explorerUrl={txExplorerUrl}
              copiedKey={copiedKey}
              onCopy={handleCopy}
            />
            <DeploymentValue
              label="Consensus Tx Id"
              value={consensusTxId}
              fallback={hasBroadcast ? 'Not returned. Receipt may not include a consensus transaction id.' : 'Pending confirmation.'}
              copiedKey={copiedKey}
              onCopy={handleCopy}
            />
            <DeploymentValue
              label="Contract Address"
              value={contractAddress}
              fallback={contractAddressFallback}
              copiedKey={copiedKey}
              onCopy={handleCopy}
            />
            <span className="uppercase tracking-[0.08em] text-text-muted">Derived Addresses</span>
            <span className={`min-w-0 break-words text-right ${derivedAddresses.length ? 'text-text-primary' : 'text-text-muted'}`}>
              {derivedAddresses.length ? (
                <span className="flex flex-col items-end gap-1">
                  {derivedAddresses.map((address, index) => {
                    const key = `Derived Address ${index + 1}`;
                    return (
                      <span key={address} className="flex max-w-full items-center justify-end gap-2">
                        <span className="min-w-0 break-all">{address}</span>
                        <button
                          type="button"
                          onClick={() => handleCopy(key, address)}
                          className="control-button flex h-6 w-6 shrink-0 items-center justify-center rounded-[6px]"
                          title="Copy derived address"
                        >
                          {copiedKey === key ? <Check size={11} className="text-accent-success" /> : <Copy size={11} />}
                        </button>
                      </span>
                    );
                  })}
                </span>
              ) : derivedAddressesFallback}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
