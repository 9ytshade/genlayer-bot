import json
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

def parse_intent(user_input: str) -> dict:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return {"action": "unknown"}

    client = Groq(api_key=api_key)

    system_prompt = """
    You are an AI intent parser for GenLayer blockchain.
    Convert user input into a strict JSON intent.
    Supported actions: 'transfer', 'check_balance', 'create_contract', 'unknown'.
    
    Rules:
    - If action is 'transfer', extract 'amount' (number), 'token' (string, default 'GEN'), and 'recipient' (string).
    - If action is 'check_balance', no extra fields needed.
    - If action is 'unknown', return {"action": "unknown"}.
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
                            "enum": ["transfer", "check_balance", "create_contract", "unknown"]
                        },
                        "amount": {"type": "number"},
                        "token": {"type": "string"},
                        "recipient": {"type": "string"}
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
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ],
            tools=tools,
            tool_choice={"type": "function", "function": {"name": "parse_intent"}},
            timeout=timeout_sec,
        )

        if not response.choices or not response.choices[0].message.tool_calls:
            return {"action": "unknown"}

        tool_call = response.choices[0].message.tool_calls[0]
        return json.loads(tool_call.function.arguments)
    except Exception as e:
        print(f"Error parsing intent with Groq: {e}")
        # Fallback for parsing errors
        return {"action": "unknown"}
