import asyncio
from app.schemas.auth import RegisterRequest, LoginRequest
from app.services.auth_service import AuthService
from app.db.postgres import AsyncSessionLocal, engine  # Imported engine
from app.db.redis import get_redis_pool
# Make sure to import your SQLAlchemy Base and Models 
# so SQLAlchemy knows what tables to create!
from app.models.player  import Base  # Adjust this import to match your project structure

async def main():
    # 1. Automatically build tables in the empty Docker database
    print("Initializing database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables ready.")

    # 2. Run the authentication tests
    async with AsyncSessionLocal() as db:
        redis = get_redis_pool()

        # Register
        req = RegisterRequest(
            username="hero123",
            email="hero@game.com",
            password="Secret1234"
        )
        player = await AuthService.register(db, req)
        print(f"Registered: {player.id} / {player.username}")

        # Login
        tokens = await AuthService.login(
            db, redis,
            LoginRequest(username="hero123", password="Secret1234")
        )
        print(f"Access token: {tokens.access_token[:40]}...")
        print(f"Expires in: {tokens.expires_in}s")

        # Verify session in Redis
        key = f"session:{tokens.access_token}"
        stored_id = await redis.get(key)
        
        # Redis returns bytes sometimes, decode if necessary or handle match checking
        if isinstance(stored_id, bytes):
            stored_id = stored_id.decode("utf-8")
            
        print(f"Redis session player_id: {stored_id}")
        print(f"Matches player.id: {str(stored_id) == str(player.id)}")

        # Logout
        await AuthService.logout(redis, tokens.access_token)
        still_there = await redis.exists(key)
        print(f"Session after logout: {still_there}")  # Should print 0 (False)

if __name__ == "__main__":
    asyncio.run(main())