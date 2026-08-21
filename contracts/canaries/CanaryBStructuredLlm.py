# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *


class CanaryBStructuredLlm(gl.Contract):
    """Bounded LLM/equivalence canary; no unconstrained prose reaches state."""

    decision: str

    def __init__(self):
        self.decision = "PENDING"

    @gl.public.write
    def evaluate(self) -> str:
        def leader_fn() -> dict:
            result = gl.nondet.exec_prompt(
                "Return JSON with exactly one key, decision, whose value is YES.",
                response_format="json",
            )
            if not isinstance(result, dict) or result.get("decision") != "YES":
                return {"decision": "INCONCLUSIVE"}
            return {"decision": "YES"}

        result = gl.eq_principle.prompt_comparative(
            leader_fn,
            principle=(
                "Independently verify the bounded decision. Accept YES only when the response "
                "substantively satisfies the requested JSON decision; otherwise require INCONCLUSIVE."
            ),
        )
        decision = str(result.get("decision", "INCONCLUSIVE"))
        self.decision = decision if decision in ["YES", "INCONCLUSIVE"] else "INCONCLUSIVE"
        return self.decision

    @gl.public.view
    def get_decision(self) -> str:
        return self.decision
