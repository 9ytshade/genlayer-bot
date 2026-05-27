import React, { useState } from 'react';
import { MessageData } from '../lib/api';
import IntentCard from './IntentCard';
import SimulationCard from './SimulationCard';
import ConfirmationButtons from './ConfirmationButtons';
import DeployContractPanel from './DeployContractPanel';
import { Terminal, User, Check, Loader2, Copy, AlertCircle, RefreshCw } from 'lucide-react';
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
      transition={{ type: "spring", stiffness: 400, damping: 25 }}
      className={`flex gap-4 max-w-3xl ${isUser ? 'ml-auto flex-row-reverse' : ''}`}
    >
      <div className={`shrink-0 w-8 h-8 flex items-center justify-center border ${isUser ? 'bg-accent-primary text-black border-accent-primary' : 'bg-black border-border-strong text-text-secondary'}`}>
        {isUser ? <User size={14} /> : <Terminal size={14} />}
      </div>
      
      <div className={`flex flex-col gap-1 max-w-[85%] ${isUser ? 'items-end' : 'items-start'}`}>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-text-muted font-mono uppercase tracking-widest">
            {isUser ? 'USER_INPUT' : 'SYS_RESPONSE'}
          </span>
          <span className="text-[9px] text-text-muted font-mono opacity-60">{formatTime(msg.id)}</span>
        </div>
        
        <div className={`px-6 py-4 border ${isUser ? 'bg-accent-primary text-black border-accent-primary rounded-none shadow-[0_0_15px_rgba(255,176,0,0.15)]' : 'bg-bg-elevated border-border-strong text-text-primary rounded-none'}`}>
          <p className="text-[14px] leading-relaxed whitespace-pre-wrap font-sans">{msg.content}</p>
        </div>

        {!isUser && msg.helpCommands && msg.helpCommands.length > 0 && (
          <div className="grid w-full gap-2 mt-2 sm:grid-cols-2">
            {msg.helpCommands.map((command) => (
              <button
                key={command.label}
                type="button"
                onClick={() => onRunCommand?.(command.command)}
                className="border border-border-strong bg-black px-3 py-3 text-left transition-colors hover:border-accent-primary hover:bg-accent-primary/10 group"
              >
                <div className="text-[11px] font-mono font-bold uppercase tracking-widest text-accent-primary group-hover:text-white">
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
          <div className="flex items-center gap-2 mt-3 text-[11px] font-mono text-accent-primary uppercase tracking-widest animate-pulse">
            <Loader2 size={12} className="animate-spin" />
            Executing_Transaction...
          </div>
        )}

        {!isUser && msg.status === 'success' && msg.txHash && (
          <div className="mt-3 p-3 bg-accent-success/10 border border-accent-success text-accent-success text-[11px] font-mono flex flex-col gap-2 w-full ticket-border">
            <div className="flex items-center gap-2 uppercase tracking-widest font-bold">
              <Check size={14} />
              Tx_Success
            </div>
            <div className="opacity-80 pl-6 break-all flex items-center justify-between gap-2">
              <span>{isRealTxHash ? `HASH: ${msg.txHash}` : msg.txHash}</span>
              <button
                onClick={() => handleCopyHash(msg.txHash!)}
                className="ml-2 p-1 hover:bg-accent-success/20 rounded transition-colors"
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
                <div className="mb-1 uppercase tracking-widest">CONTRACT_ADDRESS</div>
                <div className="flex items-center justify-between gap-2 break-all">
                  <span>{msg.contractAddress}</span>
                  <button
                    onClick={() => handleCopyAddress(msg.contractAddress!)}
                    className="ml-2 p-1 hover:bg-accent-success/20 rounded transition-colors"
                    title="Copy contract address"
                  >
                    <Copy size={12} className={copiedAddress === msg.contractAddress ? 'text-accent-primary' : ''} />
                  </button>
                </div>
              </div>
            )}
            {msg.derivedAddresses && msg.derivedAddresses.length > 0 && (
              <div className="pl-6">
                <div className="mb-1 uppercase tracking-widest">GENERATED_ADDRESSES</div>
                <div className="mb-2 text-[11px] normal-case tracking-normal text-text-muted">
                  Use these addresses as parameters when deploying dependent contracts.
                </div>
                <div className="flex flex-col gap-2">
                  {msg.derivedAddresses.map((address) => (
                    <div key={address} className="flex items-center justify-between gap-2 break-all">
                      <span>{address}</span>
                      <button
                        onClick={() => handleCopyAddress(address)}
                        className="ml-2 p-1 hover:bg-accent-success/20 rounded transition-colors"
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
                className="pl-6 text-[10px] uppercase tracking-widest text-accent-success hover:text-white transition-colors"
              >
                [VIEW_ON_EXPLORER]
              </a>
            )}
          </div>
        )}

        {!isUser && msg.status === 'error' && (
          <div className="mt-3 p-3 bg-accent-danger/10 border border-accent-danger text-accent-danger text-[11px] font-mono flex flex-col gap-2 w-full ticket-border">
            <div className="flex items-center gap-2 uppercase tracking-widest font-bold">
              <AlertCircle size={14} />
              Error
            </div>
            <div className="opacity-80 pl-6 normal-case tracking-normal">
              {msg.content}
            </div>
            {msg.intent ? (
              <button
                onClick={() => onConfirm(msg.id)}
                className="mt-2 flex items-center justify-center gap-2 py-2 px-3 bg-accent-danger/20 hover:bg-accent-danger/30 border border-accent-danger text-accent-danger font-mono text-[10px] uppercase tracking-widest transition-colors"
              >
                <RefreshCw size={12} />
                [RETRY_EXECUTION]
              </button>
            ) : null}
          </div>
        )}
      </div>
    </motion.div>
  );
}
