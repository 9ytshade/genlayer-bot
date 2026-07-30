from fastapi import APIRouter, Depends

from ..auth import get_current_user
from ..models import User
from ..schemas import UserResponse

router = APIRouter()


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get the authenticated user for the connected wallet."""
    return current_user
