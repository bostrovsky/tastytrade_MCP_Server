# TastyTrade MCP Server - Installation

## Choose Your Setup

**🏠 Local (Claude Desktop)** - Private, instant setup
**☁️ Cloud (ChatGPT + Teams)** - Shareable, web-based

## Prerequisites

- Python 3.8+
- TastyTrade account
- Git

## 🏠 Local Setup (Claude Desktop)

### 1. Install
```bash
git clone <your-repo-url>
cd Tasty_MCP
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Credentials
Create `.env` file with your **actual TastyTrade credentials**:

```bash
# For REAL trading (recommended after testing)
TASTYTRADE_USERNAME=your_actual_tastytrade_email@example.com
TASTYTRADE_PASSWORD=your_actual_tastytrade_password
TASTYTRADE_USE_PRODUCTION=true

# OR for testing only (optional sandbox account)
TASTYTRADE_SANDBOX_USERNAME=sandbox_email@example.com
TASTYTRADE_SANDBOX_PASSWORD=sandbox_password
TASTYTRADE_USE_PRODUCTION=false
```

### 3. Configure Claude Desktop
Add to `claude_desktop_config.json`:

**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
**Mac**: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "tastytrade": {
      "command": "python",
      "args": ["/full/path/to/Tasty_MCP/claude_wrapper.py"]
    }
  }
}
```

**Note**: Credentials are securely loaded from `.env` - never put them in this config file!

### 3. Test
Restart Claude Desktop. Type: "Show my TastyTrade accounts"

## ☁️ Cloud Setup (Railway + ChatGPT)

### 1. Deploy to Railway
```bash
# From your local Tasty_MCP directory
railway login
railway init
railway up
```

### 2. Set Environment Variables
In Railway dashboard → Variables:
```
# Use your REAL TastyTrade credentials for actual trading
TASTYTRADE_USERNAME=your_actual_tastytrade_email@example.com
TASTYTRADE_PASSWORD=your_actual_tastytrade_password
TASTYTRADE_USE_PRODUCTION=true
CHATGPT_MCP_TOKEN=your-secure-token

# OR for testing only (if you have sandbox access)
TASTYTRADE_SANDBOX_USERNAME=sandbox_email@example.com
TASTYTRADE_SANDBOX_PASSWORD=sandbox_password
TASTYTRADE_USE_PRODUCTION=false
```

### 3. Configure ChatGPT
After deployment, Railway will give you a unique URL. Use it in ChatGPT:

ChatGPT → Settings → Developer Mode → Connectors → Create:
- **Name**: TastyTrade
- **Server URL**: `https://YOUR-UNIQUE-APP-NAME.up.railway.app/mcp`
- **Auth**: Bearer Token: `your-secure-token`

**Note**: Replace `YOUR-UNIQUE-APP-NAME` with your actual Railway deployment URL

### 4. Test
In ChatGPT: "Show my TastyTrade accounts"

## Security Notes

- **Sandbox Mode**: Default setting for safe testing
- **Production Mode**: Set `TASTYTRADE_USE_PRODUCTION=true` only when ready
- **Credentials**: Never commit credentials to git

## Troubleshooting

**Claude Desktop not working?**
- Check file paths are absolute
- Restart Claude Desktop after config changes

**Railway 404 errors?**
- Run `railway link` to reconnect
- Check environment variables are set

**ChatGPT connection failed?**
- Verify Bearer token matches `CHATGPT_MCP_TOKEN`
- Check Railway URL is correct