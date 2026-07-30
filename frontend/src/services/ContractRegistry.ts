import type { ContractTemplate, WorkflowType } from '@/types/WorkflowConfig';

const HEADER = '# { "Depends": "py-genlayer:test" }\nfrom genlayer import *\n';

export class ContractRegistry {
  private static templates: Map<WorkflowType, ContractTemplate> = new Map([
    [
      'conditional_payment',
      {
        name: 'ConditionalPaymentContract',
        workflowType: 'conditional_payment',
        description: 'Execute a payment workflow after a condition is marked satisfied.',
        requiredParams: ['recipient', 'amount', 'condition'],
        optionalParams: ['token'],
        pythonTemplate: `${HEADER}

class ConditionalPaymentContract(gl.Contract):
    payer: Address
    recipient: Address
    amount: u256
    condition: str
    token: str
    executed: bool

    def __init__(self, payer: Address, recipient: Address, amount: u256, condition: str, token: str):
        self.payer = payer
        self.recipient = recipient
        self.amount = amount
        self.condition = condition
        self.token = token
        self.executed = False

    @gl.public.write
    def mark_condition_satisfied(self):
        if self.executed:
            gl.advanced.user_error_immediate("Conditional payment already executed")
        self.executed = True
        return "Condition satisfied. Payment workflow marked executed."

    @gl.public.view
    def status(self) -> str:
        return f"recipient={self.recipient}, amount={self.amount}, condition={self.condition}, executed={self.executed}"
`,
      },
    ],
    [
      'escrow',
      {
        name: 'EscrowContract',
        workflowType: 'escrow',
        description: 'Hold an escrow workflow until release, dispute, or cancellation.',
        requiredParams: ['buyer', 'seller', 'amount'],
        optionalParams: ['description', 'token'],
        pythonTemplate: `${HEADER}

class EscrowContract(gl.Contract):
    buyer: Address
    seller: Address
    amount: u256
    token: str
    description: str
    buyer_approved: bool
    disputed: bool
    cancelled: bool
    released: bool

    def __init__(self, buyer: Address, seller: Address, amount: u256, token: str, description: str):
        self.buyer = buyer
        self.seller = seller
        self.amount = amount
        self.token = token
        self.description = description
        self.buyer_approved = False
        self.disputed = False
        self.cancelled = False
        self.released = False

    @gl.public.write
    def approve_release(self):
        if self.cancelled or self.disputed or self.released:
            gl.advanced.user_error_immediate("Escrow cannot be released in its current state")
        self.buyer_approved = True
        self.released = True
        return "Escrow release approved"

    @gl.public.write
    def raise_dispute(self):
        if self.released or self.cancelled:
            gl.advanced.user_error_immediate("Escrow is already closed")
        self.disputed = True
        return "Escrow dispute raised"

    @gl.public.write
    def cancel_escrow(self):
        if self.released:
            gl.advanced.user_error_immediate("Released escrow cannot be cancelled")
        self.cancelled = True
        return "Escrow cancelled"

    @gl.public.view
    def status(self) -> str:
        return f"buyer={self.buyer}, seller={self.seller}, amount={self.amount}, released={self.released}, disputed={self.disputed}, cancelled={self.cancelled}"
`,
      },
    ],
    [
      'subscription',
      {
        name: 'SubscriptionContract',
        workflowType: 'subscription',
        description: 'Track a recurring payment agreement and its active state.',
        requiredParams: ['recipient', 'amount', 'frequency'],
        optionalParams: ['token'],
        pythonTemplate: `${HEADER}

class SubscriptionContract(gl.Contract):
    payer: Address
    recipient: Address
    amount: u256
    token: str
    frequency: str
    active: bool
    payment_count: u256

    def __init__(self, payer: Address, recipient: Address, amount: u256, token: str, frequency: str):
        self.payer = payer
        self.recipient = recipient
        self.amount = amount
        self.token = token
        self.frequency = frequency
        self.active = True
        self.payment_count = 0

    @gl.public.write
    def record_payment(self):
        if not self.active:
            gl.advanced.user_error_immediate("Subscription is paused or cancelled")
        self.payment_count += 1
        return "Subscription payment recorded"

    @gl.public.write
    def pause(self):
        self.active = False
        return "Subscription paused"

    @gl.public.write
    def resume(self):
        self.active = True
        return "Subscription resumed"

    @gl.public.write
    def cancel(self):
        self.active = False
        return "Subscription cancelled"

    @gl.public.view
    def status(self) -> str:
        return f"recipient={self.recipient}, amount={self.amount}, frequency={self.frequency}, active={self.active}, payments={self.payment_count}"
`,
      },
    ],
    [
      'bounty',
      {
        name: 'BountyContract',
        workflowType: 'bounty',
        description: 'Manage a bounty reward, submissions count, and selected winner.',
        requiredParams: ['title', 'reward'],
        optionalParams: ['description', 'token'],
        pythonTemplate: `${HEADER}

class BountyContract(gl.Contract):
    issuer: Address
    title: str
    description: str
    reward: u256
    token: str
    open: bool
    submission_count: u256
    winner: Address
    winner_selected: bool

    def __init__(self, issuer: Address, title: str, reward: u256, token: str, description: str):
        self.issuer = issuer
        self.title = title
        self.description = description
        self.reward = reward
        self.token = token
        self.open = True
        self.submission_count = 0
        self.winner = issuer
        self.winner_selected = False

    @gl.public.write
    def review_submission(self, submitter: Address):
        if not self.open:
            gl.advanced.user_error_immediate("Bounty is closed")
        self.submission_count += 1
        return f"Submission reviewed for {submitter}"

    @gl.public.write
    def select_winner(self, winner: Address):
        if not self.open:
            gl.advanced.user_error_immediate("Bounty is closed")
        self.winner = winner
        self.winner_selected = True
        self.open = False
        return "Bounty winner selected"

    @gl.public.write
    def close_bounty(self):
        self.open = False
        return "Bounty closed"

    @gl.public.view
    def status(self) -> str:
        return f"title={self.title}, reward={self.reward}, open={self.open}, submissions={self.submission_count}, winner_selected={self.winner_selected}"
`,
      },
    ],
  ]);

  static getTemplate(workflowType: WorkflowType): ContractTemplate | null {
    return this.templates.get(workflowType) || null;
  }

  static getAllTemplates(): ContractTemplate[] {
    return Array.from(this.templates.values());
  }

  static getTemplateByName(name: string): ContractTemplate | null {
    return this.getAllTemplates().find((template) => template.name === name) || null;
  }
}
