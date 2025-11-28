import pandas as pd, numpy as np
from .metrics import compute_metrics

def run_backtest(df: pd.DataFrame, fees_bps: float = 10.0) -> dict:
    """
    Backtest long-only avec rebalancement quotidien sur la position cible.
    Les frais sont proportionnels au turnover absolu (variation de poids).
    """
    d = df.copy()
    d["ret"] = d.get("ret", d["close"].pct_change()).fillna(0.0)
    fee = fees_bps / 10_000.0

    # allocation 0..100 -> poids 0..1
    w = d["pos"].fillna(0.0) / 100.0
    turnover = w.diff().abs().fillna(w.abs())

    d["turnover"] = turnover
    d["trade"] = (turnover > 1e-6).astype(int)
    d["strategy_ret"] = w * d["ret"] - turnover * fee
    d["equity"] = (1 + d["strategy_ret"]).cumprod()
    d["bh_equity"] = (1 + d["ret"]).cumprod()

    m = compute_metrics(d)
    m["trades"] = int(d["trade"].sum())
    m["turnover"] = float(turnover.sum())
    return {"df": d, "metrics": m}
