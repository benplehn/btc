"""
Backtest simple d'une stratégie d'allocation Bitcoin

Simule l'achat/vente de BTC avec frais proportionnels au turnover
"""
import pandas as pd
import numpy as np
from .metrics import compute_metrics


def run_backtest(df: pd.DataFrame, fees_bps: float = 10.0) -> dict:
    """
    Backtest long-only avec allocation variable

    Args:
        df: DataFrame avec colonnes 'close', 'pos' (allocation en %)
        fees_bps: Frais de transaction en basis points (10 bps = 0.1%)

    Returns:
        dict avec 'df' (résultats jour par jour) et 'metrics' (métriques de performance)
    """
    d = df.copy()

    # Calcul des rendements quotidiens
    d["ret"] = d["close"].pct_change().fillna(0.0)

    # Conversion des frais de bps en fraction
    fee_rate = fees_bps / 10_000.0

    # Poids de l'allocation (0-100% → 0-1)
    weight = d["pos"].fillna(0.0) / 100.0

    # Turnover = changement absolu du poids
    # C'est le volume traité (achats + ventes)
    turnover = weight.diff().abs().fillna(weight.abs())

    # Rendement de la stratégie = rendement pondéré - frais
    d["turnover"] = turnover
    d["strategy_ret"] = weight * d["ret"] - turnover * fee_rate

    # Equity curves (cumulées)
    d["equity"] = (1 + d["strategy_ret"]).cumprod()
    d["bh_equity"] = (1 + d["ret"]).cumprod()

    # Nombre de trades
    d["trade"] = (turnover > 1e-6).astype(int)

    # Calcul des métriques de performance
    metrics = compute_metrics(d)
    metrics["trades"] = int(d["trade"].sum())
    metrics["turnover_total"] = float(turnover.sum())
    metrics["avg_allocation"] = float(weight.mean() * 100)

    return {
        "df": d,
        "metrics": metrics
    }
