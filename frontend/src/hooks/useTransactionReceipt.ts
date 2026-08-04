'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  waitForReceipt,
  type TransactionReceipt,
  type ReceiptOptions,
} from '@/services/genlayerClient';
import type { NetworkKey } from '@/config';

interface UseTransactionReceiptResult {
  receipt: TransactionReceipt | null;
  status: TransactionReceipt['status'] | null;
  isLoading: boolean;
  error: string | null;
}

/**
 * React hook for polling a GenLayer transaction receipt.
 *
 * Automatically starts polling when a txHash is provided and stops
 * once the transaction reaches a terminal state (finalized or undetermined).
 *
 * @param txHash - The transaction hash to poll
 * @param network - Network to query (defaults to 'studionet')
 * @param opts - Polling interval and timeout options
 *
 * @example
 * ```tsx
 * const { receipt, status, isLoading } = useTransactionReceipt(
 *   '0xabc...',
 *   'studionet'
 * );
 *
 * if (status === 'finalized') {
 *   console.log('Contract address:', receipt?.contractAddress);
 * }
 * ```
 */
export function useTransactionReceipt(
  txHash: string | null | undefined,
  network: NetworkKey = 'studionet',
  opts?: ReceiptOptions
): UseTransactionReceiptResult {
  const [receipt, setReceipt] = useState<TransactionReceipt | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pollReceipt = useCallback(async () => {
    if (!txHash) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const result = await waitForReceipt(network, txHash, {
        pollingInterval: opts?.pollingInterval ?? 3000,
        timeout: opts?.timeout ?? 120000,
      });
      setReceipt(result);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to get transaction receipt';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [txHash, network, opts?.pollingInterval, opts?.timeout]);

  useEffect(() => {
    pollReceipt();
  }, [pollReceipt]);

  return {
    receipt,
    status: receipt?.status ?? null,
    isLoading,
    error,
  };
}
