# GenLayer Bot

GenLayer Bot is a full-stack chat interface for interacting with GenLayer networks through natural language. A connected wallet can check balances, send tokens, upload Python intelligent contracts, review deployment parameters, and submit Studionet deployment transactions from a guided chat UI.

The core rule of the app is simple: the bot never executes raw LLM output directly. User requests are parsed into structured intents, validated, simulated where possible, shown back to the user, and only executed after explicit confirmation.

## Current Features

- Wallet connection with RainbowKit, wagmi, and viem
- Network support for GenLayer Studionet and Bradbury
- Automatic wallet network switching from the app network selector
- Wallet-scoped chat history stored per connected wallet
- Desktop chat sidebar with New chat and previous chat sessions
- Natural-language balance checks
- Wallet-side token transfers using sendTransaction
- Immediate balance refresh after successful transactions
- Python contract upload flow for GenLayer intelligent contracts
- Safeguards for non-.py uploads
- Python syntax and structure validation before deployment
- In-chat deploy parameter editor for constructor args, kwargs, value, gas limit, rotations, and leader-only mode
- Studionet deployment transaction builder using the GenLayer consensus contract
- Deployment result display with EVM tx hash, consensus tx id, contract address, and generated addresses
- Live activity log panel
- Command palette, quick actions, risk indicators, simulations, and retryable errors
- Railway-ready backend and Vercel-ready frontend configuration

## Project Structure

```text
genlayer-bot/
|-- backend/
|   |-- routers/
|   |   |-- chat.py
|   |   |-- logs.py
|   |   |-- users.py
|   |   `-- wallet.py
|   |-- .env.example
|   |-- Dockerfile
|   |-- Procfile
|   |-- railway.json
|   |-- contract_generator.py
|   |-- contract_validation.py
|   |-- database.py
|   |-- genlayer_client.py
|   |-- intent_parser.py
|   |-- logs_store.py
|   |-- main.py
|   |-- models.py
|   |-- network_config.py
|   |-- requirements.txt
|   |-- safety.py
|   |-- schemas.py
|   `-- simulator.py
|-- frontend/
|   |-- public/
|   |-- src/
|   |   |-- app/
|   |   |   |-- layout.tsx
|   |   |   `-- page.tsx
|   |   |-- components/
|   |   |   |-- ChatInterface.tsx
|   |   |   |-- CommandPalette.tsx
|   |   |   |-- ConfirmationButtons.tsx
|   |   |   |-- ConnectWalletButton.tsx
|   |   |   |-- DeployContractPanel.tsx
|   |   |   |-- IntentCard.tsx
|   |   |   |-- LiveLogsPanel.tsx
|   |   |   |-- Message.tsx
|   |   |   |-- QuickActions.tsx
|   |   |   |-- RiskIndicator.tsx
|   |   |   |-- SimulationCard.tsx
|   |   |   |-- WalletConnect.tsx
|   |   |   `-- Web3Provider.tsx
|   |   |-- context/
|   |   |   `-- WalletContext.tsx
|   |   |-- lib/
|   |   |   `-- api.ts
|   |   |-- config.ts
|   |   `-- global.d.ts
|   |-- .env.example
|   |-- Procfile
|   |-- next.config.ts
|   |-- package.json
|   |-- tsconfig.json
|   `-- vercel.json
|-- .gitignore
`-- README.md
```

Local planning and handoff files such as fix.md, handover_prompt.md, and Build are ignored and should not be pushed.

## Architecture

```text
User chat input
  -> frontend chat UI
  -> FastAPI /chat intent endpoint
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

The backend is a FastAPI app in backend/.

Important files:

- main.py: FastAPI setup, CORS, health check, router registration
- routers/chat.py: chat, confirmation, deploy transaction, validation, and tx parameter endpoints
- routers/wallet.py: wallet balance and funding endpoints
- genlayer_client.py: async JSON-RPC wrapper and GenLayer deployment transaction builder
- contract_validation.py: Python contract validation
- network_config.py: Studionet and Bradbury network selection
- models.py and database.py: SQLAlchemy models and database setup
- logs_store.py: in-memory live activity logs

### Backend Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Use the equivalent activation command for macOS or Linux if you are not on Windows.

### Backend Environment Variables

```bash
GROQ_API_KEY=your_groq_api_key_here

GENLAYER_RPC_URL_STUDIONET=https://studio.genlayer.com/api
GENLAYER_RPC_URL_BRADBURY=https://rpc-bradbury.genlayer.com

WALLET_PRIVATE_KEY=your_wallet_private_key_here
WALLET_ADDRESS=your_wallet_address_here
MAX_TRANSFER_AMOUNT=1000

DATABASE_URL=sqlite:///./genlayer_bot.db
ENCRYPTION_KEY=your_permanent_fernet_key

ALLOWED_ORIGINS=http://localhost:3000
```

Generate ENCRYPTION_KEY once and keep it permanently:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Do not rotate this key after encrypted data has been stored.

## Frontend

The frontend is a Next.js app in frontend/.

Important files:

- src/app/page.tsx: app shell and activity panel layout
- src/components/ChatInterface.tsx: chat orchestration, wallet-scoped chat history, sidebar, upload flow, confirmations
- src/components/ConnectWalletButton.tsx: wallet dropdown and balance display
- src/context/WalletContext.tsx: wallet connection, transaction sending, network switching, balance refresh signal
- src/components/DeployContractPanel.tsx: deployment parameter editor
- src/lib/api.ts: API client functions
- src/config.ts: frontend API and chain configuration

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Default local URLs:

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- API docs: http://localhost:8000/docs

### Frontend Environment Variables

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID=your_walletconnect_project_id
NEXT_PUBLIC_GENLAYER_RPC_URL_STUDIONET=https://studio.genlayer.com/api
NEXT_PUBLIC_GENLAYER_CHAIN_ID_STUDIONET=61999
NEXT_PUBLIC_GENLAYER_RPC_URL_BRADBURY=https://rpc-bradbury.genlayer.com
NEXT_PUBLIC_GENLAYER_CHAIN_ID_BRADBURY=4221
```

## Main User Flows

### Check Balance

1. User connects a wallet.
2. User selects Studionet or Bradbury.
3. User asks for balance in chat or opens the wallet dropdown.
4. Backend reads native balance from the selected RPC.
5. UI shows the result and keeps the wallet badge current.

### Send Tokens

1. User asks to send tokens to an address.
2. Bot parses and validates the transfer intent.
3. User reviews simulation, risk, and gas estimate.
4. User confirms.
5. Frontend sends the transaction through the connected wallet.
6. Backend confirms the receipt.
7. Chat shows success or error, and the wallet balance refreshes.

### Deploy Intelligent Contract

1. User uploads a .py contract file.
2. Frontend rejects non-.py files immediately.
3. Backend validates Python syntax and basic contract structure.
4. Chat shows deployment parameters for review.
5. Backend builds the Studionet consensus-contract transaction.
6. Frontend sends it through the connected wallet.
7. Backend polls the receipt, extracts consensus and deployment details, and returns them to chat.

### Chat History

Chat history is stored client-side in localStorage, scoped by connected wallet address. Refreshing the app restores the current wallet's chats. Connecting a different wallet loads that wallet's own chat list, so users do not see another wallet's conversations in the same browser.

## Deployment

### Backend on Railway

The backend contains:

- backend/Procfile
- backend/Dockerfile
- backend/railway.json
- /health endpoint for health checks

Railway variables should include:

```bash
GROQ_API_KEY=...
GENLAYER_RPC_URL_STUDIONET=https://studio.genlayer.com/api
GENLAYER_RPC_URL_BRADBURY=https://rpc-bradbury.genlayer.com
WALLET_PRIVATE_KEY=...
WALLET_ADDRESS=...
MAX_TRANSFER_AMOUNT=1000
DATABASE_URL=sqlite:///./genlayer_bot.db
ENCRYPTION_KEY=...
ALLOWED_ORIGINS=https://your-vercel-domain.vercel.app
```

The Dockerfile binds to Railway's dynamic PORT.

### Frontend on Vercel

Set the frontend root directory to frontend.

Vercel variables should include:

```bash
NEXT_PUBLIC_API_URL=https://your-railway-backend-url
NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID=...
NEXT_PUBLIC_GENLAYER_RPC_URL_STUDIONET=https://studio.genlayer.com/api
NEXT_PUBLIC_GENLAYER_CHAIN_ID_STUDIONET=61999
NEXT_PUBLIC_GENLAYER_RPC_URL_BRADBURY=https://rpc-bradbury.genlayer.com
NEXT_PUBLIC_GENLAYER_CHAIN_ID_BRADBURY=4221
```

Also add the Vercel domain to WalletConnect Cloud allowed domains.

## Verification Commands

Backend:

```bash
cd backend
python -m py_compile main.py genlayer_client.py contract_validation.py safety.py simulator.py routers/chat.py routers/wallet.py
```

Frontend:

```bash
cd frontend
npm run lint
npx tsc --noEmit
npm run build
```

## Security Notes

- Never commit .env files, private keys, generated encryption keys, or wallet secrets.
- WALLET_PRIVATE_KEY is server-side only and should never be exposed to the frontend.
- ENCRYPTION_KEY must be stable and permanent.
- The current auth model trusts connected wallet addresses from the client. Before handling real funds or public production usage, add signed-message authentication with server-issued nonces.
- Contract uploads are validated for file type and Python structure, but deeper semantic auditing is still a future hardening step.

## Current Status

Completed:

- Balance checking
- Token transfers
- Wallet-side transaction broadcasting
- Studionet deploy transaction builder
- Python contract upload and validation
- Deploy parameter UI
- Deployment result display
- Wallet-scoped chat history
- Desktop chat sidebar
- Automatic wallet network switching
- Railway backend deployment support
- Vercel frontend deployment support

Planned hardening:

- Signed-message authentication
- Persistent server-side chat history
- Database-backed transaction history
- Better semantic validation for intelligent contracts
- Production-grade observability and alerting

## License

MIT
