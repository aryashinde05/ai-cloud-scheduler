"""
Redis-free configuration placeholder
"""

from typing import Optional, Dict, Any
import structlog
from contextlib import asynccontextmanager

logger = structlog.get_logger(__name__)

class RedisConfig:
    def __init__(self):
        self.host = "localhost"
        self.port = 6379
        self.db = 0

class RedisConnectionManager:
    """Mock Redis client that doesn't attempt any connections"""
    def __init__(self, config=None):
        self.config = config
    
    def get_sync_client(self):
        return None
    
    async def get_async_client(self):
        return None
        
    async def get_json(self, key: str) -> Optional[Any]:
        return None
        
    async def set_json(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        return True
        
    async def publish(self, channel: str, message: Any) -> int:
        return 0
        
    async def lpush(self, key: str, *values: Any) -> int:
        return 0
        
    async def ltrim(self, key: str, start: int, end: int) -> bool:
        return True
        
    async def expire(self, key: str, time: int) -> bool:
        return True
        
    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "disabled",
            "message": "Redis is disabled by user configuration"
        }
    
    async def close_connections(self):
        pass

redis_config = RedisConfig()
redis_manager = RedisConnectionManager(redis_config)

def get_redis():
    return None

@asynccontextmanager
async def get_redis_client():
    yield None
