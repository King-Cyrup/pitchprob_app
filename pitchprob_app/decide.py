"""The rule that decides whether a change ships. Used for every step in the guide."""
import numpy as np

MIN_MATCHES = 2000        # smaller samples cannot separate a real gain of 0.003 from luck
MIN_GAIN = 0.002          # smallest average log-loss gain worth the extra complexity


def paired_gain(loss_old, loss_new, n_boot: int = 2000, seed: int = 0) -> dict:
    """Per-match loss difference (old minus new; positive = the new version is better) and its 95% bootstrap interval."""
    d = np.asarray(loss_old, dtype=float) - np.asarray(loss_new, dtype=float)
    rng = np.random.default_rng(seed)
    means = [rng.choice(d, len(d)).mean() for _ in range(n_boot)]
    return {"n": len(d), "gain": float(d.mean()), "low": float(np.percentile(means, 2.5)), "high": float(np.percentile(means, 97.5))}


def decide(result: dict, min_matches: int = MIN_MATCHES, min_gain: float = MIN_GAIN) -> str:
    """'adopt' only if the whole interval is above zero, the gain is big enough and the sample is large enough."""
    if result["n"] >= min_matches and result["low"] > 0 and result["gain"] >= min_gain:
        return "adopt"
    if result["gain"] > 0:
        return "shadow"        # run it quietly next to the live model and collect more matches
    return "reject"
