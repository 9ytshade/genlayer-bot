'use client';

import React, { createContext, useContext, useState, ReactNode } from 'react';
import { useAccount, useDisconnect, useSwitchChain, useWalletClient } from 'wagmi';
import { useConnectModal } from '@rainbow-me/rainbowkit';
import type { Address, Hash, Hex } from 'viem';

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

  const connect = async () => {
    setError(null);
    if (openConnectModal) {
      openConnectModal();
    } else {
      setError('Unable to open connect modal. You may already be connected.');
    }
  };

  const disconnect = () => {
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
