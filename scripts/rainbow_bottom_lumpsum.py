"""Simulation lump-sum basée sur le dernier ruban Rainbow.

Règle demandée:
- Identifier les épisodes où le prix reste au moins `min_days` jours dans le
  dernier ruban (bande la plus basse du Rainbow Chart).
- Après un épisode éligible et une sortie du ruban, le prochain retour dans le
  ruban déclenche un achat lump-sum fixe (`amount`).
- On répète cela sur tout l'historique et on compare au buy & hold (B&H).
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import List

import pandas as pd

from fngbt.data import load_btc_prices
from fngbt.strategy import calculate_rainbow_position, _quantize_bands


@dataclass
class LumpSumConfig:
    amount: float = 50.0
    min_days_in_band: int = 7
    band_count: int = 8
    rainbow_top_decay: float = 0.0


def find_bottom_band_entries(df: pd.DataFrame, cfg: LumpSumConfig) -> List[int]:
    d = calculate_rainbow_position(df, top_decay=cfg.rainbow_top_decay)
    band_ids, _ = _quantize_bands(d["rainbow_position"], cfg.band_count)
    d["rainbow_band"] = band_ids

    in_bottom = band_ids == 0
    # Identify consecutive runs in the bottom band
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


def simulate_lump_sum(df: pd.DataFrame, entries: List[int], amount: float) -> pd.DataFrame:
    d = df.copy().reset_index(drop=True)
    d["contribution"] = 0.0
    d.loc[entries, "contribution"] = amount

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


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Lump-sum sur le dernier ruban Rainbow")
    p.add_argument("--start", type=str, default="2013-01-01", help="Date de début (YYYY-MM-DD)")
    p.add_argument("--end", type=str, default=None, help="Date de fin (YYYY-MM-DD)")
    p.add_argument("--amount", type=float, default=50.0, help="Montant investi à chaque signal")
    p.add_argument("--min-days", type=int, default=7, help="Durée minimale dans le dernier ruban pour qualifier un retour")
    p.add_argument("--bands", type=int, default=8, help="Nombre de rubans pour la quantisation")
    p.add_argument("--top-decay", type=float, default=0.0, help="Décroissance annuelle appliquée à la bande haute")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = LumpSumConfig(
        amount=args.amount,
        min_days_in_band=args.min_days,
        band_count=args.bands,
        rainbow_top_decay=args.top_decay,
    )

    df_px = load_btc_prices(start=args.start, end=args.end)
    entries = find_bottom_band_entries(df_px, cfg)
    sim = simulate_lump_sum(df_px, entries, cfg.amount)
    stats = summarize(sim)

    print("===== LUMP-SUM DANS LE DERNIER RUBAN =====")
    print(f"Période: {df_px['date'].min().date()} → {df_px['date'].max().date()} ({len(df_px)} jours)")
    print(f"Signal: retour dans le ruban 0 après un séjour >= {cfg.min_days_in_band} jours")
    print(f"Montant par achat: {cfg.amount:.2f} €")
    print(f"Décroissance bande haute: {cfg.rainbow_top_decay}")
    print()
    print(f"Nombre de signaux: {stats['signals']}")
    print(f"Capital investi: {stats['total_invested']:.2f} €")
    print(f"Valeur finale stratégie: {stats['final_value']:.2f} € (x{stats['multiple']:.2f})")
    print(f"Buy & Hold (même capital investi au début): {stats['bh_final']:.2f} € (x{stats['bh_multiple']:.2f})")
    print(f"Max Drawdown de la stratégie: {stats['max_dd']*100:.2f}%")

    # Sauvegarde rapide pour inspection si besoin
    sim.to_csv("outputs/rainbow_bottom_lumpsum.csv", index=False)
    print("Détail journalier enregistré dans outputs/rainbow_bottom_lumpsum.csv")


if __name__ == "__main__":
    main()
