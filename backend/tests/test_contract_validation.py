from backend.contract_artifacts import PINNED_DEPENDENCY_HEADER
from backend.contract_validation import validate_python_contract
from backend.routers.chat import ContractValidationRequest, validate_contract
from backend.validators.contract_validator import ContractValidator


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


def contract(body: str, storage: str = "value: u256", imports: str = "from genlayer import *") -> str:
    return f"""{PINNED_DEPENDENCY_HEADER}
{imports}

class Example(gl.Contract):
    {storage}

    def __init__(self):
        self.value = u256(0)

{body}
"""


def test_genlayer_validator_accepts_typed_deterministic_contract():
    result = ContractValidator().validate(
        contract(
            """    @gl.public.write
    def increment(self) -> u256:
        self.value += u256(1)
        return self.value
"""
        )
    )

    assert result["valid"] is True


def test_genlayer_validator_requires_exactly_one_contract_class():
    code = contract(
        """    @gl.public.view
    def get_value(self) -> u256:
        return self.value
"""
    ) + "\nclass Second(gl.Contract):\n    pass\n"

    result = ContractValidator().validate(code)

    assert result["valid"] is False
    assert any("exactly one" in error for error in result["errors"])


def test_genlayer_validator_rejects_unsupported_storage_and_float_money():
    result = ContractValidator().validate(
        contract(
            """    @gl.public.view
    def quote(self) -> float:
        return float(1.25)
""",
            storage="amount: float",
        )
    )

    assert result["valid"] is False
    assert any("Storage field 'amount'" in error for error in result["errors"])
    assert any("Floating-point" in error for error in result["errors"])


def test_genlayer_validator_requires_typed_public_parameters():
    result = ContractValidator().validate(
        contract(
            """    @gl.public.write
    def set_value(self, value):
        self.value = value
"""
        )
    )

    assert result["valid"] is False
    assert any("must type every parameter" in error for error in result["errors"])


def test_genlayer_validator_rejects_nonpayable_message_value_access():
    result = ContractValidator().validate(
        contract(
            """    @gl.public.write
    def fund(self):
        self.value = gl.message.value
"""
        )
    )

    assert result["valid"] is False
    assert any("is not payable" in error for error in result["errors"])


def test_genlayer_validator_accepts_payable_message_value_access():
    result = ContractValidator().validate(
        contract(
            """    @gl.public.write.payable
    def fund(self):
        self.value = gl.message.value
"""
        )
    )

    assert result["valid"] is True


def test_genlayer_validator_requires_equivalence_boundary_for_nondeterminism():
    result = ContractValidator().validate(
        contract(
            """    @gl.public.write
    def decide(self) -> str:
        return gl.nondet.exec_prompt("Decide")
"""
        )
    )

    assert result["valid"] is False
    assert any("Equivalence Principle boundary" in error for error in result["errors"])


def test_genlayer_validator_accepts_nondeterministic_task_passed_to_equivalence():
    result = ContractValidator().validate(
        contract(
            """    @gl.public.write
    def decide(self) -> str:
        def task() -> str:
            return gl.nondet.exec_prompt("Return structured JSON", response_format="json")
        result = gl.eq_principle.prompt_comparative(task, "The outcome enum must match")
        return str(result["outcome"])
"""
        )
    )

    assert result["valid"] is True


def test_genlayer_validator_rejects_loose_consensus_substring_checks():
    result = ContractValidator().validate(
        contract(
            """    @gl.public.write
    def decide(self) -> bool:
        def task() -> str:
            return gl.nondet.exec_prompt("Return TRUE or FALSE")
        result = gl.eq_principle.strict_eq(task)
        return "TRUE" in result.upper()
"""
        )
    )

    assert result["valid"] is False
    assert any("structured output" in error for error in result["errors"])
