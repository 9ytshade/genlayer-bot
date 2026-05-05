import React, { useMemo } from 'react';
import { Intent } from '../lib/api';
import { Check, X, Zap } from 'lucide-react';
import RiskIndicator from './RiskIndicator';

interface ConfirmationProps {
  intent: Intent;
  status: string;
  onConfirm: () => void;
  onCancel: () => void;
}

const estimateGas = (intent: Intent): number => {
  if (intent.action === 'transfer') {
    return 21000 + (intent.amount || 0) * 10;
  }
  if (intent.action === 'check_balance') {
    return 2300;
  }
  if (intent.action === 'deploy_contract') {
    if (typeof intent.gas_limit === 'number') {
      return intent.gas_limit;
    }
    if (typeof intent.gas_limit_text === 'string' && intent.gas_limit_text.trim()) {
      return Number(intent.gas_limit_text);
    }
    return 1500000;
  }
  return 50000;
};

export default function ConfirmationButtons({ intent, status, onConfirm, onCancel }: ConfirmationProps) {
  const gasEstimate = useMemo(() => estimateGas(intent), [intent]);
  
  if (status !== 'awaiting_confirmation') return null;

  return (
    <div className="mt-4 flex flex-col gap-3">
      <div className="flex items-center justify-between p-3 bg-bg-elevated border border-border-strong rounded text-[11px] font-mono">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-text-secondary">
            <Zap size={12} className="text-accent-primary" />
            <span>GAS_ESTIMATE:</span>
            <span className="text-accent-primary font-bold">{gasEstimate} WEI</span>
          </div>
        </div>
        <RiskIndicator intent={intent} />
      </div>

      <div className="flex gap-3">
        <button
          onClick={onConfirm}
          className="flex-1 flex items-center justify-center gap-2 py-2 px-4 rounded-none bg-accent-primary hover:bg-white text-black font-mono text-[11px] font-bold uppercase tracking-widest transition-colors shadow-none border border-accent-primary"
        >
          <Check size={14} />
          [EXECUTE]
        </button>
        
        <button
          onClick={onCancel}
          className="flex items-center justify-center gap-2 py-2 px-4 rounded-none bg-black border border-border-strong hover:border-text-primary text-text-secondary hover:text-text-primary font-mono text-[11px] font-bold uppercase tracking-widest transition-colors"
        >
          <X size={14} />
          [ABORT]
        </button>
      </div>
    </div>
  );
}
