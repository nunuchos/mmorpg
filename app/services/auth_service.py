from datetime import datetime, timezone

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.models.player import Player
from app.models.player_stats import PlayerStats
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse


class AuthService:

    @staticmethod
    async def register(db: AsyncSession, data: RegisterRequest) -> Player:
        # Check username
        result = await db.execute(select(Player).where(Player.username == data.username))
        if result.scalar_one_or_none():
            raise ValueError("Username already taken")

        # Check email
        result = await db.execute(select(Player).where(Player.email == data.email))
        if result.scalar_one_or_none():
            raise ValueError("Email already registered")

        player = Player(
            username=data.username,
            email=data.email,
            hashed_password=hash_password(data.password),
        )
        db.add(player)
        await db.flush()  # writes player to DB, generates id, doesn't commit yet

        stats = PlayerStats(player_id=player.id)
        db.add(stats)

        await db.commit()
        await db.refresh(player)
        return player

    @staticmethod
    async def login(db: AsyncSession, redis: Redis, data: LoginRequest) -> TokenResponse:
        result = await db.execute(select(Player).where(Player.username == data.username))
        player = result.scalar_one_or_none()

        if not player or not verify_password(data.password, player.hashed_password):
            raise ValueError("Invalid username or password")

        if player.is_banned:
            raise PermissionError("Account is banned")

        if not player.is_active:
            raise PermissionError("Account is deactivated")

        access_token = create_access_token(player.id)
        refresh_token = create_refresh_token(player.id)

        ttl = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        await redis.set(f"session:{access_token}", player.id, ex=ttl)

        refresh_ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
        await redis.set(f"refresh:{refresh_token}", player.id, ex=refresh_ttl)

        player.last_login = datetime.now(timezone.utc)
        await db.commit()

        return TokenResponse(access_token=access_token, refresh_token=refresh_token, expires_in=ttl)

    @staticmethod
    async def refresh(redis: Redis, refresh_token: str) -> TokenResponse:
        player_id = await redis.get(f"refresh:{refresh_token}")
        if not player_id:
            raise ValueError("Refresh token invalid or expired")

        # Rotate — delete old, issue new
        await redis.delete(f"refresh:{refresh_token}")

        new_access = create_access_token(player_id)
        new_refresh = create_refresh_token(player_id)

        ttl = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        await redis.set(f"session:{new_access}", player_id, ex=ttl)

        refresh_ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
        await redis.set(f"refresh:{new_refresh}", player_id, ex=refresh_ttl)

        return TokenResponse(access_token=new_access, refresh_token=new_refresh, expires_in=ttl)

    @staticmethod
    async def logout(redis: Redis, access_token: str) -> None:
        await redis.delete(f"session:{access_token}")

    @staticmethod
    async def get_player_by_id(db: AsyncSession, player_id: str) -> Player | None:
        result = await db.execute(select(Player).where(Player.id == player_id))
        return result.scalar_one_or_none()