
import hashlib
import json
import logging
from typing import Any, Optional

import redis

logger = logging.getLogger(__name__)

class RedisCache:
    def __init__(self, host: str = "redis", port: int = 6379, db: int = 2):
        """Initialize Redis cache connection"""
        self.redis_client = redis.Redis(host=host, port=port, db=db, decode_responses=True)
        
    def _generate_key(self, prefix: str, **kwargs) -> str:
        """Generate a cache key from parameters"""
        # Sort kwargs to ensure consistent key generation
        sorted_kwargs = sorted(kwargs.items())
        key_string = f"{prefix}:{':'.join(f'{k}={v}' for k, v in sorted_kwargs)}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning("Cache get error: %s", e)
            return None
    
    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in cache with TTL (default 5 minutes)"""
        try:
            serialized = json.dumps(value, default=str)
            return self.redis_client.setex(key, ttl, serialized)
        except Exception as e:
            logger.warning("Cache set error: %s", e)
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            return bool(self.redis_client.delete(key))
        except Exception as e:
            logger.warning("Cache delete error: %s", e)
            return False
    
    def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern"""
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.warning("Cache clear error: %s", e)
            return 0

# Global cache instance
cache = RedisCache()

def get_cached(key: str) -> Optional[Any]:
    """Get cached value"""
    return cache.get(key)

def set_cached(key: str, value: Any, ttl: int = 300) -> bool:
    """Set cached value"""
    return cache.set(key, value, ttl)

def clear_cache(pattern: str = "*") -> int:
    """Clear cache"""
    return cache.clear_pattern(pattern)
