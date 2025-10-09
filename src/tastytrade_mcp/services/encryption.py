"""Encryption service with KMS support and local fallback."""
import base64
import logging
import os
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from tastytrade_mcp.config.settings import get_settings

logger = logging.getLogger(__name__)


class LocalEncryption:
    """Local encryption using Fernet (symmetric encryption)."""

    def __init__(self, key: Optional[str] = None):
        """Initialize with encryption key."""
        # Get settings at init time, not import time
        settings = get_settings()

        if key:
            # Use provided key
            self._key = key.encode() if isinstance(key, str) else key
        else:
            # Use key from settings
            self._key = settings.encryption_key.encode()

        # Get salt from settings or generate random one
        salt = settings.encryption_salt
        if not salt:
            # Generate a random salt if not configured
            salt = os.urandom(16)
            logger.warning("No encryption salt configured, generated random salt. "
                         "Configure TASTYTRADE_ENCRYPTION_SALT for consistent encryption.")
        elif isinstance(salt, str):
            # Convert hex string to bytes if necessary
            salt = bytes.fromhex(salt)

        # Derive a proper Fernet key from the provided key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=settings.encryption_pbkdf2_iterations if hasattr(settings, 'encryption_pbkdf2_iterations') else 100000,
            backend=default_backend()
        )
        key_bytes = base64.urlsafe_b64encode(kdf.derive(self._key))
        self._fernet = Fernet(key_bytes)
    
    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext string."""
        encrypted = self._fernet.encrypt(plaintext.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt(self, ciphertext: str) -> str:
        """Decrypt ciphertext string."""
        decoded = base64.urlsafe_b64decode(ciphertext.encode())
        decrypted = self._fernet.decrypt(decoded)
        return decrypted.decode()


class KMSStub:
    """
    Stub KMS service for local development.
    In production, this would integrate with AWS KMS, Azure Key Vault, etc.
    """
    
    def __init__(self):
        """Initialize KMS stub."""
        self._data_keys: dict[str, bytes] = {}
        self._master_key = Fernet.generate_key()
        self._fernet = Fernet(self._master_key)
        logger.info("Using KMS stub for local development")
    
    async def generate_data_key(self, key_id: str = "default") -> tuple[bytes, bytes]:
        """
        Generate a data encryption key.
        Returns (plaintext_key, encrypted_key).
        """
        # Generate a new data key
        data_key = Fernet.generate_key()
        
        # Encrypt the data key with the master key
        encrypted_data_key = self._fernet.encrypt(data_key)
        
        # Store for later decryption (in production, this wouldn't be stored)
        self._data_keys[key_id] = data_key
        
        return data_key, encrypted_data_key
    
    async def decrypt_data_key(self, encrypted_key: bytes) -> bytes:
        """Decrypt a data encryption key."""
        return self._fernet.decrypt(encrypted_key)
    
    async def encrypt(self, plaintext: bytes, key_id: str = "default") -> bytes:
        """Encrypt data directly with KMS (for small data only)."""
        return self._fernet.encrypt(plaintext)
    
    async def decrypt(self, ciphertext: bytes) -> bytes:
        """Decrypt data directly with KMS."""
        return self._fernet.decrypt(ciphertext)


class EncryptionService:
    """
    Main encryption service with KMS integration.
    Uses envelope encryption for large data.
    """
    
    def __init__(self):
        """Initialize encryption service."""
        self._local_encryption = LocalEncryption()
        self._kms: Optional[KMSStub] = None
        self._use_kms = os.getenv("USE_KMS", "false").lower() == "true"
        self._data_keys_cache: dict[str, bytes] = {}
    
    async def initialize(self) -> None:
        """Initialize KMS connection if enabled."""
        if self._use_kms:
            self._kms = KMSStub()  # In production, initialize real KMS client
            logger.info("KMS encryption enabled")
        else:
            logger.info("Using local encryption (KMS disabled)")
    
    async def encrypt_token(self, token: str, token_type: str = "oauth") -> str:
        """
        Encrypt an OAuth or API token.
        Uses KMS if available, falls back to local encryption.
        """
        if self._kms:
            # Use KMS envelope encryption
            key_id = f"token-{token_type}"
            
            # Get or generate data key
            if key_id not in self._data_keys_cache:
                data_key, encrypted_key = await self._kms.generate_data_key(key_id)
                self._data_keys_cache[key_id] = data_key
            else:
                data_key = self._data_keys_cache[key_id]
            
            # Encrypt token with data key
            fernet = Fernet(data_key)
            encrypted = fernet.encrypt(token.encode())
            
            # Return base64-encoded result
            return base64.urlsafe_b64encode(encrypted).decode()
        else:
            # Use local encryption
            return self._local_encryption.encrypt(token)
    
    async def decrypt_token(self, encrypted_token: str, token_type: str = "oauth") -> str:
        """
        Decrypt an OAuth or API token.
        Uses KMS if available, falls back to local encryption.
        """
        if self._kms:
            # Use KMS envelope encryption
            key_id = f"token-{token_type}"
            
            # Get data key from cache (in production, would decrypt from stored encrypted key)
            if key_id not in self._data_keys_cache:
                raise ValueError(f"No data key found for {key_id}")
            
            data_key = self._data_keys_cache[key_id]
            
            # Decrypt token with data key
            fernet = Fernet(data_key)
            decoded = base64.urlsafe_b64decode(encrypted_token.encode())
            decrypted = fernet.decrypt(decoded)
            
            return decrypted.decode()
        else:
            # Use local encryption
            return self._local_encryption.decrypt(encrypted_token)
    
    def encrypt_field(self, value: str) -> str:
        """
        Encrypt a database field value.
        This uses local encryption for performance.
        """
        return self._local_encryption.encrypt(value)
    
    def decrypt_field(self, encrypted_value: str) -> str:
        """
        Decrypt a database field value.
        This uses local encryption for performance.
        """
        return self._local_encryption.decrypt(encrypted_value)
    
    def hash_value(self, value: str) -> str:
        """
        Create a one-way hash of a value.
        Used for values that need to be searchable but not reversible.
        """
        import hashlib

        # Add salt from settings
        settings = get_settings()
        salted = f"{settings.secret_key}:{value}"
        return hashlib.sha256(salted.encode()).hexdigest()
    
    def verify_hash(self, value: str, hash_value: str) -> bool:
        """Verify a value matches a hash."""
        return self.hash_value(value) == hash_value


# Global encryption service instance
_encryption_service: Optional[EncryptionService] = None


async def get_encryption_service() -> EncryptionService:
    """Get global encryption service instance."""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
        await _encryption_service.initialize()
    return _encryption_service