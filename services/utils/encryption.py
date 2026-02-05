"""
Encryption utilities for sensitive data (API keys, passwords, etc.)

Uses Fernet symmetric encryption (built on AES-128-CBC).
Encryption key is stored in environment variable.
"""
import os
import base64
from cryptography.fernet import Fernet
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Load encryption key from environment or generate one
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

if not ENCRYPTION_KEY:
    logger.warning("⚠️  ENCRYPTION_KEY not set in environment. Generating temporary key (NOT FOR PRODUCTION!)")
    # Generate a key for development ONLY
    # In production, you MUST set ENCRYPTION_KEY in .env
    ENCRYPTION_KEY = Fernet.generate_key().decode()
    logger.warning(f"⚠️  Temporary key: {ENCRYPTION_KEY}")
    logger.warning("⚠️  Add this to your .env file: ENCRYPTION_KEY={ENCRYPTION_KEY}")

# Initialize cipher
try:
    cipher = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)
except Exception as e:
    logger.error(f"❌ Failed to initialize cipher: {e}")
    logger.error("❌ ENCRYPTION_KEY must be a valid Fernet key (32 url-safe base64-encoded bytes)")
    raise


def encrypt_value(plaintext: str) -> str:
    """
    Encrypt a string value.
    
    Args:
        plaintext: The value to encrypt (e.g., password, API key)
        
    Returns:
        Encrypted value as base64 string (prefixed with "enc:")
        
    Example:
        >>> encrypt_value("my_secret_password")
        "enc:gAAAAABl..."
    """
    if not plaintext:
        return plaintext
    
    try:
        encrypted_bytes = cipher.encrypt(plaintext.encode())
        encrypted_str = base64.b64encode(encrypted_bytes).decode()
        return f"enc:{encrypted_str}"
    except Exception as e:
        logger.error(f"❌ Encryption failed: {e}")
        raise


def decrypt_value(ciphertext: str) -> str:
    """
    Decrypt an encrypted value.
    
    Args:
        ciphertext: Encrypted value (prefixed with "enc:")
        
    Returns:
        Decrypted plaintext string
        
    Example:
        >>> decrypt_value("enc:gAAAAABl...")
        "my_secret_password"
    """
    if not ciphertext:
        return ciphertext
    
    # If not encrypted (no prefix), return as-is
    if not ciphertext.startswith("enc:"):
        logger.warning(f"⚠️  Value not encrypted (missing 'enc:' prefix)")
        return ciphertext
    
    try:
        # Remove "enc:" prefix and decode base64
        encrypted_str = ciphertext[4:]  # Remove "enc:" prefix
        encrypted_bytes = base64.b64decode(encrypted_str)
        
        # Decrypt
        plaintext_bytes = cipher.decrypt(encrypted_bytes)
        return plaintext_bytes.decode()
    except Exception as e:
        logger.error(f"❌ Decryption failed: {e}")
        raise


def encrypt_dict(data: dict, fields_to_encrypt: list) -> dict:
    """
    Encrypt specific fields in a dictionary.
    
    Args:
        data: Dictionary containing sensitive fields
        fields_to_encrypt: List of field names to encrypt
        
    Returns:
        Dictionary with specified fields encrypted
        
    Example:
        >>> auth = {"username": "user", "password": "secret", "host": "localhost"}
        >>> encrypt_dict(auth, ["password"])
        {"username": "user", "password": "enc:gAAAAABl...", "host": "localhost"}
    """
    encrypted_data = data.copy()
    
    for field in fields_to_encrypt:
        if field in encrypted_data and encrypted_data[field]:
            encrypted_data[field] = encrypt_value(str(encrypted_data[field]))
    
    return encrypted_data


def decrypt_dict(data: dict, fields_to_decrypt: list) -> dict:
    """
    Decrypt specific fields in a dictionary.
    
    Args:
        data: Dictionary containing encrypted fields
        fields_to_decrypt: List of field names to decrypt
        
    Returns:
        Dictionary with specified fields decrypted
        
    Example:
        >>> auth = {"username": "user", "password": "enc:gAAAAABl...", "host": "localhost"}
        >>> decrypt_dict(auth, ["password"])
        {"username": "user", "password": "secret", "host": "localhost"}
    """
    decrypted_data = data.copy()
    
    for field in fields_to_decrypt:
        if field in decrypted_data and decrypted_data[field]:
            decrypted_data[field] = decrypt_value(str(decrypted_data[field]))
    
    return decrypted_data


def is_encrypted(value: str) -> bool:
    """
    Check if a value is encrypted.
    
    Args:
        value: String to check
        
    Returns:
        True if value starts with "enc:", False otherwise
    """
    return isinstance(value, str) and value.startswith("enc:")


# Fields that should always be encrypted
SENSITIVE_FIELDS = [
    "password",
    "api_key",
    "api_secret",
    "access_token",
    "refresh_token",
    "client_secret",
    "private_key",
]


def encrypt_authentication_details(auth_details: dict) -> dict:
    """
    Encrypt all sensitive fields in authentication_details.
    
    Args:
        auth_details: Authentication details dictionary
        
    Returns:
        Dictionary with sensitive fields encrypted
    """
    return encrypt_dict(auth_details, SENSITIVE_FIELDS)


def decrypt_authentication_details(auth_details: dict) -> dict:
    """
    Decrypt all sensitive fields in authentication_details.
    
    Args:
        auth_details: Authentication details dictionary with encrypted fields
        
    Returns:
        Dictionary with sensitive fields decrypted
    """
    return decrypt_dict(auth_details, SENSITIVE_FIELDS)


# Utility to generate a new encryption key
def generate_encryption_key() -> str:
    """
    Generate a new Fernet encryption key.
    
    Returns:
        Base64-encoded key suitable for ENCRYPTION_KEY environment variable
        
    Usage:
        Run this once to generate a key, then add to .env:
        ENCRYPTION_KEY=<generated_key>
    """
    key = Fernet.generate_key()
    return key.decode()


if __name__ == "__main__":
    # Generate a new key for initial setup
    print("=== Encryption Key Generator ===")
    print()
    print("Generated encryption key (add to .env file):")
    print()
    print(f"ENCRYPTION_KEY={generate_encryption_key()}")
    print()
    print("⚠️  Keep this key secret! If you lose it, you cannot decrypt existing data.")
    print("⚠️  Store it securely (e.g., AWS Secrets Manager, 1Password, etc.)")
