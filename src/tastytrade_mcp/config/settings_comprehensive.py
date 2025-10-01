"""Comprehensive settings configuration for TastyTrade MCP Server.

This file addresses all hardcoded values found in the codebase audit.
Move this to settings.py after review.
"""
from datetime import time
from functools import lru_cache
from typing import Literal, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with all hardcoded values externalized."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="TASTYTRADE_",  # All env vars start with TASTYTRADE_
    )

    # ============================================================
    # APPLICATION SETTINGS
    # ============================================================
    app_name: str = "tastytrade-mcp"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production", "testing"] = "development"
    debug: bool = True

    # ============================================================
    # TASTYTRADE API SETTINGS
    # ============================================================
    # API Endpoints
    api_base_url_production: str = "https://api.tastyworks.com"
    api_base_url_sandbox: str = "https://sandbox.api.tastyworks.com"
    oauth_base_url_production: str = "https://api.tastyworks.com/oauth"
    oauth_base_url_sandbox: str = "https://sandbox.api.tastyworks.com/oauth"
    oauth_redirect_uri: str = "http://localhost:8000/auth/oauth/callback"
    use_sandbox: bool = True

    # Credentials (for sandbox/testing only)
    sandbox_username: Optional[str] = None
    sandbox_password: Optional[str] = None

    # ============================================================
    # SECURITY SETTINGS
    # ============================================================
    # CRITICAL: Generate these for production!
    secret_key: str = "CHANGE-THIS-IN-PRODUCTION-USE-SECRETS-MANAGER"
    encryption_key: str = "CHANGE-THIS-IN-PRODUCTION-USE-SECRETS-MANAGER"
    encryption_salt: Optional[bytes] = None  # Will generate random if not provided
    encryption_pbkdf2_iterations: int = 100000
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24

    # ============================================================
    # DATABASE SETTINGS
    # ============================================================
    database_url: str = "postgresql+asyncpg://user:pass@localhost/tastytrade_mcp"
    database_pool_size: int = 20
    database_max_overflow: int = 40
    database_pool_timeout: int = 30
    database_echo_sql: bool = False

    # ============================================================
    # REDIS CACHE SETTINGS
    # ============================================================
    redis_url: str = "redis://localhost:6379/0"
    redis_max_connections: int = 10
    redis_decode_responses: bool = True
    use_redis: bool = True

    # ============================================================
    # HTTP CLIENT SETTINGS
    # ============================================================
    http_request_timeout_seconds: float = 30.0
    http_max_retries: int = 3
    http_retry_backoff_factor: float = 0.3
    http_pool_connections: int = 10
    http_pool_maxsize: int = 20

    # ============================================================
    # WEBSOCKET SETTINGS
    # ============================================================
    ws_max_reconnect_attempts: int = 10
    ws_heartbeat_interval_seconds: int = 30
    ws_reconnect_initial_delay_seconds: int = 1
    ws_reconnect_max_delay_seconds: int = 60
    ws_reconnect_backoff_multiplier: float = 2.0
    ws_max_symbols_per_request: int = 100
    ws_max_symbols_per_user: int = 100
    ws_latency_sample_retention_count: int = 1000
    ws_ping_timeout_seconds: int = 10
    ws_close_timeout_seconds: int = 10

    # ============================================================
    # MARKET HOURS (Eastern Time)
    # ============================================================
    market_timezone: str = "US/Eastern"
    market_pre_open_time: time = time(4, 0)  # 4:00 AM ET
    market_open_time: time = time(9, 30)  # 9:30 AM ET
    market_close_time: time = time(16, 0)  # 4:00 PM ET
    market_after_hours_close_time: time = time(20, 0)  # 8:00 PM ET

    # Trading calendar
    market_holidays_api_url: str = "https://api.tradingcalendar.com/holidays"

    # ============================================================
    # ORDER MANAGEMENT SETTINGS
    # ============================================================
    # Order Limits
    max_order_quantity: int = 10000
    min_order_quantity: int = 1
    max_order_value: float = 1000000.0  # $1M max per order

    # Order Preview
    order_preview_expiry_minutes: int = 2
    order_confirmation_code: str = "CONFIRM"
    order_confirmation_timeout_seconds: int = 60

    # Order Execution
    market_order_slippage_percent: float = 1.0
    default_price_estimate: float = 100.0
    stop_order_trigger_buffer_percent: float = 0.1

    # Token Management
    token_refresh_buffer_minutes: int = 5
    session_timeout_hours: int = 23

    # ============================================================
    # RATE LIMITING SETTINGS
    # ============================================================
    # API Rate Limits
    rate_limit_requests_per_minute: int = 100
    rate_limit_requests_per_second: int = 10
    rate_limit_window_seconds: int = 60
    rate_limit_burst_size: int = 20

    # Data Limits
    max_daily_api_calls: int = 10000
    max_daily_data_points: int = 100000
    max_concurrent_requests: int = 10
    batch_quote_limit: int = 50

    # User Limits
    max_orders_per_day_per_user: int = 500
    max_previews_per_hour_per_user: int = 100

    # ============================================================
    # CACHE TTL SETTINGS (in seconds)
    # ============================================================
    # Market Data Cache
    quote_cache_ttl_seconds: int = 5
    option_chain_cache_ttl_seconds: int = 60
    market_hours_cache_ttl_seconds: int = 86400  # 24 hours
    symbol_search_cache_ttl_seconds: int = 86400  # 24 hours

    # Historical Data Cache
    historical_cache_ttl_intraday_seconds: int = 3600  # 1 hour
    historical_cache_ttl_daily_seconds: int = 86400  # 24 hours
    historical_cache_ttl_weekly_seconds: int = 604800  # 7 days

    # Account Data Cache
    balance_cache_ttl_seconds: int = 30
    position_cache_ttl_seconds: int = 30
    order_cache_ttl_seconds: int = 5

    # ============================================================
    # RISK MANAGEMENT DEFAULTS
    # ============================================================
    # Position Limits
    default_max_position_size: int = 1000
    default_max_position_value: float = 50000.0
    default_max_portfolio_concentration: float = 0.10  # 10%

    # Portfolio Risk Limits
    default_max_daily_var: float = 5000.0
    default_max_portfolio_beta: float = 1.5
    default_max_sector_concentration: float = 0.25  # 25%

    # Account Limits
    default_min_buying_power_buffer: float = 1000.0
    default_max_daily_loss: float = 10000.0
    default_max_daily_trades: int = 100

    # Pattern Day Trader
    pdt_min_equity: float = 25000.0
    pdt_trade_limit_per_5_days: int = 3
    pdt_check_enabled: bool = True

    # Risk Validation
    risk_validation_timeout_ms: int = 50  # Must complete in 50ms
    risk_override_expiry_hours: int = 24

    # ============================================================
    # OPTIONS TRADING SETTINGS
    # ============================================================
    # Greeks Calculation
    options_risk_free_rate: float = 0.05  # 5% annual
    options_dividend_yield: float = 0.02  # 2% annual

    # Position Limits
    options_max_contracts_per_order: int = 100
    options_large_order_threshold: int = 50
    options_penny_stock_threshold: float = 5.0

    # Approval Levels
    options_min_account_value_level_1: float = 0.0
    options_min_account_value_level_2: float = 2000.0
    options_min_account_value_level_3: float = 10000.0
    options_min_account_value_level_4: float = 25000.0

    # Strategy Limits
    options_max_legs_per_strategy: int = 4
    options_max_spread_width: float = 50.0

    # ============================================================
    # HISTORICAL DATA LIMITS (in days)
    # ============================================================
    historical_1min_max_days: int = 30
    historical_5min_max_days: int = 90
    historical_15min_max_days: int = 90
    historical_30min_max_days: int = 180
    historical_1hour_max_days: int = 365
    historical_daily_max_days: int = 730  # 2 years
    historical_weekly_max_days: int = 1825  # 5 years
    historical_monthly_max_days: int = 3650  # 10 years

    # ============================================================
    # MONITORING & OBSERVABILITY
    # ============================================================
    # Metrics
    metrics_enabled: bool = True
    metrics_port: int = 9090
    metrics_path: str = "/metrics"

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    log_file_path: Optional[str] = None
    log_max_bytes: int = 10485760  # 10MB
    log_backup_count: int = 5

    # Tracing
    tracing_enabled: bool = False
    tracing_service_name: str = "tastytrade-mcp"
    tracing_jaeger_host: str = "localhost"
    tracing_jaeger_port: int = 6831

    # Health Checks
    health_check_interval_seconds: int = 30
    health_check_timeout_seconds: int = 5

    # ============================================================
    # FEATURE FLAGS
    # ============================================================
    feature_options_trading_enabled: bool = True
    feature_crypto_trading_enabled: bool = False
    feature_futures_trading_enabled: bool = False
    feature_international_exchanges_enabled: bool = False
    feature_paper_trading_enabled: bool = True
    feature_backtesting_enabled: bool = False
    feature_ai_insights_enabled: bool = False

    # ============================================================
    # BILLING & SUBSCRIPTION
    # ============================================================
    stripe_api_key: Optional[str] = None
    stripe_webhook_secret: Optional[str] = None
    billing_enabled: bool = False
    free_tier_api_calls_per_day: int = 100
    free_tier_symbols_limit: int = 10

    # ============================================================
    # COMPLIANCE & REGULATORY
    # ============================================================
    compliance_logging_enabled: bool = True
    compliance_log_retention_days: int = 2555  # 7 years
    finra_reporting_enabled: bool = False
    sec_reporting_enabled: bool = False
    gdpr_compliance_enabled: bool = True
    data_retention_days: int = 90

    # ============================================================
    # COMPUTED PROPERTIES
    # ============================================================
    @property
    def api_base_url(self) -> str:
        """Get the appropriate API base URL based on environment."""
        return self.api_base_url_sandbox if self.use_sandbox else self.api_base_url_production

    @property
    def oauth_base_url(self) -> str:
        """Get the appropriate OAuth URL based on environment."""
        return self.oauth_base_url_sandbox if self.use_sandbox else self.oauth_base_url_production

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"

    def validate_production_settings(self) -> None:
        """Validate critical settings for production environment."""
        if self.is_production:
            errors = []

            # Check security settings
            if "CHANGE-THIS" in self.secret_key:
                errors.append("secret_key must be changed for production")
            if "CHANGE-THIS" in self.encryption_key:
                errors.append("encryption_key must be changed for production")

            # Check database
            if "sqlite" in self.database_url.lower():
                errors.append("SQLite cannot be used in production")

            # Check sandbox mode
            if self.use_sandbox:
                errors.append("Sandbox mode should be disabled in production")

            # Check debug mode
            if self.debug:
                errors.append("Debug mode must be disabled in production")

            if errors:
                raise ValueError(f"Production configuration errors: {'; '.join(errors)}")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()
    settings.validate_production_settings()
    return settings