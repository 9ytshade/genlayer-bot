from intent_parser import parse_intent
import json

test_inputs = [
    "Send 5 GEN tokens to Alex",
    "Check my balance",
    "Give 0.1 tokens to 0x123",
    "What's the weather?"
]

for inp in test_inputs:
    print(f"Input: {inp}")
    intent = parse_intent(inp)
    print(f"Parsed: {json.dumps(intent, indent=2)}")
    print("-" * 20)
