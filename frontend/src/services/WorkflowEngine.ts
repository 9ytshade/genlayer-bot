import type {
  WorkflowType,
  PaymentFrequency,
  AnyWorkflowConfig,
  ConditionalPaymentConfig,
  EscrowConfig,
  SubscriptionConfig,
  BountyConfig,
} from '@/types/WorkflowConfig';
import type { Intent } from '@/lib/api';
import { ContractRegistry } from './ContractRegistry';

/**
 * Check if a string is a valid Ethereum address
 */
function isValidEthereumAddress(address: string): boolean {
  return /^0x[a-fA-F0-9]{40}$/.test((address || '').trim());
}

const ADDRESS_REGEX = /0x[a-fA-F0-9]{40}/g;
const AMOUNT_REGEX = /(\d+(?:\.\d+)?)\s*(GEN|ETH|TOKEN|TOKENS)?/i;

function extractAddresses(text: string): string[] {
  return text.match(ADDRESS_REGEX) || [];
}

function extractAmount(text: string): number | null {
  const match = text.match(AMOUNT_REGEX);
  return match ? Number(match[1]) : null;
}

function extractToken(text: string): string {
  const match = text.match(/\b(GEN|ETH)\b/i);
  return (match?.[1] || 'GEN').toUpperCase();
}

function extractEscrowDescription(text: string): string {
  const releaseMatch = text.match(/\b(?:when|after)\b\s+(.+)$/i);
  return releaseMatch?.[1]?.trim().replace(/[.?!]+$/, '') || text.trim();
}

function amountToUnits(amount: number): number {
  return Math.max(1, Math.round(amount));
}

export class WorkflowEngine {
  /**
   * Detect workflow type from user intent
   */
  static detectWorkflow(intent: Intent): WorkflowType | null {
    if (intent.action === 'conditional_payment') return 'conditional_payment';
    if (intent.action === 'escrow') return 'escrow';
    if (intent.action === 'subscription') return 'subscription';
    if (intent.action === 'bounty') return 'bounty';
    return null;
  }

  static detectWorkflowFromText(message: string): WorkflowType | null {
    const text = message.toLowerCase();
    if (/\b(bounty|reward|bug bounty)\b/.test(text)) return 'bounty';
    if (/\b(subscription|recurring|every day|daily|weekly|monthly|yearly|every week|every month|every friday)\b/.test(text)) {
      return 'subscription';
    }
    if (/\b(escrow|designer|safely hire|after .* delivered|release .* after)\b/.test(text)) return 'escrow';
    if (/\b(if|when|whenever|condition|reaches|exceeds|above|below)\b/.test(text) && /\b(pay|send)\b/.test(text)) {
      return 'conditional_payment';
    }
    return null;
  }

  static parseNaturalLanguage(message: string, walletAddress: string): {
    config: AnyWorkflowConfig | null;
    intent: Intent | null;
    errors: string[];
  } {
    const workflowType = this.detectWorkflowFromText(message);
    if (!workflowType) {
      return { config: null, intent: null, errors: [] };
    }

    const amount = extractAmount(message);
    const token = extractToken(message);
    const addresses = extractAddresses(message);
    const base = { token, validated: false, errors: [] as string[] };
    let config: AnyWorkflowConfig | null = null;

    if (workflowType === 'conditional_payment') {
      const condition = this.extractCondition(message);
      config = {
        workflowType,
        recipient: addresses[0] || '',
        amount: amount || 0,
        condition,
        ...base,
      };
    }

    if (workflowType === 'escrow') {
      const [firstAddress, secondAddress] = addresses;
      const buyer = secondAddress ? firstAddress : walletAddress || '';
      const seller = secondAddress || firstAddress || '';
      config = {
        workflowType,
        buyer,
        seller,
        amount: amount || 0,
        description: extractEscrowDescription(message),
        ...base,
      };
    }

    if (workflowType === 'subscription') {
      config = {
        workflowType,
        recipient: addresses[0] || '',
        amount: amount || 0,
        frequency: this.extractFrequency(message),
        nextPaymentDate: this.getNextPaymentLabel(this.extractFrequency(message)),
        ...base,
      };
    }

    if (workflowType === 'bounty') {
      config = {
        workflowType,
        title: this.extractBountyTitle(message),
        reward: amount || 0,
        description: message,
        ...base,
      };
    }

    if (!config) {
      return { config: null, intent: null, errors: ['Unable to configure workflow.'] };
    }

    const validation = this.validateConfig(config);
    const intent = this.buildIntentFromConfig(config);
    return { config, intent, errors: validation.errors };
  }

  static buildIntentFromConfig(config: AnyWorkflowConfig): Intent {
    switch (config.workflowType) {
      case 'conditional_payment':
        return {
          action: 'conditional_payment',
          recipient: config.recipient,
          amount: config.amount,
          token: config.token,
          condition: config.condition,
        };
      case 'escrow':
        return {
          action: 'escrow',
          buyer: config.buyer,
          seller: config.seller,
          amount: config.amount,
          token: config.token,
          description: config.description,
        };
      case 'subscription':
        return {
          action: 'subscription',
          recipient: config.recipient,
          amount: config.amount,
          token: config.token,
          frequency: config.frequency,
        };
      case 'bounty':
        return {
          action: 'bounty',
          title: config.title,
          reward: config.reward,
          token: config.token,
          description: config.description,
        };
    }
  }

  /**
   * Build workflow configuration from intent
   */
  static buildWorkflowConfig(
    intent: Intent
  ): AnyWorkflowConfig | null {
    const workflowType = this.detectWorkflow(intent);
    if (!workflowType) return null;

    const baseConfig = {
      token: intent.token || 'GEN',
      validated: false,
      errors: [] as string[],
    };

    switch (workflowType) {
      case 'conditional_payment':
        return this.buildConditionalPaymentConfig(intent, baseConfig);
      case 'escrow':
        return this.buildEscrowConfig(intent, baseConfig);
      case 'subscription':
        return this.buildSubscriptionConfig(intent, baseConfig);
      case 'bounty':
        return this.buildBountyConfig(intent, baseConfig);
      default:
        return null;
    }
  }

  private static buildConditionalPaymentConfig(
    intent: Intent,
    baseConfig: Partial<ConditionalPaymentConfig>
  ): ConditionalPaymentConfig | null {
    if (!intent.recipient || !intent.amount || !intent.condition) {
      return null;
    }

    return {
      workflowType: 'conditional_payment',
      recipient: intent.recipient,
      amount: intent.amount,
      condition: intent.condition,
      ...baseConfig,
    } as ConditionalPaymentConfig;
  }

  private static buildEscrowConfig(
    intent: Intent,
    baseConfig: Partial<EscrowConfig>
  ): EscrowConfig | null {
    if (!intent.buyer || !intent.seller || !intent.amount) {
      return null;
    }

    return {
      workflowType: 'escrow',
      buyer: intent.buyer,
      seller: intent.seller,
      amount: intent.amount,
      description: intent.description,
      ...baseConfig,
    } as EscrowConfig;
  }

  private static buildSubscriptionConfig(
    intent: Intent,
    baseConfig: Partial<SubscriptionConfig>
  ): SubscriptionConfig | null {
    if (!intent.recipient || !intent.amount || !intent.frequency) {
      return null;
    }

    return {
      workflowType: 'subscription',
      recipient: intent.recipient,
      amount: intent.amount,
        frequency: intent.frequency as PaymentFrequency,
      ...baseConfig,
    } as SubscriptionConfig;
  }

  private static buildBountyConfig(
    intent: Intent,
    baseConfig: Partial<BountyConfig>
  ): BountyConfig | null {
    if (!intent.title || !intent.reward) {
      return null;
    }

    return {
      workflowType: 'bounty',
      title: intent.title,
      reward: intent.reward,
      description: intent.description,
      ...baseConfig,
    } as BountyConfig;
  }

  /**
   * Validate workflow configuration
   */
  static validateConfig(config: AnyWorkflowConfig): {
    valid: boolean;
    errors: string[];
  } {
    const errors: string[] = [];

    // Common validations
    if (!config.token) {
      errors.push('Token must be specified');
    }

    switch (config.workflowType) {
      case 'conditional_payment': {
        const cp = config as ConditionalPaymentConfig;
        if (!cp.recipient) {
          errors.push('Recipient wallet address is required');
        } else if (!isValidEthereumAddress(cp.recipient)) {
          errors.push('Recipient must be a valid Ethereum address (0x followed by 40 hex characters)');
        }
        if (!cp.amount || cp.amount <= 0)
          errors.push('Amount must be greater than 0');
        if (!cp.condition) errors.push('Condition is required');
        break;
      }
      case 'escrow': {
        const escrow = config as EscrowConfig;
        if (!escrow.buyer) {
          errors.push('Buyer wallet address is required');
        } else if (!isValidEthereumAddress(escrow.buyer)) {
          errors.push('Buyer must be a valid Ethereum address');
        }
        if (!escrow.seller) {
          errors.push('Seller wallet address is required');
        } else if (!isValidEthereumAddress(escrow.seller)) {
          errors.push('Seller must be a valid Ethereum address');
        }
        if (!escrow.amount || escrow.amount <= 0)
          errors.push('Amount must be greater than 0');
        if (escrow.buyer === escrow.seller)
          errors.push('Buyer and seller must be different addresses');
        break;
      }
      case 'subscription': {
        const sub = config as SubscriptionConfig;
        if (!sub.recipient) {
          errors.push('Recipient wallet address is required');
        } else if (!isValidEthereumAddress(sub.recipient)) {
          errors.push('Recipient must be a valid Ethereum address');
        }
        if (!sub.amount || sub.amount <= 0)
          errors.push('Amount must be greater than 0');
        if (!sub.frequency) errors.push('Frequency is required');
        if (!['daily', 'weekly', 'monthly', 'yearly'].includes(sub.frequency)) {
          errors.push(
            'Frequency must be one of: daily, weekly, monthly, yearly'
          );
        }
        break;
      }
      case 'bounty': {
        const bounty = config as BountyConfig;
        if (!bounty.title) errors.push('Bounty title is required');
        if (!bounty.reward || bounty.reward <= 0)
          errors.push('Reward must be greater than 0');
        break;
      }
    }

    config.validated = errors.length === 0;
    config.errors = errors;

    return {
      valid: errors.length === 0,
      errors,
    };
  }

  /**
   * Generate contract code from workflow configuration
   */
  static generateContractCode(config: AnyWorkflowConfig): string {
    const template = ContractRegistry.getTemplate(config.workflowType);
    if (!template) {
      return '';
    }

    // Get the Python template and customize it with config values
    let code = template.pythonTemplate;

    // Add configuration comments
    const configComment = this.generateConfigComment(config);
    code = configComment + '\n' + code;

    return code;
  }

  static getConstructorArgs(config: AnyWorkflowConfig, walletAddress: string): unknown[] {
    switch (config.workflowType) {
      case 'conditional_payment':
        return [walletAddress, config.recipient, amountToUnits(config.amount), config.condition, config.token];
      case 'escrow':
        return [config.buyer || walletAddress, config.seller, amountToUnits(config.amount), config.token, config.description || 'Escrow workflow'];
      case 'subscription':
        return [walletAddress, config.recipient, amountToUnits(config.amount), config.token, config.frequency];
      case 'bounty':
        return [walletAddress, config.title, amountToUnits(config.reward), config.token, config.description || config.title];
    }
  }

  static getContractName(config: AnyWorkflowConfig): string {
    const template = ContractRegistry.getTemplate(config.workflowType);
    return template?.name || `${config.workflowType}_contract`;
  }

  private static extractCondition(message: string): string {
    const match = message.match(/\b(?:if|when|whenever)\b(.+)$/i);
    return match?.[1]?.trim().replace(/[.?!]+$/, '') || message;
  }

  private static extractFrequency(message: string): 'daily' | 'weekly' | 'monthly' | 'yearly' {
    const text = message.toLowerCase();
    if (/\b(daily|every day)\b/.test(text)) return 'daily';
    if (/\b(monthly|every month)\b/.test(text)) return 'monthly';
    if (/\b(yearly|annually|every year)\b/.test(text)) return 'yearly';
    return 'weekly';
  }

  private static extractBountyTitle(message: string): string {
    const cleaned = message
      .replace(/create\s+(a\s+)?/i, '')
      .replace(/\d+(?:\.\d+)?\s*(GEN|ETH)?/i, '')
      .replace(/\bbounty\b/i, '')
      .replace(/\bworth\b/i, '')
      .replace(/\bfor\b/i, '')
      .trim();
    return cleaned ? cleaned[0].toUpperCase() + cleaned.slice(1) : 'Workflow Bounty';
  }

  private static getNextPaymentLabel(frequency: 'daily' | 'weekly' | 'monthly' | 'yearly'): string {
    const date = new Date();
    if (frequency === 'daily') date.setDate(date.getDate() + 1);
    if (frequency === 'weekly') date.setDate(date.getDate() + 7);
    if (frequency === 'monthly') date.setMonth(date.getMonth() + 1);
    if (frequency === 'yearly') date.setFullYear(date.getFullYear() + 1);
    return date.toLocaleDateString();
  }

  private static generateConfigComment(config: AnyWorkflowConfig): string {
    let comment = `# Workflow Configuration\n`;
    comment += `# Type: ${config.workflowType}\n`;
    comment += `# Token: ${config.token}\n`;

    switch (config.workflowType) {
      case 'conditional_payment': {
        const cp = config as ConditionalPaymentConfig;
        comment += `# Recipient: ${cp.recipient}\n`;
        comment += `# Amount: ${cp.amount}\n`;
        comment += `# Condition: ${cp.condition}\n`;
        break;
      }
      case 'escrow': {
        const escrow = config as EscrowConfig;
        comment += `# Buyer: ${escrow.buyer}\n`;
        comment += `# Seller: ${escrow.seller}\n`;
        comment += `# Amount: ${escrow.amount}\n`;
        if (escrow.description) {
          comment += `# Description: ${escrow.description}\n`;
        }
        break;
      }
      case 'subscription': {
        const sub = config as SubscriptionConfig;
        comment += `# Recipient: ${sub.recipient}\n`;
        comment += `# Amount: ${sub.amount}\n`;
        comment += `# Frequency: ${sub.frequency}\n`;
        break;
      }
      case 'bounty': {
        const bounty = config as BountyConfig;
        comment += `# Title: ${bounty.title}\n`;
        comment += `# Reward: ${bounty.reward}\n`;
        if (bounty.description) {
          comment += `# Description: ${bounty.description}\n`;
        }
        break;
      }
    }

    return comment;
  }

  /**
   * Get workflow summary for display
   */
  static getWorkflowSummary(config: AnyWorkflowConfig): string {
    switch (config.workflowType) {
      case 'conditional_payment': {
        const cp = config as ConditionalPaymentConfig;
        return `Pay ${cp.recipient} ${cp.amount} ${cp.token} when ${cp.condition}`;
      }
      case 'escrow': {
        const escrow = config as EscrowConfig;
        return `Escrow ${escrow.amount} ${escrow.token} between ${escrow.buyer} and ${escrow.seller}`;
      }
      case 'subscription': {
        const sub = config as SubscriptionConfig;
        return `Subscribe: Send ${sub.amount} ${sub.token} to ${sub.recipient} ${sub.frequency}`;
      }
      case 'bounty': {
        const bounty = config as BountyConfig;
        return `Bounty: ${bounty.title} - Reward ${bounty.reward} ${bounty.token}`;
      }
      default:
        return 'Unknown workflow';
    }
  }
}
