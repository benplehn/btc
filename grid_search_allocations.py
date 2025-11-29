#!/usr/bin/env python3
"""
Grid Search EXHAUSTIF pour trouver les meilleures allocations
en fonction du FNG et Rainbow Chart

Logique: Plus on est haut (greed + rainbow haut) = moins d'allocation
         Plus on est bas (fear + rainbow bas) = plus d'allocation
"""
import pandas as pd
import numpy as np
from itertools import product
from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.strategy import calculate_rainbow_position
from src.fngbt.backtest import run_backtest

def build_allocation_strategy(df, fng_zones, rainbow_zones, allocation_matrix):
    """
    Construit une stratégie basée sur zones FNG x Rainbow

    Args:
        fng_zones: [low_threshold, high_threshold] ex: [25, 75]
        rainbow_zones: [low_threshold, high_threshold] ex: [0.3, 0.7]
        allocation_matrix: [[low_fng_low_rainbow, low_fng_high_rainbow],
                           [high_fng_low_rainbow, high_fng_high_rainbow]]

    Zones:
    - FNG < low: FEAR (zone d'achat)
    - FNG > high: GREED (zone de vente)
    - Rainbow < low: Prix BAS (zone d'achat)
    - Rainbow > high: Prix HAUT (zone de vente)

    Matrice d'allocation:
    - [0][0]: FNG Fear + Rainbow Bas = MAX allocation (ex: 100%)
    - [0][1]: FNG Fear + Rainbow Haut = allocation moyenne (ex: 70%)
    - [1][0]: FNG Greed + Rainbow Bas = allocation moyenne (ex: 70%)
    - [1][1]: FNG Greed + Rainbow Haut = MIN allocation (ex: 20%)
    """
    d = df.copy()
    d = calculate_rainbow_position(d)

    fng_low, fng_high = fng_zones
    rainbow_low, rainbow_high = rainbow_zones

    # Matrice d'allocation
    alloc_fear_low = allocation_matrix[0][0]   # Fear + Rainbow bas
    alloc_fear_high = allocation_matrix[0][1]  # Fear + Rainbow haut
    alloc_greed_low = allocation_matrix[1][0]  # Greed + Rainbow bas
    alloc_greed_high = allocation_matrix[1][1] # Greed + Rainbow haut

    # Classification FNG
    fng_score = np.where(
        d['fng'] <= fng_low, 0,  # Fear = 0
        np.where(d['fng'] >= fng_high, 1,  # Greed = 1
            (d['fng'] - fng_low) / (fng_high - fng_low))  # Transition linéaire
    )

    # Classification Rainbow
    rainbow_score = np.where(
        d['rainbow_position'] <= rainbow_low, 0,  # Bas = 0
        np.where(d['rainbow_position'] >= rainbow_high, 1,  # Haut = 1
            (d['rainbow_position'] - rainbow_low) / (rainbow_high - rainbow_low))
    )

    # Allocation bilinéaire
    # Interpolation 2D entre les 4 coins de la matrice
    alloc_bottom = alloc_fear_low * (1 - rainbow_score) + alloc_fear_high * rainbow_score
    alloc_top = alloc_greed_low * (1 - rainbow_score) + alloc_greed_high * rainbow_score
    allocation = alloc_bottom * (1 - fng_score) + alloc_top * fng_score

    d['pos'] = allocation
    d['trade'] = (d['pos'].diff().abs() > 5).astype(int)

    return d

def grid_search_best_allocation(df, top_n=20):
    """
    Grid search exhaustif sur:
    - Zones FNG (seuils bas/haut)
    - Zones Rainbow (seuils bas/haut)
    - Matrice d'allocation (4 valeurs)
    """
    print("="*100)
    print("🔍 GRID SEARCH EXHAUSTIF: Recherche des meilleures allocations")
    print("="*100)

    # Buy & Hold baseline
    bh = df.copy()
    bh['pos'] = 100.0
    bh['trade'] = 0
    bh_result = run_backtest(bh, fees_bps=0.0)
    bh_equity = bh_result['metrics']['EquityFinal']
    bh_cagr = bh_result['metrics']['CAGR']

    print(f"\n📊 Baseline Buy & Hold:")
    print(f"   Equity: {bh_equity:.2f}x | CAGR: {bh_cagr*100:.1f}%")

    # Grille de recherche
    fng_lows = [15, 20, 25, 30]
    fng_highs = [70, 75, 80, 85]
    rainbow_lows = [0.2, 0.25, 0.3, 0.35]
    rainbow_highs = [0.65, 0.7, 0.75, 0.8]

    # Allocations pour chaque coin de la matrice
    # [Fear+Bas, Fear+Haut, Greed+Bas, Greed+Haut]
    alloc_fear_low_options = [90, 95, 100]  # Toujours haut (achat agressif)
    alloc_fear_high_options = [50, 60, 70, 80]  # Moyen
    alloc_greed_low_options = [40, 50, 60, 70]  # Moyen
    alloc_greed_high_options = [0, 10, 20, 30]  # Toujours bas (vente agressive)

    print(f"\n🔧 Grille de recherche:")
    print(f"   FNG low: {fng_lows}")
    print(f"   FNG high: {fng_highs}")
    print(f"   Rainbow low: {rainbow_lows}")
    print(f"   Rainbow high: {rainbow_highs}")
    print(f"   Alloc Fear+Bas: {alloc_fear_low_options}")
    print(f"   Alloc Fear+Haut: {alloc_fear_high_options}")
    print(f"   Alloc Greed+Bas: {alloc_greed_low_options}")
    print(f"   Alloc Greed+Haut: {alloc_greed_high_options}")

    total_combinations = (
        len(fng_lows) * len(fng_highs) *
        len(rainbow_lows) * len(rainbow_highs) *
        len(alloc_fear_low_options) * len(alloc_fear_high_options) *
        len(alloc_greed_low_options) * len(alloc_greed_high_options)
    )

    print(f"\n⏳ Total de combinaisons à tester: {total_combinations:,}")
    print(f"   Estimation: ~{total_combinations * 0.05:.0f} secondes")

    # Grid search
    results = []
    tested = 0

    for fng_low, fng_high in product(fng_lows, fng_highs):
        if fng_low >= fng_high:
            continue

        for rainbow_low, rainbow_high in product(rainbow_lows, rainbow_highs):
            if rainbow_low >= rainbow_high:
                continue

            for alloc_fl, alloc_fh, alloc_gl, alloc_gh in product(
                alloc_fear_low_options,
                alloc_fear_high_options,
                alloc_greed_low_options,
                alloc_greed_high_options
            ):
                # Vérifier cohérence: Fear+Bas doit être >= autres allocations
                if not (alloc_fl >= alloc_fh and alloc_fl >= alloc_gl and alloc_fl >= alloc_gh):
                    continue

                # Vérifier: Greed+Haut doit être <= autres allocations
                if not (alloc_gh <= alloc_fh and alloc_gh <= alloc_gl and alloc_gh <= alloc_fl):
                    continue

                tested += 1

                try:
                    # Construire stratégie
                    signals = build_allocation_strategy(
                        df,
                        fng_zones=[fng_low, fng_high],
                        rainbow_zones=[rainbow_low, rainbow_high],
                        allocation_matrix=[[alloc_fl, alloc_fh],
                                          [alloc_gl, alloc_gh]]
                    )

                    # Backtest
                    result = run_backtest(signals, fees_bps=10.0)
                    metrics = result['metrics']

                    ratio = metrics['EquityFinal'] / bh_equity

                    results.append({
                        'fng_low': fng_low,
                        'fng_high': fng_high,
                        'rainbow_low': rainbow_low,
                        'rainbow_high': rainbow_high,
                        'alloc_fear_low': alloc_fl,
                        'alloc_fear_high': alloc_fh,
                        'alloc_greed_low': alloc_gl,
                        'alloc_greed_high': alloc_gh,
                        'equity': metrics['EquityFinal'],
                        'ratio': ratio,
                        'cagr': metrics['CAGR'],
                        'max_dd': metrics['MaxDD'],
                        'sharpe': metrics['Sharpe'],
                        'trades': metrics['trades']
                    })

                    if tested % 1000 == 0:
                        best_so_far = max(results, key=lambda x: x['ratio'])
                        print(f"   Testé: {tested:,} | Meilleur ratio: {best_so_far['ratio']:.3f}x", end='\r')

                except Exception as e:
                    continue

    print(f"\n✅ Tests terminés: {tested:,} combinaisons valides testées")

    # Trier par ratio vs B&H
    results.sort(key=lambda x: x['ratio'], reverse=True)

    # Top N résultats
    print(f"\n{'='*100}")
    print(f"🏆 TOP {top_n} STRATÉGIES (triées par ratio vs B&H)")
    print(f"{'='*100}\n")

    print(f"{'Rank':<6} {'Ratio':>8} {'Equity':>8} {'CAGR':>7} {'DD':>7} {'Trades':>7} | FNG       Rainbow    | Allocations (F+B, F+H, G+B, G+H)")
    print("-" * 100)

    for i, r in enumerate(results[:top_n], 1):
        marker = "🥇" if i == 1 else ("🥈" if i == 2 else ("🥉" if i == 3 else "  "))

        print(f"{marker} {i:<3} {r['ratio']:>7.3f}x {r['equity']:>7.2f}x {r['cagr']*100:>6.1f}% {r['max_dd']*100:>6.1f}% {r['trades']:>7} | "
              f"{r['fng_low']:>2}-{r['fng_high']:<2}  {r['rainbow_low']:.2f}-{r['rainbow_high']:<.2f} | "
              f"{r['alloc_fear_low']:>3}%, {r['alloc_fear_high']:>3}%, {r['alloc_greed_low']:>3}%, {r['alloc_greed_high']:>3}%")

    # Meilleur résultat
    best = results[0]

    print(f"\n{'='*100}")
    print(f"🎯 MEILLEURE STRATÉGIE TROUVÉE")
    print(f"{'='*100}")

    print(f"\n📊 Performance:")
    print(f"   Equity finale: {best['equity']:.2f}x")
    print(f"   Ratio vs B&H: {best['ratio']:.3f}x")
    print(f"   CAGR: {best['cagr']*100:.1f}% (vs {bh_cagr*100:.1f}% B&H)")
    print(f"   Max Drawdown: {best['max_dd']*100:.1f}%")
    print(f"   Sharpe Ratio: {best['sharpe']:.2f}")
    print(f"   Nombre de trades: {best['trades']}")

    print(f"\n🎚️  Paramètres:")
    print(f"   FNG zones: [{best['fng_low']}, {best['fng_high']}]")
    print(f"   Rainbow zones: [{best['rainbow_low']}, {best['rainbow_high']}]")
    print(f"   Allocations:")
    print(f"      Fear + Rainbow Bas:  {best['alloc_fear_low']}% (achat MAX)")
    print(f"      Fear + Rainbow Haut: {best['alloc_fear_high']}%")
    print(f"      Greed + Rainbow Bas: {best['alloc_greed_low']}%")
    print(f"      Greed + Rainbow Haut: {best['alloc_greed_high']}% (vente MAX)")

    if best['ratio'] > 1.0:
        print(f"\n🚀 SUCCÈS! Cette stratégie BAT le Buy & Hold de {best['ratio']:.2f}x!")
    else:
        print(f"\n⚠️  Même la meilleure stratégie sous-performe B&H ({best['ratio']:.2f}x)")
        print(f"    Il faut probablement:")
        print(f"    1. Élargir la grille de recherche")
        print(f"    2. Tester d'autres logiques d'allocation")
        print(f"    3. Ou accepter que sur ce bull market, B&H est roi")

    # Sauvegarder résultats
    results_df = pd.DataFrame(results[:100])
    results_df.to_csv('outputs/grid_search_results.csv', index=False)
    print(f"\n💾 Top 100 résultats sauvegardés dans: outputs/grid_search_results.csv")

    return results, best

def test_best_strategy(df, best_params):
    """Teste et visualise la meilleure stratégie trouvée"""
    print(f"\n{'='*100}")
    print(f"📊 TEST DE LA MEILLEURE STRATÉGIE")
    print(f"{'='*100}")

    # Construire stratégie
    signals = build_allocation_strategy(
        df,
        fng_zones=[best_params['fng_low'], best_params['fng_high']],
        rainbow_zones=[best_params['rainbow_low'], best_params['rainbow_high']],
        allocation_matrix=[
            [best_params['alloc_fear_low'], best_params['alloc_fear_high']],
            [best_params['alloc_greed_low'], best_params['alloc_greed_high']]
        ]
    )

    result = run_backtest(signals, fees_bps=10.0)

    # Sauvegarder pour visualisation
    signals.to_csv('outputs/best_strategy_backtest.csv', index=False)
    print(f"\n💾 Backtest complet sauvegardé: outputs/best_strategy_backtest.csv")

    return signals, result

if __name__ == "__main__":
    print("Chargement des données...")
    fng = load_fng_alt()
    btc = load_btc_prices()
    df = merge_daily(fng, btc)
    print(f"✅ {len(df)} jours chargés ({df['date'].min().date()} → {df['date'].max().date()})\n")

    # Grid search
    results, best = grid_search_best_allocation(df, top_n=20)

    # Test meilleure stratégie
    signals, result = test_best_strategy(df, best)
