# TastyTrade MCP Server

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![PyPI version](https://img.shields.io/pypi/v/tastytrade-mcp.svg)](https://pypi.org/project/tastytrade-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Security: Audited](https://img.shields.io/badge/security-audited-green.svg)](docs/SECURITY.md)

A **Model Context Protocol (MCP) server** that connects your **TastyTrade trading account** to AI assistants like Claude Desktop and ChatGPT for conversational trading and portfolio management.

## 🌟 Features

### **Multi-LLM Support**
- 🤖 **Claude Desktop** - Native MCP integration via stdio
- 💬 **ChatGPT** - HTTP MCP Bridge for Developer Mode
- 🔄 **Universal Deployment** - Works on any cloud platform

### **Trading Capabilities**
- 📊 **Real-time Market Data** - Live quotes, options chains, market search
- 💼 **Portfolio Management** - Account positions, balances, order history
- 🔍 **Symbol Search** - Find stocks, options, and other instruments
- 🔒 **Security First** - Two-step trading confirmation, audit logging

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

#### **OAuth2 Setup for Database Mode**

To use database mode, you need to register an OAuth application with TastyTrade:

1. **Register OAuth Application**:
   - Visit https://developer.tastytrade.com
   - Create a new OAuth application for "TastyTrade MCP Server"
   - Set redirect URI to: `http://localhost:8000/callback`
   - Note your `CLIENT_ID` and `CLIENT_SECRET`

2. **Run Database Setup**:
   ```bash
   tastytrade-mcp setup --mode database
   ```
   - Enter your OAuth credentials when prompted
   - Browser will open automatically for TastyTrade authorization
   - Complete the OAuth flow to store encrypted tokens

3. **OAuth Flow Details**:
   - Uses production TastyTrade OAuth (sandbox OAuth not available)
   - Tokens are encrypted and stored in local SQLite database
   - Automatic token refresh for persistent sessions
   - Local callback server handles authorization automatically

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

If database mode OAuth setup fails:

1. **Browser doesn't open automatically**:
   - Copy the authorization URL from terminal and open manually
   - Ensure port 8000 is not blocked by firewall

2. **"Authorization failed" errors**:
   - Verify CLIENT_ID and CLIENT_SECRET are correct
   - Ensure redirect URI is exactly: `http://localhost:8000/callback`
   - Check that your OAuth app is configured for production (not sandbox)

3. **"Timeout" during OAuth flow**:
   - Complete authorization within 5 minutes
   - Check internet connection and TastyTrade server status
   - Try again with fresh OAuth credentials

4. **Database connection errors**:
   - Ensure write permissions in current directory
   - Try running `tastytrade-mcp clean` and setup again

### **WebSocket Connection Issues**

If real-time quotes aren't working:
- Check that markets are open
- Verify your internet connection
- Try reducing the duration parameter

## 📞 Support

- **Documentation**: Check the comprehensive guides in `docs/`
- **Issues**: Open GitHub issues for bugs or feature requests
- **Security**: See [SECURITY.md](docs/SECURITY.md) for security policies

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**🚨 Trading Disclaimer**: This software connects to real trading accounts with actual money. All trading involves financial risk. Users are responsible for their trading decisions and should understand the risks before using this tool.