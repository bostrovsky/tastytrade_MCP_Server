"""
OAuth Token Manager Service
Handles persistence, refresh, and rotation of OAuth tokens for TastyTrade API
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import asyncio
import asyncpg
from cryptography.fernet import Fernet
from tastytrade import Session
import httpx

logger = logging.getLogger(__name__)


class TokenEncryption:
    """Handles encryption/decryption of OAuth tokens"""

    def __init__(self, key: Optional[str] = None):
        """Initialize encryption with provided or generated key"""
        if key:
            self.cipher = Fernet(key.encode() if isinstance(key, str) else key)
        else:
            # Generate a new key if none provided (for development)
            key = os.environ.get('TOKEN_ENCRYPTION_KEY')
            if not key:
                logger.warning("No encryption key provided, generating one for development")
                key = Fernet.generate_key().decode()
                logger.info(f"Generated encryption key: {key}")
            self.cipher = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, token: str) -> str:
        """Encrypt a token string"""
        return self.cipher.encrypt(token.encode()).decode()

    def decrypt(self, encrypted_token: str) -> str:
        """Decrypt an encrypted token"""
        return self.cipher.decrypt(encrypted_token.encode()).decode()


class TokenManager:
    """Manages OAuth token lifecycle with PostgreSQL persistence"""

    def __init__(self, db_url: Optional[str] = None):
        """Initialize token manager with database connection"""
        self.db_url = db_url or os.environ.get(
            'DATABASE_URL',
            'postgresql://localhost/tastytrade_mcp'
        )
        self.encryption = TokenEncryption()
        self.pool: Optional[asyncpg.Pool] = None

    async def init_db(self):
        """Initialize database connection pool"""
        if not self.pool:
            self.pool = await asyncpg.create_pool(
                self.db_url,
                min_size=1,
                max_size=10,
                command_timeout=60
            )
            logger.info("Database connection pool initialized")

    async def close(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            self.pool = None

    async def store_tokens(
        self,
        user_id: str,
        environment: str,
        access_token: str,
        refresh_token: str,
        expires_in: int = 1200,  # Default 20 minutes for TastyTrade
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Store or update OAuth tokens in database

        Args:
            user_id: TastyTrade username or account ID
            environment: 'sandbox' or 'production'
            access_token: The OAuth access token
            refresh_token: The OAuth refresh token
            expires_in: Token expiration in seconds
            metadata: Optional metadata to store with tokens

        Returns:
            Dictionary with token ID and expiration time
        """
        await self.init_db()

        # Encrypt tokens
        encrypted_access = self.encryption.encrypt(access_token)
        encrypted_refresh = self.encryption.encrypt(refresh_token)

        # Calculate expiration time (use timezone-aware datetime)
        from datetime import timezone
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        query = """
            INSERT INTO oauth_tokens (
                user_id, environment, access_token, refresh_token,
                expires_at, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (user_id, environment)
            DO UPDATE SET
                access_token = EXCLUDED.access_token,
                refresh_token = EXCLUDED.refresh_token,
                expires_at = EXCLUDED.expires_at,
                updated_at = CURRENT_TIMESTAMP,
                rotation_count = oauth_tokens.rotation_count + 1,
                metadata = EXCLUDED.metadata
            RETURNING id, rotation_count
        """

        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(
                query,
                user_id,
                environment,
                encrypted_access,
                encrypted_refresh,
                expires_at,
                json.dumps(metadata or {})
            )

            # Log audit event
            await self._audit_log(
                conn,
                result['id'],
                'refreshed' if result['rotation_count'] > 0 else 'created',
                {'user_id': user_id, 'environment': environment}
            )

            logger.info(f"Tokens stored for {user_id} in {environment} environment")
            return {
                'token_id': str(result['id']),
                'expires_at': expires_at.isoformat(),
                'rotation_count': result['rotation_count']
            }

    async def get_valid_token(
        self,
        user_id: str,
        environment: str
    ) -> Optional[str]:
        """
        Retrieve a valid access token, refreshing if necessary

        Args:
            user_id: TastyTrade username
            environment: 'sandbox' or 'production'

        Returns:
            Valid access token or None if unable to obtain
        """
        await self.init_db()

        query = """
            SELECT id, access_token, refresh_token, expires_at
            FROM oauth_tokens
            WHERE user_id = $1 AND environment = $2
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, user_id, environment)

            if not row:
                logger.warning(f"No tokens found for {user_id} in {environment}")
                return None

            # Check if token is still valid (with 5 minute buffer)
            from datetime import timezone
            if row['expires_at'] > datetime.now(timezone.utc) + timedelta(minutes=5):
                # Token is still valid
                await self._update_last_used(conn, row['id'])
                return self.encryption.decrypt(row['access_token'])

            # Token expired or expiring soon, refresh it
            logger.info(f"Token expired/expiring for {user_id}, refreshing...")
            refresh_token = self.encryption.decrypt(row['refresh_token'])

            try:
                new_tokens = await self.refresh_token(
                    user_id,
                    environment,
                    refresh_token
                )
                return new_tokens.get('access_token')
            except Exception as e:
                logger.error(f"Failed to refresh token: {e}")
                await self._audit_log(
                    conn,
                    row['id'],
                    'failed_refresh',
                    {'error': str(e)}
                )
                return None

    async def refresh_token(
        self,
        user_id: str,
        environment: str,
        refresh_token: str
    ) -> Dict[str, Any]:
        """
        Refresh OAuth tokens using the refresh token

        Args:
            user_id: TastyTrade username
            environment: 'sandbox' or 'production'
            refresh_token: Current refresh token

        Returns:
            Dictionary with new tokens
        """
        # Determine the correct API URL
        base_url = (
            "https://api.cert.tastyworks.com"
            if environment == 'sandbox'
            else "https://api.tastyworks.com"
        )

        # Prepare refresh request
        client_id = os.environ.get('TASTYTRADE_CLIENT_ID')
        client_secret = os.environ.get('TASTYTRADE_CLIENT_SECRET')

        if not client_id or not client_secret:
            raise ValueError("OAuth client credentials not configured")

        # Make refresh request
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/oauth/token",
                data={
                    'grant_type': 'refresh_token',
                    'refresh_token': refresh_token,
                    'client_id': client_id,
                    'client_secret': client_secret
                }
            )

            if response.status_code != 200:
                raise Exception(f"Token refresh failed: {response.text}")

            token_data = response.json()

            # Store the new tokens
            await self.store_tokens(
                user_id=user_id,
                environment=environment,
                access_token=token_data['access_token'],
                refresh_token=token_data.get('refresh_token', refresh_token),
                expires_in=token_data.get('expires_in', 1200)
            )

            logger.info(f"Successfully refreshed tokens for {user_id}")
            return {
                'access_token': token_data['access_token'],
                'refresh_token': token_data.get('refresh_token', refresh_token),
                'expires_in': token_data.get('expires_in', 1200)
            }

    async def revoke_tokens(self, user_id: str, environment: str):
        """Revoke and delete tokens for a user"""
        await self.init_db()

        async with self.pool.acquire() as conn:
            # Get token ID for audit log
            row = await conn.fetchrow(
                "SELECT id FROM oauth_tokens WHERE user_id = $1 AND environment = $2",
                user_id,
                environment
            )

            if row:
                await self._audit_log(
                    conn,
                    row['id'],
                    'revoked',
                    {'user_id': user_id, 'manual': True}
                )

                # Delete the token
                await conn.execute(
                    "DELETE FROM oauth_tokens WHERE user_id = $1 AND environment = $2",
                    user_id,
                    environment
                )

                logger.info(f"Revoked tokens for {user_id} in {environment}")

    async def cleanup_expired_tokens(self) -> int:
        """Clean up expired tokens from database"""
        await self.init_db()

        async with self.pool.acquire() as conn:
            result = await conn.fetchval("SELECT cleanup_expired_tokens()")
            logger.info(f"Cleaned up {result} expired tokens")
            return result

    async def _audit_log(
        self,
        conn: asyncpg.Connection,
        token_id: str,
        event_type: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Create audit log entry"""
        await conn.execute(
            """
            INSERT INTO oauth_audit_log (token_id, event_type, details)
            VALUES ($1, $2, $3)
            """,
            token_id,
            event_type,
            json.dumps(details or {})
        )

    async def _update_last_used(self, conn: asyncpg.Connection, token_id: str):
        """Update last_used_at timestamp"""
        await conn.execute(
            "UPDATE oauth_tokens SET last_used_at = CURRENT_TIMESTAMP WHERE id = $1",
            token_id
        )


# Background task to periodically refresh tokens
async def token_refresh_scheduler(manager: TokenManager, interval_minutes: int = 15):
    """
    Background task to proactively refresh tokens before expiration

    Args:
        manager: TokenManager instance
        interval_minutes: How often to check for expiring tokens
    """
    while True:
        try:
            await asyncio.sleep(interval_minutes * 60)

            # Get all tokens expiring in next 10 minutes
            await manager.init_db()
            async with manager.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT user_id, environment, refresh_token
                    FROM oauth_tokens
                    WHERE expires_at < CURRENT_TIMESTAMP + INTERVAL '10 minutes'
                    AND expires_at > CURRENT_TIMESTAMP
                    """
                )

                for row in rows:
                    try:
                        refresh_token = manager.encryption.decrypt(row['refresh_token'])
                        await manager.refresh_token(
                            row['user_id'],
                            row['environment'],
                            refresh_token
                        )
                        logger.info(f"Proactively refreshed token for {row['user_id']}")
                    except Exception as e:
                        logger.error(f"Failed to refresh token for {row['user_id']}: {e}")

        except Exception as e:
            logger.error(f"Error in token refresh scheduler: {e}")
            await asyncio.sleep(60)  # Wait a minute before retrying