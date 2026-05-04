'use client';

import React, { useState, useRef, useEffect } from 'react';
import { useWallet } from '../context/WalletContext';
import { Wallet, LogOut, Copy, Check, AlertCircle, Loader2 } from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';
import { getWalletBalance } from '../lib/api';

export default function ConnectWalletButton() {
  const { account, isConnected, isConnecting, error, connect, disconnect } = useWallet();
  const [isOpen, setIsOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [balance, setBalance] = useState<number | null>(null);
  const [isBalanceLoading, setIsBalanceLoading] = useState(false);
  const [balanceError, setBalanceError] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const formatAddress = (addr: string) => {
    return `${addr.substring(0, 6)}...${addr.substring(addr.length - 4)}`;
  };

  const handleCopy = () => {
    if (account) {
      navigator.clipboard.writeText(account);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const walletLabel = account
    ? `${formatAddress(account)}${balance !== null ? ` · ${balance.toFixed(4)} GEN` : isBalanceLoading ? ' · loading' : ' · --'}`
    : 'Connect Wallet';

  useEffect(() => {
    const fetchBalance = async () => {
      if (!account || !isConnected) {
        setBalance(null);
        setBalanceError(null);
        return;
      }

      setIsBalanceLoading(true);
      setBalanceError(null);

      try {
        const data = await getWalletBalance(account);
        setBalance(data.balance);
      } catch (err) {
        console.error(err);
        setBalance(null);
        setBalanceError('Unable to load balance');
      } finally {
        setIsBalanceLoading(false);
      }
    };

    fetchBalance();
  }, [account, isConnected]);

  if (isConnecting) {
    return (
      <button disabled className="flex items-center gap-2 px-3 py-1.5 bg-bg-base border border-border-strong text-[11px] font-mono text-text-muted cursor-not-allowed">
        <Loader2 size={12} className="animate-spin" />
        Connecting...
      </button>
    );
  }

  if (!isConnected) {
    return (
      <div className="flex items-center gap-2">
        {error && (
          <span className="text-[10px] text-accent-danger font-mono uppercase flex items-center gap-1">
            <AlertCircle size={10} /> {error}
          </span>
        )}
        <button 
          onClick={connect}
          className="flex items-center gap-2 px-3 py-1.5 bg-black border border-accent-primary text-accent-primary hover:bg-accent-primary hover:text-black text-[11px] font-mono font-bold uppercase tracking-widest transition-colors shadow-none"
        >
          <Wallet size={12} />
          Connect Wallet
        </button>
      </div>
    );
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center gap-2 px-3 py-1.5 bg-black border ${isOpen ? 'border-text-primary text-text-primary' : 'border-border-strong text-text-secondary'} hover:border-text-primary hover:text-text-primary text-[11px] font-mono uppercase transition-colors`}
      >
        <span className="flex h-1.5 w-1.5 bg-accent-success shadow-[0_0_5px_rgba(212,255,0,0.8)]"></span>
        {walletLabel}
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: -5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -5 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 top-full mt-1 w-48 bg-bg-elevated border border-border-strong shadow-2xl z-50 overflow-hidden"
          >
            <div className="p-3 border-b border-border-subtle bg-bg-base">
              <span className="text-[10px] text-text-muted font-mono uppercase tracking-widest">Active Connection</span>
              <div className="mt-2 text-[11px] font-mono text-text-primary">
                {isBalanceLoading ? (
                  <span className="inline-flex items-center gap-1 text-text-muted">
                    <Loader2 size={11} className="animate-spin" />
                    Loading balance...
                  </span>
                ) : balanceError ? (
                  <span className="text-accent-danger">{balanceError}</span>
                ) : (
                  <span>
                    AVAILABLE: <span className="text-accent-primary">{balance ?? 0} GEN</span>
                  </span>
                )}
              </div>
            </div>
            
            <div className="p-1 flex flex-col">
              <button 
                onClick={handleCopy}
                className="w-full text-left px-3 py-2 text-[11px] font-mono text-text-primary hover:bg-bg-surface hover:text-accent-primary transition-colors flex items-center justify-between group"
              >
                <span className="flex items-center gap-2">
                  {copied ? <Check size={12} className="text-accent-success" /> : <Copy size={12} className="text-text-muted group-hover:text-accent-primary" />}
                  {copied ? 'COPIED!' : 'Copy address'}
                </span>
              </button>
              
              <button 
                onClick={() => {
                  disconnect();
                  setIsOpen(false);
                }}
                className="w-full text-left px-3 py-2 text-[11px] font-mono text-accent-danger hover:bg-accent-danger/10 transition-colors flex items-center gap-2"
              >
                <LogOut size={12} />
                Disconnect
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
