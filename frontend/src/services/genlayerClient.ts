/**
 * GenLayer JS SDK client factory.
 *
 * Wraps the official `genlayer-js` SDK for read-only operations:
 * - readContract: query deployed contract state
 * - getContractSchema: introspect contract methods/fields
 * - waitForTransactionReceipt: poll for tx finality
 *
 * Write operations remain backend-driven (safety rails, simulation, etc.).
 */

import { createClient as createGenlayerClient, chains } from 'genlayer-js';
import { NETWORK_CONFIG, type NetworkKey } from '@/config';

export interface ContractSchema {
  methods: SchemaMethod[];
  fields: SchemaField[];
}

export interface SchemaMethod {
  name: string;
  params: Array<{ name: string; type: string }>;
  returnType: string | null;
  isView: boolean;
  isWrite: boolean;
}

export interface SchemaField {
  name: string;
  type: string;
}

export interface TransactionReceipt {
  hash: string;
  status: 'pending' | 'accepted' | 'finalized' | 'undetermined';
  consensusData?: Record<string, unknown>;
  contractAddress?: string;
  blockNumber?: number;
}

export interface ReadContractParams {
  address: string;
  method: string;
  args?: unknown[];
}

export interface ReceiptOptions {
  pollingInterval?: number;
  timeout?: number;
}

function getChainConfig(network: NetworkKey) {
  const config = NETWORK_CONFIG[network];

  // Map our network keys to genlayer-js chain objects
  const chainMap: Record<string, typeof chains.studionet> = {
    bradbury: chains.testnetBradbury,
    studionet: chains.studionet,
    localnet: chains.localnet,
  };

  const baseChain = chainMap[network];

  if (baseChain) {
    return {
      ...baseChain,
      id: config.chainId,
      rpcUrls: {
        default: { http: [config.rpcUrl] },
      },
    };
  }

  // Fallback for unknown networks
  return {
    id: config.chainId,
    name: config.label,
    nativeCurrency: { name: 'GEN', symbol: 'GEN', decimals: 18 },
    rpcUrls: {
      default: { http: [config.rpcUrl] },
    },
  };
}

/**
 * Create a GenLayer client for the given network using the official SDK.
 */
export function createGenLayerClient(network: NetworkKey = 'studionet') {
  const chain = getChainConfig(network);
  return createGenlayerClient({ chain } as Parameters<typeof createGenlayerClient>[0]);
}

/**
 * Read a deployed contract's state by calling a view method.
 */
export async function readContract(
  network: NetworkKey,
  params: ReadContractParams
): Promise<unknown> {
  const client = createGenLayerClient(network);
  const result = await client.readContract({
    address: params.address as `0x${string}`,
    functionName: params.method,
    args: params.args ?? [],
  } as Parameters<typeof client.readContract>[0]);
  return result;
}

/**
 * Wait for a transaction receipt with polling.
 */
export async function waitForReceipt(
  network: NetworkKey,
  txHash: string,
  opts?: ReceiptOptions
): Promise<TransactionReceipt> {
  const client = createGenLayerClient(network);

  try {
    const receipt = await client.waitForTransactionReceipt({
      hash: txHash as `0x${string}`,
      pollingInterval: opts?.pollingInterval ?? 3000,
      timeout: opts?.timeout ?? 120000,
    } as Parameters<typeof client.waitForTransactionReceipt>[0]);

    const raw = receipt as Record<string, unknown>;
    let status: TransactionReceipt['status'] = 'pending';
    if (raw.status === 'success' || raw.status === '0x1' || raw.status === BigInt(1)) {
      status = 'finalized';
    } else if (raw.status === 'reverted' || raw.status === '0x0' || raw.status === BigInt(0)) {
      status = 'undetermined';
    } else if (raw.consensus_data) {
      status = 'accepted';
    }

    return {
      hash: txHash,
      status,
      consensusData: raw.consensus_data as Record<string, unknown> | undefined,
      contractAddress: raw.contractAddress as string | undefined,
      blockNumber: typeof raw.blockNumber === 'bigint'
        ? Number(raw.blockNumber)
        : raw.blockNumber as number | undefined,
    };
  } catch {
    return { hash: txHash, status: 'pending' };
  }
}

/**
 * Get a deployed contract's schema (methods and fields).
 * Falls back to JSON-RPC if the SDK doesn't expose a direct method.
 */
export async function getContractSchema(
  network: NetworkKey,
  contractAddress: string
): Promise<ContractSchema> {
  const config = NETWORK_CONFIG[network];

  const response = await fetch(config.rpcUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      jsonrpc: '2.0',
      id: Date.now(),
      method: 'gen_getContractSchemaForCode',
      params: [contractAddress],
    }),
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch contract schema: ${response.status}`);
  }

  const data = await response.json();
  if (data.error) {
    throw new Error(data.error.message || 'RPC error fetching schema');
  }

  const raw = data.result as Record<string, unknown>;
  const methods: SchemaMethod[] = [];
  const fields: SchemaField[] = [];

  if (Array.isArray(raw?.methods)) {
    for (const m of raw.methods) {
      methods.push({
        name: m.name ?? '',
        params: Array.isArray(m.params) ? m.params : [],
        returnType: m.return_type ?? null,
        isView: m.is_view ?? false,
        isWrite: m.is_write ?? false,
      });
    }
  }

  if (Array.isArray(raw?.fields)) {
    for (const f of raw.fields) {
      fields.push({
        name: f.name ?? '',
        type: f.type ?? 'unknown',
      });
    }
  }

  return { methods, fields };
}
