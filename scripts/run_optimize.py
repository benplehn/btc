import argparse
import itertools
import os
import sys
from pathlib import Path

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

import pandas as pd

from fngbt import (
    StrategyConfig,
    build_signals,
    default_search_space,
    grid_search_full,
    load_btc_prices,
    load_fng_alt,
    merge_daily,
    optuna_search,
    plot_overview,
    run_backtest,
    to_weekly,
)

OUT = Path("outputs")


def parse_args():
    p = argparse.ArgumentParser(description="Optimisation (grid ou Optuna) du moteur FNG (paliers) + Rainbow (sizing).")
    p.add_argument("--fees-bps", type=float, default=10.0, help="Frais aller-retour en bps.")
    p.add_argument("--weekly", action="store_true", help="Utiliser des données hebdo (vendredi).")
    p.add_argument("--lookback-years", type=float, default=6.0, help="Restreint l'historique aux X dernières années (None pour tout).")
    p.add_argument(
        "--fng-levels",
        type=str,
        default="3",
        help="Nombre de paliers FNG (buy/sell). Ex: '3' ou '3,4' pour tester 3 et 4 paliers.",
    )
    p.add_argument(
        "--fng-source-cols",
        type=str,
        default="fng,ema200_soft",
        help="Colonnes FNG candidates (comma) ex: 'fng,ema200_soft'.",
    )
    p.add_argument(
        "--rainbow-k-grid",
        type=str,
        default="1.0,1.5,2.0",
        help="Grille pour le paramètre k de la courbe Rainbow A(x).",
    )
    p.add_argument(
        "--max-alloc-grid",
        type=str,
        default="80,100",
        help="Plafond d'allocation (%) testé.",
    )
    p.add_argument(
        "--min-trades-per-year",
        type=float,
        default=3.0,
        help="Filtre : nombre de trades/an minimal.",
    )
    p.add_argument("--min-hold-days", type=int, default=3, help="Hold minimal avant nouveau trade.")
    p.add_argument("--ramp-step-grid", type=str, default="5,10", help="Pas (%) de quantification d'allocation.")
    p.add_argument("--fng-step", type=int, default=5, help="Pas (%) pour générer les paliers FNG (0..100).")
    p.add_argument(
        "--search",
        choices=["grid", "optuna"],
        default="optuna",
        help="grid = exhaustif; optuna = échantillonnage intelligent.",
    )
    p.add_argument(
        "--cv-mode",
        choices=["none", "kfold", "walkforward"],
        default="walkforward",
        help="Validation temporelle: none (full sample), kfold (segments contigus), walkforward (segments successifs).",
    )
    p.add_argument(
        "--cv-folds",
        type=int,
        default=4,
        help="Nombre de segments pour la validation temporelle.",
    )
    p.add_argument(
        "--cv-warmup-days",
        type=int,
        default=160,
        help="Jours de contexte ajoutés avant chaque fold pour stabiliser les indicateurs.",
    )
    p.add_argument("--n-trials", type=int, default=300, help="Nb de trials Optuna (si search=optuna).")
    p.add_argument("--out-csv", type=str, default=str(OUT / "opt_results.csv"), help="Sauvegarde des résultats.")
    return p.parse_args()


def _parse_grid(val: str, cast=float):
    """
    Accepte "1,2,3" ou "start:end:step".
    """
    if ":" in val:
        parts = val.split(":")
        if len(parts) not in (2, 3):
            raise ValueError(f"Format de range invalide: {val}")
        start = cast(parts[0]); end = cast(parts[1]); step = cast(parts[2]) if len(parts)==3 else 1
        return [cast(x) for x in frange(start, end, step)]
    return [cast(x) for x in val.split(",") if str(x).strip() != ""]


def _parse_str_list(val: str) -> list[str]:
    return [x.strip() for x in val.split(",") if str(x).strip() != ""]


def frange(start, end, step):
    out = []
    x = start
    forward = step > 0
    while (forward and x <= end) or ((not forward) and x >= end):
        out.append(x)
        x = x + step
    return out


def _all_combos_step(min_val: int, max_val: int, step: int, n_levels: int) -> list[list[int]]:
    vals = list(range(min_val, max_val + step, step))
    return [list(c) for c in itertools.combinations(vals, n_levels)]


def main():
    args = parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    fng = load_fng_alt()
    px = load_btc_prices(start=fng["date"].min())
    df = merge_daily(fng, px)
    if args.weekly:
        df = to_weekly(df, how="last")
    if args.lookback_years:
        cutoff = df["date"].max() - pd.Timedelta(days=int(args.lookback_years * 365))
        df = df[df["date"] >= cutoff].reset_index(drop=True)

    # Prépare un FNG très lissé (ema200) utilisable via fng_source_col
    if "fng" in df.columns:
        df["ema200_soft"] = df["fng"].ewm(span=200, adjust=False).mean()

    step = max(1, int(args.fng_step))
    level_counts = [max(3, int(x)) for x in _parse_grid(args.fng_levels, int)]
    fng_buy_combos = list(
        itertools.chain.from_iterable(_all_combos_step(0, 50, step, n) for n in level_counts)
    )
    fng_sell_combos = list(
        itertools.chain.from_iterable(_all_combos_step(50, 100, step, n) for n in level_counts)
    )
    fng_curve_vals = [1.0]
    fng_smooth_vals = [1]
    fng_source_cols = _parse_str_list(args.fng_source_cols)
    rainbow_k_vals = _parse_grid(args.rainbow_k_grid, float)
    max_alloc_vals = _parse_grid(args.max_alloc_grid, int)
    ramp_step_vals = _parse_grid(args.ramp_step_grid, int)

    space = default_search_space(
        use_fng=True,
        fng_source_cols=fng_source_cols,
        fng_buy_vals=[0],  # ignoré, remplacé par paliers
        fng_sell_vals=[100],  # ignoré, remplacé par paliers
        fng_buy_levels_vals=fng_buy_combos,
        fng_sell_levels_vals=fng_sell_combos,
        fng_curve_exp_vals=fng_curve_vals,
        fng_smoothing_vals=fng_smooth_vals,
        use_rainbow=True,
        rainbow_k_vals=rainbow_k_vals,
        max_allocation_pct_vals=max_alloc_vals,
        ramp_step_pct_vals=ramp_step_vals,
        min_hold_days_vals=[args.min_hold_days],
    )
    if args.search == "optuna":
        res = optuna_search(
            df,
            search_space=space,
            n_trials=args.n_trials,
            fees_bps=args.fees_bps,
            min_trades_per_year=args.min_trades_per_year,
            cv_mode=args.cv_mode,
            cv_folds=args.cv_folds,
            cv_warmup_days=args.cv_warmup_days,
        )
    else:
        res = grid_search_full(
            df,
            search_space=space,
            fees_bps=args.fees_bps,
            min_trades_per_year=args.min_trades_per_year,
            cv_mode=args.cv_mode,
            cv_folds=args.cv_folds,
            cv_warmup_days=args.cv_warmup_days,
        )

    out_csv = Path(args.out_csv)
    res.to_csv(out_csv, index=False)
    print(f"Résultats sauvegardés: {out_csv}")

    if res.empty:
        print("Aucune combinaison évaluée. Vérifie la longueur des données.")
        return

    print("\n=== Top 5 (score décroissant) ===")
    cols = [
        "score",
        "med_equity_ratio",
        "full_equity_ratio",
        "med_Calmar",
        "med_Sharpe",
        "med_CAGR",
        "med_MaxDD",
        "med_trades_per_year",
        "use_fng",
        "use_rainbow",
    ]
    print(res.head(5)[[c for c in cols if c in res.columns]])

    best = res.iloc[0]
    cfg_kwargs = {field: best[field] for field in StrategyConfig.__annotations__ if field in best.index}
    cfg = StrategyConfig(**cfg_kwargs)
    print("\n=== Meilleure config ===")
    for k, v in cfg.to_dict().items():
        print(f"{k:>20}: {v}")

    sig = build_signals(df, cfg)
    final = run_backtest(sig, fees_bps=args.fees_bps)
    print("\n=== Metrics sur l'échantillon complet ===")
    for k, v in final["metrics"].items():
        print(f"{k:>16}: {v:.4f}" if isinstance(v, float) else f"{k:>16}: {v}")

    plot_path = OUT / "best_overview.png"
    plot_overview(final["df"], cfg, title="Best FNG (régime) + Rainbow (sizing)", out=plot_path)
    print(f"Graphique sauvegardé: {plot_path}")


if __name__ == "__main__":
    main()
