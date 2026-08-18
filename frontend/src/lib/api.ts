export interface Intent {
  action: 'transfer' | 'check_balance' | 'deploy_contract' | 'generate_contract' | 'contract_review' | 'contract_call' | 'conditional_payment' | 'escrow' | 'subscription' | 'bounty' | 'debug_trace' | 'appeal_transaction' | 'notarize_claim' | 'unknown';
  tx_hash?: string;
  amount?: number | string;
  token?: string;
  recipient?: string;
  address?: string;
  code?: string;
  contract_name?: string;
  contract_type?: string;
  logic_description?: string;
  condition?: string;
  evidenceSources?: string[];
  buyer?: string;
  seller?: string;
  frequency?: string;
  title?: string;
  reward?: number | string;
  description?: string;
  constructor_args?: unknown[];
  constructor_kwargs?: Record<string, unknown>;
  constructor_args_text?: string;
  constructor_kwargs_text?: string;
  deploy_value?: number;
  deploy_value_text?: string;
  deploy_value_wei?: string;
  value_wei?: string;
  gas_limit?: number | null;
  gas_limit_text?: string;
  consensus_max_rotations?: number | null;
  consensus_max_rotations_text?: string;
  leader_only?: boolean;
  source_file_name?: string;
  source_hash?: string;
  source_origin?: 'generated' | 'workflow' | 'uploaded' | 'notary';
  py_genlayer_dependency?: string;
  genlayer_sdk_version?: string;
  generator_version?: string;
  validator_version?: string;
  compiler_version?: string;
  artifact_version?: number;
  workflow_config?: import('@/types/WorkflowConfig').AnyWorkflowConfig;
  contract_address?: string;
  method?: string;
  args?: unknown[];
  kwargs?: Record<string, unknown>;
  workflow_type?: string;
  next_status?: string;
  notary_operation?: 'deploy_registry' | 'submit_claim' | 'evaluate_claim';
  notary_spec?: import('@/types/Notary').NotarySpec;
  claim_id?: string;
  claimant_address?: string;
  [key: string]: unknown;
}

export type ConsensusStatus =
  | 'UNINITIALIZED'
  | 'PENDING'
  | 'PROPOSING'
  | 'COMMITTING'
  | 'REVEALING'
  | 'ACCEPTED'
  | 'UNDETERMINED'
  | 'FINALIZED'
  | 'CANCELED'
  | 'APPEAL_REVEALING'
  | 'APPEAL_COMMITTING'
  | 'READY_TO_FINALIZE'
  | 'VALIDATORS_TIMEOUT'
  | 'LEADER_TIMEOUT'
  | 'UNKNOWN';

export type ExecutionStatus =
  | 'NOT_VOTED'
  | 'FINISHED_WITH_RETURN'
  | 'FINISHED_WITH_ERROR'
  | 'UNKNOWN';

export type LifecycleStatus =
  | 'PREPARED'
  | 'AWAITING_SIGNATURE'
  | 'BROADCAST'
  | 'CHAIN_ACCEPTED'
  | 'CONSENSUS_PENDING'
  | 'ACCEPTED'
  | 'FINALIZED'
  | 'UNDETERMINED'
  | 'CANCELED'
  | 'VALIDATORS_TIMEOUT'
  | 'LEADER_TIMEOUT'
  | 'FAILED';

export type EvmStatus = 'NOT_BROADCAST' | 'BROADCAST' | 'SUCCESS' | 'FAILED';

export type MessageStatus =
  | 'pending'
  | 'simulating'
  | 'awaiting_input'
  | 'awaiting_confirmation'
  | 'executing'
  | 'submitted'
  | 'finalized'
  | 'success'
  | 'error';

export interface SimulationResult {
  success: boolean;
  cases?: string[];
  error?: string;
  summary?: string;
  gasEstimate?: number;
}

export interface MessageData {
  id: string;
  role: 'user' | 'bot';
  content: string;
  intent?: Intent;
  simulation?: SimulationResult;
  status?: MessageStatus;
  txHash?: string;
  consensusTxId?: string;
  consensusStatus?: ConsensusStatus;
  consensusStatusCode?: number | null;
  executionStatus?: ExecutionStatus;
  lifecycleStatus?: LifecycleStatus;
  evmStatus?: EvmStatus;
  consensusFinal?: boolean;
  consensusAppealable?: boolean;
  consensusTerminal?: boolean;
  consensusError?: string;
  protocolResult?: string | null;
  consensusRounds?: number | null;
  validatorCount?: number | null;
  voteCount?: number | null;
  zeroRoundNoMajority?: boolean;
  consensusNetwork?: NetworkKey;
  preparedTransactionId?: string;
  intentHash?: string;
  transactionDiagnostics?: TransactionDiagnostics;
  contractAddress?: string;
  derivedAddresses?: string[];
  helpCommands?: Array<{
    label: string;
    command: string;
    description: string;
  }>;
  generatedContract?: {
    contractName: string;
    contractType: string;
    explanation: string;
    code: string;
    fileName: string;
    specification?: Record<string, unknown>;
    validation?: ContractValidationResult;
    sourceHash: string;
    sourceOrigin: 'generated' | 'workflow' | 'uploaded' | 'notary';
    pyGenlayerDependency: string;
    genlayerSdkVersion: string;
    generatorVersion: string;
    validatorVersion: string;
    compilerVersion: string;
    artifactVersion: number;
  };
  workflowConfig?: import('@/types/WorkflowConfig').AnyWorkflowConfig;
  workflowState?: WorkflowState;
  notaryBlueprint?: import('@/types/Notary').NotaryBlueprintArtifact;
  contractReview?: ContractReviewResult;
  notaryRecord?: import('@/types/Notary').NotaryRecord;
}

export interface WorkflowState {
  workflow_type: string;
  contract_address: string;
  network: NetworkKey;
  state: Record<string, unknown>;
  transaction_hash_variant: 'latest-final';
}

export interface ChatHistoryPayload {
  chats: Array<{
    id: string;
    title: string;
    updatedAt: number;
    messages: MessageData[];
  }>;
  currentChatId?: string | null;
}

import { API_BASE_URL as API_URL } from '@/config';
import type { NetworkKey } from '@/config';
import { parseEther } from 'viem';
import type { Address, Hex } from 'viem';

export interface WalletBalanceResponse {
  address: string;
  balance: number;
  token: string;
}

export interface ContractValidationResult {
  valid: boolean;
  message: string;
  errors: string[];
  warnings: string[];
  contract_names: string[];
  source_hash?: string;
  source_origin?: 'uploaded';
  py_genlayer_dependency?: string;
  genlayer_sdk_version?: string;
  generator_version?: string;
  validator_version?: string;
  compiler_version?: string;
  artifact_version?: number;
}

export interface ContractReviewResult {
  verdict: 'READY' | 'READY_WITH_WARNINGS' | 'BLOCKED';
  deploymentReady: boolean;
  blockingErrors: string[];
  warnings: string[];
  suggestions: string[];
  structural: {
    contractNames: string[];
    publicMethods: string[];
    storageFields: string[];
    nondeterministicCalls: string[];
    equivalenceBoundaries: string[];
  };
  safety: {
    financialCustody: boolean;
    authorizationChecks: Array<{ method: string; senderCheckDetected: boolean }>;
    findings: string[];
  };
  genlayer: {
    requiredForBehavior: boolean;
    judgmentDescription: string;
    findings: string[];
  };
}

const tokenKey = (address: string) => `genlayer-auth:${address.toLowerCase()}`;

function isStoredTokenExpired(token: string): boolean {
  try {
    const payloadSegment = token.split('.')[1];
    if (!payloadSegment) {
      return true;
    }
    const normalized = payloadSegment.replaceAll('-', '+').replaceAll('_', '/');
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=');
    const payload = JSON.parse(window.atob(padded)) as { exp?: number };
    return typeof payload.exp !== 'number' || payload.exp * 1000 <= Date.now();
  } catch {
    return true;
  }
}

export function getStoredAuthToken(address?: string | null): string | null {
  if (!address || typeof window === 'undefined') {
    return null;
  }
  const key = tokenKey(address);
  const token = window.localStorage.getItem(key);
  if (token && isStoredTokenExpired(token)) {
    window.localStorage.removeItem(key);
    return null;
  }
  return token;
}

export function setStoredAuthToken(address: string, token: string) {
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(tokenKey(address), token);
  }
}

export function clearStoredAuthToken(address?: string | null) {
  if (address && typeof window !== 'undefined') {
    window.localStorage.removeItem(tokenKey(address));
  }
}

function authHeaders(walletAddress?: string | null): HeadersInit {
  const token = getStoredAuthToken(walletAddress);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function getNonce(address: string): Promise<string> {
  const url = new URL(`${API_URL}/auth/nonce`);
  url.searchParams.set('address', address);
  const response = await fetch(url.toString(), { headers: authHeaders(address) });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to get auth nonce: ${response.status}`);
  }
  const data = await response.json();
  return data.nonce;
}

export async function verifySignature(address: string, message: string, signature: string): Promise<string> {
  const response = await fetch(`${API_URL}/auth/verify`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ address, message, signature }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to verify wallet signature: ${response.status}`);
  }

  const data = await response.json();
  setStoredAuthToken(address, data.access_token);
  return data.access_token;
}

export async function getChatHistory(walletAddress: string): Promise<ChatHistoryPayload | null> {
  const response = await fetch(`${API_URL}/chat/history`, {
    headers: authHeaders(walletAddress),
  });

  if (response.status === 401 || response.status === 404) {
    return null;
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch chat history: ${response.status}`);
  }

  return response.json();
}

export async function saveChatHistory(walletAddress: string, payload: ChatHistoryPayload): Promise<void> {
  const response = await fetch(`${API_URL}/chat/history`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(walletAddress),
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to save chat history: ${response.status}`);
  }
}

export async function validateContractFile(code: string, fileName: string, walletAddress?: string): Promise<ContractValidationResult> {
  const response = await fetch(`${API_URL}/chat/validate-contract`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(walletAddress),
    },
    body: JSON.stringify({
      code,
      file_name: fileName,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to validate contract: ${response.status}`);
  }

  return response.json();
}

export async function reviewContract(code: string, walletAddress?: string): Promise<ContractReviewResult> {
  const response = await fetch(`${API_URL}/chat/contract-review`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(walletAddress),
    },
    body: JSON.stringify({ code }),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to review contract: ${response.status}`);
  }
  return response.json();
}

export interface WorkflowContractArtifact {
  code: string;
  contract_name: string;
  contract_type: string;
  file_name: string;
  explanation: string;
  workflow_config: import('@/types/WorkflowConfig').AnyWorkflowConfig;
  constructor_args: unknown[];
  constructor_kwargs: Record<string, unknown>;
  validation: ContractValidationResult;
  source_hash: string;
  source_origin: 'workflow';
  py_genlayer_dependency: string;
  genlayer_sdk_version: string;
  generator_version: string;
  validator_version: string;
  compiler_version: string;
  artifact_version: number;
}

export async function reviewWorkflowContract(
  workflowConfig: import('@/types/WorkflowConfig').AnyWorkflowConfig,
  walletAddress: string
): Promise<WorkflowContractArtifact> {
  const response = await fetch(API_URL + '/chat/workflow-contract', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(walletAddress),
    },
    body: JSON.stringify({ workflow_config: workflowConfig }),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to review canonical workflow source: ' + response.status);
  }
  return response.json();
}

export async function reviewPhase9ConditionalContract(
  workflowConfig: import('@/types/WorkflowConfig').ConditionalPaymentConfig,
  walletAddress: string,
): Promise<WorkflowContractArtifact> {
  const response = await fetch(`${API_URL}/chat/phase9/conditional-artifact`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(walletAddress),
    },
    body: JSON.stringify({ workflow_config: workflowConfig }),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to review Phase 9 artifact: ${response.status}`);
  }
  return response.json();
}

export async function reviewNotaryBlueprint(
  notarySpec: Partial<import('@/types/Notary').NotarySpec>,
  walletAddress: string,
): Promise<import('@/types/Notary').NotaryBlueprintArtifact> {
  const response = await fetch(`${API_URL}/chat/notary-blueprint`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(walletAddress),
    },
    body: JSON.stringify({ notary_spec: notarySpec }),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to review AI Notary blueprint: ${response.status}`);
  }
  return response.json();
}

export async function sendMessage(
  content: string,
  walletAddress?: string,
  network?: NetworkKey,
  pendingNotarySpec?: Partial<import('@/types/Notary').NotarySpec>,
): Promise<Partial<MessageData>> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);

  try {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...authHeaders(walletAddress),
    };

    const body = walletAddress
      ? { message: content, wallet_address: walletAddress, network, notary_spec: pendingNotarySpec }
      : { message: content, network, notary_spec: pendingNotarySpec };

    const response = await fetch(`${API_URL}/chat`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const data = await response.json();
    return data;
  } catch (error) {
    console.error("Error calling chat API:", error);
    const isTimeout = error instanceof DOMException && error.name === 'AbortError';
    return {
      content: isTimeout
        ? "Request timed out while interpreting your prompt. Please retry."
        : "Error communicating with the GenLayer AI backend. Is the server running?",
      intent: { action: 'unknown' },
      status: 'error'
    };
  } finally {
    clearTimeout(timeout);
  }
}

export interface TransactionDiagnostics {
  code?: string;
  message?: string;
  txHash?: string;
  preparedTransactionId?: string;
  intentHash?: string;
  field?: string;
  expected?: string | number | null;
  actual?: string | number | null;
  retriable?: boolean;
  retryAttempts?: number;
}

export interface ConfirmActionResult {
  txHash?: string;
  consensusTxId?: string;
  consensusStatus?: ConsensusStatus;
  executionStatus?: ExecutionStatus;
  lifecycleStatus?: LifecycleStatus;
  evmStatus?: EvmStatus;
  preparedTransactionId?: string;
  intentHash?: string;
  transactionDiagnostics?: TransactionDiagnostics;
  contractAddress?: string;
  derivedAddresses?: string[];
  balance?: number;
  content?: string;
  error?: string;
}

export function parseTransactionDiagnostics(detail: unknown): {
  message: string;
  diagnostics?: TransactionDiagnostics;
} {
  if (typeof detail === 'string') {
    return { message: detail };
  }
  if (!detail || typeof detail !== 'object') {
    return { message: 'Failed to confirm action.' };
  }
  const value = detail as Record<string, unknown>;
  const diagnostics: TransactionDiagnostics = {
    code: typeof value.code === 'string' ? value.code : undefined,
    message: typeof value.message === 'string' ? value.message : undefined,
    txHash: typeof value.tx_hash === 'string' ? value.tx_hash : undefined,
    preparedTransactionId: typeof value.prepared_transaction_id === 'string' ? value.prepared_transaction_id : undefined,
    intentHash: typeof value.intent_hash === 'string' ? value.intent_hash : undefined,
    field: typeof value.field === 'string' ? value.field : undefined,
    expected: typeof value.expected === 'string' || typeof value.expected === 'number' ? value.expected : null,
    actual: typeof value.actual === 'string' || typeof value.actual === 'number' ? value.actual : null,
    retriable: typeof value.retriable === 'boolean' ? value.retriable : undefined,
    retryAttempts: typeof value.retry_attempts === 'number' ? value.retry_attempts : undefined,
  };
  const hasDiagnostics = Object.values(diagnostics).some((entry) => entry !== undefined && entry !== null);
  return {
    message: diagnostics.message || 'Failed to confirm action.',
    diagnostics: hasDiagnostics ? diagnostics : undefined,
  };
}

export interface ConsensusStatusResult {
  consensusTxId: string;
  status: ConsensusStatus;
  statusCode: number | null;
  executionStatus: ExecutionStatus;
  lifecycleStatus: LifecycleStatus;
  evmStatus?: EvmStatus | null;
  final: boolean;
  appealable: boolean;
  terminal: boolean;
  contractAddress?: string | null;
  derivedAddresses?: string[];
  protocolResult?: string | null;
  numRounds?: number | null;
  validatorCount?: number | null;
  voteCount?: number | null;
  zeroRoundNoMajority?: boolean;
}

export interface ConsensusReadinessResult {
  ready: boolean;
  blockerCode?: string;
  message?: string;
  network?: NetworkKey;
  lastTxHash?: string | null;
  protocolResult?: string | null;
  numRounds?: number | null;
  validatorCount?: number | null;
  retryAfterSeconds?: number;
}

export async function confirmAction(
  intent: Intent,
  walletAddress?: string,
  signedTransaction?: string,
  txHash?: string,
  network?: NetworkKey,
  preparedTransactionId?: string,
  intentHash?: string
): Promise<ConfirmActionResult> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 65000);
  const fallbackIdentifiers = {
    ...(txHash ? { txHash } : {}),
    ...(preparedTransactionId ? { preparedTransactionId } : {}),
    ...(intentHash ? { intentHash } : {}),
  };
  let transactionDiagnostics: TransactionDiagnostics | undefined;
  try {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...authHeaders(walletAddress),
    };

    const body = {
      intent,
      ...(walletAddress && { wallet_address: walletAddress }),
      ...(signedTransaction && { signed_transaction: signedTransaction }),
      ...(txHash && { tx_hash: txHash }),
      ...(network && { network }),
      ...(preparedTransactionId && { prepared_transaction_id: preparedTransactionId }),
      ...(intentHash && { intent_hash: intentHash }),
    };

    const response = await fetch(`${API_URL}/chat/confirm`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const parsed = parseTransactionDiagnostics(errorData.detail);
      transactionDiagnostics = {
        ...parsed.diagnostics,
        ...fallbackIdentifiers,
      };
      throw new Error(parsed.message || `HTTP error! status: ${response.status}`);
    }

    const data = await response.json() as ConfirmActionResult & {
      transaction_diagnostics?: TransactionDiagnostics;
      prepared_transaction_id?: string;
      intent_hash?: string;
      tx_hash?: string;
    };
    return {
      ...fallbackIdentifiers,
      ...data,
      txHash: data.txHash || data.tx_hash || fallbackIdentifiers.txHash,
      preparedTransactionId: data.preparedTransactionId || data.prepared_transaction_id || fallbackIdentifiers.preparedTransactionId,
      intentHash: data.intentHash || data.intent_hash || fallbackIdentifiers.intentHash,
      transactionDiagnostics: data.transactionDiagnostics || data.transaction_diagnostics,
    };
  } catch (error: unknown) {
    console.error("Error confirming action:", error);

    if (error instanceof TypeError) {
      return {
        ...fallbackIdentifiers,
        transactionDiagnostics: {
          ...transactionDiagnostics,
          code: transactionDiagnostics?.code || 'backend_unreachable',
          message: transactionDiagnostics?.message || 'Backend connection failed while confirming the transaction.',
          retriable: true,
        },
        error: `Unable to reach backend at ${API_URL}. Start the API server and try again.`,
      };
    }

    if (error instanceof Error) {
      return {
        ...fallbackIdentifiers,
        transactionDiagnostics,
        error: error.message || "Failed to confirm action.",
      };
    }

    return { ...fallbackIdentifiers, transactionDiagnostics, error: "Failed to confirm action." };
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function getConsensusReadiness(
  walletAddress: string,
  network: NetworkKey,
): Promise<ConsensusReadinessResult> {
  const url = new URL(`${API_URL}/chat/consensus-readiness`);
  url.searchParams.set('network', network);
  const response = await fetch(url.toString(), { headers: authHeaders(walletAddress) });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to read consensus readiness: ${response.status}`);
  }
  return response.json();
}

export async function getConsensusStatus(
  consensusTxId: string,
  walletAddress: string,
  network: NetworkKey,
  workflowIntent?: Intent,
  txHash?: string,
  preparedTransactionId?: string,
  intentHash?: string
): Promise<ConsensusStatusResult> {
  const response = await fetch(`${API_URL}/chat/consensus-status`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(walletAddress),
    },
    body: JSON.stringify({
      consensus_tx_id: consensusTxId,
      network,
      workflow_intent: workflowIntent
        ? {
            ...workflowIntent,
            ...(txHash ? { tx_hash: txHash } : {}),
          }
        : undefined,
      prepared_transaction_id: preparedTransactionId,
      intent_hash: intentHash,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to read consensus status: ${response.status}`);
  }

  return response.json();
}

export async function getWalletBalance(address?: string, network?: NetworkKey): Promise<WalletBalanceResponse> {
  const url = new URL(`${API_URL}/wallet/balance`);
  if (address) {
    url.searchParams.set('address', address);
  }
  if (network) {
    url.searchParams.set('network', network);
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20000);

  try {
    const response = await fetch(url.toString(), { signal: controller.signal, headers: authHeaders(address) });
    if (!response.ok) {
      throw new Error(`Failed to fetch wallet balance: ${response.status}`);
    }

    return response.json();
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('Wallet balance request timed out');
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

export interface TxParams {
  chain_id: number;
  gas_price: string;
  nonce: number;
  gas_limit: number;
  rpc_url: string;
}

export async function getTxParams(address: string, network: NetworkKey): Promise<TxParams> {
  const url = new URL(`${API_URL}/chat/tx-params`);
  url.searchParams.set('address', address);
  url.searchParams.set('network', network);

  try {
    const response = await fetch(url.toString(), { headers: authHeaders(address) });
    if (!response.ok) {
      throw new Error(`Failed to fetch tx params: ${response.status}`);
    }
    return response.json();
  } catch (error) {
    console.error("Error fetching tx params:", error);
    throw error;
  }
}

export interface PreparedTransactionMetadata {
  preparedTransactionId: string;
  intentHash: string;
  preparedIntent: Intent;
  expiresAt: string;
}

export interface ContractArtifactMetadata {
  sourceHash: string;
  sourceOrigin: 'generated' | 'workflow' | 'uploaded' | 'notary';
  pyGenlayerDependency: string;
  genlayerSdkVersion: string;
  generatorVersion: string;
  validatorVersion: string;
  compilerVersion: string;
  artifactVersion: number;
}

export interface TransferTxData extends PreparedTransactionMetadata {
  to: Address;
  value: bigint;
  data: Hex;
  chainId: number;
  nonce: number;
  gas: bigint;
  gasPrice?: bigint;
  maxFeePerGas?: bigint;
  maxPriorityFeePerGas?: bigint;
}

export interface AppealTxData extends TransferTxData {
  consensusTxId: string;
  consensusStatus: string;
  appealWindowOpen: boolean;
  appealWindowStatus: string;
  minimumAppealBondWei: string;
  appealBondWei: string;
  appealRound?: number | null;
  appealStatusCode?: number | null;
  appealWindowSource?: string | null;
  minimumAppealBondSource?: string | null;
}

export interface DeployTxData extends PreparedTransactionMetadata, Partial<ContractArtifactMetadata> {
  to: Address;
  data: Hex;
  value: bigint;
  chainId: number;
  nonce: number;
  gas: bigint;
  gasPrice?: bigint;
  maxFeePerGas?: bigint;
  maxPriorityFeePerGas?: bigint;
}

export async function buildTransferTx(
  recipient: string,
  amount: number,
  walletAddress: string,
  network: NetworkKey,
  intent?: Intent
): Promise<TransferTxData> {
  const amountWei = parseEther(amount.toString());
  const response = await fetch(`${API_URL}/chat/transfer-tx`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(walletAddress),
    },
    body: JSON.stringify({
      address: walletAddress,
      recipient,
      amount_wei: amountWei.toString(),
      intent,
      network,
    }),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to prepare transfer transaction: ${response.status}`);
  }

  const tx = await response.json();
  return {
    to: tx.to as Address,
    value: BigInt(tx.value),
    data: tx.data as Hex,
    chainId: tx.chain_id,
    nonce: tx.nonce,
    gas: BigInt(tx.gas_limit),
    gasPrice: tx.gas_price ? BigInt(tx.gas_price) : undefined,
    maxFeePerGas: tx.max_fee_per_gas ? BigInt(tx.max_fee_per_gas) : undefined,
    maxPriorityFeePerGas: tx.max_priority_fee_per_gas ? BigInt(tx.max_priority_fee_per_gas) : undefined,
    preparedTransactionId: tx.prepared_transaction_id,
    intentHash: tx.intent_hash,
    preparedIntent: tx.prepared_intent,
    expiresAt: tx.expires_at,
  };
}

export interface DeployTxRequestPayload {
  code: string;
  intent?: Intent;
  constructor_args?: unknown[];
  constructor_kwargs?: Record<string, unknown>;
  deploy_value_wei?: string;
  gas_limit?: number | null;
  consensus_max_rotations?: number | null;
  leader_only?: boolean;
  source_hash: string;
  source_origin: 'generated' | 'uploaded';
  py_genlayer_dependency: string;
  generator_version: string;
  validator_version: string;
}

export interface WorkflowDeployTxRequestPayload {
  workflow_config: import('@/types/WorkflowConfig').AnyWorkflowConfig;
  intent?: Intent;
  deploy_value_wei?: string;
  gas_limit?: number | null;
  consensus_max_rotations?: number | null;
  leader_only?: boolean;
  source_hash: string;
  py_genlayer_dependency: string;
  generator_version: string;
  validator_version: string;
}

export interface WorkflowDeployTxData extends DeployTxData {
  code: string;
  contractName: string;
  constructorArgs: unknown[];
  constructorKwargs: Record<string, unknown>;
  workflowConfig: import('@/types/WorkflowConfig').AnyWorkflowConfig;
}

export interface NotaryDeployTxRequestPayload {
  notary_spec: import('@/types/Notary').NotarySpec;
  intent?: Intent;
  gas_limit?: number | null;
  consensus_max_rotations?: number | null;
  leader_only?: boolean;
  source_hash: string;
  py_genlayer_dependency: string;
  generator_version: string;
  validator_version: string;
}

export interface NotaryDeployTxData extends DeployTxData {
  code: string;
  contractName: string;
  constructorArgs: unknown[];
  constructorKwargs: Record<string, unknown>;
  notarySpec: import('@/types/Notary').NotarySpec;
}

export interface NotaryCallTxRequestPayload {
  contract_address: string;
  notary_action: 'submit_claim' | 'evaluate_claim';
  claim_id: string;
  notary_spec?: import('@/types/Notary').NotarySpec;
  intent?: Intent;
  gas_limit?: number | null;
  consensus_max_rotations?: number | null;
  leader_only?: boolean;
}

export async function buildAppealTx(
  consensusTxId: string,
  walletAddress: string,
  network: NetworkKey,
  intent?: Intent,
  bondWei?: string,
): Promise<AppealTxData> {
  const response = await fetch(`${API_URL}/chat/appeal-tx`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(walletAddress) },
    body: JSON.stringify({
      address: walletAddress,
      consensus_tx_id: consensusTxId,
      bond_wei: bondWei,
      intent,
      network,
    }),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to prepare appeal transaction: ${response.status}`);
  }
  const tx = await response.json();
  return {
    to: tx.to as Address,
    value: BigInt(tx.value),
    data: tx.data as Hex,
    chainId: tx.chain_id,
    nonce: tx.nonce,
    gas: BigInt(tx.gas_limit),
    gasPrice: tx.gas_price ? BigInt(tx.gas_price) : undefined,
    maxFeePerGas: tx.max_fee_per_gas ? BigInt(tx.max_fee_per_gas) : undefined,
    maxPriorityFeePerGas: tx.max_priority_fee_per_gas ? BigInt(tx.max_priority_fee_per_gas) : undefined,
    preparedTransactionId: tx.prepared_transaction_id,
    intentHash: tx.intent_hash,
    preparedIntent: tx.prepared_intent,
    expiresAt: tx.expires_at,
    consensusTxId: tx.consensus_tx_id,
    consensusStatus: tx.consensus_status,
    appealWindowOpen: tx.appeal_window_open,
    appealWindowStatus: tx.appeal_window_status,
    minimumAppealBondWei: tx.minimum_appeal_bond_wei,
    appealBondWei: tx.appeal_bond_wei,
    appealRound: tx.appeal_round,
    appealStatusCode: tx.appeal_status_code,
    appealWindowSource: tx.appeal_window_source,
    minimumAppealBondSource: tx.minimum_appeal_bond_source,
  };
}

export async function buildDeployTx(
  payload: DeployTxRequestPayload,
  walletAddress: string,
  network: NetworkKey
): Promise<DeployTxData> {
  const response = await fetch(`${API_URL}/chat/deploy-tx`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(walletAddress),
    },
    body: JSON.stringify({
      address: walletAddress,
      code: payload.code,
      intent: payload.intent,
      constructor_args: payload.constructor_args ?? [],
      constructor_kwargs: payload.constructor_kwargs ?? {},
      value_wei: payload.deploy_value_wei ?? '0',
      gas_limit: payload.gas_limit ?? null,
      consensus_max_rotations: payload.consensus_max_rotations ?? null,
      leader_only: payload.leader_only ?? false,
      source_hash: payload.source_hash,
      source_origin: payload.source_origin,
      py_genlayer_dependency: payload.py_genlayer_dependency,
      generator_version: payload.generator_version,
      validator_version: payload.validator_version,
      network,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to prepare deploy transaction: ${response.status}`);
  }

  const tx = await response.json();
  return {
    to: tx.to as Address,
    data: tx.data as Hex,
    value: BigInt(tx.value),
    chainId: tx.chain_id,
    nonce: tx.nonce,
    gas: BigInt(tx.gas_limit),
    gasPrice: tx.gas_price ? BigInt(tx.gas_price) : undefined,
    maxFeePerGas: tx.max_fee_per_gas ? BigInt(tx.max_fee_per_gas) : undefined,
    maxPriorityFeePerGas: tx.max_priority_fee_per_gas ? BigInt(tx.max_priority_fee_per_gas) : undefined,
    preparedTransactionId: tx.prepared_transaction_id,
    intentHash: tx.intent_hash,
    preparedIntent: tx.prepared_intent,
    expiresAt: tx.expires_at,
    sourceHash: tx.source_hash,
    sourceOrigin: tx.source_origin,
    pyGenlayerDependency: tx.py_genlayer_dependency,
    genlayerSdkVersion: tx.genlayer_sdk_version,
    generatorVersion: tx.generator_version,
    validatorVersion: tx.validator_version,
    compilerVersion: tx.compiler_version,
    artifactVersion: tx.artifact_version,
  };
}

export async function buildWorkflowDeployTx(
  payload: WorkflowDeployTxRequestPayload,
  walletAddress: string,
  network: NetworkKey
): Promise<WorkflowDeployTxData> {
  const response = await fetch(`${API_URL}/chat/workflow-deploy-tx`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(walletAddress),
    },
    body: JSON.stringify({
      address: walletAddress,
      workflow_config: payload.workflow_config,
      intent: payload.intent,
      value_wei: payload.deploy_value_wei ?? '0',
      gas_limit: payload.gas_limit ?? null,
      consensus_max_rotations: payload.consensus_max_rotations ?? null,
      leader_only: payload.leader_only ?? false,
      source_hash: payload.source_hash,
      py_genlayer_dependency: payload.py_genlayer_dependency,
      generator_version: payload.generator_version,
      validator_version: payload.validator_version,
      network,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to prepare workflow deployment: ${response.status}`);
  }

  const tx = await response.json();
  return {
    to: tx.to as Address,
    data: tx.data as Hex,
    value: BigInt(tx.value),
    chainId: tx.chain_id,
    nonce: tx.nonce,
    gas: BigInt(tx.gas_limit),
    gasPrice: tx.gas_price ? BigInt(tx.gas_price) : undefined,
    maxFeePerGas: tx.max_fee_per_gas ? BigInt(tx.max_fee_per_gas) : undefined,
    maxPriorityFeePerGas: tx.max_priority_fee_per_gas ? BigInt(tx.max_priority_fee_per_gas) : undefined,
    code: tx.code,
    contractName: tx.contract_name,
    constructorArgs: tx.constructor_args,
    constructorKwargs: tx.constructor_kwargs,
    workflowConfig: tx.workflow_config,
    preparedTransactionId: tx.prepared_transaction_id,
    intentHash: tx.intent_hash,
    preparedIntent: tx.prepared_intent,
    expiresAt: tx.expires_at,
    sourceHash: tx.source_hash,
    sourceOrigin: tx.source_origin,
    pyGenlayerDependency: tx.py_genlayer_dependency,
    genlayerSdkVersion: tx.genlayer_sdk_version,
    generatorVersion: tx.generator_version,
    validatorVersion: tx.validator_version,
    compilerVersion: tx.compiler_version,
    artifactVersion: tx.artifact_version,
  };
}

export async function buildPhase9ConditionalDeployTx(
  payload: WorkflowDeployTxRequestPayload,
  walletAddress: string,
  network: NetworkKey,
): Promise<WorkflowDeployTxData> {
  const response = await fetch(`${API_URL}/chat/phase9/conditional-deploy-tx`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(walletAddress),
    },
    body: JSON.stringify({
      address: walletAddress,
      workflow_config: payload.workflow_config,
      intent: payload.intent,
      value_wei: payload.deploy_value_wei ?? '0',
      gas_limit: payload.gas_limit ?? null,
      consensus_max_rotations: payload.consensus_max_rotations ?? null,
      leader_only: payload.leader_only ?? false,
      source_hash: payload.source_hash,
      py_genlayer_dependency: payload.py_genlayer_dependency,
      generator_version: payload.generator_version,
      validator_version: payload.validator_version,
      network,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const detail = typeof errorData.detail === 'string'
      ? errorData.detail
      : JSON.stringify(errorData.detail || {});
    throw new Error(detail || `Failed to prepare Phase 9 deployment: ${response.status}`);
  }

  const tx = await response.json();
  return {
    to: tx.to as Address,
    data: tx.data as Hex,
    value: BigInt(tx.value),
    chainId: tx.chain_id,
    nonce: tx.nonce,
    gas: BigInt(tx.gas_limit),
    gasPrice: tx.gas_price ? BigInt(tx.gas_price) : undefined,
    maxFeePerGas: tx.max_fee_per_gas ? BigInt(tx.max_fee_per_gas) : undefined,
    maxPriorityFeePerGas: tx.max_priority_fee_per_gas ? BigInt(tx.max_priority_fee_per_gas) : undefined,
    code: tx.code,
    contractName: tx.contract_name,
    constructorArgs: tx.constructor_args,
    constructorKwargs: tx.constructor_kwargs,
    workflowConfig: tx.workflow_config,
    preparedTransactionId: tx.prepared_transaction_id,
    intentHash: tx.intent_hash,
    preparedIntent: tx.prepared_intent,
    expiresAt: tx.expires_at,
    sourceHash: tx.source_hash,
    sourceOrigin: tx.source_origin,
    pyGenlayerDependency: tx.py_genlayer_dependency,
    genlayerSdkVersion: tx.genlayer_sdk_version,
    generatorVersion: tx.generator_version,
    validatorVersion: tx.validator_version,
    compilerVersion: tx.compiler_version,
    artifactVersion: tx.artifact_version,
  };
}

export async function buildNotaryDeployTx(
  payload: NotaryDeployTxRequestPayload,
  walletAddress: string,
  network: NetworkKey,
): Promise<NotaryDeployTxData> {
  const response = await fetch(`${API_URL}/chat/notary-deploy-tx`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(walletAddress),
    },
    body: JSON.stringify({
      address: walletAddress,
      notary_spec: payload.notary_spec,
      intent: payload.intent,
      gas_limit: payload.gas_limit ?? null,
      consensus_max_rotations: payload.consensus_max_rotations ?? null,
      leader_only: payload.leader_only ?? false,
      source_hash: payload.source_hash,
      py_genlayer_dependency: payload.py_genlayer_dependency,
      generator_version: payload.generator_version,
      validator_version: payload.validator_version,
      network,
    }),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to prepare AI Notary deployment: ${response.status}`);
  }

  const tx = await response.json();
  return {
    to: tx.to as Address,
    data: tx.data as Hex,
    value: BigInt(tx.value),
    chainId: tx.chain_id,
    nonce: tx.nonce,
    gas: BigInt(tx.gas_limit),
    gasPrice: tx.gas_price ? BigInt(tx.gas_price) : undefined,
    maxFeePerGas: tx.max_fee_per_gas ? BigInt(tx.max_fee_per_gas) : undefined,
    maxPriorityFeePerGas: tx.max_priority_fee_per_gas ? BigInt(tx.max_priority_fee_per_gas) : undefined,
    code: tx.code,
    contractName: tx.contract_name,
    constructorArgs: tx.constructor_args,
    constructorKwargs: tx.constructor_kwargs,
    notarySpec: tx.notary_spec,
    preparedTransactionId: tx.prepared_transaction_id,
    intentHash: tx.intent_hash,
    preparedIntent: tx.prepared_intent,
    expiresAt: tx.expires_at,
    sourceHash: tx.source_hash,
    sourceOrigin: tx.source_origin,
    pyGenlayerDependency: tx.py_genlayer_dependency,
    genlayerSdkVersion: tx.genlayer_sdk_version,
    generatorVersion: tx.generator_version,
    validatorVersion: tx.validator_version,
    compilerVersion: tx.compiler_version,
    artifactVersion: tx.artifact_version,
  };
}

export async function buildNotaryCallTx(
  payload: NotaryCallTxRequestPayload,
  walletAddress: string,
  network: NetworkKey,
): Promise<DeployTxData> {
  const response = await fetch(`${API_URL}/chat/notary-call-tx`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(walletAddress),
    },
    body: JSON.stringify({
      address: walletAddress,
      contract_address: payload.contract_address,
      notary_action: payload.notary_action,
      claim_id: payload.claim_id,
      notary_spec: payload.notary_spec,
      intent: payload.intent,
      gas_limit: payload.gas_limit ?? null,
      consensus_max_rotations: payload.consensus_max_rotations ?? null,
      leader_only: payload.leader_only ?? false,
      network,
    }),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to prepare AI Notary action: ${response.status}`);
  }

  const tx = await response.json();
  return {
    to: tx.to as Address,
    data: tx.data as Hex,
    value: BigInt(tx.value),
    chainId: tx.chain_id,
    nonce: tx.nonce,
    gas: BigInt(tx.gas_limit),
    gasPrice: tx.gas_price ? BigInt(tx.gas_price) : undefined,
    maxFeePerGas: tx.max_fee_per_gas ? BigInt(tx.max_fee_per_gas) : undefined,
    maxPriorityFeePerGas: tx.max_priority_fee_per_gas ? BigInt(tx.max_priority_fee_per_gas) : undefined,
    preparedTransactionId: tx.prepared_transaction_id,
    intentHash: tx.intent_hash,
    preparedIntent: tx.prepared_intent,
    expiresAt: tx.expires_at,
  };
}

export interface ContractCallTxRequestPayload {
  contract_address: string;
  method: string;
  intent?: Intent;
  args?: unknown[];
  kwargs?: Record<string, unknown>;
  value_wei?: string;
  gas_limit?: number | null;
  consensus_max_rotations?: number | null;
  leader_only?: boolean;
  workflow_type?: string;
}

export async function buildContractCallTx(
  payload: ContractCallTxRequestPayload,
  walletAddress: string,
  network: NetworkKey
): Promise<DeployTxData> {
  const response = await fetch(`${API_URL}/chat/contract-call-tx`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(walletAddress),
    },
    body: JSON.stringify({
      address: walletAddress,
      contract_address: payload.contract_address,
      method: payload.method,
      intent: payload.intent,
      args: payload.args ?? [],
      kwargs: payload.kwargs ?? {},
      value_wei: payload.value_wei ?? '0',
      gas_limit: payload.gas_limit ?? null,
      consensus_max_rotations: payload.consensus_max_rotations ?? null,
      leader_only: payload.leader_only ?? false,
      workflow_type: payload.workflow_type,
      network,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to prepare contract call: ${response.status}`);
  }

  const tx = await response.json();
  return {
    to: tx.to as Address,
    data: tx.data as Hex,
    value: BigInt(tx.value),
    chainId: tx.chain_id,
    nonce: tx.nonce,
    gas: BigInt(tx.gas_limit),
    gasPrice: tx.gas_price ? BigInt(tx.gas_price) : undefined,
    maxFeePerGas: tx.max_fee_per_gas ? BigInt(tx.max_fee_per_gas) : undefined,
    maxPriorityFeePerGas: tx.max_priority_fee_per_gas ? BigInt(tx.max_priority_fee_per_gas) : undefined,
    preparedTransactionId: tx.prepared_transaction_id,
    intentHash: tx.intent_hash,
    preparedIntent: tx.prepared_intent,
    expiresAt: tx.expires_at,
  };
}

export async function buildPhase9ConditionalCallTx(
  payload: ContractCallTxRequestPayload,
  walletAddress: string,
  network: NetworkKey,
): Promise<DeployTxData> {
  const response = await fetch(`${API_URL}/chat/phase9/conditional-call-tx`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(walletAddress),
    },
    body: JSON.stringify({
      address: walletAddress,
      contract_address: payload.contract_address,
      method: payload.method,
      intent: payload.intent,
      args: payload.args ?? [],
      kwargs: payload.kwargs ?? {},
      value_wei: payload.value_wei ?? '0',
      gas_limit: payload.gas_limit ?? null,
      consensus_max_rotations: payload.consensus_max_rotations ?? null,
      leader_only: payload.leader_only ?? false,
      workflow_type: 'conditional_payment',
      network,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const detail = typeof errorData.detail === 'string'
      ? errorData.detail
      : JSON.stringify(errorData.detail || {});
    throw new Error(detail || `Failed to prepare Phase 9 contract call: ${response.status}`);
  }

  const tx = await response.json();
  return {
    to: tx.to as Address,
    data: tx.data as Hex,
    value: BigInt(tx.value),
    chainId: tx.chain_id,
    nonce: tx.nonce,
    gas: BigInt(tx.gas_limit),
    gasPrice: tx.gas_price ? BigInt(tx.gas_price) : undefined,
    maxFeePerGas: tx.max_fee_per_gas ? BigInt(tx.max_fee_per_gas) : undefined,
    maxPriorityFeePerGas: tx.max_priority_fee_per_gas ? BigInt(tx.max_priority_fee_per_gas) : undefined,
    preparedTransactionId: tx.prepared_transaction_id,
    intentHash: tx.intent_hash,
    preparedIntent: tx.prepared_intent,
    expiresAt: tx.expires_at,
  };
}

export async function getWorkflowState(
  contractAddress: string,
  walletAddress: string,
  network: NetworkKey,
): Promise<WorkflowState> {
  const response = await fetch(
    `${API_URL}/chat/workflows/${encodeURIComponent(contractAddress)}/state?network=${encodeURIComponent(network)}`,
    { headers: authHeaders(walletAddress) },
  );
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to read workflow state: ${response.status}`);
  }
  return response.json() as Promise<WorkflowState>;
}

export async function getNotaryRegistries(
  walletAddress: string,
): Promise<import('@/types/Notary').NotaryRegistrySummary[]> {
  const response = await fetch(`${API_URL}/chat/notary-registries`, {
    headers: authHeaders(walletAddress),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to list AI Notary registries: ${response.status}`);
  }
  const data = await response.json();
  return data.registries;
}

export async function getNotaryRecord(
  contractAddress: string,
  claimId: string,
  walletAddress: string,
  network: NetworkKey,
): Promise<{
  contract_address: string;
  network: NetworkKey;
  record: import('@/types/Notary').NotaryRecord;
  transaction_hash_variant: 'latest-final';
}> {
  const response = await fetch(
    `${API_URL}/chat/notary-registries/${encodeURIComponent(contractAddress)}/claims/${encodeURIComponent(claimId)}?network=${encodeURIComponent(network)}`,
    { headers: authHeaders(walletAddress) },
  );
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to read AI Notary claim: ${response.status}`);
  }
  return response.json();
}

export interface GenerateContractResult {
  code: string;
  contract_name: string;
  valid: boolean;
  errors: string[];
  warnings: string[];
  message: string;
  source_hash: string;
  source_origin: 'generated';
  py_genlayer_dependency: string;
  genlayer_sdk_version: string;
  generator_version: string;
  validator_version: string;
  compiler_version: string;
  artifact_version: number;
}

export async function generateContract(
  intent: {
    contract_type?: string;
    logic_description?: string;
    contract_name?: string;
    amount?: number;
    recipient?: string;
    condition?: string;
    advanced?: boolean;
  },
  walletAddress: string
): Promise<GenerateContractResult> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30000);
  try {
    const response = await fetch(`${API_URL}/chat/generate-contract`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders(walletAddress),
      },
      body: JSON.stringify({ intent }),
      signal: controller.signal,
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Failed to generate contract: ${response.status}`);
    }
    return response.json();
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('Contract generation timed out. Please try again.');
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}
