#!/usr/bin/env python3
"""
Test ULTRA-CONSERVATIVE bands - rester le plus proche possible de 100%

Hypothèse: Si on ne réduit que très légèrement l'allocation,
on peut battre B&H en capturant presque tout le bull tout en
protégeant légèrement en tops extrêmes
"""
import pandas as pd
import numpy as np
from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.strategy import calculate_rainbow_position
from src.fngbt.backtest import run_backtest

def build_bands_strategy(df, bands, allocations):
    d = df.copy()
    d = calculate_rainbow_position(d)

    rainbow_pos = d['rainbow_position'].values
    allocation = np.zeros(len(d))

    for i in range(len(d)):
        pos = rainbow_pos[i]

        band_idx = 0
        for j, band_limit in enumerate(bands):
            if pos >= band_limit:
                band_idx = j + 1
            else:
                break

        allocation[i] = allocations[band_idx]

    d['pos'] = allocation
    d['trade'] = (d['pos'].diff().abs() > 1).astype(int)

    return d

fng = load_fng_alt()
btc = load_btc_prices()
df = merge_daily(fng, btc)

# Baseline
bh = df.copy()
bh['pos'] = 100.0
bh['trade'] = 0
bh_result = run_backtest(bh, fees_bps=0.0)
bh_equity = bh_result['metrics']['EquityFinal']

print("="*100)
print("🎯 TEST: BANDES ULTRA-CONSERVATRICES (Rester proche de 100%)")
print("="*100)
print(f"\n📊 Buy & Hold: {bh_equity:.2f}x\n")

configs = [
    {
        'name': '2 bandes: 100% → 95% (top extrême seulement)',
        'bands': [0.8],
        'allocations': [100, 95]
    },
    {
        'name': '2 bandes: 100% → 90% (top extrême seulement)',
        'bands': [0.8],
        'allocations': [100, 90]
    },
    {
        'name': '2 bandes: 100% → 85% (top extrême seulement)',
        'bands': [0.8],
        'allocations': [100, 85]
    },
    {
        'name': '3 bandes: 100% → 95% → 90% (progressif doux)',
        'bands': [0.7, 0.85],
        'allocations': [100, 95, 90]
    },
    {
        'name': '3 bandes: 100% → 90% → 80% (progressif moyen)',
        'bands': [0.7, 0.85],
        'allocations': [100, 90, 80]
    },
    {
        'name': '4 bandes: 100 → 95 → 90 → 85 (très progressif)',
        'bands': [0.6, 0.75, 0.9],
        'allocations': [100, 95, 90, 85]
    },
    {
        'name': '4 bandes: 100 → 90 → 85 → 80 (progressif)',
        'bands': [0.6, 0.75, 0.9],
        'allocations': [100, 90, 85, 80]
    },
    {
        'name': '5 bandes: 100→95→90→85→80 (très fin)',
        'bands': [0.5, 0.65, 0.8, 0.9],
        'allocations': [100, 95, 90, 85, 80]
    },
]

results = []

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
    print(f"{marker} {config['name']:<55} → Ratio {ratio:5.3f}x | "
          f"Equity {metrics['EquityFinal']:5.2f}x | Avg {metrics['avg_allocation']:.1f}%")

# Grid search ULTRA FIN
print(f"\n{'='*100}")
print(f"🔍 GRID SEARCH: Variations Ultra-Fines")
print(f"{'='*100}\n")

best_overall = None
best_ratio = 0

# Tester 2 bandes avec différents seuils et allocations minimales
for rainbow_threshold in [0.7, 0.75, 0.8, 0.85, 0.9]:
    for min_alloc in [80, 85, 90, 92, 94, 95, 96, 97, 98, 99]:
        max_alloc = 100

        bands = [rainbow_threshold]
        allocations = [max_alloc, min_alloc]

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

# Tester 3 bandes ultra-fines
for thresh1 in [0.6, 0.65, 0.7]:
    for thresh2 in [0.8, 0.85, 0.9]:
        for step in [2, 3, 4, 5]:
            max_alloc = 100
            mid_alloc = 100 - step
            min_alloc = 100 - 2 * step

            bands = [thresh1, thresh2]
            allocations = [max_alloc, mid_alloc, min_alloc]

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
        print(f"\n🎉🎉🎉 VICTOIRE! Cette stratégie BAT le B&H de {best_overall['ratio']:.3f}x! 🎉🎉🎉")
        print(f"\n🎯 Stratégie gagnante:")
        print(f"   Rainbow < {best_overall['bands'][0]:.2f}: {best_overall['allocations'][0]:.0f}%")
        if len(best_overall['bands']) > 1:
            for i in range(1, len(best_overall['bands'])):
                print(f"   {best_overall['bands'][i-1]:.2f} ≤ Rainbow < {best_overall['bands'][i]:.2f}: {best_overall['allocations'][i]:.0f}%")
            print(f"   Rainbow ≥ {best_overall['bands'][-1]:.2f}: {best_overall['allocations'][-1]:.0f}%")
        else:
            print(f"   Rainbow ≥ {best_overall['bands'][0]:.2f}: {best_overall['allocations'][1]:.0f}%")
    else:
        print(f"\n⚠️  Meilleure trouvée sous-performe: {best_overall['ratio']:.3f}x")
        print(f"\n💡 Allocation moyenne: {best_overall['metrics']['avg_allocation']:.1f}%")
        print(f"   → Les {100 - best_overall['metrics']['avg_allocation']:.1f}% en cash coûtent plus cher que la protection apportée")

# Sauvegarder
df_results = pd.DataFrame(results)
df_results.to_csv('outputs/ultra_conservative_bands.csv', index=False)
print(f"\n💾 Résultats sauvegardés: outputs/ultra_conservative_bands.csv")
