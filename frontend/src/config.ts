const defaultApiUrl = 'http://127.0.0.1:8000';
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL?.replace('localhost', '127.0.0.1') || defaultApiUrl;

export type NetworkKey = 'bradbury' | 'studionet';

export const DEFAULT_NETWORK: NetworkKey = 'bradbury';

export const NETWORK_CONFIG: Record<NetworkKey, { label: string; chainId: number; rpcUrl: string }> = {
  bradbury: {
    label: 'Bradbury',
    chainId: Number(process.env.NEXT_PUBLIC_GENLAYER_CHAIN_ID_BRADBURY || 4221),
    rpcUrl: process.env.NEXT_PUBLIC_GENLAYER_RPC_URL_BRADBURY || 'https://rpc-bradbury.genlayer.com',
  },
  studionet: {
    label: 'Studionet',
    chainId: Number(
      process.env.NEXT_PUBLIC_GENLAYER_CHAIN_ID_STUDIONET
        || process.env.NEXT_PUBLIC_GENLAYER_CHAIN_ID
        || 61999
    ),
    rpcUrl: process.env.NEXT_PUBLIC_GENLAYER_RPC_URL_STUDIONET
      || process.env.NEXT_PUBLIC_GENLAYER_RPC_URL
      || 'https://studio.genlayer.com/api',
  },
};
