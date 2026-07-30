# GenLayer Bot

GenLayer Bot is a full-stack chat interface for interacting with GenLayer networks through natural language. A connected wallet can check balances, send tokens, upload Python intelligent contracts, review deployment parameters, and submit Studionet deployment transactions from a guided chat UI.

The core rule of the app is simple: the bot never executes raw LLM output directly. User requests are parsed into structured intents, validated, simulated where possible, shown back to the user, and only executed after explicit confirmation from the connected wallet. The app is user-wallet-only: the backend prepares GenLayer transaction data, and the connected wallet signs.

## Current Features

- Wallet connection with RainbowKit, wagmi, viem, SIWE, and backend JWT sessions
- Network support for GenLayer Studionet and Bradbury
- Automatic wallet network switching from the app network selector
- Wallet-scoped chat history stored per connected wallet
- Desktop chat sidebar with New chat and previous chat sessions
- Natural-language balance checks
- Wallet-side token transfers using `sendTransaction`
- Immediate balance refresh after successful transactions
- Python contract upload flow for GenLayer intelligent contracts
- Safeguards for non-`.py` uploads
- Python syntax and structure validation before deployment
- In-chat deploy parameter editor for constructor args, kwargs, value, gas limit, rotations, and leader-only mode
- Studionet deployment transaction builder using the GenLayer consensus contract
- Deployment result display with EVM tx hash, consensus tx id, contract address, and generated addresses
- Trusted workflow templates for conditional payments, escrow, subscriptions, and bounties
- GenLayer contract-call transaction builder for deployed workflow actions
- Live activity log panel with in-memory logs locally and optional Redis-backed logs in production
- Render-ready backend deployment with Supabase Postgres
- Vercel-ready frontend deployment

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
|   |-- contract_generator.py
|   |-- contract_validation.py
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
  -> wallet-side transaction broadcast
  -> backend receipt polling and result formatting
  -> chat result and activity logs
```

The frontend owns wallet interaction. The backend prepares safe transaction data, validates contract uploads, checks balances through configured RPC endpoints, and confirms transaction receipts after the wallet broadcasts them.

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
JWT_SECRET=your_long_random_secret
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
4. User confirms.
5. Frontend sends the transaction through the connected wallet.
6. Backend confirms the receipt.
7. Chat shows success or error, and the wallet balance refreshes.

### Deploy Intelligent Contract

1. User uploads a `.py` contract file.
2. Frontend and backend reject non-`.py` files.
3. Backend validates Python syntax and basic contract structure.
4. Chat shows deployment parameters for review.
5. Backend builds the Studionet consensus-contract transaction.
6. Frontend sends it through the connected wallet.
7. Backend polls the receipt, extracts consensus and deployment details, and returns them to chat.

### Workflow Contracts

1. User describes a conditional payment, escrow, subscription, or bounty.
2. The UI and backend validate the workflow configuration.
3. Backend selects the trusted workflow template and builds the GenLayer deployment transaction.
4. User signs deployment from their connected wallet.
5. Dashboard actions build GenLayer contract-call transactions through the backend and are signed by the connected wallet.
6. Backend confirms receipts and stores workflow deployment/action metadata for the authenticated wallet.

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
npm run build
```

## Security Notes

- Never commit `.env` files, private keys, JWT secrets, or wallet secrets.
- The backend must only prepare GenLayer transaction data; the connected wallet signs user transactions.
- Backend auth uses SIWE nonces and JWTs; do not replace it with raw wallet-address bearer tokens.
- Contract uploads are validated for file type and Python structure, but deeper semantic auditing is still future hardening.
- Use Supabase RLS policies if you expose any tables through Supabase APIs.

## Current Status

Completed:

- Balance checking
- Token transfers
- Wallet-side transaction broadcasting
- SIWE authentication and backend JWT sessions
- Supabase Postgres database target
- Render backend deployment support
- Studionet deploy transaction builder
- GenLayer workflow contract-call transaction builder
- Python contract upload and validation
- Deploy parameter UI
- Deployment result display
- Wallet-scoped chat history
- Desktop chat sidebar
- Automatic wallet network switching
- Trusted workflow templates and persisted workflow deployment metadata
- Vercel frontend deployment support

Planned hardening:

- Database-backed transaction history
- Production Redis for logs and live activity events
- Better semantic validation for intelligent contracts
- Production-grade observability and alerting

## License

MIT
