from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# User Schemas
class UserCreate(BaseModel):
    """Schema for creating a new user"""
    connected_wallet_address: str

    class Config:
        json_schema_extra = {
            "example": {
                "connected_wallet_address": "0x742d35Cc6634C0532925a3b844Bc0e7595f24a2d"
            }
        }


class UserResponse(BaseModel):
    """Schema for user response"""
    id: int
    connected_wallet_address: str
    created_at: datetime

    class Config:
        from_attributes = True


# Platform Wallet Schemas
class PlatformWalletCreate(BaseModel):
    """Schema for creating a platform wallet"""
    user_id: int


class PlatformWalletResponse(BaseModel):
    """Schema for platform wallet response"""
    id: int
    user_id: int
    address: str
    balance: float
    created_at: datetime

    class Config:
        from_attributes = True


class PlatformWalletWithPrivateKey(PlatformWalletResponse):
    """Schema for platform wallet with private key (only for creation)"""
    private_key: str


# Fund Wallet Schemas
class FundWalletRequest(BaseModel):
    """Schema for funding platform wallet from connected wallet"""
    amount: float

    class Config:
        json_schema_extra = {
            "example": {
                "amount": 100.0
            }
        }


class FundWalletResponse(BaseModel):
    """Schema for fund wallet response"""
    tx_hash: str
    from_address: str
    to_address: str
    amount: float
    status: str


# Transaction Schemas
class TransactionResponse(BaseModel):
    """Schema for transaction response"""
    tx_hash: str
    status: str
    error: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "tx_hash": "0x123...",
                "status": "success",
                "error": None
            }
        }
