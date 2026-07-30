import type { BountyConfig } from '@/types/WorkflowConfig';
import { WorkflowEngine } from '@/services/WorkflowEngine';

export class BountyWorkflow {
  static contractName = 'BountyContract';

  static getConstructorArgs(config: BountyConfig, walletAddress: string): unknown[] {
    return WorkflowEngine.getConstructorArgs(config, walletAddress);
  }

  static getDashboardActions() {
    return ['review_submission', 'select_winner', 'close_bounty'] as const;
  }
}
