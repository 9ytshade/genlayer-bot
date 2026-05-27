from backend.safety import normalize_intent


def test_normalize_transfer_intent():
    intent = normalize_intent(
        {
            "action": "transfer",
            "amount": "10",
            "token": "gen",
            "recipient": "0x1111111111111111111111111111111111111111",
        }
    )

    assert intent["action"] == "transfer"
    assert intent["amount"] == 10
    assert intent["token"] == "GEN"


def test_normalize_create_contract_aliases_to_deploy():
    intent = normalize_intent({"action": "create_contract", "contract_name": "Vault", "code": "class Vault: pass"})

    assert intent["action"] == "deploy_contract"
    assert intent["contract_name"] == "Vault"
    assert intent["code"] == "class Vault: pass"
