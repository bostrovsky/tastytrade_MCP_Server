"""MCP tool for risk validation."""
from typing import Dict, Any, Optional
from uuid import UUID

from tastytrade_mcp.db.session import get_session_context
from tastytrade_mcp.services.risk import RiskValidator
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)


async def validate_trade_risk(
    trade_request: Dict[str, Any],
    account_number: str,
    user_id: UUID,
) -> Dict[str, Any]:
    """
    Validate a trade against risk rules before execution.

    Args:
        trade_request: The trade request to validate
        account_number: The account number to validate against
        user_id: The user ID making the request

    Returns:
        Dict containing validation result
    """
    async with get_session_context() as session:
        validator = RiskValidator(session)

        result = await validator.validate_trade(
            trade_request,
            account_number,
            user_id
        )

        return result.to_dict()


async def get_account_risk_status(
    account_number: str,
    user_id: Optional[UUID] = None
) -> Dict[str, Any]:
    """
    Get current risk status for an account.

    Args:
        account_number: The account to check
        user_id: Optional user ID for permission check

    Returns:
        Dict containing risk status and metrics
    """
    async with get_session_context() as session:
        from tastytrade_mcp.services.risk import RiskMonitor

        monitor = RiskMonitor(session)
        status = await monitor.get_account_risk_status(account_number)

        return status


async def check_risk_rule(
    rule_type: str,
    account_number: str,
    parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Check a specific risk rule.

    Args:
        rule_type: Type of risk rule to check
        account_number: Account to check against
        parameters: Parameters for the risk check

    Returns:
        Dict containing check result
    """
    async with get_session_context() as session:
        validator = RiskValidator(session)

        # Get account limits
        from tastytrade_mcp.models.risk import AccountRiskLimits
        from sqlalchemy import select

        stmt = select(AccountRiskLimits).where(
            AccountRiskLimits.account_number == account_number
        )
        result = await session.execute(stmt)
        limits = result.scalar_one_or_none()

        if not limits:
            return {
                "passed": True,
                "message": "No risk limits configured for account"
            }

        # Run specific check based on rule type
        from tastytrade_mcp.services.risk import RuleType

        if rule_type == RuleType.POSITION_LIMIT.value:
            violations = await validator.check_position_limits(parameters, account_number, limits)
        elif rule_type == RuleType.CONCENTRATION.value:
            violations = await validator.check_concentration_risk(parameters, account_number, limits)
        elif rule_type == RuleType.BUYING_POWER.value:
            violations = await validator.check_buying_power(parameters, account_number, limits)
        else:
            return {
                "passed": False,
                "message": f"Unknown rule type: {rule_type}"
            }

        return {
            "passed": len(violations) == 0,
            "violations": [v.to_dict() for v in violations] if violations else []
        }


async def override_risk_validation(
    validation_id: UUID,
    override_type: str,
    reason: str,
    approved_by: UUID,
    expires_at: Optional[str] = None
) -> Dict[str, Any]:
    """
    Override a risk validation.

    Args:
        validation_id: ID of the validation to override
        override_type: Type of override (manual, emergency, system, admin)
        reason: Reason for the override
        approved_by: User ID approving the override
        expires_at: Optional expiration time for the override

    Returns:
        Dict containing override result
    """
    async with get_session_context() as session:
        from tastytrade_mcp.models.risk import RiskOverride, RiskValidation, OverrideType
        from sqlalchemy import select, update
        from datetime import datetime

        # Get the validation
        stmt = select(RiskValidation).where(RiskValidation.id == validation_id)
        result = await session.execute(stmt)
        validation = result.scalar_one_or_none()

        if not validation:
            return {
                "success": False,
                "message": "Validation not found"
            }

        # Create override record
        override = RiskOverride(
            validation_id=validation_id,
            override_type=OverrideType(override_type),
            override_reason=reason,
            approved_by=approved_by,
            expires_at=datetime.fromisoformat(expires_at) if expires_at else None
        )
        session.add(override)

        # Update validation status
        stmt = (
            update(RiskValidation)
            .where(RiskValidation.id == validation_id)
            .values(status="overridden")
        )
        await session.execute(stmt)

        await session.commit()

        return {
            "success": True,
            "override_id": str(override.id),
            "message": "Risk validation overridden"
        }