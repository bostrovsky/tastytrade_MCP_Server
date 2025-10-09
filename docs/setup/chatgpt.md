# ChatGPT MCP Integration Guide
## TastyTrade MCP Server

This guide explains how to connect the TastyTrade MCP Server to ChatGPT using Developer Mode.

## 🔧 **Quick Setup**

### 1. **Deploy to Railway (Recommended)**
Your TastyTrade MCP server now includes unified support for both local MCP and ChatGPT HTTP modes.

**Railway URL:** `https://your-app.railway.app` (replace with your actual Railway URL)

### 2. **Local Testing**
For development and testing, use the unified server in ChatGPT mode:

```bash
# Start the unified server in ChatGPT MCP mode
source .venv/bin/activate
export TASTYTRADE_SANDBOX_USERNAME="your_email@example.com"
export TASTYTRADE_SANDBOX_PASSWORD="your_password"
export TASTYTRADE_USE_PRODUCTION="false"
export CHATGPT_MCP_TOKEN="your-secure-token"
PORT=8086 python tastytrade_unified_server.py
```

**Note:** The unified server automatically detects the environment:
- With `CHATGPT_MCP_TOKEN` set: Runs as ChatGPT HTTP MCP Bridge
- On Railway (with `PORT` but no `CHATGPT_MCP_TOKEN`): Runs as standard HTTP API
- Local development: Runs as stdio MCP server for Claude Desktop

## 📋 **ChatGPT Configuration**

### 1. **Enable Developer Mode**
- Open ChatGPT → Settings → Developer Mode → Enable
- Go to left sidebar → Connectors → Create

### 2. **Add TastyTrade Connector**
Fill in the connector dialog:

```
Name: TastyTrade Trading
Server URL: https://your-railway-app.railway.app/mcp
Auth Type: Bearer Token
Token: your-secure-token
```

### 3. **Verify Connection**
ChatGPT will validate your server. You should see:
- ✅ "Connected successfully"
- Available tools in the connector settings

## 🛠️ **Available Tools**

The ChatGPT integration provides these MCP tools:

### **Core Tools (Required by ChatGPT)**
- `search_symbols` - Search for trading symbols and instruments
- `fetch_accounts` - Get user trading accounts
- `fetch_positions` - Get current positions for an account
- `fetch_balances` - Get account balance information
- `fetch_market_data` - Get real-time market data for symbols

### **Advanced Tools**
- `search_options` - Search options chains for underlying symbols

## 📊 **Usage Examples**

### **Basic Account Information**
```
User: "Show me my TastyTrade accounts and current balances"
ChatGPT: [Calls fetch_accounts and fetch_balances tools]
```

### **Market Data**
```
User: "Get current market data for AAPL and TSLA"
ChatGPT: [Calls fetch_market_data for both symbols]
```

### **Portfolio Analysis**
```
User: "Analyze my current positions and suggest portfolio adjustments"
ChatGPT: [Calls fetch_positions, fetch_balances, fetch_market_data]
```

### **Options Research**
```
User: "Find AAPL call options expiring next month with strikes near current price"
ChatGPT: [Calls search_options with appropriate parameters]
```

## 🔐 **Security Configuration**

### **Production Setup**
1. **Set secure authentication token:**
   ```bash
   export CHATGPT_MCP_TOKEN="your-very-secure-random-token"
   ```

2. **Use HTTPS only** (Railway provides this automatically)

3. **Restrict CORS if needed** (currently allows all origins for development)

### **Environment Variables**
Required environment variables for Railway deployment:

```bash
# TastyTrade Authentication
TASTYTRADE_SANDBOX_USERNAME=your_email@example.com
TASTYTRADE_SANDBOX_PASSWORD=your_password
TASTYTRADE_USE_PRODUCTION=false

# ChatGPT MCP Authentication
CHATGPT_MCP_TOKEN=your-secure-token

# Optional: Rate limiting
RATE_LIMIT_REQUESTS_PER_MINUTE=100
```

## 🚀 **Deployment Options**

### **Option 1: Railway (Recommended)**
Your existing Railway deployment can be extended to support ChatGPT MCP:

1. **Add the ChatGPT bridge to your Railway app**
2. **Update environment variables** with ChatGPT MCP token
3. **Use Railway URL** in ChatGPT connector settings

### **Option 2: Local Development**
For testing and development:

```bash
# Terminal 1: Start the bridge
python chatgpt_mcp_bridge.py

# Terminal 2: Test endpoints
curl "http://localhost:8086/health"
curl "http://localhost:8086/mcp/tools"
```

### **Option 3: Custom Deployment**
Deploy to any cloud provider that supports:
- HTTPS endpoints
- Environment variables
- Python 3.8+

## ⚠️ **ChatGPT MCP Availability**

### **Current Status (September 2024)**
- **Limited Preview**: ChatGPT MCP integration is currently in limited preview
- **Access Required**: Not publicly available - requires Developer Mode access from OpenAI
- **Token Generation**: When you have access, tokens are generated in ChatGPT → Settings → Developer Mode → Connectors → Create
- **Ready for Future**: Our implementation is ready - just waiting for broader ChatGPT MCP availability

### **Getting Access**
- Apply through OpenAI's developer channels
- Monitor OpenAI announcements for public release
- ChatGPT Plus/Pro subscribers may get earlier access

## 🔍 **Troubleshooting**

### **Common Issues**

#### "This MCP server doesn't implement our specification"
- ✅ Verify `/mcp/capabilities` endpoint returns proper MCP schema
- ✅ Check `/mcp/tools` includes required tools (search, fetch)
- ✅ Ensure tool schemas match MCP specification

#### "Unauthorized" Errors
- ✅ Check Bearer token in ChatGPT connector settings
- ✅ Verify `CHATGPT_MCP_TOKEN` environment variable
- ✅ Ensure token matches between server and ChatGPT

#### "Timeout" Errors
- ✅ Check server latency (should be < 3 seconds)
- ✅ Verify TastyTrade credentials are valid
- ✅ Check Railway/server logs for errors

#### Tool Not Visible in ChatGPT
- ✅ Confirm connector is enabled in current chat
- ✅ Try refreshing ChatGPT browser tab
- ✅ Check connector status in settings

### **Debugging Commands**

```bash
# Test health endpoint
curl "https://your-app.railway.app/health"

# Test MCP capabilities
curl "https://your-app.railway.app/mcp/capabilities"

# Test tool call
curl -X POST "https://your-app.railway.app/mcp/call" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-token" \
  -d '{"name": "fetch_accounts", "arguments": {}}'
```

### **Log Analysis**
Check Railway logs for:
- Authentication success/failure
- Tool call requests and responses
- TastyTrade API connection status
- HTTP response codes and timing

## 📈 **Performance Optimization**

### **Response Time Targets**
- Health check: < 200ms
- Account info: < 1s
- Market data: < 500ms
- Complex queries: < 3s

### **Caching Strategy**
- Account data: 5 minutes
- Market data: 30 seconds
- Position data: 1 minute

### **Rate Limiting**
Default limits (configurable):
- 100 requests per minute per IP
- 1000 requests per hour per token

## 🔄 **Comparison: ChatGPT vs Claude**

| Feature | ChatGPT MCP | Claude MCP | Notes |
|---------|-------------|------------|-------|
| **Connection** | HTTP/HTTPS | stdio | ChatGPT requires web endpoint |
| **Authentication** | Bearer Token | None | ChatGPT needs auth header |
| **Latency** | ~500ms | ~50ms | Network vs local |
| **Tool Schema** | OpenAI format | MCP standard | Same data, different format |
| **Error Handling** | HTTP codes | MCP errors | Both provide actionable messages |
| **CORS Support** | Required | Not needed | Web vs desktop app |

## 🎯 **Next Steps**

1. **Test the integration** with various trading scenarios
2. **Monitor performance** and optimize slow endpoints
3. **Add more advanced tools** like order placement
4. **Implement rate limiting** for production use
5. **Add monitoring and alerting** for system health

## 📞 **Support**

For issues with the ChatGPT integration:
1. Check server health: `GET /health`
2. Review server logs in Railway dashboard
3. Test endpoints directly with curl
4. Verify ChatGPT connector configuration

---

**Ready to connect ChatGPT to your TastyTrade account!** 🚀

The bridge server provides the same powerful trading tools through a ChatGPT-compatible interface, enabling natural language trading conversations with full MCP protocol support.