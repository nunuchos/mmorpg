from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.postgres import get_db
from app.db.redis import get_redis
from app.models.player import Player
from app.services.auth_service import AuthService

bearer_scheme = HTTPBearer()


async def get_current_player(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> Player:
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise invalid
        player_id: str = payload.get("sub")
        if not player_id:
            raise invalid
    except JWTError:
        raise invalid

    if not await redis.exists(f"session:{credentials.credentials}"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired — please log in again",
        )

    player = await AuthService.get_player_by_id(db, player_id)
    if not player:
        raise invalid

    return player


# Convenience type aliases — used in route signatures
DBSession = Annotated[AsyncSession, Depends(get_db)]
RedisClient = Annotated[Redis, Depends(get_redis)]
CurrentPlayer = Annotated[Player, Depends(get_current_player)]