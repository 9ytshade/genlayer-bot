from __future__ import annotations

import ast
from typing import Any

from ..validators.contract_validator import (
    EQUIVALENCE_CALLS,
    NONDETERMINISTIC_CALLS,
    ContractValidator,
    _dotted_name,
)


class ContractReviewService:
    """Produce bounded automated preflight findings for a GenLayer contract."""

    def __init__(self, validator: ContractValidator | None = None):
        self.validator = validator or ContractValidator()

    def review(self, code: str) -> dict[str, Any]:
        validation = self.validator.validate(code)
        structural: dict[str, Any] = {
            "contractNames": [],
            "publicMethods": [],
            "storageFields": [],
            "nondeterministicCalls": [],
            "equivalenceBoundaries": [],
        }
        safety: dict[str, Any] = {
            "financialCustody": False,
            "authorizationChecks": [],
            "findings": [],
        }
        genlayer: dict[str, Any] = {
            "requiredForBehavior": False,
            "judgmentDescription": "No nondeterministic judgment was detected.",
            "findings": [],
        }

        try:
            tree = ast.parse(code.replace("\r\n", "\n"))
        except SyntaxError:
            tree = None

        if tree is not None:
            classes = [
                node
                for node in tree.body
                if isinstance(node, ast.ClassDef)
                and any(_dotted_name(base) in {"gl.Contract", "gl.contract.Contract"} for base in node.bases)
            ]
            for class_def in classes:
                structural["contractNames"].append(class_def.name)
                for field in class_def.body:
                    if isinstance(field, (ast.AnnAssign, ast.Assign)):
                        target = field.target if isinstance(field, ast.AnnAssign) else field.targets[0]
                        if isinstance(target, ast.Name):
                            structural["storageFields"].append(target.id)
                    if not isinstance(field, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    decorators = {_dotted_name(item) for item in field.decorator_list}
                    if not any(
                        name.startswith("gl.public.write") or name == "gl.public.view"
                        for name in decorators
                    ):
                        continue
                    structural["publicMethods"].append(field.name)
                    method_text = ast.unparse(field)
                    has_sender_check = "gl.message.sender_address" in method_text
                    if "gl.public.write" in decorators:
                        safety["authorizationChecks"].append(
                            {"method": field.name, "senderCheckDetected": has_sender_check}
                        )
                        if not has_sender_check and any(
                            marker in method_text for marker in ("emit_transfer", "gl.message.value")
                        ):
                            safety["findings"].append(
                                f"Write method '{field.name}' handles value or transfers without a detected sender authorization check."
                            )

            source = ast.unparse(tree)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                dotted = _dotted_name(node.func)
                if dotted in NONDETERMINISTIC_CALLS:
                    structural["nondeterministicCalls"].append(dotted)
                if dotted in EQUIVALENCE_CALLS:
                    structural["equivalenceBoundaries"].append(dotted)

            safety["financialCustody"] = any(
                marker in source for marker in ("gl.message.value", "emit_transfer")
            )
            genlayer["requiredForBehavior"] = bool(structural["nondeterministicCalls"])
            if genlayer["requiredForBehavior"]:
                genlayer["judgmentDescription"] = (
                    "Validators influence a nondeterministic contract decision; deterministic code must constrain the result before any state or value transition."
                )
                if not structural["equivalenceBoundaries"]:
                    genlayer["findings"].append(
                        "Nondeterministic calls were detected without a visible Equivalence Principle boundary."
                    )
                if "gl.nondet.web." in source and "response_format" not in source:
                    genlayer["findings"].append(
                        "Web evidence is evaluated without a visible structured response format; verify schema validation and abstention handling."
                    )
            elif safety["financialCustody"]:
                genlayer["findings"].append(
                    "The contract moves or accepts GEN but no GenLayer judgment was detected; classify it as deterministic."
                )

            if safety["financialCustody"] and not any(
                marker in source
                for marker in ("released", "refunded", "settled", "cancelled", "closed", "paid")
            ):
                safety["findings"].append(
                    "Financial behavior has no obvious terminal-state guard; verify duplicate settlement and replay protection."
                )

        errors = list(validation.get("errors", []))
        warnings = list(validation.get("warnings", []))
        warnings.extend(safety["findings"])
        warnings.extend(genlayer["findings"])
        blocking = list(dict.fromkeys(errors))
        warnings = list(dict.fromkeys(warnings))
        verdict = "BLOCKED" if blocking else "READY_WITH_WARNINGS" if warnings else "READY"
        return {
            "verdict": verdict,
            "deploymentReady": not blocking,
            "blockingErrors": blocking,
            "warnings": warnings,
            "suggestions": [
                "Review every warning against the intended trust model before signing deployment.",
                "Treat this result as automated preflight, not a formal security audit.",
            ],
            "structural": structural,
            "safety": safety,
            "genlayer": genlayer,
            "validation": validation,
        }
