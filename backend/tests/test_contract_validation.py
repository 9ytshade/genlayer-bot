from backend.contract_validation import validate_python_contract
from backend.routers.chat import ContractValidationRequest, validate_contract


def test_rejects_empty_contract():
    result = validate_python_contract("")

    assert result["valid"] is False
    assert "empty" in result["message"].lower()


def test_rejects_python_syntax_error():
    result = validate_python_contract("class Broken(:\n    pass")

    assert result["valid"] is False
    assert result["errors"]


def test_accepts_python_contract_class():
    result = validate_python_contract("from genlayer import gl\n\nclass Counter:\n    def __init__(self):\n        self.count = 0")

    assert result["valid"] is True
    assert result["contract_names"] == ["Counter"]


async def test_rejects_non_python_contract_upload():
    result = await validate_contract(ContractValidationRequest(code="class Counter: pass", file_name="Counter.txt"))

    assert result.valid is False
    assert ".py" in result.message
