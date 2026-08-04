import ast
from typing import Any


def validate_python_contract(code: str) -> dict[str, Any]:
    normalized_code = code.replace("\r\n", "\n").strip()
    if not normalized_code:
        return {
            "valid": False,
            "message": "The uploaded file is empty.",
            "errors": ["No Python source code was found in the uploaded file."],
            "warnings": [],
        }

    try:
        tree = ast.parse(normalized_code)
    except SyntaxError as exc:
        line = exc.lineno or 1
        column = exc.offset or 1
        error_line = normalized_code.splitlines()[line - 1] if normalized_code.splitlines() else ""
        return {
            "valid": False,
            "message": f"Python syntax error on line {line}, column {column}.",
            "errors": [
                f"{exc.msg} (line {line}, column {column})",
                error_line,
            ],
            "warnings": [],
        }

    class_defs = [node for node in tree.body if isinstance(node, ast.ClassDef)]
    if not class_defs:
        return {
            "valid": False,
            "message": "This file is valid Python, but it does not define a contract class.",
            "errors": ["Add at least one Python class that represents the contract you want to deploy."],
            "warnings": [],
        }

    warnings: list[str] = []
    if not any(
        isinstance(node, (ast.Import, ast.ImportFrom)) and (
            (isinstance(node, ast.Import) and any(alias.name.startswith("genlayer") for alias in node.names))
            or (isinstance(node, ast.ImportFrom) and (node.module or "").startswith("genlayer"))
        )
        for node in tree.body
    ):
        warnings.append("No `genlayer` import was found. The file may still be valid, but it does not obviously use GenLayer helpers.")

    first_line = normalized_code.splitlines()[0].strip() if normalized_code.splitlines() else ""
    if not first_line.startswith('# { "Depends"') and not first_line.startswith("# { 'Depends'"):
        warnings.append('Missing version header. GenLayer contracts should start with: # { "Depends": "py-genlayer:<hash>" }')

    if not any(
        isinstance(node, ast.FunctionDef) and node.name == "__init__"
        for class_def in class_defs
        for node in class_def.body
    ):
        warnings.append("No constructor (`__init__`) was found. If your contract needs deployment parameters, add one before deploying.")

    return {
        "valid": True,
        "message": f"Contract file passed validation with {len(class_defs)} class definition(s).",
        "errors": [],
        "warnings": warnings,
        "contract_names": [class_def.name for class_def in class_defs],
    }
