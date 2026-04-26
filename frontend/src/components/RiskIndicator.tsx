import React from 'react';
import { AlertTriangle, AlertCircle, CheckCircle2 } from 'lucide-react';
import { Intent } from '../lib/api';

interface RiskIndicatorProps {
  intent: Intent;
}

export default function RiskIndicator({ intent }: RiskIndicatorProps) {
  const calculateRisk = () => {
    if (intent.action === 'check_balance') {
      return { level: 'safe', textColor: 'text-accent-success', bgColor: 'bg-accent-success/10', borderColor: 'border-accent-success', icon: CheckCircle2, text: 'SAFE' };
    }

    if (intent.action === 'transfer') {
      const amount = intent.amount || 0;
      
      // High risk: > 1000 tokens
      if (amount > 1000) {
        return { level: 'high', textColor: 'text-accent-danger', bgColor: 'bg-accent-danger/10', borderColor: 'border-accent-danger', icon: AlertTriangle, text: 'HIGH_RISK' };
      }
      
      // Medium risk: 100-1000 tokens
      if (amount >= 100) {
        return { level: 'medium', textColor: 'text-accent-warning', bgColor: 'bg-accent-warning/10', borderColor: 'border-accent-warning', icon: AlertCircle, text: 'MEDIUM_RISK' };
      }
      
      // Low risk: < 100 tokens
      return { level: 'safe', textColor: 'text-accent-success', bgColor: 'bg-accent-success/10', borderColor: 'border-accent-success', icon: CheckCircle2, text: 'LOW_RISK' };
    }

    // Default for other actions
    return { level: 'medium', textColor: 'text-accent-warning', bgColor: 'bg-accent-warning/10', borderColor: 'border-accent-warning', icon: AlertCircle, text: 'REVIEW_REQUIRED' };
  };

  const risk = calculateRisk();
  const Icon = risk.icon;

  return (
    <div className={`flex items-center gap-2 px-3 py-2 border ${risk.borderColor} ${risk.bgColor} rounded text-[11px] font-mono uppercase tracking-widest font-bold`}>
      <Icon size={14} className={risk.textColor} />
      <span className={risk.textColor}>{risk.text}</span>
    </div>
  );
}
