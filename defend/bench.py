"""The hot path and its latency benchmark.

Every value named _TARGET_MS here is an engineering target, not a measurement.
Measurements come only from runs/<run_id>/latency.json, written from run_benchmark's
output. This module's import list is the enforced hot-path boundary: onnxruntime, redis,
hmac, hashlib, numpy, time and runtime.config, and nothing else.
"""

import hashlib
import hmac
import time

import numpy as np
import onnxruntime
import redis

from runtime.config import load_config

LATENCY_TARGET_INLINE_TOTAL_MS: float = 15.0
LATENCY_TARGET_FEATURE_LOOKUP_MS: float = 5.0
LATENCY_TARGET_MODEL_MS: float = 2.0
LATENCY_TARGET_HASH_COMPARE_MS: float = 0.05

BENCH_ITERATIONS: int = 10_000
BENCH_WARMUP: int = 500
PERCENTILES: tuple[int, ...] = (50, 95, 99)
MILLISECONDS_PER_SECOND: float = 1000.0
SESSION_THREADS: int = 1
HLL_BENCH_PREFIX: str = "hll:bench:device"
HLL_SEED_VALUES: int = 4096
HLL_BENCH_ITERATIONS: int = 2_000
REDIS_CONNECT_TIMEOUT_S: float = 2.0


def load_session(model_path: str) -> onnxruntime.InferenceSession:
    """The one file read permitted on the hot path, and only at process start."""
    options = onnxruntime.SessionOptions()
    options.intra_op_num_threads = SESSION_THREADS
    options.inter_op_num_threads = SESSION_THREADS
    return onnxruntime.InferenceSession(model_path, options, providers=["CPUExecutionProvider"])


def raw_score(session: onnxruntime.InferenceSession, features: np.ndarray) -> float:
    outputs = session.run(None, {session.get_inputs()[0].name: features})
    probabilities = outputs[-1]
    array = np.asarray(probabilities, dtype="float64").reshape(features.shape[0], -1)
    return float(array[0, -1])


def calibrated_score(
    session: onnxruntime.InferenceSession, features: np.ndarray, platt_a: float, platt_b: float
) -> float:
    """Platt scaling is four arithmetic operations, which is why calibration stays inline."""
    return float(1.0 / (1.0 + np.exp(platt_a * raw_score(session, features) + platt_b)))


def cart_hash_matches(intent_hex: str, settle_hex: str) -> bool:
    """Constant-time, so the comparison cannot be probed by timing."""
    return hmac.compare_digest(intent_hex, settle_hex)


def digest_of(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def feature_lookup(client: redis.Redis, key: str) -> int:
    return int(client.pfcount(key))


def benchmark_feature_lookup(url: str, iterations: int, warmup: int) -> dict:
    """Measure a HyperLogLog distinct-count lookup, or report that it could not be measured.

    A counter costs 12 KB at roughly 0.81% standard error, which is why the distinct-PAN
    feature family is served this way rather than from an exact set. If Redis is not
    reachable the path reports unavailable: an unmeasured number would breach the same rule
    every other latency figure here obeys."""
    key = f"{HLL_BENCH_PREFIX}:{int(time.time())}"
    try:
        client = redis.Redis.from_url(url, socket_connect_timeout=REDIS_CONNECT_TIMEOUT_S)
        client.ping()
        for index in range(HLL_SEED_VALUES):
            client.pfadd(key, f"tok_{index:016x}")
        samples = np.empty(iterations, dtype="float64")
        for index in range(iterations + warmup):
            started = time.perf_counter()
            feature_lookup(client, key)
            elapsed = (time.perf_counter() - started) * MILLISECONDS_PER_SECOND
            if index >= warmup:
                samples[index - warmup] = elapsed
        client.delete(key)
    except (redis.RedisError, OSError) as exc:
        return {
            "source": "unavailable",
            "reason": f"redis unreachable: {type(exc).__name__}",
            "target_ms": LATENCY_TARGET_FEATURE_LOOKUP_MS,
        }
    measurement = _percentiles(samples)
    measurement.update(
        {
            "source": "measured",
            "iterations": iterations,
            "seeded_values": HLL_SEED_VALUES,
            "target_ms": LATENCY_TARGET_FEATURE_LOOKUP_MS,
        }
    )
    return measurement


def _percentiles(samples: np.ndarray) -> dict[str, float]:
    return {f"p{value}_ms": round(float(np.percentile(samples, value)), 4) for value in PERCENTILES}


def run_benchmark(
    model_path: str,
    feature_row: np.ndarray,
    platt: tuple[float, float],
    iterations: int | None = None,
    warmup: int | None = None,
) -> dict:
    config = load_config()
    total = iterations or config.bench_iterations
    skip = warmup or config.bench_warmup
    session = load_session(model_path)
    features = np.ascontiguousarray(feature_row.reshape(1, -1).astype("float32"))

    samples = np.empty(total, dtype="float64")
    for index in range(total + skip):
        started = time.perf_counter()
        calibrated_score(session, features, platt[0], platt[1])
        elapsed = (time.perf_counter() - started) * MILLISECONDS_PER_SECOND
        if index >= skip:
            samples[index - skip] = elapsed

    measurement = _percentiles(samples)
    measurement.update(
        {
            "source": "measured",
            "iterations": total,
            "warmup": skip,
            "budget_ms": config.scoring_latency_budget_ms,
            "targets": {
                "inline_total_ms": LATENCY_TARGET_INLINE_TOTAL_MS,
                "feature_lookup_ms": LATENCY_TARGET_FEATURE_LOOKUP_MS,
                "model_ms": LATENCY_TARGET_MODEL_MS,
                "hash_compare_ms": LATENCY_TARGET_HASH_COMPARE_MS,
            },
        }
    )
    return measurement
