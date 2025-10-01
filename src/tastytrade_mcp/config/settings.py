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

    # Server
    server_name: str = "tastytrade-mcp"
    server_version: str = "1.0.0"

    # Database (if enabled)
    database_url: Optional[str] = None

    @classmethod
    def from_env(cls) -> "Settings":
        """Load settings from environment variables."""
        return cls(
            client_id=os.getenv("TASTYTRADE_CLIENT_ID"),
            client_secret=os.getenv("TASTYTRADE_CLIENT_SECRET"),
            refresh_token=os.getenv("TASTYTRADE_REFRESH_TOKEN"),
            use_production=os.getenv("TASTYTRADE_USE_PRODUCTION", "false").lower() == "true",
            use_database_mode=os.getenv("TASTYTRADE_USE_DATABASE", "false").lower() == "true",
            database_url=os.getenv("DATABASE_URL"),
        )


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
    return _settings
