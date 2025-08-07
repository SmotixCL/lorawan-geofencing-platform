from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Base de Datos
    DATABASE_URL: str = "postgresql+asyncpg://lorawan_user:Roro123123@localhost/lorawan_platform"

    # Seguridad
    SECRET_KEY: str = "tu-clave-secreta-muy-segura-cambiar-en-produccion"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Integración con ChirpStack para Downlinks
    CHIRPSTACK_API_URL: str = "http://localhost:8080/api"
    CHIRPSTACK_API_KEY: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcGlfa2V5X2lkIjoiN2Q1ZmUyNTAtMWE0NS00ZjkyLThlNmQtMjcxYmQyZjA0MTA2IiwiYXVkIjoiYXMiLCJpc3MiOiJhcyIsIm5iZiI6MTc1MjExNTcxMywic3ViIjoiYXBpX2tleSJ9.1qPBnqxtqKs3HIn0iCek7Tojo4hAg0KLkw4aGIjH5jc"

    class Config:
        env_file = ".env"

settings = Settings()
