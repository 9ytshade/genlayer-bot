import ast
from typing import Any

from ..contract_validation import validate_python_contract


FORBIDDEN_IMPORTS = {"os", "subprocess", "socket", "requests", "httpx", "urllib", "pathlib", "shutil"}
FORBIDDEN_CALLS = {"eval", "exec", "open", "compile", "__import__"}


class ContractValidator:
    """Validation gate for generated contracts before they can be shown or deployed."""

    def validate(self, code: str) -> dict[str, Any]:
        base = validate_python_contract(code)
        if not base["valid"]:
            return base

        tree = ast.parse(code)
        errors: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    if root in FORBIDDEN_IMPORTS:
                        errors.append(f"Forbidden import: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".", 1)[0]
                if root in FORBIDDEN_IMPORTS:
                    errors.append(f"Forbidden import: {node.module}")
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
                errors.append(f"Forbidden call: {node.func.id}()")

        class_defs = [node for node in tree.body if isinstance(node, ast.ClassDef)]
        has_contract_base = any(
            any(
                (
                    # New pattern: gl.Contract
                    isinstance(base_node, ast.Attribute)
                    and base_node.attr == "Contract"
                    and isinstance(base_node.value, ast.Name)
                    and base_node.value.id == "gl"
                )
                or (
                    # Legacy pattern: gl.contract.Contract
                    isinstance(base_node, ast.Attribute)
                    and base_node.attr == "Contract"
                    and isinstance(base_node.value, ast.Attribute)
                    and base_node.value.attr == "contract"
                )
                for base_node in class_def.bases
            )
            for class_def in class_defs
        )
        if not has_contract_base:
            errors.append("Generated contract must inherit from gl.Contract.")

        has_public_method = any(
            any(
                isinstance(decorator, ast.Attribute)
                and decorator.attr in {"write", "view"}
                and isinstance(decorator.value, ast.Attribute)
                and decorator.value.attr == "public"
                for decorator in function.decorator_list
            )
            for class_def in class_defs
            for function in class_def.body
            if isinstance(function, ast.FunctionDef)
        )
        if not has_public_method:
            errors.append("Generated contract must expose at least one @gl.public.write or @gl.public.view method.")

        if errors:
            return {
                "valid": False,
                "message": "Generated contract failed validation.",
                "errors": errors,
                "warnings": base.get("warnings", []),
                "contract_names": base.get("contract_names", []),
            }

        return base
