"""Simple transfer simulation script for maintainers.

Usage (local):
  export WALLET_PRIVATE_KEY=0x...    # ephemeral test key only
  export GENLAYER_RPC_URL_STUDIONET=https://studio.genlayer.com/api
  export GENLAYER_CHAIN_ID_STUDIONET=61999
  python3 test_transfer_sim.py

The script will only execute a broadcast if WALLET_PRIVATE_KEY and RUN_TRANSFER_TEST=1 are set.
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

RUN = os.getenv("RUN_TRANSFER_TEST", "0") == "1"
PRIVATE_KEY = os.getenv("WALLET_PRIVATE_KEY")
NETWORK = os.getenv("TEST_NETWORK", "studionet")
RECIPIENT = os.getenv("TEST_RECIPIENT", "0x1111111111111111111111111111111111111111")
AMOUNT = float(os.getenv("TEST_AMOUNT", "0.001"))

if not PRIVATE_KEY:
    print("WALLET_PRIVATE_KEY not set. Skipping live transfer test.")
    sys.exit(0)

if not RUN:
    print("RUN_TRANSFER_TEST != 1. To run live transfer set RUN_TRANSFER_TEST=1. Exiting.")
    sys.exit(0)

print(f"Running transfer test on network={NETWORK} sending {AMOUNT} GEN to {RECIPIENT}")

try:
    from genlayer_client import send_transfer
except Exception:
    # fallback if running from package context
    from .genlayer_client import send_transfer

try:
    tx_hash = send_transfer(RECIPIENT, AMOUNT, private_key=PRIVATE_KEY, network=NETWORK)
    print(f"Broadcasted tx: {tx_hash}")
except Exception as e:
    print(f"Transfer test failed: {e}")
    raise
