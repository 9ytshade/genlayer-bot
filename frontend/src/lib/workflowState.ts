import { formatEther } from 'viem';

export function isSameAddress(left: unknown, right: unknown): boolean {
  return typeof left === 'string'
    && typeof right === 'string'
    && left.toLowerCase() === right.toLowerCase();
}

export function formatGenWei(value: unknown): string {
  if (typeof value !== 'string' && typeof value !== 'number' && typeof value !== 'bigint') {
    return 'Unavailable';
  }
  try {
    return `${formatEther(BigInt(value))} GEN`;
  } catch {
    return 'Unavailable';
  }
}

export function readStateCount(value: unknown): string {
  if (typeof value === 'number' || typeof value === 'bigint') {
    return value.toString();
  }
  if (typeof value === 'string' && /^\d+$/.test(value)) {
    return value;
  }
  return '0';
}
