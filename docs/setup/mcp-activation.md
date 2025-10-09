# TastyTrade MCP Server Activation Guide

## Status: ✅ MCP Server Ready!

The TastyTrade MCP server is now fully operational and ready for client connections.

## Quick Start

### 1. Run the MCP Server

```bash
# Activate virtual environment and run server
source .venv/bin/activate
python scripts/run_mcp_server.py
```

Or directly:
```bash
.venv/bin/python scripts/run_mcp_server.py
```

### 2. Available MCP Tools (20 Total)

#### Account & Portfolio Management
- `health_check` - Check server status
- `get_accounts` - List linked TastyTrade accounts
- `get_positions` - View current positions
- `get_balances` - Check account balances

#### Market Data
- `search_symbols` - Search trading instruments
- `get_quotes` - Real-time quotes
- `get_historical_data` - Historical price data
- `get_options_chain` - Options chain data

#### WebSocket Streaming
- `subscribe_market_stream` - Real-time market data
- `unsubscribe_market_stream` - Stop streaming
- `get_stream_status` - Check stream status
- `get_stream_data` - Get latest stream data
- `get_stream_metrics` - Streaming metrics
- `shutdown_streams` - Close all streams

#### Trading Operations
- `create_equity_order` - Create stock order preview
- `create_options_order` - Create options order preview
- `confirm_order` - Execute order from preview
- `list_orders` - View order history
- `cancel_order` - Cancel pending order

#### Analysis
- `analyze_options_strategy` - Analyze options strategies with Greeks

## Integration with Claude Desktop

### Option 1: Manual Configuration

Add this to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "tastytrade": {
      "command": "/Volumes/Working_6/Tasty_MCP/.venv/bin/python3",
      "args": [
        "/Volumes/Working_6/Tasty_MCP/scripts/run_mcp_server.py"
      ],
      "env": {
        "PYTHONPATH": "/Volumes/Working_6/Tasty_MCP/src"
      }
    }
  }
}
```

### Option 2: Use Generated Config

A configuration file has been generated at:
```
/Volumes/Working_6/Tasty_MCP/mcp_config.json
```

## Testing the Server

### 1. Test Tools Directly
```bash
source .venv/bin/activate
python scripts/test_mcp_client.py
```

### 2. Test with MCP Client Library
```python
import asyncio
from mcp import ClientSession, StdioServerParameters
import subprocess

async def test_connection():
    server_params = StdioServerParameters(
        command=".venv/bin/python",
        args=["scripts/run_mcp_server.py"]
    )

    async with ClientSession(server_params) as session:
        # Initialize connection
        await session.initialize()

        # List available tools
        tools = await session.list_tools()
        print(f"Found {len(tools)} tools")

        # Test health check
        result = await session.call_tool("health_check", {})
        print(f"Health: {result}")
```

## Environment Configuration

The server uses the `.env` file for configuration. Key settings:

- `TASTYTRADE_USE_SANDBOX=true` - Use sandbox for testing
- `TASTYTRADE_ENVIRONMENT=development` - Environment mode
- `TASTYTRADE_DATABASE_URL` - Database connection (SQLite for dev)

## Architecture Overview

```
MCP Client (Claude/LLM)
    ↓ stdio/JSON-RPC
TastyTrade MCP Server
    ├── MCP Tools Layer (20 tools)
    ├── Service Layer
    │   ├── TastyTradeService (API integration)
    │   ├── OptionsOrderService (Options trading)
    │   ├── WebSocketManager (Real-time data)
    │   └── EncryptionService (Security)
    ├── Database Layer (SQLAlchemy + AsyncPG)
    └── TastyTrade API (OAuth2)
```

## Security Features

- ✅ OAuth2 token management with auto-refresh
- ✅ Token encryption at rest
- ✅ Sandbox/production isolation
- ✅ Two-step order confirmation flow
- ✅ Risk validation for trades

## Current Status

### ✅ Completed
- MCP server implementation
- 20 functional tools
- OAuth2 authentication
- Database integration
- Options trading with Greeks
- WebSocket streaming support
- Risk validation system

### 🚧 Pending
- Rate limiting implementation
- Position size limits
- Daily loss limits
- Audit logging
- Backtesting integration
- Production deployment

## Troubleshooting

### Server doesn't start
```bash
# Check dependencies
source .venv/bin/activate
pip list | grep mcp

# Should show: mcp 1.14.0 or higher
```

### Missing dependencies
```bash
source .venv/bin/activate
pip install mcp numpy scipy
```

### Database issues
```bash
# Server auto-creates SQLite database at:
# data/tastytrade_mcp.db
```

### Environment issues
```bash
# Ensure .env exists
cp .env.template .env
# Edit .env with your settings
```

## Next Steps

1. **Connect with Claude Desktop**: Use the configuration above
2. **Test Trading Flow**: Try the sandbox trading tools
3. **Implement Guardrails**: Add missing safety features
4. **Add Tests**: Increase test coverage
5. **Production Ready**: Harden for production use

## Support

For issues or questions:
- Check logs in `api.log`
- Review test output: `python scripts/test_mcp_client.py`
- Server debug mode is enabled by default in development

---

**Server Status**: ✅ Ready for MCP client connections
**Tools Available**: 20
**Environment**: Development (Sandbox)
**Version**: 0.1.0