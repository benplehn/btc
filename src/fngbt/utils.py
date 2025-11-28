import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional

from .strategy import StrategyConfig


def ensure_dir(path: str | Path):
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def plot_equity(d: pd.DataFrame, title: str, out: Optional[str] = None):
    plt.figure(figsize=(10, 5))
    plt.plot(d["date"], d["equity"], label="Strategy")
    plt.plot(d["date"], d["bh_equity"], label="Buy & Hold")
    plt.title(title)
    plt.legend()
    plt.tight_layout()
    if out:
        ensure_dir(Path(out).parent)
        plt.savefig(out, dpi=120)
    plt.show()


def plot_overview(d: pd.DataFrame, cfg: StrategyConfig | None, title: str = "", out: Optional[str] = None):
    """
    Vue en 3 panneaux : prix BTC (log) + Rainbow/alloc, FNG, equity.
    """
    fig, axes = plt.subplots(3, 1, figsize=(11, 10), sharex=True)

    # Prix BTC sur log + Rainbow + allocation
    ax_price = axes[0]
    ax_price.plot(d["date"], d["close"], label="BTC-USD", color="#2d6cdf")
    ax_price.set_yscale("log")
    if cfg and cfg.use_rainbow and "rainbow_base" in d:
        ax_price.plot(d["date"], d["rainbow_base"], label="Rainbow mid (fit)", color="#f59f00", alpha=0.8)
        if "rainbow_min" in d:
            ax_price.plot(d["date"], d["rainbow_min"], color="#18a957", linestyle="--", alpha=0.9, label="Ruban bas")
        if "rainbow_max" in d:
            ax_price.plot(d["date"], d["rainbow_max"], color="#d7263d", linestyle="--", alpha=0.9, label="Ruban haut")
        band_cols = [c for c in d.columns if c.startswith("rainbow_band_")]
        for c in sorted(band_cols):
            ax_price.plot(d["date"], d[c], color="#f59f00", alpha=0.18, linewidth=0.8)
    ax_price.fill_between(
        d["date"],
        d["close"].min(),
        d["close"].max(),
        where=d["pos"] > 0,
        color="#18a957",
        alpha=0.08,
        label="Exposition > 0",
    )
    ax_alloc = ax_price.twinx()
    ax_alloc.plot(d["date"], d["pos"], color="#18a957", alpha=0.7, label="Allocation (%)")
    ax_alloc.set_ylabel("Allocation (%)")
    max_pos = float(np.nanmax(d["pos"])) if len(d) else 0.0
    ax_alloc.set_ylim(0, max(110, max_pos * 1.1))
    ax_price.set_ylabel("BTC (log)")
    ax_price.legend(loc="upper left")
    ax_alloc.legend(loc="upper right")

    # FNG + signal contrarien
    ax_sent = axes[1]
    fng_plot = d["fng"]
    if "fng_used" in d:
        ax_sent.plot(d["date"], d["fng_used"], label="F&G lissé", color="#f59f00")
        ax_sent.plot(d["date"], d["fng"], label="F&G brut", color="#f59f00", alpha=0.25, linestyle="--")
    else:
        ax_sent.plot(d["date"], fng_plot, label="Fear & Greed", color="#f59f00")
    if cfg and cfg.use_fng and hasattr(cfg, "fng_buy"):
        ax_sent.axhline(cfg.fng_buy, color="#18a957", linestyle="--", linewidth=1, label="Seuil achat")
        ax_sent.axhline(cfg.fng_sell, color="#d7263d", linestyle="--", linewidth=1, label="Seuil vente")
    ax_sent.axhline(50, color="#888", linestyle="--", linewidth=1, alpha=0.4)
    ax_sent.fill_between(d["date"], d["fng"], 0, where=d["pos"] > 0, color="#18a957", alpha=0.05)
    ax_sent.set_ylabel("FNG")
    ax_sent.legend(loc="upper left")

    # Equity curve
    axes[2].plot(d["date"], d["equity"], label="Strategy", color="#18a957")
    axes[2].plot(d["date"], d["bh_equity"], label="Buy & Hold", color="#555")
    axes[2].set_ylabel("Equity (start=1)")
    axes[2].legend(loc="upper left")

    fig.suptitle(title or "BTC strategy: FNG (régime) + Rainbow (sizing)")
    fig.tight_layout()
    if out:
        ensure_dir(Path(out).parent)
        fig.savefig(out, dpi=130)
    plt.show()
