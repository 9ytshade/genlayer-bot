import type { EscrowConfig } from '@/types/WorkflowConfig';
import { WorkflowEngine } from '@/services/WorkflowEngine';

export class EscrowWorkflow {
  static contractName = 'EscrowContract';

  static getConstructorArgs(config: EscrowConfig, walletAddress: string): unknown[] {
    return WorkflowEngine.getConstructorArgs(config, walletAddress);
  }

  static getDashboardActions() {
    return ['approve_release', 'raise_dispute', 'cancel_escrow'] as const;
  }
}
