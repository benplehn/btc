import argparse
import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from importlib import import_module

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

# Import direct du module pour éviter les problèmes d'exports partiels du package
load_btc_prices = import_module("fngbt.data").load_btc_prices


DEF_START = "2013-01-01"


def analyze_series(df: pd.DataFrame) -> dict:
    df = df.copy().dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)
    dates = pd.DatetimeIndex(pd.to_datetime(df["date"], utc=True).tz_localize(None))
    expected = pd.date_range(dates.min(), dates.max(), freq="D")
    missing = expected.difference(dates)
    duplicates = dates.duplicated().sum()
    gaps = df.loc[df["date"].diff().dt.days > 1, ["date"]].assign(gap_days=lambda d: d["date"].diff().dt.days)
    return {
        "start": dates.min(),
        "end": dates.max(),
        "rows": len(df),
        "missing_days": len(missing),
        "dup_dates": int(duplicates),
        "max_gap_days": int(gaps["gap_days"].max()) if not gaps.empty else 0,
        "gap_examples": gaps.head(5),
    }


def plot_prices(df: pd.DataFrame, out_path: Path):
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(df["date"], df["close"], color="#1f77b4", linewidth=1.1)
    ax.set_title("BTC-USD (close) depuis 2013")
    ax.set_ylabel("Prix (USD)")
    ax.set_xlabel("Date")
    ax.grid(True, linestyle=":", alpha=0.5)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180)
    print(f"Graphique sauvegardé -> {out_path}")


def main():
    p = argparse.ArgumentParser(description="Vérifie la continuité des prix BTC-USD depuis 2013.")
    p.add_argument("--start", type=str, default=DEF_START, help="Date de début (YYYY-MM-DD).")
    p.add_argument("--end", type=str, default=None, help="Date de fin (YYYY-MM-DD).")
    p.add_argument("--csv", type=str, default=None, help="Chemin d'un CSV local (colonnes date, close) si pas d'Internet.")
    p.add_argument("--plot", type=str, default=None, help="Chemin de sauvegarde du graphique.")
    args = p.parse_args()

    try:
        df = load_btc_prices(start=args.start, end=args.end, csv_path=args.csv)
    except Exception as exc:  # pragma: no cover - dépend d'Internet
        print(f"Erreur lors du chargement des prix BTC-USD: {exc}")
        if args.csv:
            print("Vérifiez le format du CSV ou la couverture temporelle demandée.")
        else:
            print("Vous pouvez fournir un CSV local via --csv pour contourner l'absence d'Internet.")
        sys.exit(1)
    stats = analyze_series(df)

    print("=== Résumé données BTC-USD ===")
    for k, v in stats.items():
        if k != "gap_examples":
            print(f"{k:>14}: {v}")
    if not stats["gap_examples"].empty:
        print("\nExemples de gaps (>1 jour):")
        print(stats["gap_examples"])
    else:
        print("\nAucun gap détecté (>1 jour).")

    if args.plot:
        plot_prices(df, Path(args.plot))


if __name__ == "__main__":
    main()
