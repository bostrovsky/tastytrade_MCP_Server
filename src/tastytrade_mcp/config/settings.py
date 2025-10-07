"""Settings for TastyTrade MCP Server."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Settings:
    """Application settings."""

    # OAuth Settings
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    refresh_token: Optional[str] = None

    # Environment
    use_production: bool = False
    use_database_mode: bool = False
    use_sandbox: bool = True
    debug: bool = False
    environment: str = "development"

    # Server
    server_name: str = "tastytrade-mcp"
    server_version: str = "1.0.0"
    app_version: str = "1.0.6"

    # Database (if enabled)
    database_url: Optional[str] = None

    # Security
    secret_key: str = "default-secret-key-change-in-production"
    encryption_key: str = "default-encryption-key-change-in-production"
    encryption_salt: Optional[bytes] = None

    # Cache
    use_redis: bool = False
    redis_url: str = "redis://localhost:6379/0"

    # Logging
    log_level: str = "INFO"

    # Mode (for backwards compatibility)
    mode: str = "simple"

    @classmethod
    def from_env(cls) -> "Settings":
        """Load settings from environment variables."""
        use_production = os.getenv("TASTYTRADE_USE_PRODUCTION", "false").lower() == "true"
        use_database = os.getenv("TASTYTRADE_USE_DATABASE_MODE", "false").lower() == "true"

        return cls(
            client_id=os.getenv("TASTYTRADE_CLIENT_ID") or os.getenv("OAUTH_CLIENT_ID"),
            client_secret=os.getenv("TASTYTRADE_CLIENT_SECRET") or os.getenv("OAUTH_CLIENT_SECRET"),
            refresh_token=os.getenv("TASTYTRADE_REFRESH_TOKEN"),
            use_production=use_production,
            use_database_mode=use_database,
            use_sandbox=not use_production,
            debug=os.getenv("DEBUG", "false").lower() == "true",
            environment=os.getenv("ENVIRONMENT", "development"),
            database_url=os.getenv("DATABASE_URL"),
            mode="database" if use_database else "simple",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
    return _settings
