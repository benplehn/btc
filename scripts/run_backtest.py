import argparse
import os
import sys
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from fngbt import (
    StrategyConfig,
    build_signals,
    load_btc_prices,
    load_fng_alt,
    merge_daily,
    plot_overview,
    run_backtest,
    to_weekly,
)


def _parse_int_list(val: str) -> list[int]:
    if not val.strip():
        return []
    return [int(x.strip()) for x in val.split(",") if x.strip()]


def parse_args():
    p = argparse.ArgumentParser(description="Backtest BTC : FNG (régime) + Rainbow (sizing).")
    p.add_argument("--fees-bps", type=float, default=10.0, help="Frais aller-retour en bps.")
    p.add_argument("--weekly", action="store_true", help="Utiliser des données hebdo (vendredi).")
    p.add_argument("--lookback-years", type=float, default=6.0, help="Restreint l'historique aux X dernières années (None pour tout).")
    p.add_argument("--no-fng", action="store_true", help="Désactive le filtre Fear & Greed.")
    p.add_argument("--no-rainbow", action="store_true", help="Désactive le sizing Rainbow.")
    p.add_argument("--fng-buy", type=int, default=25, help="Seuil F&G pour achat (mode accumulation).")
    p.add_argument("--fng-sell", type=int, default=70, help="Seuil F&G pour vente (mode distribution).")
    p.add_argument("--fng-buys", type=str, default="", help="Liste de seuils FNG d'achat (ex: 30,20,10).")
    p.add_argument("--fng-sells", type=str, default="", help="Liste de seuils FNG de vente (ex: 60,70,80).")
    p.add_argument("--fng-curve", type=float, default=1.2, help="Exposant de courbure FNG (1=linéaire, >1=plus binaire).")
    p.add_argument("--fng-smooth", type=int, default=1, help="Lissage EMA du FNG (jours).")
    p.add_argument("--rainbow-k", type=float, default=1.5, help="Paramètre k de la courbe Rainbow A(x).")
    p.add_argument("--max-alloc", type=int, default=100, help="Plafond d'allocation (%)")
    p.add_argument("--min-hold-days", type=int, default=3, help="Hold minimal avant nouveau trade.")
    p.add_argument("--ramp-step", type=int, default=5, help="Pas de quantification de l'allocation (%).")
    p.add_argument("--same-day", action="store_true", help="Exécuter le signal le jour même (sinon J+1 par défaut).")
    p.add_argument("--out", type=str, default=None, help="Chemin png pour sauvegarder le graphique.")
    return p.parse_args()


def main():
    args = parse_args()

    fng = load_fng_alt()
    px = load_btc_prices(start=fng["date"].min())
    df = merge_daily(fng, px)
    if args.weekly:
        df = to_weekly(df, how="last")
    if args.lookback_years:
        cutoff = df["date"].max() - pd.Timedelta(days=int(args.lookback_years * 365))
        df = df[df["date"] >= cutoff].reset_index(drop=True)

    cfg = StrategyConfig(
        use_fng=not args.no_fng,
        fng_buy=args.fng_buy,
        fng_sell=args.fng_sell,
        fng_buy_levels=_parse_int_list(args.fng_buys) or None,
        fng_sell_levels=_parse_int_list(args.fng_sells) or None,
        use_rainbow=not args.no_rainbow,
        fng_curve_exp=float(args.fng_curve),
        fng_smoothing_days=int(args.fng_smooth),
        rainbow_k=float(args.rainbow_k),
        max_allocation_pct=int(args.max_alloc),
        min_hold_days=max(0, int(args.min_hold_days)),
        ramp_step_pct=max(1, int(args.ramp_step)),
        execute_next_day=not args.same_day,
    )

    sig = build_signals(df, cfg)
    res = run_backtest(sig, fees_bps=args.fees_bps)

    print("=== Config ===")
    for k, v in cfg.to_dict().items():
        print(f"{k:>20}: {v}")

    print("\n=== Metrics (test unique) ===")
    for k, v in res["metrics"].items():
        print(f"{k:>16}: {v:.4f}" if isinstance(v, float) else f"{k:>16}: {v}")

    title = "BTC strategy: FNG (régime) + Rainbow (sizing)"
    plot_overview(res["df"], cfg, title=title, out=args.out)


if __name__ == "__main__":
    main()
