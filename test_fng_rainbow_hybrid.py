#!/usr/bin/env python3
"""
Stratégie Hybride FNG + Rainbow:
- FNG = Drive les PALIERS (quand agir)
- Rainbow = Détermine ALLOCATION à chaque palier (combien)

Logique:
1. FNG définit dans quel palier on est (Fear, Neutral, Greed)
2. À l'intérieur de chaque palier FNG, Rainbow module l'allocation

Exemple:
- FNG < 30 (Extreme Fear): Palier "Achat Agressif"
  - Rainbow bas (0-0.5): 100%
  - Rainbow haut (0.5-1.0): 95%

- FNG 30-70 (Neutral): Palier "Hold"
  - Rainbow bas: 100%
  - Rainbow haut: 90%

- FNG > 70 (Greed): Palier "Réduction"
  - Rainbow bas: 95%
  - Rainbow haut: 85%
"""
import pandas as pd
import numpy as np
from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.strategy import calculate_rainbow_position
from src.fngbt.backtest import run_backtest

def build_fng_rainbow_hybrid(df, fng_bands, rainbow_threshold, allocations_per_band):
    """
    Stratégie hybride FNG + Rainbow

    Args:
        fng_bands: Seuils FNG [30, 70]
        rainbow_threshold: Seuil Rainbow pour moduler allocation (ex: 0.6)
        allocations_per_band: Dict avec allocations par palier FNG
            {
                'fear': [100, 95],  # [rainbow_low, rainbow_high]
                'neutral': [100, 90],
                'greed': [95, 85]
            }
    """
    d = df.copy()
    d = calculate_rainbow_position(d)

    fngs = d['fng'].values
    rainbow_values = d['rainbow_position'].values
    allocation = np.zeros(len(d))

    for i in range(len(d)):
        fng = fngs[i]
        rainbow = rainbow_values[i]

        # Déterminer palier FNG
        if fng < fng_bands[0]:
            # Palier FEAR
            alloc_low, alloc_high = allocations_per_band['fear']
        elif fng < fng_bands[1]:
            # Palier NEUTRAL
            alloc_low, alloc_high = allocations_per_band['neutral']
        else:
            # Palier GREED
            alloc_low, alloc_high = allocations_per_band['greed']

        # Rainbow module l'allocation dans ce palier
        if rainbow < rainbow_threshold:
            allocation[i] = alloc_low
        else:
            allocation[i] = alloc_high

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
print("🎯 STRATÉGIE HYBRIDE: FNG (Quand) + Rainbow (Combien)")
print("="*100)
print(f"\n📊 Buy & Hold: {bh_equity:.2f}x")
print(f"🎯 OBJECTIF: FNG drive les paliers, Rainbow module l'allocation\n")

# Analyser distributions
print("📊 Distributions:")
print(f"\nFNG:")
print(f"   25%: {df['fng'].quantile(0.25):.0f}")
print(f"   50%: {df['fng'].quantile(0.50):.0f}")
print(f"   75%: {df['fng'].quantile(0.75):.0f}")

d_temp = calculate_rainbow_position(df.copy())
print(f"\nRainbow:")
print(f"   25%: {d_temp['rainbow_position'].quantile(0.25):.2f}")
print(f"   50%: {d_temp['rainbow_position'].quantile(0.50):.2f}")
print(f"   75%: {d_temp['rainbow_position'].quantile(0.75):.2f}")

# Test configurations prédéfinies
print(f"\n{'='*100}")
print("🔍 TEST: Configurations Hybrides Prédéfinies")
print(f"{'='*100}\n")

configs = [
    {
        'name': 'Conservative: FNG 30-70, Rainbow 0.6',
        'fng_bands': [30, 70],
        'rainbow_threshold': 0.6,
        'allocations': {
            'fear': [100, 100],  # En Fear: toujours 100%
            'neutral': [100, 95],  # En Neutral: 100% si Rainbow bas, 95% si haut
            'greed': [95, 90]  # En Greed: 95% si Rainbow bas, 90% si haut
        }
    },
    {
        'name': 'Ultra-Conservative: FNG 25-75, Rainbow 0.7',
        'fng_bands': [25, 75],
        'rainbow_threshold': 0.7,
        'allocations': {
            'fear': [100, 100],
            'neutral': [100, 97],
            'greed': [97, 95]
        }
    },
    {
        'name': 'Aggressive: FNG 35-65, Rainbow 0.5',
        'fng_bands': [35, 65],
        'rainbow_threshold': 0.5,
        'allocations': {
            'fear': [100, 95],
            'neutral': [100, 90],
            'greed': [90, 80]
        }
    },
]

results = []

for config in configs:
    signals = build_fng_rainbow_hybrid(
        df,
        config['fng_bands'],
        config['rainbow_threshold'],
        config['allocations']
    )
    result = run_backtest(signals, fees_bps=10.0)
    metrics = result['metrics']

    ratio = metrics['EquityFinal'] / bh_equity

    results.append({
        'name': config['name'],
        'fng_bands': config['fng_bands'],
        'rainbow_threshold': config['rainbow_threshold'],
        'allocations': config['allocations'],
        'equity': metrics['EquityFinal'],
        'ratio': ratio,
        'trades': metrics['trades'],
        'avg_alloc': metrics['avg_allocation']
    })

    marker = "🎉" if ratio > 1.0 else "  "
    print(f"{marker} {config['name']:<50} → Ratio {ratio:5.3f}x | "
          f"Trades {metrics['trades']:3d} | Avg {metrics['avg_allocation']:.1f}%")

# Grid search optimal
print(f"\n{'='*100}")
print(f"🔍 GRID SEARCH: Paramètres Optimaux FNG+Rainbow")
print(f"{'='*100}\n")

best_overall = None
best_ratio = 0

# Tester différentes combinaisons
for fng_low in range(25, 41, 5):
    for fng_high in range(65, 81, 5):
        for rainbow_thresh in [0.5, 0.55, 0.6, 0.65, 0.7]:
            # Tester différentes allocations ultra-conservatrices
            for fear_alloc in [[100, 100], [100, 98], [100, 97]]:
                for neutral_alloc in [[100, 95], [100, 96], [100, 97], [100, 98]]:
                    for greed_alloc in [[95, 90], [96, 92], [97, 94], [98, 95], [99, 97]]:

                        allocations = {
                            'fear': fear_alloc,
                            'neutral': neutral_alloc,
                            'greed': greed_alloc
                        }

                        try:
                            signals = build_fng_rainbow_hybrid(
                                df,
                                [fng_low, fng_high],
                                rainbow_thresh,
                                allocations
                            )
                            result = run_backtest(signals, fees_bps=10.0)
                            metrics = result['metrics']

                            ratio = metrics['EquityFinal'] / bh_equity

                            if ratio > best_ratio:
                                best_ratio = ratio
                                best_overall = {
                                    'fng_bands': [fng_low, fng_high],
                                    'rainbow_threshold': rainbow_thresh,
                                    'allocations': allocations,
                                    'metrics': metrics,
                                    'ratio': ratio
                                }

                                marker = "🎉" if ratio > 1.0 else "🔥"
                                print(f"{marker} FNG [{fng_low},{fng_high}], Rainbow {rainbow_thresh:.2f}, "
                                      f"Allocs {allocations} → Ratio {ratio:.5f}x | Trades {metrics['trades']}")
                        except:
                            continue

print(f"\n{'='*100}")
print(f"🏆 MEILLEURE CONFIGURATION HYBRIDE TROUVÉE")
print(f"{'='*100}")

if best_overall:
    print(f"\nPaliers FNG: {best_overall['fng_bands']}")
    print(f"Seuil Rainbow: {best_overall['rainbow_threshold']:.2f}")
    print(f"\nAllocations par palier:")
    print(f"  • FNG < {best_overall['fng_bands'][0]} (FEAR):")
    print(f"      - Rainbow < {best_overall['rainbow_threshold']:.2f}: {best_overall['allocations']['fear'][0]:.0f}%")
    print(f"      - Rainbow ≥ {best_overall['rainbow_threshold']:.2f}: {best_overall['allocations']['fear'][1]:.0f}%")
    print(f"  • {best_overall['fng_bands'][0]} ≤ FNG < {best_overall['fng_bands'][1]} (NEUTRAL):")
    print(f"      - Rainbow < {best_overall['rainbow_threshold']:.2f}: {best_overall['allocations']['neutral'][0]:.0f}%")
    print(f"      - Rainbow ≥ {best_overall['rainbow_threshold']:.2f}: {best_overall['allocations']['neutral'][1]:.0f}%")
    print(f"  • FNG ≥ {best_overall['fng_bands'][1]} (GREED):")
    print(f"      - Rainbow < {best_overall['rainbow_threshold']:.2f}: {best_overall['allocations']['greed'][0]:.0f}%")
    print(f"      - Rainbow ≥ {best_overall['rainbow_threshold']:.2f}: {best_overall['allocations']['greed'][1]:.0f}%")

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
        print(f"🎉🎉🎉 VICTOIRE HYBRIDE!!! STRATÉGIE BAT LE B&H!!! 🎉🎉🎉")
        print(f"{'='*100}")
        print(f"\n🏆 Ratio final: {best_overall['ratio']:.5f}x")
        print(f"🎯 Amélioration: +{(best_overall['ratio'] - 1.0) * 100:.3f}%")
    else:
        print(f"\n⚠️  Meilleure hybride: {best_overall['ratio']:.5f}x vs B&H")

        # Test SANS frais
        print(f"\n🔬 Test SANS FRAIS:")
        signals_no_fees = build_fng_rainbow_hybrid(
            df,
            best_overall['fng_bands'],
            best_overall['rainbow_threshold'],
            best_overall['allocations']
        )
        result_no_fees = run_backtest(signals_no_fees, fees_bps=0.0)
        ratio_no_fees = result_no_fees['metrics']['EquityFinal'] / bh_equity

        print(f"   Ratio sans frais: {ratio_no_fees:.5f}x")
        print(f"   Impact des frais: {(ratio_no_fees - best_overall['ratio']):.5f}x")

        if ratio_no_fees > 1.0:
            print(f"\n   ✅ SANS frais, stratégie hybride BAT B&H!")

# Sauvegarder
df_results = pd.DataFrame(results)
df_results.to_csv('outputs/fng_rainbow_hybrid_results.csv', index=False)
print(f"\n💾 Résultats sauvegardés: outputs/fng_rainbow_hybrid_results.csv")
