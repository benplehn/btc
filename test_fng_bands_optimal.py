#!/usr/bin/env python3
"""
Test FNG BANDS: Trouver les paliers optimaux basés sur Fear & Greed Index

Le FNG drive le marché:
- FNG bas (Fear): Acheter progressivement
- FNG neutre: Hold
- FNG haut (Greed): Réduire légèrement

Approche: Paliers ultra-conservatifs comme la stratégie gagnante Rainbow
"""
import pandas as pd
import numpy as np
from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.backtest import run_backtest

def build_fng_bands_strategy(df, fng_bands, allocations):
    """
    Stratégie à bandes basée sur FNG

    Args:
        fng_bands: Liste de seuils FNG [30, 70]
        allocations: Liste d'allocations [100, 95, 90]

    Exemple:
        fng_bands = [30, 70]
        allocations = [100, 95, 90]

        FNG < 30: 100% (Extreme Fear → ALL-IN)
        30 <= FNG < 70: 95% (Neutre → Quasi full)
        FNG >= 70: 90% (Greed → Légère réduction)
    """
    d = df.copy()

    fngs = d['fng'].values
    allocation = np.zeros(len(d))

    for i in range(len(d)):
        fng = fngs[i]

        # Déterminer la bande FNG
        band_idx = 0
        for j, band_limit in enumerate(fng_bands):
            if fng >= band_limit:
                band_idx = j + 1
            else:
                break

        allocation[i] = allocations[band_idx]

    d['pos'] = allocation
    d['trade'] = (d['pos'].diff().abs() > 0.5).astype(int)

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
print("🎯 TEST: FNG BANDS (Paliers basés sur Fear & Greed)")
print("="*100)
print(f"\n📊 Buy & Hold: {bh_equity:.2f}x")
print(f"🎯 OBJECTIF: Trouver paliers FNG qui battent B&H\n")

# Analyser distribution FNG
print("📊 Distribution FNG:")
print(f"   Min: {df['fng'].min():.0f}")
print(f"   25%: {df['fng'].quantile(0.25):.0f}")
print(f"   50%: {df['fng'].quantile(0.50):.0f}")
print(f"   75%: {df['fng'].quantile(0.75):.0f}")
print(f"   Max: {df['fng'].max():.0f}")
print()

# Test configurations prédéfinies
print("="*100)
print("🔍 TEST: Configurations FNG prédéfinies")
print("="*100)
print()

configs = [
    {
        'name': '2 bandes: 100% → 95% (seuil greed 70)',
        'bands': [70],
        'allocations': [100, 95]
    },
    {
        'name': '2 bandes: 100% → 95% (seuil greed 75)',
        'bands': [75],
        'allocations': [100, 95]
    },
    {
        'name': '2 bandes: 100% → 90% (seuil greed 70)',
        'bands': [70],
        'allocations': [100, 90]
    },
    {
        'name': '3 bandes: 100% → 95% → 90% (30-70)',
        'bands': [30, 70],
        'allocations': [100, 95, 90]
    },
    {
        'name': '3 bandes: 100% → 97% → 94% (40-75)',
        'bands': [40, 75],
        'allocations': [100, 97, 94]
    },
    {
        'name': '3 bandes: 100% → 98% → 96% (50-80)',
        'bands': [50, 80],
        'allocations': [100, 98, 96]
    },
]

results = []

for config in configs:
    signals = build_fng_bands_strategy(df, config['bands'], config['allocations'])
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
    print(f"{marker} {config['name']:<50} → Ratio {ratio:5.3f}x | "
          f"Equity {metrics['EquityFinal']:5.2f}x | Avg {metrics['avg_allocation']:.1f}%")

# Grid search ULTRA FIN sur FNG
print(f"\n{'='*100}")
print(f"🔍 GRID SEARCH: FNG Paliers Optimaux (steps de 1%)")
print(f"{'='*100}\n")

best_overall = None
best_ratio = 0

# 2 bandes: Test tous les seuils FNG de 60 à 90 avec allocations 95-100%
for fng_threshold in range(60, 91):
    for min_alloc in range(95, 101):
        max_alloc = 100

        bands = [fng_threshold]
        allocations = [max_alloc, min_alloc]

        try:
            signals = build_fng_bands_strategy(df, bands, allocations)
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

                marker = "🎉" if ratio > 1.0 else "🔥"
                print(f"{marker} FNG threshold {fng_threshold}, Min alloc {min_alloc}% → Ratio {ratio:.5f}x | "
                      f"Equity {metrics['EquityFinal']:.4f}x | Trades {metrics['trades']}")
        except:
            continue

# 3 bandes: Test avec steps de 1-3%
print(f"\n{'='*100}")
print("🔍 Grid Search 3 BANDES FNG (steps fins)")
print(f"{'='*100}\n")

for thresh1 in range(30, 60, 5):
    for thresh2 in range(65, 86, 5):
        for step in [1, 2, 3, 4]:
            max_alloc = 100
            mid_alloc = 100 - step
            min_alloc = 100 - 2 * step

            bands = [thresh1, thresh2]
            allocations = [max_alloc, mid_alloc, min_alloc]

            try:
                signals = build_fng_bands_strategy(df, bands, allocations)
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

                    marker = "🎉" if ratio > 1.0 else "🔥"
                    print(f"{marker} FNG thresholds [{thresh1}, {thresh2}], Allocs {allocations} → Ratio {ratio:.5f}x | "
                          f"Trades {metrics['trades']}")
            except:
                continue

print(f"\n{'='*100}")
print(f"🏆 MEILLEURE CONFIGURATION FNG TROUVÉE")
print(f"{'='*100}")

if best_overall:
    print(f"\nSeuils FNG: {best_overall['bands']}")
    print(f"Allocations: {[f'{a:.0f}%' for a in best_overall['allocations']]}")
    print(f"\nPerformance:")
    print(f"  Equity: {best_overall['metrics']['EquityFinal']:.4f}x (B&H: {bh_equity:.4f}x)")
    print(f"  Ratio vs B&H: {best_overall['ratio']:.5f}x")
    print(f"  CAGR: {best_overall['metrics']['CAGR']*100:.2f}%")
    print(f"  Max DD: {best_overall['metrics']['MaxDD']*100:.1f}%")
    print(f"  Sharpe: {best_overall['metrics']['Sharpe']:.2f}")
    print(f"  Trades: {best_overall['metrics']['trades']}")
    print(f"  Allocation moyenne: {best_overall['metrics']['avg_allocation']:.2f}%")

    if best_overall['ratio'] >= 1.0:
        print(f"\n{'='*100}")
        print(f"🎉🎉🎉 VICTOIRE FNG!!! STRATÉGIE BAT LE B&H!!! 🎉🎉🎉")
        print(f"{'='*100}")
        print(f"\n🏆 Ratio final: {best_overall['ratio']:.5f}x")
        print(f"🎯 Amélioration: +{(best_overall['ratio'] - 1.0) * 100:.3f}%")
        print(f"\n✅ Stratégie gagnante FNG:")
        if len(best_overall['bands']) == 1:
            print(f"   • FNG < {best_overall['bands'][0]}: {best_overall['allocations'][0]:.0f}%")
            print(f"   • FNG ≥ {best_overall['bands'][0]}: {best_overall['allocations'][1]:.0f}%")
        else:
            print(f"   • FNG < {best_overall['bands'][0]}: {best_overall['allocations'][0]:.0f}%")
            for i in range(1, len(best_overall['bands'])):
                print(f"   • {best_overall['bands'][i-1]} ≤ FNG < {best_overall['bands'][i]}: {best_overall['allocations'][i]:.0f}%")
            print(f"   • FNG ≥ {best_overall['bands'][-1]}: {best_overall['allocations'][-1]:.0f}%")
    else:
        print(f"\n⚠️  Meilleure FNG trouvée: {best_overall['ratio']:.5f}x vs B&H")
        print(f"   Différence: {(1.0 - best_overall['ratio']) * 100:.3f}% sous B&H")

        # Test SANS frais
        print(f"\n🔬 Test SANS FRAIS:")
        signals_no_fees = build_fng_bands_strategy(df, best_overall['bands'], best_overall['allocations'])
        result_no_fees = run_backtest(signals_no_fees, fees_bps=0.0)
        ratio_no_fees = result_no_fees['metrics']['EquityFinal'] / bh_equity

        print(f"   Ratio sans frais: {ratio_no_fees:.5f}x")
        print(f"   Impact des frais: {(ratio_no_fees - best_overall['ratio']):.5f}x")

        if ratio_no_fees > 1.0:
            print(f"\n   ✅ SANS frais, stratégie FNG BAT B&H!")

# Sauvegarder
df_results = pd.DataFrame(results)
df_results.to_csv('outputs/fng_bands_results.csv', index=False)
print(f"\n💾 Résultats sauvegardés: outputs/fng_bands_results.csv")
