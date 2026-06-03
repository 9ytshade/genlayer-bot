export interface Intent {
  action: 'transfer' | 'check_balance' | 'deploy_contract' | 'generate_contract' | 'contract_review' | 'unknown';
  amount?: number;
  token?: string;
  recipient?: string;
  address?: string;
  code?: string;
  contract_name?: string;
  contract_type?: string;
  logic_description?: string;
  condition?: string;
  constructor_args?: unknown[];
  constructor_kwargs?: Record<string, unknown>;
  constructor_args_text?: string;
  constructor_kwargs_text?: string;
  deploy_value?: number;
  deploy_value_text?: string;
  gas_limit?: number | null;
  gas_limit_text?: string;
  consensus_max_rotations?: number | null;
  consensus_max_rotations_text?: string;
  leader_only?: boolean;
  source_file_name?: string;
  [key: string]: unknown;
}

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
  status?: 'pending' | 'simulating' | 'awaiting_input' | 'awaiting_confirmation' | 'executing' | 'success' | 'error';
  txHash?: string;
  consensusTxId?: string;
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
  };
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
}

const tokenKey = (address: string) => `genlayer-auth:${address.toLowerCase()}`;

export function getStoredAuthToken(address?: string | null): string | null {
  if (!address || typeof window === 'undefined') {
    return null;
  }
  return window.localStorage.getItem(tokenKey(address));
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

export interface PlatformWalletResponse {
  id: number;
  user_id: number;
  address: string;
  balance: number;
  created_at: string;
}

export async function getPlatformWallet(walletAddress: string): Promise<PlatformWalletResponse | null> {
  const response = await fetch(`${API_URL}/users/me/wallet`, {
    headers: authHeaders(walletAddress),
  });
  if (response.status === 404 || response.status === 401) {
    return null;
  }
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch platform wallet: ${response.status}`);
  }
  return response.json();
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

export async function sendMessage(content: string, walletAddress?: string, network?: NetworkKey): Promise<Partial<MessageData>> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);

  try {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...authHeaders(walletAddress),
    };

    const body = walletAddress
      ? { message: content, wallet_address: walletAddress, network }
      : { message: content, network };

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

export async function confirmAction(
  intent: Intent,
  walletAddress?: string,
  signedTransaction?: string,
  txHash?: string,
  network?: NetworkKey
): Promise<{ txHash?: string; consensusTxId?: string; contractAddress?: string; derivedAddresses?: string[]; balance?: number; content?: string; error?: string }> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 65000);
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
    };

    const response = await fetch(`${API_URL}/chat/confirm`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    
    if (!response.ok) {
       const errorData = await response.json().catch(() => ({}));
       throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }
    
    const data = await response.json();
    return data;
  } catch (error: unknown) {
    console.error("Error confirming action:", error);

    if (error instanceof TypeError) {
      return {
        error: `Unable to reach backend at ${API_URL}. Start the API server and try again.`
      };
    }

    if (error instanceof Error) {
      return { error: error.message || "Failed to confirm action." };
    }

    return { error: "Failed to confirm action." };
  } finally {
    clearTimeout(timeoutId);
  }
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

export interface TransferTxData {
  to: Address;
  value: bigint;
  data: Hex;
  chainId: number;
  nonce: number;
  gas: bigint;
  gasPrice: bigint;
}

export interface DeployTxData {
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
  network: NetworkKey
): Promise<TransferTxData> {
  const txParams = await getTxParams(walletAddress, network);

  return {
    to: recipient as Address,
    value: parseEther(amount.toString()),
    data: '0x',
    chainId: txParams.chain_id,
    nonce: txParams.nonce,
    gas: BigInt(txParams.gas_limit),
    gasPrice: BigInt(txParams.gas_price),
  };
}

export interface DeployTxRequestPayload {
  code: string;
  constructor_args?: unknown[];
  constructor_kwargs?: Record<string, unknown>;
  deploy_value_wei?: string;
  gas_limit?: number | null;
  consensus_max_rotations?: number | null;
  leader_only?: boolean;
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
      constructor_args: payload.constructor_args ?? [],
      constructor_kwargs: payload.constructor_kwargs ?? {},
      value_wei: payload.deploy_value_wei ?? '0',
      gas_limit: payload.gas_limit ?? null,
      consensus_max_rotations: payload.consensus_max_rotations ?? null,
      leader_only: payload.leader_only ?? false,
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
  };
}

export interface GenerateContractResult {
  code: string;
  contract_name: string;
  valid: boolean;
  errors: string[];
  warnings: string[];
  message: string;
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
