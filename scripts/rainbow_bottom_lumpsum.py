"""Simulation lump-sum basée sur le dernier ruban Rainbow.

Règle demandée:
- Identifier les épisodes où le prix reste au moins `min_days` jours dans le
  dernier ruban (bande la plus basse du Rainbow Chart).
- Après un épisode éligible et une sortie du ruban, le prochain retour dans le
  ruban déclenche un achat lump-sum fixe (`amount`).
- On répète cela sur tout l'historique et on compare à un DCA mensuel qui
  répartit le même capital total sur la période.
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
    p = argparse.ArgumentParser(description="Lump-sum sur le dernier ruban Rainbow")
    p.add_argument("--start", type=str, default="2018-01-01", help="Date de début (YYYY-MM-DD)")
    p.add_argument("--end", type=str, default=None, help="Date de fin (YYYY-MM-DD)")
    p.add_argument("--amount", type=float, default=50.0, help="Montant investi à chaque signal")
    p.add_argument("--min-days", type=int, default=1, help="Durée minimale dans le dernier ruban pour qualifier un retour")
    p.add_argument("--bands", type=int, default=8, help="Nombre de rubans pour la quantisation")
    p.add_argument("--top-decay", type=float, default=0.0, help="Décroissance annuelle appliquée à la bande haute")
    p.add_argument(
        "--no-plots",
        action="store_true",
        help="Désactive l'enregistrement des graphiques (prix/trades, equity, overview)",
    )
    p.add_argument(
        "--plot-price",
        type=str,
        default="outputs/rainbow_bottom_lumpsum_price.png",
        help="Chemin du graphe prix + rubans + achats",
    )
    p.add_argument(
        "--plot-equity",
        type=str,
        default="outputs/rainbow_bottom_lumpsum_equity.png",
        help="Chemin du graphe equity (stratégie vs DCA)",
    )
    p.add_argument(
        "--plot-overview",
        type=str,
        default="outputs/rainbow_bottom_lumpsum_overview.png",
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

    print("===== LUMP-SUM DANS LE DERNIER RUBAN =====")
    print(
        f"Période: {sim['date'].min().date()} → {sim['date'].max().date()} "
        f"({len(sim)} jours)"
    )
    print(f"Signal: retour dans le ruban 0 après un séjour >= {cfg.min_days_in_band} jours")
    print(f"Montant par achat: {cfg.amount:.2f} €")
    print(f"Décroissance bande haute: {cfg.rainbow_top_decay}")
    print()
    print(f"Nombre de signaux: {stats['signals']}")
    print(f"Capital investi: {stats['total_invested']:.2f} €")
    print(f"Valeur finale stratégie: {stats['final_value']:.2f} € (x{stats['multiple']:.2f})")
    print(
        "DCA mensuel (même capital total, lissé sur la période): "
        f"{stats['dca_final']:.2f} € (x{stats['dca_multiple']:.2f})"
    )
    print(f"Max Drawdown de la stratégie: {stats['max_dd']*100:.2f}%")

    # Sauvegarde rapide pour inspection si besoin
    sim.to_csv("outputs/rainbow_bottom_lumpsum.csv", index=False)
    print("Détail journalier enregistré dans outputs/rainbow_bottom_lumpsum.csv")

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
