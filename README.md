# GenLayer AI Chatbot 🤖⛓️

A sophisticated AI-powered chatbot that bridges natural language to blockchain execution on GenLayer. Execute transactions, generate intelligent contracts, and interact with the blockchain through intuitive conversation.

**Never execute raw LLM output on-chain.** Every transaction passes through structured intent parsing, validation, simulation, and user confirmation.

---

## 🎯 Overview

GenLayer Bot is a full-stack application that transforms how users interact with blockchain. Instead of writing code or managing complex wallet interactions, users can simply talk to the AI agent:

```
User: "Send 10 GEN to alice"
↓
AI parses intent → validates safety → simulates outcome → asks for confirmation
↓
User approves → transaction executes on GenLayer
```

**Core Principle:** NEVER trust raw LLM output. All actions must be validated, simulated, and explicitly confirmed by the user.

---

## ✨ Key Features

### 1. **Natural Language Intent Parsing**
- Uses GROQ LLM with function calling for structured intent extraction
- Converts user input into validated JSON schemas
- Supports multiple action types: transfers, balance checks, contract creation

### 2. **Smart Risk Assessment** 🎯
- Real-time transaction risk classification:
  - 🟢 **Safe**: Balance checks, small transfers (<100 GEN)
  - 🟡 **Medium**: Transfers 100-1,000 GEN
  - 🔴 **High**: Large transfers (>1,000 GEN)
- Visual risk indicators with action icons
- Gas fee estimation before execution

### 3. **Contract Simulation Engine** 🔄
- Simulates contract logic before deployment
- Shows multiple outcome scenarios
- Prevents costly errors through safe testing

### 4. **Multi-Layer Safety** 🔐
- **Intent Validation**: Schema validation + semantic checks
- **Logic Validation**: Verify conditions, recipients, amounts
- **Economic Constraints**: Rate limiting + spend caps
- **User Confirmation**: Explicit approval required

### 5. **Modern Terminal UI** 💻
- Dark theme with accent colors (inspired by trading terminals)
- Command palette (Cmd+K) for quick actions
- Quick action buttons for common operations
- Timestamp tracking for all transactions
- Copy-to-clipboard for transaction hashes
- Error handling with retry buttons

### 6. **Responsive Design** 📱
- Desktop optimized 3-column layout
- Mobile-friendly collapsible panels
- Touch-friendly command palette modal
- Adaptive quick actions grid

### 7. **GenLayer Integration** 🧪
- Full GenLayer SDK integration for testnet
- Transaction execution via GenLayer nodes
- Real wallet address support
- Actual on-chain transaction hashing

---

## 🏗️ Architecture

### System Design

```
┌─────────────────────────────────────────────────────────┐
│                    USER INTERFACE                        │
│         Next.js Chat + Terminal Aesthetic                │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│              INTENT PARSING LAYER                        │
│  GROQ LLM + Function Calling → Structured JSON           │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│           SAFETY & VALIDATION LAYER                      │
│  • Schema validation  • Logic checks  • Amount limits    │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│          SIMULATION ENGINE                               │
│  Test contract logic with sample inputs → Outcomes       │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│       USER CONFIRMATION & EXPLAINABILITY                │
│  Show: Intent | Simulation | Risk | Gas Estimate        │
│  Require: Explicit "Execute" approval                   │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│         GENLAYER INTEGRATION & EXECUTION                 │
│  Deploy via GenLayer SDK → Track Status → Notify User   │
└─────────────────────────────────────────────────────────┘
```

### Component Structure

```
Frontend/
├── ChatInterface (main chat orchestrator)
├── Message (message display with timestamps)
├── IntentCard (parsed intent visualization with icons)
├── SimulationCard (simulation results & outcomes)
├── ConfirmationButtons (confirmation UI with gas estimates)
├── RiskIndicator (transaction risk assessment)
├── QuickActions (quick action buttons)
├── CommandPalette (searchable command modal)
└── ConnectWalletButton (wallet connection)

Backend/
├── main.py (FastAPI app setup)
├── intent_parser.py (GROQ LLM intent parsing)
├── safety.py (validation logic)
├── simulator.py (contract simulation)
├── genlayer_client.py (GenLayer SDK wrapper)
└── routers/
    ├── chat.py (chat endpoints)
    └── wallet.py (wallet endpoints)
```

---

## 🚀 Getting Started

### Prerequisites

- **Node.js** 18+ (for frontend)
- **Python** 3.9+ (for backend)
- **Git**
- **GROQ API Key** (free at https://console.groq.com)
- **GenLayer Wallet** (testnet credentials)

### Installation

#### 1. Clone the Repository
```bash
git clone https://github.com/9ytshade/genlayer-bot.git
cd genlayer-bot
```

#### 2. Setup Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your credentials:
# - GROQ_API_KEY: Get from https://console.groq.com
# - WALLET_PRIVATE_KEY: Your GenLayer testnet private key
# - WALLET_ADDRESS: Your GenLayer testnet address
# - GENLAYER_RPC_URL: https://rpc-bradbury.genlayer.com

# Start backend server
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### 3. Setup Frontend

```bash
cd ../frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

#### 4. Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

---

## � Railway Deployment

This repo includes Railway-friendly startup files for backend and frontend deployment.

### Backend
- `backend/Procfile` starts the FastAPI app via Uvicorn
- Railway will use `PORT` for the listening port
- Backend env vars should include:
  - `GENLAYER_RPC_URL`
  - `GENLAYER_CHAIN_ID`
  - `WALLET_PRIVATE_KEY`
  - `WALLET_ADDRESS`
  - `DATABASE_URL`
  - `GROQ_API_KEY`
  - `ENCRYPTION_KEY`

### Frontend
- `frontend/Procfile` starts Next.js with `npm run start`
- Configure Railway env vars for the frontend build:
  - `NEXT_PUBLIC_API_URL` → your Railway backend URL
  - `NEXT_PUBLIC_GENLAYER_RPC_URL_BRADBURY`
  - `NEXT_PUBLIC_GENLAYER_CHAIN_ID_BRADBURY`
  - `NEXT_PUBLIC_GENLAYER_RPC_URL_STUDIONET`
  - `NEXT_PUBLIC_GENLAYER_CHAIN_ID_STUDIONET`
  - `NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID`

### Railway backend service
- `railway.json` is now configured as a root-level backend-only Railway service definition.
- Deploying this project on Railway will start the backend from `backend/` and expose a public backend URL.
- Use that URL in your frontend environment via `NEXT_PUBLIC_API_URL`.

### Optional frontend deployment
- `frontend/Procfile` is still available if you want to deploy the frontend separately on Railway or another host.

---

## �📖 Usage Guide

### Basic Operations

#### 1. **Check Balance**
```
User: "What is my balance?"
```
- AI parses intent
- Shows balance check in UI
- No transaction needed

#### 2. **Send Tokens**
```
User: "Send 10 GEN to 0x742d35Cc6634C0532925a3b844Bc0e7595f24a2d"
```
- Parses recipient & amount
- Shows risk indicator (🟢 Low Risk for 10 GEN)
- Displays gas estimate
- Simulates outcome
- Waits for confirmation
- Executes transaction

#### 3. **Deploy Contract**
```
User: "Create a weekly payment contract for my designer"
```
- Builds contract spec from template
- Simulates with sample inputs
- Shows multiple outcome scenarios
- Requires confirmation before deployment

### UI Features

#### Command Palette (Cmd+K / Ctrl+K)
- Search available commands
- View recent commands
- Quick access to common operations

#### Quick Actions
- **Check Balance**: View wallet balance
- **Send Tokens**: Quick transfer interface
- **Deploy Contract**: Contract creation wizard

#### Transaction Details
- ⏰ **Timestamps**: When each transaction occurred
- 📋 **Copy Hash**: One-click hash copying
- 🎯 **Risk Indicator**: Visual safety assessment
- ⛽ **Gas Estimate**: Estimated network fees
- 🔄 **Retry Button**: On failed transactions

---

## 🔐 Security Model

### 1. Intent Parsing (Structured Output)
✅ GROQ LLM with function calling → JSON schema only  
❌ NO free-form text execution  
✅ Schema validation before processing

### 2. Validation Layer
✅ Check action type is supported  
✅ Validate recipient address format  
✅ Verify amount is within limits  
✅ Check user has sufficient balance  

### 3. Simulation Layer
✅ Run contract logic without state changes  
✅ Calculate gas estimates  
✅ Detect potential errors early  
✅ Show outcome scenarios to user

### 4. Confirmation Layer
✅ Explicit user approval required  
✅ Show full transaction details  
✅ Display risk assessment  
✅ Allow cancellation at any time

### 5. GenLayer Integration
✅ Use GenLayer's consensus system  
✅ Distributed oracle validation  
✅ On-chain execution tracking  
✅ Immutable transaction records

### Environment Variables (NEVER commit!)
```bash
# .env (DO NOT COMMIT)
GROQ_API_KEY=gsk_xxxxxxxxxxxx          # GROQ API key
WALLET_PRIVATE_KEY=0xabc...            # Private key (KEEP SECRET!)
WALLET_ADDRESS=0x123...                # Your wallet address
GENLAYER_RPC_URL=https://rpc-bradbury.genlayer.com
MAX_TRANSFER_AMOUNT=1000               # Spending limit (GEN)
```

---

## 🛠️ Tech Stack

### Frontend
- **Framework**: Next.js 16.2.4 with React 19
- **Styling**: Tailwind CSS 4
- **Animations**: Framer Motion
- **Icons**: Lucide React
- **Language**: TypeScript
- **Build Tool**: Turbopack

### Backend
- **Framework**: FastAPI
- **Server**: Uvicorn
- **LLM**: GROQ (llama-3.3-70b-versatile)
- **Blockchain**: GenLayer SDK (genlayer-py)
- **Web3**: Web3.py
- **Validation**: Pydantic 2.4+
- **Language**: Python 3.9+

### DevOps
- **Package Manager**: npm, pip
- **Version Control**: Git
- **Environment**: Python venv, Node.js npm

---

## 📊 Project Status

### ✅ Completed (V1 - MVP)
- [x] Chat UI with terminal aesthetic
- [x] Intent parser with GROQ LLM
- [x] Token transfer functionality
- [x] Balance checking
- [x] Safety validation layer
- [x] Simulation engine
- [x] Confirmation flow
- [x] GenLayer integration
- [x] Risk indicators
- [x] Gas fee estimation
- [x] Command palette
- [x] Quick actions
- [x] Error handling

### 🚧 In Development (V2)
- [ ] Conditional payment contracts
- [ ] Transaction history persistence
- [ ] Advanced contract templates
- [ ] Multi-wallet support

### 📋 Planned (V3+)
- [ ] Escrow contracts
- [ ] Subscription contracts
- [ ] Natural language → advanced contract builder
- [ ] Autonomous agents
- [ ] Monitoring dashboard
- [ ] Mobile app
- [ ] Multi-chain support

---

## 📁 Project Structure

```
genlayer-bot/
├── frontend/                      # Next.js React app
│   ├── src/
│   │   ├── app/                  # Next.js pages & layout
│   │   ├── components/           # React components
│   │   ├── context/              # React context (wallet)
│   │   └── lib/                  # Utilities & API calls
│   ├── package.json
│   ├── tsconfig.json
│   └── tailwind.config.ts
│
├── backend/                       # FastAPI Python app
│   ├── routers/                  # API route handlers
│   ├── main.py                   # FastAPI app setup
│   ├── intent_parser.py          # GROQ LLM parsing
│   ├── safety.py                 # Validation logic
│   ├── simulator.py              # Simulation engine
│   ├── genlayer_client.py        # GenLayer SDK wrapper
│   ├── requirements.txt          # Python dependencies
│   ├── .env.example              # Environment template
│   └── .env                      # Environment (DO NOT COMMIT!)
│
├── Gen Layer Docs/               # Reference documentation
├── handover_prompt.md            # Project specification
├── .gitignore                    # Git ignore rules
└── README.md                     # This file
```

---

## 🧪 Testing

### Manual Testing Checklist

- [ ] **Balance Check**: "What is my balance?"
- [ ] **Small Transfer**: "Send 5 GEN to [address]" (should be 🟢 Safe)
- [ ] **Medium Transfer**: "Send 250 GEN to [address]" (should be 🟡 Medium)
- [ ] **Large Transfer**: "Send 5000 GEN to [address]" (should be 🔴 High)
- [ ] **Invalid Input**: "Send GEN to invalid" (should error gracefully)
- [ ] **Command Palette**: Press Cmd+K to open
- [ ] **Quick Actions**: Click available buttons
- [ ] **Error Handling**: Attempt failed transaction, check retry button
- [ ] **Hash Copy**: Copy tx hash to clipboard

### API Testing
```bash
# Health check
curl http://localhost:8000/health

# Send message
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Send 10 GEN to 0x..."}'

# API docs (Swagger UI)
http://localhost:8000/docs
```

---

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### Development Guidelines
- Keep components focused and reusable
- Add TypeScript types for frontend components
- Add docstrings to Python functions
- Test security implications carefully
- Never commit `.env` files
- Follow existing code style

---

## 🐛 Troubleshooting

### Backend Issues

**Error: `GROQ_API_KEY not found`**
```bash
# Solution: Add to .env
GROQ_API_KEY=gsk_your_key_here
```

**Error: `WALLET_PRIVATE_KEY not found`**
```bash
# Solution: Add to .env
WALLET_PRIVATE_KEY=0x...your_private_key
WALLET_ADDRESS=0x...your_address
```

**Error: `Failed to fetch` in frontend**
- Check backend is running on http://localhost:8000
- Check CORS is enabled (should be in main.py)
- Check browser console for detailed error

### Frontend Issues

**Error: `Cannot find module`**
```bash
cd frontend
npm install
```

**Port already in use**
```bash
# Kill process on port 3000
lsof -ti:3000 | xargs kill -9  # macOS/Linux
netstat -ano | findstr :3000   # Windows (find PID, then taskkill /PID xxx)
```

---

## 📚 Resources

- [GenLayer Documentation](https://docs.genlayer.com)
- [GROQ API Docs](https://console.groq.com/docs)
- [Next.js Documentation](https://nextjs.org/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Web3.py Documentation](https://web3py.readthedocs.io)

---

## 📝 License

This project is open source under the MIT License.

---

## 🙌 Acknowledgments

- **GenLayer Team**: For the intelligent oracle infrastructure
- **GROQ**: For fast, reliable LLM inference
- **Web3 Community**: For blockchain development tools
- **Design Inspiration**: Modern trading terminals

---

## 📧 Contact & Support

- **Issues**: [GitHub Issues](https://github.com/9ytshade/genlayer-bot/issues)
- **Discussions**: [GitHub Discussions](https://github.com/9ytshade/genlayer-bot/discussions)
- **Security Issues**: Please email security@genlayer.bot

---

## 🚀 What's Next?

Join the development! Check out the [Project Board](https://github.com/9ytshade/genlayer-bot/projects) to see what's being worked on.

**Star ⭐ the repository if you find this project interesting!**

---

*Built with ❤️ for the GenLayer ecosystem | Last Updated: April 2026*
