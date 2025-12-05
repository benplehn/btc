"""Simulation dédiée au facteur "LowestWindowWeapon" uniquement.

La stratégie se contente de repérer les retours dans le dernier ruban du
Rainbow (bande 0) après un séjour d'au moins `min_days` jours, et d'investir un
montant fixe à chaque re-rentrée qualifiée. Aucun autre signal n'est utilisé.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from fngbt.lowest_window_weapon import (
    LowestWindowWeaponConfig,
    load_and_simulate,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Simule uniquement le facteur LowestWindowWeapon (ruban 0)."
    )
    p.add_argument("--start", type=str, default="2018-01-01", help="Date de début (YYYY-MM-DD)")
    p.add_argument("--end", type=str, default=None, help="Date de fin (YYYY-MM-DD)")
    p.add_argument("--amount", type=float, default=50.0, help="Montant investi à chaque entrée qualifiée")
    p.add_argument(
        "--min-days",
        type=int,
        default=1,
        help="Séjour minimal dans le ruban 0 avant qu'un retour déclenche un achat",
    )
    p.add_argument("--bands", type=int, default=8, help="Nombre de rubans pour la quantisation")
    p.add_argument("--top-decay", type=float, default=0.0, help="Décroissance annuelle appliquée à la bande haute")
    p.add_argument("--out", type=str, default="outputs/lowest_window_weapon.csv", help="Chemin du CSV de sortie")
    p.add_argument(
        "--no-plots",
        action="store_true",
        help="Désactive l'enregistrement des graphiques (prix/trades, equity, overview)",
    )
    p.add_argument(
        "--plot-price",
        type=str,
        default="outputs/lowest_window_weapon_price.png",
        help="Chemin du graphe prix + rubans + achats",
    )
    p.add_argument(
        "--plot-equity",
        type=str,
        default="outputs/lowest_window_weapon_equity.png",
        help="Chemin du graphe equity (stratégie vs DCA)",
    )
    p.add_argument(
        "--plot-overview",
        type=str,
        default="outputs/lowest_window_weapon_overview.png",
        help="Chemin du graphe combiné prix + achats + equity",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = LowestWindowWeaponConfig(
        amount=args.amount,
        min_days_in_band=args.min_days,
        band_count=args.bands,
        rainbow_top_decay=args.top_decay,
    )

    sim, stats = load_and_simulate(args.start, args.end, cfg)

    print("================ LOWEST WINDOW WEAPON ================")
    print(
        f"Période: {sim['date'].min().date()} → {sim['date'].max().date()} "
        f"({len(sim)} jours)"
    )
    print(
        "Facteur unique: retour dans le ruban 0 après un séjour de "
        f">= {cfg.min_days_in_band} jours"
    )
    print(f"Montant par entrée: {cfg.amount:.2f} €")
    print(f"Décroissance bande haute: {cfg.rainbow_top_decay}")
    print()
    print(f"Nombre d'achats déclenchés: {stats['signals']}")
    print(f"Capital investi: {stats['total_invested']:.2f} €")
    print(f"Valeur finale stratégie: {stats['final_value']:.2f} € (x{stats['multiple']:.2f})")
    print(
        "DCA mensuel (même capital total, lissé sur la période): "
        f"{stats['dca_final']:.2f} € (x{stats['dca_multiple']:.2f})"
    )
    print(f"Max Drawdown de la stratégie: {stats['max_dd']*100:.2f}%")

    sim.to_csv(args.out, index=False)
    print(f"Résultats détaillés exportés vers {args.out}")

    if not args.no_plots:
        from fngbt.lowest_window_weapon import plot_equity, plot_overview, plot_price_with_signals

        plot_price_with_signals(sim, cfg, args.plot_price)
        plot_equity(sim, args.plot_equity)
        plot_overview(sim, cfg, args.plot_overview)
        print("Graphiques sauvegardés :")
        print(f"- Prix + rubans + achats : {args.plot_price}")
        print(f"- Equity stratégie vs DCA : {args.plot_equity}")
        print(f"- Vue combinée : {args.plot_overview}")


if __name__ == "__main__":
    main()
