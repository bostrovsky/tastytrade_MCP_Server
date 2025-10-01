"""Token storage for OAuth refresh tokens."""
import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class TokenStorage:
    """Store and retrieve OAuth tokens locally."""

    def __init__(self):
        # Store tokens in user's home directory
        self.token_dir = Path.home() / '.tastytrade_mcp'
        self.token_file = self.token_dir / 'tokens.json'

        # Create directory if it doesn't exist
        self.token_dir.mkdir(exist_ok=True)

        # Set permissions to user-only
        os.chmod(self.token_dir, 0o700)

    def save_tokens(self, client_id: str, refresh_token: str, access_token: Optional[str] = None) -> None:
        """Save tokens to local storage."""
        try:
            # Read existing tokens
            tokens = self.load_all_tokens()

            # Update tokens for this client_id
            tokens[client_id] = {
                'refresh_token': refresh_token,
                'access_token': access_token
            }

            # Write back to file
            with open(self.token_file, 'w') as f:
                json.dump(tokens, f, indent=2)

            # Set file permissions to user-only
            os.chmod(self.token_file, 0o600)

            logger.info(f"Saved new refresh token for client {client_id[:8]}...")

        except Exception as e:
            logger.error(f"Failed to save tokens: {e}")
            raise

    def load_tokens(self, client_id: str) -> Optional[Dict[str, str]]:
        """Load tokens for a specific client_id."""
        tokens = self.load_all_tokens()
        return tokens.get(client_id)

    def load_all_tokens(self) -> Dict[str, Dict[str, str]]:
        """Load all stored tokens."""
        if not self.token_file.exists():
            return {}

        try:
            with open(self.token_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load tokens: {e}")
            return {}

    def get_or_init_refresh_token(self, client_id: str) -> Optional[str]:
        """Get stored refresh token or initialize from environment."""
        # First check if we have a stored token
        stored = self.load_tokens(client_id)
        if stored and stored.get('refresh_token'):
            logger.info("Using stored refresh token")
            return stored['refresh_token']

        # Fall back to environment variable
        env_token = os.environ.get('TASTYTRADE_REFRESH_TOKEN')
        if env_token:
            logger.info("Initializing with refresh token from environment")
            # Save it for next time
            self.save_tokens(client_id, env_token)
            return env_token

        return None