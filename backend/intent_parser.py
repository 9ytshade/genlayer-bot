import json
import os
import re
from decimal import Decimal, InvalidOperation
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

def extract_amount(text: str) -> str:
    """Extract an exact, non-exponent decimal amount as text."""
    match = re.search(r'(\d+(?:\.\d+)?)\s*(?:GEN|ETH|BTC)?', text)
    if match:
        try:
            amount = Decimal(match.group(1))
            if amount.is_finite() and amount > 0:
                normalized = format(amount, "f")
                return normalized.rstrip("0").rstrip(".") if "." in normalized else normalized
        except InvalidOperation:
            pass
    return "0"

def extract_escrow_description(text: str) -> str:
    """Extract the human release/delivery condition for escrow descriptions."""
    match = re.search(r'\b(?:when|after)\b\s+(.+?)\s*$', text, re.IGNORECASE)
    return match.group(1).strip(" .?!") if match else text.strip()


def extract_https_urls(text: str) -> list[str]:
    return [
        match.rstrip(".,);]")
        for match in re.findall(r"https://[^\s<>\"']+", text, re.IGNORECASE)
    ]


def extract_notary_statement(text: str, source_urls: list[str]) -> str:
    statement = text
    for source_url in source_urls:
        statement = statement.replace(source_url, " ")
    statement = re.sub(
        r"^\s*(?:please\s+)?(?:notarize|fact[- ]?check|verify(?:\s+the)?\s+claim|attest)\s+(?:whether\s+)?",
        "",
        statement,
        flags=re.IGNORECASE,
    )
    statement = re.split(r"\busing\b|\bwith evidence from\b", statement, maxsplit=1, flags=re.IGNORECASE)[0]
    return " ".join(statement.strip(" .,:;-").split())


def _extract_notary_labeled_value(text: str, labels: str) -> str:
    match = re.search(
        rf"(?:^|\n)\s*(?:{labels})\s*:\s*(.+?)(?=\n\s*(?:claim|statement|sources?|rubric|freshness(?:\s+rule)?)\s*:|\Z)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return " ".join(match.group(1).strip().split()) if match else ""


def merge_notary_spec_context(raw_spec: dict | None, user_input: str) -> dict:
    """Merge a follow-up chat message into a partial Notary blueprint."""
    context = raw_spec if isinstance(raw_spec, dict) else {}
    existing_sources = context.get("source_urls", context.get("sourceUrls", []))
    source_urls = [str(url).strip() for url in existing_sources] if isinstance(existing_sources, list) else []
    for source_url in extract_https_urls(user_input):
        if source_url not in source_urls:
            source_urls.append(source_url)

    statement = str(context.get("statement") or "").strip()
    labeled_statement = _extract_notary_labeled_value(user_input, "claim|statement")
    if labeled_statement:
        statement = labeled_statement
    elif not statement:
        candidate = extract_notary_statement(user_input, extract_https_urls(user_input))
        if candidate and not re.match(
            r"^(?:sources?|rubric|freshness(?:\s+rule)?)\s*:",
            candidate,
            flags=re.IGNORECASE,
        ):
            statement = candidate

    rubric = str(context.get("rubric") or "").strip()
    labeled_rubric = _extract_notary_labeled_value(user_input, "rubric")
    if labeled_rubric:
        rubric = labeled_rubric

    freshness_rule = str(
        context.get("freshness_rule") or context.get("freshnessRule") or ""
    ).strip()
    labeled_freshness = _extract_notary_labeled_value(
        user_input,
        r"freshness(?:\s+rule)?",
    )
    if labeled_freshness:
        freshness_rule = labeled_freshness

    return {
        "statement": statement,
        "source_urls": source_urls,
        "rubric": rubric,
        "freshness_rule": freshness_rule,
    }


def parse_with_patterns(user_input: str, wallet_address: str | None = None) -> dict:
    """Fallback pattern-based parser for common workflows."""
    lower_input = user_input.lower()

    # AI NOTARY patterns
    if any(
        pattern in lower_input
        for pattern in ("notarize", "notary", "fact-check", "fact check", "verify the claim", "attest")
    ):
        source_urls = extract_https_urls(user_input)
        return {
            "action": "notarize_claim",
            "claimant_address": wallet_address,
            "notary_spec": {
                "statement": extract_notary_statement(user_input, source_urls),
                "source_urls": source_urls,
                "rubric": "",
                "freshness_rule": "",
            },
        }
    
    # CONDITIONAL PAYMENT patterns
    if any(pattern in lower_input for pattern in ['if ', 'when ', 'reaches ', 'exceeds ', 'drops ', 'falls ']):
        if any(p in lower_input for p in ['pay', 'send', 'transfer']):
            source_urls = list(dict.fromkeys(extract_https_urls(user_input)))[:3]
            # Extract condition
            condition_match = re.search(r'(?:if|when)\s+(.+?)(?:$|\.)', user_input)
            condition = condition_match.group(1).strip() if condition_match else "condition met"
            condition = re.split(
                r"\b(?:using|with evidence from)\b",
                condition,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0].strip()
            for source_url in source_urls:
                condition = condition.replace(source_url, " ").strip()
            
            recipient = extract_ethereum_address(user_input)
            amount = extract_amount(user_input)
            
            if recipient and is_valid_ethereum_address(recipient) and amount != "0":
                return {
                    "action": "conditional_payment",
                    "recipient": recipient,
                    "amount": amount,
                    "token": "GEN",
                    "condition": condition,
                    "evidenceSources": source_urls,
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
            
            if amount != "0":
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
            
            if amount != "0" and is_valid_ethereum_address(buyer) and is_valid_ethereum_address(seller):
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
        
        if amount != "0":
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
            
            if amount != "0":
                return {
                    "action": "transfer",
                    "recipient": recipient,
                    "amount": amount,
                    "token": "GEN"
                }
    
    # DEBUG TRACE patterns
    if any(pattern in lower_input for pattern in ['debug tx', 'trace tx', 'debug transaction', 'trace transaction', 'inspect tx', 'inspect transaction']):
        tx_hash = extract_ethereum_address(user_input)  # reuse hex extraction
        tx_match = re.search(r'(0x[a-fA-F0-9]{64})', user_input)
        if tx_match:
            return {
                "action": "debug_trace",
                "tx_hash": tx_match.group(1)
            }
        return {"action": "unknown", "error": "Transaction hash required for debug trace"}

    # APPEAL TRANSACTION patterns
    if any(pattern in lower_input for pattern in ['appeal tx', 'appeal transaction', 'challenge tx', 'challenge transaction', 'dispute tx']):
        tx_match = re.search(r'(0x[a-fA-F0-9]{64})', user_input)
        if tx_match:
            return {
                "action": "appeal_transaction",
                "tx_hash": tx_match.group(1)
            }
        return {"action": "unknown", "error": "Transaction hash required for appeal"}

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
- notarize_claim: Evaluate a public claim against one to three HTTPS evidence sources
- unknown: Cannot determine intent

AI NOTARY DETECTION:
Requirements: connected claimant wallet, claim statement, one to three public HTTPS evidence URLs
Patterns: "Notarize whether [claim] using https://...", "Fact-check [claim] with evidence from https://..."
Extract: claimant_address, notary_spec with statement, source_urls, optional rubric, optional freshness_rule

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
- AI Notary evidence must use public HTTPS URLs; never accept credentials or private documents
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
                            "enum": ["transfer", "check_balance", "deploy_contract", "generate_contract", "contract_review", "conditional_payment", "escrow", "subscription", "bounty", "notarize_claim", "unknown"]
                        },
                        "amount": {"type": "number"},
                        "token": {"type": "string"},
                        "recipient": {"type": "string"},
                        "contract_name": {"type": "string"},
                        "code": {"type": "string"},
                        "logic_description": {"type": "string"},
                        "advanced": {"type": "boolean"},
                        "condition": {"type": "string"},
                        "evidenceSources": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "buyer": {"type": "string"},
                        "seller": {"type": "string"},
                        "description": {"type": "string"},
                        "frequency": {"type": "string"},
                        "title": {"type": "string"},
                        "reward": {"type": "number"},
                        "claimant_address": {"type": "string"},
                        "notary_spec": {
                            "type": "object",
                            "properties": {
                                "statement": {"type": "string"},
                                "source_urls": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "rubric": {"type": "string"},
                                "freshness_rule": {"type": "string"}
                            }
                        }
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
