'use client';

import React, { createContext, useContext, useState, ReactNode } from 'react';
import { useAccount, useDisconnect, useWalletClient } from 'wagmi';
import { useConnectModal } from '@rainbow-me/rainbowkit';

interface WalletContextType {
  account: string | null;
  isConnected: boolean;
  isConnecting: boolean;
  error: string | null;
  connect: () => Promise<void>;
  disconnect: () => void;
  signTransaction: (txData: any) => Promise<string>;  // Returns signed raw transaction hex
}

const WalletContext = createContext<WalletContextType | undefined>(undefined);

export function WalletProvider({ children }: { children: ReactNode }) {
  const { address, isConnected } = useAccount();
  const { disconnect: wagmiDisconnect } = useDisconnect();
  const { openConnectModal } = useConnectModal();
  const [error, setError] = useState<string | null>(null);

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

  const signTransaction = async (txData: any): Promise<string> => {
    if (!account) {
      throw new Error('No account connected');
    }

    if (!walletClient) {
      throw new Error('Wallet client is not available yet');
    }

    try {
      const signature = await walletClient.signTransaction({
        account,
        ...txData,
      });

      return signature;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to sign transaction';
      setError(message);
      throw err;
    }
  };

  return (
    <WalletContext.Provider value={{ account, isConnected, isConnecting: false, error, connect, disconnect, signTransaction }}>
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

// Add TypeScript support for window.ethereum
declare global {
  interface Window {
    ethereum?: any;
  }
}
