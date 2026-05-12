import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

# Use SQLite for simplicity; can be upgraded to PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./genlayer_bot.db")

# Fix for SQLAlchemy 1.4+ which requires 'postgresql://' instead of 'postgres://'
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    # SQLite requires check_same_thread=False
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    # Import models here to ensure their table definitions are registered
    # with Base.metadata before create_all is called, regardless of
    # import order in the application startup sequence.
    try:
        from .models import User, PlatformWallet  # noqa: F401
    except ImportError:
        from models import User, PlatformWallet  # noqa: F401
    Base.metadata.create_all(bind=engine)
