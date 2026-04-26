import React from 'react';
import { Intent } from '../lib/api';
import { TerminalSquare, Send, Wallet, FileCode } from 'lucide-react';
import RiskIndicator from './RiskIndicator';

export default function IntentCard({ intent }: { intent: Intent }) {
  if (intent.action === 'unknown') return null;

  const getActionIcon = () => {
    switch (intent.action) {
      case 'transfer':
        return Send;
      case 'check_balance':
        return Wallet;
      case 'create_contract':
        return FileCode;
      default:
        return TerminalSquare;
    }
  };

  const getActionLabel = () => {
    switch (intent.action) {
      case 'transfer':
        return 'TRANSFER';
      case 'check_balance':
        return 'BALANCE_CHECK';
      case 'create_contract':
        return 'CONTRACT_CREATION';
      default:
        return intent.action.toUpperCase();
    }
  };

  const ActionIcon = getActionIcon();

  return (
    <div className="mt-2 p-4 bg-black text-text-primary ticket-border font-mono text-[11px] uppercase tracking-wider">
      <div className="flex items-center justify-between mb-3 pb-2 border-b border-border-strong">
        <div className="flex items-center gap-2 text-accent-primary">
          <ActionIcon size={14} />
          <span className="font-bold">PARSED_INTENT // {getActionLabel()}</span>
        </div>
        <RiskIndicator intent={intent} />
      </div>
      
      <div className="flex flex-col gap-2">
        {intent.action === 'transfer' && (
          <>
            <div className="flex justify-between border-b border-border-subtle border-dotted pb-1">
              <span className="text-text-muted">RECIPIENT:</span>
              <span className="text-accent-success font-bold">{intent.recipient || 'UNKNOWN'}</span>
            </div>
            <div className="flex justify-between border-b border-border-subtle border-dotted pb-1">
              <span className="text-text-muted">AMOUNT:</span>
              <span className="text-accent-primary font-bold">{intent.amount} {intent.token || 'GEN'}</span>
            </div>
          </>
        )}
        
        {intent.action === 'check_balance' && (
          <div className="flex justify-between border-b border-border-subtle border-dotted pb-1">
            <span className="text-text-muted">TARGET:</span>
            <span className="text-accent-primary">SELF</span>
          </div>
        )}

        {intent.action !== 'transfer' && intent.action !== 'check_balance' && (
          <pre className="text-text-secondary overflow-x-auto">
            {JSON.stringify(intent, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}
