'use client';

import { useState, useEffect } from 'react';
import { Wallet, LogOut } from 'lucide-react';
import { registerUser, getPlatformWallet, setWalletAuth, clearWalletAuth } from '../lib/api';

interface WalletConnectProps {
  onWalletConnected?: (address: string) => void;
  onWalletDisconnected?: () => void;
}

export default function WalletConnect({ onWalletConnected, onWalletDisconnected }: WalletConnectProps) {
  const [connectedAddress, setConnectedAddress] = useState<string | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load wallet from localStorage on mount
  useEffect(() => {
    const savedAddress = localStorage.getItem('connectedWallet');
    if (savedAddress) {
      setConnectedAddress(savedAddress);
      setWalletAuth(savedAddress);
    }
  }, []);

  const connectWallet = async () => {
    setIsConnecting(true);
    setError(null);

    try {
      // Check if MetaMask or other Web3 provider exists
      const ethereum = (window as any).ethereum;
      if (!ethereum) {
        setError('No Web3 wallet found. Please install MetaMask or another Web3 wallet.');
        setIsConnecting(false);
        return;
      }

      // Request account access
      const accounts = await ethereum.request({ method: 'eth_requestAccounts' });
      const address = accounts[0];

      if (!address) {
        setError('Failed to get wallet address');
        setIsConnecting(false);
        return;
      }

      // Set wallet auth in localStorage
      setWalletAuth(address);
      setConnectedAddress(address);

      // Register user and create platform wallet
      try {
        await registerUser(address);
        
        // Fetch platform wallet details to ensure it's created
        await getPlatformWallet();
        
        if (onWalletConnected) {
          onWalletConnected(address);
        }
      } catch (apiError: any) {
        console.error('API error:', apiError);
        setError(`Registration failed: ${apiError.message}`);
        setConnectedAddress(null);
        clearWalletAuth();
      }
    } catch (err: any) {
      console.error('Wallet connection error:', err);
      setError(err.message || 'Failed to connect wallet');
    } finally {
      setIsConnecting(false);
    }
  };

  const disconnectWallet = () => {
    clearWalletAuth();
    setConnectedAddress(null);
    if (onWalletDisconnected) {
      onWalletDisconnected();
    }
  };

  const formatAddress = (address: string) => {
    return `${address.slice(0, 6)}...${address.slice(-4)}`;
  };

  if (connectedAddress) {
    return (
      <div className="flex items-center gap-2 px-4 py-2 bg-green-50 border border-green-200 rounded-lg">
        <Wallet className="w-4 h-4 text-green-600" />
        <span className="text-sm font-medium text-green-800">
          {formatAddress(connectedAddress)}
        </span>
        <button
          onClick={disconnectWallet}
          className="ml-2 p-1 hover:bg-red-100 rounded transition-colors"
          title="Disconnect wallet"
        >
          <LogOut className="w-4 h-4 text-red-600" />
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <button
        onClick={connectWallet}
        disabled={isConnecting}
        className="flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        <Wallet className="w-4 h-4" />
        {isConnecting ? 'Connecting...' : 'Connect Wallet'}
      </button>
      {error && (
        <p className="text-sm text-red-600 text-center">{error}</p>
      )}
    </div>
  );
}
