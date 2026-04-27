from sqlalchemy import Column, String, DateTime, ForeignKey, Float, Integer
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base
from cryptography.fernet import Fernet
import os

# Encryption key for sensitive data
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", Fernet.generate_key().decode())

cipher = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)

class User(Base):
    """User model - represents a user connecting their wallet"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    connected_wallet_address = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to platform wallets
    platform_wallets = relationship("PlatformWallet", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "connected_wallet_address": self.connected_wallet_address,
            "created_at": self.created_at.isoformat(),
        }


class PlatformWallet(Base):
    """PlatformWallet model - represents a wallet owned by platform, funded by user"""
    __tablename__ = "platform_wallets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Wallet details
    address = Column(String, unique=True, index=True, nullable=False)
    private_key_encrypted = Column(String, nullable=False)  # Encrypted private key
    
    # Wallet state
    balance = Column(Float, default=0.0)  # GEN balance
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship back to user
    user = relationship("User", back_populates="platform_wallets")

    def set_private_key(self, private_key: str):
        """Encrypt and store private key"""
        self.private_key_encrypted = cipher.encrypt(private_key.encode()).decode()

    def get_private_key(self) -> str:
        """Decrypt and retrieve private key"""
        return cipher.decrypt(self.private_key_encrypted.encode()).decode()

    def to_dict(self, include_private_key=False):
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "address": self.address,
            "balance": self.balance,
            "created_at": self.created_at.isoformat(),
        }
        if include_private_key:
            data["private_key"] = self.get_private_key()
        return data
