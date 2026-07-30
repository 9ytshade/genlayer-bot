import React, { useState } from 'react';
import { MessageData } from '../lib/api';
import IntentCard from './IntentCard';
import SimulationCard from './SimulationCard';
import ConfirmationButtons from './ConfirmationButtons';
import DeployContractPanel from './DeployContractPanel';
import { WorkflowPanel } from './WorkflowPanel';
import { Bot, UserRound, Check, Loader2, Copy, AlertCircle, RefreshCw, Download, Rocket, ExternalLink } from 'lucide-react';
import { motion } from 'framer-motion';

interface MessageProps {
  msg: MessageData;
  onConfirm: (id: string) => void;
  onCancel: (id: string) => void;
  onUpdateIntent: (id: string, patch: Partial<NonNullable<MessageData['intent']>>) => void;
  onWorkflowAction: (id: string, action: string, data?: unknown) => void;
  onRunCommand?: (command: string) => void;
}

export default function Message({ msg, onConfirm, onCancel, onUpdateIntent, onWorkflowAction, onRunCommand }: MessageProps) {
  const isUser = msg.role === 'user';
  const [copied, setCopied] = useState(false);
  const [copiedAddress, setCopiedAddress] = useState<string | null>(null);
  const [copiedCode, setCopiedCode] = useState(false);
  const isRealTxHash = Boolean(msg.txHash && /^0x[a-fA-F0-9]{64}$/.test(msg.txHash));
  const configuredTxExplorerBase = process.env.NEXT_PUBLIC_EXPLORER_TX_URL;
  const txExplorerBase = configuredTxExplorerBase || 'https://explorer-studio.genlayer.com/tx/';
  const txExplorerUrl = isRealTxHash ? `${txExplorerBase}${msg.txHash}` : null;

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

  const handleCopyCode = (code: string) => {
    navigator.clipboard.writeText(code);
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 2000);
  };

  const handleDownloadContract = (fileName: string, code: string) => {
    const blob = new Blob([code], { type: 'text/x-python;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
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
      className={`flex w-full gap-3 px-1 sm:gap-4 ${isUser ? 'ml-auto flex-row-reverse' : ''}`}
    >
      <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-[8px] border ${isUser ? 'border-accent-primary bg-accent-primary text-black' : 'border-border-strong bg-bg-elevated text-accent-cyan'}`}>
        {isUser ? <UserRound size={14} /> : <Bot size={14} />}
      </div>
      
      <div className={`flex max-w-[88%] flex-col gap-2 sm:max-w-[86%] ${isUser ? 'items-end' : 'items-start'}`}>
        <div className="flex items-center gap-2 px-1">
          <span className="micro-label">
            {isUser ? 'You' : 'Agent'}
          </span>
          <span className="font-mono text-[9px] text-text-muted opacity-60">{formatTime(msg.id)}</span>
        </div>
        
        <div className={`rounded-[10px] px-4 py-3 sm:px-5 ${isUser ? 'message-card-user' : 'message-card text-text-primary'}`}>
          <p className="whitespace-pre-wrap break-words text-[12px] font-medium leading-relaxed sm:text-[13px]">{msg.content}</p>
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

        {!isUser && msg.generatedContract && (
          <div className="data-card mt-3 w-full overflow-hidden rounded-[12px]">
            <div className="border-b border-border-default p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="micro-label mb-1">Generated Contract</div>
                  <h3 className="font-display text-[18px] font-semibold leading-tight text-text-primary">
                    {msg.generatedContract.contractName}
                  </h3>
                  <p className="mt-1 font-mono text-[10px] text-accent-primary">
                    {msg.generatedContract.contractType.replace(/_/g, ' ')}
                  </p>
                </div>
                <span className="status-pill border-accent-success/45 bg-accent-success/5 text-accent-success">
                  IntelligentContract
                </span>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <span className="status-pill border-accent-primary/45 bg-accent-primary/5 text-accent-primary">awaiting confirmation</span>
                <span className="status-pill border-accent-success/45 bg-accent-success/5 text-accent-success">syntax valid</span>
                <span className="status-pill border-accent-warning/45 bg-accent-warning/5 text-accent-warning">review constructor args</span>
              </div>
              <p className="mt-4 text-[12px] leading-relaxed text-text-secondary">
                {msg.generatedContract.explanation}
              </p>
            </div>
            <pre className="mx-4 mt-4 max-h-80 overflow-auto rounded-[8px] border border-border-subtle bg-bg-base p-4 font-mono text-[10px] leading-relaxed text-text-secondary sm:text-[11px]">
              {msg.generatedContract.code}
            </pre>
            <div className="flex flex-wrap gap-2 p-4">
              <button
                type="button"
                onClick={() => handleCopyCode(msg.generatedContract!.code)}
                className="control-button flex items-center gap-2 rounded-[8px] px-3 py-2 font-mono text-[10px] font-bold"
              >
                <Copy size={12} />
                {copiedCode ? 'Copied' : 'Copy code'}
              </button>
              <button
                type="button"
                onClick={() => handleDownloadContract(msg.generatedContract!.fileName, msg.generatedContract!.code)}
                className="control-button flex items-center gap-2 rounded-[8px] px-3 py-2 font-mono text-[10px] font-bold"
              >
                <Download size={12} />
                Download .py
              </button>
              <button
                type="button"
                onClick={() => onConfirm(msg.id)}
                disabled={msg.status === 'executing' || msg.status === 'success'}
                className="primary-action flex items-center gap-2 rounded-[8px] px-3 py-2 font-mono text-[10px] font-bold disabled:opacity-50"
              >
                <Rocket size={12} />
                Deploy
              </button>
            </div>
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
              txHash={msg.txHash}
              consensusTxId={msg.consensusTxId}
              contractAddress={msg.contractAddress}
              derivedAddresses={msg.derivedAddresses}
              status={msg.status}
              onChange={(patch) => onUpdateIntent(msg.id, patch)}
            />
          </div>
        )}

        {!isUser && msg.workflowConfig && (
          <div className="w-full">
            <WorkflowPanel
              config={msg.workflowConfig}
              contractAddress={msg.contractAddress}
              deploymentTxHash={msg.txHash}
              onAction={(action, data) => onWorkflowAction(msg.id, action, data)}
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
              <span className="min-w-0 break-all">{isRealTxHash ? `HASH: ${msg.txHash}` : msg.txHash}</span>
              <div className="flex shrink-0 items-center gap-1">
                <button
                  onClick={() => handleCopyHash(msg.txHash!)}
                  className="control-button rounded-[6px] p-1"
                  title="Copy transaction hash"
                >
                  <Copy size={12} className={copied ? 'text-accent-primary' : ''} />
                </button>
                {txExplorerUrl && (
                  <a
                    href={txExplorerUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="control-button flex items-center gap-1 rounded-[6px] px-2 py-1 text-[10px] text-accent-success"
                    title="View transaction in GenLayer explorer"
                  >
                    <ExternalLink size={11} />
                    Check in explorer
                  </a>
                )}
              </div>
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
