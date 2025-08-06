"""Security utilities for adapter integrations."""
import hashlib
import hmac
import json
import secrets
from datetime import datetime
from typing import Any

import structlog
from cryptography.fernet import Fernet
from pydantic import BaseModel, Field


logger = structlog.get_logger()


class CredentialStorage(BaseModel):
    """Secure credential storage model."""

    platform: str = Field(..., description="Platform name")
    user_id: str = Field(..., description="User ID")
    credentials: str = Field(..., description="Encrypted credentials")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    expires_at: datetime | None = Field(None, description="Credential expiration")
    is_active: bool = Field(default=True, description="Whether credentials are active")


class AuditLog(BaseModel):
    """Audit log entry model."""

    log_id: str = Field(..., description="Unique log entry ID")
    platform: str = Field(..., description="Platform name")
    user_id: str = Field(..., description="User ID")
    action: str = Field(..., description="Action performed")
    resource: str = Field(..., description="Resource accessed")
    method: str = Field(..., description="HTTP method")
    status_code: int = Field(..., description="Response status code")
    request_data: dict[str, Any] | None = Field(None, description="Request data (sanitized)")
    response_data: dict[str, Any] | None = Field(None, description="Response data (sanitized)")
    ip_address: str | None = Field(None, description="Client IP address")
    user_agent: str | None = Field(None, description="Client user agent")
    timestamp: datetime = Field(default_factory=datetime.now)
    duration_ms: float | None = Field(None, description="Request duration in milliseconds")
    error: str | None = Field(None, description="Error message if any")


class SecurityManager:
    """Security manager for handling credentials and audit logging."""

    def __init__(self, encryption_key: str | None = None):
        """Initialize security manager.

        Args:
        ----
            encryption_key: Base64-encoded encryption key. If None, generates a new one.

        """
        if encryption_key:
            self.fernet = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
        else:
            # Generate a new key - in production, this should be stored securely
            key = Fernet.generate_key()
            self.fernet = Fernet(key)
            logger.warning(
                "Generated new encryption key. In production, store this securely!",
                key=key.decode()
            )

        # In-memory storage for demo - replace with secure database in production
        self._credentials: dict[str, CredentialStorage] = {}
        self._audit_logs: list[AuditLog] = []

    def encrypt_credentials(self, credentials: dict[str, Any]) -> str:
        """Encrypt credentials for secure storage.

        Args:
        ----
            credentials: Dictionary of credentials to encrypt

        Returns:
        -------
            str: Encrypted credentials string

        """
        try:
            # Convert to JSON and encrypt
            credentials_json = json.dumps(credentials)
            encrypted = self.fernet.encrypt(credentials_json.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error("Failed to encrypt credentials", error=str(e))
            raise

    def decrypt_credentials(self, encrypted_credentials: str) -> dict[str, Any]:
        """Decrypt credentials from secure storage.

        Args:
        ----
            encrypted_credentials: Encrypted credentials string

        Returns:
        -------
            Dict[str, Any]: Decrypted credentials dictionary

        """
        try:
            # Decrypt and parse JSON
            decrypted = self.fernet.decrypt(encrypted_credentials.encode())
            return json.loads(decrypted.decode())
        except Exception as e:
            logger.error("Failed to decrypt credentials", error=str(e))
            raise

    def store_credentials(
        self,
        platform: str,
        user_id: str,
        credentials: dict[str, Any],
        expires_at: datetime | None = None
    ) -> bool:
        """Store encrypted credentials.

        Args:
        ----
            platform: Platform name
            user_id: User ID
            credentials: Credentials dictionary
            expires_at: Optional expiration datetime

        Returns:
        -------
            bool: Success status

        """
        try:
            # Encrypt credentials
            encrypted_creds = self.encrypt_credentials(credentials)

            # Create storage entry
            key = f"{platform}:{user_id}"
            storage_entry = CredentialStorage(
                platform=platform,
                user_id=user_id,
                credentials=encrypted_creds,
                expires_at=expires_at
            )

            # Update existing or create new
            if key in self._credentials:
                storage_entry.created_at = self._credentials[key].created_at
                storage_entry.updated_at = datetime.now()

            self._credentials[key] = storage_entry

            logger.info(
                "Stored encrypted credentials",
                platform=platform,
                user_id=user_id,
                expires_at=expires_at
            )
            return True

        except Exception as e:
            logger.error("Failed to store credentials", error=str(e), platform=platform, user_id=user_id)
            return False

    def retrieve_credentials(self, platform: str, user_id: str) -> dict[str, Any] | None:
        """Retrieve and decrypt credentials.

        Args:
        ----
            platform: Platform name
            user_id: User ID

        Returns:
        -------
            Optional[Dict[str, Any]]: Decrypted credentials or None if not found

        """
        try:
            key = f"{platform}:{user_id}"

            if key not in self._credentials:
                return None

            storage_entry = self._credentials[key]

            # Check if credentials are active
            if not storage_entry.is_active:
                logger.warning("Inactive credentials requested", platform=platform, user_id=user_id)
                return None

            # Check expiration
            if storage_entry.expires_at and datetime.now() > storage_entry.expires_at:
                logger.warning("Expired credentials requested", platform=platform, user_id=user_id)
                return None

            # Decrypt and return
            return self.decrypt_credentials(storage_entry.credentials)

        except Exception as e:
            logger.error("Failed to retrieve credentials", error=str(e), platform=platform, user_id=user_id)
            return None

    def delete_credentials(self, platform: str, user_id: str) -> bool:
        """Delete stored credentials.

        Args:
        ----
            platform: Platform name
            user_id: User ID

        Returns:
        -------
            bool: Success status

        """
        try:
            key = f"{platform}:{user_id}"

            if key in self._credentials:
                del self._credentials[key]
                logger.info("Deleted credentials", platform=platform, user_id=user_id)
                return True

            return False

        except Exception as e:
            logger.error("Failed to delete credentials", error=str(e), platform=platform, user_id=user_id)
            return False

    def rotate_credentials(
        self,
        platform: str,
        user_id: str,
        new_credentials: dict[str, Any],
        expires_at: datetime | None = None
    ) -> bool:
        """Rotate (update) stored credentials.

        Args:
        ----
            platform: Platform name
            user_id: User ID
            new_credentials: New credentials dictionary
            expires_at: Optional expiration datetime

        Returns:
        -------
            bool: Success status

        """
        logger.info("Rotating credentials", platform=platform, user_id=user_id)
        return self.store_credentials(platform, user_id, new_credentials, expires_at)

    def log_audit_event(
        self,
        platform: str,
        user_id: str,
        action: str,
        resource: str,
        method: str,
        status_code: int,
        request_data: dict[str, Any] | None = None,
        response_data: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        duration_ms: float | None = None,
        error: str | None = None
    ):
        """Log an audit event.

        Args:
        ----
            platform: Platform name
            user_id: User ID
            action: Action performed
            resource: Resource accessed
            method: HTTP method
            status_code: Response status code
            request_data: Request data (will be sanitized)
            response_data: Response data (will be sanitized)
            ip_address: Client IP address
            user_agent: Client user agent
            duration_ms: Request duration in milliseconds
            error: Error message if any

        """
        try:
            # Generate unique log ID
            log_id = secrets.token_hex(16)

            # Sanitize sensitive data
            sanitized_request = self._sanitize_data(request_data) if request_data else None
            sanitized_response = self._sanitize_data(response_data) if response_data else None

            # Create audit log entry
            audit_entry = AuditLog(
                log_id=log_id,
                platform=platform,
                user_id=user_id,
                action=action,
                resource=resource,
                method=method,
                status_code=status_code,
                request_data=sanitized_request,
                response_data=sanitized_response,
                ip_address=ip_address,
                user_agent=user_agent,
                duration_ms=duration_ms,
                error=error
            )

            # Store audit log
            self._audit_logs.append(audit_entry)

            # Log to structured logger
            logger.info(
                "API audit event",
                log_id=log_id,
                platform=platform,
                user_id=user_id,
                action=action,
                resource=resource,
                method=method,
                status_code=status_code,
                duration_ms=duration_ms,
                error=error
            )

        except Exception as e:
            logger.error("Failed to log audit event", error=str(e))

    def _sanitize_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Sanitize sensitive data for audit logging.

        Args:
        ----
            data: Data to sanitize

        Returns:
        -------
            Dict[str, Any]: Sanitized data

        """
        if not isinstance(data, dict):
            return {}

        # List of sensitive keys to redact
        sensitive_keys = {
            'password', 'token', 'secret', 'key', 'api_key', 'access_token',
            'refresh_token', 'client_secret', 'webhook_secret', 'auth',
            'authorization', 'credential', 'private'
        }

        sanitized = {}

        for key, value in data.items():
            key_lower = key.lower()

            # Check if key contains sensitive information
            is_sensitive = any(sensitive_word in key_lower for sensitive_word in sensitive_keys)

            if is_sensitive:
                # Redact sensitive values
                if isinstance(value, str) and value:
                    sanitized[key] = f"***{value[-4:]}" if len(value) > 4 else "***"
                else:
                    sanitized[key] = "***"
            elif isinstance(value, dict):
                # Recursively sanitize nested dictionaries
                sanitized[key] = self._sanitize_data(value)
            elif isinstance(value, list):
                # Sanitize lists of dictionaries
                sanitized[key] = [
                    self._sanitize_data(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                # Keep non-sensitive values as-is
                sanitized[key] = value

        return sanitized

    def get_audit_logs(
        self,
        platform: str | None = None,
        user_id: str | None = None,
        action: str | None = None,
        limit: int = 100
    ) -> list[AuditLog]:
        """Retrieve audit logs with optional filtering.

        Args:
        ----
            platform: Filter by platform
            user_id: Filter by user ID
            action: Filter by action
            limit: Maximum number of logs to return

        Returns:
        -------
            List[AuditLog]: Filtered audit logs

        """
        filtered_logs = self._audit_logs

        # Apply filters
        if platform:
            filtered_logs = [log for log in filtered_logs if log.platform == platform]

        if user_id:
            filtered_logs = [log for log in filtered_logs if log.user_id == user_id]

        if action:
            filtered_logs = [log for log in filtered_logs if log.action == action]

        # Sort by timestamp (newest first) and limit
        filtered_logs.sort(key=lambda x: x.timestamp, reverse=True)

        return filtered_logs[:limit]

    def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        secret: str,
        algorithm: str = "sha256"
    ) -> bool:
        """Verify webhook signature using HMAC.

        Args:
        ----
            payload: Raw webhook payload
            signature: Signature to verify
            secret: Webhook secret
            algorithm: Hash algorithm (sha256, sha1, etc.)

        Returns:
        -------
            bool: Whether signature is valid

        """
        try:
            # Remove common signature prefixes
            clean_signature = signature
            for prefix in ["sha256=", "sha1=", "hmac-"]:
                if clean_signature.startswith(prefix):
                    clean_signature = clean_signature[len(prefix):]
                    break

            # Create expected signature
            hash_func = getattr(hashlib, algorithm)
            expected_signature = hmac.new(
                secret.encode('utf-8'),
                payload,
                hash_func
            ).hexdigest()

            # Use constant-time comparison
            return hmac.compare_digest(expected_signature, clean_signature)

        except Exception as e:
            logger.error("Webhook signature verification failed", error=str(e))
            return False

    def generate_webhook_secret(self) -> str:
        """Generate a secure webhook secret.

        Returns
        -------
            str: Generated webhook secret

        """
        return secrets.token_urlsafe(32)

    def validate_input_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate and sanitize input data.

        Args:
        ----
            data: Input data to validate

        Returns:
        -------
            Dict[str, Any]: Validated and sanitized data

        """
        if not isinstance(data, dict):
            raise ValueError("Input data must be a dictionary")

        # Basic input validation and sanitization
        sanitized = {}

        for key, value in data.items():
            # Validate key
            if not isinstance(key, str):
                continue

            # Basic sanitization
            if isinstance(value, str):
                # Remove potentially dangerous characters
                value = value.replace('\x00', '').strip()
                # Limit string length
                if len(value) > 10000:
                    value = value[:10000]
            elif isinstance(value, int | float):
                # Validate numeric ranges
                if abs(value) > 1e15:  # Arbitrary large number limit
                    continue
            elif isinstance(value, dict):
                # Recursively validate nested dictionaries
                value = self.validate_input_data(value)
            elif isinstance(value, list):
                # Validate list items
                if len(value) > 1000:  # Limit list size
                    value = value[:1000]

                validated_list = []
                for item in value:
                    if isinstance(item, dict):
                        validated_list.append(self.validate_input_data(item))
                    elif isinstance(item, str):
                        item = item.replace('\x00', '').strip()
                        if len(item) <= 1000:
                            validated_list.append(item)
                    else:
                        validated_list.append(item)
                value = validated_list

            sanitized[key] = value

        return sanitized
