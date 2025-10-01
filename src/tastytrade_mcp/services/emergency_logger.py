"""Emergency action logging service for TastyTrade MCP.

This service provides database-backed logging for emergency actions,
circuit breakers, and audit trails. Operates in two modes:
- Simple Mode: Logs to application logger only
- Database Mode: Persists to PostgreSQL tables
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from enum import Enum
import os
import asyncpg

from tastytrade_mcp.config.settings import get_settings
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class EmergencyActionType(str, Enum):
    PANIC_BUTTON = "panic_button"
    EMERGENCY_EXIT = "emergency_exit"
    HALT_TRADING = "halt_trading"
    RESUME_TRADING = "resume_trading"
    EMERGENCY_STOP_ALL = "emergency_stop_all"
    CIRCUIT_BREAKER_TRIGGERED = "circuit_breaker_triggered"


class EmergencyActionStatus(str, Enum):
    INITIATED = "initiated"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class EmergencyLogger:
    """
    Logger for emergency actions with database-optional operation.

    Modes:
    - Simple: Logs to application logger only
    - Database: Persists to emergency_actions, circuit_breakers, and audit_log tables
    """

    def __init__(self, use_database: bool = False, db_url: Optional[str] = None):
        """
        Initialize emergency logger.

        Args:
            use_database: If True, use database persistence. If False, log only.
            db_url: PostgreSQL connection URL (optional, uses DATABASE_URL env var if not provided)
        """
        self.use_database = use_database
        self.db_pool: Optional[asyncpg.Pool] = None
        self.db_url = db_url or os.environ.get(
            'DATABASE_URL',
            'postgresql://localhost/tastytrade_mcp'
        )

        logger.info(f"EmergencyLogger initialized in {'DATABASE' if use_database else 'SIMPLE'} mode")

    async def connect(self):
        """Establish database connection pool if in database mode."""
        if not self.use_database:
            return

        try:
            self.db_pool = await asyncpg.create_pool(
                self.db_url,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            logger.info("Emergency logger database pool connected")
        except Exception as e:
            logger.error(f"Failed to connect emergency logger to database: {e}")
            raise

    async def disconnect(self):
        """Close database connection pool."""
        if self.db_pool:
            await self.db_pool.close()
            logger.info("Emergency logger database pool closed")

    async def log_emergency_action(
        self,
        user_id: str,
        action_type: EmergencyActionType,
        account_number: Optional[str] = None,
        reason: Optional[str] = None,
        confirmation_phrase: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Log initiation of an emergency action.

        Args:
            user_id: User initiating the action
            action_type: Type of emergency action
            account_number: Account affected (optional)
            reason: Reason for action
            confirmation_phrase: Confirmation phrase if provided
            metadata: Additional metadata

        Returns:
            Action ID (UUID string)
        """
        action_id = None

        if not self.use_database or not self.db_pool:
            logger.warning(
                f"Emergency action logged (SIMPLE MODE): "
                f"user={user_id}, type={action_type.value}, account={account_number}, "
                f"reason={reason}"
            )
            return "simple-mode-no-id"

        try:
            async with self.db_pool.acquire() as conn:
                action_id = await conn.fetchval(
                    """
                    INSERT INTO emergency_actions (
                        user_id, account_number, action_type, status,
                        reason, confirmation_phrase, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING id::text
                    """,
                    user_id,
                    account_number,
                    action_type.value,
                    EmergencyActionStatus.INITIATED.value,
                    reason,
                    confirmation_phrase,
                    metadata
                )

            logger.info(
                f"Emergency action logged: id={action_id}, "
                f"user={user_id}, type={action_type.value}"
            )
            return action_id

        except Exception as e:
            logger.error(f"Failed to log emergency action: {e}", exc_info=True)
            return "error-logging-action"

    async def update_emergency_action(
        self,
        action_id: str,
        status: EmergencyActionStatus,
        orders_cancelled: Optional[int] = None,
        positions_closed: Optional[int] = None,
        accounts_affected: Optional[int] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Update emergency action with results.

        Args:
            action_id: Action ID from log_emergency_action
            status: Final status
            orders_cancelled: Number of orders cancelled
            positions_closed: Number of positions closed
            accounts_affected: Number of accounts affected
            error_message: Error message if failed
            metadata: Additional metadata
        """
        if not self.use_database or not self.db_pool or action_id == "simple-mode-no-id":
            logger.info(
                f"Emergency action update (SIMPLE MODE): "
                f"status={status.value}, orders_cancelled={orders_cancelled}, "
                f"positions_closed={positions_closed}"
            )
            return

        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE emergency_actions
                    SET status = $2,
                        orders_cancelled = COALESCE($3, orders_cancelled),
                        positions_closed = COALESCE($4, positions_closed),
                        accounts_affected = COALESCE($5, accounts_affected),
                        error_message = COALESCE($6, error_message),
                        metadata = COALESCE($7, metadata)
                    WHERE id = $1::uuid
                    """,
                    action_id,
                    status.value,
                    orders_cancelled,
                    positions_closed,
                    accounts_affected,
                    error_message,
                    metadata
                )

            logger.info(f"Emergency action updated: id={action_id}, status={status.value}")

        except Exception as e:
            logger.error(f"Failed to update emergency action {action_id}: {e}", exc_info=True)

    async def log_audit_event(
        self,
        user_id: str,
        action: str,
        status: str,
        account_number: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        request_payload: Optional[Dict[str, Any]] = None,
        response_payload: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        duration_ms: Optional[int] = None
    ):
        """
        Log audit event for tracking all critical actions.

        Args:
            user_id: User performing action
            action: Action name
            status: Action status
            account_number: Account affected (optional)
            resource_type: Type of resource
            resource_id: Resource identifier
            request_payload: Request data
            response_payload: Response data
            error_message: Error if failed
            duration_ms: Action duration in milliseconds
        """
        if not self.use_database or not self.db_pool:
            logger.info(
                f"Audit event (SIMPLE MODE): user={user_id}, action={action}, "
                f"status={status}, resource={resource_type}/{resource_id}"
            )
            return

        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO audit_log (
                        user_id, account_number, action, resource_type, resource_id,
                        status, request_payload, response_payload, error_message, duration_ms
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    """,
                    user_id,
                    account_number,
                    action,
                    resource_type,
                    resource_id,
                    status,
                    request_payload,
                    response_payload,
                    error_message,
                    duration_ms
                )

            logger.debug(f"Audit event logged: user={user_id}, action={action}")

        except Exception as e:
            logger.error(f"Failed to log audit event: {e}", exc_info=True)

    async def get_emergency_history(
        self,
        user_id: str,
        account_number: Optional[str] = None,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get emergency action history for a user.

        Args:
            user_id: User ID to query
            account_number: Filter by account (optional)
            days: Number of days of history

        Returns:
            List of emergency actions
        """
        if not self.use_database or not self.db_pool:
            logger.warning("Emergency history requires database mode")
            return []

        try:
            since = datetime.utcnow() - timedelta(days=days)

            async with self.db_pool.acquire() as conn:
                if account_number:
                    rows = await conn.fetch(
                        """
                        SELECT id::text, action_type, status, reason,
                               orders_cancelled, positions_closed, accounts_affected,
                               error_message, initiated_at, completed_at, duration_ms
                        FROM emergency_actions
                        WHERE user_id = $1::uuid AND account_number = $2
                              AND initiated_at >= $3
                        ORDER BY initiated_at DESC
                        """,
                        user_id,
                        account_number,
                        since
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT id::text, action_type, status, reason,
                               orders_cancelled, positions_closed, accounts_affected,
                               error_message, initiated_at, completed_at, duration_ms
                        FROM emergency_actions
                        WHERE user_id = $1::uuid AND initiated_at >= $2
                        ORDER BY initiated_at DESC
                        """,
                        user_id,
                        since
                    )

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get emergency history: {e}", exc_info=True)
            return []

    async def check_circuit_breakers(
        self,
        user_id: str,
        account_number: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Check active circuit breakers for a user.

        Args:
            user_id: User ID to query
            account_number: Filter by account (optional)

        Returns:
            List of active circuit breakers
        """
        if not self.use_database or not self.db_pool:
            logger.warning("Circuit breakers require database mode")
            return []

        try:
            async with self.db_pool.acquire() as conn:
                if account_number:
                    rows = await conn.fetch(
                        """
                        SELECT id::text, name, trigger_type, threshold_value,
                               action_type, status, triggered_count, last_triggered_at
                        FROM circuit_breakers
                        WHERE user_id = $1::uuid AND account_number = $2
                              AND status = 'active'
                        ORDER BY created_at DESC
                        """,
                        user_id,
                        account_number
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT id::text, name, trigger_type, threshold_value,
                               action_type, status, triggered_count, last_triggered_at
                        FROM circuit_breakers
                        WHERE user_id = $1::uuid AND status = 'active'
                        ORDER BY created_at DESC
                        """,
                        user_id
                    )

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to check circuit breakers: {e}", exc_info=True)
            return []