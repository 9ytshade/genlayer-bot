import React, { useState } from 'react';
import { MessageData } from '../lib/api';
import IntentCard from './IntentCard';
import SimulationCard from './SimulationCard';
import ConfirmationButtons from './ConfirmationButtons';
import DeployContractPanel from './DeployContractPanel';
import { Bot, UserRound, Check, Loader2, Copy, AlertCircle, RefreshCw } from 'lucide-react';
import { motion } from 'framer-motion';

interface MessageProps {
  msg: MessageData;
  onConfirm: (id: string) => void;
  onCancel: (id: string) => void;
  onUpdateIntent: (id: string, patch: Partial<NonNullable<MessageData['intent']>>) => void;
  onRunCommand?: (command: string) => void;
}

export default function Message({ msg, onConfirm, onCancel, onUpdateIntent, onRunCommand }: MessageProps) {
  const isUser = msg.role === 'user';
  const [copied, setCopied] = useState(false);
  const [copiedAddress, setCopiedAddress] = useState<string | null>(null);
  const isRealTxHash = Boolean(msg.txHash && /^0x[a-fA-F0-9]{64}$/.test(msg.txHash));
  const txExplorerBase = process.env.NEXT_PUBLIC_EXPLORER_TX_URL;
  const txExplorerUrl = isRealTxHash && txExplorerBase ? `${txExplorerBase}${msg.txHash}` : null;

  const handleCopyHash = (hash: string) => {
    navigator.clipboard.writeText(hash);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleCopyAddress = (address: string) => {
    navigator.clipboard.writeText(address);
    setCopiedAddress(address);
    setTimeout(() => setCopiedAddress(null), 2000);
  };

  const formatTime = (id: string) => {
    const time = new Date(parseInt(id));
    return time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 15, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
      className={`flex w-full max-w-3xl gap-4 px-1 sm:gap-5 sm:px-2 ${isUser ? 'ml-auto flex-row-reverse' : ''}`}
    >
      <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full border ${isUser ? 'border-accent-primary bg-accent-primary text-black' : 'border-border-strong bg-bg-elevated text-accent-cyan'}`}>
        {isUser ? <UserRound size={17} /> : <Bot size={17} />}
      </div>
      
      <div className={`flex max-w-[88%] flex-col gap-2 sm:max-w-[85%] ${isUser ? 'items-end' : 'items-start'}`}>
        <div className="flex items-center gap-2 px-1">
          <span className="micro-label">
            {isUser ? 'You' : 'Agent'}
          </span>
          <span className="font-mono text-[9px] text-text-muted opacity-60">{formatTime(msg.id)}</span>
        </div>
        
        <div className={`px-6 py-[1.125rem] sm:px-7 sm:py-5 ${isUser ? 'message-card-user' : 'message-card text-text-primary'}`}>
          <p className="whitespace-pre-wrap break-words text-[14px] leading-relaxed">{msg.content}</p>
        </div>

        {!isUser && msg.helpCommands && msg.helpCommands.length > 0 && (
          <div className="mt-2 grid w-full gap-2 sm:grid-cols-2">
            {msg.helpCommands.map((command) => (
              <button
                key={command.label}
                type="button"
                onClick={() => onRunCommand?.(command.command)}
                className="control-button group rounded-[8px] px-3 py-3 text-left"
              >
                <div className="font-mono text-[11px] font-bold uppercase tracking-[0.08em] text-accent-primary group-hover:text-white">
                  {command.label}
                </div>
                <div className="mt-1 text-[10px] leading-relaxed text-text-muted">
                  {command.description}
                </div>
              </button>
            ))}
          </div>
        )}

        {!isUser && msg.intent && (
          <div className="w-full mt-2">
            <IntentCard intent={msg.intent} />
          </div>
        )}

        {!isUser && msg.simulation && (
          <div className="w-full">
            <SimulationCard simulation={msg.simulation} />
          </div>
        )}

        {!isUser && msg.intent?.action === 'deploy_contract' && (
          <div className="w-full">
            <DeployContractPanel
              intent={msg.intent}
              disabled={msg.status === 'executing' || msg.status === 'success'}
              onChange={(patch) => onUpdateIntent(msg.id, patch)}
            />
          </div>
        )}

        {!isUser && msg.status === 'awaiting_confirmation' && msg.intent && (
          <div className="w-full">
            <ConfirmationButtons 
              intent={msg.intent} 
              status={msg.status} 
              onConfirm={() => onConfirm(msg.id)} 
              onCancel={() => onCancel(msg.id)} 
            />
          </div>
        )}

        {!isUser && msg.status === 'executing' && (
          <div className="mt-3 flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.08em] text-accent-primary">
            <Loader2 size={12} className="animate-spin" />
            Executing transaction
          </div>
        )}

        {!isUser && msg.status === 'success' && msg.txHash && (
          <div className="data-card mt-3 flex w-full flex-col gap-2 p-3 font-mono text-[11px] text-accent-success">
            <div className="flex items-center gap-2 font-bold uppercase tracking-[0.08em]">
              <Check size={14} />
              Transaction success
            </div>
            <div className="flex items-center justify-between gap-2 break-all pl-6 opacity-85">
              <span>{isRealTxHash ? `HASH: ${msg.txHash}` : msg.txHash}</span>
              <button
                onClick={() => handleCopyHash(msg.txHash!)}
                className="control-button ml-2 rounded-[6px] p-1"
                title="Copy transaction hash"
              >
                <Copy size={12} className={copied ? 'text-accent-primary' : ''} />
              </button>
            </div>
            {msg.consensusTxId && (
              <div className="opacity-80 pl-6 break-all">
                <span>{`CONSENSUS_TX: ${msg.consensusTxId}`}</span>
              </div>
            )}
            {msg.contractAddress && (
              <div className="pl-6">
                <div className="mb-1 uppercase tracking-[0.08em]">Contract address</div>
                <div className="flex items-center justify-between gap-2 break-all">
                  <span>{msg.contractAddress}</span>
                  <button
                    onClick={() => handleCopyAddress(msg.contractAddress!)}
                    className="control-button ml-2 rounded-[6px] p-1"
                    title="Copy contract address"
                  >
                    <Copy size={12} className={copiedAddress === msg.contractAddress ? 'text-accent-primary' : ''} />
                  </button>
                </div>
              </div>
            )}
            {msg.derivedAddresses && msg.derivedAddresses.length > 0 && (
              <div className="pl-6">
                <div className="mb-1 uppercase tracking-[0.08em]">Generated addresses</div>
                <div className="mb-2 text-[11px] normal-case text-text-muted">
                  Use these addresses as parameters when deploying dependent contracts.
                </div>
                <div className="flex flex-col gap-2">
                  {msg.derivedAddresses.map((address) => (
                    <div key={address} className="flex items-center justify-between gap-2 break-all">
                      <span>{address}</span>
                      <button
                        onClick={() => handleCopyAddress(address)}
                        className="control-button ml-2 rounded-[6px] p-1"
                        title="Copy derived address"
                      >
                        <Copy size={12} className={copiedAddress === address ? 'text-accent-primary' : ''} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {txExplorerUrl && (
              <a
                href={txExplorerUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="pl-6 text-[10px] uppercase tracking-[0.08em] text-accent-success transition-colors hover:text-white"
              >
                View on explorer
              </a>
            )}
          </div>
        )}

        {!isUser && msg.status === 'error' && (
          <div className="data-card mt-3 flex w-full flex-col gap-2 border-accent-danger/70 bg-accent-danger/10 p-3 font-mono text-[11px] text-accent-danger">
            <div className="flex items-center gap-2 font-bold uppercase tracking-[0.08em]">
              <AlertCircle size={14} />
              Error
            </div>
            <div className="pl-6 normal-case opacity-85">
              {msg.content}
            </div>
            {msg.intent ? (
              <button
                onClick={() => onConfirm(msg.id)}
                className="control-button mt-2 flex items-center justify-center gap-2 rounded-[6px] border-accent-danger px-3 py-2 font-mono text-[10px] uppercase tracking-[0.08em] text-accent-danger"
              >
                <RefreshCw size={12} />
                Retry execution
              </button>
            ) : null}
          </div>
        )}
      </div>
    </motion.div>
  );
}
