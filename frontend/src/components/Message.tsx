import React, { useState } from 'react';
import { MessageData } from '../lib/api';
import IntentCard from './IntentCard';
import SimulationCard from './SimulationCard';
import ConfirmationButtons from './ConfirmationButtons';
import DeployContractPanel from './DeployContractPanel';
import { WorkflowPanel } from './WorkflowPanel';
import NotaryBlueprintPanel from './NotaryBlueprintPanel';
import NotaryRecordPanel from './NotaryRecordPanel';
import { Bot, UserRound, Check, Loader2, Copy, AlertCircle, RefreshCw, Download, Rocket, ExternalLink, ShieldAlert } from 'lucide-react';
import { motion } from 'framer-motion';

interface MessageProps {
  msg: MessageData;
  onConfirm: (id: string) => void;
  onCancel: (id: string) => void;
  onUpdateIntent: (id: string, patch: Partial<NonNullable<MessageData['intent']>>) => void;
  onWorkflowAction: (id: string, action: string, data?: unknown) => void;
  onNotaryAction: (id: string, action: 'submit_claim' | 'evaluate_claim' | 'refresh') => void;
  onRunCommand?: (command: string) => void;
  walletAddress?: string;
}

export default function Message({ msg, onConfirm, onCancel, onUpdateIntent, onWorkflowAction, onNotaryAction, onRunCommand, walletAddress }: MessageProps) {
  const isUser = msg.role === 'user';
  const [copied, setCopied] = useState(false);
  const [copiedAddress, setCopiedAddress] = useState<string | null>(null);
  const [copiedCode, setCopiedCode] = useState(false);
  const isRealTxHash = Boolean(msg.txHash && /^0x[a-fA-F0-9]{64}$/.test(msg.txHash));
  const configuredTxExplorerBase = process.env.NEXT_PUBLIC_EXPLORER_TX_URL;
  const txExplorerBase = configuredTxExplorerBase || 'https://explorer-studio.genlayer.com/tx/';
  const txExplorerUrl = isRealTxHash ? `${txExplorerBase}${msg.txHash}` : null;
  const hasConsensusLifecycle = Boolean(
    msg.consensusTxId
    && ['submitted', 'finalized', 'success', 'error'].includes(msg.status || '')
  );
  const showTransactionCard = Boolean(
    hasConsensusLifecycle
    || (msg.txHash && ['submitted', 'success', 'error'].includes(msg.status || ''))
  );
  const transactionCardTone = msg.status === 'success'
    ? 'text-accent-success'
    : msg.status === 'error'
      ? 'border-accent-danger/70 bg-accent-danger/10 text-accent-danger'
      : msg.status === 'finalized'
        ? 'border-accent-warning/70 bg-accent-warning/10 text-accent-warning'
        : 'text-accent-primary';
  const consensusPillTone = msg.status === 'success'
    ? 'border-accent-success/45 bg-accent-success/5 text-accent-success'
    : msg.status === 'error'
      ? 'border-accent-danger/45 bg-accent-danger/5 text-accent-danger'
      : msg.status === 'finalized'
        ? 'border-accent-warning/45 bg-accent-warning/5 text-accent-warning'
        : 'border-accent-primary/45 bg-accent-primary/5 text-accent-primary';
  const hasVerifiedExecutionSuccess = (
    msg.status === 'success'
    && (
      msg.executionStatus === 'FINISHED_WITH_RETURN'
      || !msg.consensusTxId
    )
  );

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

  const handleRetry = () => {
    const operation = msg.intent?.notary_operation;
    if (operation === 'submit_claim' || operation === 'evaluate_claim') {
      onNotaryAction(msg.id, operation);
      return;
    }
    onConfirm(msg.id);
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
              {msg.generatedContract.sourceHash ? (
                <div className="mt-4 grid gap-2 rounded-[8px] border border-border-subtle bg-bg-base/55 p-3 font-mono text-[9px] text-text-secondary sm:grid-cols-[120px_minmax(0,1fr)]">
                  <span className="uppercase text-text-muted">Source SHA-256</span>
                  <span className="break-all text-right text-text-primary">{msg.generatedContract.sourceHash}</span>
                  <span className="uppercase text-text-muted">GenVM runtime</span>
                  <span className="break-all text-right">{msg.generatedContract.pyGenlayerDependency}</span>
                  <span className="uppercase text-text-muted">Validator</span>
                  <span className="break-all text-right">{msg.generatedContract.validatorVersion}</span>
                </div>
              ) : null}
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
                onClick={handleRetry}
                disabled={msg.status === 'executing' || msg.status === 'submitted' || msg.status === 'finalized' || msg.status === 'success'}
                className="primary-action flex items-center gap-2 rounded-[8px] px-3 py-2 font-mono text-[10px] font-bold disabled:opacity-50"
              >
                <Rocket size={12} />
                Deploy
              </button>
            </div>
          </div>
        )}

        {!isUser && msg.notaryBlueprint && (
          <div className="mt-2 w-full">
            <NotaryBlueprintPanel
              artifact={msg.notaryBlueprint}
              contractAddress={msg.contractAddress}
              operation={msg.intent?.notary_operation}
              status={msg.status}
              record={msg.notaryRecord}
              onDeploy={() => onConfirm(msg.id)}
              onSubmit={() => onNotaryAction(msg.id, 'submit_claim')}
              onRefresh={() => onNotaryAction(msg.id, 'refresh')}
            />
          </div>
        )}

        {!isUser && msg.notaryRecord && (
          <div className="w-full">
            <NotaryRecordPanel
              record={msg.notaryRecord}
              isBusy={msg.status === 'executing' || msg.status === 'submitted' || msg.status === 'finalized'}
              onEvaluate={() => onNotaryAction(msg.id, 'evaluate_claim')}
              onRefresh={() => onNotaryAction(msg.id, 'refresh')}
            />
          </div>
        )}

        {!isUser && msg.intent && !msg.notaryBlueprint && (
          <div className="w-full mt-2">
            <IntentCard intent={msg.intent} />
          </div>
        )}

        {!isUser && msg.simulation && (
          <div className="w-full">
            <SimulationCard simulation={msg.simulation} />
          </div>
        )}

        {!isUser && msg.intent?.action === 'deploy_contract' && !msg.notaryBlueprint && (
          <div className="w-full">
            <DeployContractPanel
              intent={msg.intent}
              txHash={msg.txHash}
              consensusTxId={msg.consensusTxId}
              consensusStatus={msg.consensusStatus}
              executionStatus={msg.executionStatus}
              contractAddress={msg.contractAddress}
              derivedAddresses={msg.derivedAddresses}
              status={msg.status}
              disabled={msg.status === 'executing' || msg.status === 'submitted' || msg.status === 'finalized' || msg.status === 'success'}
              onChange={(patch) => onUpdateIntent(msg.id, patch)}
            />
          </div>
        )}

        {!isUser
          && msg.workflowConfig
          && hasVerifiedExecutionSuccess
          && msg.contractAddress
          && (
          <div className="w-full">
            <WorkflowPanel
              config={msg.workflowConfig}
              state={msg.workflowState}
              contractAddress={msg.contractAddress}
              deploymentTxHash={msg.txHash}
              walletAddress={walletAddress}
              onAction={(action, data) => onWorkflowAction(msg.id, action, data)}
            />
          </div>
        )}

        {!isUser && msg.status === 'awaiting_confirmation' && msg.intent && !msg.notaryBlueprint && (
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
            {msg.intent?.action === 'check_balance'
              ? 'Reading wallet balance'
              : 'Waiting for wallet confirmation'}
          </div>
        )}

        {!isUser && msg.contractReview && (
          <div className="data-card mt-3 w-full p-3 font-mono text-[11px]">
            <div className="mb-2 flex items-center justify-between gap-2 font-bold uppercase tracking-[0.08em]">
              <span>Automated contract preflight</span>
              <span className="status-pill border-current/30 bg-black/10">
                {msg.contractReview.verdict.replaceAll('_', ' ')}
              </span>
            </div>
            <div className="space-y-1 opacity-85">
              <div>{`Contracts: ${msg.contractReview.structural.contractNames.join(', ') || 'none detected'}`}</div>
              <div>{`Public methods: ${msg.contractReview.structural.publicMethods.length}`}</div>
              <div>{`GenLayer judgment: ${msg.contractReview.genlayer.requiredForBehavior ? 'detected' : 'not detected'}`}</div>
              <div>{`Financial custody: ${msg.contractReview.safety.financialCustody ? 'detected' : 'not detected'}`}</div>
            </div>
            {(msg.contractReview.blockingErrors.length > 0 || msg.contractReview.warnings.length > 0) && (
              <div className="mt-2 space-y-1 border-t border-current/20 pt-2">
                {[...msg.contractReview.blockingErrors, ...msg.contractReview.warnings].slice(0, 8).map((finding) => (
                  <div key={finding} className="text-accent-warning">{finding}</div>
                ))}
              </div>
            )}
          </div>
        )}

        {!isUser && showTransactionCard && (
          <div className={`data-card mt-3 flex w-full flex-col gap-2 p-3 font-mono text-[11px] ${transactionCardTone}`}>
            <div className="flex items-center gap-2 font-bold uppercase tracking-[0.08em]">
              {msg.status === 'success' ? (
                <Check size={14} />
              ) : msg.status === 'error' ? (
                <AlertCircle size={14} />
              ) : msg.status === 'finalized' ? (
                <ShieldAlert size={14} />
              ) : (
                <Loader2 size={14} className="animate-spin" />
              )}
              {msg.status === 'success'
                ? (msg.consensusTxId ? 'Execution successful' : 'Transaction confirmed')
                : msg.status === 'error'
                  ? (
                      msg.executionStatus === 'FINISHED_WITH_ERROR'
                        ? 'Execution failed'
                        : 'Consensus ended'
                    )
                  : msg.status === 'finalized'
                    ? 'Execution result pending'
                    : 'Consensus in progress'}
            </div>
            {msg.evmStatus && (
              <div className="flex flex-wrap items-center gap-2 pl-6 text-[10px] uppercase tracking-[0.08em]">
                <span className="opacity-70">EVM</span>
                <span className="status-pill border-current/30 bg-black/10">
                  {msg.evmStatus.replaceAll('_', ' ')}
                </span>
              </div>
            )}
            {msg.consensusStatus && (
              <div className="flex flex-wrap items-center gap-2 pl-6 text-[10px] uppercase tracking-[0.08em]">
                <span className="opacity-70">GenLayer</span>
                <span className={`status-pill ${consensusPillTone}`}>
                  {msg.consensusStatus.replaceAll('_', ' ')}
                </span>
                {msg.consensusAppealable && (
                  <span className="status-pill border-accent-warning/45 bg-accent-warning/5 text-accent-warning">
                    appeal window open
                  </span>
                )}
                {msg.consensusStatus === 'UNDETERMINED' && (
                  <ShieldAlert size={13} className="text-accent-warning" aria-label="Consensus undetermined" />
                )}
              </div>
            )}
            {msg.executionStatus && msg.executionStatus !== 'NOT_VOTED' && (
              <div className="flex flex-wrap items-center gap-2 pl-6 text-[10px] uppercase tracking-[0.08em]">
                <span className="opacity-70">GenVM</span>
                <span className="status-pill border-current/30 bg-black/10">
                  {msg.executionStatus.replaceAll('_', ' ')}
                </span>
              </div>
            )}
            {msg.txHash && (
              <div className="flex items-center justify-between gap-2 break-all pl-6 opacity-85">
                <span className="min-w-0 break-all">{isRealTxHash ? `HASH: ${msg.txHash}` : msg.txHash}</span>
                <div className="flex shrink-0 items-center gap-1">
                  <button
                    type="button"
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
            )}
            {msg.consensusTxId && (
              <div className="opacity-80 pl-6 break-all">
                <span>{`CONSENSUS_TX: ${msg.consensusTxId}`}</span>
              </div>
            )}
            {msg.intentHash && (
              <div className="opacity-80 pl-6 break-all">
                <span>{`INTENT_HASH: ${msg.intentHash}`}</span>
              </div>
            )}
            {msg.transactionDiagnostics && (
              <div className="ml-6 rounded-[6px] border border-current/25 bg-black/10 p-2 text-[10px] normal-case">
                <div className="mb-1 font-bold uppercase tracking-[0.08em]">Transaction diagnostics</div>
                {msg.transactionDiagnostics.code && (
                  <div>{`Code: ${msg.transactionDiagnostics.code}`}</div>
                )}
                {msg.preparedTransactionId && (
                  <div className="break-all">{`Prepared transaction: ${msg.preparedTransactionId}`}</div>
                )}
                {msg.transactionDiagnostics.field && (
                  <div>{`Mismatch field: ${msg.transactionDiagnostics.field}`}</div>
                )}
                {msg.transactionDiagnostics.expected !== undefined
                  && msg.transactionDiagnostics.expected !== null
                  && (
                  <div className="break-all">{`Expected: ${msg.transactionDiagnostics.expected}`}</div>
                )}
                {msg.transactionDiagnostics.actual !== undefined
                  && msg.transactionDiagnostics.actual !== null
                  && (
                  <div className="break-all">{`Submitted: ${msg.transactionDiagnostics.actual}`}</div>
                )}
                {msg.transactionDiagnostics.retriable && (
                  <div className="mt-1 font-bold">This confirmation can be retried safely.</div>
                )}
              </div>
            )}
            {hasVerifiedExecutionSuccess
              && msg.contractAddress
              && (
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
            {hasVerifiedExecutionSuccess
              && msg.derivedAddresses
              && msg.derivedAddresses.length > 0
              && (
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
            {msg.status === 'error' && msg.intent && msg.zeroRoundNoMajority && (
              <div className="mt-2 rounded-[6px] border border-accent-warning/50 bg-accent-warning/10 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.06em] text-accent-warning">
                Wallet retry blocked until the Studionet health gate clears.
              </div>
            )}
            {msg.status === 'error' && msg.intent && !msg.zeroRoundNoMajority && (
              <button
                type="button"
                onClick={handleRetry}
                className="control-button mt-2 flex items-center justify-center gap-2 rounded-[6px] border-accent-danger px-3 py-2 font-mono text-[10px] uppercase tracking-[0.08em] text-accent-danger"
              >
                <RefreshCw size={12} />
                Retry transaction
              </button>
            )}
          </div>
        )}

        {!isUser && msg.status === 'error' && !msg.consensusTxId && !msg.txHash && (
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
                onClick={handleRetry}
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
