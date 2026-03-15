"""
No-op Cache Service to replace Redis-based implementation
"""

from typing import Any, Optional, Dict, Union, Callable, TypeVar, List
import structlog

logger = structlog.get_logger(__name__)

T = TypeVar('T')

class NoOpCache:
    """A cache service that does nothing (no-op)"""
    
    async def get(self, key: str, default: Any = None) -> Any:
        return default
        
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        return True
        
    async def delete(self, key: str) -> bool:
        return True
    
    async def clear(self) -> bool:
        return True
        
    async def get_stats(self) -> Dict[str, Any]:
        return {
            "status": "disabled",
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0
        }

    def cached(self, ttl: int = 3600, key_prefix: str = ""):
        """Decorator that DOES NOT cache anything"""
        def decorator(func):
            return func
        return decorator

# Re-define CacheService and cache_service for compatibility
class CacheService(NoOpCache):
    pass

cache_service = CacheService()
