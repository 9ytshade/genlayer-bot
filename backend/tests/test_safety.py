from backend.safety import validate_intent


def test_blocks_zero_address_transfer():
    valid, error = validate_intent(
        {
            "action": "transfer",
            "amount": 1,
            "token": "GEN",
            "recipient": "0x0000000000000000000000000000000000000000",
        }
    )

    assert valid is False
    assert "zero address" in error


def test_allows_basic_deploy_with_code():
    valid, error = validate_intent({"action": "deploy_contract", "code": "class Contract: pass", "deploy_value": 0})

    assert valid is True
    assert error == ""
