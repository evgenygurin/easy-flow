"""Система безопасного хранения учетных данных для интеграций."""
import base64
import os
from cryptography.fernet import Fernet
from typing import Any

import structlog


logger = structlog.get_logger()


class CredentialManager:
    """Менеджер для безопасного хранения и получения учетных данных."""

    def __init__(self, encryption_key: str | None = None):
        if encryption_key:
            self.fernet = Fernet(encryption_key.encode())
        else:
            # Генерируем или получаем ключ из переменных окружения
            key = os.getenv("ENCRYPTION_KEY")
            if not key:
                key = Fernet.generate_key().decode()
                logger.warning("Сгенерирован новый ключ шифрования. Сохраните его в ENCRYPTION_KEY")
                logger.info(f"ENCRYPTION_KEY={key}")
            
            self.fernet = Fernet(key.encode())

    def encrypt_credentials(self, credentials: dict[str, str]) -> str:
        """Зашифровать учетные данные."""
        try:
            import json
            credential_json = json.dumps(credentials)
            encrypted_data = self.fernet.encrypt(credential_json.encode())
            return base64.b64encode(encrypted_data).decode()
        except Exception as e:
            logger.error("Ошибка шифрования учетных данных", error=str(e))
            raise

    def decrypt_credentials(self, encrypted_credentials: str) -> dict[str, str]:
        """Расшифровать учетные данные."""
        try:
            import json
            encrypted_data = base64.b64decode(encrypted_credentials.encode())
            decrypted_data = self.fernet.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
        except Exception as e:
            logger.error("Ошибка расшифровки учетных данных", error=str(e))
            raise

    def validate_credentials(self, platform: str, credentials: dict[str, str]) -> bool:
        """Валидация учетных данных для платформы."""
        validation_rules = {
            "wildberries": ["api_key"],
            "ozon": ["client_id", "api_key"],
            "1c-bitrix": ["webhook_url", "client_id", "client_secret"],
            "insales": ["domain", "api_key", "password"],
            "shopify": ["shop_domain", "access_token"],
            "woocommerce": ["site_url", "consumer_key", "consumer_secret"],
            "telegram": ["bot_token"],
            "whatsapp": ["access_token", "phone_number_id"],
        }

        required_fields = validation_rules.get(platform, [])
        missing_fields = [field for field in required_fields if not credentials.get(field)]

        if missing_fields:
            logger.error(
                "Отсутствуют обязательные поля для платформы",
                platform=platform,
                missing_fields=missing_fields
            )
            return False

        return True

    def mask_sensitive_data(self, credentials: dict[str, str]) -> dict[str, str]:
        """Замаскировать чувствительные данные для логирования."""
        masked = {}
        sensitive_keys = ["api_key", "password", "secret", "token", "client_secret"]
        
        for key, value in credentials.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                if len(value) > 8:
                    masked[key] = f"{value[:4]}...{value[-4:]}"
                else:
                    masked[key] = "***"
            else:
                masked[key] = value

        return masked


class AuditLogger:
    """Логирование всех операций с интеграциями для аудита."""

    def __init__(self):
        self.logger = structlog.get_logger().bind(component="audit")

    def log_integration_event(
        self,
        event_type: str,
        platform: str,
        user_id: str,
        details: dict[str, Any] | None = None
    ):
        """Логировать событие интеграции."""
        self.logger.info(
            "Событие интеграции",
            event_type=event_type,
            platform=platform,
            user_id=user_id,
            details=details or {}
        )

    def log_api_call(
        self,
        platform: str,
        method: str,
        endpoint: str,
        status_code: int,
        response_time_ms: float,
        user_id: str | None = None
    ):
        """Логировать API вызовы."""
        self.logger.info(
            "API вызов",
            platform=platform,
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            response_time_ms=response_time_ms,
            user_id=user_id
        )

    def log_webhook_received(
        self,
        platform: str,
        event_type: str,
        payload_size: int,
        processing_time_ms: float
    ):
        """Логировать получение webhook."""
        self.logger.info(
            "Webhook получен",
            platform=platform,
            event_type=event_type,
            payload_size=payload_size,
            processing_time_ms=processing_time_ms
        )

    def log_error(
        self,
        error_type: str,
        platform: str,
        error_message: str,
        user_id: str | None = None,
        additional_data: dict[str, Any] | None = None
    ):
        """Логировать ошибки."""
        self.logger.error(
            "Ошибка интеграции",
            error_type=error_type,
            platform=platform,
            error_message=error_message,
            user_id=user_id,
            additional_data=additional_data or {}
        )


class SecurityValidator:
    """Валидатор безопасности для интеграций."""

    @staticmethod
    def validate_webhook_signature(
        payload: bytes,
        signature: str,
        secret: str,
        algorithm: str = "sha256"
    ) -> bool:
        """Проверить подпись webhook."""
        import hashlib
        import hmac

        try:
            if algorithm == "sha256":
                expected_signature = hmac.new(
                    secret.encode(),
                    payload,
                    hashlib.sha256
                ).hexdigest()
            elif algorithm == "sha1":
                expected_signature = hmac.new(
                    secret.encode(),
                    payload,
                    hashlib.sha1
                ).hexdigest()
            else:
                raise ValueError(f"Неподдерживаемый алгоритм: {algorithm}")

            return hmac.compare_digest(signature, expected_signature)

        except Exception as e:
            logger.error("Ошибка проверки подписи webhook", error=str(e))
            return False

    @staticmethod
    def sanitize_input(data: dict[str, Any]) -> dict[str, Any]:
        """Очистить входные данные от потенциально опасного содержимого."""
        sanitized = {}
        
        for key, value in data.items():
            if isinstance(value, str):
                # Удаляем потенциально опасные символы
                sanitized_value = value.replace("<script>", "").replace("</script>", "")
                sanitized_value = sanitized_value.replace("javascript:", "")
                sanitized[key] = sanitized_value
            elif isinstance(value, dict):
                sanitized[key] = SecurityValidator.sanitize_input(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    SecurityValidator.sanitize_input(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                sanitized[key] = value

        return sanitized

    @staticmethod
    def validate_api_response(response_data: dict[str, Any]) -> bool:
        """Валидировать ответ API на предмет безопасности."""
        # Проверяем на наличие потенциально опасных данных
        dangerous_patterns = [
            "<script>",
            "javascript:",
            "eval(",
            "exec(",
            "system(",
            "shell_exec("
        ]

        def check_recursive(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if not check_recursive(value):
                        return False
            elif isinstance(obj, list):
                for item in obj:
                    if not check_recursive(item):
                        return False
            elif isinstance(obj, str):
                for pattern in dangerous_patterns:
                    if pattern.lower() in obj.lower():
                        logger.warning("Обнаружен подозрительный паттерн в ответе API", pattern=pattern)
                        return False

            return True

        return check_recursive(response_data)


class RateLimitManager:
    """Менеджер лимитов запросов для разных платформ."""

    def __init__(self):
        self.platform_limits = {
            "wildberries": {"requests_per_minute": 60, "requests_per_hour": 3600},
            "ozon": {"requests_per_minute": 1000, "requests_per_hour": 60000},
            "1c-bitrix": {"requests_per_minute": 120, "requests_per_hour": 7200},
            "insales": {"requests_per_minute": 120, "requests_per_hour": 7200},
            "shopify": {"requests_per_minute": 40, "requests_per_hour": 2400},
            "woocommerce": {"requests_per_minute": 100, "requests_per_hour": 6000}
        }
        
        # Счетчики запросов (в реальности должны храниться в Redis)
        self.request_counters = {}

    def can_make_request(self, platform: str, user_id: str) -> tuple[bool, int]:
        """Проверить, можно ли сделать запрос."""
        limits = self.platform_limits.get(platform, {"requests_per_minute": 60})
        key = f"{platform}:{user_id}"
        
        # Простая реализация - в продакшене нужно использовать Redis
        current_count = self.request_counters.get(key, 0)
        max_requests = limits["requests_per_minute"]
        
        if current_count >= max_requests:
            return False, max_requests - current_count
        
        return True, max_requests - current_count

    def record_request(self, platform: str, user_id: str):
        """Зафиксировать выполненный запрос."""
        key = f"{platform}:{user_id}"
        self.request_counters[key] = self.request_counters.get(key, 0) + 1

    def reset_counters(self, platform: str = None):
        """Сбросить счетчики (должно вызываться периодически)."""
        if platform:
            keys_to_reset = [key for key in self.request_counters.keys() if key.startswith(f"{platform}:")]
            for key in keys_to_reset:
                self.request_counters[key] = 0
        else:
            self.request_counters.clear()


# Глобальные экземпляры
credential_manager = CredentialManager()
audit_logger = AuditLogger()
security_validator = SecurityValidator()
rate_limit_manager = RateLimitManager()