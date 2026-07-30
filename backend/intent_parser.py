import json
import os
import re
from groq import Groq
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

def is_valid_ethereum_address(address: str) -> bool:
    """Check if string is a valid Ethereum address."""
    if not address:
        return False
    # Ethereum addresses are 0x followed by 40 hex characters
    return bool(re.match(r'^0x[a-fA-F0-9]{40}$', address.strip()))

def extract_ethereum_address(text: str) -> str:
    """Extract first valid Ethereum address from text."""
    matches = re.findall(r'0x[a-fA-F0-9]{40}', text)
    return matches[0] if matches else ""

def extract_amount(text: str) -> float:
    """Extract the first number mentioned as amount."""
    match = re.search(r'(\d+(?:\.\d+)?)\s*(?:GEN|ETH|BTC)?', text)
    if match:
        try:
            return float(match.group(1))
        except:
            pass
    return 0

def extract_escrow_description(text: str) -> str:
    """Extract the human release/delivery condition for escrow descriptions."""
    match = re.search(r'\b(?:when|after)\b\s+(.+?)\s*$', text, re.IGNORECASE)
    return match.group(1).strip(" .?!") if match else text.strip()


def parse_with_patterns(user_input: str, wallet_address: str | None = None) -> dict:
    """Fallback pattern-based parser for common workflows."""
    lower_input = user_input.lower()
    
    # CONDITIONAL PAYMENT patterns
    if any(pattern in lower_input for pattern in ['if ', 'when ', 'reaches ', 'exceeds ', 'drops ', 'falls ']):
        if any(p in lower_input for p in ['pay', 'send', 'transfer']):
            # Extract condition
            condition_match = re.search(r'(?:if|when)\s+(.+?)(?:$|\.)', user_input)
            condition = condition_match.group(1).strip() if condition_match else "condition met"
            
            recipient = extract_ethereum_address(user_input)
            amount = extract_amount(user_input)
            
            if recipient and is_valid_ethereum_address(recipient) and amount > 0:
                return {
                    "action": "conditional_payment",
                    "recipient": recipient,
                    "amount": amount,
                    "token": "GEN",
                    "condition": condition
                }
            elif not recipient:
                # No valid address found
                return {"action": "unknown", "error": "Wallet address required for conditional payment"}
    
    # SUBSCRIPTION patterns
    if any(pattern in lower_input for pattern in ['every ', 'each ', 'daily', 'weekly', 'monthly', 'yearly', 'recurring']):
        if any(p in lower_input for p in ['pay', 'send', 'transfer']):
            recipient = extract_ethereum_address(user_input)
            amount = extract_amount(user_input)
            
            if not recipient or not is_valid_ethereum_address(recipient):
                return {"action": "unknown", "error": "Valid wallet address required for subscription"}
            
            # Extract frequency
            frequency = "monthly"
            if 'daily' in lower_input:
                frequency = 'daily'
            elif 'weekly' in lower_input or 'week' in lower_input or 'friday' in lower_input or 'monday' in lower_input:
                frequency = 'weekly'
            elif 'monthly' in lower_input or 'month' in lower_input:
                frequency = 'monthly'
            elif 'yearly' in lower_input or 'year' in lower_input or 'annual' in lower_input:
                frequency = 'yearly'
            
            if amount > 0:
                return {
                    "action": "subscription",
                    "recipient": recipient,
                    "amount": amount,
                    "token": "GEN",
                    "frequency": frequency
                }
    
    # ESCROW patterns
    if any(pattern in lower_input for pattern in ['escrow', 'between', 'after', 'approval', 'deliver', 'delivered', 'submitted']):
        if any(p in lower_input for p in ['pay', 'send', 'transfer', 'release', 'releases', 'funds']):
            amount = extract_amount(user_input)
            
            addresses = re.findall(r'0x[a-fA-F0-9]{40}', user_input)
            
            if len(addresses) >= 2:
                buyer = addresses[0]
                seller = addresses[1]
            elif len(addresses) == 1 and wallet_address and is_valid_ethereum_address(wallet_address):
                buyer = wallet_address
                seller = addresses[0]
            else:
                return {"action": "unknown", "error": "Escrow requires a seller wallet address and a connected buyer wallet"}
            
            if amount > 0 and is_valid_ethereum_address(buyer) and is_valid_ethereum_address(seller):
                return {
                    "action": "escrow",
                    "buyer": buyer,
                    "seller": seller,
                    "amount": amount,
                    "token": "GEN",
                    "description": extract_escrow_description(user_input)
                }
    
    # BOUNTY patterns
    if any(pattern in lower_input for pattern in ['bounty', 'reward', 'prize', 'paid for']):
        amount = extract_amount(user_input)
        
        # Extract title/description
        title_match = re.search(r'bounty\s+(?:for\s+)?(.+?)(?:\$|\.|$)', user_input)
        title = title_match.group(1).strip() if title_match else "Bounty"
        
        if amount > 0:
            return {
                "action": "bounty",
                "title": title,
                "reward": amount,
                "token": "GEN"
            }
    
    # TRANSFER patterns
    if any(pattern in lower_input for pattern in ['send', 'transfer', 'pay']):
        if not any(p in lower_input for p in ['if ', 'when ', 'every ', 'bounty', 'escrow']):
            recipient = extract_ethereum_address(user_input)
            amount = extract_amount(user_input)
            
            if not recipient or not is_valid_ethereum_address(recipient):
                return {"action": "unknown", "error": "Valid wallet address required for transfer"}
            
            if amount > 0:
                return {
                    "action": "transfer",
                    "recipient": recipient,
                    "amount": amount,
                    "token": "GEN"
                }
    
    # CHECK BALANCE patterns
    if any(pattern in lower_input for pattern in ['balance', 'how much', 'do i have', 'check', 'what\'s my']):
        return {"action": "check_balance"}
    
    return None

def parse_intent(user_input: str, wallet_address: str | None = None) -> dict:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        # Fallback to pattern matching if no API key
        result = parse_with_patterns(user_input, wallet_address)
        return result if result else {"action": "unknown"}

    client = Groq(api_key=api_key)

    system_prompt = """
You are an AI intent parser for GenLayer blockchain. Your job is to identify user intent and extract parameters.

CRITICAL: ONLY ACCEPT WALLET ADDRESSES (0x...), NOT NAMES OR USERNAMES.
The blockchain can only execute transactions with valid Ethereum wallet addresses (format: 0x followed by 40 hexadecimal characters).
If the user provides a name instead of a wallet address, you MUST ask them to provide the wallet address or return unknown.

SUPPORTED ACTIONS:
- transfer: Send tokens to a recipient wallet address
- check_balance: Get wallet balance
- deploy_contract: Deploy a contract file
- generate_contract: AI-generated contract from description
- contract_review: Review a contract
- conditional_payment: Pay when a condition is met
- escrow: Secure payment between two parties
- subscription: Recurring payment at intervals
- bounty: Reward for work/submissions
- unknown: Cannot determine intent

CONDITIONAL PAYMENT DETECTION:
Requirements: recipient wallet address, amount, condition
Patterns: "Pay X to 0x... if [condition]", "Send amount when [market condition]"
Extract: recipient (wallet address only), amount, token (default GEN), condition

Examples:
- Input: "Pay 100 GEN to 0x3f6DCbE220EBF442D0CA785bD4D4D6650C23B1 if ETH reaches 10000"
  → {action: "conditional_payment", recipient: "0x3f6DCbE220EBF442D0CA785bD4D4D6650C23B1", amount: 100, token: "GEN", condition: "ETH reaches 10000"}
- Input: "Send 50 GEN to 0x1234567890123456789012345678901234567890 when BTC exceeds 150000"
  → {action: "conditional_payment", recipient: "0x1234567890123456789012345678901234567890", amount: 50, token: "GEN", condition: "BTC exceeds 150000"}

ESCROW DETECTION:
Requirements: amount, seller wallet address, and either buyer wallet address or connected wallet address
Patterns: "Create escrow between 0x... and 0x...", "Pay from 0x... to 0x... after approval", "Create escrow that releases X GEN when work is submitted by 0x..."
Extract: buyer (wallet address), seller (wallet address), amount, token (default GEN), description

Examples:
- Input: "Create escrow for 500 GEN between 0x1111111111111111111111111111111111111111 and 0x2222222222222222222222222222222222222222"
  → {action: "escrow", buyer: "0x1111111111111111111111111111111111111111", seller: "0x2222222222222222222222222222222222222222", amount: 500, token: "GEN"}
- Input: "Pay 500 GEN from 0xaaaa... to 0xbbbb... after approval"
  → {action: "escrow", buyer: "0xaaaa...", seller: "0xbbbb...", amount: 500, token: "GEN"}

SUBSCRIPTION DETECTION:
Requirements: recipient wallet address, amount, frequency
Patterns: "Pay 0x... X every [frequency]", "Send amount [frequency] to 0x..."
Extract: recipient (wallet address), amount, token (default GEN), frequency (daily/weekly/monthly/yearly)

Examples:
- Input: "Pay 100 GEN to 0x3333333333333333333333333333333333333333 every Friday"
  → {action: "subscription", recipient: "0x3333333333333333333333333333333333333333", amount: 100, token: "GEN", frequency: "weekly"}
- Input: "Send 50 GEN monthly to 0x4444444444444444444444444444444444444444"
  → {action: "subscription", recipient: "0x4444444444444444444444444444444444444444", amount: 50, token: "GEN", frequency: "monthly"}

BOUNTY DETECTION:
Requirements: amount/reward, title/description
Patterns: "Create 1000 GEN bounty for [description]", "Post reward for [task]"
Extract: title (description of work), reward (amount), token (default GEN)

Examples:
- Input: "Create 1000 GEN bounty for building a landing page"
  → {action: "bounty", title: "Building a landing page", reward: 1000, token: "GEN"}
- Input: "Post 500 GEN bug bounty"
  → {action: "bounty", title: "Bug bounty", reward: 500, token: "GEN"}

TRANSFER DETECTION:
Requirements: recipient wallet address, amount
Patterns: "Send X to 0x...", "Transfer amount to 0x..."
Extract: recipient (wallet address), amount, token (default GEN)

BALANCE CHECK DETECTION:
Patterns: "Check balance", "What's my balance", "How much do I have"
Extract: nothing additional needed

IMPORTANT RULES:
- WALLET ADDRESSES ONLY - All recipient, buyer, seller fields must be valid Ethereum addresses (0x followed by 40 hex chars)
- If user mentions names like "john", "sarah", "designer" - ask for their wallet address instead
- If user mentions a condition (if/when/reaches/exceeds), it's CONDITIONAL_PAYMENT
- If user mentions recurring/frequency (every/daily/weekly/monthly), it's SUBSCRIPTION
- If user mentions two parties and approval/delivery, it's ESCROW
- If user mentions one seller address in an escrow request, use CONNECTED_WALLET_ADDRESS as buyer when available
- If user mentions reward/bounty for work, it's BOUNTY
- Default token is always GEN if not specified
- Return only the action and required parameters
- If any required wallet address is missing or invalid, set action to "unknown"
"""
    
    tools = [
        {
            "type": "function",
            "function": {
                "name": "parse_intent",
                "description": "Parse the user's blockchain intent",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["transfer", "check_balance", "deploy_contract", "generate_contract", "contract_review", "conditional_payment", "escrow", "subscription", "bounty", "unknown"]
                        },
                        "amount": {"type": "number"},
                        "token": {"type": "string"},
                        "recipient": {"type": "string"},
                        "contract_name": {"type": "string"},
                        "code": {"type": "string"},
                        "logic_description": {"type": "string"},
                        "advanced": {"type": "boolean"},
                        "condition": {"type": "string"},
                        "buyer": {"type": "string"},
                        "seller": {"type": "string"},
                        "description": {"type": "string"},
                        "frequency": {"type": "string"},
                        "title": {"type": "string"},
                        "reward": {"type": "number"}
                    },
                    "required": ["action"]
                }
            }
        }
    ]

    try:
        timeout_sec = float(os.getenv("GROQ_TIMEOUT_SEC", "12"))
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": f"{system_prompt}\nCONNECTED_WALLET_ADDRESS: {wallet_address or 'not provided'}"},
                {"role": "user", "content": user_input}
            ],
            tools=tools,
            tool_choice={"type": "function", "function": {"name": "parse_intent"}},
            timeout=timeout_sec,
        )

        if not response.choices or not response.choices[0].message.tool_calls:
            # Fallback to pattern matching if Groq doesn't return a tool call
            result = parse_with_patterns(user_input, wallet_address)
            return result if result else {"action": "unknown"}

        tool_call = response.choices[0].message.tool_calls[0]
        result = json.loads(tool_call.function.arguments)
        
        # If Groq returns unknown, try pattern matching as backup
        if result.get("action") == "unknown":
            pattern_result = parse_with_patterns(user_input, wallet_address)
            if pattern_result:
                return pattern_result
        
        return result
    except Exception as e:
        print(f"Error parsing intent with Groq: {e}")
        # Fallback to pattern matching on any error
        result = parse_with_patterns(user_input, wallet_address)
        return result if result else {"action": "unknown"}
