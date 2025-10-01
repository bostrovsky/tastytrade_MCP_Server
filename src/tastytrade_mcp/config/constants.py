"""Application-wide constants.

This file contains constants that are not configuration values
but rather fixed values used throughout the application.
"""
from enum import Enum


# ============================================================
# TRADING CONSTANTS
# ============================================================

class OrderConfirmation:
    """Order confirmation constants."""
    CONFIRM_CODE = "CONFIRM"
    CONFIRM_PATTERN = "^CONFIRM$"
    CONFIRM_MESSAGE = "Type 'CONFIRM' to execute this order"
    INVALID_MESSAGE = "Invalid confirmation code. Type 'CONFIRM' to execute"


class MarketStatus:
    """Market status messages."""
    PRE_MARKET = "pre-market"
    REGULAR = "regular"
    AFTER_HOURS = "after-hours"
    CLOSED = "closed"


class TradingDays:
    """Trading day constants."""
    BUSINESS_DAYS_PER_YEAR = 252
    CALENDAR_DAYS_PER_YEAR = 365
    TRADING_HOURS_PER_DAY = 6.5  # 9:30 AM - 4:00 PM ET


# ============================================================
# ERROR MESSAGES
# ============================================================

class ErrorMessages:
    """Standardized error messages."""

    # Authentication
    AUTH_INVALID_CREDENTIALS = "Invalid credentials provided"
    AUTH_TOKEN_EXPIRED = "Authentication token has expired"
    AUTH_UNAUTHORIZED = "Unauthorized access"
    AUTH_SESSION_EXPIRED = "Session has expired. Please log in again"

    # Order Management
    ORDER_NOT_FOUND = "Order not found"
    ORDER_ALREADY_FILLED = "Order has already been filled"
    ORDER_ALREADY_CANCELLED = "Order has already been cancelled"
    ORDER_PREVIEW_EXPIRED = "Order preview has expired"
    ORDER_INVALID_QUANTITY = "Invalid order quantity"
    ORDER_INVALID_PRICE = "Invalid order price"
    ORDER_MARKET_CLOSED = "Market is closed"

    # Risk Management
    RISK_POSITION_LIMIT_EXCEEDED = "Position size exceeds maximum allowed"
    RISK_VALUE_LIMIT_EXCEEDED = "Position value exceeds maximum allowed"
    RISK_CONCENTRATION_EXCEEDED = "Portfolio concentration limit exceeded"
    RISK_BUYING_POWER_INSUFFICIENT = "Insufficient buying power"
    RISK_DAILY_LOSS_EXCEEDED = "Daily loss limit exceeded"
    RISK_PDT_VIOLATION = "Pattern Day Trader rule violation"

    # WebSocket
    WS_CONNECTION_FAILED = "WebSocket connection failed"
    WS_SUBSCRIPTION_LIMIT = "WebSocket subscription limit exceeded"
    WS_RATE_LIMIT = "WebSocket rate limit exceeded"

    # General
    INVALID_REQUEST = "Invalid request parameters"
    INTERNAL_ERROR = "An internal error occurred"
    SERVICE_UNAVAILABLE = "Service temporarily unavailable"
    RATE_LIMIT_EXCEEDED = "Rate limit exceeded. Please try again later"


# ============================================================
# API RESPONSE CODES
# ============================================================

class ResponseCodes:
    """API response codes."""

    # Success
    SUCCESS = "SUCCESS"
    CREATED = "CREATED"
    ACCEPTED = "ACCEPTED"

    # Client Errors
    BAD_REQUEST = "BAD_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    VALIDATION_ERROR = "VALIDATION_ERROR"

    # Server Errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"

    # Business Logic Errors
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    RISK_CHECK_FAILED = "RISK_CHECK_FAILED"
    MARKET_CLOSED = "MARKET_CLOSED"
    SYMBOL_NOT_TRADEABLE = "SYMBOL_NOT_TRADEABLE"


# ============================================================
# NUMERIC CONSTANTS
# ============================================================

class NumericConstants:
    """Numeric constants used in calculations."""

    # Percentages
    PERCENT_MULTIPLIER = 100.0
    BASIS_POINT = 0.0001  # 1 basis point = 0.01%

    # Price Precision
    PRICE_DECIMAL_PLACES = 4
    QUANTITY_DECIMAL_PLACES = 0
    PERCENTAGE_DECIMAL_PLACES = 2

    # Greeks
    DELTA_MIN = -1.0
    DELTA_MAX = 1.0
    GAMMA_MIN = 0.0
    VEGA_PRECISION = 0.01
    THETA_PRECISION = 0.01

    # Risk Metrics
    VAR_CONFIDENCE_LEVEL = 0.95  # 95% confidence
    SHARPE_RATIO_RISK_FREE = 0.02  # 2% annual

    # Limits
    MAX_SYMBOL_LENGTH = 12
    MAX_ORDER_COMMENT_LENGTH = 255
    MAX_RETRY_ATTEMPTS = 3


# ============================================================
# TIME CONSTANTS
# ============================================================

class TimeConstants:
    """Time-related constants."""

    # Milliseconds
    MS_PER_SECOND = 1000
    MS_PER_MINUTE = 60000
    MS_PER_HOUR = 3600000

    # Seconds
    SECONDS_PER_MINUTE = 60
    SECONDS_PER_HOUR = 3600
    SECONDS_PER_DAY = 86400

    # Trading Time
    PRE_MARKET_HOURS = 5.5  # 4:00 AM - 9:30 AM ET
    REGULAR_HOURS = 6.5  # 9:30 AM - 4:00 PM ET
    AFTER_HOURS = 4.0  # 4:00 PM - 8:00 PM ET

    # Cache Defaults
    DEFAULT_CACHE_TTL = 300  # 5 minutes

    # Timeouts
    DEFAULT_TIMEOUT = 30.0
    WEBSOCKET_TIMEOUT = 60.0
    DATABASE_TIMEOUT = 10.0


# ============================================================
# REGEX PATTERNS
# ============================================================

class RegexPatterns:
    """Common regex patterns."""

    # Financial
    SYMBOL = r"^[A-Z]{1,12}$"
    OPTION_SYMBOL = r"^[A-Z]{1,6}\d{6}[CP]\d{8}$"
    USD_AMOUNT = r"^\$?\d+(\.\d{2})?$"

    # Identifiers
    UUID = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    ACCOUNT_NUMBER = r"^[A-Z0-9]{6,12}$"

    # Validation
    EMAIL = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    PHONE_US = r"^\+?1?\d{10}$"


# ============================================================
# STATUS ENUMS
# ============================================================

class SystemStatus(Enum):
    """System status values."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    MAINTENANCE = "maintenance"


class ConnectionStatus(Enum):
    """Connection status values."""
    CONNECTED = "connected"
    CONNECTING = "connecting"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


# ============================================================
# METADATA
# ============================================================

class Metadata:
    """Application metadata."""

    # API Version
    API_VERSION = "v1"
    API_PREFIX = "/api/v1"

    # Headers
    API_KEY_HEADER = "X-API-Key"
    AUTH_HEADER = "Authorization"
    CONTENT_TYPE = "application/json"

    # User Agent
    USER_AGENT = "TastyTradeMCP/1.0"

    # Pagination
    DEFAULT_PAGE_SIZE = 50
    MAX_PAGE_SIZE = 500

    # Sorting
    DEFAULT_SORT_ORDER = "desc"
    DEFAULT_SORT_FIELD = "created_at"