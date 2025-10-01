"""JWT service for API authentication."""
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from uuid import UUID

from jose import JWTError, jwt
from pydantic import BaseModel

from tastytrade_mcp.config.settings import get_settings
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class TokenData(BaseModel):
    """JWT token payload data."""
    
    sub: str  # Subject (user_id)
    exp: datetime  # Expiration
    iat: datetime  # Issued at
    jti: Optional[str] = None  # JWT ID for revocation
    scope: Optional[str] = None  # Permissions scope
    broker_linked: bool = False  # Whether broker is linked
    is_sandbox: bool = True  # Sandbox mode


class JWTService:
    """Service for creating and validating JWT tokens."""
    
    def __init__(self):
        """Initialize JWT service."""
        self.secret_key = settings.secret_key
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 60  # 1 hour
        self.refresh_token_expire_days = 30
    
    def create_access_token(
        self,
        user_id: UUID,
        broker_linked: bool = False,
        is_sandbox: bool = True,
        scope: Optional[str] = None,
    ) -> str:
        """
        Create a JWT access token.
        
        Args:
            user_id: User ID to encode
            broker_linked: Whether user has linked broker
            is_sandbox: Whether using sandbox mode
            scope: Optional permissions scope
        
        Returns:
            Encoded JWT token
        """
        now = datetime.utcnow()
        expire = now + timedelta(minutes=self.access_token_expire_minutes)
        
        payload = {
            "sub": str(user_id),
            "exp": expire,
            "iat": now,
            "type": "access",
            "broker_linked": broker_linked,
            "is_sandbox": is_sandbox,
        }
        
        if scope:
            payload["scope"] = scope
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        
        logger.info(
            "Access token created",
            extra={
                "user_id": str(user_id),
                "expires_in": self.access_token_expire_minutes * 60,
            }
        )
        
        return token
    
    def create_refresh_token(self, user_id: UUID) -> str:
        """
        Create a JWT refresh token.
        
        Args:
            user_id: User ID to encode
        
        Returns:
            Encoded JWT refresh token
        """
        now = datetime.utcnow()
        expire = now + timedelta(days=self.refresh_token_expire_days)
        
        payload = {
            "sub": str(user_id),
            "exp": expire,
            "iat": now,
            "type": "refresh",
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        
        logger.info(
            "Refresh token created",
            extra={
                "user_id": str(user_id),
                "expires_in_days": self.refresh_token_expire_days,
            }
        )
        
        return token
    
    def decode_token(self, token: str) -> TokenData:
        """
        Decode and validate a JWT token.
        
        Args:
            token: JWT token to decode
        
        Returns:
            TokenData with decoded payload
        
        Raises:
            JWTError: If token is invalid or expired
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            
            # Convert timestamps
            if "exp" in payload:
                payload["exp"] = datetime.fromtimestamp(payload["exp"])
            if "iat" in payload:
                payload["iat"] = datetime.fromtimestamp(payload["iat"])
            
            return TokenData(**payload)
            
        except JWTError as e:
            logger.warning(f"JWT decode error: {e}")
            raise
    
    def verify_token(self, token: str, token_type: str = "access") -> Optional[TokenData]:
        """
        Verify a token and return its data.
        
        Args:
            token: JWT token to verify
            token_type: Expected token type (access/refresh)
        
        Returns:
            TokenData if valid, None otherwise
        """
        try:
            token_data = self.decode_token(token)
            
            # Check token type
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            
            if payload.get("type") != token_type:
                logger.warning(f"Invalid token type: expected {token_type}")
                return None
            
            return token_data
            
        except JWTError:
            return None
    
    def refresh_access_token(
        self,
        refresh_token: str,
        broker_linked: bool = False,
        is_sandbox: bool = True,
    ) -> Optional[str]:
        """
        Create a new access token from a refresh token.
        
        Args:
            refresh_token: Valid refresh token
            broker_linked: Current broker link status
            is_sandbox: Current sandbox mode
        
        Returns:
            New access token if refresh token is valid, None otherwise
        """
        token_data = self.verify_token(refresh_token, token_type="refresh")
        
        if not token_data:
            return None
        
        # Create new access token with updated status
        return self.create_access_token(
            user_id=UUID(token_data.sub),
            broker_linked=broker_linked,
            is_sandbox=is_sandbox,
        )


# Global JWT service instance
_jwt_service: Optional[JWTService] = None


def get_jwt_service() -> JWTService:
    """Get global JWT service instance."""
    global _jwt_service
    if _jwt_service is None:
        _jwt_service = JWTService()
    return _jwt_service