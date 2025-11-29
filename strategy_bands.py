#!/usr/bin/env python3
"""
Stratégie à BANDES (paliers) au lieu de seuils linéaires

Logique:
- Diviser Rainbow en BANDES (ex: 0-0.2, 0.2-0.4, 0.4-0.6, etc.)
- Chaque bande = allocation fixe
- Réduction progressive par paliers (jamais 0%)

Exemple avec 5 bandes:
- Bande 1 (0.0-0.2): 100%
- Bande 2 (0.2-0.4): 80%
- Bande 3 (0.4-0.6): 60%
- Bande 4 (0.6-0.8): 40%
- Bande 5 (0.8-1.0): 20%
"""
import pandas as pd
import numpy as np
from itertools import product
from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.strategy import calculate_rainbow_position
from src.fngbt.backtest import run_backtest

def build_bands_strategy(df, bands, allocations):
    """
    Stratégie à bandes avec allocation par paliers

    Args:
        bands: Liste de limites de bandes [0.2, 0.4, 0.6, 0.8]
        allocations: Liste d'allocations par bande [100, 80, 60, 40, 20]
                    (doit avoir len(bands) + 1 éléments)

    Exemple:
        bands = [0.2, 0.4, 0.6, 0.8]
        allocations = [100, 80, 60, 40, 20]

        Rainbow < 0.2: 100%
        0.2 <= Rainbow < 0.4: 80%
        0.4 <= Rainbow < 0.6: 60%
        0.6 <= Rainbow < 0.8: 40%
        Rainbow >= 0.8: 20%
    """
    d = df.copy()
    d = calculate_rainbow_position(d)

    rainbow_pos = d['rainbow_position'].values
    allocation = np.zeros(len(d))

    for i in range(len(d)):
        pos = rainbow_pos[i]

        # Déterminer la bande
        band_idx = 0
        for j, band_limit in enumerate(bands):
            if pos >= band_limit:
                band_idx = j + 1
            else:
                break

        allocation[i] = allocations[band_idx]

    d['pos'] = allocation
    d['trade'] = (d['pos'].diff().abs() > 5).astype(int)

    return d

def test_bands_strategies(df):
    """
    Test différentes configurations de bandes
    """
    print("="*100)
    print("🎯 STRATÉGIE À BANDES (Paliers d'Allocation)")
    print("="*100)

    # Baseline
    bh = df.copy()
    bh['pos'] = 100.0
    bh['trade'] = 0
    bh_result = run_backtest(bh, fees_bps=0.0)
    bh_equity = bh_result['metrics']['EquityFinal']

    print(f"\n📊 Buy & Hold: {bh_equity:.2f}x\n")

    results = []

    # Configuration 1: 5 bandes égales (20% chacune)
    configs = [
        {
            'name': '5 bandes (100→20 par -20%)',
            'bands': [0.2, 0.4, 0.6, 0.8],
            'allocations': [100, 80, 60, 40, 20]
        },
        {
            'name': '5 bandes (100→40 par -15%)',
            'bands': [0.2, 0.4, 0.6, 0.8],
            'allocations': [100, 85, 70, 55, 40]
        },
        {
            'name': '5 bandes (100→50 par -12.5%)',
            'bands': [0.2, 0.4, 0.6, 0.8],
            'allocations': [100, 87, 75, 62, 50]
        },
        {
            'name': '4 bandes (100→40 par -20%)',
            'bands': [0.25, 0.5, 0.75],
            'allocations': [100, 80, 60, 40]
        },
        {
            'name': '4 bandes (100→50 par -16%)',
            'bands': [0.25, 0.5, 0.75],
            'allocations': [100, 84, 67, 50]
        },
        {
            'name': '3 bandes (100→60 par -20%)',
            'bands': [0.33, 0.67],
            'allocations': [100, 80, 60]
        },
        {
            'name': '3 bandes (100→70 par -15%)',
            'bands': [0.33, 0.67],
            'allocations': [100, 85, 70]
        },
        {
            'name': '6 bandes (100→30 par -14%)',
            'bands': [0.17, 0.33, 0.5, 0.67, 0.83],
            'allocations': [100, 86, 72, 58, 44, 30]
        },
    ]

    for config in configs:
        signals = build_bands_strategy(df, config['bands'], config['allocations'])
        result = run_backtest(signals, fees_bps=10.0)
        metrics = result['metrics']

        ratio = metrics['EquityFinal'] / bh_equity

        results.append({
            'name': config['name'],
            'bands': config['bands'],
            'allocations': config['allocations'],
            'equity': metrics['EquityFinal'],
            'ratio': ratio,
            'cagr': metrics['CAGR'],
            'max_dd': metrics['MaxDD'],
            'sharpe': metrics['Sharpe'],
            'trades': metrics['trades'],
            'avg_alloc': metrics['avg_allocation']
        })

        marker = "🎉" if ratio > 1.0 else "  "
        print(f"{marker} {config['name']:<35} → Equity {metrics['EquityFinal']:5.2f}x | "
              f"Ratio {ratio:5.3f}x | CAGR {metrics['CAGR']*100:5.1f}% | "
              f"Avg alloc {metrics['avg_allocation']:.1f}%")

    # Grid search sur bandes optimales
    print(f"\n{'='*100}")
    print(f"🔍 GRID SEARCH: Bandes Optimales")
    print(f"{'='*100}\n")

    best_overall = None
    best_ratio = 0

    # Tester différentes configurations de bandes
    # 5 bandes avec allocations variables
    for alloc_min in [20, 30, 40, 50, 60]:
        for alloc_step in [10, 12, 15, 18, 20]:
            alloc_max = 100

            # Calculer allocations par paliers
            n_bands = 5
            allocations = []
            for i in range(n_bands):
                alloc = alloc_max - i * alloc_step
                allocations.append(max(alloc, alloc_min))

            # Bandes égales
            bands = [0.2, 0.4, 0.6, 0.8]

            try:
                signals = build_bands_strategy(df, bands, allocations)
                result = run_backtest(signals, fees_bps=10.0)
                metrics = result['metrics']

                ratio = metrics['EquityFinal'] / bh_equity

                if ratio > best_ratio:
                    best_ratio = ratio
                    best_overall = {
                        'bands': bands,
                        'allocations': allocations,
                        'metrics': metrics,
                        'ratio': ratio
                    }
            except:
                continue

    print(f"\n{'='*100}")
    print(f"🏆 MEILLEURE CONFIGURATION TROUVÉE")
    print(f"{'='*100}")

    if best_overall:
        print(f"\nBandes: {[f'{b:.2f}' for b in best_overall['bands']]}")
        print(f"Allocations: {[f'{a:.0f}%' for a in best_overall['allocations']]}")
        print(f"\nPerformance:")
        print(f"  Equity: {best_overall['metrics']['EquityFinal']:.2f}x")
        print(f"  Ratio vs B&H: {best_overall['ratio']:.3f}x")
        print(f"  CAGR: {best_overall['metrics']['CAGR']*100:.1f}%")
        print(f"  Max DD: {best_overall['metrics']['MaxDD']*100:.1f}%")
        print(f"  Sharpe: {best_overall['metrics']['Sharpe']:.2f}")
        print(f"  Trades: {best_overall['metrics']['trades']}")
        print(f"  Allocation moyenne: {best_overall['metrics']['avg_allocation']:.1f}%")

        if best_overall['ratio'] > 1.0:
            print(f"\n🎉 VICTOIRE! Cette stratégie BAT le B&H de {best_overall['ratio']:.3f}x!")
        else:
            print(f"\n⚠️  Meilleure trouve sous-performe: {best_overall['ratio']:.3f}x")

    # Tester avec bandes ASYMÉTRIQUES (plus de bandes en bas)
    print(f"\n{'='*100}")
    print(f"🔍 TEST: Bandes ASYMÉTRIQUES (Plus de granularité en bas)")
    print(f"{'='*100}\n")

    asymmetric_configs = [
        {
            'name': 'Asymétrique: 3 bandes basses, 2 hautes',
            'bands': [0.15, 0.3, 0.45, 0.7],
            'allocations': [100, 90, 80, 60, 40]
        },
        {
            'name': 'Asymétrique: Granularité fine en bas',
            'bands': [0.1, 0.2, 0.3, 0.5, 0.8],
            'allocations': [100, 95, 85, 70, 50, 30]
        },
        {
            'name': 'Asymétrique: Hold fort jusqu\'à 0.5',
            'bands': [0.3, 0.5, 0.7, 0.85],
            'allocations': [100, 90, 70, 50, 35]
        },
    ]

    for config in asymmetric_configs:
        signals = build_bands_strategy(df, config['bands'], config['allocations'])
        result = run_backtest(signals, fees_bps=10.0)
        metrics = result['metrics']

        ratio = metrics['EquityFinal'] / bh_equity

        marker = "🎉" if ratio > 1.0 else "  "
        print(f"{marker} {config['name']:<45} → Ratio {ratio:5.3f}x | "
              f"Equity {metrics['EquityFinal']:5.2f}x | Avg {metrics['avg_allocation']:.1f}%")

    # Sauvegarder
    results_df = pd.DataFrame(results)
    results_df.to_csv('outputs/bands_strategy_results.csv', index=False)
    print(f"\n💾 Résultats sauvegardés: outputs/bands_strategy_results.csv")

    return results, best_overall

if __name__ == "__main__":
    print("Chargement données...")
    fng = load_fng_alt()
    btc = load_btc_prices()
    df = merge_daily(fng, btc)
    print(f"✅ {len(df)} jours\n")

    results, best = test_bands_strategies(df)
