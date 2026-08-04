'use client';

import { useState, useEffect, useCallback } from 'react';
import { readContract, type ReadContractParams } from '@/services/genlayerClient';
import type { NetworkKey } from '@/config';

interface UseContractReadResult {
  data: unknown;
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
}

/**
 * React hook for reading deployed GenLayer contract state.
 *
 * @param contractAddress - The deployed contract address
 * @param method - The view method to call
 * @param args - Optional arguments to pass to the method
 * @param network - Network to query (defaults to 'studionet')
 * @param enabled - Whether to auto-fetch on mount (defaults to true)
 *
 * @example
 * ```tsx
 * const { data, isLoading, error, refetch } = useContractRead(
 *   '0x1234...',
 *   'status',
 *   [],
 *   'studionet'
 * );
 * ```
 */
export function useContractRead(
  contractAddress: string | null | undefined,
  method: string,
  args: unknown[] = [],
  network: NetworkKey = 'studionet',
  enabled: boolean = true
): UseContractReadResult {
  const [data, setData] = useState<unknown>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    if (!contractAddress || !method || !enabled) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const params: ReadContractParams = {
        address: contractAddress,
        method,
        args,
      };
      const result = await readContract(network, params);
      setData(result);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to read contract';
      setError(message);
      setData(null);
    } finally {
      setIsLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contractAddress, method, JSON.stringify(args), network, enabled]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return {
    data,
    isLoading,
    error,
    refetch: fetchData,
  };
}
