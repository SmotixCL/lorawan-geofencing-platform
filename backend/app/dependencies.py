from app.core.database import SessionLocal

async def get_db():
    async with SessionLocal() as session:
        yield session
