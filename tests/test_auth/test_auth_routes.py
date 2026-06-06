import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.postgres import Base, get_db
from app.db.redis import get_redis
from main import app

# ── Test database — SQLite in memory ─────────────────────────────────────────

TEST_DB_URL = "sqlite+aiosqlite:///./test.db"

test_engine = create_async_engine(
    TEST_DB_URL, connect_args={"check_same_thread": False}
)
TestSession = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


async def override_db():
    async with TestSession() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Fake Redis — dict backed ──────────────────────────────────────────────────

class FakeRedis:
    def __init__(self):
        self._store: dict = {}

    async def set(self, key: str, value: str, ex: int | None = None):
        self._store[key] = value

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def exists(self, key: str) -> bool:
        return key in self._store

    async def delete(self, key: str):
        self._store.pop(key, None)

    async def ping(self):
        return True


_fake_redis = FakeRedis()


async def override_redis():
    yield _fake_redis


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(autouse=True, scope="session")
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(autouse=True)
async def clear_redis():
    _fake_redis._store.clear()
    yield


@pytest_asyncio.fixture
async def client():
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = override_redis
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


# ── Helper ────────────────────────────────────────────────────────────────────

PLAYER = {"username": "hero123", "email": "hero@game.com", "password": "Secret1234"}


async def register_and_login(client: AsyncClient) -> str:
    await client.post("/api/v1/auth/register", json=PLAYER)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": PLAYER["username"], "password": PLAYER["password"]},
    )
    return resp.json()["access_token"]


# ── Tests ─────────────────────────────────────────────────────────────────────

async def test_register_success(client):
    resp = await client.post("/api/v1/auth/register", json=PLAYER)
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "hero123"
    assert "hashed_password" not in data
    assert "password" not in data


async def test_register_duplicate_username(client):
    await client.post("/api/v1/auth/register", json=PLAYER)
    resp = await client.post("/api/v1/auth/register", json=PLAYER)
    assert resp.status_code == 409


async def test_register_duplicate_email(client):
    await client.post("/api/v1/auth/register", json=PLAYER)
    resp = await client.post(
        "/api/v1/auth/register",
        json={**PLAYER, "username": "different"},
    )
    assert resp.status_code == 409


async def test_register_weak_password(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={**PLAYER, "password": "alllowercase"},
    )
    assert resp.status_code == 422


async def test_register_no_digit_password(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={**PLAYER, "password": "NoDigitsHere"},
    )
    assert resp.status_code == 422


async def test_register_invalid_username_chars(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={**PLAYER, "username": "hero 123"},  # space not allowed
    )
    assert resp.status_code == 422


async def test_login_success(client):
    await client.post("/api/v1/auth/register", json=PLAYER)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": PLAYER["username"], "password": PLAYER["password"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 1800


async def test_login_wrong_password(client):
    await client.post("/api/v1/auth/register", json=PLAYER)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": PLAYER["username"], "password": "WrongPass1"},
    )
    assert resp.status_code == 401


async def test_login_unknown_username(client):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "nobody", "password": "Secret1234"},
    )
    assert resp.status_code == 401
    # Same message as wrong password — no username enumeration
    assert resp.json()["detail"] == "Invalid username or password"


async def test_me_authenticated(client):
    token = await register_and_login(client)
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["username"] == "hero123"


async def test_me_no_token(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 403


async def test_me_invalid_token(client):
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer this.is.garbage"},
    )
    assert resp.status_code == 401


async def test_logout_invalidates_token(client):
    token = await register_and_login(client)

    logout = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert logout.status_code == 200

    # Same token now rejected
    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 401


async def test_refresh_issues_new_tokens(client):
    await client.post("/api/v1/auth/register", json=PLAYER)
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": PLAYER["username"], "password": PLAYER["password"]},
    )
    refresh_token = login_resp.json()["refresh_token"]

    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["access_token"] != login_resp.json()["access_token"]


async def test_refresh_token_rotation(client):
    await client.post("/api/v1/auth/register", json=PLAYER)
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": PLAYER["username"], "password": PLAYER["password"]},
    )
    refresh_token = login_resp.json()["refresh_token"]

    # First refresh — should succeed
    first = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert first.status_code == 200

    # Same refresh token again — should fail (rotated)
    second = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert second.status_code == 401


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"