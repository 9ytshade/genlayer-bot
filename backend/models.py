from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
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
    notary_registries = relationship("NotaryRegistry", back_populates="user", cascade="all, delete-orphan")
    notary_claims = relationship("NotaryClaim", back_populates="user", cascade="all, delete-orphan")


class SiweNonce(Base):
    """Single-use SIWE challenge persisted across backend instances."""

    __tablename__ = "siwe_nonces"

    id = Column(Integer, primary_key=True)
    wallet_address = Column(String, unique=True, index=True, nullable=False)
    nonce_hash = Column(String, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


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
    lifecycle_status = Column(String, nullable=False, default="PREPARED", index=True)
    evm_status = Column(String, nullable=False, default="NOT_BROADCAST")
    consensus_status = Column(String, nullable=False, default="UNINITIALIZED")
    execution_status = Column(String, nullable=False, default="UNKNOWN")
    final = Column(Boolean, nullable=False, default=False)
    terminal = Column(Boolean, nullable=False, default=False)
    appealable = Column(Boolean, nullable=False, default=False)
    protocol_result = Column(String, nullable=True)
    num_rounds = Column(Integer, nullable=True)
    validator_count = Column(Integer, nullable=True)
    vote_count = Column(Integer, nullable=True)
    zero_round_no_majority = Column(Boolean, nullable=False, default=False)
    diagnostic_json = Column(Text, nullable=False, default="{}")
    last_polled_at = Column(DateTime, nullable=True)
    last_action = Column(String, nullable=True)
    last_action_tx_hash = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="workflow_deployments")


class PreparedTransaction(Base):
    """A wallet-reviewed transaction envelope bound to one authenticated user."""

    __tablename__ = "prepared_transactions"

    id = Column(String, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    action = Column(String, nullable=False, index=True)
    network = Column(String, nullable=False, index=True)
    chain_id = Column(Integer, nullable=False)
    sender_address = Column(String, nullable=False, index=True)
    to_address = Column(String, nullable=False)
    data = Column(Text, nullable=False, default="0x")
    calldata_hash = Column(String, nullable=False, index=True)
    value_wei = Column(String, nullable=False, default="0")
    gas_limit = Column(Integer, nullable=False)
    nonce = Column(Integer, nullable=False)
    gas_price = Column(String, nullable=True)
    max_fee_per_gas = Column(String, nullable=True)
    max_priority_fee_per_gas = Column(String, nullable=True)
    consensus_max_rotations = Column(Integer, nullable=True)
    leader_only = Column(Boolean, nullable=False, default=False)
    intent_json = Column(Text, nullable=False, default="{}")
    intent_hash = Column(String, nullable=False, index=True)
    intent_version = Column(Integer, nullable=False, default=2)
    consensus_tx_id = Column(String, nullable=True, index=True)
    tx_hash = Column(String, nullable=True, index=True, unique=True)
    status = Column(String, nullable=False, default="prepared", index=True)
    lifecycle_status = Column(String, nullable=False, default="PREPARED", index=True)
    evm_status = Column(String, nullable=False, default="NOT_BROADCAST")
    consensus_status = Column(String, nullable=False, default="UNINITIALIZED")
    execution_status = Column(String, nullable=False, default="UNKNOWN")
    final = Column(Boolean, nullable=False, default=False)
    terminal = Column(Boolean, nullable=False, default=False)
    appealable = Column(Boolean, nullable=False, default=False)
    protocol_result = Column(String, nullable=True)
    num_rounds = Column(Integer, nullable=True)
    validator_count = Column(Integer, nullable=True)
    vote_count = Column(Integer, nullable=True)
    zero_round_no_majority = Column(Boolean, nullable=False, default=False)
    diagnostic_json = Column(Text, nullable=False, default="{}")
    last_polled_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=False)
    confirmed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")


class NotaryRegistry(Base):
    """Backend reference to a reusable on-chain AI Notary registry."""

    __tablename__ = "notary_registries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    network = Column(String, nullable=False, default="studionet", index=True)
    contract_address = Column(String, nullable=True, index=True)
    deploy_tx_hash = Column(String, nullable=True, index=True)
    consensus_tx_id = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, default="submitted", index=True)
    source_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="notary_registries")
    claims = relationship("NotaryClaim", back_populates="registry", cascade="all, delete-orphan")


class NotaryClaim(Base):
    """Wallet-scoped cache of a claim reference; on-chain state remains authoritative."""

    __tablename__ = "notary_claims"
    __table_args__ = (
        UniqueConstraint("registry_id", "claim_id", name="uq_notary_claim_registry_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    registry_id = Column(Integer, ForeignKey("notary_registries.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    claim_id = Column(String, nullable=False, index=True)
    spec_json = Column(Text, nullable=False, default="{}")
    submit_tx_hash = Column(String, nullable=True, index=True)
    submit_consensus_tx_id = Column(String, nullable=True, index=True)
    evaluate_tx_hash = Column(String, nullable=True, index=True)
    evaluate_consensus_tx_id = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, default="submitted", index=True)
    verdict = Column(String, nullable=False, default="PENDING", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    registry = relationship("NotaryRegistry", back_populates="claims")
    user = relationship("User", back_populates="notary_claims")
