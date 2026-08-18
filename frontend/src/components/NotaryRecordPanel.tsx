'use client';

import {
  CircleHelp,
  ExternalLink,
  FileSearch,
  Loader2,
  RefreshCw,
  Scale,
  ShieldCheck,
  ShieldX,
} from 'lucide-react';

import type { NotaryRecord, NotaryVerdict } from '@/types/Notary';

interface NotaryRecordPanelProps {
  record: NotaryRecord;
  isBusy?: boolean;
  onEvaluate: () => void;
  onRefresh: () => void;
}
const verdictConfig: Record<NotaryVerdict, { label: string; tone: string; icon: typeof ShieldCheck }> = {
  PENDING: {
    label: 'Pending evaluation',
    tone: 'border-accent-warning/45 bg-accent-warning/5 text-accent-warning',
    icon: CircleHelp,
  },
  CONFIRMED: {
    label: 'Confirmed',
    tone: 'border-accent-success/45 bg-accent-success/5 text-accent-success',
    icon: ShieldCheck,
  },
  REFUTED: {
    label: 'Refuted',
    tone: 'border-accent-danger/45 bg-accent-danger/5 text-accent-danger',
    icon: ShieldX,
  },
  INCONCLUSIVE: {
    label: 'Inconclusive',
    tone: 'border-accent-warning/45 bg-accent-warning/5 text-accent-warning',
    icon: Scale,
  },
};

export default function NotaryRecordPanel({
  record,
  isBusy = false,
  onEvaluate,
  onRefresh,
}: NotaryRecordPanelProps) {
  const verdict = verdictConfig[record.verdict];
  const VerdictIcon = verdict.icon;

  return (
    <section className="data-card w-full overflow-hidden rounded-[8px]">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border-default px-4 py-4 sm:px-5">
        <div>
          <div className="micro-label mb-1 flex items-center gap-2">
            <FileSearch size={12} />
            Finalized claim record
          </div>
          <h3 className="font-display text-[16px] font-semibold text-text-primary">Evidence verdict</h3>
        </div>
        <span className={`status-pill flex items-center gap-2 ${verdict.tone}`}>
          <VerdictIcon size={12} />
          {verdict.label}
        </span>
      </div>

      <div className="px-4 py-4 sm:px-5">
        <p className="text-[12px] font-medium leading-relaxed text-text-primary">{record.statement}</p>

        <div className="mt-4 space-y-2">
          {record.source_urls.map((source, index) => {
            const sourceStatus = record.source_statuses[index] || 'UNAVAILABLE';
            const statusTone = sourceStatus === 'USABLE'
              ? 'text-accent-success'
              : sourceStatus === 'CONFLICTING'
                ? 'text-accent-danger'
                : 'text-accent-warning';
            return (
              <div key={source} className="grid gap-1 border-b border-border-subtle pb-2 last:border-b-0 last:pb-0 sm:grid-cols-[minmax(0,1fr)_110px] sm:items-center">
                <a
                  href={source}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex min-w-0 items-center gap-2 break-all text-[10px] text-text-secondary hover:text-accent-cyan"
                >
                  <span className="font-mono text-text-muted">S{index + 1}</span>
                  <span className="min-w-0 flex-1">{source}</span>
                  <ExternalLink size={11} className="shrink-0" />
                </a>
                <span className={`font-mono text-[9px] font-bold uppercase sm:text-right ${statusTone}`}>
                  {sourceStatus}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {record.material_facts.length > 0 && (
        <div className="border-t border-border-default px-4 py-4 sm:px-5">
          <div className="micro-label mb-2">Material facts</div>
          <ol className="space-y-2">
            {record.material_facts.map((fact, index) => (
              <li key={`${fact}-${index}`} className="grid grid-cols-[20px_minmax(0,1fr)] gap-2 text-[11px] leading-relaxed text-text-secondary">
                <span className="font-mono text-accent-cyan">{String(index + 1).padStart(2, '0')}</span>
                <span>{fact}</span>
              </li>
            ))}
          </ol>
        </div>
      )}

      {(record.rationale || record.failure_reason) && (
        <div className="grid border-t border-border-default sm:grid-cols-2 sm:divide-x sm:divide-border-default">
          <div className="px-4 py-4 sm:px-5">
            <div className="micro-label mb-2">Rationale</div>
            <p className="text-[11px] leading-relaxed text-text-secondary">
              {record.rationale || 'No rationale was returned.'}
            </p>
          </div>
          <div className="border-t border-border-default px-4 py-4 sm:border-t-0 sm:px-5">
            <div className="micro-label mb-2">Failure reason</div>
            <p className={`font-mono text-[10px] leading-relaxed ${record.failure_reason ? 'text-accent-warning' : 'text-text-muted'}`}>
              {record.failure_reason || 'None'}
            </p>
          </div>
        </div>
      )}

      <div className="flex flex-wrap gap-2 border-t border-border-default px-4 py-3 sm:px-5">
        {!record.evaluated && (
          <button
            type="button"
            onClick={onEvaluate}
            disabled={isBusy}
            className="primary-action flex items-center gap-2 rounded-[7px] px-3 py-2 font-mono text-[10px] font-bold disabled:opacity-50"
          >
            {isBusy ? <Loader2 size={12} className="animate-spin" /> : <Scale size={12} />}
            Evaluate evidence
          </button>
        )}
        <button
          type="button"
          onClick={onRefresh}
          disabled={isBusy}
          className="control-button flex items-center gap-2 rounded-[7px] px-3 py-2 font-mono text-[10px] font-bold disabled:opacity-50"
        >
          <RefreshCw size={12} className={isBusy ? 'animate-spin' : ''} />
          Refresh record
        </button>
      </div>
    </section>
  );
}
