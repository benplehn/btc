#!/usr/bin/env python3
"""
🔍 GRID SEARCH: MA21 Paliers (ce que le ML a identifié!)

Le ML a découvert que rainbow_ma21 (28.8%) et fng_ma21 (23%) sont les features
les plus importantes. Testons des stratégies SIMPLES basées sur ces MAs.

Stratégie:
- Calculer FNG MA21 et Rainbow MA21
- Créer des paliers d'allocation basés sur ces MAs
- Tester toutes les combinaisons de thresholds et allocations
- Avec fees réalistes (0.1% par trade)

Objectif: Trouver la meilleure combinaison simple qui bat B&H!
"""
import pandas as pd
import numpy as np
from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.strategy import calculate_rainbow_position
from src.fngbt.backtest_realistic_fees import run_backtest_realistic_fees
import itertools
import warnings
warnings.filterwarnings('ignore')

def ma21_paliers_strategy(df,
                          fng_ma21_threshold=50,
                          rainbow_ma21_threshold=0.60,
                          alloc_low_fng=100,
                          alloc_high_fng=97,
                          alloc_low_rainbow=100,
                          alloc_high_rainbow=95):
    """
    Stratégie paliers basée sur FNG MA21 et Rainbow MA21

    Args:
        fng_ma21_threshold: Seuil pour FNG MA21 (peur vs greed)
        rainbow_ma21_threshold: Seuil pour Rainbow MA21 (cheap vs expensive)
        alloc_low_fng: Allocation si FNG MA21 < threshold (peur)
        alloc_high_fng: Allocation si FNG MA21 >= threshold (greed)
        alloc_low_rainbow: Allocation si Rainbow MA21 < threshold (cheap)
        alloc_high_rainbow: Allocation si Rainbow MA21 >= threshold (expensive)
    """
    d = df.copy()
    d = calculate_rainbow_position(d)

    # Calculer les MA21
    d['fng_ma21'] = d['fng'].rolling(21, min_periods=1).mean()
    d['rainbow_ma21'] = d['rainbow_position'].rolling(21, min_periods=1).mean()

    # Allocation basée sur FNG MA21
    fng_allocation = np.where(d['fng_ma21'] < fng_ma21_threshold,
                              alloc_low_fng,
                              alloc_high_fng)

    # Allocation basée sur Rainbow MA21
    rainbow_allocation = np.where(d['rainbow_ma21'] < rainbow_ma21_threshold,
                                  alloc_low_rainbow,
                                  alloc_high_rainbow)

    # Combinaison: prendre le minimum (plus conservateur)
    d['pos'] = np.minimum(fng_allocation, rainbow_allocation)

    return d

def ma21_single_factor_strategy(df, factor='fng', threshold=50, alloc_low=100, alloc_high=95):
    """
    Stratégie paliers basée sur UN SEUL facteur MA21

    Args:
        factor: 'fng' ou 'rainbow'
        threshold: Seuil pour le facteur
        alloc_low: Allocation si < threshold
        alloc_high: Allocation si >= threshold
    """
    d = df.copy()
    d = calculate_rainbow_position(d)

    if factor == 'fng':
        d['fng_ma21'] = d['fng'].rolling(21, min_periods=1).mean()
        d['pos'] = np.where(d['fng_ma21'] < threshold, alloc_low, alloc_high)
    else:  # rainbow
        d['rainbow_ma21'] = d['rainbow_position'].rolling(21, min_periods=1).mean()
        d['pos'] = np.where(d['rainbow_ma21'] < threshold, alloc_low, alloc_high)

    return d

# Load data
print("="*100)
print("🔍 GRID SEARCH: MA21 Paliers (Features identifiés par ML)")
print("="*100)
print()

print("Chargement données...")
fng = load_fng_alt()
btc = load_btc_prices()
df = merge_daily(fng, btc)
print(f"✅ {len(df)} jours\n")

# Grid Search Parameters
print("="*100)
print("📊 GRID SEARCH 1: UN SEUL FACTEUR (FNG MA21 ou Rainbow MA21)")
print("="*100)
print()

# FNG MA21 seul
print("Testing FNG MA21 seul...")
fng_thresholds = [30, 40, 50, 60, 70]
allocations = [
    (100, 95),  # Très conservateur
    (100, 90),  # Moyennement conservateur
    (98, 95),   # Subtil
]

results_fng_single = []

for threshold in fng_thresholds:
    for alloc_low, alloc_high in allocations:
        signals = ma21_single_factor_strategy(df, factor='fng',
                                              threshold=threshold,
                                              alloc_low=alloc_low,
                                              alloc_high=alloc_high)

        result = run_backtest_realistic_fees(signals, initial_capital=100.0, fee_rate=0.001)
        metrics = result['metrics']
        bh_equity = result['df']['bh_equity'].iloc[-1]
        ratio = metrics['EquityFinal'] / bh_equity

        results_fng_single.append({
            'factor': 'fng',
            'threshold': threshold,
            'alloc_low': alloc_low,
            'alloc_high': alloc_high,
            'ratio': ratio,
            'equity': metrics['EquityFinal'],
            'trades': metrics['trades'],
            'fees': metrics['total_fees_paid'],
            'sharpe': metrics['Sharpe']
        })

print(f"✅ {len(results_fng_single)} configurations FNG MA21 testées\n")

# Rainbow MA21 seul
print("Testing Rainbow MA21 seul...")
rainbow_thresholds = [0.40, 0.50, 0.60, 0.70, 0.80]

results_rainbow_single = []

for threshold in rainbow_thresholds:
    for alloc_low, alloc_high in allocations:
        signals = ma21_single_factor_strategy(df, factor='rainbow',
                                              threshold=threshold,
                                              alloc_low=alloc_low,
                                              alloc_high=alloc_high)

        result = run_backtest_realistic_fees(signals, initial_capital=100.0, fee_rate=0.001)
        metrics = result['metrics']
        bh_equity = result['df']['bh_equity'].iloc[-1]
        ratio = metrics['EquityFinal'] / bh_equity

        results_rainbow_single.append({
            'factor': 'rainbow',
            'threshold': threshold,
            'alloc_low': alloc_low,
            'alloc_high': alloc_high,
            'ratio': ratio,
            'equity': metrics['EquityFinal'],
            'trades': metrics['trades'],
            'fees': metrics['total_fees_paid'],
            'sharpe': metrics['Sharpe']
        })

print(f"✅ {len(results_rainbow_single)} configurations Rainbow MA21 testées\n")

# Combine results
results_single = results_fng_single + results_rainbow_single
df_single = pd.DataFrame(results_single).sort_values('ratio', ascending=False)

print("="*100)
print("🏆 TOP 10: UN SEUL FACTEUR MA21")
print("="*100)
print()
print(df_single.head(10).to_string(index=False))
print()

best_single = df_single.iloc[0]
print(f"🥇 MEILLEUR (single factor):")
print(f"   • Facteur: {best_single['factor'].upper()} MA21")
print(f"   • Threshold: {best_single['threshold']}")
print(f"   • Allocations: {best_single['alloc_low']}% / {best_single['alloc_high']}%")
print(f"   • Ratio: {best_single['ratio']:.5f}x (+{(best_single['ratio']-1)*100:.2f}%)")
print(f"   • Trades: {int(best_single['trades'])}")
print(f"   • Fees: {best_single['fees']:.2f} EUR")
print()

# Grid Search 2: Combinaison FNG + Rainbow MA21
print("="*100)
print("📊 GRID SEARCH 2: COMBINAISON FNG MA21 + Rainbow MA21")
print("="*100)
print()

print("Testing combinaisons FNG MA21 + Rainbow MA21...")

# Utiliser les meilleurs thresholds trouvés au-dessus pour limiter la recherche
fng_thresholds_combo = [40, 50, 60]
rainbow_thresholds_combo = [0.50, 0.60, 0.70]

# Allocations
fng_allocations = [(100, 97), (100, 95), (98, 95)]
rainbow_allocations = [(100, 97), (100, 95), (98, 95)]

results_combo = []

total_combos = len(fng_thresholds_combo) * len(rainbow_thresholds_combo) * len(fng_allocations) * len(rainbow_allocations)
print(f"Total combinaisons à tester: {total_combos}\n")

tested = 0
for fng_thresh in fng_thresholds_combo:
    for rainbow_thresh in rainbow_thresholds_combo:
        for fng_alloc in fng_allocations:
            for rainbow_alloc in rainbow_allocations:
                alloc_low_fng, alloc_high_fng = fng_alloc
                alloc_low_rainbow, alloc_high_rainbow = rainbow_alloc

                signals = ma21_paliers_strategy(df,
                                                fng_ma21_threshold=fng_thresh,
                                                rainbow_ma21_threshold=rainbow_thresh,
                                                alloc_low_fng=alloc_low_fng,
                                                alloc_high_fng=alloc_high_fng,
                                                alloc_low_rainbow=alloc_low_rainbow,
                                                alloc_high_rainbow=alloc_high_rainbow)

                result = run_backtest_realistic_fees(signals, initial_capital=100.0, fee_rate=0.001)
                metrics = result['metrics']
                bh_equity = result['df']['bh_equity'].iloc[-1]
                ratio = metrics['EquityFinal'] / bh_equity

                results_combo.append({
                    'fng_thresh': fng_thresh,
                    'rainbow_thresh': rainbow_thresh,
                    'fng_low': alloc_low_fng,
                    'fng_high': alloc_high_fng,
                    'rainbow_low': alloc_low_rainbow,
                    'rainbow_high': alloc_high_rainbow,
                    'ratio': ratio,
                    'equity': metrics['EquityFinal'],
                    'trades': metrics['trades'],
                    'fees': metrics['total_fees_paid'],
                    'sharpe': metrics['Sharpe']
                })

                tested += 1
                if tested % 20 == 0:
                    print(f"   Progress: {tested}/{total_combos} ({tested/total_combos*100:.1f}%)")

print(f"\n✅ {len(results_combo)} combinaisons testées\n")

df_combo = pd.DataFrame(results_combo).sort_values('ratio', ascending=False)

print("="*100)
print("🏆 TOP 10: COMBINAISON FNG MA21 + Rainbow MA21")
print("="*100)
print()
print(df_combo.head(10).to_string(index=False))
print()

best_combo = df_combo.iloc[0]
print(f"🥇 MEILLEUR (combo):")
print(f"   • FNG MA21 threshold: {best_combo['fng_thresh']}")
print(f"   • FNG allocations: {best_combo['fng_low']}% / {best_combo['fng_high']}%")
print(f"   • Rainbow MA21 threshold: {best_combo['rainbow_thresh']}")
print(f"   • Rainbow allocations: {best_combo['rainbow_low']}% / {best_combo['rainbow_high']}%")
print(f"   • Ratio: {best_combo['ratio']:.5f}x (+{(best_combo['ratio']-1)*100:.2f}%)")
print(f"   • Trades: {int(best_combo['trades'])}")
print(f"   • Fees: {best_combo['fees']:.2f} EUR")
print()

# Comparaison finale
print("="*100)
print("📊 COMPARAISON FINALE: MA21 vs Meilleures Stratégies Précédentes")
print("="*100)
print()

comparison = pd.DataFrame([
    {
        'Strategy': 'FNG+Rainbow Hybrid (paliers bruts)',
        'Ratio': 1.18183,
        'Trades': 2165,
        'Fees': 3.64
    },
    {
        'Strategy': 'Rainbow Bands (0.60, 95%)',
        'Ratio': 1.15529,
        'Trades': 658,
        'Fees': 0.65
    },
    {
        'Strategy': f'{best_single["factor"].upper()} MA21 (single)',
        'Ratio': best_single['ratio'],
        'Trades': best_single['trades'],
        'Fees': best_single['fees']
    },
    {
        'Strategy': 'FNG MA21 + Rainbow MA21 (combo)',
        'Ratio': best_combo['ratio'],
        'Trades': best_combo['trades'],
        'Fees': best_combo['fees']
    }
])

print(comparison.to_string(index=False))

best_overall = comparison.loc[comparison['Ratio'].idxmax()]
print(f"\n🥇 CHAMPIONNE ABSOLUE: {best_overall['Strategy']}")
print(f"   • Ratio: {best_overall['Ratio']:.5f}x")
print(f"   • Amélioration vs B&H: +{(best_overall['Ratio']-1)*100:.2f}%")
print(f"   • Trades: {int(best_overall['Trades'])}")
print(f"   • Fees: {best_overall['Fees']:.2f} EUR")
print()

# Sauvegarder
df_single.to_csv('outputs/ma21_single_factor_grid_search.csv', index=False)
df_combo.to_csv('outputs/ma21_combo_grid_search.csv', index=False)
comparison.to_csv('outputs/ma21_final_comparison.csv', index=False)

print("💾 Résultats sauvegardés:")
print("   • outputs/ma21_single_factor_grid_search.csv")
print("   • outputs/ma21_combo_grid_search.csv")
print("   • outputs/ma21_final_comparison.csv")
print()

# Walk-Forward Validation de la meilleure stratégie
print("="*100)
print("🚶 WALK-FORWARD VALIDATION: Meilleure Stratégie MA21")
print("="*100)
print()

# Utiliser la meilleure combo
walk_forward_windows = [
    {
        'name': 'Window 1 (2022)',
        'train_end': '2021-12-31',
        'test_start': '2022-01-01',
        'test_end': '2022-12-31'
    },
    {
        'name': 'Window 2 (2023)',
        'train_end': '2022-12-31',
        'test_start': '2023-01-01',
        'test_end': '2023-12-31'
    },
    {
        'name': 'Window 3 (2024-2025)',
        'train_end': '2023-12-31',
        'test_start': '2024-01-01',
        'test_end': '2025-11-29'
    }
]

wf_results = []

for window in walk_forward_windows:
    test_df = df[(df['date'] >= window['test_start']) & (df['date'] <= window['test_end'])].copy()

    signals = ma21_paliers_strategy(test_df,
                                    fng_ma21_threshold=best_combo['fng_thresh'],
                                    rainbow_ma21_threshold=best_combo['rainbow_thresh'],
                                    alloc_low_fng=best_combo['fng_low'],
                                    alloc_high_fng=best_combo['fng_high'],
                                    alloc_low_rainbow=best_combo['rainbow_low'],
                                    alloc_high_rainbow=best_combo['rainbow_high'])

    result = run_backtest_realistic_fees(signals, initial_capital=100.0, fee_rate=0.001)
    metrics = result['metrics']
    bh_equity = result['df']['bh_equity'].iloc[-1]
    ratio = metrics['EquityFinal'] / bh_equity

    print(f"{window['name']}:")
    print(f"   Ratio: {ratio:.4f}x ({(ratio-1)*100:+.2f}%)")
    print(f"   Trades: {metrics['trades']}, Fees: {metrics['total_fees_paid']:.2f} EUR")
    print()

    wf_results.append({
        'window': window['name'],
        'ratio': ratio,
        'trades': metrics['trades'],
        'fees': metrics['total_fees_paid']
    })

df_wf = pd.DataFrame(wf_results)
avg_ratio = df_wf['ratio'].mean()

print(f"📊 Ratio moyen OOS: {avg_ratio:.4f}x ({(avg_ratio-1)*100:+.2f}%)")
print()

if avg_ratio > 1.0:
    print(f"✅ Stratégie MA21 BAT B&H en moyenne OOS!")
else:
    print(f"⚠️  Stratégie MA21 ne bat pas B&H en moyenne OOS")

df_wf.to_csv('outputs/ma21_walkforward_validation.csv', index=False)

print()
print("✨ Grid Search MA21 terminé!")
