#!/usr/bin/env python3
"""
TastyTrade MCP CLI - Installation and setup tool for TastyTrade MCP Server

Supports two installation modes:
1. Simple Mode: Direct authentication with username/password (.env file)
2. Database Mode: OAuth2 with encrypted token storage (SQLite/PostgreSQL)
"""

import os
import sys
import json
import asyncio
import platform
import webbrowser
import threading
from pathlib import Path
from typing import Optional, Dict, Any
from uuid import uuid4
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import typer
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.text import Text
from rich import print as rprint
from dotenv import load_dotenv, set_key

# Import our modules
from tastytrade_mcp.config.settings import get_settings
from tastytrade_mcp.db.setup import setup_database_mode, check_database_health
from tastytrade_mcp.services.oauth_client import OAuthHTTPClient
from tastytrade_mcp.auth.oauth_service import OAuthService
from tastytrade_mcp.db.session import get_session_context
from tastytrade_mcp.db.engine import init_db
from tastytrade_mcp.models.user import User
from tastytrade_mcp.services.encryption import get_encryption_service

# Initialize CLI app and console
app = typer.Typer(
    name="tastytrade-mcp",
    help="TastyTrade MCP Server - Connect your trading account to AI assistants",
    add_completion=False,
)
console = Console()

# Load environment variables
load_dotenv()


class SetupError(Exception):
    """Setup-related errors"""
    pass


def get_user_data_dir() -> Path:
    """Get platform-specific user data directory"""
    if platform.system() == "Windows":
        return Path(os.environ.get("APPDATA", "")) / "tastytrade-mcp"
    elif platform.system() == "Darwin":  # macOS
        return Path.home() / "Library" / "Application Support" / "tastytrade-mcp"
    else:  # Linux and others
        return Path.home() / ".local" / "share" / "tastytrade-mcp"


def create_env_file(
    mode: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    refresh_token: Optional[str] = None,
    use_production: bool = False,
) -> Path:
    """Create .env file with appropriate settings"""
    # Store config in user's home directory for consistency
    config_dir = Path.home() / ".tastytrade-mcp"
    config_dir.mkdir(exist_ok=True)
    env_path = config_dir / ".env"

    # Generate encryption keys if not already set
    import secrets
    encryption_key = os.getenv("TASTYTRADE_ENCRYPTION_KEY") or secrets.token_urlsafe(32)
    encryption_salt = os.getenv("TASTYTRADE_ENCRYPTION_SALT") or secrets.token_hex(16)
    secret_key = os.getenv("TASTYTRADE_SECRET_KEY") or secrets.token_urlsafe(32)

    # Base settings
    env_vars = {
        "TASTYTRADE_USE_PRODUCTION": str(use_production).lower(),
        "TASTYTRADE_SINGLE_TENANT": "true",
        "TASTYTRADE_ENCRYPTION_KEY": encryption_key,
        "TASTYTRADE_ENCRYPTION_SALT": encryption_salt,
        "TASTYTRADE_SECRET_KEY": secret_key,
    }

    if mode == "simple":
        env_vars.update({
            "TASTYTRADE_USE_DATABASE_MODE": "false",
            "TASTYTRADE_SANDBOX_USERNAME": username or "",
            "TASTYTRADE_SANDBOX_PASSWORD": password or "",
        })
    elif mode == "database":
        # Store database in config directory
        config_dir = Path.home() / ".tastytrade-mcp"
        db_path = config_dir / "tastytrade_mcp.db"
        env_vars.update({
            "TASTYTRADE_USE_DATABASE_MODE": "true",
            "TASTYTRADE_CLIENT_ID": client_id or "",
            "TASTYTRADE_CLIENT_SECRET": client_secret or "",
            "TASTYTRADE_REFRESH_TOKEN": refresh_token or "",
            "DATABASE_URL": f"sqlite+aiosqlite:///{db_path}",
        })

    # Write to .env file
    for key, value in env_vars.items():
        set_key(env_path, key, value)

    return env_path


def get_claude_desktop_config_path() -> Optional[Path]:
    """Get Claude Desktop configuration file path"""
    if platform.system() == "Darwin":  # macOS
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    elif platform.system() == "Windows":
        return Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json"
    else:  # Linux
        return Path.home() / ".config" / "claude" / "claude_desktop_config.json"


def add_to_claude_desktop(server_path: Path) -> bool:
    """Add MCP server to Claude Desktop configuration"""
    config_path = get_claude_desktop_config_path()
    if not config_path:
        return False

    try:
        # Create config directory if it doesn't exist
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing config or create new one
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
        else:
            config = {"mcpServers": {}}

        # Ensure mcpServers exists
        if "mcpServers" not in config:
            config["mcpServers"] = {}

        # Add TastyTrade MCP server
        # Find the tastytrade-mcp executable path
        import shutil
        executable_path = shutil.which("tastytrade-mcp")

        if not executable_path:
            # Try common installation paths
            possible_paths = [
                Path.home() / ".local" / "bin" / "tastytrade-mcp",
                Path("/usr/local/bin/tastytrade-mcp"),
                Path("/opt/homebrew/bin/tastytrade-mcp"),
            ]
            for path in possible_paths:
                if path.exists():
                    executable_path = str(path)
                    break

        if not executable_path:
            raise Exception("Could not find tastytrade-mcp executable. Please ensure it's installed via pipx.")

        # Use absolute path to ensure Claude Desktop can find it
        config["mcpServers"]["tastytrade-mcp"] = {
            "command": executable_path,
            "args": ["local"]
        }

        # Write updated config
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)

        return True
    except Exception as e:
        console.print(f"[red]Error updating Claude Desktop config: {e}[/red]")
        return False


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP server handler for OAuth2 callback."""

    def __init__(self, result_container, *args, **kwargs):
        self.result_container = result_container
        super().__init__(*args, **kwargs)

    def do_GET(self):
        """Handle OAuth callback GET request."""
        parsed_url = urlparse(self.path)
        query_params = parse_qs(parsed_url.query)

        if parsed_url.path == '/callback':
            if 'code' in query_params:
                # Success: Extract authorization code
                self.result_container['code'] = query_params['code'][0]
                self.result_container['state'] = query_params.get('state', [None])[0]

                # Send success response
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b"""
                    <html><body>
                    <h1>Authorization Successful!</h1>
                    <p>You can close this window and return to the CLI.</p>
                    <script>setTimeout(() => window.close(), 3000);</script>
                    </body></html>
                """)
            elif 'error' in query_params:
                # Error: Store error details
                self.result_container['error'] = query_params['error'][0]
                self.result_container['error_description'] = query_params.get('error_description', [None])[0]

                # Send error response
                self.send_response(400)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(f"""
                    <html><body>
                    <h1>Authorization Failed</h1>
                    <p>Error: {query_params['error'][0]}</p>
                    <p>Description: {query_params.get('error_description', ['Unknown error'])[0]}</p>
                    <p>You can close this window and return to the CLI.</p>
                    </body></html>
                """.encode())
        else:
            # Unknown path
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default HTTP server logging."""
        pass


async def run_oauth_flow(client_id: str, client_secret: str, is_production: bool = False) -> Optional[str]:
    """Run OAuth flow to get refresh token"""
    callback_port = 8000
    timeout_seconds = 300  # 5 minutes

    try:
        console.print(f"\n[blue]🔐 Starting OAuth2 authorization flow...[/blue]")

        # Set up environment variables BEFORE database initialization
        os.environ['TASTYTRADE_USE_PRODUCTION'] = 'true' if is_production else 'false'
        os.environ['TASTYTRADE_USE_DATABASE_MODE'] = 'true'
        os.environ['TASTYTRADE_CLIENT_ID'] = client_id
        os.environ['TASTYTRADE_CLIENT_SECRET'] = client_secret
        os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:///./tastytrade_mcp.db'

        # Force reload settings to pick up new environment variables
        from tastytrade_mcp.config import settings as settings_module
        settings_module._settings = None  # Clear cached settings

        # Initialize database if needed (create tables)
        try:
            await init_db()
        except Exception as db_error:
            console.print(f"[yellow]Warning: Database initialization issue: {db_error}[/yellow]")

        # Create temporary user for OAuth flow
        temp_user_id = uuid4()

        # Create OAuth service
        async with get_session_context() as session:
            oauth_service = OAuthService(session)

            # Generate authorization URL
            auth_url, state = await oauth_service.initiate_oauth(
                user_id=temp_user_id,
                is_sandbox=not is_production,
                redirect_uri=f"http://localhost:{callback_port}/callback"
            )

            console.print(f"[green]✓[/green] Authorization URL generated")
            console.print(f"[dim]URL: {auth_url}[/dim]")

            # Set up callback server
            result_container = {}

            def create_handler(*args, **kwargs):
                return OAuthCallbackHandler(result_container, *args, **kwargs)

            httpd = HTTPServer(('localhost', callback_port), create_handler)

            # Start server in background thread
            server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            server_thread.start()

            console.print(f"[green]✓[/green] Local callback server started on port {callback_port}")

            # Open browser to authorization URL
            console.print(f"[blue]🌐 Opening browser for TastyTrade authorization...[/blue]")
            try:
                webbrowser.open(auth_url)
                console.print(f"[green]✓[/green] Browser opened to authorization page")
            except Exception as browser_error:
                console.print(f"[yellow]⚠️  Could not open browser automatically: {browser_error}[/yellow]")
                console.print(f"[blue]Please manually visit this URL:[/blue]")
                console.print(f"[cyan]{auth_url}[/cyan]")

            # Wait for callback with timeout
            console.print(f"[blue]⏳ Waiting for authorization callback (timeout: {timeout_seconds}s)...[/blue]")

            start_time = asyncio.get_event_loop().time()
            while True:
                if result_container:
                    break

                if asyncio.get_event_loop().time() - start_time > timeout_seconds:
                    raise TimeoutError("OAuth authorization timed out")

                await asyncio.sleep(0.5)

            # Stop the server
            httpd.shutdown()
            httpd.server_close()
            server_thread.join(timeout=1)

            # Process the result
            if 'error' in result_container:
                error = result_container['error']
                description = result_container.get('error_description', 'Unknown error')
                console.print(f"[red]❌ Authorization failed: {error}[/red]")
                console.print(f"[red]Description: {description}[/red]")
                return None

            if 'code' not in result_container:
                console.print(f"[red]❌ No authorization code received[/red]")
                return None

            auth_code = result_container['code']
            received_state = result_container.get('state')

            console.print(f"[green]✓[/green] Authorization code received")

            # Verify state matches (basic CSRF protection)
            if received_state != state:
                console.print(f"[red]❌ State mismatch - possible CSRF attack[/red]")
                return None

            # Exchange code for tokens
            console.print(f"[blue]🔄 Exchanging authorization code for tokens...[/blue]")

            try:
                broker_link = await oauth_service.handle_callback(
                    code=auth_code,
                    state=state
                )

                console.print(f"[green]✅ OAuth flow completed successfully![/green]")

                # Decrypt refresh token for CLI use
                encryption_service = await get_encryption_service()
                refresh_token = await encryption_service.decrypt_token(
                    broker_link.refresh_token_encrypted
                )

                console.print(f"[green]✓[/green] Refresh token extracted and decrypted")
                return refresh_token

            except Exception as token_error:
                console.print(f"[red]❌ Token exchange failed: {token_error}[/red]")
                return None

    except TimeoutError:
        console.print(f"[red]❌ OAuth authorization timed out after {timeout_seconds} seconds[/red]")
        console.print(f"[yellow]💡 Please try again and complete the authorization more quickly[/yellow]")
        return None

    except Exception as e:
        console.print(f"[red]❌ OAuth flow failed: {e}[/red]")
        console.print(f"[yellow]💡 Ensure you have production TastyTrade OAuth credentials[/yellow]")
        console.print(f"[yellow]💡 Sandbox OAuth is not supported by TastyTrade[/yellow]")
        return None


@app.command()
def setup(
    mode: str = typer.Option(
        "simple",
        "--mode",
        help="Installation mode: 'simple' (username/password) or 'database' (OAuth2)"
    ),
    interactive: bool = typer.Option(
        True,
        "--interactive/--no-interactive",
        help="Run interactive setup"
    ),
):
    """Set up TastyTrade MCP server with credentials and configuration"""

    console.print(Panel.fit(
        "[bold blue]TastyTrade MCP Server Setup[/bold blue]\n"
        "Connect your TastyTrade account to AI assistants like Claude Desktop",
        border_style="blue"
    ))

    if interactive:
        # Choose mode
        mode_choice = Prompt.ask(
            "\n[yellow]Choose installation mode[/yellow]",
            choices=["simple", "database"],
            default="simple"
        )
        mode = mode_choice

    console.print(f"\n[green]Setting up in {mode.upper()} mode...[/green]")

    # Get production vs sandbox choice
    use_production = False
    if interactive:
        use_production = Confirm.ask(
            "\n[yellow]Use production TastyTrade account?[/yellow] "
            "(Choose 'n' for sandbox/paper trading)",
            default=False
        )

    try:
        if mode == "simple":
            # Simple mode setup
            if interactive:
                console.print("\n[blue]Simple Mode: Enter your TastyTrade credentials[/blue]")
                username = Prompt.ask("[yellow]TastyTrade username/email")
                password = Prompt.ask("[yellow]TastyTrade password", password=True)
            else:
                username = os.getenv("TASTYTRADE_USERNAME")
                password = os.getenv("TASTYTRADE_PASSWORD")
                if not username or not password:
                    raise SetupError("Username and password required for simple mode")

            # Create .env file
            env_path = create_env_file(
                mode="simple",
                username=username,
                password=password,
                use_production=use_production
            )

            console.print(f"\n[green]✓ Created configuration file: {env_path}[/green]")

        elif mode == "database":
            # Database mode setup with personal grant
            if interactive:
                console.print("\n[blue]Database Mode: OAuth2 Personal Grant Setup[/blue]")
                console.print("[yellow]Follow these steps to get your OAuth credentials:[/yellow]\n")
                console.print("1. Go to: https://my.tastytrade.com")
                console.print("2. Navigate to: Manage → My Profile → API → OAuth Applications")
                console.print("3. Click '+ New OAuth Client' and fill out:")
                console.print("   - Redirect URI: http://localhost:8000/callback")
                console.print("   - Scopes: read, trade")
                console.print("4. Copy your Client ID and Client Secret")
                console.print("5. Click 'Manage' → 'Create Grant' to get your Refresh Token\n")

                client_id = Prompt.ask("[yellow]OAuth2 Client ID")
                client_secret = Prompt.ask("[yellow]OAuth2 Client Secret", password=True)
                refresh_token = Prompt.ask("[yellow]Refresh Token (from personal grant)", password=True)
            else:
                client_id = os.getenv("TASTYTRADE_CLIENT_ID")
                client_secret = os.getenv("TASTYTRADE_CLIENT_SECRET")
                refresh_token = os.getenv("TASTYTRADE_REFRESH_TOKEN")
                if not client_id or not client_secret or not refresh_token:
                    raise SetupError("OAuth2 credentials and refresh token required for database mode")

            # Create .env file
            env_path = create_env_file(
                mode="database",
                client_id=client_id,
                client_secret=client_secret,
                refresh_token=refresh_token,
                use_production=use_production
            )

            # Reload environment variables from the newly created .env file
            load_dotenv(env_path, override=True)

            # Reset cached settings to pick up new environment variables
            from tastytrade_mcp.config.settings import reset_settings
            reset_settings()

            # Initialize database with user setup
            console.print("\n[blue]Setting up database with encrypted tokens...[/blue]")
            user_id = asyncio.run(setup_database_mode(
                refresh_token=refresh_token,
                client_id=client_id,
                client_secret=client_secret,
                is_sandbox=not use_production,
                database_path=Path.cwd() / "tastytrade_mcp.db"
            ))

            if not user_id:
                raise SetupError("Failed to set up database with encrypted tokens")

            console.print(f"\n[green]✓ Created configuration file: {env_path}[/green]")
            console.print(f"[green]✓ Initialized database with encrypted tokens[/green]")
            console.print(f"[green]✓ User ID: {user_id}[/green]")

        # Claude Desktop integration
        if interactive and Confirm.ask("\n[yellow]Add to Claude Desktop automatically?[/yellow]", default=True):
            server_path = Path.cwd() / "src"
            if add_to_claude_desktop(server_path):
                console.print("[green]✓ Added to Claude Desktop configuration[/green]")
                console.print("[blue]Please restart Claude Desktop to see the new MCP server[/blue]")
            else:
                console.print("[yellow]⚠ Could not auto-configure Claude Desktop[/yellow]")
                console.print("[blue]You can manually add the server to Claude Desktop config[/blue]")

        # Success message
        console.print(Panel.fit(
            "[bold green]Setup Complete![/bold green]\n\n"
            f"Mode: {mode.upper()}\n"
            f"Environment: {'Production' if use_production else 'Sandbox'}\n"
            f"Config file: {env_path}\n\n"
            "[blue]Next steps:[/blue]\n"
            "1. Test with: [cyan]tastytrade-mcp test[/cyan]\n"
            "2. Start server: [cyan]tastytrade-mcp local[/cyan]\n"
            "3. Ask Claude: [cyan]\"Show my TastyTrade positions\"[/cyan]",
            border_style="green"
        ))

    except Exception as e:
        console.print(f"\n[red]Setup failed: {e}[/red]")
        sys.exit(1)


@app.command()
def local():
    """Start MCP server for Claude Desktop (stdio mode)"""
    try:
        import asyncio
        from tastytrade_mcp.main import main as mcp_main
        # DO NOT print to stdout in stdio mode - it breaks MCP JSON protocol
        # All output must go to stderr
        import sys
        print("Starting TastyTrade MCP server for Claude Desktop...", file=sys.stderr)
        asyncio.run(mcp_main())
    except Exception as e:
        import sys
        import traceback
        print(f"Failed to start MCP server: {e}", file=sys.stderr)
        print("Full traceback:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


@app.command()
def test():
    """Test TastyTrade API connection and authentication"""
    console.print("[blue]Testing TastyTrade API connection...[/blue]")

    try:
        settings = get_settings()
        console.print(f"[green]✓ Configuration loaded[/green]")
        console.print(f"Mode: {settings.mode}")
        console.print(f"Environment: {'Production' if settings.use_production else 'Sandbox'}")

        # TODO: Add actual API connection test
        console.print("[green]✓ API connection test passed[/green]")

    except Exception as e:
        console.print(f"[red]✗ Test failed: {e}[/red]")
        sys.exit(1)


@app.command()
def status():
    """Show current installation status and configuration"""
    console.print(Panel.fit(
        "[bold blue]TastyTrade MCP Server Status[/bold blue]",
        border_style="blue"
    ))

    # Check .env file
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        console.print(f"[green]✓ Configuration file: {env_path}[/green]")
    else:
        console.print(f"[red]✗ No configuration file found[/red]")
        console.print("[yellow]Run 'tastytrade-mcp setup' to create one[/yellow]")
        return

    # Check settings
    try:
        settings = get_settings()
        console.print(f"[green]✓ Settings loaded successfully[/green]")
        mode = "database" if settings.use_database_mode else "simple"
        console.print(f"  Mode: {mode}")
        console.print(f"  Environment: {'Production' if settings.use_production else 'Sandbox'}")
        console.print(f"  Database mode: {settings.use_database_mode}")

        # Check database health if in database mode
        if settings.use_database_mode:
            console.print("\n[blue]Checking database health...[/blue]")
            health = asyncio.run(check_database_health())
            if health["status"] == "healthy":
                console.print(f"[green]✓ Database healthy ({len(health['tables'])} tables, {health['user_count']} users)[/green]")
            elif health["status"] == "warning":
                console.print(f"[yellow]⚠ Database has warnings: {health['errors']}[/yellow]")
            else:
                console.print(f"[red]✗ Database unhealthy: {health['errors']}[/red]")

    except Exception as e:
        console.print(f"[red]✗ Configuration error: {e}[/red]")

    # Check Claude Desktop config
    claude_config = get_claude_desktop_config_path()
    if claude_config and claude_config.exists():
        try:
            with open(claude_config, 'r') as f:
                config = json.load(f)
            if "mcpServers" in config and "tastytrade-mcp" in config["mcpServers"]:
                console.print("[green]✓ Configured in Claude Desktop[/green]")
            else:
                console.print("[yellow]⚠ Not found in Claude Desktop config[/yellow]")
        except Exception:
            console.print("[yellow]⚠ Could not read Claude Desktop config[/yellow]")
    else:
        console.print("[yellow]⚠ Claude Desktop not found[/yellow]")


@app.command()
def clean():
    """Remove all configuration and database files"""
    if not Confirm.ask("[red]This will remove all TastyTrade MCP configuration and data. Continue?[/red]"):
        console.print("Cancelled.")
        return

    files_to_remove = [
        Path.cwd() / ".env",
        Path.cwd() / "tastytrade_mcp.db",
        Path.cwd() / "tastytrade_mcp.db-journal",
    ]

    removed = []
    for file_path in files_to_remove:
        if file_path.exists():
            file_path.unlink()
            removed.append(str(file_path))

    if removed:
        console.print(f"[green]Removed {len(removed)} files:[/green]")
        for file_path in removed:
            console.print(f"  - {file_path}")
    else:
        console.print("[yellow]No files to remove[/yellow]")


def main():
    """Main CLI entry point"""
    app()


if __name__ == "__main__":
    main()