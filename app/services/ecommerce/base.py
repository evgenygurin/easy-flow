"""Base classes for e-commerce platform integrations."""
import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import httpx
import structlog
from pydantic import BaseModel, Field

from app.models.ecommerce import Customer, Order, Product

logger = structlog.get_logger()


class PlatformCredentials(BaseModel):
    """Base credentials model."""
    
    platform_id: str = Field(..., description="Platform identifier")
    created_at: datetime = Field(default_factory=datetime.now)


class APIResponse(BaseModel):
    """Unified API response model."""
    
    success: bool = Field(..., description="Operation success")
    data: Any = Field(None, description="Response data")
    error_message: str | None = Field(None, description="Error message")
    status_code: int | None = Field(None, description="HTTP status code")
    rate_limit_remaining: int | None = Field(None, description="Rate limit remaining")


class SyncResult(BaseModel):
    """Platform synchronization result."""
    
    platform: str = Field(..., description="Platform name")
    sync_type: str = Field(..., description="Type of sync (orders, products, customers)")
    records_processed: int = Field(default=0, description="Records processed")
    records_updated: int = Field(default=0, description="Records updated")
    records_created: int = Field(default=0, description="Records created")
    errors: list[str] = Field(default_factory=list, description="Sync errors")
    sync_time: datetime = Field(default_factory=datetime.now)
    duration_seconds: float = Field(default=0.0, description="Sync duration")


class PlatformAdapter(ABC):
    """Abstract base class for e-commerce platform adapters."""
    
    def __init__(self, credentials: dict[str, Any], config: dict[str, Any] | None = None):
        self.credentials = credentials
        self.config = config or {}
        self.client = httpx.AsyncClient(timeout=30.0)
        self.platform_name = self.__class__.__name__.replace('Adapter', '').lower()
        
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()
    
    @abstractmethod
    async def authenticate(self) -> APIResponse:
        """Authenticate with platform API."""
        pass
    
    @abstractmethod
    async def get_orders(
        self, 
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None
    ) -> APIResponse:
        """Fetch orders from platform."""
        pass
    
    @abstractmethod
    async def get_products(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None
    ) -> APIResponse:
        """Fetch products from platform."""
        pass
    
    @abstractmethod
    async def get_customers(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None
    ) -> APIResponse:
        """Fetch customers from platform."""
        pass
    
    @abstractmethod
    async def update_order_status(self, order_id: str, status: str) -> APIResponse:
        """Update order status on platform."""
        pass
    
    @abstractmethod
    async def handle_webhook(self, payload: dict[str, Any]) -> APIResponse:
        """Handle incoming webhook from platform."""
        pass
    
    @abstractmethod
    def transform_order(self, raw_order: dict[str, Any]) -> Order | None:
        """Transform platform-specific order data to unified format."""
        pass
    
    @abstractmethod
    def transform_product(self, raw_product: dict[str, Any]) -> Product | None:
        """Transform platform-specific product data to unified format."""
        pass
    
    @abstractmethod
    def transform_customer(self, raw_customer: dict[str, Any]) -> Customer | None:
        """Transform platform-specific customer data to unified format."""
        pass
    
    async def test_connection(self) -> APIResponse:
        """Test platform API connection."""
        try:
            result = await self.authenticate()
            if result.success:
                logger.info(f"Connection test successful for {self.platform_name}")
            else:
                logger.error(f"Connection test failed for {self.platform_name}: {result.error_message}")
            return result
        except Exception as e:
            logger.error(f"Connection test error for {self.platform_name}", error=str(e))
            return APIResponse(
                success=False,
                error_message=f"Connection test failed: {str(e)}"
            )
    
    async def sync_data(self, sync_types: list[str] | None = None) -> list[SyncResult]:
        """Perform data synchronization."""
        if sync_types is None:
            sync_types = ["orders", "products", "customers"]
        
        results = []
        
        for sync_type in sync_types:
            start_time = datetime.now()
            result = SyncResult(
                platform=self.platform_name,
                sync_type=sync_type
            )
            
            try:
                if sync_type == "orders":
                    api_result = await self.get_orders(limit=1000)
                elif sync_type == "products":
                    api_result = await self.get_products(limit=1000)
                elif sync_type == "customers":
                    api_result = await self.get_customers(limit=1000)
                else:
                    result.errors.append(f"Unknown sync type: {sync_type}")
                    results.append(result)
                    continue
                
                if api_result.success and api_result.data:
                    result.records_processed = len(api_result.data)
                    # In real implementation, would save to database here
                    result.records_updated = result.records_processed
                    logger.info(
                        f"Synced {sync_type} for {self.platform_name}",
                        records=result.records_processed
                    )
                else:
                    result.errors.append(api_result.error_message or "Unknown error")
                
            except Exception as e:
                error_msg = f"Sync failed for {sync_type}: {str(e)}"
                result.errors.append(error_msg)
                logger.error(error_msg, platform=self.platform_name)
            
            finally:
                end_time = datetime.now()
                result.duration_seconds = (end_time - start_time).total_seconds()
                results.append(result)
        
        return results
    
    async def make_request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None
    ) -> APIResponse:
        """Make HTTP request with error handling."""
        try:
            response = await self.client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data
            )
            
            # Parse rate limit info if available
            rate_limit_remaining = None
            if "x-ratelimit-remaining" in response.headers:
                rate_limit_remaining = int(response.headers["x-ratelimit-remaining"])
            elif "x-rate-limit-remaining" in response.headers:
                rate_limit_remaining = int(response.headers["x-rate-limit-remaining"])
            
            if response.is_success:
                data = response.json() if response.content else None
                return APIResponse(
                    success=True,
                    data=data,
                    status_code=response.status_code,
                    rate_limit_remaining=rate_limit_remaining
                )
            else:
                error_data = {}
                try:
                    error_data = response.json()
                except Exception:
                    pass
                
                return APIResponse(
                    success=False,
                    data=error_data,
                    error_message=f"HTTP {response.status_code}: {response.text}",
                    status_code=response.status_code,
                    rate_limit_remaining=rate_limit_remaining
                )
                
        except httpx.TimeoutException:
            return APIResponse(
                success=False,
                error_message="Request timeout"
            )
        except Exception as e:
            return APIResponse(
                success=False,
                error_message=f"Request failed: {str(e)}"
            )


class PlatformManager:
    """Manages multiple e-commerce platform adapters."""
    
    def __init__(self):
        self.adapters: dict[str, PlatformAdapter] = {}
    
    async def register_adapter(self, platform_name: str, adapter: PlatformAdapter) -> bool:
        """Register a platform adapter."""
        try:
            # Test connection before registering
            connection_result = await adapter.test_connection()
            if connection_result.success:
                self.adapters[platform_name] = adapter
                logger.info(f"Registered adapter for {platform_name}")
                return True
            else:
                logger.error(f"Failed to register {platform_name}: {connection_result.error_message}")
                return False
        except Exception as e:
            logger.error(f"Error registering adapter for {platform_name}", error=str(e))
            return False
    
    async def sync_all_platforms(self, sync_types: list[str] | None = None) -> dict[str, list[SyncResult]]:
        """Synchronize data across all registered platforms."""
        results = {}
        
        # Run sync operations in parallel for better performance
        sync_tasks = []
        platform_names = []
        
        for platform_name, adapter in self.adapters.items():
            task = asyncio.create_task(adapter.sync_data(sync_types))
            sync_tasks.append(task)
            platform_names.append(platform_name)
        
        if sync_tasks:
            sync_results = await asyncio.gather(*sync_tasks, return_exceptions=True)
            
            for i, result in enumerate(sync_results):
                platform_name = platform_names[i]
                if isinstance(result, Exception):
                    logger.error(f"Sync failed for {platform_name}", error=str(result))
                    results[platform_name] = [SyncResult(
                        platform=platform_name,
                        sync_type="error",
                        errors=[str(result)]
                    )]
                else:
                    results[platform_name] = result
        
        return results
    
    def get_adapter(self, platform_name: str) -> PlatformAdapter | None:
        """Get adapter for a specific platform."""
        return self.adapters.get(platform_name)
    
    async def process_webhook(self, platform_name: str, payload: dict[str, Any]) -> APIResponse:
        """Process webhook for a specific platform."""
        adapter = self.adapters.get(platform_name)
        if not adapter:
            return APIResponse(
                success=False,
                error_message=f"No adapter registered for {platform_name}"
            )
        
        return await adapter.handle_webhook(payload)
    
    async def cleanup(self):
        """Clean up all adapters."""
        for adapter in self.adapters.values():
            try:
                await adapter.client.aclose()
            except Exception as e:
                logger.error("Error closing adapter client", error=str(e))
        
        self.adapters.clear()
        logger.info("All adapters cleaned up")