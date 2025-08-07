from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# URL de conexión a la base de datos PostgreSQL con el driver asyncpg
DATABASE_URL = "postgresql+asyncpg://lorawan_user:Roro123123@localhost/lorawan_platform"

# Crear el motor de la base de datos
engine = create_async_engine(DATABASE_URL, echo=False)

# Crear una clase SessionLocal para cada solicitud
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)

# Declarar una base para tus modelos de SQLAlchemy
Base = declarative_base()
