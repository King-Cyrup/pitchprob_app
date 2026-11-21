"""Compare the model with bookmaker closing odds. The market is the hardest benchmark there is."""
import numpy as np
import pandas as pd


def devig(odds: np.ndarray) -> np.ndarray:
    """Decimal odds [home, draw, away] -> probabilities without the bookmaker's margin (proportional method)."""
    inverse = 1 / np.asarray(odds, dtype=float)
    return inverse / inverse.sum(axis=-1, keepdims=True)


def log_loss_1x2(probs: np.ndarray, results: np.ndarray) -> float:
    return float(-np.log(np.clip(probs[np.arange(len(results)), results], 1e-12, 1)).mean())


def compare_with_market(model_probs: np.ndarray, market_probs: np.ndarray, results: np.ndarray) -> pd.DataFrame:
    """All three inputs refer to the same matches. Also reports the 50/50 mix, which shows whether the model adds anything the market lacks."""
    mix = (model_probs + market_probs) / 2
    rows = [("Model", model_probs), ("Bookmaker closing odds", market_probs), ("50/50 mix", mix)]
    return pd.DataFrame({"log_loss": [log_loss_1x2(p, results) for _, p in rows]}, index=[n for n, _ in rows])
