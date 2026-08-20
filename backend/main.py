from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from contextlib import asynccontextmanager
import os
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from . import auth
from .database import run_migrations
from .genlayer_client import close_clients
from .logs_store import reset_log_wallet_address, set_log_wallet_address
from .rate_limit import limiter, rate_limit_exceeded_handler
from .readiness import assert_production_configuration, readiness_report
from .routers import chat, logs, users, wallet

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    assert_production_configuration()
    run_migrations()
    try:
        yield
    finally:
        await close_clients()

app = FastAPI(title="GenLayer AI Chatbot API", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def bind_authenticated_log_scope(request, call_next):
    try:
        wallet_address = auth.get_wallet_address_from_authorization(
            request.headers.get("authorization")
        )
    except Exception:
        wallet_address = None
    token = set_log_wallet_address(wallet_address)
    try:
        return await call_next(request)
    finally:
        reset_log_wallet_address(token)

app.include_router(chat.router)
app.include_router(wallet.router)
app.include_router(logs.router)
app.include_router(auth.router)
app.include_router(users.router, prefix="/users", tags=["users"])

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "genlayer-bot-api"}


@app.get("/ready")
def readiness_check():
    report = readiness_report()
    return JSONResponse(content=report, status_code=200 if report["status"] == "ready" else 503)
