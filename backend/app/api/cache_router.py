from fastapi import APIRouter


router = APIRouter()


@router.get("/cache/stats")
async def get_cache_stats():
    """Get Redis cache statistics"""
    try:
        from app.cache import cache

        info = cache.redis_client.info()
        return {
            "ok": True,
            "stats": {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
            },
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/cache/clear")
async def clear_cache():
    """Clear all cache"""
    try:
        from app.cache import clear_cache

        cleared = clear_cache()
        return {"ok": True, "cleared_keys": cleared}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/cache/keys")
async def list_cache_keys():
    """List all cache keys"""
    try:
        from app.cache import cache

        keys = cache.redis_client.keys("*")
        return {"ok": True, "keys": keys, "count": len(keys)}
    except Exception as e:
        return {"ok": False, "error": str(e)}

