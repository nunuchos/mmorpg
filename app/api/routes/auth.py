from fastapi import APIRouter, HTTPException, Request, status

from app.core.dependencies import CurrentPlayer, DBSession, RedisClient
from app.schemas.auth import (
    LoginRequest,
    MessageResponse,
    PlayerPublic,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=PlayerPublic, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: DBSession):
    try:
        player = await AuthService.register(db, body)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return player


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: DBSession, redis: RedisClient):
    try:
        tokens = await AuthService.login(db, redis, body)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    return tokens


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, redis: RedisClient):
    try:
        tokens = await AuthService.refresh(redis, body.refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return tokens


@router.post("/logout", response_model=MessageResponse)
async def logout(request: Request, redis: RedisClient, current_player: CurrentPlayer):
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    await AuthService.logout(redis, token)
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=PlayerPublic)
async def me(current_player: CurrentPlayer):
    return current_player