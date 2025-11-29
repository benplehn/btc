#!/usr/bin/env python3
"""
Test EXTRÊME: Réductions minimales de 1-2% seulement

On est à 0.998x, cherchons le sweet spot pour passer au-dessus de 1.0x
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
    d['trade'] = (d['pos'].diff().abs() > 0.5).astype(int)  # Seuil plus bas pour détecter petits changements

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
print("🎯 TEST EXTRÊME: Réductions de 1-2% SEULEMENT")
print("="*100)
print(f"\n📊 Buy & Hold: {bh_equity:.2f}x")
print(f"🎯 OBJECTIF: Trouver configuration > 1.000x\n")

# Grid search ULTRA FIN avec steps de 1%
best_overall = None
best_ratio = 0

print("🔍 Grid Search avec steps de 1%...")
print()

results = []

# Tester toutes les combinaisons possibles avec steps de 1%
for rainbow_threshold in np.arange(0.5, 0.95, 0.05):
    for min_alloc in range(95, 101):  # 95% à 100%
        max_alloc = 100

        bands = [rainbow_threshold]
        allocations = [max_alloc, min_alloc]

        try:
            signals = build_bands_strategy(df, bands, allocations)
            result = run_backtest(signals, fees_bps=10.0)
            metrics = result['metrics']

            ratio = metrics['EquityFinal'] / bh_equity

            results.append({
                'threshold': rainbow_threshold,
                'min_alloc': min_alloc,
                'ratio': ratio,
                'equity': metrics['EquityFinal'],
                'trades': metrics['trades'],
                'avg_alloc': metrics['avg_allocation']
            })

            if ratio > best_ratio:
                best_ratio = ratio
                best_overall = {
                    'bands': bands,
                    'allocations': allocations,
                    'metrics': metrics,
                    'ratio': ratio,
                    'threshold': rainbow_threshold,
                    'min_alloc': min_alloc
                }

                marker = "🎉" if ratio > 1.0 else "🔥"
                print(f"{marker} Rainbow threshold {rainbow_threshold:.2f}, Min alloc {min_alloc}% → Ratio {ratio:.5f}x | "
                      f"Equity {metrics['EquityFinal']:.4f}x | Trades {metrics['trades']}")
        except:
            continue

# Tester 3 bandes avec steps de 1-2%
print(f"\n{'='*100}")
print("🔍 Grid Search 3 BANDES avec steps de 1-2%...")
print(f"{'='*100}\n")

for thresh1 in np.arange(0.5, 0.75, 0.05):
    for thresh2 in np.arange(0.8, 0.95, 0.05):
        for step in [1, 2, 3]:
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

                results.append({
                    'threshold': f"{thresh1:.2f}-{thresh2:.2f}",
                    'min_alloc': min_alloc,
                    'ratio': ratio,
                    'equity': metrics['EquityFinal'],
                    'trades': metrics['trades'],
                    'avg_alloc': metrics['avg_allocation']
                })

                if ratio > best_ratio:
                    best_ratio = ratio
                    best_overall = {
                        'bands': bands,
                        'allocations': allocations,
                        'metrics': metrics,
                        'ratio': ratio,
                        'threshold': f"{thresh1:.2f}-{thresh2:.2f}",
                        'min_alloc': min_alloc
                    }

                    marker = "🎉" if ratio > 1.0 else "🔥"
                    print(f"{marker} Thresholds [{thresh1:.2f}, {thresh2:.2f}], Allocs {allocations} → Ratio {ratio:.5f}x | "
                          f"Trades {metrics['trades']}")
            except:
                continue

print(f"\n{'='*100}")
print(f"🏆 MEILLEURE CONFIGURATION ABSOLUE")
print(f"{'='*100}")

if best_overall:
    print(f"\nBandes: {[f'{b:.2f}' for b in best_overall['bands']]}")
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
        print(f"🎉🎉🎉 VICTOIRE!!! STRATÉGIE BAT LE B&H!!! 🎉🎉🎉")
        print(f"{'='*100}")
        print(f"\n🏆 Ratio final: {best_overall['ratio']:.5f}x")
        print(f"🎯 Amélioration: +{(best_overall['ratio'] - 1.0) * 100:.3f}%")
        print(f"\n✅ Stratégie gagnante:")
        if len(best_overall['bands']) == 1:
            print(f"   • Rainbow < {best_overall['bands'][0]:.2f}: {best_overall['allocations'][0]:.0f}%")
            print(f"   • Rainbow ≥ {best_overall['bands'][0]:.2f}: {best_overall['allocations'][1]:.0f}%")
        else:
            print(f"   • Rainbow < {best_overall['bands'][0]:.2f}: {best_overall['allocations'][0]:.0f}%")
            for i in range(1, len(best_overall['bands'])):
                print(f"   • {best_overall['bands'][i-1]:.2f} ≤ Rainbow < {best_overall['bands'][i]:.2f}: {best_overall['allocations'][i]:.0f}%")
            print(f"   • Rainbow ≥ {best_overall['bands'][-1]:.2f}: {best_overall['allocations'][-1]:.0f}%")
    else:
        print(f"\n⚠️  Meilleure trouvée: {best_overall['ratio']:.5f}x vs B&H")
        print(f"   Différence: {(1.0 - best_overall['ratio']) * 100:.3f}% sous B&H")
        print(f"\n💡 Analyse:")
        print(f"   • Allocation moyenne: {best_overall['metrics']['avg_allocation']:.2f}%")
        print(f"   • Cash moyen: {100 - best_overall['metrics']['avg_allocation']:.2f}%")
        print(f"   • Nombre de trades: {best_overall['metrics']['trades']}")
        print(f"   • Coût des frais: {best_overall['metrics']['trades']} × 10 bps = {best_overall['metrics']['trades'] * 0.001:.2f}x")

        # Test SANS frais
        print(f"\n🔬 Test SANS FRAIS:")
        signals_no_fees = build_bands_strategy(df, best_overall['bands'], best_overall['allocations'])
        result_no_fees = run_backtest(signals_no_fees, fees_bps=0.0)
        ratio_no_fees = result_no_fees['metrics']['EquityFinal'] / bh_equity

        print(f"   Ratio sans frais: {ratio_no_fees:.5f}x")
        print(f"   Impact des frais: {(ratio_no_fees - best_overall['ratio']):.5f}x ({(ratio_no_fees - best_overall['ratio'])/ratio_no_fees * 100:.2f}%)")

        if ratio_no_fees > 1.0:
            print(f"\n   ✅ SANS frais, stratégie BAT B&H!")
            print(f"   ⚠️  Mais frais mangent {(ratio_no_fees - best_overall['ratio']):.5f}x")

# Sauvegarder
df_results = pd.DataFrame(results)
df_results = df_results.sort_values('ratio', ascending=False)
df_results.to_csv('outputs/extreme_minimal_results.csv', index=False)
print(f"\n💾 Tous résultats sauvegardés: outputs/extreme_minimal_results.csv")
print(f"   Top 10 configurations:")
print(df_results.head(10).to_string(index=False))
