'use client';

import {
  CheckCircle2,
  ExternalLink,
  FileCode2,
  Fingerprint,
  Loader2,
  RefreshCw,
  Rocket,
  Send,
  ShieldCheck,
} from 'lucide-react';

import type { MessageStatus } from '@/lib/api';
import type { NotaryBlueprintArtifact, NotaryRecord } from '@/types/Notary';

interface NotaryBlueprintPanelProps {
  artifact: NotaryBlueprintArtifact;
  contractAddress?: string;
  operation?: 'deploy_registry' | 'submit_claim' | 'evaluate_claim';
  status?: MessageStatus;
  record?: NotaryRecord;
  onDeploy: () => void;
  onSubmit: () => void;
  onRefresh: () => void;
}
export default function NotaryBlueprintPanel({
  artifact,
  contractAddress,
  operation,
  status,
  record,
  onDeploy,
  onSubmit,
  onRefresh,
}: NotaryBlueprintPanelProps) {
  const isBusy = status === 'executing' || status === 'submitted' || status === 'finalized';
  const canDeploy = !contractAddress && status === 'awaiting_confirmation';
  const canSubmit = Boolean(contractAddress && operation === 'deploy_registry' && status === 'success');
  const canRefresh = Boolean(
    contractAddress
    && operation === 'submit_claim'
    && status === 'success'
    && !record,
  );

  return (
    <section className="data-card w-full overflow-hidden rounded-[8px] border-accent-cyan/35">
      <div className="border-b border-border-default px-4 py-4 sm:px-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="micro-label mb-1 flex items-center gap-2 text-accent-cyan">
              <ShieldCheck size={12} />
              AI Notary blueprint
            </div>
            <h3 className="font-display text-[16px] font-semibold leading-snug text-text-primary sm:text-[18px]">
              Public evidence claim
            </h3>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="status-pill border-accent-warning/45 bg-accent-warning/5 text-accent-warning">
              prototype
            </span>
            <span className="status-pill border-accent-success/45 bg-accent-success/5 text-accent-success">
              canonical source
            </span>
          </div>
        </div>

        <p className="mt-4 text-[13px] font-medium leading-relaxed text-text-primary">
          {artifact.notary_spec.statement}
        </p>

        <div className="mt-4 grid gap-px overflow-hidden rounded-[6px] border border-border-subtle bg-border-subtle sm:grid-cols-[128px_minmax(0,1fr)]">
          <div className="bg-bg-base px-3 py-2 font-mono text-[9px] uppercase text-text-muted">Claim ID</div>
          <div className="break-all bg-bg-base px-3 py-2 font-mono text-[10px] text-text-primary">
            {artifact.notary_spec.claim_id}
          </div>
          <div className="bg-bg-base px-3 py-2 font-mono text-[9px] uppercase text-text-muted">Freshness</div>
          <div className="bg-bg-base px-3 py-2 text-[11px] leading-relaxed text-text-secondary">
            {artifact.notary_spec.freshness_rule}
          </div>
        </div>
      </div>

      <div className="px-4 py-4 sm:px-5">
        <div className="micro-label mb-2">Evidence sources</div>
        <div className="space-y-2">
          {artifact.notary_spec.source_urls.map((source, index) => (
            <a
              key={source}
              href={source}
              target="_blank"
              rel="noopener noreferrer"
              className="group flex min-w-0 items-center gap-3 border-b border-border-subtle pb-2 text-[11px] text-text-secondary transition-colors last:border-b-0 last:pb-0 hover:text-accent-cyan"
            >
              <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-[4px] border border-border-strong font-mono text-[9px] text-text-muted">
                {index + 1}
              </span>
              <span className="min-w-0 flex-1 break-all">{source}</span>
              <ExternalLink size={12} className="shrink-0 opacity-55 group-hover:opacity-100" />
            </a>
          ))}
        </div>
      </div>

      <div className="grid border-y border-border-default bg-bg-base/45 sm:grid-cols-3 sm:divide-x sm:divide-border-default">
        <div className="border-b border-border-default px-4 py-3 sm:border-b-0">
          <div className="micro-label mb-1">Evidence policy</div>
          <p className="text-[10px] leading-relaxed text-text-muted">{artifact.evidence_policy}</p>
        </div>
        <div className="border-b border-border-default px-4 py-3 sm:border-b-0">
          <div className="micro-label mb-1">Validator agreement</div>
          <p className="text-[10px] leading-relaxed text-text-muted">{artifact.equivalence_rule}</p>
        </div>
        <div className="px-4 py-3">
          <div className="micro-label mb-1">Authorization</div>
          <p className="text-[10px] leading-relaxed text-text-muted">{artifact.authorization}</p>
        </div>
      </div>

      <details className="border-b border-border-default px-4 py-3 sm:px-5">
        <summary className="flex cursor-pointer list-none items-center gap-2 font-mono text-[10px] font-bold uppercase text-text-secondary hover:text-text-primary">
          <FileCode2 size={12} />
          Reviewed contract source
        </summary>
        <div className="mt-3 grid gap-2 font-mono text-[9px] text-text-muted sm:grid-cols-[120px_minmax(0,1fr)]">
          <span className="uppercase">Source SHA-256</span>
          <span className="break-all text-text-primary">{artifact.source_hash}</span>
          <span className="uppercase">GenVM runtime</span>
          <span className="break-all">{artifact.py_genlayer_dependency}</span>
          <span className="uppercase">Validator</span>
          <span className="break-all">{artifact.validator_version}</span>
        </div>
        <pre className="mt-3 max-h-72 overflow-auto rounded-[6px] border border-border-subtle bg-bg-base p-3 font-mono text-[10px] leading-relaxed text-text-secondary">
          {artifact.code}
        </pre>
      </details>

      <div className="flex flex-wrap items-center gap-2 px-4 py-3 sm:px-5">
        {canDeploy && (
          <button type="button" onClick={onDeploy} className="primary-action flex items-center gap-2 rounded-[7px] px-3 py-2 font-mono text-[10px] font-bold">
            <Rocket size={12} />
            Deploy registry
          </button>
        )}
        {canSubmit && (
          <button type="button" onClick={onSubmit} className="primary-action flex items-center gap-2 rounded-[7px] px-3 py-2 font-mono text-[10px] font-bold">
            <Send size={12} />
            Submit claim
          </button>
        )}
        {canRefresh && (
          <button type="button" onClick={onRefresh} className="control-button flex items-center gap-2 rounded-[7px] px-3 py-2 font-mono text-[10px] font-bold">
            <RefreshCw size={12} />
            Refresh claim
          </button>
        )}
        {isBusy && (
          <span className="flex items-center gap-2 font-mono text-[10px] uppercase text-accent-primary">
            <Loader2 size={12} className="animate-spin" />
            {operation === 'submit_claim'
              ? 'Submitting claim'
              : operation === 'evaluate_claim'
                ? 'Evaluating evidence'
                : 'Deploying registry'}
          </span>
        )}
        {contractAddress && (
          <span className="ml-auto flex min-w-0 items-center gap-2 font-mono text-[9px] text-text-muted">
            <Fingerprint size={12} className="shrink-0 text-accent-cyan" />
            <span className="max-w-[240px] truncate" title={contractAddress}>{contractAddress}</span>
          </span>
        )}
        {record?.evaluated && (
          <span className="ml-auto flex items-center gap-2 font-mono text-[10px] uppercase text-accent-success">
            <CheckCircle2 size={12} />
            Record finalized
          </span>
        )}
      </div>
    </section>
  );
}
