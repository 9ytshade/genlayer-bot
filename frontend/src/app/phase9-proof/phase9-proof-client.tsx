'use client';

import { useMemo, useState, type FormEvent } from 'react';
import {
  CheckCircle2,
  CircleDot,
  ExternalLink,
  FileCheck2,
  Link2,
  Radio,
  RefreshCw,
  Send,
  ShieldCheck,
  Wallet,
} from 'lucide-react';
import { formatEther } from 'viem';
import { NETWORK_CONFIG } from '@/config';
import { useWallet } from '@/context/WalletContext';
import {
  buildPhase9ConditionalCallTx,
  buildPhase9ConditionalDeployTx,
  confirmAction,
  getConsensusStatus,
  getWorkflowState,
  reviewPhase9ConditionalContract,
  type ConsensusStatusResult,
  type DeployTxData,
  type Intent,
  type WorkflowContractArtifact,
  type WorkflowState,
} from '@/lib/api';
import type { ConditionalPaymentConfig } from '@/types/WorkflowConfig';

const NETWORK = 'bradbury' as const;
const AMOUNT = '0.01';
const DEFAULT_CONDITION = 'The provided evidence is an official GenLayer documentation page.';
const DEFAULT_SOURCE = 'https://docs.genlayer.com/';

type ProofOperation =
  | 'deploy'
  | 'fund'
  | 'request_evaluation'
  | 'evaluate'
  | 'settle_release'
  | 'settle_refund'
  | 'second_settlement';

interface PendingTransaction {
  operation: ProofOperation;
  label: string;
  tx: DeployTxData;
}

interface ProofRecord {
  operation: ProofOperation;
  label: string;
  txHash: string;
  consensusTxId: string;
  preparedTransactionId: string;
  intentHash: string;
  intent: Intent;
  consensus?: ConsensusStatusResult;
}

function errorText(error: unknown) {
  return error instanceof Error ? error.message : 'Unexpected Phase 9 proof error.';
}

function shortAddress(value: string) {
  return value.length > 14 ? `${value.slice(0, 8)}...${value.slice(-6)}` : value;
}

export default function Phase9ProofClient() {
  const { account, isConnected, connect, disconnect, sendTransaction, switchNetwork } = useWallet();
  const [recipient, setRecipient] = useState('');
  const [condition, setCondition] = useState(DEFAULT_CONDITION);
  const [evidenceSource, setEvidenceSource] = useState(DEFAULT_SOURCE);
  const [artifact, setArtifact] = useState<WorkflowContractArtifact | null>(null);
  const [pending, setPending] = useState<PendingTransaction | null>(null);
  const [records, setRecords] = useState<ProofRecord[]>([]);
  const [contractAddress, setContractAddress] = useState('');
  const [workflowState, setWorkflowState] = useState<WorkflowState | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [broadcastHash, setBroadcastHash] = useState('');

  const config = useMemo<ConditionalPaymentConfig>(() => ({
    workflowType: 'conditional_payment',
    recipient: recipient.trim(),
    amount: AMOUNT,
    token: 'GEN',
    condition: condition.trim(),
    evidenceSources: [evidenceSource.trim()],
    validated: true,
    errors: [],
  }), [condition, evidenceSource, recipient]);

  const terminalState = String(workflowState?.state.state || '');
  const outcome = String(workflowState?.state.outcome || '');
  const settlementMethod = outcome === 'SATISFIED'
    ? 'settle_release'
    : outcome === 'NOT_SATISFIED'
      ? 'settle_refund'
      : null;
  const settlementComplete = ['RELEASED', 'REFUNDED'].includes(terminalState);

  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setError('');
    try {
      await action();
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setBusy(false);
    }
  };

  const requireWallet = () => {
    if (!account) {
      throw new Error('Connect the payer wallet before preparing the proof.');
    }
    return account;
  };

  const reviewArtifact = () => run(async () => {
    const wallet = requireWallet();
    const reviewed = await reviewPhase9ConditionalContract(config, wallet);
    setArtifact(reviewed);
    setPending(null);
    setBroadcastHash('');
  });

  const prepareDeployment = () => run(async () => {
    const wallet = requireWallet();
    if (!artifact) {
      throw new Error('Review the canonical conditional-payment source first.');
    }
    const intent: Intent = {
      action: 'deploy_contract',
      contract_type: 'conditional_payment',
      workflow_config: artifact.workflow_config,
      source_hash: artifact.source_hash,
      source_origin: 'workflow',
      py_genlayer_dependency: artifact.py_genlayer_dependency,
      generator_version: artifact.generator_version,
      validator_version: artifact.validator_version,
    };
    const tx = await buildPhase9ConditionalDeployTx({
      workflow_config: artifact.workflow_config,
      intent,
      deploy_value_wei: '0',
      source_hash: artifact.source_hash,
      py_genlayer_dependency: artifact.py_genlayer_dependency,
      generator_version: artifact.generator_version,
      validator_version: artifact.validator_version,
    }, wallet, NETWORK);
    setPending({ operation: 'deploy', label: 'Deploy conditional payment', tx });
  });

  const prepareCall = (operation: Exclude<ProofOperation, 'deploy'>, method: string) => run(async () => {
    const wallet = requireWallet();
    if (!contractAddress) {
      throw new Error('A finalized deployed contract address is required.');
    }
    const intent: Intent = {
      action: 'contract_call',
      contract_address: contractAddress,
      method,
      args: [],
      kwargs: {},
      workflow_type: 'conditional_payment',
    };
    const tx = await buildPhase9ConditionalCallTx({
      contract_address: contractAddress,
      method,
      intent,
      args: [],
      kwargs: {},
      value_wei: '0',
      workflow_type: 'conditional_payment',
    }, wallet, NETWORK);
    const label = operation === 'second_settlement'
      ? `Attempt duplicate ${method}`
      : method.replaceAll('_', ' ');
    setPending({ operation, label, tx });
  });

  const reconcilePending = async (txHash: string) => {
    const wallet = requireWallet();
    const normalizedTxHash = txHash.trim();
    setBroadcastHash(normalizedTxHash);
    if (!pending) {
      throw new Error('Prepare the matching transaction before reconciling its broadcast hash.');
    }
    const confirmed = await confirmAction(
      pending.tx.preparedIntent,
      wallet,
      undefined,
      normalizedTxHash,
      NETWORK,
      pending.tx.preparedTransactionId,
      pending.tx.intentHash,
    );
    if (confirmed.error) {
      const diagnostics = confirmed.transactionDiagnostics;
      const gasDetail = diagnostics?.expected !== undefined && diagnostics.actual !== undefined
        ? ` Expected gas ${diagnostics.expected}; submitted gas ${diagnostics.actual}.`
        : '';
      throw new Error(`${confirmed.error}${gasDetail} Do not send the transaction again; use the broadcast hash to reconcile it.`);
    }
    const consensusTxId = confirmed.consensusTxId || confirmed.txHash || txHash;
    setRecords((current) => [{
      operation: pending.operation,
      label: pending.label,
      txHash: confirmed.txHash || normalizedTxHash,
      consensusTxId,
      preparedTransactionId: pending.tx.preparedTransactionId,
      intentHash: pending.tx.intentHash,
      intent: pending.tx.preparedIntent,
    }, ...current]);
    setBroadcastHash('');
    setPending(null);
  };

  const broadcastPending = () => run(async () => {
    if (!pending) {
      throw new Error('Prepare a transaction before sending it to Rabby.');
    }
    const txHash = await sendTransaction({
      to: pending.tx.to,
      data: pending.tx.data,
      value: pending.tx.value,
      chainId: pending.tx.chainId,
      nonce: pending.tx.nonce,
      gas: pending.tx.gas,
      gasPrice: pending.tx.gasPrice,
      maxFeePerGas: pending.tx.maxFeePerGas,
      maxPriorityFeePerGas: pending.tx.maxPriorityFeePerGas,
    });
    setBroadcastHash(txHash);
    await reconcilePending(txHash);
  });

  const recoverBroadcast = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const txHash = String(formData.get('txHash') || '').trim();
    void run(() => reconcilePending(txHash));
  };

  const refreshConsensus = (index: number) => run(async () => {
    const wallet = requireWallet();
    const record = records[index];
    const status = await getConsensusStatus(
      record.consensusTxId,
      wallet,
      NETWORK,
      record.intent,
      record.txHash,
      record.preparedTransactionId,
      record.intentHash,
    );
    setRecords((current) => current.map((item, itemIndex) => (
      itemIndex === index ? { ...item, consensus: status } : item
    )));
    if (status.contractAddress) {
      setContractAddress(status.contractAddress);
    }
    if (status.zeroRoundNoMajority) {
      throw new Error(`${NETWORK_CONFIG[NETWORK].label} finalized with zero rounds and NO_MAJORITY. Stop the proof and record the infrastructure blocker.`);
    }
  });

  const refreshState = () => run(async () => {
    const wallet = requireWallet();
    if (!contractAddress) {
      throw new Error('A finalized contract address is required.');
    }
    setWorkflowState(await getWorkflowState(contractAddress, wallet, NETWORK));
  });

  return (
    <main className="min-h-dvh bg-bg-base text-text-primary">
      <header className="border-b border-border-default bg-bg-elevated/70">
        <div className="mx-auto flex max-w-[1500px] flex-wrap items-center justify-between gap-4 px-5 py-4">
          <div>
            <div className="micro-label mb-1 text-accent-primary">Phase 9 / {NETWORK_CONFIG[NETWORK].label} proof</div>
            <h1 className="font-display text-2xl font-semibold">Intelligent Conditional Payment</h1>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="status-pill border-accent-success/40 bg-accent-success/5 text-accent-success">
              {NETWORK_CONFIG[NETWORK].label} / {NETWORK_CONFIG[NETWORK].chainId}
            </span>
            {isConnected && account ? (
              <>
                <span className="status-pill border-border-strong bg-bg-base text-text-secondary">
                  {shortAddress(account)}
                </span>
                <button type="button" className="control-button flex h-9 items-center gap-2 px-3" onClick={disconnect}>
                  <Wallet size={15} /> Disconnect
                </button>
              </>
            ) : (
              <button type="button" className="control-button flex h-9 items-center gap-2 px-3" onClick={connect}>
                <Wallet size={15} /> Connect wallet
              </button>
            )}
            <button
              type="button"
              className="control-button flex h-9 items-center gap-2 px-3"
              onClick={() => run(() => switchNetwork(NETWORK_CONFIG[NETWORK].chainId))}
              disabled={busy || !isConnected}
            >
              <Radio size={15} /> Use {NETWORK_CONFIG[NETWORK].label}
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-[1500px] gap-6 px-5 py-6 xl:grid-cols-[minmax(0,1.05fr)_minmax(420px,0.95fr)]">
        <section className="min-w-0 space-y-6">
          <div className="border-b border-border-default pb-5">
            <div className="mb-4 flex items-center gap-2 text-accent-primary">
              <FileCheck2 size={17} />
              <h2 className="font-display text-lg font-semibold">Proof Configuration</h2>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="flex flex-col gap-1 md:col-span-2">
                <span className="micro-label">Recipient wallet</span>
                <input className="field-input px-3 py-2 font-mono text-xs" value={recipient} onChange={(event) => setRecipient(event.target.value)} placeholder="0x..." />
              </label>
              <label className="flex flex-col gap-1 md:col-span-2">
                <span className="micro-label">Condition</span>
                <input className="field-input px-3 py-2 text-sm" value={condition} onChange={(event) => setCondition(event.target.value)} />
              </label>
              <label className="flex flex-col gap-1 md:col-span-2">
                <span className="micro-label">External evidence</span>
                <input className="field-input px-3 py-2 font-mono text-xs" value={evidenceSource} onChange={(event) => setEvidenceSource(event.target.value)} />
              </label>
              <div className="field-input px-3 py-2">
                <div className="micro-label">Principal</div>
                <div className="mt-1 font-mono text-sm text-accent-success">{AMOUNT} GEN</div>
              </div>
              <button type="button" className="control-button flex items-center justify-center gap-2 px-4 py-2" onClick={reviewArtifact} disabled={busy || !isConnected}>
                <ShieldCheck size={16} /> Review canonical source
              </button>
            </div>
          </div>

          {artifact && (
            <div className="border-b border-border-default pb-5">
              <div className="mb-3 flex items-center gap-2 text-accent-success">
                <CheckCircle2 size={17} />
                <h2 className="font-display text-lg font-semibold">Reviewed Artifact</h2>
              </div>
              <dl className="grid gap-2 font-mono text-xs sm:grid-cols-[160px_minmax(0,1fr)]">
                <dt className="text-text-muted">Contract</dt><dd>{artifact.contract_name}</dd>
                <dt className="text-text-muted">Source hash</dt><dd className="break-all">{artifact.source_hash}</dd>
                <dt className="text-text-muted">Dependency</dt><dd className="break-all">{artifact.py_genlayer_dependency}</dd>
                <dt className="text-text-muted">Constructor</dt><dd className="break-all">{JSON.stringify(artifact.constructor_args)}</dd>
              </dl>
              <details className="mt-4 border border-border-default bg-black/20">
                <summary className="cursor-pointer px-3 py-2 font-mono text-xs text-text-secondary">Inspect exact source</summary>
                <pre className="max-h-80 overflow-auto border-t border-border-default p-3 text-[10px] leading-relaxed text-text-secondary">{artifact.code}</pre>
              </details>
              <button type="button" className="control-button mt-4 flex items-center gap-2 px-4 py-2" onClick={prepareDeployment} disabled={busy || Boolean(pending)}>
                <Link2 size={16} /> Prepare deployment
              </button>
            </div>
          )}

          {contractAddress && (
            <div className="border-b border-border-default pb-5">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-accent-primary">
                  <CircleDot size={17} />
                  <h2 className="font-display text-lg font-semibold">Lifecycle Actions</h2>
                </div>
                <button type="button" className="control-button flex items-center gap-2 px-3 py-2" onClick={refreshState} disabled={busy}>
                  <RefreshCw size={15} /> Refresh state
                </button>
              </div>
              <div className="mb-4 break-all font-mono text-xs text-text-secondary">{contractAddress}</div>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                <button type="button" className="control-button px-3 py-2" onClick={() => prepareCall('fund', 'fund')} disabled={busy || Boolean(pending)}>Prepare fund</button>
                <button type="button" className="control-button px-3 py-2" onClick={() => prepareCall('request_evaluation', 'request_evaluation')} disabled={busy || Boolean(pending)}>Prepare request evaluation</button>
                <button type="button" className="control-button px-3 py-2" onClick={() => prepareCall('evaluate', 'evaluate')} disabled={busy || Boolean(pending)}>Prepare evaluation</button>
                <button type="button" className="control-button px-3 py-2" onClick={() => prepareCall('settle_release', 'settle_release')} disabled={busy || Boolean(pending)}>Prepare release</button>
                <button type="button" className="control-button px-3 py-2" onClick={() => prepareCall('settle_refund', 'settle_refund')} disabled={busy || Boolean(pending)}>Prepare refund</button>
                <button
                  type="button"
                  className="control-button px-3 py-2"
                  onClick={() => settlementMethod && prepareCall('second_settlement', settlementMethod)}
                  disabled={busy || Boolean(pending) || !settlementComplete || !settlementMethod}
                >
                  Prepare second settlement
                </button>
              </div>
              <div className="mt-4 grid gap-2 font-mono text-xs sm:grid-cols-3">
                <div className="field-input px-3 py-2"><span className="text-text-muted">State:</span> {terminalState || 'unknown'}</div>
                <div className="field-input px-3 py-2"><span className="text-text-muted">Outcome:</span> {outcome || 'unknown'}</div>
                <div className="field-input px-3 py-2"><span className="text-text-muted">Balance:</span> {String(workflowState?.state.balance_wei || 'unknown')} wei</div>
              </div>
              {workflowState && (
                <pre className="mt-3 max-h-64 overflow-auto border border-border-default bg-black/20 p-3 text-[10px] text-text-secondary">{JSON.stringify(workflowState.state, null, 2)}</pre>
              )}
            </div>
          )}
        </section>

        <aside className="min-w-0 space-y-5">
          {pending && (
            <section className="border border-accent-warning/50 bg-accent-warning/5 p-4">
              <div className="mb-3 flex items-center gap-2 text-accent-warning">
                <Send size={16} />
                <h2 className="font-display text-base font-semibold">Prepared: {pending.label}</h2>
              </div>
              <dl className="grid gap-2 font-mono text-xs sm:grid-cols-[110px_minmax(0,1fr)]">
                <dt className="text-text-muted">Destination</dt><dd className="break-all">{pending.tx.to}</dd>
                <dt className="text-text-muted">Value</dt><dd>{formatEther(pending.tx.value)} GEN</dd>
                <dt className="text-text-muted">Gas limit</dt><dd>{pending.tx.gas.toString()}</dd>
                <dt className="text-text-muted">Nonce</dt><dd>{pending.tx.nonce}</dd>
                <dt className="text-text-muted">Prepared ID</dt><dd className="break-all">{pending.tx.preparedTransactionId}</dd>
                <dt className="text-text-muted">Intent hash</dt><dd className="break-all">{pending.tx.intentHash}</dd>
                {broadcastHash && <><dt className="text-text-muted">Broadcast hash</dt><dd className="break-all">{broadcastHash}</dd></>}
                <dt className="text-text-muted">Expires</dt><dd>{pending.tx.expiresAt}</dd>
              </dl>
              <button type="button" className="mt-4 flex w-full items-center justify-center gap-2 bg-accent-primary px-4 py-3 font-mono text-xs font-bold text-black" onClick={broadcastPending} disabled={busy || Boolean(broadcastHash)}>
                <Wallet size={16} /> Send to Rabby
              </button>
              <form className="mt-3 grid gap-2" onSubmit={recoverBroadcast}>
                <label className="micro-label" htmlFor="phase9-recovery-hash">Already broadcast?</label>
                <input
                  id="phase9-recovery-hash"
                  name="txHash"
                  className="field-input px-3 py-2 font-mono text-xs"
                  placeholder="0x transaction hash"
                  value={broadcastHash}
                  onChange={(event) => setBroadcastHash(event.target.value)}
                  required
                />
                <button type="submit" className="control-button px-3 py-2" disabled={busy}>
                  Reconcile broadcast hash
                </button>
              </form>
            </section>
          )}

          <section>
            <div className="mb-3 flex items-center gap-2 text-accent-primary">
              <Radio size={16} />
              <h2 className="font-display text-base font-semibold">Transaction Evidence</h2>
            </div>
            <div className="space-y-3">
              {records.length === 0 && <p className="font-mono text-xs text-text-muted">No wallet transactions broadcast.</p>}
              {records.map((record, index) => (
                <article key={`${record.txHash}-${record.operation}`} className="border border-border-default bg-bg-elevated/45 p-3">
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <strong className="font-mono text-xs uppercase text-text-primary">{record.label}</strong>
                    <button type="button" className="control-button flex h-8 items-center gap-1 px-2 text-[10px]" onClick={() => refreshConsensus(index)} disabled={busy}>
                      <RefreshCw size={12} /> Poll
                    </button>
                  </div>
                  <div className="space-y-1 break-all font-mono text-[10px] text-text-secondary">
                    <div>TX: {record.txHash}</div>
                    <div>CONSENSUS: {record.consensusTxId}</div>
                    <div>STATUS: {record.consensus?.status || 'not polled'}</div>
                    <div>EXECUTION: {record.consensus?.executionStatus || 'not polled'}</div>
                    <div>PROTOCOL: {record.consensus?.protocolResult || 'unknown'}</div>
                    <div>ROUNDS / VALIDATORS / VOTES: {record.consensus?.numRounds ?? '?'} / {record.consensus?.validatorCount ?? '?'} / {record.consensus?.voteCount ?? '?'}</div>
                  </div>
                  <a className="mt-2 inline-flex items-center gap-1 text-[10px] text-accent-success" href={`https://explorer-studio.genlayer.com/tx/${record.txHash}`} target="_blank" rel="noreferrer">
                    <ExternalLink size={11} /> Explorer
                  </a>
                </article>
              ))}
            </div>
          </section>

          {error && (
            <div className="border border-accent-danger/50 bg-accent-danger/10 p-3 font-mono text-xs text-accent-danger">{error}</div>
          )}
        </aside>
      </div>
    </main>
  );
}
