from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings
import uuid



#password

def hash_password(plain:str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())

#jwt



def _make_token(payload: dict, expires_delta: timedelta) -> str:
    data = payload.copy()
    data["exp"] = datetime.now(timezone.utc) + expires_delta
    data["jti"] = str(uuid.uuid4())  # ← unique per token
    return jwt.encode(data, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def create_access_token(player_id: str) -> str:
    return _make_token(
        {"sub": player_id, "type": "access"},
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

def create_refresh_token(player_id: str) -> str:
    return _make_token({"sub": player_id, "type": "refresh"},
                       timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
                       )

def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(
        token, 
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM]
    )
