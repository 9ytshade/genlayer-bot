import type { SubscriptionConfig } from '@/types/WorkflowConfig';
import { WorkflowEngine } from '@/services/WorkflowEngine';

export class SubscriptionWorkflow {
  static contractName = 'SubscriptionContract';

  static getConstructorArgs(config: SubscriptionConfig, walletAddress: string): unknown[] {
    return WorkflowEngine.getConstructorArgs(config, walletAddress);
  }

  static getDashboardActions() {
    return ['pause_subscription', 'resume_subscription', 'cancel_subscription'] as const;
  }
}
