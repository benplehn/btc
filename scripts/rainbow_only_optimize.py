"""Optimisation d'une stratégie 100% Rainbow Chart.

Usage exemple:
    PYTHONPATH=src python scripts/rainbow_only_optimize.py --search optuna --n-trials 150
"""

import argparse
import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from fngbt.data import load_btc_prices
from fngbt.optimize import (
    optuna_search_rainbow_only,
    grid_search_rainbow_only,
    rainbow_only_search_space,
)
from fngbt.strategy import RainbowOnlyConfig, build_rainbow_only_signals
from fngbt.backtest import run_backtest


def parse_args():
    p = argparse.ArgumentParser(description="Optimise une stratégie basée uniquement sur le Rainbow Chart.")
    p.add_argument("--start", type=str, default="2013-01-01", help="Début des prix BTC (YYYY-MM-DD).")
    p.add_argument("--end", type=str, default=None, help="Fin des prix BTC (YYYY-MM-DD).")
    p.add_argument("--search", choices=["grid", "optuna"], default="optuna", help="Méthode d'optimisation.")
    p.add_argument("--n-trials", type=int, default=150, help="Nb de trials Optuna (si search=optuna).")
    p.add_argument("--fees-bps", type=float, default=10.0, help="Frais de transaction en bps (0.1% = 10 bps).")
    p.add_argument("--initial-capital", type=float, default=100.0, help="Capital de départ en euros.")
    p.add_argument("--min-trades-per-year", type=float, default=0.5, help="Filtre trades/an minimum.")
    p.add_argument("--wf-folds", type=int, default=5, help="Nombre de folds walk-forward.")
    p.add_argument("--wf-train-ratio", type=float, default=0.6, help="Ratio train pour walk-forward.")
    p.add_argument(
        "--objective",
        choices=["equity_ratio", "equity_final", "equity_value", "cagr", "sharpe", "sortino", "calmar"],
        default="equity_ratio",
        help="Métrique à maximiser pendant la recherche.",
    )
    p.add_argument(
        "--turnover-penalty",
        type=float,
        default=0.0,
        help="Pénalité par unité de turnover (ex: 0.01 réduit le score de 0.01 par changement de 100%).",
    )
    p.add_argument("--out", type=str, default="outputs/rainbow_only_results.csv", help="Fichier CSV de sortie.")
    p.add_argument(
        "--plot",
        type=str,
        default="outputs/rainbow_only_equity.png",
        help="Fichier image pour le graphe stratégie vs B&H.",
    )
    return p.parse_args()


def main():
    args = parse_args()

    print("=" * 80)
    print("🚀 OPTIMISATION RAINBOW ONLY")
    print("=" * 80)
    print(f"🎯 Objectif: {args.objective}  |  Pénalité turnover: {args.turnover_penalty}")

    px = load_btc_prices(start=args.start, end=args.end)
    print(f"Données BTC chargées: {len(px)} jours du {px['date'].min().date()} au {px['date'].max().date()}")

    search_space = rainbow_only_search_space()

    if args.search == "grid":
        results_df = grid_search_rainbow_only(
            df=px,
            search_space=search_space,
            fees_bps=args.fees_bps,
            initial_capital=args.initial_capital,
            min_trades_per_year=args.min_trades_per_year,
            use_walk_forward=True,
            wf_n_folds=args.wf_folds,
            wf_train_ratio=args.wf_train_ratio,
            objective=args.objective,
            turnover_penalty=args.turnover_penalty,
        )
    else:
        results_df = optuna_search_rainbow_only(
            df=px,
            search_space=search_space,
            n_trials=args.n_trials,
            fees_bps=args.fees_bps,
            initial_capital=args.initial_capital,
            min_trades_per_year=args.min_trades_per_year,
            use_walk_forward=True,
            wf_n_folds=args.wf_folds,
            wf_train_ratio=args.wf_train_ratio,
            objective=args.objective,
            turnover_penalty=args.turnover_penalty,
        )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(out, index=False)
    print(f"\n💾 Résultats sauvegardés -> {out}")

    if results_df.empty:
        print("Aucun résultat valide.")
        return

    best = results_df.iloc[0]
    print("\n🏆 Meilleure configuration (Walk-forward)")
    for k in [
        "rainbow_buy_threshold",
        "rainbow_sell_threshold",
        "allocation_power",
        "max_allocation_pct",
        "min_allocation_pct",
        "min_position_change_pct",
        "execute_next_day",
        "band_count",
    ]:
        if k in best:
            print(f"   {k}: {best[k]}")

    print("\nPerformance médiane walk-forward:")
    for k in ["cv_EquityFinal", "cv_CAGR", "cv_MaxDD", "cv_Sharpe", "cv_trades_per_year"]:
        if k in best:
            val = best[k]
            print(f"   {k}: {val:.4f}" if isinstance(val, float) else f"   {k}: {val}")

    print("\nDiagnostics Rainbow (médian walk-forward):")
    for k in [
        "cv_rainbow_pos_mean",
        "cv_rainbow_pos_std",
        "cv_rainbow_time_in_buy_zone",
        "cv_rainbow_time_in_sell_zone",
        "cv_rainbow_band_velocity",
        "cv_rainbow_band_cross_per_year",
        "cv_rainbow_pos_velocity",
        "cv_rainbow_pos_up_speed",
        "cv_rainbow_pos_down_speed",
        "cv_rainbow_pos_drift",
    ]:
        if k in best:
            val = best[k]
            print(f"   {k}: {val:.4f}")

    cfg = RainbowOnlyConfig(
        rainbow_buy_threshold=float(best["rainbow_buy_threshold"]),
        rainbow_sell_threshold=float(best["rainbow_sell_threshold"]),
        allocation_power=float(best["allocation_power"]),
        max_allocation_pct=int(best["max_allocation_pct"]),
        min_allocation_pct=int(best["min_allocation_pct"]),
        min_position_change_pct=float(best["min_position_change_pct"]),
        execute_next_day=bool(best["execute_next_day"]),
        band_count=int(best.get("band_count", 8)),
    )

    print("\n📈 Backtest complet avec la meilleure config...")
    signals_df = build_rainbow_only_signals(px, cfg)
    backtest = run_backtest(signals_df, fees_bps=args.fees_bps, initial_capital=args.initial_capital)

    metrics = backtest["metrics"]
    print("\nMétriques complètes:")
    for key in [
        "EquityFinalValue",
        "EquityFinal",
        "CAGR",
        "MaxDD",
        "Sharpe",
        "Sortino",
        "Calmar",
        "trades",
        "trades_per_year",
        "turnover_total",
        "avg_allocation",
    ]:
        if key in metrics:
            val = metrics[key]
            if isinstance(val, float):
                print(f"   {key}: {val:.4f}")
            else:
                print(f"   {key}: {val}")

    bh_ratio = metrics.get("EquityFinal", 0.0) / max(metrics.get("BHEquityFinal", 1.0), 1e-12)
    print(f"   Ratio vs Buy & Hold: {bh_ratio:.3f}x")

    if args.plot:
        out_plot = Path(args.plot)
        out_plot.parent.mkdir(parents=True, exist_ok=True)
        d = backtest["df"].copy()
        eq_val = d["equity"] * args.initial_capital
        bh_val = d["bh_equity"] * args.initial_capital

        plt.figure(figsize=(11, 6))
        plt.plot(d["date"], eq_val, label="Stratégie Rainbow", color="#1f77b4")
        plt.plot(d["date"], bh_val, label="Buy & Hold", color="#ff7f0e", linestyle="--")
        plt.yscale("log")
        plt.title("Equity: Rainbow-only vs Buy & Hold")
        plt.xlabel("Date")
        plt.ylabel("Valeur du portefeuille (€)")
        plt.legend()
        plt.grid(alpha=0.3)
        plt.tight_layout()
        plt.savefig(out_plot, dpi=150)
        print(f"\n🖼️ Graphe sauvegardé -> {out_plot}")


if __name__ == "__main__":
    main()
