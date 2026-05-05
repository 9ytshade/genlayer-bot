'use client';

import React from 'react';
import { FileCode2, Settings2 } from 'lucide-react';
import type { Intent } from '../lib/api';

interface DeployContractPanelProps {
  intent: Intent;
  disabled?: boolean;
  onChange: (patch: Partial<Intent>) => void;
}

export default function DeployContractPanel({ intent, disabled = false, onChange }: DeployContractPanelProps) {
  const sourceName = intent.source_file_name || `${intent.contract_name || 'contract'}.py`;
  const sourcePreview = typeof intent.code === 'string'
    ? intent.code.split('\n').slice(0, 12).join('\n')
    : '';

  return (
    <div className="mt-3 border border-border-strong bg-bg-surface">
      <div className="flex items-center justify-between border-b border-border-strong bg-black px-4 py-3">
        <div className="flex items-center gap-2 text-accent-primary">
          <Settings2 size={14} />
          <span className="font-mono text-[11px] font-bold uppercase tracking-widest">Deploy Config</span>
        </div>
        <span className="font-mono text-[10px] uppercase tracking-widest text-text-muted">{sourceName}</span>
      </div>

      <div className="grid gap-3 p-4 md:grid-cols-2">
        <label className="flex flex-col gap-1">
          <span className="font-mono text-[10px] uppercase tracking-widest text-text-muted">Contract Name</span>
          <input
            type="text"
            value={intent.contract_name || ''}
            disabled={disabled}
            onChange={(event) => onChange({ contract_name: event.target.value })}
            className="bg-black border border-border-strong px-3 py-2 text-sm text-text-primary focus:border-accent-primary focus:outline-none"
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="font-mono text-[10px] uppercase tracking-widest text-text-muted">Initial Value (GEN)</span>
          <input
            type="number"
            min="0"
            step="0.0001"
            value={intent.deploy_value_text || '0'}
            disabled={disabled}
            onChange={(event) => onChange({ deploy_value_text: event.target.value })}
            className="bg-black border border-border-strong px-3 py-2 text-sm text-text-primary focus:border-accent-primary focus:outline-none"
          />
        </label>

        <label className="flex flex-col gap-1 md:col-span-2">
          <span className="font-mono text-[10px] uppercase tracking-widest text-text-muted">Constructor Args (JSON Array)</span>
          <textarea
            rows={3}
            value={intent.constructor_args_text || '[]'}
            disabled={disabled}
            onChange={(event) => onChange({ constructor_args_text: event.target.value })}
            className="resize-y bg-black border border-border-strong px-3 py-2 font-mono text-xs text-text-primary focus:border-accent-primary focus:outline-none"
          />
        </label>

        <label className="flex flex-col gap-1 md:col-span-2">
          <span className="font-mono text-[10px] uppercase tracking-widest text-text-muted">Constructor Kwargs (JSON Object)</span>
          <textarea
            rows={3}
            value={intent.constructor_kwargs_text || '{}'}
            disabled={disabled}
            onChange={(event) => onChange({ constructor_kwargs_text: event.target.value })}
            className="resize-y bg-black border border-border-strong px-3 py-2 font-mono text-xs text-text-primary focus:border-accent-primary focus:outline-none"
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="font-mono text-[10px] uppercase tracking-widest text-text-muted">Gas Limit</span>
          <input
            type="number"
            min="21000"
            step="1"
            value={intent.gas_limit_text || ''}
            disabled={disabled}
            onChange={(event) => onChange({ gas_limit_text: event.target.value })}
            className="bg-black border border-border-strong px-3 py-2 text-sm text-text-primary focus:border-accent-primary focus:outline-none"
            placeholder="Auto"
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="font-mono text-[10px] uppercase tracking-widest text-text-muted">Consensus Rotations</span>
          <input
            type="number"
            min="1"
            step="1"
            value={intent.consensus_max_rotations_text || ''}
            disabled={disabled}
            onChange={(event) => onChange({ consensus_max_rotations_text: event.target.value })}
            className="bg-black border border-border-strong px-3 py-2 text-sm text-text-primary focus:border-accent-primary focus:outline-none"
            placeholder="Default"
          />
        </label>

        <label className="md:col-span-2 flex items-center gap-3 border border-border-strong bg-black px-3 py-2">
          <input
            type="checkbox"
            checked={Boolean(intent.leader_only)}
            disabled={disabled}
            onChange={(event) => onChange({ leader_only: event.target.checked })}
            className="h-4 w-4 accent-[var(--color-accent-primary)]"
          />
          <div className="flex flex-col">
            <span className="font-mono text-[11px] uppercase tracking-widest text-text-primary">Leader-only execution</span>
            <span className="text-[11px] text-text-muted">Use validator leader-only mode for this deployment.</span>
          </div>
        </label>
      </div>

      <div className="border-t border-border-strong p-4">
        <div className="mb-2 flex items-center gap-2 text-text-secondary">
          <FileCode2 size={14} />
          <span className="font-mono text-[10px] uppercase tracking-widest">Source Preview</span>
        </div>
        <pre className="max-h-52 overflow-auto bg-black p-3 font-mono text-[11px] leading-relaxed text-text-secondary">
          {sourcePreview || '# No source code attached'}
        </pre>
      </div>
    </div>
  );
}
