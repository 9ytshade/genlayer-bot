import os

from fastapi import Request
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


def rate_limit_key(request: Request) -> str:
    authorization = request.headers.get("authorization")
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
        secret = os.getenv("JWT_SECRET")
        if secret:
            try:
                payload = jwt.decode(token, secret, algorithms=["HS256"])
                subject = payload.get("sub")
                if subject:
                    return f"wallet:{str(subject).lower()}"
            except JWTError:
                pass

    return get_remote_address(request)


limiter = Limiter(key_func=rate_limit_key)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many chat requests. Please wait a moment and try again."},
    )
