export interface Intent {
  action: 'transfer' | 'check_balance' | 'create_contract' | 'unknown';
  amount?: number;
  token?: string;
  recipient?: string;
  [key: string]: any;
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
  status?: 'pending' | 'simulating' | 'awaiting_confirmation' | 'executing' | 'success' | 'error';
  txHash?: string;
}

import { API_BASE_URL as API_URL } from '@/config';

export interface WalletBalanceResponse {
  address: string;
  balance: number;
  token: string;
}

export async function sendMessage(content: string, walletAddress?: string): Promise<Partial<MessageData>> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);

  try {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };

    const body = walletAddress 
      ? { message: content, wallet_address: walletAddress }
      : { message: content };

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

export async function confirmAction(intent: Intent, walletAddress?: string, signedTransaction?: string): Promise<{ txHash?: string; balance?: number; error?: string }> {
  try {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };

    const body = {
      intent,
      ...(walletAddress && { wallet_address: walletAddress }),
      ...(signedTransaction && { signed_transaction: signedTransaction }),
    };

    const response = await fetch(`${API_URL}/chat/confirm`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
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
  }
}

export async function getWalletBalance(address?: string): Promise<WalletBalanceResponse> {
  const url = new URL(`${API_URL}/wallet/balance`);
  if (address) {
    url.searchParams.set('address', address);
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);

  try {
    const response = await fetch(url.toString(), { signal: controller.signal });
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
  rpc_url: string;
}

export async function getTxParams(address: string): Promise<TxParams> {
  const url = new URL(`${API_URL}/chat/tx-params`);
  url.searchParams.set('address', address);

  try {
    const response = await fetch(url.toString());
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
  to: string;
  value: string;
  data: string;
}

export interface DeployTxData {
  data: string;
  value: string;
}

export async function buildTransferTx(
  recipient: string,
  amount: number,
  walletAddress: string
): Promise<TransferTxData> {
  const txParams = await getTxParams(walletAddress);
  
  const valueInWei = BigInt(amount * 1e18).toString(16);
  
  return {
    to: recipient,
    value: '0x' + valueInWei,
    data: '0x',
  };
}

export async function buildDeployTx(
  code: string,
  walletAddress: string
): Promise<DeployTxData> {
  await getTxParams(walletAddress);
  
  const codeHex = Buffer.from(code).toString('hex');
  
  return {
    data: '0x' + codeHex,
    value: '0x0',
  };
}

