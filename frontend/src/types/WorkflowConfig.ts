// Workflow Types and Configuration

export type WorkflowType = 'conditional_payment' | 'escrow' | 'subscription' | 'bounty';

export type PaymentFrequency = 'daily' | 'weekly' | 'monthly' | 'yearly';

// Base workflow configuration
export interface WorkflowConfig {
  workflowType: WorkflowType;
  token: string;
  validated: boolean;
  errors: string[];
}

// Conditional Payment Workflow
export interface ConditionalPaymentConfig extends WorkflowConfig {
  workflowType: 'conditional_payment';
  recipient: string;
  amount: number;
  condition: string;
}

// Escrow Workflow
export interface EscrowConfig extends WorkflowConfig {
  workflowType: 'escrow';
  buyer: string;
  seller: string;
  amount: number;
  description?: string;
}

// Subscription Workflow
export interface SubscriptionConfig extends WorkflowConfig {
  workflowType: 'subscription';
  recipient: string;
  amount: number;
  frequency: PaymentFrequency;
  nextPaymentDate?: string;
}

// Bounty Workflow
export interface BountyConfig extends WorkflowConfig {
  workflowType: 'bounty';
  title: string;
  reward: number;
  description?: string;
}

// Union type for all workflow configs
export type AnyWorkflowConfig =
  | ConditionalPaymentConfig
  | EscrowConfig
  | SubscriptionConfig
  | BountyConfig;

// Contract Template Information
export interface ContractTemplate {
  name: string;
  workflowType: WorkflowType;
  description: string;
  requiredParams: string[];
  optionalParams: string[];
  pythonTemplate: string;
}

// Workflow Dashboard State
export interface WorkflowDashboardState {
  workflowType: WorkflowType;
  config: AnyWorkflowConfig;
  contractAddress?: string;
  deploymentTxHash?: string;
  status: 'configuring' | 'deploying' | 'active' | 'completed' | 'cancelled';
  createdAt: string;
  updatedAt: string;
}
