import redis
import os
import json
from datetime import datetime

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

try:
    ## Creates a Redis client from URL, converts bytes to strings, and
    ## Checks if Redis is reachable
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    redis_client.ping()
    print("Redis connected")
except Exception as e:
    ## if connection fails
    print(f"Redis not available: {e}")
    redis_client = None

## Cache a URL mapping by storing a URL in Redis using its short code
def set_url(short_code: str, original_url: str, expires_at=None):
    if not redis_client:
        return
    
    try:
        ## Cache for 24 hours or until expiration
        ttl = 86400  ## 24 hours
        if expires_at:
            ttl = int((expires_at - datetime.now()).total_seconds())
            if ttl <= 0:
                return
        ## sets a key in Redis with expiration time
        ## redis_client.setex(key, ttl, value)
        redis_client.setex(f"url:{short_code}", ttl, original_url)
    except Exception as e:
        print(f"Cache set error: {e}")

## looks up a URL by short code in Redis
## if Redis is unavailable return None, if error Print error and return None
def get_url(short_code: str):
    if not redis_client:
        return None
    
    try:
        return redis_client.get(f"url:{short_code}")
    except Exception as e:
        print(f"Cache get error: {e}")
        return None

## deletes cached URL from Redis with exception handling
def delete_url(short_code: str):
    if not redis_client:
        return
    
    try:
        redis_client.delete(f"url:{short_code}")
    except Exception as e:
        print(f"Cache delete error: {e}")