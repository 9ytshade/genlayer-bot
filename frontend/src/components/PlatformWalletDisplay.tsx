'use client';

import { useState, useEffect } from 'react';
import { Copy, RefreshCw, CreditCard } from 'lucide-react';

interface PlatformWallet {
  id: number;
  user_id: number;
  address: string;
  balance: number;
  created_at: string;
}

interface PlatformWalletDisplayProps {
  connectedWallet?: string;
}

export default function PlatformWalletDisplay({ connectedWallet }: PlatformWalletDisplayProps) {
  const [wallet, setWallet] = useState<PlatformWallet | null>(null);
  const [loading, setLoading] = useState(false);
  const [fundAmount, setFundAmount] = useState('');
  const [fundingStatus, setFundingStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [fundingError, setFundingError] = useState('');
  const [copied, setCopied] = useState(false);

  const fetchWallet = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('authToken');
      if (!token) {
        throw new Error('Not authenticated');
      }

      const response = await fetch('http://localhost:8000/users/me/wallet', {
        headers: {
          'Authorization': token,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch wallet');
      }

      const data = await response.json();
      setWallet(data);
    } catch (error: any) {
      console.error('Error fetching wallet:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (connectedWallet) {
      fetchWallet();
    }
  }, [connectedWallet]);

  const handleFundWallet = async () => {
    if (!fundAmount || parseFloat(fundAmount) <= 0) {
      setFundingError('Please enter a valid amount');
      return;
    }

    setFundingStatus('loading');
    setFundingError('');

    try {
      const token = localStorage.getItem('authToken');
      if (!token) {
        throw new Error('Not authenticated');
      }

      const response = await fetch('http://localhost:8000/wallet/fund', {
        method: 'POST',
        headers: {
          'Authorization': token,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          amount: parseFloat(fundAmount),
        }),
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Failed to fund wallet');
      }

      const result = await response.json();
      setFundingStatus('success');
      setFundAmount('');
      
      // Refresh wallet balance after 2 seconds
      setTimeout(() => {
        fetchWallet();
        setFundingStatus('idle');
      }, 2000);
    } catch (error: any) {
      setFundingError(error.message);
      setFundingStatus('error');
    }
  };

  const copyAddress = () => {
    if (wallet) {
      navigator.clipboard.writeText(wallet.address);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const formatAddress = (address: string) => {
    return `${address.slice(0, 6)}...${address.slice(-4)}`;
  };

  if (!connectedWallet) {
    return null;
  }

  if (loading) {
    return (
      <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
        <p className="text-gray-600">Loading platform wallet...</p>
      </div>
    );
  }

  if (!wallet) {
    return (
      <div className="p-4 bg-yellow-50 rounded-lg border border-yellow-200">
        <p className="text-yellow-800">No platform wallet found</p>
      </div>
    );
  }

  return (
    <div className="space-y-4 p-4 bg-gradient-to-br from-blue-50 to-indigo-50 rounded-lg border border-indigo-200">
      {/* Wallet Address Section */}
      <div className="space-y-2">
        <h3 className="text-sm font-semibold text-gray-700">Platform Wallet</h3>
        <div className="flex items-center justify-between p-3 bg-white rounded border border-gray-200">
          <span className="font-mono text-sm text-gray-600">
            {formatAddress(wallet.address)}
          </span>
          <button
            onClick={copyAddress}
            className="p-1 hover:bg-gray-100 rounded transition-colors"
            title="Copy full address"
          >
            <Copy className={`w-4 h-4 ${copied ? 'text-green-600' : 'text-gray-400'}`} />
          </button>
        </div>
        {copied && <p className="text-xs text-green-600">Copied!</p>}
      </div>

      {/* Balance Section */}
      <div className="space-y-2">
        <h3 className="text-sm font-semibold text-gray-700">Balance</h3>
        <div className="p-3 bg-white rounded border border-gray-200">
          <p className="text-2xl font-bold text-indigo-600">{wallet.balance} GEN</p>
          <button
            onClick={fetchWallet}
            className="mt-2 flex items-center gap-1 text-xs text-gray-600 hover:text-gray-800"
          >
            <RefreshCw className="w-3 h-3" />
            Refresh
          </button>
        </div>
      </div>

      {/* Fund Wallet Section */}
      <div className="space-y-2">
        <h3 className="text-sm font-semibold text-gray-700">Fund Wallet</h3>
        <div className="flex gap-2">
          <input
            type="number"
            value={fundAmount}
            onChange={(e) => setFundAmount(e.target.value)}
            placeholder="Amount (GEN)"
            className="flex-1 px-3 py-2 bg-white border border-gray-300 rounded text-sm"
            min="0"
            step="0.01"
            disabled={fundingStatus === 'loading'}
          />
          <button
            onClick={handleFundWallet}
            disabled={fundingStatus === 'loading' || !fundAmount}
            className="px-4 py-2 bg-indigo-600 text-white rounded text-sm hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 transition-colors"
          >
            <CreditCard className="w-4 h-4" />
            {fundingStatus === 'loading' ? 'Funding...' : 'Fund'}
          </button>
        </div>
        {fundingError && (
          <p className="text-sm text-red-600">{fundingError}</p>
        )}
        {fundingStatus === 'success' && (
          <p className="text-sm text-green-600">✓ Wallet funded successfully!</p>
        )}
      </div>
    </div>
  );
}
