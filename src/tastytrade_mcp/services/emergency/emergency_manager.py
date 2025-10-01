"""Main emergency management system orchestrator."""
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from .controller import EmergencyController
from .circuit_breakers import CircuitBreakerMonitor
from .models import (
    EmergencyResponse, CircuitBreakerEvent, EmergencyAlert,
    CircuitBreakerType, TradingHalt, EmergencyStatus
)


class EmergencyManager:
    """Main emergency management system that orchestrates all emergency services."""

    def __init__(self, session: AsyncSession):
        """Initialize emergency manager with all emergency services."""
        self.session = session
        self.controller = EmergencyController(session)
        self.circuit_breaker_monitor = CircuitBreakerMonitor(session)

    async def execute_panic_button(
        self,
        user_id: str,
        account_number: str,
        reason: str = "User panic button"
    ) -> EmergencyResponse:
        """Execute panic button with full emergency response."""
        response = await self.controller.panic_button(user_id, account_number, reason)

        # Check if we should also trigger circuit breakers
        if response.success:
            await self.circuit_breaker_monitor.check_circuit_breakers(account_number, force_check=True)

        return response

    async def execute_emergency_exit(
        self,
        user_id: str,
        account_number: str,
        reason: str = "Emergency position exit"
    ) -> EmergencyResponse:
        """Execute emergency exit with full monitoring."""
        response = await self.controller.emergency_exit_all_positions(user_id, account_number, reason)

        # Force circuit breaker check after emergency exit
        if response.success:
            await self.circuit_breaker_monitor.check_circuit_breakers(account_number, force_check=True)

        return response

    async def halt_trading_with_monitoring(
        self,
        user_id: str,
        account_number: str,
        reason: str,
        override_required: bool = True
    ) -> TradingHalt:
        """Halt trading with comprehensive monitoring."""
        halt = await self.controller.halt_trading(user_id, account_number, reason, override_required)

        # Generate alerts for the halt
        alerts = await self.circuit_breaker_monitor.generate_graduated_alerts(account_number)

        return halt

    async def check_emergency_conditions(
        self,
        account_number: str
    ) -> Dict[str, Any]:
        """Comprehensive check of all emergency conditions."""
        results = {
            "account_number": account_number,
            "timestamp": datetime.utcnow(),
            "trading_halted": False,
            "circuit_breakers_triggered": [],
            "emergency_alerts": [],
            "emergency_status": EmergencyStatus.NORMAL,
            "recommendations": []
        }

        # Check if trading is halted
        results["trading_halted"] = await self.controller.is_trading_halted(account_number)

        # Check circuit breakers
        triggered_breakers = await self.circuit_breaker_monitor.check_circuit_breakers(account_number)
        results["circuit_breakers_triggered"] = [
            {
                "event_id": event.event_id,
                "breaker_type": event.trigger_reason,
                "trigger_value": float(event.trigger_value),
                "threshold": float(event.threshold_value),
                "triggered_at": event.triggered_at.isoformat(),
                "actions_taken": event.actions_taken
            }
            for event in triggered_breakers
        ]

        # Generate graduated alerts
        alerts = await self.circuit_breaker_monitor.generate_graduated_alerts(account_number)
        results["emergency_alerts"] = [
            {
                "alert_id": alert.alert_id,
                "level": alert.alert_level.value,
                "type": alert.alert_type,
                "message": alert.message,
                "current_value": float(alert.current_value),
                "threshold": float(alert.threshold_value) if alert.threshold_value else None,
                "created_at": alert.created_at.isoformat()
            }
            for alert in alerts
        ]

        # Determine overall emergency status
        if results["trading_halted"]:
            results["emergency_status"] = EmergencyStatus.TRADING_HALTED
        elif triggered_breakers:
            results["emergency_status"] = EmergencyStatus.CIRCUIT_BREAKER_TRIGGERED
        elif any(alert.alert_level.value in ["critical", "emergency"] for alert in alerts):
            results["emergency_status"] = EmergencyStatus.WARNING
        else:
            results["emergency_status"] = EmergencyStatus.NORMAL

        # Generate recommendations
        results["recommendations"] = self._generate_recommendations(results)

        return results

    async def create_circuit_breaker(
        self,
        account_number: str,
        breaker_type: str,
        threshold_percentage: float,
        created_by: str,
        auto_trigger: bool = True
    ) -> Dict[str, Any]:
        """Create a new circuit breaker."""
        try:
            breaker_type_enum = CircuitBreakerType(breaker_type)
        except ValueError:
            raise ValueError(f"Invalid circuit breaker type: {breaker_type}")

        breaker = await self.circuit_breaker_monitor.create_circuit_breaker(
            account_number=account_number,
            breaker_type=breaker_type_enum,
            threshold_percentage=threshold_percentage / 100,  # Convert percentage to decimal
            created_by=created_by,
            auto_trigger=auto_trigger
        )

        return {
            "breaker_id": breaker.breaker_id,
            "breaker_type": breaker.breaker_type.value,
            "threshold_percentage": float(breaker.threshold_percentage * 100),
            "auto_trigger": breaker.auto_trigger,
            "created_at": breaker.created_at.isoformat(),
            "status": "active"
        }

    async def resume_trading_with_checks(
        self,
        user_id: str,
        account_number: str,
        halt_id: str,
        justification: str
    ) -> Dict[str, Any]:
        """Resume trading with safety checks."""
        # Check current emergency conditions first
        emergency_status = await self.check_emergency_conditions(account_number)

        # Don't allow resume if there are critical conditions
        critical_alerts = [
            alert for alert in emergency_status["emergency_alerts"]
            if alert["level"] in ["critical", "emergency"]
        ]

        if critical_alerts and not justification.lower().startswith("override"):
            return {
                "success": False,
                "message": "Cannot resume trading: Critical emergency conditions still present",
                "critical_alerts": critical_alerts,
                "override_required": True
            }

        # Attempt to resume trading
        success = await self.controller.resume_trading(user_id, account_number, halt_id, justification)

        return {
            "success": success,
            "message": "Trading resumed successfully" if success else "Failed to resume trading",
            "resumed_at": datetime.utcnow().isoformat() if success else None,
            "resumed_by": user_id if success else None
        }

    async def get_emergency_history(
        self,
        account_number: str,
        hours: int = 24
    ) -> Dict[str, Any]:
        """Get emergency action history for an account."""
        # Mock implementation - in real system, query from database
        return {
            "account_number": account_number,
            "lookback_hours": hours,
            "emergency_actions": [
                {
                    "action_id": "action1",
                    "action_type": "panic_button",
                    "executed_at": "2024-01-15T10:30:00Z",
                    "executed_by": "user123",
                    "reason": "Market volatility",
                    "orders_affected": 5,
                    "success": True
                }
            ],
            "circuit_breaker_events": [
                {
                    "event_id": "event1",
                    "breaker_type": "daily_loss_limit",
                    "triggered_at": "2024-01-15T14:20:00Z",
                    "trigger_value": 0.12,
                    "threshold": 0.10,
                    "actions_taken": ["Cancelled 3 orders", "Trading halted"]
                }
            ],
            "total_emergency_actions": 1,
            "total_circuit_breaker_triggers": 1
        }

    def _generate_recommendations(self, emergency_status: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on emergency status."""
        recommendations = []

        if emergency_status["trading_halted"]:
            recommendations.append("Review halt reason and contact support before resuming trading")

        if emergency_status["circuit_breakers_triggered"]:
            recommendations.append("Investigate circuit breaker triggers and adjust risk parameters")

        critical_alerts = [
            alert for alert in emergency_status["emergency_alerts"]
            if alert["level"] in ["critical", "emergency"]
        ]

        if critical_alerts:
            recommendations.append("Address critical alerts before continuing trading activities")

        if emergency_status["emergency_status"] == EmergencyStatus.WARNING:
            recommendations.append("Consider reducing position sizes and reviewing risk exposure")

        if not recommendations:
            recommendations.append("All emergency systems normal - continue monitoring")

        return recommendations

    # Convenience methods for common emergency scenarios
    async def emergency_stop_all(
        self,
        user_id: str,
        account_number: str,
        reason: str = "Complete emergency stop"
    ) -> Dict[str, Any]:
        """Complete emergency stop: cancel orders, exit positions, and halt trading."""
        results = {
            "panic_response": None,
            "exit_response": None,
            "trading_halt": None,
            "success": True,
            "errors": []
        }

        try:
            # Execute panic button
            results["panic_response"] = await self.execute_panic_button(user_id, account_number, reason)
            if not results["panic_response"].success:
                results["errors"].append("Panic button failed")

            # Emergency exit all positions
            results["exit_response"] = await self.execute_emergency_exit(user_id, account_number, reason)
            if not results["exit_response"].success:
                results["errors"].append("Emergency exit failed")

            # Halt trading
            results["trading_halt"] = await self.halt_trading_with_monitoring(
                user_id, account_number, reason, override_required=True
            )

        except Exception as e:
            results["errors"].append(f"Emergency stop failed: {str(e)}")
            results["success"] = False

        results["success"] = len(results["errors"]) == 0

        return results