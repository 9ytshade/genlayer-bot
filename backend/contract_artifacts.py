from __future__ import annotations

from functools import lru_cache
import hashlib
from importlib import metadata
from pathlib import Path
import platform
from typing import Literal


ArtifactOrigin = Literal["generated", "workflow", "notary", "uploaded"]

ARTIFACT_FORMAT_VERSION = 1
PY_GENLAYER_DEPENDENCY = "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6"
PINNED_DEPENDENCY_HEADER = f'# {{ "Depends": "{PY_GENLAYER_DEPENDENCY}" }}'


class ContractSourceIntegrityError(ValueError):
    """The submitted source does not match the artifact the user reviewed."""


class StaleContractReviewError(ContractSourceIntegrityError):
    """The generator, validator, or runtime changed after source review."""


def source_hash(code: str) -> str:
    return "0x" + hashlib.sha256(code.encode("utf-8")).hexdigest()


def dependency_from_source(code: str) -> str | None:
    first_line = code.replace("\r\n", "\n").split("\n", 1)[0].strip()
    if first_line == PINNED_DEPENDENCY_HEADER:
        return PY_GENLAYER_DEPENDENCY
    return None


def _file_fingerprint(label: str, *paths: Path) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.read_bytes())
    return f"{label}:sha256:{digest.hexdigest()}"


@lru_cache(maxsize=None)
def generator_version(origin: ArtifactOrigin) -> str:
    backend_dir = Path(__file__).resolve().parent
    if origin == "generated":
        return _file_fingerprint("contract-generator", backend_dir / "generators" / "contract_generator.py")
    if origin == "workflow":
        return _file_fingerprint("workflow-generator", backend_dir / "services" / "workflow_service.py")
    if origin == "notary":
        return _file_fingerprint("notary-generator", backend_dir / "services" / "notary_service.py")
    return "user-supplied-source"


@lru_cache(maxsize=1)
def validator_version() -> str:
    backend_dir = Path(__file__).resolve().parent
    return _file_fingerprint(
        "contract-validator",
        backend_dir / "contract_validation.py",
        backend_dir / "validators" / "contract_validator.py",
    )


@lru_cache(maxsize=1)
def compiler_version() -> str:
    return f"{platform.python_implementation().lower()}-ast:{platform.python_version()}"


@lru_cache(maxsize=1)
def genlayer_sdk_version() -> str:
    try:
        return metadata.version("genlayer-py")
    except metadata.PackageNotFoundError:
        return "unavailable"


def artifact_metadata(code: str, origin: ArtifactOrigin) -> dict[str, str | int]:
    return {
        "artifact_version": ARTIFACT_FORMAT_VERSION,
        "source_hash": source_hash(code),
        "source_origin": origin,
        "py_genlayer_dependency": PY_GENLAYER_DEPENDENCY,
        "genlayer_sdk_version": genlayer_sdk_version(),
        "generator_version": generator_version(origin),
        "validator_version": validator_version(),
        "compiler_version": compiler_version(),
    }


def verify_reviewed_source(
    *,
    code: str,
    origin: ArtifactOrigin,
    reviewed_source_hash: str | None,
    reviewed_py_genlayer_dependency: str | None,
    reviewed_generator_version: str | None,
    reviewed_validator_version: str | None,
) -> dict[str, str | int]:
    current = artifact_metadata(code, origin)
    if not reviewed_source_hash:
        raise ContractSourceIntegrityError("A reviewed contract source hash is required before deployment.")
    if reviewed_source_hash.lower() != str(current["source_hash"]).lower():
        raise StaleContractReviewError(
            "The contract source changed after review. Review the current backend-generated source before deploying."
        )
    if dependency_from_source(code) != PY_GENLAYER_DEPENDENCY:
        raise ContractSourceIntegrityError(
            f"Contract source must pin the supported GenVM dependency: {PY_GENLAYER_DEPENDENCY}."
        )
    if reviewed_py_genlayer_dependency != current["py_genlayer_dependency"]:
        raise StaleContractReviewError(
            "The pinned GenVM dependency changed after review. Regenerate or revalidate the contract."
        )
    if reviewed_generator_version != current["generator_version"]:
        raise StaleContractReviewError(
            "The backend contract generator changed after review. Regenerate or revalidate the contract."
        )
    if reviewed_validator_version != current["validator_version"]:
        raise StaleContractReviewError(
            "The contract validator changed after review. Revalidate the contract before deploying."
        )
    return current
