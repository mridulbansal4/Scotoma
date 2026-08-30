"""Named deterministic generators. Every random draw in PayLoop starts here."""

import hashlib
from uuid import UUID, uuid5

import numpy as np

from backend.runtime.config import load_config

PAYLOOP_UUID_NAMESPACE = UUID("6f5c1a20-8d2e-5b41-9c73-0a1e4d7b6f28")


def stable_hash(purpose: str) -> int:
    # Python's built-in hash is salted per process, so committed artefacts would not reproduce.
    digest = hashlib.blake2b(purpose.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big")


def rng_for(purpose: str, seed: int | None = None) -> np.random.Generator:
    """The same purpose string always yields the same stream, whatever the call order."""
    root = load_config().population_seed if seed is None else seed
    sequence = np.random.SeedSequence(entropy=root, spawn_key=(stable_hash(purpose),))
    return np.random.default_rng(sequence)


def seeded_uuid(purpose: str, index: int) -> UUID:
    return uuid5(PAYLOOP_UUID_NAMESPACE, f"{purpose}:{index}")
