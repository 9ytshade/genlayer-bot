from backend.safety import normalize_intent
from backend.intent_parser import parse_with_patterns


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


def test_one_address_escrow_uses_connected_wallet_as_buyer():
    buyer = "0x1111111111111111111111111111111111111111"
    seller = "0x1BCB24fb161155B24982657bE4641F4fC38cd796"

    intent = parse_with_patterns(
        "create an escrow contract that releases 20 GEN when a satisfied job is submitted by "
        f"{seller}",
        wallet_address=buyer,
    )

    assert intent["action"] == "escrow"
    assert intent["buyer"] == buyer
    assert intent["seller"] == seller
    assert intent["amount"] == 20
    assert intent["token"] == "GEN"
    assert intent["description"] == f"a satisfied job is submitted by {seller}"
