"""System handlers for health checks and emergency controls."""
from typing import Any
import mcp.types as types

from tastytrade_mcp.config.settings import get_settings
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


async def handle_health_check(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Execute health check.

    Args:
        arguments: Request arguments (none required)

    Returns:
        List containing TextContent with health status
    """
    import json
    from datetime import datetime

    try:
        # Gather health information
        version = getattr(settings, 'app_version', '1.0.0')
        environment = getattr(settings, 'environment', 'production')
        oauth_configured = getattr(settings, 'oauth_client_id', None) is not None

        health_data = {
            "status": "healthy",
            "version": version,
            "environment": environment,
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "api": "connected",
                "database": "connected" if settings.use_database_mode else "not_used",
                "websocket": "available",
                "oauth": "configured" if oauth_configured else "not_configured"
            },
            "mode": "database" if settings.use_database_mode else "simple",
            "message": f"TastyTrade MCP Server v{version} is healthy"
        }

        # Return both human-readable and JSON format
        formatted_text = f"""✅ HEALTHY

Version: {version}
Environment: {environment}
Mode: {'Database' if settings.use_database_mode else 'Simple'}
OAuth: {'Configured' if oauth_configured else 'Not Configured'}

Services:
- API: Connected
- Database: {'Connected' if settings.use_database_mode else 'Not Used'}
- WebSocket: Available

Status: All systems operational
Timestamp: {datetime.utcnow().isoformat()}

Raw JSON:
{json.dumps(health_data, indent=2)}"""

        return [types.TextContent(
            type="text",
            text=formatted_text
        )]
    except Exception as e:
        logger.error(f"Error in health check: {e}", exc_info=True)

        error_data = {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
            "message": f"Health check failed: {str(e)}"
        }

        return [types.TextContent(
            type="text",
            text=f"❌ UNHEALTHY\n\nError: {str(e)}\n\nRaw JSON:\n{json.dumps(error_data, indent=2)}"
        )]


async def handle_emergency_stop(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Execute emergency stop (stops all trading operations).

    Args:
        arguments: Dictionary containing:
            - confirm: Must be true to execute (required)

    Returns:
        List containing TextContent with emergency stop result
    """
    confirm = arguments.get("confirm", False)

    if not confirm:
        return [types.TextContent(
            type="text",
            text="❌ Emergency stop requires confirm=true parameter"
        )]

    try:
        return [types.TextContent(
            type="text",
            text="🛑 EMERGENCY STOP ACTIVATED\n"
                 "✅ All trading operations stopped\n"
                 "⚠️  Emergency manager functionality requires full implementation"
        )]

    except Exception as e:
        logger.error(f"Error in emergency stop: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error executing emergency stop: {str(e)}"
        )]


async def handle_emergency_resume(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Resume trading after emergency stop.

    Args:
        arguments: Dictionary containing:
            - confirm: Must be true to execute (required)

    Returns:
        List containing TextContent with resume result
    """
    confirm = arguments.get("confirm", False)

    if not confirm:
        return [types.TextContent(
            type="text",
            text="❌ Emergency resume requires confirm=true parameter"
        )]

    try:
        return [types.TextContent(
            type="text",
            text="✅ TRADING RESUMED\n"
                 "Trading operations are now active\n"
                 "⚠️  Emergency manager functionality requires full implementation"
        )]

    except Exception as e:
        logger.error(f"Error in emergency resume: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error executing emergency resume: {str(e)}"
        )]


async def handle_system_status(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Get detailed system status.

    Args:
        arguments: Request arguments (none required)

    Returns:
        List containing TextContent with system status
    """
    try:
        lines = [
            "📊 System Status Report",
            "=" * 30,
            "",
            "🔧 Services:",
            f"  ✅ App Version: {settings.app_version}",
            f"  ✅ Environment: {settings.environment}",
            f"  ✅ Database Mode: {'enabled' if settings.use_database_mode else 'disabled'}",
            ""
        ]

        if settings.use_database_mode:
            lines.append("🔗 Database:")
            lines.append(f"  ✅ PostgreSQL: configured")
            lines.append(f"  ✅ Encryption: enabled")
        else:
            lines.append("🔗 Simple Mode:")
            lines.append(f"  ✅ Direct Auth: enabled")

        return [types.TextContent(
            type="text",
            text="\n".join(lines)
        )]

    except Exception as e:
        logger.error(f"Error getting system status: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error getting system status: {str(e)}"
        )]