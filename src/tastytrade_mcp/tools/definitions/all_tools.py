"""All tool definitions combined."""
from typing import Any

import mcp.types as types

from .accounts import get_account_tools
from .emergency import get_emergency_tools
from .health import get_health_tools
from .market_data import get_market_data_tools, get_streaming_tools
from .options import get_options_tools
from .positions import get_position_management_tools
from .scanning import get_scanning_tools
from .trading import get_trading_tools


def get_all_tools() -> list[types.Tool]:
    """Get all tool definitions combined."""
    all_tools = []

    # Add all tool categories
    all_tools.extend(get_health_tools())
    all_tools.extend(get_account_tools())
    all_tools.extend(get_market_data_tools())
    all_tools.extend(get_streaming_tools())
    all_tools.extend(get_trading_tools())
    all_tools.extend(get_options_tools())
    all_tools.extend(get_position_management_tools())
    all_tools.extend(get_emergency_tools())
    all_tools.extend(get_scanning_tools())

    return all_tools