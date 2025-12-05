"""Simulation de la stratégie "LowestWindowWeapon".

Cette stratégie ne repose que sur un facteur : le retour dans le ruban le plus
bas (bande 0) du Rainbow Chart après y avoir séjourné un certain nombre de
jours. À chaque re-rentrée qualifiée, on investit un montant fixe.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import pandas as pd

from fngbt.data import load_btc_prices
from fngbt.strategy import calculate_rainbow_position, _quantize_bands


@dataclass
class LowestWindowWeaponConfig:
    amount: float = 50.0
    min_days_in_band: int = 7
    band_count: int = 8
    rainbow_top_decay: float = 0.0


def find_bottom_band_entries(df: pd.DataFrame, cfg: LowestWindowWeaponConfig) -> List[int]:
    d = calculate_rainbow_position(df, top_decay=cfg.rainbow_top_decay)
    band_ids, _ = _quantize_bands(d["rainbow_position"], cfg.band_count)
    d["rainbow_band"] = band_ids

    in_bottom = band_ids == 0
    run_id = (in_bottom != in_bottom.shift()).cumsum()
    grouped = in_bottom.groupby(run_id).first()
    entries: List[int] = []
    last_bottom_qualifies = False
    for rid in run_id.unique():
        is_bottom = bool(grouped.loc[rid])
        if not is_bottom:
            continue
        mask = run_id == rid
        idx = d.index[mask]
        run_len = len(idx)
        if last_bottom_qualifies:
            entries.append(idx[0])
        last_bottom_qualifies = run_len >= cfg.min_days_in_band
    return entries


def simulate_lowest_window_weapon(df: pd.DataFrame, cfg: LowestWindowWeaponConfig) -> pd.DataFrame:
    entries = find_bottom_band_entries(df, cfg)
    d = df.copy().reset_index(drop=True)
    d["contribution"] = 0.0
    d.loc[entries, "contribution"] = cfg.amount

    d["btc_bought"] = d["contribution"] / d["close"]
    d["btc_holdings"] = d["btc_bought"].cumsum()
    d["invested_eur"] = d["contribution"].cumsum()
    d["equity"] = d["btc_holdings"] * d["close"]

    total_invested = d["invested_eur"].iloc[-1]
    if total_invested > 0:
        first_price = d["close"].iloc[0]
        bh_btc = total_invested / first_price
        d["bh_equity"] = bh_btc * d["close"]
    else:
        d["bh_equity"] = 0.0
    return d


def summarize(d: pd.DataFrame) -> dict:
    total_invested = float(d["invested_eur"].iloc[-1])
    eq = float(d["equity"].iloc[-1])
    bh_eq = float(d["bh_equity"].iloc[-1])
    nb_signals = int((d["contribution"] > 0).sum())
    mdd = _max_drawdown(d["equity"])
    return {
        "signals": nb_signals,
        "total_invested": total_invested,
        "final_value": eq,
        "multiple": (eq / total_invested) if total_invested > 0 else 0.0,
        "bh_final": bh_eq,
        "bh_multiple": (bh_eq / total_invested) if total_invested > 0 else 0.0,
        "max_dd": mdd,
    }


def _max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax().replace(0, pd.NA).fillna(method="ffill").fillna(1.0)
    dd = equity / peak - 1.0
    return float(dd.min())


def load_and_simulate(
    start: str,
    end: str | None,
    cfg: LowestWindowWeaponConfig,
) -> tuple[pd.DataFrame, dict]:
    df_px = load_btc_prices(start=start, end=end)
    sim = simulate_lowest_window_weapon(df_px, cfg)
    stats = summarize(sim)
    return sim, stats
