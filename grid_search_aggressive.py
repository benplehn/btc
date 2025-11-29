#!/usr/bin/env python3
"""
Grid Search AGRESSIF - Sans contraintes

Si le grid search standard ne trouve rien, on teste TOUT:
- Full range 0-100% pour toutes allocations
- Sans contraintes logiques
- Combinaisons extrêmes permises
"""
import pandas as pd
import numpy as np
from itertools import product
from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.strategy import calculate_rainbow_position
from src.fngbt.backtest import run_backtest

def build_simple_allocation(df, fng_low, fng_high, rainbow_low, rainbow_high,
                            alloc_min, alloc_max):
    """
    Stratégie SIMPLE: Allocation linéaire basée sur FNG et Rainbow

    - Si FNG bas ET Rainbow bas → alloc_max
    - Si FNG haut ET Rainbow haut → alloc_min
    - Sinon → interpolation linéaire
    """
    d = df.copy()
    d = calculate_rainbow_position(d)

    # Score combiné (0 = fear+bas = achat, 1 = greed+haut = vente)
    fng_score = np.clip((d['fng'] - fng_low) / (fng_high - fng_low), 0, 1)
    rainbow_score = np.clip((d['rainbow_position'] - rainbow_low) / (rainbow_high - rainbow_low), 0, 1)

    combined_score = (fng_score + rainbow_score) / 2.0

    # Allocation: inverse du score (bas score = haute allocation)
    allocation = alloc_max - (alloc_max - alloc_min) * combined_score

    d['pos'] = allocation
    d['trade'] = (d['pos'].diff().abs() > 5).astype(int)

    return d

def grid_search_aggressive(df, top_n=20):
    """
    Grid search agressif avec ranges extrêmes
    """
    print("="*100)
    print("🔥 GRID SEARCH AGRESSIF: Ranges extrêmes sans contraintes")
    print("="*100)

    # Buy & Hold baseline
    bh = df.copy()
    bh['pos'] = 100.0
    bh['trade'] = 0
    bh_result = run_backtest(bh, fees_bps=0.0)
    bh_equity = bh_result['metrics']['EquityFinal']

    print(f"\n📊 Baseline B&H: {bh_equity:.2f}x")

    # Grilles agressives
    fng_lows = [10, 15, 20, 25, 30, 35]
    fng_highs = [65, 70, 75, 80, 85, 90]
    rainbow_lows = [0.15, 0.2, 0.25, 0.3, 0.35, 0.4]
    rainbow_highs = [0.6, 0.65, 0.7, 0.75, 0.8, 0.85]
    alloc_mins = [0, 5, 10, 15, 20]  # Allocation MIN (en greed+haut)
    alloc_maxs = [95, 100]  # Allocation MAX (en fear+bas)

    total = len(fng_lows) * len(fng_highs) * len(rainbow_lows) * len(rainbow_highs) * len(alloc_mins) * len(alloc_maxs)

    print(f"\n⏳ Total combinaisons: {total:,}")

    results = []
    tested = 0

    for fng_low, fng_high in product(fng_lows, fng_highs):
        if fng_low >= fng_high:
            continue

        for rainbow_low, rainbow_high in product(rainbow_lows, rainbow_highs):
            if rainbow_low >= rainbow_high:
                continue

            for alloc_min, alloc_max in product(alloc_mins, alloc_maxs):
                if alloc_min >= alloc_max:
                    continue

                tested += 1

                try:
                    signals = build_simple_allocation(
                        df, fng_low, fng_high, rainbow_low, rainbow_high,
                        alloc_min, alloc_max
                    )

                    result = run_backtest(signals, fees_bps=10.0)
                    metrics = result['metrics']
                    ratio = metrics['EquityFinal'] / bh_equity

                    results.append({
                        'fng_low': fng_low,
                        'fng_high': fng_high,
                        'rainbow_low': rainbow_low,
                        'rainbow_high': rainbow_high,
                        'alloc_min': alloc_min,
                        'alloc_max': alloc_max,
                        'equity': metrics['EquityFinal'],
                        'ratio': ratio,
                        'cagr': metrics['CAGR'],
                        'max_dd': metrics['MaxDD'],
                        'sharpe': metrics['Sharpe'],
                        'trades': metrics['trades']
                    })

                    if tested % 500 == 0:
                        best_so_far = max(results, key=lambda x: x['ratio'])
                        print(f"   Testé: {tested:,} | Meilleur: {best_so_far['ratio']:.3f}x", end='\r')

                except Exception:
                    continue

    print(f"\n✅ Tests terminés: {tested:,} combinaisons")

    # Trier
    results.sort(key=lambda x: x['ratio'], reverse=True)

    # Top N
    print(f"\n{'='*100}")
    print(f"🏆 TOP {top_n} RÉSULTATS")
    print(f"{'='*100}\n")

    print(f"{'Rank':<6} {'Ratio':>8} {'Equity':>8} {'CAGR':>7} {'DD':>7} {'Trades':>7} | "
          f"FNG       Rainbow    | Alloc")
    print("-" * 100)

    for i, r in enumerate(results[:top_n], 1):
        marker = "🥇" if i == 1 else ("🥈" if i == 2 else ("🥉" if i == 3 else "  "))
        print(f"{marker} {i:<3} {r['ratio']:>7.3f}x {r['equity']:>7.2f}x {r['cagr']*100:>6.1f}% "
              f"{r['max_dd']*100:>6.1f}% {r['trades']:>7} | "
              f"{r['fng_low']:>2}-{r['fng_high']:<2}  {r['rainbow_low']:.2f}-{r['rainbow_high']:<.2f} | "
              f"{r['alloc_min']:>3}%-{r['alloc_max']:>3}%")

    best = results[0]

    if best['ratio'] > 1.0:
        print(f"\n🚀 SUCCÈS! Ratio: {best['ratio']:.3f}x vs B&H")
    else:
        print(f"\n⚠️  Meilleur: {best['ratio']:.3f}x vs B&H (sous-performe)")

    # Sauvegarder
    results_df = pd.DataFrame(results[:100])
    results_df.to_csv('outputs/grid_search_aggressive_results.csv', index=False)
    print(f"\n💾 Résultats sauvegardés: outputs/grid_search_aggressive_results.csv")

    return results, best

if __name__ == "__main__":
    print("Chargement données...")
    fng = load_fng_alt()
    btc = load_btc_prices()
    df = merge_daily(fng, btc)
    print(f"✅ {len(df)} jours\n")

    results, best = grid_search_aggressive(df, top_n=30)
