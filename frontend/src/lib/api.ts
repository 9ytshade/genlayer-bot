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

export async function sendMessage(content: string): Promise<Partial<MessageData>> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);

  try {
    const token = localStorage.getItem('authToken');
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };
    
    if (token) {
      headers['Authorization'] = token;
    }

    const response = await fetch(`${API_URL}/chat`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ message: content }),
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

export async function confirmAction(intent: Intent): Promise<{ txHash?: string; error?: string }> {
  try {
    const token = localStorage.getItem('authToken');
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };
    
    if (token) {
      headers['Authorization'] = token;
    }

    const response = await fetch(`${API_URL}/chat/confirm`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ intent }),
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
