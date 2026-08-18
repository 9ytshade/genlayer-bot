# Production Infrastructure Provisioning and Verification

This runbook provisions or verifies the infrastructure for the nine functioning feature families. If the services were created during the earlier deployment, skip resource creation and start at the inventory and verification steps. It intentionally stops before broadcasting a real GenLayer consensus transaction.

## Existing Deployment First

Before creating anything, check the existing provider dashboards:

- Render: confirm the existing backend web service and its public URL.
- Supabase: confirm the existing production project and database.
- Redis provider: confirm the existing instance and TLS connection URL.
- Vercel: confirm the existing frontend project and production domain.
- WalletConnect Cloud: confirm the existing project ID and allowed domain.

Do not create a second resource if the existing resource is healthy and belongs to this application. Compare configuration and run the verification gates below instead.

Repository evidence already present:

- Render deployment files: `backend/Procfile` and `backend/Dockerfile`.
- Vercel deployment files: `frontend/vercel.json` and `frontend/Procfile`.
- Local backend and frontend environment files exist, but their secret values are intentionally not inspected or displayed.
- The local `/health` and `/ready` endpoints currently respond successfully.

This local evidence does not prove that the remote Render, Supabase, Redis, or Vercel resources are currently healthy.

## Manual Secret Placement

Never send secret values in chat or commit them to Git. Use these locations:

- Production backend secrets: existing Render service -> `Environment` -> `Environment Variables`.
- Production frontend configuration: existing Vercel project -> `Settings` -> `Environment Variables` -> `Production`.
- Local backend configuration: `backend/.env` only.
- Local frontend configuration: `frontend/.env.local` only.
- Supabase and Redis passwords go into Render only, never Vercel.

Backend-only secrets:

```text
DATABASE_URL=<Supabase server-side Postgres URL with sslmode=require>
JWT_SECRET=<random secret of at least 32 characters>
GROQ_API_KEY=<Groq API key>
REDIS_URL=<managed Redis TLS URL, normally rediss://...>
```

Generate a JWT secret locally when needed:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Frontend values are public because they use `NEXT_PUBLIC_`:

```text
NEXT_PUBLIC_API_URL=https://<existing-render-backend>
NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID=<WalletConnect project ID>
NEXT_PUBLIC_BRADBURY_CHAIN_ID=4221
NEXT_PUBLIC_BRADBURY_RPC=<approved Bradbury RPC URL>
NEXT_PUBLIC_STUDIONET_CHAIN_ID=61999
NEXT_PUBLIC_STUDIONET_RPC=<approved Studionet RPC URL>
```

Never place `DATABASE_URL`, `JWT_SECRET`, `REDIS_URL`, or `GROQ_API_KEY` in a frontend variable.

## Render Variables

In the existing Render backend service, add or update these production variables:

```text
APP_ENV=production
GENLAYER_PHASE9_LIVE_PROOF=0
SIWE_ORIGINS=https://<production-frontend-domain>
SIWE_CHAIN_IDS=4221,61999
ALLOWED_ORIGINS=https://<production-frontend-domain>
GENLAYER_RPC_URL_BRADBURY=<approved Bradbury RPC URL>
GENLAYER_RPC_URL_STUDIONET=<approved Studionet RPC URL>
GENLAYER_CHAIN_ID_BRADBURY=4221
GENLAYER_CHAIN_ID_STUDIONET=61999
RPC_REQUEST_TIMEOUT_SEC=15
RPC_MAX_ATTEMPTS=3
RPC_RETRY_BACKOFF_SEC=0.25
RPC_READINESS_TIMEOUT_SEC=5
REQUIRE_REDIS=true
ACTIVITY_LOG_MAX_ITEMS=300
MAX_TRANSFER_AMOUNT=1000
SUPPORTED_TOKENS=GEN
PYTHONUNBUFFERED=1
```

Add network-specific protocol contract addresses only when independently confirmed for that network. Do not copy an address from an old README or another network.

After saving Render variables, redeploy the existing service. Keep these settings:

```text
Root Directory: .
Build Command: pip install -r backend/requirements.txt
Start Command: python -m uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

## Vercel Variables

In the existing Vercel project, set the public variables for the `Production` environment, set the project root to `frontend`, and redeploy:

```text
NEXT_PUBLIC_API_URL=https://<existing-render-backend>
NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID=<WalletConnect project ID>
NEXT_PUBLIC_BRADBURY_CHAIN_ID=4221
NEXT_PUBLIC_BRADBURY_RPC=<approved Bradbury RPC URL>
NEXT_PUBLIC_STUDIONET_CHAIN_ID=61999
NEXT_PUBLIC_STUDIONET_RPC=<approved Studionet RPC URL>
```

Then add the final Vercel/custom domain to Render's `SIWE_ORIGINS`, Render's `ALLOWED_ORIGINS`, and WalletConnect Cloud's allowed domains.

## Local Files

Use `backend/.env` and `frontend/.env.local` only for local development. Local backend values should use `APP_ENV=development`, local origins, and normally `DATABASE_URL=sqlite:///./genlayer_bot.db`. Local frontend should use `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000`. Do not point local testing at the production database unless explicitly intended.

## Verification Order

1. Confirm the existing Render, Supabase, Redis, Vercel, and WalletConnect resources in their dashboards.
2. Update Render production variables and redeploy.
3. Update Vercel production variables and redeploy.
4. Check `https://<existing-render-backend>/health` returns HTTP `200`.
5. Check `https://<existing-render-backend>/ready` returns HTTP `200` and `status: ready`.
6. Confirm `database_migrations` is at `202608180002`.
7. Confirm `shared_log_store`, `studionet_rpc_connection`, and `bradbury_rpc_connection` pass.
8. Open the production frontend in Chrome, connect Rabby, and verify SIWE authentication.
9. Test network switching, balance lookup, chat history, contract review, wallet-scoped logs, and transaction preparation without broadcasting.
10. Only after all checks pass should the separate multi-validator consensus deployment begin.

If `/ready` returns `503`, stop and correct the provider or environment configuration. Do not bypass the readiness check. Infrastructure readiness does not prove validator readiness.

## Target Topology

- Frontend: Vercel, using the `frontend` directory.
- Backend: Render web service, using the repository root.
- Database: Supabase Postgres through the backend's SQLAlchemy connection.
- Shared activity logs: managed Redis over TLS, required for multiple backend instances.
- Wallet: browser wallet such as Rabby or MetaMask. The backend never holds a private key.
- Networks: Bradbury and Studionet, with independently verified RPC URLs and chain IDs.

## 1. Create External Services

Create these resources before configuring the application:

1. A Supabase production project and database password.
2. A managed Redis instance with TLS and authentication, such as Redis Cloud, Upstash, or Render Redis.
3. A Render web service for the backend.
4. A Vercel project for the frontend.
5. A WalletConnect Cloud project ID for the production frontend domain.
6. A production Groq API key if natural-language parsing is enabled.

Do not commit any secret, database password, Redis URL, API key, JWT secret, or wallet private key.

## 2. Provision Supabase Postgres

Use the Supabase Postgres connection string intended for server-side connections. It must use SSL:

```text
postgresql://postgres.<project-ref>:<url-encoded-password>@<supabase-host>:5432/postgres?sslmode=require
```

URL-encode the database password if it contains characters such as `@`, `:`, `/`, `?`, or `#`.

Before deploying the backend, confirm that the database accepts a connection from the Render service and that the database network policy allows that connection.

The backend startup runs Alembic migrations. The expected schema head is:

```text
202608180002
```

That head includes lifecycle persistence and the database-backed `siwe_nonces` table.

For a controlled migration run from the repository root, set `DATABASE_URL` in the shell and run:

```powershell
$env:DATABASE_URL = "postgresql://..."
python -c "from backend.database import run_migrations; run_migrations()"
```

Run this from the repository root, not from `backend`, because the nested `backend/types` package can shadow Python's standard-library `types` module when Python starts in that directory.

## 3. Provision Redis

Create a private or access-controlled Redis instance and obtain a TLS URL, normally beginning with `rediss://`.

Required production settings:

```text
REDIS_URL=rediss://:<password>@<redis-host>:<port>
REQUIRE_REDIS=true
ACTIVITY_LOG_MAX_ITEMS=300
```

The application uses hashed wallet scopes for Redis keys and channels. Do not expose Redis directly to the browser. Redis is for backend-to-backend activity-log storage and streaming only.

## 4. Configure Backend Environment

Set these variables on Render. Replace every placeholder with a real value:

```text
APP_ENV=production
GENLAYER_PHASE9_LIVE_PROOF=0

DATABASE_URL=postgresql://...
JWT_SECRET=<at-least-32-random-characters>
GROQ_API_KEY=<production-groq-key>

SIWE_ORIGINS=https://<frontend-domain>
SIWE_CHAIN_IDS=4221,61999
ALLOWED_ORIGINS=https://<frontend-domain>

GENLAYER_RPC_URL_BRADBURY=https://<approved-bradbury-rpc>
GENLAYER_RPC_URL_STUDIONET=https://<approved-studionet-rpc>
GENLAYER_CHAIN_ID_BRADBURY=4221
GENLAYER_CHAIN_ID_STUDIONET=61999

RPC_REQUEST_TIMEOUT_SEC=15
RPC_MAX_ATTEMPTS=3
RPC_RETRY_BACKOFF_SEC=0.25
RPC_READINESS_TIMEOUT_SEC=5

REDIS_URL=rediss://...
REQUIRE_REDIS=true
ACTIVITY_LOG_MAX_ITEMS=300

MAX_TRANSFER_AMOUNT=1000
SUPPORTED_TOKENS=GEN
```

Use only official or explicitly approved GenLayer RPC endpoints. The readiness check verifies that each endpoint returns the configured chain ID, but it does not prove validator availability.

Protocol contract address overrides should be set only when they have been confirmed for the specific network. Do not guess or copy an address from another network:

```text
GENLAYER_CONSENSUS_CONTRACT_ADDRESS_BRADBURY=<confirmed-address-or-omit>
GENLAYER_CONSENSUS_CONTRACT_ADDRESS_STUDIONET=<confirmed-address-or-omit>
GENLAYER_APPEALS_CONTRACT_ADDRESS_BRADBURY=<confirmed-address-or-omit>
GENLAYER_APPEALS_CONTRACT_ADDRESS_STUDIONET=<confirmed-address-or-omit>
GENLAYER_ROUNDS_STORAGE_CONTRACT_ADDRESS_BRADBURY=<confirmed-address-or-omit>
GENLAYER_ROUNDS_STORAGE_CONTRACT_ADDRESS_STUDIONET=<confirmed-address-or-omit>
GENLAYER_FEE_MANAGER_CONTRACT_ADDRESS_BRADBURY=<confirmed-address-or-omit>
GENLAYER_FEE_MANAGER_CONTRACT_ADDRESS_STUDIONET=<confirmed-address-or-omit>
```

Do not set `GENLAYER_PHASE9_LIVE_PROOF=1` during ordinary production setup. That flag is reserved for a supervised proof run.

Generate a JWT secret locally without exposing it in chat or source control:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## 5. Deploy Backend to Render

Use a Render web service with:

```text
Root Directory: .
Build Command: pip install -r backend/requirements.txt
Start Command: python -m uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

Use Python 3.12 to match the CI runtime. Configure the Render health check as:

```text
/health
```

`/health` is liveness only. Treat `/ready` as the deployment readiness gate and monitor it separately.

After deployment, record the backend URL:

```text
https://<render-backend>.onrender.com
```

## 6. Deploy Frontend to Vercel

Create a Vercel project with:

```text
Root Directory: frontend
Build Command: npm run build
Install Command: npm ci
```

Set these Vercel environment variables for the Production environment:

```text
NEXT_PUBLIC_API_URL=https://<render-backend>.onrender.com
NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID=<walletconnect-project-id>

NEXT_PUBLIC_BRADBURY_CHAIN_ID=4221
NEXT_PUBLIC_BRADBURY_RPC=https://<approved-bradbury-rpc>
NEXT_PUBLIC_STUDIONET_CHAIN_ID=61999
NEXT_PUBLIC_STUDIONET_RPC=https://<approved-studionet-rpc>
```

All `NEXT_PUBLIC_*` values are visible in the browser. Never put a private secret in a frontend environment variable.

Add the final Vercel domain to both `SIWE_ORIGINS` and `ALLOWED_ORIGINS` on Render. Add the same domain to the WalletConnect Cloud allowed-domain configuration.

## 7. Infrastructure Verification

Run these checks against the deployed backend before using a real deployment:

```powershell
Invoke-WebRequest https://<render-backend>.onrender.com/health
Invoke-WebRequest https://<render-backend>.onrender.com/ready
```

Expected results:

- `/health` returns HTTP `200` with `status: healthy`.
- `/ready` returns HTTP `200` with `status: ready`.
- `database_connection` passes.
- `database_migrations` passes at `202608180002`.
- `studionet_rpc_connection` passes with chain ID `61999`.
- `bradbury_rpc_connection` passes with chain ID `4221`.
- `shared_log_store` passes with Redis configured.
- No required check reports `fail`.

If `/ready` fails, stop and correct the infrastructure. Do not bypass it by changing the readiness code.

## 8. Controlled Application Verification

Use Chrome with Rabby or the intended wallet extension:

1. Open the production frontend.
2. Connect a test wallet.
3. Confirm SIWE authentication succeeds.
4. Switch between Bradbury and Studionet and confirm the wallet chain changes correctly.
5. Run a read-only balance lookup on each network.
6. Confirm chat history persists after refresh.
7. Upload a `.py` contract and verify validation and automated review.
8. Open activity logs and verify only the connected wallet's events appear.
9. Prepare a transfer or contract transaction, but do not broadcast it yet.
10. Confirm the backend returns a fresh prepared transaction ID, intent hash, expiry, chain ID, destination, calldata, and fee fields.

Use a second test wallet to verify that the first wallet cannot see the first wallet's activity events or use its prepared transaction.

## 9. Pre-Consensus Gate

Do not begin the real GenLayer deployment until all of these are true:

- Production `/ready` returns HTTP `200`.
- The database is at Alembic head `202608180002`.
- Redis is connected and required.
- Both RPC endpoints pass connectivity and chain identity checks.
- The frontend points to the production backend, not localhost.
- SIWE authentication works from the final HTTPS domain.
- Wallet network switching works in Chrome/Rabby.
- Contract source review and source-hash verification work.
- Transaction preparation works without backend custody of funds.
- Consensus lifecycle diagnostics are visible and distinguish EVM receipt from GenLayer finality.
- The validator/network target for the proof run is known and approved.

Infrastructure readiness is not validator readiness. The actual consensus phase begins only after this gate passes and a fresh canonical artifact is prepared.
