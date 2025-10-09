"""Handler adapter for database-optional operation.

This adapter pattern allows handlers to work with or without database infrastructure:
- Simple Mode (Phase 1): Direct authentication using environment credentials
- Database Mode (Phase 2): User lookup, token decryption, session management
"""
import os
from typing import Optional
from datetime import datetime, timezone, timedelta
import asyncpg
from cryptography.fernet import Fernet
from httpx import Client
from tastytrade import Session, Account
from tastytrade.session import API_URL, CERT_URL

from tastytrade_mcp.config.settings import get_settings
from tastytrade_mcp.services.simple_session import get_tastytrade_session
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)


class HandlerAdapter:
    """
    Adapter allowing handlers to work with or without database.

    Modes:
    - Simple (Phase 1): Direct auth from environment variables via simple_session
    - Database (Phase 2): Lookup user, decrypt tokens, create session

    Usage:
        adapter = HandlerAdapter(use_database=False)
        session = await adapter.get_session()
        account_number = await adapter.get_account_number()
    """

    def __init__(self, use_database: bool = False):
        """
        Initialize adapter with mode selection.

        Args:
            use_database: If True, use database mode (Phase 2). If False, use simple mode (Phase 1).
        """
        self.use_database = use_database
        self.settings = get_settings()

        logger.info(f"HandlerAdapter initialized in {'DATABASE' if use_database else 'SIMPLE'} mode")

    async def get_session(self, user_id: Optional[str] = None) -> Session:
        """
        Get authenticated TastyTrade session.

        Args:
            user_id: User ID (optional - uses single-tenant mode if not provided)

        Returns:
            Session: Authenticated TastyTrade session

        Raises:
            ValueError: If credentials are missing or authentication fails
        """
        # Single-tenant mode: Use OAuth from .env when no user_id provided
        if self.use_database and (not user_id or user_id == "default"):
            # Check if single-tenant mode is enabled
            if os.environ.get('TASTYTRADE_SINGLE_TENANT', 'false').lower() == 'true':
                logger.info("Using single-tenant OAuth mode from .env")
                return await self._get_session_from_env_oauth()
            else:
                # Try to get default user from database
                user_id = await self._get_default_user_id()
                if user_id:
                    return await self._get_session_from_database(user_id)
                else:
                    logger.warning("No user_id provided and no default user found")
                    # Fallback to env OAuth if available
                    return await self._get_session_from_env_oauth()

        if self.use_database and user_id:
            return await self._get_session_from_database(user_id)

        # Simple mode (non-database)
        try:
            session = get_tastytrade_session()
            logger.debug("Successfully retrieved session in simple mode")
            return session

        except Exception as e:
            logger.error(f"Failed to get session: {e}", exc_info=True)
            raise ValueError(
                f"Failed to authenticate with TastyTrade. "
                f"Please check your TASTYTRADE_SANDBOX_USERNAME and TASTYTRADE_SANDBOX_PASSWORD "
                f"environment variables. Error: {str(e)}"
            )

    async def _get_session_from_database(self, user_id: str) -> Session:
        """
        Retrieve and restore TastyTrade session from database.

        Args:
            user_id: User ID to lookup

        Returns:
            Session: Restored TastyTrade session

        Raises:
            ValueError: If user not found, no broker link, or token invalid
        """
        if not user_id:
            raise ValueError("user_id is required for database mode")

        database_url = self.settings.database_url
        if not database_url:
            raise ValueError("PostgreSQL DATABASE_URL required for database mode")

        if database_url.startswith("sqlite"):
            raise ValueError("PostgreSQL DATABASE_URL required for database mode (not SQLite)")

        # Convert to asyncpg format
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

        if not self.settings.encryption_key:
            raise ValueError("TASTYTRADE_ENCRYPTION_KEY required for database mode")

        try:
            conn = await asyncpg.connect(database_url)

            user_data = await conn.fetchrow("""
                SELECT
                    bl.account_number,
                    bl.is_sandbox,
                    bs.enc_access_token,
                    bs.enc_refresh_token,
                    bs.access_expires_at,
                    bs.id as secret_id
                FROM users u
                JOIN broker_links bl ON bl.user_id = u.id
                JOIN broker_secrets bs ON bs.broker_link_id = bl.id
                WHERE u.id = $1
                LIMIT 1
            """, user_id)

            await conn.close()

            if not user_data:
                raise ValueError(f"No active broker link found for user_id: {user_id}")

            is_sandbox = user_data['is_sandbox']
            encrypted_access_token = user_data['enc_access_token']
            encrypted_refresh_token = user_data['enc_refresh_token']
            access_expires_at = user_data['access_expires_at']
            secret_id = user_data['secret_id']

            cipher = Fernet(self.settings.encryption_key.encode())
            access_token = cipher.decrypt(encrypted_access_token.encode()).decode()

            # Check if access token is expired
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)

            # Make access_expires_at timezone aware if it isn't
            if access_expires_at and access_expires_at.tzinfo is None:
                access_expires_at = access_expires_at.replace(tzinfo=timezone.utc)

            if access_expires_at and access_expires_at < now:
                logger.info(f"Access token expired for user {user_id}, refreshing...")

                # Decrypt refresh token
                refresh_token = cipher.decrypt(encrypted_refresh_token.encode()).decode()

                # Use refresh token to get new access token
                import httpx

                # Get OAuth client credentials from environment
                client_id = self.settings.oauth_client_id or os.environ.get('TASTYTRADE_CLIENT_ID')
                client_secret = self.settings.oauth_client_secret or os.environ.get('TASTYTRADE_CLIENT_SECRET')

                if not client_id or not client_secret:
                    raise ValueError("OAuth client credentials not configured")

                # Refresh the token
                refresh_url = "https://api.tastytrade.com/oauth/token"
                refresh_data = {
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": client_id,
                    "client_secret": client_secret
                }

                async with httpx.AsyncClient() as client:
                    response = await client.post(refresh_url, data=refresh_data)

                    if response.status_code == 200:
                        token_data = response.json()
                        new_access_token = token_data['access_token']
                        new_refresh_token = token_data.get('refresh_token', refresh_token)
                        expires_in = token_data.get('expires_in', 1200)

                        # Update database with new tokens (make naive for PostgreSQL)
                        new_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                        encrypted_new_access = cipher.encrypt(new_access_token.encode()).decode()
                        encrypted_new_refresh = cipher.encrypt(new_refresh_token.encode()).decode()

                        conn = await asyncpg.connect(database_url)
                        await conn.execute("""
                            UPDATE broker_secrets
                            SET enc_access_token = $1,
                                enc_refresh_token = $2,
                                access_expires_at = $3
                            WHERE id = $4
                        """, encrypted_new_access, encrypted_new_refresh, new_expires_at, secret_id)
                        await conn.close()

                        logger.info(f"Successfully refreshed OAuth tokens for user {user_id}")
                        access_token = new_access_token
                    else:
                        logger.error(f"Failed to refresh token: {response.status_code} - {response.text}")
                        raise ValueError(f"Failed to refresh OAuth token: {response.status_code}")

            session = Session.__new__(Session)
            session.is_test = is_sandbox
            session.proxy = None
            session.session_token = access_token  # Use the potentially refreshed token
            session.remember_token = None
            session.user = None

            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": access_token  # Use the potentially refreshed token
            }

            base_url = CERT_URL if is_sandbox else API_URL
            session.sync_client = Client(base_url=base_url, headers=headers, proxy=None)

            logger.info(f"Successfully restored session from database for user {user_id}")
            return session

        except asyncpg.PostgresError as e:
            logger.error(f"Database error retrieving session: {e}", exc_info=True)
            raise ValueError(f"Database error: {str(e)}")

        except Exception as e:
            logger.error(f"Failed to restore session from database: {e}", exc_info=True)
            raise ValueError(f"Failed to restore session: {str(e)}")

    async def get_account_number(self, user_id: Optional[str] = None) -> str:
        """
        Get account number for the authenticated user.

        Args:
            user_id: User ID (required for database mode, ignored in simple mode)

        Returns:
            str: Account number

        Raises:
            ValueError: If no accounts found or authentication fails
        """
        if self.use_database:
            return await self._get_account_number_from_database(user_id)

        try:
            session = await self.get_session(user_id)

            accounts = Account.get(session)

            if not accounts or len(accounts) == 0:
                raise ValueError("No accounts found for authenticated user")

            account_number = accounts[0].account_number
            logger.debug(f"Retrieved account number: {account_number}")

            return account_number

        except Exception as e:
            logger.error(f"Failed to get account number: {e}", exc_info=True)
            raise ValueError(
                f"Failed to retrieve account number. "
                f"Ensure you have at least one account linked. Error: {str(e)}"
            )

    async def _get_account_number_from_database(self, user_id: str) -> str:
        """
        Retrieve account number from database.

        Args:
            user_id: User ID to lookup

        Returns:
            str: Account number

        Raises:
            ValueError: If user not found or no broker link
        """
        if not user_id:
            raise ValueError("user_id is required for database mode")

        database_url = self.settings.database_url
        if not database_url:
            raise ValueError("PostgreSQL DATABASE_URL required for database mode")

        if database_url.startswith("sqlite"):
            raise ValueError("PostgreSQL DATABASE_URL required for database mode (not SQLite)")

        # Convert to asyncpg format
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

        try:
            conn = await asyncpg.connect(database_url)

            account_number = await conn.fetchval("""
                SELECT bl.account_number
                FROM users u
                JOIN broker_links bl ON bl.user_id = u.id
                WHERE u.id = $1
                LIMIT 1
            """, user_id)

            await conn.close()

            if not account_number:
                raise ValueError(f"No broker link found for user_id: {user_id}")

            logger.debug(f"Retrieved account number from database: {account_number}")
            return account_number

        except asyncpg.PostgresError as e:
            logger.error(f"Database error retrieving account number: {e}", exc_info=True)
            raise ValueError(f"Database error: {str(e)}")

        except Exception as e:
            logger.error(f"Failed to retrieve account number from database: {e}", exc_info=True)
            raise ValueError(f"Failed to retrieve account number: {str(e)}")

    async def _get_session_from_env_oauth(self) -> Session:
        """
        Get session using OAuth credentials from environment variables (single-tenant mode).

        Returns:
            Session: Authenticated TastyTrade session

        Raises:
            ValueError: If OAuth credentials are missing or authentication fails
        """
        import httpx
        from datetime import datetime, timedelta
        from .token_storage import TokenStorage

        # Get OAuth credentials from environment
        client_id = os.environ.get('TASTYTRADE_CLIENT_ID')
        client_secret = os.environ.get('TASTYTRADE_CLIENT_SECRET')

        # Get refresh token from storage or environment
        token_storage = TokenStorage()
        refresh_token = token_storage.get_or_init_refresh_token(client_id) if client_id else None

        if not all([client_id, client_secret, refresh_token]):
            raise ValueError(
                "Single-tenant OAuth requires TASTYTRADE_CLIENT_ID, "
                "TASTYTRADE_CLIENT_SECRET, and TASTYTRADE_REFRESH_TOKEN in .env"
            )

        logger.info("Refreshing OAuth token from .env credentials")

        # Refresh the token
        refresh_url = "https://api.tastytrade.com/oauth/token"
        refresh_data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(refresh_url, data=refresh_data)

            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data['access_token']

                # Create session with OAuth token
                # The Session class needs a login parameter, but we'll override everything
                # Create a dummy session and inject our OAuth client
                from tastytrade import Account

                # Create HTTP client with OAuth token
                http_client = Client(base_url=API_URL)
                http_client.headers["Authorization"] = f"Bearer {access_token}"

                # Validate the token works
                response = http_client.get("/api-quote-tokens")
                if response.status_code != 200:
                    raise ValueError(f"Failed to validate OAuth session: {response.status_code}")

                # Get customer info to create proper session
                customer_response = http_client.get("/customers/me")
                if customer_response.status_code != 200:
                    raise ValueError(f"Failed to get customer info: {customer_response.status_code}")

                customer_data = customer_response.json()['data']

                # Create a mock session object that has the required attributes
                class OAuthSession:
                    def __init__(self, http_client, customer_data):
                        self._session = http_client
                        self.session_token = access_token
                        self.is_test = os.environ.get('TASTYTRADE_USE_PRODUCTION', 'true').lower() != 'true'
                        self.username = customer_data.get('email', 'oauth_user')

                        # Get accounts
                        accounts_response = http_client.get("/accounts")
                        if accounts_response.status_code == 200:
                            accounts_data = accounts_response.json()['data']['items']
                            self.accounts = [Account(**acc) for acc in accounts_data]
                        else:
                            self.accounts = []

                    def validate(self):
                        return True

                    def get_customer(self):
                        return customer_data

                session = OAuthSession(http_client, customer_data)
                logger.info("Successfully created OAuth session")
                return session
            else:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                error_msg = f"Failed to refresh OAuth token: {response.status_code} - {response.text}"
                logger.error(error_msg)

                # Check for expired refresh token
                if response.status_code == 400 and 'grant_id' in response.text.lower():
                    raise ValueError(
                        "OAuth refresh token has expired. Please update TASTYTRADE_REFRESH_TOKEN in your .env file. "
                        "To get a new refresh token:\n"
                        "1. Log into TastyTrade web/app\n"
                        "2. Go to API settings\n"
                        "3. Generate new OAuth tokens\n"
                        "4. Update .env with new TASTYTRADE_REFRESH_TOKEN"
                    )
                raise ValueError(error_msg)

    async def _get_default_user_id(self) -> Optional[str]:
        """
        Get default user ID from database (first user found).

        Returns:
            Optional[str]: User ID if found, None otherwise
        """
        try:
            database_url = self.settings.database_url
            if not database_url:
                return None

            conn = await asyncpg.connect(database_url)

            # Try to get user with 'bostrovsky' email first (primary user)
            user_data = await conn.fetchrow(
                "SELECT id FROM users WHERE email = 'bostrovsky' LIMIT 1"
            )

            if not user_data:
                # Fallback to any user
                user_data = await conn.fetchrow("SELECT id FROM users LIMIT 1")

            await conn.close()

            if user_data:
                user_id = str(user_data['id'])
                logger.info(f"Using default user ID: {user_id}")
                return user_id

            return None

        except Exception as e:
            logger.error(f"Failed to get default user: {e}")
            return None