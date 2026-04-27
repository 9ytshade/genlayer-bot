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
        ctype = intent.get("contract_type", "custom")
        summary = f"This will deploy a new '{ctype}' Intelligent Contract."
        cases = ["Contract will be deployed and active on GenLayer Studionet."]
        
        if ctype == "conditional_payment":
            summary = f"This will deploy a conditional payment contract that sends {intent.get('amount')} GEN to {intent.get('recipient')} when '{intent.get('condition')}' is met."
            cases.append(f"If '{intent.get('condition')}' evaluates to true, the payment will be triggered.")
            cases.append("The contract will use GenLayer oracles/web-data-access to verify the condition.")
        elif ctype == "escrow":
            summary = f"This will deploy an escrow contract for {intent.get('amount')} GEN with {intent.get('recipient')} as the beneficiary."
            cases.append("Funds will be locked in the contract until release conditions are met.")
            
        return {
            "success": True,
            "summary": summary,
            "cases": cases
        }

    return {"success": True}
