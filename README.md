# TastyTrade MCP Server

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![PyPI version](https://img.shields.io/pypi/v/tastytrade-mcp.svg)](https://pypi.org/project/tastytrade-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Security: Audited](https://img.shields.io/badge/security-audited-green.svg)](docs/SECURITY.md)

A **Model Context Protocol (MCP) server** that connects your **TastyTrade trading account** to AI assistants like Claude Desktop and ChatGPT for conversational trading and portfolio management.

## 🌟 Features

### **✅ Production-Ready OAuth Trading** (v1.4.0)
- 🎉 **Full OAuth Support** - Production trading via OAuth2 authentication
- 📈 **All Instrument Types** - Stocks, Options, Futures, Crypto
- ✅ **Tested & Verified** - Real orders placed and cancelled successfully
- 🔄 **Universal Order Handler** - Same code works in sandbox and production

### **Multi-LLM Support**
- 🤖 **Claude Desktop** - Native MCP integration via stdio
- 💬 **ChatGPT** - HTTP MCP Bridge for Developer Mode
- 🔄 **Universal Deployment** - Works on any cloud platform

### **Trading Capabilities**
- 📊 **Real-time Market Data** - Live quotes, options chains, market search
- 💼 **Portfolio Management** - Account positions, balances, order history
- 🔍 **Symbol Search** - Find stocks, options, and other instruments
- 🔒 **Security First** - Two-step trading confirmation, audit logging
- 💰 **Full Order Support** - Limit, Market, Stop, Stop Limit orders

### **API Limitations**
> ⚠️ **Important**: The TastyTrade API has certain limitations. The following features are NOT available:
> - **Options Greeks** - Delta, Gamma, Theta, etc. are not provided by the API
> - **Historical Price Data** - No historical bars/candles endpoint available
> - **These tools have been removed** to avoid misleading functionality

### **Enterprise-Grade Security**
- 🔐 **Secure Authentication** - Your credentials never exposed to AI
- 📝 **Comprehensive Audit Trail** - All operations logged for compliance
- 🚫 **LLM Safety** - Trading requires explicit user confirmation

## 🚀 Quick Start

### **Prerequisites**
- TastyTrade trading account (production or sandbox)
- Python 3.8+ with pipx installed

### **Install & Setup**

```bash
# 1. Install the package
pipx install tastytrade-mcp

# 2. Run interactive setup
tastytrade-mcp setup

# 3. Start MCP server for Claude Desktop
tastytrade-mcp local
```

## ⚙️ Interactive Setup

The setup wizard will guide you through two authentication modes:

### **Simple Mode** (Recommended for new users)
- Username/password authentication
- Credentials stored in `.env` file
- Quick setup, no database required

### **Database Mode** (Advanced)
- OAuth2 with encrypted token storage
- Persistent authentication sessions
- SQLite database with encrypted tokens

#### **OAuth2 Personal Grant Setup for Database Mode**

Database mode uses OAuth2 personal grants for secure, encrypted token storage. This is perfect for personal use and self-hosted deployments.

**Step 1: Create Your OAuth Application**

1. Go to https://my.tastytrade.com
2. Navigate to: **Manage** → **My Profile** → **API** → **OAuth Applications**
3. Click **+ New OAuth Client**
4. Fill out the form:
   - **Client Name**: TastyTrade MCP Server (or your preferred name)
   - **Redirect URI**: `http://localhost:8000/callback` (required but not used for personal grants)
   - **Scopes**: Select `read` and `trade`
5. Click **Create**
6. **IMPORTANT**: Copy and securely save:
   - ✅ **Client ID**
   - ✅ **Client Secret** (shown only once!)

**Step 2: Generate Personal Grant**

1. On the OAuth Applications page, click **Manage** next to your application
2. Click **Create Grant**
3. **IMPORTANT**: Copy and securely save your **Refresh Token** (shown only once!)

**Step 3: Run Database Setup**

```bash
tastytrade-mcp setup --mode database
```

The setup wizard will prompt you for:
- Client ID (from Step 1)
- Client Secret (from Step 1)
- Refresh Token (from Step 2)

**Security Features**:
- ✅ Tokens encrypted and stored in local SQLite database
- ✅ Automatic access token refresh (every 15 minutes)
- ✅ Long-lived refresh token (never expires)
- ✅ No browser redirects - fully local setup

**Important Security Notes**:
- ⚠️ Keep Client Secret and Refresh Token safe - they're like passwords
- ⚠️ Never commit them to git or share publicly
- ⚠️ If compromised, delete the grant on my.tastytrade.com and create a new one
- ⚠️ Store them in environment variables or secure password manager

### **Setup Commands**

```bash
# Interactive setup wizard
tastytrade-mcp setup

# Simple mode setup
tastytrade-mcp setup --mode simple

# Database mode setup
tastytrade-mcp setup --mode database

# Check current status
tastytrade-mcp status

# Test your connection
tastytrade-mcp test

# Clean all config/database files
tastytrade-mcp clean
```

⚠️ **Important**: Use your **real TastyTrade account** credentials. This connects to your actual trading account.

### **Security Features**
- Credentials never exposed to AI assistants
- All tokens encrypted using Fernet symmetric encryption
- Two-step trading confirmation required
- Comprehensive audit logging

## 📱 Usage

### **For Claude Desktop**
```bash
tastytrade-mcp local
```
Then restart Claude Desktop and ask: *"Show my TastyTrade positions"*

### **Available CLI Commands**
```bash
tastytrade-mcp setup     # Interactive setup wizard
tastytrade-mcp local     # Start MCP server for Claude Desktop
tastytrade-mcp status    # Show configuration status
tastytrade-mcp test      # Test API connections
tastytrade-mcp clean     # Remove all config/database files
tastytrade-mcp --help    # Show all available commands
```

## 🌐 Claude Desktop Integration

Once you've run `tastytrade-mcp local`, the MCP server is ready for Claude Desktop:

1. **Restart Claude Desktop** - Close and reopen the application
2. **Verify Connection** - Claude should detect the MCP server automatically
3. **Start Trading** - Ask Claude about your positions, balances, or market data

### **Example Questions for Claude:**
```
"Show me my current TastyTrade positions"
"What's my account balance?"
"Get a quote for AAPL"
"Search for AI-related stocks"
"Show me my recent orders"
```

## 🛠️ Available Tools

### **Account Management**
- `accounts` - List all TastyTrade accounts
- `balances` - Get account balance information
- `positions` - View current positions

### **Market Data**
- `search_symbols` - Search stocks, ETFs, and other instruments
- `quote` - Get real-time market quotes
- `search_options` - Find options chains with filtering

### **Security & Audit**
- `audit_log` - View trading activity audit trail
- `security_status` - Check authentication and encryption status

## 📊 Management Commands

```bash
# Check current installation status
tastytrade-mcp status

# Test API connection and authentication
tastytrade-mcp test

# Remove all configuration and database files
tastytrade-mcp clean

# Show all available commands
tastytrade-mcp --help
```

## 🔧 Manual Installation (Advanced)

If you prefer manual setup:

```bash
git clone <repository-url>
cd Tasty_MCP
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Create .env file with your credentials
echo "TASTYTRADE_USERNAME=your_email@tastytrade.com" > .env
echo "TASTYTRADE_PASSWORD=your_password" >> .env
echo "TASTYTRADE_USE_PRODUCTION=true" >> .env

# Start server
python tastytrade_unified_server.py
```

## 🔒 Security Best Practices

1. **Never commit credentials** - Always use `.env` files
2. **Use production accounts** - Connect to your real TastyTrade account
3. **Monitor audit logs** - Review all trading activity
4. **Secure your deployment** - Use HTTPS and authentication tokens
5. **Regular updates** - Keep the server updated for security patches

## ⚠️ Important Disclaimers

- **Real Trading**: This connects to your actual TastyTrade account with real money
- **User Responsibility**: All trades require your explicit confirmation
- **No Financial Advice**: This is a technical tool, not investment advice
- **Security**: Keep your credentials secure and use HTTPS in production

## 📚 Usage Examples

### **Getting Portfolio Information**

```
"Show me my current positions and account balances"
"What are my open orders?"
"Get real-time quotes for NVDA, TSLA, and AAPL"
```

### **Real-Time Market Data**

```
"Get live quotes for my stock holdings"
"Stream real-time data for AAPL for 30 seconds"
"Show me the current market price of Bitcoin futures"
```

### **Options Trading Workflow**

```
# Step 1: Get your current option positions
"Show me all my current option positions"

# Step 2: Get real-time pricing (use exact symbols from positions)
"Get real-time quotes for these symbols: AMD  251121P00165000, NVDA  251121C00240000"

# Step 3: Analyze options strategies
"Analyze my AMD put spread strategy with current market conditions"
```

### **Streaming Options Quotes**

For real-time streaming of option quotes, use `stream_option_quotes`:

**Important**: This tool takes the underlying symbol and constructs the option symbols for you.

**Correct Usage:**
```json
{
  "symbol": "AAPL",
  "strikes": "230,235,240",
  "expiration": "2025-10-17",
  "option_type": "put"
}
```

**Parameters:**
- `symbol`: Underlying stock symbol (e.g., "AAPL")
- `strikes`: Comma-separated strike prices (e.g., "230,235,240")
- `expiration`: Expiration date in YYYY-MM-DD format
- `option_type`: Either "call" or "put"
- `duration`: How long to stream in seconds (default: 10)

**Example Questions:**
```
"Stream option quotes for AAPL puts at strikes 230, 235, and 240 expiring 2025-10-17"
"Get real-time quotes for SPY calls at 570, 575, 580 expiring next Friday"
```

**Note**: Do NOT pass full option symbols like "AAPL  251017P00230000" - the tool constructs these for you.

### **Market Research**

```
"Search for symbols related to artificial intelligence"
"Get the option chain for TSLA expiring in 30 days"
"Find options with delta around 0.30 for SPY"
```

### **Order Management**

```
"Create a buy order for 100 shares of AAPL at market price"
"Set up a stop-loss order for my NVDA position at $200"
"Show me the status of my pending orders"
```

### **Risk Management**

```
"Calculate the total value of my portfolio"
"Show me my unrealized P&L by position"
"What's my current buying power?"
```

## 🔧 Troubleshooting

### **Option Pricing Issues**

If option prices aren't showing:

1. **Get exact symbols first**: Use `get_positions` to see your actual option symbols
2. **Use correct format**: Option symbols look like `AAPL  251121C00150000` (not "AAPL $150 Call")
3. **Try direct quotes**: Use `get_realtime_quotes` with the exact symbols from your positions

### **Authentication Prompts**

If you keep getting "Allow" prompts:
- This is normal security behavior
- Select "Always Allow" to reduce frequency
- Each tool request requires permission for security

### **OAuth Setup Issues**

If database mode setup fails:

1. **"Invalid refresh token" errors**:
   - Verify you copied the refresh token correctly (no extra spaces)
   - Ensure the grant hasn't been deleted on my.tastytrade.com
   - Create a new grant if the refresh token was compromised

2. **"Invalid client credentials" errors**:
   - Verify CLIENT_ID and CLIENT_SECRET are correct
   - Ensure no extra spaces when copying credentials
   - Check that you're using credentials from the same OAuth app

3. **Database connection errors**:
   - Ensure write permissions in current directory
   - Try running `tastytrade-mcp clean` and setup again

4. **Token refresh failures**:
   - Check that CLIENT_SECRET is correctly set in .env file
   - Verify refresh token hasn't been revoked
   - Create a new personal grant if needed

### **WebSocket Connection Issues**

If real-time quotes aren't working:
- Check that markets are open
- Verify your internet connection
- Try reducing the duration parameter

## 🚀 Roadmap

### **Future: Full OAuth Flow (Trusted Partner)**

Currently, the MCP server uses **personal grant OAuth** for individual use. We're planning to become a **TastyTrade Trusted Partner** to enable full OAuth flow:

**What this means:**
- ✅ **One-click setup**: Users can simply click "Connect with TastyTrade"
- ✅ **No manual token management**: Browser-based OAuth consent screen
- ✅ **Multi-user support**: Deploy once, serve many users
- ✅ **Simpler onboarding**: No need to create OAuth apps manually

**Current Status**: Personal grant flow (perfect for open source self-hosted use)
**Future Goal**: Trusted partner approval for public deployments

If you're interested in helping or have feedback on this roadmap, please open a GitHub issue!

## 📚 Documentation

### **Setup Guides**
- 📦 [Installation](docs/setup/installation.md) - Complete installation guide
- 🖥️ [Claude Desktop Setup](docs/setup/claude-desktop.md) - MCP configuration
- 💬 [ChatGPT Integration](docs/setup/chatgpt.md) - OpenAI setup
- 🔐 [OAuth Database Mode](docs/setup/oauth-database.md) - Advanced auth

### **Deployment**
- 🚀 [Deployment Overview](docs/deployment/overview.md) - Cloud deployment guide

### **Development**
- 🏗️ [Architecture](docs/development/architecture.md) - System design
- 🤝 [Contributing](docs/development/contributing.md) - Development guide
- 📝 [Coding Standards](docs/development/coding-standards.md) - Code style

### **API Reference**
- 🔧 [Handlers](docs/api/handlers.md) - Available MCP tools

### **Supported Instrument Types**

| Type | Sandbox | Production | Notes |
|------|---------|------------|-------|
| **Equity (Stocks)** | ✅ | ✅ | Fully tested |
| **Equity Options** | ✅ | ✅ | Single & multi-leg |
| **Futures** | ❌ | ⚠️ | Requires special account |
| **Future Options** | ❌ | ⚠️ | Requires special account |
| **Cryptocurrency** | ❌ | ❌ | Not yet supported by API |

## 📞 Support

- **Documentation**: See [docs/](docs/) for comprehensive guides
- **Issues**: Open GitHub issues for bugs or feature requests
- **Security**: Review our security policies before deployment

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**🚨 Trading Disclaimer**: This software connects to real trading accounts with actual money. All trading involves financial risk. Users are responsible for their trading decisions and should understand the risks before using this tool.