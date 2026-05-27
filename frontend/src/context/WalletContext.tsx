'use client';

import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { useAccount, useDisconnect, useSwitchChain, useWalletClient } from 'wagmi';
import { useConnectModal } from '@rainbow-me/rainbowkit';
import type { Address, Hash, Hex } from 'viem';
import { clearStoredAuthToken, getNonce, getStoredAuthToken, setStoredAuthToken, verifySignature } from '@/lib/api';

interface WalletTransactionRequest {
  to?: Address;
  data?: Hex;
  value?: bigint;
  chainId?: number;
  nonce?: number;
  gas?: bigint;
  gasPrice?: bigint;
  maxFeePerGas?: bigint;
  maxPriorityFeePerGas?: bigint;
}

interface WalletContextType {
  account: Address | null;
  isConnected: boolean;
  isConnecting: boolean;
  error: string | null;
  connect: () => Promise<void>;
  disconnect: () => void;
  sendTransaction: (txData: WalletTransactionRequest) => Promise<Hash>;
  switchNetwork: (chainId: number) => Promise<void>;
  balanceRefreshNonce: number;
  refreshBalance: () => void;
}

const WalletContext = createContext<WalletContextType | undefined>(undefined);

export function WalletProvider({ children }: { children: ReactNode }) {
  const { address, isConnected } = useAccount();
  const { disconnect: wagmiDisconnect } = useDisconnect();
  const { switchChainAsync } = useSwitchChain();
  const { openConnectModal } = useConnectModal();
  const [error, setError] = useState<string | null>(null);
  const [balanceRefreshNonce, setBalanceRefreshNonce] = useState(0);

  const account = address ?? null;
  const { data: walletClient } = useWalletClient();

  useEffect(() => {
    let cancelled = false;

    async function authenticateWallet() {
      if (!address || !walletClient) {
        return;
      }

      const existingToken = getStoredAuthToken(address);
      if (existingToken) {
        setError(null);
        return;
      }

      try {
        const nonce = await getNonce(address);
        const chainId = walletClient.chain?.id ?? 1;
        const origin = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:3000';
        const host = typeof window !== 'undefined' ? window.location.host : 'localhost:3000';
        const message = [
          `${host} wants you to sign in with your Ethereum account:`,
          address,
          '',
          'Sign in to GenLayer Bot.',
          '',
          `URI: ${origin}`,
          'Version: 1',
          `Chain ID: ${chainId}`,
          `Nonce: ${nonce}`,
          `Issued At: ${new Date().toISOString()}`,
        ].join('\n');
        const signature = await walletClient.signMessage({ account: address, message });
        const token = await verifySignature(address, message, signature);
        if (!cancelled) {
          setStoredAuthToken(address, token);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          const message = err instanceof Error ? err.message : 'Wallet authentication failed';
          setError(message);
          clearStoredAuthToken(address);
        }
      }
    }

    authenticateWallet();
    return () => {
      cancelled = true;
    };
  }, [address, walletClient]);

  const connect = async () => {
    setError(null);
    if (openConnectModal) {
      openConnectModal();
    } else {
      setError('Unable to open connect modal. You may already be connected.');
    }
  };

  const disconnect = () => {
    clearStoredAuthToken(account);
    wagmiDisconnect();
  };

  const refreshBalance = () => {
    setBalanceRefreshNonce((value) => value + 1);
  };

  const switchNetwork = async (chainId: number) => {
    setError(null);
    if (!switchChainAsync) {
      throw new Error('Wallet does not support automatic network switching.');
    }

    try {
      await switchChainAsync({ chainId });
      refreshBalance();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to switch network';
      setError(message);
      throw err;
    }
  };

  const sendTransaction = async (txData: WalletTransactionRequest): Promise<Hash> => {
    if (!account) {
      throw new Error('No account connected');
    }

    if (!walletClient) {
      throw new Error('Wallet client is not available yet');
    }

    try {
      const request = txData.gasPrice !== undefined
        ? {
            account,
            to: txData.to,
            data: txData.data,
            value: txData.value,
            chainId: txData.chainId,
            nonce: txData.nonce,
            gas: txData.gas,
            gasPrice: txData.gasPrice,
          }
        : {
            account,
            to: txData.to,
            data: txData.data,
            value: txData.value,
            chainId: txData.chainId,
            nonce: txData.nonce,
            gas: txData.gas,
            maxFeePerGas: txData.maxFeePerGas,
            maxPriorityFeePerGas: txData.maxPriorityFeePerGas,
          };

      const txHash = await walletClient.sendTransaction(request);

      return txHash;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to send transaction';
      setError(message);
      throw err;
    }
  };

  return (
    <WalletContext.Provider
      value={{
        account,
        isConnected,
        isConnecting: false,
        error,
        connect,
        disconnect,
        sendTransaction,
        switchNetwork,
        balanceRefreshNonce,
        refreshBalance,
      }}
    >
      {children}
    </WalletContext.Provider>
  );
}

export function useWallet() {
  const context = useContext(WalletContext);
  if (context === undefined) {
    throw new Error('useWallet must be used within a WalletProvider');
  }
  return context;
}
