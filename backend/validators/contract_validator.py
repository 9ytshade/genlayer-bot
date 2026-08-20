import ast
from typing import Any

from ..contract_artifacts import PINNED_DEPENDENCY_HEADER, dependency_from_source
from ..contract_validation import validate_python_contract


FORBIDDEN_IMPORTS = {"os", "subprocess", "socket", "requests", "httpx", "urllib", "pathlib", "shutil"}
FORBIDDEN_CALLS = {"eval", "exec", "open", "compile", "__import__"}
UNSAFE_TYPES = {"Any", "float"}
UNSUPPORTED_STORAGE_TYPES = {"Any", "dict", "float", "int", "list", "set", "tuple"}
SUPPORTED_STORAGE_TYPES = {"Address", "bool", "bytes", "DynArray", "i256", "str", "TreeMap", "u256"}
NONDETERMINISTIC_CALLS = {
    "gl.nondet.exec_prompt",
    "gl.nondet.web.get",
    "gl.nondet.web.render",
}
EQUIVALENCE_CALLS = {
    "gl.eq_principle.prompt_comparative",
    "gl.eq_principle.prompt_non_comparative",
    "gl.eq_principle.strict_eq",
    "gl.vm.run_nondet_unsafe",
}


class ContractValidator:
    """Fail-closed static preflight for generated and uploaded GenLayer contracts."""

    def validate(self, code: str) -> dict[str, Any]:
        base = validate_python_contract(code)
        if not base["valid"]:
            return base

        tree = ast.parse(code)
        errors: list[str] = []
        warnings = list(base.get("warnings", []))

        if dependency_from_source(code) is None:
            errors.append(f"Contract must start with the pinned dependency header: {PINNED_DEPENDENCY_HEADER}")

        contract_classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and _is_contract_class(node)]
        if len(contract_classes) != 1:
            errors.append("Source must define exactly one top-level gl.Contract subclass.")

        boundary_functions = _equivalence_boundary_functions(tree)
        parent_map = _parent_map(tree)

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
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "float":
                errors.append("Floating-point arithmetic is forbidden in Intelligent Contracts.")
            elif isinstance(node, ast.Constant) and isinstance(node.value, float):
                errors.append("Floating-point literals are forbidden in Intelligent Contracts.")
            elif isinstance(node, ast.Call) and _dotted_name(node.func) in NONDETERMINISTIC_CALLS:
                containing_function = _containing_function(node, parent_map)
                if containing_function is None or containing_function.name not in boundary_functions:
                    errors.append(
                        "Nondeterministic GenLayer calls must execute inside a function passed to an "
                        "Equivalence Principle boundary."
                    )
            elif _is_loose_consensus_substring_check(node):
                errors.append(
                    "Consensus decisions must use validated structured output, not TRUE/FALSE/PASS/FAIL substring checks."
                )

        for class_def in contract_classes:
            errors.extend(_validate_contract_class(class_def))

        if errors:
            return {
                "valid": False,
                "message": "Generated contract failed GenLayer-aware validation.",
                "errors": _deduplicate(errors),
                "warnings": _deduplicate(warnings),
                "contract_names": base.get("contract_names", []),
            }

        return {**base, "warnings": _deduplicate(warnings)}


def _validate_contract_class(class_def: ast.ClassDef) -> list[str]:
    errors: list[str] = []
    public_method_count = 0

    for statement in class_def.body:
        if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            type_name = _annotation_name(statement.annotation)
            if type_name in UNSUPPORTED_STORAGE_TYPES:
                errors.append(
                    f"Storage field '{statement.target.id}' uses unsupported type '{type_name}'. "
                    "Use a GenVM-supported type or typed TreeMap/DynArray."
                )
            elif type_name not in SUPPORTED_STORAGE_TYPES:
                errors.append(
                    f"Storage field '{statement.target.id}' uses unsupported or unknown type '{type_name}'."
                )
            elif type_name in {"TreeMap", "DynArray"} and not isinstance(statement.annotation, ast.Subscript):
                errors.append(f"Storage field '{statement.target.id}' must fully parameterize {type_name}.")
        elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            decorators = {_dotted_name(decorator) for decorator in statement.decorator_list}
            public_decorators = {
                decorator for decorator in decorators if decorator.startswith("gl.public.write") or decorator == "gl.public.view"
            }
            if not public_decorators:
                continue
            public_method_count += 1
            for argument in [*statement.args.posonlyargs, *statement.args.args, *statement.args.kwonlyargs]:
                if argument.arg == "self":
                    continue
                if argument.annotation is None:
                    errors.append(f"Public method '{statement.name}' must type every parameter.")
                elif _annotation_name(argument.annotation) in UNSAFE_TYPES:
                    errors.append(
                        f"Public method '{statement.name}' uses unsupported parameter type "
                        f"'{_annotation_name(argument.annotation)}'."
                    )
            if statement.returns is not None and _annotation_name(statement.returns) in UNSAFE_TYPES:
                errors.append(
                    f"Public method '{statement.name}' uses unsupported return type "
                    f"'{_annotation_name(statement.returns)}'."
                )
            if _contains_message_value(statement) and not any(
                decorator.endswith(".payable") for decorator in public_decorators
            ):
                errors.append(f"Public method '{statement.name}' reads gl.message.value but is not payable.")

    if public_method_count == 0:
        errors.append("Generated contract must expose at least one @gl.public.write or @gl.public.view method.")
    return errors


def _is_contract_class(node: ast.ClassDef) -> bool:
    return any(_dotted_name(base) in {"gl.Contract", "gl.contract.Contract"} for base in node.bases)


def _annotation_name(annotation: ast.expr) -> str:
    if isinstance(annotation, ast.Name):
        return annotation.id
    if isinstance(annotation, ast.Attribute):
        return annotation.attr
    if isinstance(annotation, ast.Subscript):
        return _annotation_name(annotation.value)
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        return annotation.value.split("[", 1)[0]
    return ast.unparse(annotation)


def _dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _equivalence_boundary_functions(tree: ast.AST) -> set[str]:
    functions: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _dotted_name(node.func) not in EQUIVALENCE_CALLS:
            continue
        for argument in node.args:
            if isinstance(argument, ast.Name):
                functions.add(argument.id)
        for keyword in node.keywords:
            if isinstance(keyword.value, ast.Name):
                functions.add(keyword.value.id)
    return functions


def _parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}


def _containing_function(node: ast.AST, parent_map: dict[ast.AST, ast.AST]) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    current = node
    while current in parent_map:
        current = parent_map[current]
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return current
    return None


def _contains_message_value(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(_dotted_name(node) == "gl.message.value" for node in ast.walk(function))


def _is_loose_consensus_substring_check(node: ast.AST) -> bool:
    if not isinstance(node, ast.Compare) or not any(isinstance(operator, (ast.In, ast.NotIn)) for operator in node.ops):
        return False
    values = [node.left, *node.comparators]
    return any(
        isinstance(value, ast.Constant)
        and isinstance(value.value, str)
        and value.value.strip().upper() in {"TRUE", "FALSE", "PASS", "FAIL"}
        for value in values
    )


def _deduplicate(messages: list[str]) -> list[str]:
    return list(dict.fromkeys(messages))
