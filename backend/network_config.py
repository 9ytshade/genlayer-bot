import os

SUPPORTED_NETWORKS = ("bradbury", "studionet")
DEFAULT_NETWORK = "studionet"


def normalize_network(network: str | None) -> str:
    if not network:
        return DEFAULT_NETWORK
    normalized = str(network).strip().lower()
    if normalized not in SUPPORTED_NETWORKS:
        raise ValueError(
            f"Unsupported network '{network}'. Supported networks: {', '.join(SUPPORTED_NETWORKS)}"
        )
    return normalized


def get_network_config(network: str | None) -> tuple[str, str, int]:
    normalized = normalize_network(network)

    if normalized == "studionet":
        rpc_url = os.getenv("GENLAYER_RPC_URL_STUDIONET")
        chain_id = int(os.getenv("GENLAYER_CHAIN_ID_STUDIONET", "61999"))
    else:
        rpc_url = os.getenv("GENLAYER_RPC_URL_BRADBURY") or os.getenv("GENLAYER_RPC_URL")
        chain_id = int(
            os.getenv("GENLAYER_CHAIN_ID_BRADBURY")
            or os.getenv("GENLAYER_CHAIN_ID", "4221")
        )

    if not rpc_url:
        raise ValueError(
            f"RPC URL is not configured for '{normalized}'. "
            "Set GENLAYER_RPC_URL_BRADBURY/GENLAYER_RPC_URL_STUDIONET."
        )

    return normalized, rpc_url, chain_id
