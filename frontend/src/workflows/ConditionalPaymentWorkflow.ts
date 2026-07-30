import type { ConditionalPaymentConfig } from '@/types/WorkflowConfig';
import { WorkflowEngine } from '@/services/WorkflowEngine';

export class ConditionalPaymentWorkflow {
  static contractName = 'ConditionalPaymentContract';

  static getConstructorArgs(config: ConditionalPaymentConfig, walletAddress: string): unknown[] {
    return WorkflowEngine.getConstructorArgs(config, walletAddress);
  }

  static getDashboardActions() {
    return ['view_details', 'cancel_contract'] as const;
  }
}
