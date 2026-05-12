The repository structure is:
    genlayer-bot/
    ├── backend/
    │   ├── main.py
    │   ├── genlayer_client.py
    │   ├── intent_parser.py
    │   ├── safety.py
    │   ├── simulator.py
    │   ├── contract_validation.py
    │   ├── contract_generator.py
    │   ├── database.py
    │   ├── models.py
    │   ├── logs_store.py
    │   ├── network_config.py
    │   ├── schemas.py
    │   ├── requirements.txt
    │   ├── .env.example
    │   ├── Dockerfile
    │   ├── Procfile
    │   ├── railway.json
    │   └── routers/
    │       ├── chat.py
    │       ├── wallet.py
    │       ├── logs.py
    │       └── users.py
    └── frontend/
        ├── package.json
        ├── next.config.ts
        ├── vercel.json
        ├── Procfile
        └── src/
            ├── config.ts
            ├── app/
            │   ├── layout.tsx
            │   └── page.tsx
            ├── components/
            │   ├── ChatInterface.tsx
            │   ├── Web3Provider.tsx
            │   ├── ConnectWalletButton.tsx
            │   ├── CommandPalette.tsx
            │   ├── ConfirmationButtons.tsx
            │   ├── DeployContractPanel.tsx
            │   ├── IntentCard.tsx
            │   ├── LiveLogsPanel.tsx
            │   ├── Message.tsx
            │   ├── QuickActions.tsx
            │   ├── RiskIndicator.tsx
            │   ├── SimulationCard.tsx
            │   └── WalletConnect.tsx
            ├── context/
            │   └── WalletContext.tsx
            └── lib/
                └── api.ts

  Your task is to apply ALL of the following fixes exactly as described, in the exact files
  specified. Do not skip any step. Do not add features beyond what is described. Do not
  rename variables or restructure files unless the fix explicitly requires it. After
  completing every fix, output a final deployment checklist that the developer must complete
  manually in their Railway and Vercel dashboards.

  Read the current content of every file before editing it.

  ---

  ## FIX 1 — CORS: Replace wildcard origin with environment-driven allowlist
  **File:** `backend/main.py`

  The current code sets `allow_origins=["*"]` combined with `allow_credentials=True`. This
  combination is forbidden by the CORS specification and causes browsers to reject all
  credentialed requests. Fix it by reading a comma-separated `ALLOWED_ORIGINS` environment
  variable and splitting it into a list. Fall back to `http://localhost:3000` if the variable
  is not set.

  Replace the existing `add_middleware` call with:

  ```python
  ALLOWED_ORIGINS = [
      o.strip()
      for o in os.getenv("ALLOWED_ORIGINS", "localhost:3000").split(",")
      if o.strip()
  ]

  app.add_middleware(
      CORSMiddleware,
      allow_origins=ALLOWED_ORIGINS,
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )

  Ensure import os is already present at the top of the file (it is — do not add a
  duplicate).

  ---
  FIX 2 — requirements.txt: Add missing critical packages

  File: backend/requirements.txt

  The following packages are imported directly in the backend code but are absent from
  requirements.txt: web3, eth-abi, eth-utils. Add them with minimum version pins.
  Also add asyncio is built-in and does not need to be listed.

  The final requirements.txt must contain exactly these entries (preserve existing entries,
  only add the three missing ones):

  fastapi
  uvicorn
  groq
  genlayer-py>=0.1.0,<0.6.0
  python-dotenv
  pydantic>=2.4.0
  httpx
  sqlalchemy>=2.0.0
  cryptography>=42.0.0
  python-jose[cryptography]>=3.3.0
  passlib[bcrypt]>=1.7.4
  psycopg2-binary>=2.9.9
  web3>=6.0.0
  eth-abi>=4.0.0
  eth-utils>=2.0.0

  ---
  FIX 3 — package.json: Fix non-existent lucide-react version

  File: frontend/package.json

  The current version "lucide-react": "^1.11.0" does not exist on npm and will cause
  npm install to fail, preventing the entire frontend from building. Replace it with the
  latest stable version from the 0.x release line:

  "lucide-react": "^0.400.0"

  Do not change any other dependency versions.

  ---
  FIX 4 — genlayer_client.py: Make all RPC calls and receipt polling fully async

  File: backend/genlayer_client.py

  This is the most structurally significant fix. The current code uses synchronous
  httpx.post() and time.sleep() inside methods that are called from async FastAPI route
  handlers. Both block the entire asyncio event loop, meaning no other requests can be
  served while waiting for an RPC response or transaction receipt. All blocking I/O must be
  replaced with async equivalents.

  Apply the following changes:

  4a — Replace import time with import asyncio and change httpx import

  At the top of the file:
  - Remove import time
  - Add import asyncio
  - Keep import httpx as-is (it supports both sync and async clients)

  4b — Make _rpc_call async using httpx.AsyncClient

  Replace the entire _rpc_call method with:

  async def _rpc_call(self, method: str, params: list):
      payload = {
          "jsonrpc": "2.0",
          "method": method,
          "params": params,
          "id": 1,
      }
      async with httpx.AsyncClient() as client:
          response = await client.post(self.rpc_url, json=payload, timeout=30.0)
      response.raise_for_status()
      data = response.json()
      if "error" in data and data["error"]:
          raise RuntimeError(data["error"].get("message", str(data["error"])))
      return data.get("result")

  4c — Make _wait_for_receipt_or_raise async using asyncio.sleep

  Replace the entire _wait_for_receipt_or_raise method with:

  async def _wait_for_receipt_or_raise(self, tx_hash: str):
      loop = asyncio.get_event_loop()
      deadline = loop.time() + self.receipt_timeout_sec
      while loop.time() < deadline:
          receipt = await self._rpc_call("eth_getTransactionReceipt", [tx_hash])
          if receipt:
              status_hex = receipt.get("status")
              if status_hex in ("0x1", 1):
                  return
              raise RuntimeError(
                  f"Transaction reverted on-chain. status={status_hex}"
              )
          await asyncio.sleep(self.receipt_poll_interval_sec)
      raise RuntimeError(
          f"Timed out waiting for transaction receipt after {self.receipt_timeout_sec}s"
      )

  4d — Make all methods that call _rpc_call or _wait_for_receipt_or_raise async

  Convert the following methods from def to async def and add await to every internal
  call to _rpc_call or _wait_for_receipt_or_raise:

  - get_balance → async def get_balance
  - send_transfer → async def send_transfer
  - deploy_contract → async def deploy_contract
  - build_deploy_transaction → async def build_deploy_transaction
  - get_consensus_transaction_id → async def get_consensus_transaction_id
  - get_deployment_details → async def get_deployment_details

  Within each of these methods, prefix every call to self._rpc_call(...) with await,
  and prefix every call to self._wait_for_receipt_or_raise(...) with await.

  4e — Make module-level wrapper functions async

  At the bottom of genlayer_client.py, the following module-level functions must also
  become async def and use await:

  async def get_balance(address: str, private_key: str = None, network: str | None = None) -> float:
      return await get_client(private_key, network=network).get_balance(address)

  async def send_transfer(to_address: str, amount: float, private_key: str = None, network: str | None = None) -> str:
      return await get_client(private_key, network=network).send_transfer(to_address, amount)

  async def deploy_contract(code: str, args: list = [], private_key: str = None, network: str | None = None) -> str:
      return await get_client(private_key, network=network).deploy_contract(code, args)

  4f — Update all callers in routers/chat.py

  In backend/routers/chat.py, every call to get_balance, send_transfer,
  client.build_deploy_transaction, client.get_consensus_transaction_id,
  client.get_deployment_details, client._wait_for_receipt_or_raise, and
  client._rpc_call must be prefixed with await. The route handler functions are already
  async def, so only await needs to be added to the calls.

  ---
  FIX 5 — genlayer_client.py: Remove the broken deploy_contract method and its export

  File: backend/genlayer_client.py

  The deploy_contract instance method encodes Python contract source code as raw UTF-8 hex
  in the data field of a standard EVM creation transaction:
  "data": Web3.to_hex(text=code),
  This completely bypasses the GenLayer consensus contract ABI encoding that
  build_deploy_transaction correctly performs. If called, it would produce an invalid
  transaction. The current flow does not call this method (deployments use
  build_deploy_transaction + wallet-side signing), so it is dead code.

  Remove:
  1. The entire deploy_contract instance method from the GenLayerClientWrapper class
  2. The module-level deploy_contract wrapper function at the bottom of the file
  3. Any import of deploy_contract in other files (check routers/chat.py — remove it
  from that import line if present, but do not remove the import line itself if other
  names are imported from the same module)

  ---
  FIX 6 — models.py: Crash on missing ENCRYPTION_KEY instead of regenerating it

  File: backend/models.py

  The current code generates a new Fernet encryption key if ENCRYPTION_KEY is not set in
  the environment. Since the key changes every time the process starts, any private keys
  already stored in the database become permanently unreadable after a restart. There is no
  error message.

  Replace the key initialization block with code that raises a RuntimeError at startup if
  the key is missing:

  import os
  from cryptography.fernet import Fernet

  _raw_key = os.getenv("ENCRYPTION_KEY")
  if not _raw_key:
      raise RuntimeError(
          "ENCRYPTION_KEY environment variable is not set. "
          "Generate a key with: "
          "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
          " — then set it as a permanent environment variable. "
          "Never regenerate this key once data has been encrypted with it."
      )

  fernet = Fernet(_raw_key.encode())

  Replace all existing usages of the old fernet or cipher variable throughout models.py
  with this fernet instance. Do not change the set_private_key or get_private_key
  method signatures.

  ---
  FIX 7 — database.py: Explicitly import models inside init_db()

  File: backend/database.py

  The init_db() function calls Base.metadata.create_all(bind=engine) but never imports
  the model classes. SQLAlchemy only registers table definitions when the model class is
  imported. If init_db() runs before any router has imported the models, no tables are
  created and every database operation fails at runtime with no startup error.

  Replace the init_db function with:

  def init_db():
      # Import models here to ensure their table definitions are registered
      # with Base.metadata before create_all is called, regardless of
      # import order in the application startup sequence.
      try:
          from .models import User, PlatformWallet  # noqa: F401
      except ImportError:
          from models import User, PlatformWallet  # noqa: F401
      Base.metadata.create_all(bind=engine)

  ---
  FIX 8 — ChatInterface.tsx: Show error to user when sendMessage fails

  File: frontend/src/components/ChatInterface.tsx

  Inside handleSubmit, the catch block currently only calls console.error(error) and
  does nothing visible to the user. When the backend is unreachable or times out, the loading
  spinner disappears silently and the user's message is shown with no response.

  Replace the catch block inside handleSubmit with:

  } catch (error) {
    const message =
      error instanceof Error
        ? error.message
        : 'Failed to reach the server. Please try again.';
    setMessages(prev => [
      ...prev,
      {
        id: (Date.now() + 1).toString(),
        role: 'bot',
        content: message,
        status: 'error',
      },
    ]);
  } finally {
    setIsLoading(false);
  }

  ---
  FIX 9 — page.tsx: Remove hardcoded "0xDavid" placeholder

  File: frontend/src/app/page.tsx

  The left panel of the terminal layout contains a hardcoded "0xDavid" entry displayed as an
  active online connection. This is placeholder test data that was never removed. It displays
  to real users as if it represents live network state.

  Find the element rendering "0xDavid" (or any similar hardcoded address/name in the
  connections panel) and remove it entirely. If the connections list becomes empty after
  removal, replace the entire connections section with a simple static label:

  <div className="text-[10px] uppercase tracking-widest text-text-muted font-mono px-4 pt-4">
    No active connections
  </div>

  Do not add fake placeholder data of any kind.

  ---
  FIX 10 — .env.example: Clarify network variable naming

  File: backend/.env.example

  The current file uses GENLAYER_RPC_URL as the key for the bradbury RPC URL. This is
  ambiguous because network_config.py first checks GENLAYER_RPC_URL_BRADBURY, then falls
  back to GENLAYER_RPC_URL. A developer who sets only GENLAYER_RPC_URL with the bradbury
  endpoint but uses the default network (studionet) will connect to the wrong RPC silently.

  Replace the RPC URL section with clearly labeled, network-specific variables:

  # === GenLayer Network Configuration ===
  # Studionet (default network for this app)
  GENLAYER_RPC_URL_STUDIONET=studio.genlayer.com/api

  # Bradbury testnet
  GENLAYER_RPC_URL_BRADBURY=rpc-bradbury.genlayer.com

  # === Wallet Configuration ===
  WALLET_PRIVATE_KEY=your_wallet_private_key_here
  WALLET_ADDRESS=your_wallet_address_here
  MAX_TRANSFER_AMOUNT=1000

  # === Database ===
  DATABASE_URL=sqlite:///./genlayer_bot.db

  # === Security ===
  # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ENCRYPTION_KEY=

  # === CORS ===
  # Comma-separated list of allowed frontend origins
  ALLOWED_ORIGINS=localhost:3000

  # === AI ===
  GROQ_API_KEY=your_groq_api_key_here

  ---
  FIX 11 — railway.json: Add health check configuration

  File: backend/railway.json

  The /health endpoint already exists in main.py. Wire it into the Railway deployment
  config so Railway knows when the backend is genuinely ready to receive traffic and will
  auto-restart on failure.

  Replace the contents of railway.json with:

  {
    "$schema": "railway.app/railway.schema.json",
    "build": {
      "builder": "NIXPACKS"
    },
    "deploy": {
      "healthcheckPath": "/health",
      "healthcheckTimeout": 30,
      "restartPolicyType": "ON_FAILURE",
      "restartPolicyMaxRetries": 5
    }
  }

  ---
  FIX 12 — api.ts: Increase confirmAction timeout to outlast backend receipt polling

  File: frontend/src/lib/api.ts

  The backend's _wait_for_receipt_or_raise polls for a transaction receipt for up to 45
  seconds by default (TX_RECEIPT_TIMEOUT_SEC=45). If the frontend's confirmAction HTTP
  call times out before the backend finishes polling, the user sees a network error even
  though the transaction may have succeeded.

  Find the confirmAction function in api.ts. If it uses an AbortController or
  setTimeout for timeout, increase the timeout value to 65000 milliseconds (65 seconds
  — 45s backend receipt wait + 15s buffer + 5s HTTP overhead).

  If no explicit timeout exists on confirmAction, add one:

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 65_000);
  try {
    const response = await fetch(`${API_BASE_URL}/chat/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    // ... rest of existing response handling
  } finally {
    clearTimeout(timeoutId);
  }

  Preserve all existing response parsing and error handling logic. Only change the timeout
  value / add the AbortController if missing.

  ---
  FIX 13 — network_config.py: Add studionet as the documented default

  File: backend/network_config.py

  Add a module-level comment at the top of the file documenting that studionet is the
  application default and explaining what happens when no network is passed:

  # Supported networks: "studionet" (default), "bradbury"
  # When network=None is passed to get_network_config(), it resolves to "studionet".
  # Set GENLAYER_RPC_URL_STUDIONET or GENLAYER_RPC_URL_BRADBURY in your environment.

  Do not change any logic in this file — only add this comment block at the top, below any
  existing imports.

  ---
  POST-FIX: Output a Railway → Vercel Deployment Checklist

  After applying all fixes above, output the following checklist exactly as formatted below.
  This is for the developer to complete manually — do not attempt to execute these steps:

  ============================================================
  DEPLOYMENT CHECKLIST — Complete these steps manually
  ============================================================

  STEP 1 — Generate your ENCRYPTION_KEY (run this once, save the output permanently):
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

  STEP 2 — Get a WalletConnect Project ID:
    Visit: cloud.walletconnect.com
    Create a new project.
    Under "Allowed Domains" add: localhost:3000
    (You will add your Vercel domain in Step 8.)
    Copy the Project ID.

  STEP 3 — Deploy backend to Railway:
    a. Go to railway.app → New Project → Deploy from GitHub repo
    b. Select the genlayer-bot repo, set root directory to: /backend
    c. Verify the Procfile contains:
         web: uvicorn main:app --host 0.0.0.0 --port $PORT
    d. Under Variables, set ALL of the following:
         GROQ_API_KEY             = <your Groq API key>
         WALLET_PRIVATE_KEY       = <your wallet private key>
         WALLET_ADDRESS           = <your wallet address>
         GENLAYER_RPC_URL_STUDIONET = studio.genlayer.com/api
         GENLAYER_RPC_URL_BRADBURY  = rpc-bradbury.genlayer.com
         MAX_TRANSFER_AMOUNT      = 1000
         DATABASE_URL             = sqlite:///./genlayer_bot.db
         ENCRYPTION_KEY           = <output from Step 1>
         ALLOWED_ORIGINS          = localhost:3000  ← temporary, update in Step 7
    e. Deploy. Copy the Railway URL (e.g. genlayer-bot-production.up.railway.app)

  STEP 4 — Deploy frontend to Vercel:
    a. Go to vercel.com → Add New Project → import the genlayer-bot repo
    b. Set Root Directory to: frontend
    c. Framework preset: Next.js (auto-detected)
    d. Under Environment Variables, set ALL of the following:
         NEXT_PUBLIC_API_BASE_URL              = <Railway URL from Step 3e>
         NEXT_PUBLIC_WALLET_CONNECT_PROJECT_ID = <WalletConnect Project ID from Step 2>
         NEXT_PUBLIC_GENLAYER_RPC_URL_STUDIONET = studio.genlayer.com/api
         NEXT_PUBLIC_GENLAYER_RPC_URL_BRADBURY  = rpc-bradbury.genlayer.com
    e. Deploy. Copy the Vercel URL (e.g. your-app.vercel.app)

  STEP 5 — Run npm install locally to verify the lucide-react fix:
    cd frontend && npm install
    Confirm no errors. If lucide-react icons look different, check icon name changes
    in the 0.400.0 changelog: github.com/lucide-icons/lucide/releases

  STEP 6 — Update CORS on Railway to allow your Vercel domain:
    Go to Railway → your project → Variables
    Update ALLOWED_ORIGINS to:
      your-app.vercel.app
    If you have a custom domain, append it:
      your-app.vercel.app,https://yourdomain.com
    Railway will redeploy automatically.

  STEP 7 — Add Vercel domain to WalletConnect:
    Go to cloud.walletconnect.com → your project → Allowed Domains
    Add: your-app.vercel.app
    Save. Without this, WalletConnect will refuse to initialize on the live frontend.

  STEP 8 — Verify end-to-end:
    a. Open your Vercel URL in a browser
    b. Open DevTools → Network tab
    c. Connect a wallet via RainbowKit
    d. Type "check my balance" and confirm
    e. Verify:
         - No CORS errors in the Network tab
         - The balance response arrives within 30 seconds
         - The WalletConnect modal opens without errors
         - The Railway /health endpoint returns {"status": "healthy"}

  STEP 9 — Optional: Add custom domain
    In Vercel: Settings → Domains → Add your domain
    In Railway: Settings → Networking → Custom Domain
    After adding both, update ALLOWED_ORIGINS in Railway to include the custom domain.

  ============================================================
  SECURITY REMINDERS
  ============================================================
    - WALLET_PRIVATE_KEY is a server-side admin key used only for the /fund endpoint.
      Never expose it on the frontend. Never commit it to git.
    - ENCRYPTION_KEY must never be rotated once data is in the database.
      Store it in a password manager as a permanent secret.
    - The current auth system trusts wallet addresses without cryptographic proof.
      Before launching to real users with real funds, implement signed-message
      authentication (sign a server-issued nonce with the wallet, verify on backend).
  ============================================================

  ---
  CONSTRAINTS — Read before starting

  1. Read every file before editing it. Never overwrite content you have not read.
  2. Apply fixes in the order numbered above (1 through 13). Some fixes depend on earlier
  ones (Fix 4 must happen before Fix 6's callers are updated).
  3. Do not add comments to code unless a fix explicitly instructs you to.
  4. Do not rename any existing variables, functions, classes, or files unless a fix
  explicitly requires it.
  5. Do not refactor code that is not directly related to a numbered fix.
  6. Do not add new dependencies beyond what Fix 2 and Fix 3 specify.
  7. Do not create new files unless a fix explicitly requires it.
  8. After all fixes are applied, output the deployment checklist from the POST-FIX section
  verbatim.
  9. If a file referenced in a fix does not exist or cannot be read, report the error
  clearly and stop — do not guess or substitute a different file.
  10. Do not push to any remote, deploy to any service, or run git commit at any point.