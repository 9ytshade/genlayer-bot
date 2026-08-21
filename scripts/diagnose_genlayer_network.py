"""Read-only GenLayer consensus and execution diagnostic.

Example: python scripts/diagnose_genlayer_network.py --network studionet --tx-id 0x...
"""

from __future__ import annotations

import argparse
import asyncio

from backend.genlayer_client import GenLayerClientWrapper
from backend.network_diagnostics import diagnose_transaction, diagnostic_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose a GenLayer transaction without broadcasting anything.")
    parser.add_argument("--network", required=True, choices=("studionet", "bradbury", "localnet"))
    parser.add_argument("--tx-id", required=True, help="32-byte GenLayer consensus transaction ID")
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    client = GenLayerClientWrapper(network=args.network)
    try:
        print(diagnostic_json(await diagnose_transaction(client, args.tx_id)))
    finally:
        await client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
