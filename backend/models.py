from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    """User model represented by a connected wallet address."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    connected_wallet_address = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    chat_history = relationship("ChatHistory", back_populates="user", cascade="all, delete-orphan", uselist=False)
    workflow_deployments = relationship("WorkflowDeployment", back_populates="user", cascade="all, delete-orphan")


class ChatHistory(Base):
    """Wallet-scoped persisted chat history."""
    __tablename__ = "chat_histories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    payload = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="chat_history")


class WorkflowDeployment(Base):
    """Persisted workflow deployment scoped to the authenticated wallet user."""
    __tablename__ = "workflow_deployments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    workflow_type = Column(String, nullable=False, index=True)
    network = Column(String, nullable=False, default="studionet")
    config_json = Column(Text, nullable=False, default="{}")
    contract_address = Column(String, nullable=True, index=True)
    deploy_tx_hash = Column(String, nullable=True, index=True)
    consensus_tx_id = Column(String, nullable=True)
    status = Column(String, nullable=False, default="deploying")
    last_action = Column(String, nullable=True)
    last_action_tx_hash = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="workflow_deployments")
