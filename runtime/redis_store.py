"""HyperLogLog feature serving. 12 KB per counter at ~0.81% standard error, which is
why distinct counts over 50,000 entities are served from HLL rather than exact sets."""

import redis

from runtime.config import load_config


def redis_client() -> redis.Redis:
    return redis.Redis.from_url(load_config().redis_url, decode_responses=True)


def hll_key(entity_type: str, entity_id: str, counted: str) -> str:
    return f"hll:{entity_type}:{entity_id}:{counted}"


def record_distinct(entity_type: str, entity_id: str, counted: str, value: str) -> None:
    key = hll_key(entity_type, entity_id, counted)
    client = redis_client()
    client.pfadd(key, value)
    client.expire(key, load_config().hll_ttl_seconds)


def count_distinct(entity_type: str, entity_id: str, counted: str) -> int:
    return int(redis_client().pfcount(hll_key(entity_type, entity_id, counted)))
