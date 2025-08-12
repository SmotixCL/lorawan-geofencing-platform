from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Base de Datos
    DATABASE_URL: str = "postgresql+asyncpg://lorawan_user:Roro123123@localhost/lorawan_platform"
    
    # Seguridad
    SECRET_KEY: str = "tu-clave-secreta-muy-segura-cambiar-en-produccion"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # ChirpStack API (NUEVOS CAMPOS)
    CHIRPSTACK_API_URL: Optional[str] = "http://localhost:8080"
    CHIRPSTACK_API_TOKEN: Optional[str] = ""
    
    class Config:
        env_file = ".env"
        case_sensitive = False  # No distingue mayúsculas/minúsculas

settings = Settings()
