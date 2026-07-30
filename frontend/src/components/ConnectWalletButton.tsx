'use client';

import React, { useState, useRef, useEffect } from 'react';
import { useWallet } from '../context/WalletContext';
import { Wallet, LogOut, Copy, Check, AlertCircle, Loader2 } from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';
import { getWalletBalance } from '../lib/api';
import type { NetworkKey } from '@/config';

interface ConnectWalletButtonProps {
  network: NetworkKey;
}

export default function ConnectWalletButton({ network }: ConnectWalletButtonProps) {
  const { account, isConnected, isConnecting, error, connect, disconnect, balanceRefreshNonce } = useWallet();
  const [isOpen, setIsOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [balance, setBalance] = useState<number | null>(null);
  const [isBalanceLoading, setIsBalanceLoading] = useState(false);
  const [balanceError, setBalanceError] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const formatAddress = (addr: string) => `${addr.substring(0, 6)}...${addr.substring(addr.length - 4)}`;

  const handleCopy = () => {
    if (account) {
      navigator.clipboard.writeText(account);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const balanceLabel = balance !== null ? `${balance.toFixed(4)} GEN` : isBalanceLoading ? 'loading' : '-- GEN';

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
        const data = await getWalletBalance(account, network);
        setBalance(data.balance);
      } catch {
        setBalance(null);
        setBalanceError('Unable to load balance');
      } finally {
        setIsBalanceLoading(false);
      }
    };

    fetchBalance();
  }, [account, isConnected, network, balanceRefreshNonce]);

  if (isConnecting) {
    return (
      <button disabled className="control-button flex items-center gap-2 rounded-[8px] px-3 py-1.5 font-mono text-[11px]">
        <Loader2 size={12} className="animate-spin" />
        Connecting...
      </button>
    );
  }

  if (!isConnected) {
    return (
      <div className="flex items-center gap-2">
        {error && (
          <span className="hidden items-center gap-1 font-mono text-[10px] uppercase text-accent-danger sm:flex">
            <AlertCircle size={10} /> {error}
          </span>
        )}
        <button
          onClick={connect}
          className="primary-action flex items-center gap-2 rounded-[8px] px-3 py-1.5 font-mono text-[11px] font-bold uppercase tracking-[0.08em]"
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
        className={`control-button flex max-w-[190px] items-start gap-2 rounded-full px-3 py-2 font-mono sm:max-w-[220px] ${isOpen ? 'border-text-primary text-text-primary' : ''}`}
      >
        <span className="mt-1 flex h-1.5 w-1.5 shrink-0 rounded-full bg-accent-success shadow-[0_0_10px_rgba(212,255,0,0.45)]"></span>
        {account ? (
          <span className="flex min-w-0 flex-col items-start gap-0.5 leading-none">
            <span className="max-w-full truncate text-[9px] font-semibold uppercase tracking-[0.04em] sm:text-[10px]">
              {formatAddress(account)}
            </span>
            <span className="max-w-full truncate text-[9px] text-text-secondary sm:text-[10px]">
              {balanceLabel}
            </span>
          </span>
        ) : (
          <span className="text-[10px] uppercase">Connect Wallet</span>
        )}
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: -5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -5 }}
            transition={{ duration: 0.15 }}
            className="panel absolute right-0 top-full z-50 mt-2 w-72 overflow-hidden rounded-[8px] shadow-2xl"
          >
            <div className="border-b border-border-subtle bg-bg-base p-3">
              <span className="micro-label">Active connection</span>
              <div className="mt-2 font-mono text-[11px] text-text-primary">
                {isBalanceLoading ? (
                  <span className="inline-flex items-center gap-1 text-text-muted">
                    <Loader2 size={11} className="animate-spin" />
                    Loading balance...
                  </span>
                ) : balanceError ? (
                  <span className="text-accent-danger">{balanceError}</span>
                ) : (
                  <span>
                    Available: <span className="text-accent-primary">{balance ?? 0} GEN</span>
                  </span>
                )}
              </div>
            </div>

            <div className="p-1 flex flex-col">
              <button
                onClick={handleCopy}
                className="group flex w-full items-center justify-between rounded-[6px] px-3 py-2 text-left font-mono text-[11px] text-text-primary transition-colors hover:bg-bg-surface hover:text-accent-primary"
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
                className="flex w-full items-center gap-2 rounded-[6px] px-3 py-2 text-left font-mono text-[11px] text-accent-danger transition-colors hover:bg-accent-danger/10"
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
