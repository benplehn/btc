"""Simulation de la stratégie "LowestWindowWeapon".

Cette stratégie ne repose que sur un facteur : le retour dans le ruban le plus
bas (bande 0) du Rainbow Chart après y avoir séjourné un certain nombre de
jours. À chaque re-rentrée qualifiée, on investit un montant fixe.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from fngbt.data import load_btc_prices
from fngbt.strategy import calculate_rainbow_position, _quantize_bands


@dataclass
class LowestWindowWeaponConfig:
    amount: float = 50.0
    min_days_in_band: int = 1
    band_count: int = 8
    rainbow_top_decay: float = 0.0


def _compute_band_lines(rainbow_min: pd.Series, rainbow_max: pd.Series, band_count: int) -> list[pd.Series]:
    """Interpole les bandes Rainbow (log) pour faciliter les tracés colorés."""
    log_min = np.log10(rainbow_min.clip(lower=1e-12))
    log_max = np.log10(rainbow_max.clip(lower=1e-12))
    lines: list[pd.Series] = []
    for i in range(band_count + 1):
        frac = i / band_count
        line = 10 ** (log_min + frac * (log_max - log_min))
        lines.append(line)
    return lines


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

    rainbow = calculate_rainbow_position(df, top_decay=cfg.rainbow_top_decay)
    band_ids, _ = _quantize_bands(rainbow["rainbow_position"], cfg.band_count)
    rainbow["rainbow_band"] = band_ids

    band_lines = _compute_band_lines(rainbow["rainbow_min"], rainbow["rainbow_max"], cfg.band_count)
    for i, line in enumerate(band_lines):
        rainbow[f"rainbow_band_{i}"] = line

    d = rainbow.reset_index(drop=True)
    d["contribution"] = 0.0
    d.loc[entries, "contribution"] = cfg.amount

    d["btc_bought"] = d["contribution"] / d["close"]
    d["btc_holdings"] = d["btc_bought"].cumsum()
    d["invested_eur"] = d["contribution"].cumsum()
    d["equity"] = d["btc_holdings"] * d["close"]

    total_invested = d["invested_eur"].iloc[-1]
    d["dca_equity"] = _dca_monthly_equity(d, total_invested)
    return d


def summarize(d: pd.DataFrame) -> dict:
    total_invested = float(d["invested_eur"].iloc[-1])
    eq = float(d["equity"].iloc[-1])
    dca_eq = float(d["dca_equity"].iloc[-1])
    nb_signals = int((d["contribution"] > 0).sum())
    mdd = _max_drawdown(d["equity"])
    return {
        "signals": nb_signals,
        "total_invested": total_invested,
        "final_value": eq,
        "multiple": (eq / total_invested) if total_invested > 0 else 0.0,
        "dca_final": dca_eq,
        "dca_multiple": (dca_eq / total_invested) if total_invested > 0 else 0.0,
        "max_dd": mdd,
    }


def _max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax().replace(0, pd.NA).ffill().fillna(1.0)
    dd = equity / peak - 1.0
    return float(dd.min())


def _dca_monthly_equity(d: pd.DataFrame, total_invested: float) -> pd.Series:
    """Calcule l'équity d'un DCA mensuel répliquant le capital total investi."""

    if total_invested <= 0:
        return pd.Series(0.0, index=d.index)

    dates = pd.to_datetime(d["date"])
    months = pd.date_range(dates.iloc[0].normalize(), dates.iloc[-1].normalize(), freq="MS")
    if len(months) == 0:
        return pd.Series(0.0, index=d.index)

    monthly_amt = total_invested / len(months)
    contrib = pd.Series(0.0, index=d.index)
    date_values = dates.values
    for m in months:
        pos = date_values.searchsorted(np.datetime64(m), side="left")
        if pos < len(contrib):
            contrib.iloc[pos] += monthly_amt

    btc_bought = contrib / d["close"]
    holdings = btc_bought.cumsum()
    return holdings * d["close"]


def load_and_simulate(
    start: str,
    end: str | None,
    cfg: LowestWindowWeaponConfig,
) -> tuple[pd.DataFrame, dict]:
    df_px = load_btc_prices(start=start, end=end)
    sim = simulate_lowest_window_weapon(df_px, cfg)
    stats = summarize(sim)
    return sim, stats


def _ensure_out_path(path: str | Path | None) -> Path | None:
    if not path:
        return None
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def plot_price_with_signals(sim: pd.DataFrame, cfg: LowestWindowWeaponConfig, out: str | Path | None = None) -> None:
    """Prix BTC en log + rubans + marqueurs d'achats."""
    bands: List[pd.Series] = []
    for i in range(cfg.band_count + 1):
        col = f"rainbow_band_{i}"
        if col in sim:
            bands.append(sim[col])
    fig, ax = plt.subplots(figsize=(11, 6))
    colors = plt.cm.rainbow(np.linspace(0, 1, max(len(bands) - 1, 1)))
    for i in range(len(bands) - 1):
        ax.fill_between(sim["date"], bands[i], bands[i + 1], color=colors[i], alpha=0.08, linewidth=0)
    ax.plot(sim["date"], sim["close"], color="#111", label="BTC-USD")
    buys = sim[sim["contribution"] > 0]
    if not buys.empty:
        ax.scatter(buys["date"], buys["close"], color="black", marker="^", s=35, label="Achats")
    ax.set_yscale("log")
    ax.set_ylabel("BTC (log)")
    ax.set_title("BTC + retours dans le ruban bas (achats €50)")
    ax.legend(loc="upper left")
    fig.tight_layout()
    out_path = _ensure_out_path(out)
    if out_path:
        fig.savefig(out_path, dpi=140)
    plt.close(fig)


def plot_equity(sim: pd.DataFrame, out: str | Path | None = None) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(sim["date"], sim["equity"], label="Stratégie", color="#18a957")
    ax.plot(sim["date"], sim["dca_equity"], label="DCA mensuel équivalent", color="#555")
    ax.set_ylabel("€")
    ax.set_title("Equity: LowestWindowWeapon vs DCA")
    ax.legend(loc="upper left")
    fig.tight_layout()
    out_path = _ensure_out_path(out)
    if out_path:
        fig.savefig(out_path, dpi=140)
    plt.close(fig)


def plot_overview(sim: pd.DataFrame, cfg: LowestWindowWeaponConfig, out: str | Path | None = None) -> None:
    """Vue combinée : prix + rubans + achats et equity vs B&H."""
    fig, axes = plt.subplots(2, 1, figsize=(11, 9), sharex=True)

    # Prix + rubans + achats
    bands: Sequence[pd.Series] = []
    for i in range(cfg.band_count + 1):
        col = f"rainbow_band_{i}"
        if col in sim:
            bands.append(sim[col])
    ax_price = axes[0]
    colors = plt.cm.rainbow(np.linspace(0, 1, max(len(bands) - 1, 1)))
    for i in range(len(bands) - 1):
        ax_price.fill_between(sim["date"], bands[i], bands[i + 1], color=colors[i], alpha=0.08, linewidth=0)
    ax_price.plot(sim["date"], sim["close"], color="#111", label="BTC-USD")
    buys = sim[sim["contribution"] > 0]
    if not buys.empty:
        ax_price.scatter(buys["date"], buys["close"], color="black", marker="^", s=35, label="Achats")
    ax_price.set_yscale("log")
    ax_price.set_ylabel("BTC (log)")
    ax_price.legend(loc="upper left")
    ax_price.set_title("Prix BTC + rubans Rainbow + entrées lump-sum")

    # Equity
    ax_eq = axes[1]
    ax_eq.plot(sim["date"], sim["equity"], label="Stratégie", color="#18a957")
    ax_eq.plot(sim["date"], sim["dca_equity"], label="DCA mensuel équivalent", color="#555")
    ax_eq.set_ylabel("€")
    ax_eq.set_title("Equity cumulée")
    ax_eq.legend(loc="upper left")

    fig.tight_layout()
    out_path = _ensure_out_path(out)
    if out_path:
        fig.savefig(out_path, dpi=140)
    plt.close(fig)
