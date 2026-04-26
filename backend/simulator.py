def simulate_intent(intent: dict) -> dict:
    if intent.get("action") == "transfer":
        return {
            "success": True,
            "summary": f"This transaction will send {intent.get('amount')} {intent.get('token')} to {intent.get('recipient')}.",
            "cases": [
                f"If you have >= {intent.get('amount')} {intent.get('token')}, the transfer will succeed.",
                "If you have insufficient funds, the transaction will revert."
            ]
        }
        
    if intent.get("action") == "create_contract":
        return {
            "success": True,
            "summary": "This will deploy a new Intelligent Contract.",
            "cases": [
                "Contract will be deployed and active on GenLayer Studionet."
            ]
        }

    return {"success": True}
