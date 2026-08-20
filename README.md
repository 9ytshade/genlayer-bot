# GenLayer Bot

GenLayer Bot Preview is a wallet-controlled chat interface for understanding GenLayer contracts, reviewing contract source, checking balances, and preparing safe GEN transactions. It is a testnet/demo product, not a production custody product or a guarantee that an Intelligent Contract deployment will finalize.

The core rule of the app is simple: the bot never executes raw LLM output directly. User requests are parsed into structured intents, validated, simulated where possible, shown back to the user, and only executed after explicit confirmation from the connected wallet. The app is user-wallet-only: the backend prepares GenLayer transaction data, and the connected wallet signs.

## What You Can Use Today

- Wallet connection with RainbowKit, wagmi, viem, SIWE, and backend JWT sessions
- Network support for GenLayer Studionet and Bradbury
- Automatic wallet network switching from the app network selector
- Wallet-scoped chat history stored per connected wallet
- Desktop chat sidebar with New chat and previous chat sessions
- Natural-language balance checks
- Wallet-side token transfers using `sendTransaction`
- Immediate balance refresh after successful transactions
- Python contract upload/paste and automated GenLayer-aware preflight
- Safeguards for non-`.py` uploads
- Python syntax and structure validation before deployment
- In-chat deploy parameter editor for constructor args, kwargs, value, gas limit, rotations, and leader-only mode
- Safe deployment and contract-call preparation with immutable reviewed transaction intents
- Transaction diagnostics and lifecycle display that distinguishes broadcast, EVM acceptance, consensus, and GenVM execution
- Read-only inspection of legacy workflow records where available
- Live activity log panel with in-memory logs locally and optional Redis-backed logs in production
- Render-ready backend deployment with Supabase Postgres
- Vercel-ready frontend deployment

## Temporarily Unavailable

GenLayer validator consensus on the recorded Studionet canary had zero participating validators and finalized with `NO_MAJORITY`. To avoid presenting a simulated or unsafe flow as real, the following remain unavailable for public use:

- Intelligent Contract deployment/finalization
- Conditional payment deployment, evidence evaluation, and settlement
- Bounty deployment, validator review, winner selection, and payout
- Screenshot-verification contracts
- AI Notary live deployment and claim evaluation
- Appeal preparation and submission

These limitations do not affect wallet connection, authentication, balance checks, native GEN transfers, contract preflight, source review, or transaction preparation. See [shipping blockers](docs/SHIPPING-BLOCKERS.md) and [known limitations](docs/KNOWN-LIMITATIONS.md).

## Project Structure

```text
genlayer-bot/
|-- backend/
|   |-- alembic/
|   |-- routers/
|   |   |-- chat.py
|   |   |-- logs.py
|   |   |-- users.py
|   |   `-- wallet.py
|   |-- tests/
|   |-- .env.example
|   |-- Dockerfile
|   |-- Procfile
|   |-- alembic.ini
|   |-- auth.py
|   |-- contract_artifacts.py
|   |-- contract_validation.py
|   |-- transaction_intent.py
|   |-- services/
|   |-- validators/
|   |-- database.py
|   |-- genlayer_client.py
|   |-- intent_parser.py
|   |-- logs_store.py
|   |-- main.py
|   |-- models.py
|   |-- network_config.py
|   |-- pyproject.toml
|   |-- rate_limit.py
|   |-- requirements.txt
|   |-- safety.py
|   |-- schemas.py
|   `-- simulator.py
|-- frontend/
|   |-- public/
|   |-- src/
|   |   |-- app/
|   |   |-- components/
|   |   |-- context/
|   |   |-- lib/
|   |   |-- config.ts
|   |   `-- global.d.ts
|   |-- .env.example
|   |-- next.config.ts
|   |-- package.json
|   |-- tsconfig.json
|   `-- vercel.json
|-- .gitignore
`-- README.md
```

Local planning and handoff files such as `fix.md`, `handover_prompt.md`, `Fix Prompt.txt`, `Full Project Ananlysis.txt`, and `Build` are ignored and should not be pushed.

## Architecture

```text
User chat input
  -> frontend chat UI
  -> FastAPI backend on Render
  -> Supabase Postgres for persistent backend data
  -> Groq structured intent parsing
  -> safety validation
  -> simulation or deploy preparation
  -> user confirmation
  -> authenticated backend builder persists a single-use reviewed intent envelope
  -> wallet-side transaction broadcast
  -> backend verifies wallet, chain, destination, calldata, value, nonce, gas, and fees against the envelope
  -> backend EVM receipt confirmation and consensus tx-id extraction
  -> frontend GenLayer consensus polling with backoff
  -> finalized GenVM execution verification
  -> successful deployment details and result formatting
  -> chat result and activity logs
```

The frontend owns wallet interaction. SIWE binds the session to the connected wallet. Every transfer, deployment, workflow deployment, and contract call is prepared for that authenticated wallet and stored as a short-lived, single-use intent envelope before the wallet broadcasts it. Confirmation accepts only the resulting transaction hash, reads the transaction from the selected RPC, and rejects any wallet, chain, destination, calldata, value, nonce, gas, or fee mismatch. Raw signed transactions are not relayed by the backend.

After exact EVM transaction verification, the chat polls canonical GenLayer consensus status independently so an EVM receipt is never presented as consensus finality. Finalized consensus is also kept separate from GenVM execution: only `FINISHED_WITH_RETURN` is shown as successful, `FINISHED_WITH_ERROR` is shown as failed, and unavailable execution results remain in a finalized-but-verifying state.

Generated and workflow contract source is owned by the backend. Every reviewed artifact includes an exact SHA-256 source hash plus the pinned `py-genlayer` dependency, SDK, generator, validator, and compiler versions. The deployment builder rejects stale or modified reviews and encodes the exact source bytes whose hash was displayed; the frontend no longer contains duplicate Python workflow templates.

## GenLayer Readiness

All future feature work follows the repository's GenLayer readiness and research rules. Read the [GenLayer Readiness and Feature Research Charter](docs/genlayer-readiness-charter.md) before proposing an Intelligent Contract feature, and use the [GenLayer Hardening Backlog](docs/genlayer-hardening-backlog.md) for the current implementation order.

The charter requires Ideas-page provenance, explicit equivalence criteria, consensus and appeal behavior, correct GEN value movement, authenticated transaction intent, GenVM/Studio proof, and truthful finality reporting. Escrow and subscription are currently deterministic workflows, not GenLayer judgment claims. Conditional-payment and bounty generation, deployment, and actions are disabled until their dedicated rebuild phases are complete. Screenshot verification and appeal submission are also disabled until their complete protocol paths are proven. See [architecture](docs/ARCHITECTURE.md), [trust model](docs/GENLAYER-TRUST-MODEL.md), and [known limitations](docs/KNOWN-LIMITATIONS.md) for the current boundary.

## Backend

The backend is a FastAPI app in `backend/`.

Important files:

- `main.py`: FastAPI setup, CORS, health check, router registration, startup migrations
- `auth.py`: SIWE nonce and signature verification, JWT issuing, authenticated user lookup
- `routers/chat.py`: chat, confirmation, deploy transaction, validation, and tx parameter endpoints
- `routers/wallet.py`: connected wallet balance endpoint
- `genlayer_client.py`: async JSON-RPC wrapper plus GenLayer deployment and contract-call transaction builders
- `contract_validation.py`: Python contract validation
- `database.py`, `models.py`, `alembic/`: SQLAlchemy models and migrations
- `logs_store.py`: in-memory logs locally and Redis-backed logs when `REDIS_URL` is set

### Backend Setup

Run the backend from the project root so `backend.main:app` resolves correctly:

```bash
cd "C:\Users\9ytshade\Documents\Genlayer Bot"
python -m venv backend/.venv
backend\.venv\Scripts\activate
pip install -r backend/requirements.txt
copy backend\.env.example backend\.env
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Use the equivalent activation command for macOS or Linux if needed.

### Backend Environment Variables

```bash
DATABASE_URL=sqlite:///./genlayer_bot.db
APP_ENV=production
JWT_SECRET=your_random_secret_with_at_least_32_characters
SIWE_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
SIWE_CHAIN_IDS=
GROQ_API_KEY=your_groq_api_key_here

GENLAYER_RPC_URL_STUDIONET=https://studio.genlayer.com/api
GENLAYER_RPC_URL_BRADBURY=https://rpc-bradbury.genlayer.com
GENLAYER_CHAIN_ID_STUDIONET=61999
GENLAYER_CHAIN_ID_BRADBURY=4221
GENLAYER_CONSENSUS_CONTRACT_ADDRESS=0xb7278A61aa25c888815aFC32Ad3cC52fF24fE575

MAX_TRANSFER_AMOUNT=1000
SUPPORTED_TOKENS=GEN
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
REDIS_URL=
```

Generate `JWT_SECRET`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

## Frontend

The frontend is a Next.js app in `frontend/`.

Important files:

- `src/components/ChatInterface.tsx`: chat orchestration, wallet-scoped chat history, sidebar, upload flow, confirmations
- `src/components/ConnectWalletButton.tsx`: wallet dropdown and balance display
- `src/context/WalletContext.tsx`: wallet connection, SIWE authentication, transaction sending, network switching, balance refresh signal
- `src/components/DeployContractPanel.tsx`: deployment parameter editor
- `src/lib/api.ts`: API client functions
- `src/config.ts`: frontend API and chain configuration

### Frontend Setup

```bash
cd frontend
npm install
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Default local URLs:

- Frontend: `http://127.0.0.1:3000`
- Backend: `http://127.0.0.1:8000`
- API docs: `http://127.0.0.1:8000/docs`

### Frontend Environment Variables

```bash
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID=your_walletconnect_project_id
NEXT_PUBLIC_STUDIONET_CHAIN_ID=61999
NEXT_PUBLIC_STUDIONET_RPC=https://studio.genlayer.com/api
NEXT_PUBLIC_BRADBURY_CHAIN_ID=4221
NEXT_PUBLIC_BRADBURY_RPC=https://rpc-bradbury.genlayer.com
```

## Main User Flows

### Check Balance

1. User connects a wallet.
2. User signs the SIWE message once for backend JWT auth.
3. User selects Studionet or Bradbury.
4. User asks for balance in chat or opens the wallet dropdown.
5. Backend reads native balance from the selected RPC.
6. UI shows the result and keeps the wallet badge current.

### Send Tokens

1. User asks to send tokens to an address.
2. Bot parses and validates the transfer intent.
3. User reviews simulation, risk, and gas estimate.
4. Authenticated backend preparation stores the exact reviewed transfer envelope and intent hash.
5. User confirms and the frontend broadcasts through the connected wallet.
6. Backend reads the submitted transaction and rejects any envelope mismatch.
7. Backend confirms the receipt.
8. Chat shows success or error, and the wallet balance refreshes.

### Review or Prepare an Intelligent Contract

1. User uploads a `.py` contract file.
2. Frontend and backend reject non-`.py` files.
3. Backend validates Python syntax and basic contract structure.
4. Chat shows deployment parameters for review.
5. The backend can prepare a reviewed deployment intent, binding the exact source and transaction fields.
6. Deployment broadcasting is currently unavailable for public use because a healthy validator consensus environment has not yet been proven.
7. Once validator health is restored, the frontend will send the reviewed intent through the connected wallet and the backend will verify the submitted transaction exactly.

### Workflow Contracts

1. Workflow records may be inspected, but public workflow deployment and write actions are currently unavailable.
2. The UI and backend validate the supported workflow configuration.
3. The backend retains trusted templates, exact integer-wei handling, source hashes, and intent integrity checks for the later re-enable.
4. Existing conditional-payment and bounty records remain readable, but their new generation, deployment, settlement, review, winner-selection, and closure paths fail closed until validator health and full lifecycle proof are available.

Activity-log HTTP and WebSocket access also requires the authenticated SIWE session. Activity events are wallet-scoped, redacted, bounded, and retained through the configured in-memory or Redis-backed store.

### Chat History

Chat history is stored client-side in `localStorage`, scoped by connected wallet address. Refreshing the app restores the current wallet's chats. Connecting a different wallet loads that wallet's own chat list, so users do not see another wallet's conversations in the same browser.

## Deployment

Production deployment uses:

- Backend: Render web service
- Database: Supabase Postgres
- Frontend: Vercel or any static/Next.js host

### Supabase Postgres

1. Create a Supabase project.
2. Open `Project Settings -> Database -> Connection string`.
3. Copy the Postgres connection string.
4. Replace the password placeholder with your database password.
5. URL-encode special characters in the password.
6. Add `?sslmode=require` if it is not already present.

Example:

```bash
DATABASE_URL=postgresql://postgres.project_ref:encoded_password@host:5432/postgres?sslmode=require
```

### Backend on Render

Render settings:

```text
Root Directory: .
Build Command: pip install -r backend/requirements.txt
Start Command: python -m uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

Render environment variables:

```bash
DATABASE_URL=your_supabase_postgres_url
JWT_SECRET=your_jwt_secret
GROQ_API_KEY=your_groq_key
GENLAYER_RPC_URL_STUDIONET=https://studio.genlayer.com/api
GENLAYER_RPC_URL_BRADBURY=https://rpc-bradbury.genlayer.com
GENLAYER_CHAIN_ID_STUDIONET=61999
GENLAYER_CHAIN_ID_BRADBURY=4221
GENLAYER_CONSENSUS_CONTRACT_ADDRESS=0xb7278A61aa25c888815aFC32Ad3cC52fF24fE575
MAX_TRANSFER_AMOUNT=1000
SUPPORTED_TOKENS=GEN
ALLOWED_ORIGINS=https://your-frontend-domain.com,http://localhost:3000,http://127.0.0.1:3000
REDIS_URL=
PYTHONUNBUFFERED=1
```

After deployment, verify:

```text
https://your-render-backend.onrender.com/health
```

Expected response:

```json
{"status":"healthy"}
```

### Frontend on Vercel

Set the frontend root directory to `frontend`.

Frontend environment variables:

```bash
NEXT_PUBLIC_API_URL=https://your-render-backend.onrender.com
NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID=your_walletconnect_project_id
NEXT_PUBLIC_STUDIONET_CHAIN_ID=61999
NEXT_PUBLIC_STUDIONET_RPC=https://studio.genlayer.com/api
NEXT_PUBLIC_BRADBURY_CHAIN_ID=4221
NEXT_PUBLIC_BRADBURY_RPC=https://rpc-bradbury.genlayer.com
```

Also add the frontend domain to:

- Render `ALLOWED_ORIGINS`
- WalletConnect Cloud allowed domains

## Verification Commands

Backend:

```bash
python -m py_compile backend/main.py backend/genlayer_client.py backend/contract_validation.py backend/safety.py backend/simulator.py backend/routers/chat.py backend/routers/wallet.py
python -m pytest backend/tests -q
```

Frontend:

```bash
cd frontend
npm run lint
npm run test:lifecycle
npm run test:notary
npm run build
```

## Security Notes

- Never commit `.env` files, private keys, JWT secrets, or wallet secrets.
- The backend must only prepare GenLayer transaction data; the connected wallet signs user transactions.
- Backend auth uses SIWE nonces and JWTs; do not replace it with raw wallet-address bearer tokens.
- Contract uploads receive an automated GenLayer-aware preflight. It is advisory, not a formal security audit; deployment is still restricted to a reviewed immutable source artifact.
- Use Supabase RLS policies if you expose any tables through Supabase APIs.

## Release Status

**Public preview — safe to test:** wallet connection, SIWE authentication, balance checks, native GEN transfers, natural-language intent parsing, automated contract preflight, source review, transaction previews, and integrity diagnostics.

**Not ready to ship:** Intelligent Contract deployment, validator-dependent workflows, evidence-based decisions, payouts/refunds from Intelligent Contracts, screenshots, AI Notary evaluation, and appeals. The recorded Studionet canary had no participating validators, so this repository does not claim a successful live consensus lifecycle proof.

Current blockers and re-enable gates are documented in [Shipping Blockers](docs/SHIPPING-BLOCKERS.md) and [Known Limitations](docs/KNOWN-LIMITATIONS.md).

## License

MIT
