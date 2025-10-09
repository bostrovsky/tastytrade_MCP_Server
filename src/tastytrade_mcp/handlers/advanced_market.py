"""Advanced market data handlers using SDK (sandbox mode).

These handlers use the TastyTrade SDK Session with username/password authentication.
For production (OAuth), see advanced_market_oauth.py
"""

from typing import Any
import mcp.types as types
from tastytrade_mcp.utils.logging import get_logger

# Import SDK-compatible implementations from market_data.py
from tastytrade_mcp.handlers.market_data import (
    handle_search_symbols,
    handle_get_quotes,
)

logger = get_logger(__name__)


async def handle_search_symbols_advanced(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Advanced symbol search using SDK.

    For now, delegates to basic search_symbols.
    TODO: Implement advanced filtering when needed.
    """
    logger.info("Advanced symbol search - using basic search for SDK mode")
    return await handle_search_symbols(arguments)


async def handle_get_options_chain(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Get options chain for a symbol using SDK.

    Uses TastyTrade SDK to fetch option chain data.
    """
    from tastytrade_mcp.services.simple_session import get_tastytrade_session
    from tastytrade.instruments import get_option_chain
    import json

    symbol = arguments.get("symbol", "").upper()

    if not symbol:
        return [types.TextContent(type="text", text="Error: Symbol is required")]

    try:
        session = get_tastytrade_session()

        # Get option chain
        chain = get_option_chain(session, symbol)

        if not chain or len(chain) == 0:
            return [types.TextContent(
                type="text",
                text=f"No options found for symbol: {symbol}"
            )]

        # Format response
        result = f"Options Chain for {symbol}:\n"
        result += f"Total options: {len(chain)}\n\n"

        # Group by expiration
        expirations = {}
        for option in chain[:50]:  # Limit to first 50
            exp_date = option.expiration_date
            if exp_date not in expirations:
                expirations[exp_date] = []
            expirations[exp_date].append(option)

        for exp_date in sorted(expirations.keys())[:5]:  # Show first 5 expirations
            result += f"\nExpiration: {exp_date}\n"
            options = expirations[exp_date]
            for opt in options[:10]:  # Limit to 10 per expiration
                result += f"  {opt.symbol} - Strike: {opt.strike_price}\n"

        return [types.TextContent(type="text", text=result)]

    except Exception as e:
        logger.error(f"Error fetching options chain: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error fetching options chain: {str(e)}"
        )]
