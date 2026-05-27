'use client';

import React from 'react';
import '@rainbow-me/rainbowkit/styles.css';
import { RainbowKitProvider, getDefaultConfig } from '@rainbow-me/rainbowkit';
import { WagmiConfig } from 'wagmi';
import type { Chain } from 'viem';
import { QueryClientProvider, QueryClient } from '@tanstack/react-query';
import { NETWORK_CONFIG } from '@/config';

const projectId = process.env.NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID || 'YOUR_PROJECT_ID';

if (!process.env.NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID && typeof window !== 'undefined') {
  console.warn('NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID is not set. WalletConnect may not work in production.');
}

const bradburyChain: Chain = {
  id: NETWORK_CONFIG.bradbury.chainId,
  name: 'GenLayer Bradbury',
  nativeCurrency: { name: 'GEN', symbol: 'GEN', decimals: 18 },
  rpcUrls: {
    default: { http: [NETWORK_CONFIG.bradbury.rpcUrl] },
    public: { http: [NETWORK_CONFIG.bradbury.rpcUrl] },
  },
  blockExplorers: {
    default: { name: 'GenLayer Explorer', url: 'https://explorer.genlayer.com' },
  },
};

const studionetChain: Chain = {
  id: NETWORK_CONFIG.studionet.chainId,
  name: 'GenLayer Studionet',
  nativeCurrency: { name: 'GEN', symbol: 'GEN', decimals: 18 },
  rpcUrls: {
    default: { http: [NETWORK_CONFIG.studionet.rpcUrl] },
    public: { http: [NETWORK_CONFIG.studionet.rpcUrl] },
  },
  blockExplorers: {
    default: { name: 'GenLayer Studio', url: 'https://studio.genlayer.com' },
  },
};

const config = getDefaultConfig({
  appName: 'GenLayer AI Bot',
  projectId,
  chains: [bradburyChain, studionetChain],
  ssr: true,
});

const queryClient = new QueryClient();

export function Web3Provider({ children }: { children: React.ReactNode }) {
  return (
    <WagmiConfig config={config}>
      <QueryClientProvider client={queryClient}>
        <RainbowKitProvider>
          {children}
        </RainbowKitProvider>
      </QueryClientProvider>
    </WagmiConfig>
  );
}
