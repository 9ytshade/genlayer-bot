from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from contextlib import asynccontextmanager
import os

try:
    from .routers import chat, wallet, logs
    from .database import init_db
except ImportError:
    # Fallback when running from inside backend directory.
    from routers import chat, wallet, logs
    from database import init_db

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - initialize database
    init_db()
    yield
    # Shutdown
    pass

app = FastAPI(title="GenLayer AI Chatbot API", lifespan=lifespan)

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

app.include_router(chat.router)
app.include_router(wallet.router)
app.include_router(logs.router)

@app.get("/health")
def health_check():
    return {"status": "healthy"}
