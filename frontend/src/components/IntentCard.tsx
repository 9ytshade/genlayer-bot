import React from 'react';
import { Intent } from '../lib/api';
import { TerminalSquare, Send, Wallet, FileCode, Sparkles, ClipboardCheck, Repeat, Handshake, Trophy, Workflow, Bug, ShieldAlert } from 'lucide-react';
import RiskIndicator from './RiskIndicator';

const ACTION_ICON = {
  transfer: Send,
  check_balance: Wallet,
  deploy_contract: FileCode,
  generate_contract: Sparkles,
  contract_review: ClipboardCheck,
  contract_call: Workflow,
  conditional_payment: Send,
  escrow: Handshake,
  subscription: Repeat,
  bounty: Trophy,
  debug_trace: Bug,
  appeal_transaction: ShieldAlert,
  unknown: TerminalSquare,
} as const;

export default function IntentCard({ intent }: { intent: Intent }) {
  if (intent.action === 'unknown') return null;

  const getActionLabel = () => {
    switch (intent.action) {
      case 'transfer':
        return 'TRANSFER';
      case 'check_balance':
        return 'BALANCE_CHECK';
      case 'deploy_contract':
        return 'CONTRACT_CREATION';
      case 'generate_contract':
        return 'CONTRACT_GENERATION';
      case 'contract_review':
        return 'CONTRACT_REVIEW';
      case 'contract_call':
        return 'CONTRACT_CALL';
      case 'conditional_payment':
        return 'CONDITIONAL_PAYMENT';
      case 'escrow':
        return 'ESCROW_WORKFLOW';
      case 'subscription':
        return 'SUBSCRIPTION_WORKFLOW';
      case 'bounty':
        return 'BOUNTY_WORKFLOW';
      default:
        return intent.action.toUpperCase();
    }
  };

  const ActionIcon = ACTION_ICON[intent.action] ?? TerminalSquare;

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

        {intent.action === 'contract_call' && (
          <div className="flex flex-col gap-2">
            <div className="flex justify-between border-b border-border-subtle border-dotted pb-1">
              <span className="text-text-muted">CONTRACT:</span>
              <span className="text-accent-primary font-bold">{intent.contract_address || 'UNKNOWN'}</span>
            </div>
            <div className="flex justify-between border-b border-border-subtle border-dotted pb-1">
              <span className="text-text-muted">METHOD:</span>
              <span className="text-accent-success font-bold">{intent.method || 'UNKNOWN'}</span>
            </div>
            <div className="flex justify-between border-b border-border-subtle border-dotted pb-1">
              <span className="text-text-muted">ARGS:</span>
              <span className="text-text-secondary">{JSON.stringify(intent.args || [])}</span>
            </div>
          </div>
        )}

        {intent.action !== 'transfer' && intent.action !== 'check_balance' && intent.action !== 'contract_call' && (
          <div className="flex flex-col gap-2">
            <div className="flex justify-between border-b border-border-subtle border-dotted pb-1">
              <span className="text-text-muted">CONTRACT:</span>
              <span className="text-accent-primary font-bold">{intent.contract_name || 'IntelligentContract'}</span>
            </div>
            <div className="flex justify-between border-b border-border-subtle border-dotted pb-1">
              <span className="text-text-muted">SOURCE:</span>
              <span className="text-accent-success font-bold">{typeof intent.source_file_name === 'string' ? intent.source_file_name : 'INLINE'}</span>
            </div>
            <div className="flex justify-between border-b border-border-subtle border-dotted pb-1">
              <span className="text-text-muted">VALUE:</span>
              <span className="text-accent-primary font-bold">{intent.deploy_value_text || intent.deploy_value || 0} GEN</span>
            </div>
            <div className="flex justify-between border-b border-border-subtle border-dotted pb-1">
              <span className="text-text-muted">ARGS:</span>
              <span className="text-text-secondary">{typeof intent.constructor_args_text === 'string' ? intent.constructor_args_text : '[]'}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
