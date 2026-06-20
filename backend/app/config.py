"""Application configuration from environment variables."""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "JeevanMarg"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./jeevanmarg.db"

    # Authentication
    JWT_SECRET: str = "jeevanmarg-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 24

    # Google ADK
    GOOGLE_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # MCP Server Ports (for HTTP transport)
    TRAFFIC_MCP_PORT: int = 8010
    ROUTE_MCP_PORT: int = 8011
    HOSPITAL_MCP_PORT: int = 8012
    TRUST_MCP_PORT: int = 8013

    # Rate Limiting
    RATE_LIMIT_GENERAL: str = "100/minute"
    RATE_LIMIT_MUTATIONS: str = "10/minute"

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Demo
    DEMO_CITY: str = "Delhi"
    AUTO_PROGRESS_SCENARIOS: bool = True

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
