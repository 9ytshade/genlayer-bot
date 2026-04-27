from intent_parser import parse_intent
import json

test_inputs = [
    "Send 5 GEN tokens to Alex",
    "Check my balance",
    "Give 0.1 tokens to 0x123",
    "What's the weather?",
    "Create a contract that sends 50 GEN to 0x1234567890123456789012345678901234567890 if BTC price is above 60000",
    "Set up an escrow for 100 GEN with 0xabcdef1234567890abcdef1234567890abcdef12"
]

for inp in test_inputs:
    print(f"Input: {inp}")
    intent = parse_intent(inp)
    print(f"Parsed: {json.dumps(intent, indent=2)}")
    print("-" * 20)
