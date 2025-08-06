"""Base adapter interface for platform integrations."""
import asyncio
import hashlib
import hmac
import json
import time
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional, Union
from urllib.parse import urljoin

import aiohttp
import structlog
from pydantic import BaseModel, Field

from app.models.ecommerce import Customer, Order, Product

logger = structlog.get_logger()


class APIResponse(BaseModel):
    """Unified API response model."""
    
    success: bool = Field(..., description="Whether the request was successful")
    data: Any = Field(None, description="Response data")
    error: Optional[str] = Field(None, description="Error message if any")
    status_code: int = Field(..., description="HTTP status code")
    platform: str = Field(..., description="Platform name")
    timestamp: datetime = Field(default_factory=datetime.now)


class SyncResult(BaseModel):
    """Result of data synchronization operation."""
    
    platform: str = Field(..., description="Platform name")
    operation: str = Field(..., description="Operation type (orders, products, customers)")
    records_processed: int = Field(..., description="Number of records processed")
    records_success: int = Field(..., description="Number of successful records")
    records_failed: int = Field(..., description="Number of failed records")
    errors: List[str] = Field(default_factory=list, description="Error messages")
    duration_seconds: float = Field(..., description="Operation duration")
    timestamp: datetime = Field(default_factory=datetime.now)


class RateLimitConfig(BaseModel):
    """Rate limiting configuration."""
    
    requests_per_minute: int = Field(default=60, description="Max requests per minute")
    requests_per_hour: int = Field(default=3600, description="Max requests per hour")
    burst_size: int = Field(default=10, description="Max burst requests")


class PlatformAdapter(ABC):
    """Abstract base class for platform adapters."""
    
    def __init__(
        self,
        api_key: str,
        base_url: str,
        platform_name: str,
        rate_limit_config: Optional[RateLimitConfig] = None,
        timeout: int = 30,
        max_retries: int = 3
    ):
        """Initialize the adapter.
        
        Args:
        ----
            api_key: API key for authentication
            base_url: Base URL for the platform API
            platform_name: Name of the platform
            rate_limit_config: Rate limiting configuration
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.platform_name = platform_name
        self.rate_limit_config = rate_limit_config or RateLimitConfig()
        self.timeout = timeout
        self.max_retries = max_retries
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Rate limiting state
        self._request_times: List[float] = []
        self._last_burst_reset = time.time()
        self._burst_count = 0
    
    @asynccontextmanager
    async def _get_session(self) -> AsyncIterator[aiohttp.ClientSession]:
        """Get an HTTP session for requests."""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
        
        try:
            yield self.session
        finally:
            # Keep session alive for reuse
            pass
    
    async def close(self):
        """Close the HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    def _check_rate_limit(self) -> bool:
        """Check if we can make a request without exceeding rate limits."""
        current_time = time.time()
        
        # Clean up old request times (older than 1 hour)
        self._request_times = [t for t in self._request_times if current_time - t < 3600]
        
        # Check hourly limit
        if len(self._request_times) >= self.rate_limit_config.requests_per_hour:
            return False
        
        # Check minute limit
        recent_requests = [t for t in self._request_times if current_time - t < 60]
        if len(recent_requests) >= self.rate_limit_config.requests_per_minute:
            return False
        
        # Check burst limit
        if current_time - self._last_burst_reset > 60:
            self._burst_count = 0
            self._last_burst_reset = current_time
        
        if self._burst_count >= self.rate_limit_config.burst_size:
            return False
        
        return True
    
    async def _wait_for_rate_limit(self):
        """Wait until we can make a request."""
        while not self._check_rate_limit():
            await asyncio.sleep(1)
    
    async def _make_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, str]] = None,
        retries: int = 0
    ) -> APIResponse:
        """Make an HTTP request with rate limiting and retries.
        
        Args:
        ----
            method: HTTP method (GET, POST, PUT, DELETE)
            url: Request URL (can be relative to base_url)
            headers: Additional headers
            data: Request body data
            params: URL parameters
            retries: Current retry attempt
            
        Returns:
        -------
            APIResponse: Unified response object
        """
        # Wait for rate limit
        await self._wait_for_rate_limit()
        
        # Record request time
        current_time = time.time()
        self._request_times.append(current_time)
        self._burst_count += 1
        
        # Prepare URL
        if not url.startswith('http'):
            url = urljoin(self.base_url + '/', url)
        
        # Prepare headers
        request_headers = await self._get_auth_headers()
        if headers:
            request_headers.update(headers)
        
        try:
            async with self._get_session() as session:
                logger.info(
                    "Making API request",
                    platform=self.platform_name,
                    method=method,
                    url=url,
                    retry_attempt=retries
                )
                
                async with session.request(
                    method=method,
                    url=url,
                    headers=request_headers,
                    json=data,
                    params=params
                ) as response:
                    response_data = None
                    try:
                        response_data = await response.json()
                    except Exception:
                        try:
                            response_data = await response.text()
                        except Exception:
                            response_data = None
                    
                    if response.status >= 400:
                        error_msg = f"HTTP {response.status}: {response_data}"
                        
                        # Retry on server errors or rate limits
                        if response.status >= 500 or response.status == 429:
                            if retries < self.max_retries:
                                wait_time = 2 ** retries  # Exponential backoff
                                logger.warning(
                                    "Request failed, retrying",
                                    platform=self.platform_name,
                                    status=response.status,
                                    retry_attempt=retries + 1,
                                    wait_time=wait_time
                                )
                                await asyncio.sleep(wait_time)
                                return await self._make_request(
                                    method, url, headers, data, params, retries + 1
                                )
                        
                        return APIResponse(
                            success=False,
                            error=error_msg,
                            status_code=response.status,
                            platform=self.platform_name
                        )
                    
                    return APIResponse(
                        success=True,
                        data=response_data,
                        status_code=response.status,
                        platform=self.platform_name
                    )
                    
        except Exception as e:
            error_msg = f"Request exception: {str(e)}"
            logger.error(
                "Request failed with exception",
                platform=self.platform_name,
                error=error_msg,
                retry_attempt=retries
            )
            
            # Retry on connection errors
            if retries < self.max_retries:
                wait_time = 2 ** retries
                logger.warning(
                    "Request exception, retrying",
                    platform=self.platform_name,
                    retry_attempt=retries + 1,
                    wait_time=wait_time
                )
                await asyncio.sleep(wait_time)
                return await self._make_request(
                    method, url, headers, data, params, retries + 1
                )
            
            return APIResponse(
                success=False,
                error=error_msg,
                status_code=0,
                platform=self.platform_name
            )
    
    @abstractmethod
    async def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for requests."""
        pass
    
    @abstractmethod
    async def test_connection(self) -> APIResponse:
        """Test the connection to the platform."""
        pass
    
    @abstractmethod
    async def sync_orders(self, limit: int = 100) -> SyncResult:
        """Synchronize orders from the platform."""
        pass
    
    @abstractmethod
    async def sync_products(self, limit: int = 100) -> SyncResult:
        """Synchronize products from the platform."""
        pass
    
    @abstractmethod
    async def sync_customers(self, limit: int = 100) -> SyncResult:
        """Synchronize customers from the platform."""
        pass
    
    @abstractmethod
    async def handle_webhook(self, payload: Dict[str, Any], signature: Optional[str] = None) -> bool:
        """Handle incoming webhook from the platform."""
        pass
    
    @abstractmethod
    def verify_webhook_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """Verify webhook signature."""
        pass
    
    def _verify_hmac_sha256(self, payload: bytes, signature: str, secret: str) -> bool:
        """Verify HMAC-SHA256 signature (common for many platforms)."""
        try:
            # Remove potential prefix like 'sha256='
            if signature.startswith('sha256='):
                signature = signature[7:]
            
            expected_signature = hmac.new(
                secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(expected_signature, signature)
        except Exception as e:
            logger.error("Signature verification failed", error=str(e))
            return False
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the adapter."""
        try:
            test_result = await self.test_connection()
            return {
                "platform": self.platform_name,
                "healthy": test_result.success,
                "last_check": datetime.now().isoformat(),
                "error": test_result.error if not test_result.success else None,
                "rate_limit_status": {
                    "requests_in_last_hour": len(self._request_times),
                    "burst_count": self._burst_count,
                    "can_make_request": self._check_rate_limit()
                }
            }
        except Exception as e:
            return {
                "platform": self.platform_name,
                "healthy": False,
                "last_check": datetime.now().isoformat(),
                "error": str(e)
            }


class PlatformManager:
    """Manager for coordinating multiple platform adapters."""
    
    def __init__(self):
        self.adapters: Dict[str, PlatformAdapter] = {}
    
    def register_adapter(self, name: str, adapter: PlatformAdapter):
        """Register a platform adapter."""
        self.adapters[name] = adapter
        logger.info("Platform adapter registered", platform=name)
    
    def get_adapter(self, name: str) -> Optional[PlatformAdapter]:
        """Get a platform adapter by name."""
        return self.adapters.get(name)
    
    async def sync_all_platforms(self, operation: str = "orders", limit: int = 100) -> List[SyncResult]:
        """Synchronize data across all registered platforms."""
        results = []
        tasks = []
        
        for name, adapter in self.adapters.items():
            if operation == "orders":
                task = adapter.sync_orders(limit)
            elif operation == "products":
                task = adapter.sync_products(limit)
            elif operation == "customers":
                task = adapter.sync_customers(limit)
            else:
                continue
            
            tasks.append(task)
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out exceptions and log them
            valid_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(
                        "Platform sync failed",
                        platform=list(self.adapters.keys())[i],
                        error=str(result)
                    )
                else:
                    valid_results.append(result)
            
            return valid_results
        
        return []
    
    async def get_all_health_status(self) -> Dict[str, Any]:
        """Get health status of all registered adapters."""
        health_status = {}
        
        for name, adapter in self.adapters.items():
            health_status[name] = await adapter.get_health_status()
        
        return {
            "platforms": health_status,
            "total_platforms": len(self.adapters),
            "healthy_platforms": sum(1 for status in health_status.values() if status.get("healthy", False)),
            "timestamp": datetime.now().isoformat()
        }
    
    async def close_all(self):
        """Close all adapter connections."""
        for adapter in self.adapters.values():
            await adapter.close()