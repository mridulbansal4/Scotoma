"""The two DE39 decline mixes and the sampler. No copy of this table exists elsewhere.

Code 14 (invalid card number) is deliberately absent from the legitimate mix: it is
emitted only by the enumeration and BIN-attack injectors, which is what makes it a signal.
"""

import numpy as np

# Shares are the Visa Global Declines distribution; the India column carries the
# documented do-not-honor skew.
DE39_MIX: dict[str, dict[str, float]] = {
    "GLOBAL": {
        "05": 0.40,
        "51": 0.35,
        "54": 0.10,
        "57": 0.03,
        "59": 0.03,
        "61": 0.03,
        "65": 0.02,
        "82": 0.02,
        "91": 0.02,
    },
    "INDIA": {
        "05": 0.34,
        "51": 0.42,
        "54": 0.08,
        "57": 0.03,
        "59": 0.03,
        "61": 0.03,
        "65": 0.02,
        "82": 0.02,
        "91": 0.03,
    },
}

ENUMERATION_DECLINE_CODE: str = "14"


def mix_for(region: str) -> dict[str, float]:
    if region not in DE39_MIX:
        raise KeyError(f"unknown decline mix region {region}")
    return DE39_MIX[region]


def sample_decline_code(region: str, rng: np.random.Generator) -> str:
    mix = mix_for(region)
    codes = list(mix.keys())
    return str(rng.choice(codes, p=list(mix.values())))


def sample_decline_codes(region: str, size: int, rng: np.random.Generator) -> np.ndarray:
    mix = mix_for(region)
    return rng.choice(list(mix.keys()), size=size, p=list(mix.values()))
