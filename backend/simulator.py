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
        
    if intent.get("action") == "deploy_contract":
        ctype = intent.get("contract_type", "custom")
        summary = f"This will deploy a new '{ctype}' Intelligent Contract."
        cases = ["Contract will be deployed through GenLayer Studionet consensus."]

        contract_name = intent.get("contract_name")
        if contract_name:
            summary = f"This will deploy '{contract_name}' to GenLayer Studionet."

        constructor_args = intent.get("constructor_args")
        if isinstance(constructor_args, list) and constructor_args:
            cases.append(f"Constructor args supplied: {constructor_args}")

        deploy_value = intent.get("deploy_value")
        if deploy_value:
            cases.append(f"The deployment will send {deploy_value} GEN with the constructor call.")

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
            "cases": cases,
            "gasEstimate": intent.get("gas_limit") or 1500000,
        }

    return {"success": True}
