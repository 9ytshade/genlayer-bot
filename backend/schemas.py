from datetime import datetime

from pydantic import BaseModel


class UserResponse(BaseModel):
    """Schema for the authenticated connected-wallet user."""
    id: int
    connected_wallet_address: str
    created_at: datetime

    class Config:
        from_attributes = True
