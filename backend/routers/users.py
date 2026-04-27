from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from database import get_db
from models import User, PlatformWallet
from schemas import UserCreate, UserResponse, PlatformWalletResponse, PlatformWalletWithPrivateKey
from web3 import Web3
import os

router = APIRouter(prefix="/users", tags=["users"])

# Simple token-based auth for now (in production, use JWT)
def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)):
    """Extract user from token (wallet address)"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    try:
        # Token format: "Bearer 0x..."
        token = authorization.split(" ")[1]
        if not Web3.is_address(token):
            raise HTTPException(status_code=401, detail="Invalid wallet address")
        
        user = db.query(User).filter(User.connected_wallet_address == token).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except IndexError:
        raise HTTPException(status_code=401, detail="Invalid token format")


@router.post("/register", response_model=UserResponse)
def register_user(user_create: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user with their connected wallet address.
    Also creates a platform wallet for the user.
    """
    # Validate wallet address
    if not Web3.is_address(user_create.connected_wallet_address):
        raise HTTPException(status_code=400, detail="Invalid Ethereum address")
    
    # Check if user already exists
    db_user = db.query(User).filter(
        User.connected_wallet_address == user_create.connected_wallet_address
    ).first()
    
    if not db_user:
        # Create new user
        db_user = User(connected_wallet_address=user_create.connected_wallet_address)
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
    
    # Ensure user has a platform wallet
    existing_wallet = db.query(PlatformWallet).filter(
        PlatformWallet.user_id == db_user.id
    ).first()
    
    if not existing_wallet:
        # Create a platform wallet for the user
        w3 = Web3()
        account = w3.eth.account.create()
        
        platform_wallet = PlatformWallet(
            user_id=db_user.id,
            address=account.address
        )
        platform_wallet.set_private_key(account.key.hex())
        
        db.add(platform_wallet)
        db.commit()
        db.refresh(platform_wallet)
    
    return db_user


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user info"""
    return current_user


@router.get("/me/wallet", response_model=PlatformWalletResponse)
def get_user_platform_wallet(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get user's platform wallet"""
    wallet = db.query(PlatformWallet).filter(
        PlatformWallet.user_id == current_user.id
    ).first()
    
    if not wallet:
        raise HTTPException(status_code=404, detail="Platform wallet not found")
    
    return wallet


@router.post("/me/wallet/create", response_model=PlatformWalletWithPrivateKey)
def create_user_platform_wallet(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Create a new platform wallet for the user.
    Returns the private key ONLY on creation.
    """
    # Check if user already has a wallet
    existing_wallet = db.query(PlatformWallet).filter(
        PlatformWallet.user_id == current_user.id
    ).first()
    
    if existing_wallet:
        raise HTTPException(status_code=400, detail="User already has a platform wallet")
    
    # Create new account
    w3 = Web3()
    account = w3.eth.account.create()
    
    # Store wallet
    platform_wallet = PlatformWallet(
        user_id=current_user.id,
        address=account.address
    )
    platform_wallet.set_private_key(account.key.hex())
    
    db.add(platform_wallet)
    db.commit()
    db.refresh(platform_wallet)
    
    return {
        "id": platform_wallet.id,
        "user_id": platform_wallet.user_id,
        "address": platform_wallet.address,
        "private_key": account.key.hex(),
        "balance": platform_wallet.balance,
        "created_at": platform_wallet.created_at
    }
