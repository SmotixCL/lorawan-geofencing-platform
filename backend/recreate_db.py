# recreate_db.py
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.database import Base, DATABASE_URL
from app.models import device, group, geofence, position # Asegura que todos los modelos son importados

async def recreate_database():
    print("Conectando a la base de datos para reconstruir el esquema...")
    engine = create_async_engine(DATABASE_URL)
    
    async with engine.begin() as conn:
        print("Eliminando todas las tablas existentes...")
        await conn.run_sync(Base.metadata.drop_all)
        print("Creando todas las tablas...")
        await conn.run_sync(Base.metadata.create_all)
    
    print("¡Esquema de base de datos reconstruido con éxito!")

if __name__ == "__main__":
    asyncio.run(recreate_database())
