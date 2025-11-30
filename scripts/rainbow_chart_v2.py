import argparse
import os
import sys
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from fngbt.data import load_btc_prices

GENESIS = pd.Timestamp("2009-01-03")
DEFAULT_START = "2013-01-01"
DEFAULT_EXTEND = "2025-12-31"


def _log_regression(dates: pd.Series, prices: pd.Series) -> tuple[float, float]:
    days = (dates - GENESIS).dt.days.clip(lower=1).astype(float)
    x = np.log10(days)
    y = np.log10(prices.clip(lower=1e-9))
    slope, intercept = np.polyfit(x, y, deg=1)
    return slope, intercept


def build_rainbow_v2(px: pd.DataFrame, extend_to: str | None = None) -> pd.DataFrame:
    df = px.copy().dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)
    if df.empty:
        raise ValueError("Aucune donnée BTC pour construire le Rainbow Chart.")

    slope, intercept = _log_regression(df["date"], df["close"])
    quantiles = [0.02, 0.10, 0.20, 0.35, 0.50, 0.65, 0.80, 0.90, 0.98]
    deviation = np.log10(df["close"].clip(lower=1e-12)) - (
        intercept + slope * np.log10((df["date"] - GENESIS).dt.days.clip(lower=1).astype(float))
    )
    band_devs = np.quantile(deviation, quantiles)

    def _lines(dates: Iterable[pd.Timestamp]) -> pd.DataFrame:
        dates = pd.to_datetime(pd.Index(dates)).sort_values()
        delta_days = (dates - GENESIS).days.astype(float)
        days = np.clip(delta_days, 1.0, None)
        log_mid = intercept + slope * np.log10(days)
        out = pd.DataFrame({"date": dates, "rainbow_base": 10 ** log_mid})
        for q, d in zip(quantiles, band_devs):
            out[f"rainbow_band_{int(q * 100):02d}"] = 10 ** (log_mid + d)
        return out

    end_date = pd.to_datetime(extend_to) if extend_to else df["date"].max()
    if end_date < df["date"].max():
        end_date = df["date"].max()

    full_dates = pd.date_range(df["date"].min(), end_date, freq="D")
    rainbow = _lines(full_dates)
    rainbow = rainbow.merge(df[["date", "close"]], on="date", how="left")
    return rainbow


def plot_rainbow_v2(d: pd.DataFrame, out: Path | None = None):
    band_cols = sorted([c for c in d.columns if c.startswith("rainbow_band_")])
    if len(band_cols) < 2:
        raise ValueError("Pas assez de bandes Rainbow pour tracer.")

    fig, ax = plt.subplots(figsize=(12, 6))
    price = d.dropna(subset=["close"])
    ax.plot(price["date"], price["close"], color="#1f77b4", linewidth=1.2, label="BTC-USD")
    ax.plot(d["date"], d["rainbow_base"], color="#f59f00", linestyle="--", linewidth=1.0, label="Rainbow base (log fit)")

    colors = [
        "#2b9348",
        "#55a630",
        "#80b918",
        "#aacc00",
        "#ffdd00",
        "#f8961e",
        "#f3722c",
        "#d7263d",
    ]
    labels = [
        "🔥 Fortement survendu",
        "Survendu",
        "Bonne valeur",
        "Zone neutre",
        "Chaleur modérée",
        "Suracheté",
        "Bull euphérique",
        "🚀 Bulle",
    ]

    for lower, upper, color, label in zip(band_cols[:-1], band_cols[1:], colors, labels):
        ax.fill_between(d["date"], d[lower], d[upper], color=color, alpha=0.25, label=label)

    ax.set_yscale("log")
    ax.set_title("Bitcoin Rainbow Chart v2 (2013-2025)")
    ax.set_xlabel("Date")
    ax.set_ylabel("Prix (USD, échelle log)")
    ax.grid(True, linestyle=":", alpha=0.5)
    ax.legend(loc="upper left", ncol=2)
    fig.tight_layout()

    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=160)
        print(f"Graphique sauvegardé -> {out}")


def main():
    p = argparse.ArgumentParser(description="Trace le Rainbow Chart v2 (log-reg + bandes quantiles).")
    p.add_argument("--start", type=str, default=DEFAULT_START, help="Date de début (YYYY-MM-DD).")
    p.add_argument("--end", type=str, default=None, help="Date de fin des prix (YYYY-MM-DD).")
    p.add_argument("--extend-to", type=str, default=DEFAULT_EXTEND, help="Date future jusqu'où prolonger le Rainbow.")
    p.add_argument("--out", type=str, default="outputs/rainbow_v2.png", help="Chemin de sauvegarde du graphique.")
    args = p.parse_args()

    px = load_btc_prices(
        start=args.start,
        end=args.end,
    )
    rainbow = build_rainbow_v2(px, extend_to=args.extend_to)
    plot_rainbow_v2(rainbow, out=Path(args.out))


if __name__ == "__main__":
    main()
