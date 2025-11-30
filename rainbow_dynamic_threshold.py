#!/usr/bin/env python3
"""
🌈 RAINBOW DYNAMIC THRESHOLD: S'adapter à la maturation du Bitcoin

Problème identifié:
- Rainbow Cheap Only (threshold fixe 0.25) = 105x full dataset, mais 1.84x OOS
- Cause: Bitcoin mature → rainbow ne descend plus aussi bas
  - 2018-2019: min = 0.087
  - 2024-2025: min = 0.303 → threshold 0.25 jamais atteint!

Solution:
- Threshold DYNAMIQUE basé sur percentile mobile
- Acheter quand rainbow < percentile X% des N derniers jours
- S'adapte automatiquement à la volatilité du marché

Objectif: Battre 18x vs B&H avec validation OOS rigoureuse
"""
import pandas as pd
import numpy as np
from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.strategy import calculate_rainbow_position
from src.fngbt.backtest_realistic_fees import run_backtest_realistic_fees
import warnings
warnings.filterwarnings('ignore')

print("="*100)
print("🌈 RAINBOW DYNAMIC THRESHOLD: Adaptation à la maturation du Bitcoin")
print("="*100)
print()

# Load data
print("Chargement données...")
fng = load_fng_alt()
btc = load_btc_prices()
df = merge_daily(fng, btc)
df = calculate_rainbow_position(df)
print(f"✅ {len(df)} jours\n")

bh_ratio = df['close'].iloc[-1] / df['close'].iloc[0]
print(f"📊 Buy & Hold: {bh_ratio:.2f}x")
print(f"🎯 Objectif: 18x vs B&H\n")

# ============================================================================
# ANALYSE: Évolution du Rainbow dans le temps
# ============================================================================

print("="*100)
print("📊 ANALYSE: Le Rainbow change-t-il avec le temps?")
print("="*100)
print()

print("Rainbow par année:")
print("-" * 80)
print("Année  | Min   | P10   | P25   | Médiane | P75   | P90   | Max")
print("-" * 80)

for year in range(2018, 2026):
    df_year = df[df['date'].dt.year == year]
    if len(df_year) > 0:
        rainbow = df_year['rainbow_position']
        print(f"{year}   | {rainbow.min():.3f} | {rainbow.quantile(0.10):.3f} | "
              f"{rainbow.quantile(0.25):.3f} | {rainbow.median():.3f} | "
              f"{rainbow.quantile(0.75):.3f} | {rainbow.quantile(0.90):.3f} | {rainbow.max():.3f}")

print()
print("💡 Observation: Le rainbow MINIMUM augmente avec le temps!")
print("   → Threshold fixe devient obsolète")
print()

# ============================================================================
# STRATÉGIE 1: Percentile Mobile (Rolling Percentile)
# ============================================================================

print("="*100)
print("🎯 STRATÉGIE 1: Percentile Mobile (Rolling)")
print("="*100)
print()

def rainbow_rolling_percentile(df, percentile=25, window=365):
    """
    Acheter quand rainbow < percentile X% des N derniers jours

    Exemple: percentile=25, window=365
    → Acheter si rainbow actuel < 25ème percentile des 365 derniers jours
    → S'adapte automatiquement à la volatilité
    """
    d = df.copy()

    # Calculer percentile mobile
    d['rainbow_p25_rolling'] = d['rainbow_position'].rolling(window, min_periods=30).quantile(percentile/100)

    # Allocation: 100% BTC si rainbow < threshold mobile, sinon 0% cash
    d['pos'] = np.where(d['rainbow_position'] < d['rainbow_p25_rolling'], 100, 0)

    return d

print("Test percentiles mobiles (window = 365 jours)...\n")

results_rolling = []

for percentile in [10, 15, 20, 25, 30, 35, 40]:
    signals = rainbow_rolling_percentile(df, percentile=percentile, window=365)
    result = run_backtest_realistic_fees(signals, initial_capital=100.0, fee_rate=0.001)
    metrics = result['metrics']
    ratio_bh = metrics['EquityFinal'] / (bh_ratio * 100)

    # Calculer temps en BTC
    time_in_btc = (signals['pos'] == 100).sum() / len(signals) * 100

    results_rolling.append({
        'percentile': percentile,
        'window': 365,
        'equity': metrics['EquityFinal'],
        'ratio_bh': ratio_bh,
        'trades': metrics['trades'],
        'fees': metrics['total_fees_paid'],
        'time_in_btc': time_in_btc
    })

df_rolling = pd.DataFrame(results_rolling).sort_values('ratio_bh', ascending=False)

print("Résultats Percentile Mobile (365 jours):")
print(df_rolling.to_string(index=False))
print()

best_rolling = df_rolling.iloc[0]
print(f"🥇 Meilleur: P{best_rolling['percentile']:.0f} (365j)")
print(f"   Equity: {best_rolling['equity']:.2f} EUR ({best_rolling['ratio_bh']:.2f}x vs B&H)")
print(f"   Trades: {int(best_rolling['trades'])}, Fees: {best_rolling['fees']:.2f} EUR")
print(f"   Temps en BTC: {best_rolling['time_in_btc']:.1f}%")
print()

# ============================================================================
# STRATÉGIE 2: Threshold Linéaire Croissant
# ============================================================================

print("="*100)
print("🎯 STRATÉGIE 2: Threshold Linéaire Croissant")
print("="*100)
print()

def rainbow_linear_threshold(df, start_threshold=0.20, end_threshold=0.40,
                             start_date='2018-01-01', end_date='2025-12-31'):
    """
    Threshold qui croît linéairement dans le temps

    Exemple: 0.20 en 2018 → 0.40 en 2025
    """
    d = df.copy()

    # Calculer threshold pour chaque date
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)
    total_days = (end_ts - start_ts).days

    thresholds = []
    for date in d['date']:
        days_elapsed = (date - start_ts).days
        progress = min(max(days_elapsed / total_days, 0), 1)
        threshold = start_threshold + (end_threshold - start_threshold) * progress
        thresholds.append(threshold)

    d['dynamic_threshold'] = thresholds

    # Allocation
    d['pos'] = np.where(d['rainbow_position'] < d['dynamic_threshold'], 100, 0)

    return d

print("Test thresholds linéaires croissants...\n")

results_linear = []

configs = [
    (0.15, 0.30),
    (0.15, 0.35),
    (0.20, 0.35),
    (0.20, 0.40),
    (0.25, 0.40),
    (0.25, 0.45),
]

for start_thresh, end_thresh in configs:
    signals = rainbow_linear_threshold(df, start_threshold=start_thresh, end_threshold=end_thresh)
    result = run_backtest_realistic_fees(signals, initial_capital=100.0, fee_rate=0.001)
    metrics = result['metrics']
    ratio_bh = metrics['EquityFinal'] / (bh_ratio * 100)

    time_in_btc = (signals['pos'] == 100).sum() / len(signals) * 100

    results_linear.append({
        'start_thresh': start_thresh,
        'end_thresh': end_thresh,
        'equity': metrics['EquityFinal'],
        'ratio_bh': ratio_bh,
        'trades': metrics['trades'],
        'fees': metrics['total_fees_paid'],
        'time_in_btc': time_in_btc
    })

df_linear = pd.DataFrame(results_linear).sort_values('ratio_bh', ascending=False)

print("Résultats Threshold Linéaire:")
print(df_linear.to_string(index=False))
print()

best_linear = df_linear.iloc[0]
print(f"🥇 Meilleur: {best_linear['start_thresh']:.2f} → {best_linear['end_thresh']:.2f}")
print(f"   Equity: {best_linear['equity']:.2f} EUR ({best_linear['ratio_bh']:.2f}x vs B&H)")
print(f"   Trades: {int(best_linear['trades'])}, Fees: {best_linear['fees']:.2f} EUR")
print(f"   Temps en BTC: {best_linear['time_in_btc']:.1f}%")
print()

# ============================================================================
# STRATÉGIE 3: Threshold basé sur Cycle Bitcoin (Halving)
# ============================================================================

print("="*100)
print("🎯 STRATÉGIE 3: Threshold basé sur Cycle Halving")
print("="*100)
print()

def rainbow_halving_cycle(df, base_threshold=0.25, cycle_adjustment=0.05):
    """
    Threshold qui augmente à chaque cycle de halving

    Halvings Bitcoin:
    - 2016-07-09
    - 2020-05-11
    - 2024-04-20

    Threshold = base + (cycles_since_first * adjustment)
    """
    d = df.copy()

    halving_dates = [
        pd.Timestamp('2016-07-09'),
        pd.Timestamp('2020-05-11'),
        pd.Timestamp('2024-04-20'),
    ]

    thresholds = []
    for date in d['date']:
        # Compter combien de halvings ont eu lieu
        cycles_passed = sum(1 for h_date in halving_dates if date >= h_date)
        threshold = base_threshold + (cycles_passed * cycle_adjustment)
        thresholds.append(threshold)

    d['dynamic_threshold'] = thresholds
    d['pos'] = np.where(d['rainbow_position'] < d['dynamic_threshold'], 100, 0)

    return d

print("Test thresholds basés sur cycles halving...\n")

results_halving = []

configs_halving = [
    (0.20, 0.05),
    (0.20, 0.06),
    (0.22, 0.05),
    (0.22, 0.06),
    (0.25, 0.04),
    (0.25, 0.05),
]

for base, adjustment in configs_halving:
    signals = rainbow_halving_cycle(df, base_threshold=base, cycle_adjustment=adjustment)
    result = run_backtest_realistic_fees(signals, initial_capital=100.0, fee_rate=0.001)
    metrics = result['metrics']
    ratio_bh = metrics['EquityFinal'] / (bh_ratio * 100)

    time_in_btc = (signals['pos'] == 100).sum() / len(signals) * 100

    results_halving.append({
        'base': base,
        'adjustment': adjustment,
        'equity': metrics['EquityFinal'],
        'ratio_bh': ratio_bh,
        'trades': metrics['trades'],
        'fees': metrics['total_fees_paid'],
        'time_in_btc': time_in_btc
    })

df_halving = pd.DataFrame(results_halving).sort_values('ratio_bh', ascending=False)

print("Résultats Threshold Halving Cycle:")
print(df_halving.to_string(index=False))
print()

best_halving = df_halving.iloc[0]
print(f"🥇 Meilleur: base={best_halving['base']:.2f}, adj=+{best_halving['adjustment']:.2f}/cycle")
print(f"   Equity: {best_halving['equity']:.2f} EUR ({best_halving['ratio_bh']:.2f}x vs B&H)")
print(f"   Trades: {int(best_halving['trades'])}, Fees: {best_halving['fees']:.2f} EUR")
print(f"   Temps en BTC: {best_halving['time_in_btc']:.1f}%")
print()

# ============================================================================
# WALK-FORWARD VALIDATION: Meilleure Stratégie Dynamique
# ============================================================================

print("="*100)
print("🚶 WALK-FORWARD VALIDATION: Stratégie Dynamique")
print("="*100)
print()

# Choisir la meilleure stratégie
best_overall = max(
    [('Rolling Percentile', best_rolling['ratio_bh'], best_rolling['percentile'], None),
     ('Linear Threshold', best_linear['ratio_bh'], best_linear['start_thresh'], best_linear['end_thresh']),
     ('Halving Cycle', best_halving['ratio_bh'], best_halving['base'], best_halving['adjustment'])],
    key=lambda x: x[1]
)

print(f"Meilleure stratégie dynamique: {best_overall[0]} ({best_overall[1]:.2f}x)\n")

# Walk-forward windows
walk_forward_windows = [
    {
        'name': 'Train 2018-2021 → Test 2022',
        'train_start': '2018-01-01',
        'train_end': '2021-12-31',
        'test_start': '2022-01-01',
        'test_end': '2022-12-31'
    },
    {
        'name': 'Train 2018-2022 → Test 2023',
        'train_start': '2018-01-01',
        'train_end': '2022-12-31',
        'test_start': '2023-01-01',
        'test_end': '2023-12-31'
    },
    {
        'name': 'Train 2018-2023 → Test 2024-2025',
        'train_start': '2018-01-01',
        'train_end': '2023-12-31',
        'test_start': '2024-01-01',
        'test_end': '2025-11-29'
    }
]

wf_results = []

print(f"Validation de la stratégie: {best_overall[0]}\n")

for window in walk_forward_windows:
    print(f"{'='*100}")
    print(f"WINDOW: {window['name']}")
    print(f"{'='*100}\n")

    # Split data
    train = df[(df['date'] >= window['train_start']) & (df['date'] <= window['train_end'])].copy()
    test = df[(df['date'] >= window['test_start']) & (df['date'] <= window['test_end'])].copy()

    print(f"Train: {len(train)} jours, Test: {len(test)} jours")

    # Grid search sur TRAIN
    if best_overall[0] == 'Rolling Percentile':
        # Test différents percentiles
        train_results = []
        for p in [10, 15, 20, 25, 30, 35, 40]:
            signals = rainbow_rolling_percentile(train, percentile=p, window=365)
            result = run_backtest_realistic_fees(signals, initial_capital=100.0, fee_rate=0.001)
            bh_train = result['df']['bh_equity'].iloc[-1]
            train_results.append({
                'param': p,
                'equity': result['metrics']['EquityFinal'],
                'ratio': result['metrics']['EquityFinal'] / bh_train
            })

        best_train = max(train_results, key=lambda x: x['equity'])
        signals_test = rainbow_rolling_percentile(test, percentile=best_train['param'], window=365)

    elif best_overall[0] == 'Linear Threshold':
        # Test différentes configs linéaires
        train_results = []
        for start, end in [(0.15, 0.30), (0.15, 0.35), (0.20, 0.35), (0.20, 0.40), (0.25, 0.40)]:
            signals = rainbow_linear_threshold(train, start_threshold=start, end_threshold=end)
            result = run_backtest_realistic_fees(signals, initial_capital=100.0, fee_rate=0.001)
            bh_train = result['df']['bh_equity'].iloc[-1]
            train_results.append({
                'param': (start, end),
                'equity': result['metrics']['EquityFinal'],
                'ratio': result['metrics']['EquityFinal'] / bh_train
            })

        best_train = max(train_results, key=lambda x: x['equity'])
        signals_test = rainbow_linear_threshold(test, start_threshold=best_train['param'][0],
                                               end_threshold=best_train['param'][1])

    else:  # Halving Cycle
        # Test différentes configs halving
        train_results = []
        for base, adj in [(0.20, 0.05), (0.22, 0.05), (0.25, 0.04), (0.25, 0.05)]:
            signals = rainbow_halving_cycle(train, base_threshold=base, cycle_adjustment=adj)
            result = run_backtest_realistic_fees(signals, initial_capital=100.0, fee_rate=0.001)
            bh_train = result['df']['bh_equity'].iloc[-1]
            train_results.append({
                'param': (base, adj),
                'equity': result['metrics']['EquityFinal'],
                'ratio': result['metrics']['EquityFinal'] / bh_train
            })

        best_train = max(train_results, key=lambda x: x['equity'])
        signals_test = rainbow_halving_cycle(test, base_threshold=best_train['param'][0],
                                            cycle_adjustment=best_train['param'][1])

    print(f"\n🏆 Meilleur paramètre sur TRAIN: {best_train['param']}")
    print(f"   Train Equity: {best_train['equity']:.2f} EUR ({best_train['ratio']:.2f}x vs B&H)")

    # Test OOS
    result_test = run_backtest_realistic_fees(signals_test, initial_capital=100.0, fee_rate=0.001)
    metrics_test = result_test['metrics']
    bh_test = result_test['df']['bh_equity'].iloc[-1]
    ratio_test = metrics_test['EquityFinal'] / bh_test

    print(f"\n📊 Performance sur TEST (OOS):")
    print(f"   Equity: {metrics_test['EquityFinal']:.2f} EUR")
    print(f"   Ratio vs B&H: {ratio_test:.2f}x ({(ratio_test-1)*100:+.1f}%)")
    print(f"   Trades: {metrics_test['trades']}")
    print(f"   Fees: {metrics_test['total_fees_paid']:.2f} EUR")

    wf_results.append({
        'window': window['name'],
        'best_param': str(best_train['param']),
        'train_ratio': best_train['ratio'],
        'test_equity': metrics_test['EquityFinal'],
        'test_ratio': ratio_test,
        'test_trades': metrics_test['trades']
    })

# Summary
print("\n" + "="*100)
print("📊 RÉSUMÉ WALK-FORWARD VALIDATION")
print("="*100)
print()

df_wf = pd.DataFrame(wf_results)
print(df_wf[['window', 'best_param', 'test_equity', 'test_ratio', 'test_trades']].to_string(index=False))
print()

avg_test_ratio = df_wf['test_ratio'].mean()
print(f"📈 Ratio moyen OOS: {avg_test_ratio:.2f}x vs B&H")
print(f"🎯 vs Objectif 18x: {'✅ ATTEINT!' if avg_test_ratio >= 18 else f'❌ Manque {18 - avg_test_ratio:.1f}x'}")
print()

# ============================================================================
# COMPARAISON FINALE
# ============================================================================

print("="*100)
print("⚖️  COMPARAISON: Fixe vs Dynamique")
print("="*100)
print()

comparison = pd.DataFrame([
    {
        'Stratégie': 'Buy & Hold',
        'Equity (EUR)': bh_ratio * 100,
        'Ratio vs B&H': 1.0,
        'OOS Validé': 'N/A',
        'Atteint 18x': '❌'
    },
    {
        'Stratégie': 'Rainbow Cheap Only (fixe 0.25)',
        'Equity (EUR)': 64775,
        'Ratio vs B&H': 105.45,
        'OOS Validé': 'Non (1.84x OOS)',
        'Atteint 18x': '❌ (overfitting)'
    },
    {
        'Stratégie': f'Rainbow Dynamic ({best_overall[0]})',
        'Equity (EUR)': df_wf['test_equity'].mean(),
        'Ratio vs B&H': avg_test_ratio,
        'OOS Validé': 'Oui ✅',
        'Atteint 18x': '✅' if avg_test_ratio >= 18 else '❌'
    },
    {
        'Stratégie': 'ML avec S&P 500 (OOS validé)',
        'Equity (EUR)': 1.284 * bh_ratio * 100,
        'Ratio vs B&H': 1.284,
        'OOS Validé': 'Oui ✅',
        'Atteint 18x': '❌'
    }
]).sort_values('Ratio vs B&H', ascending=False)

print(comparison.to_string(index=False))
print()

# Sauvegarder
df_rolling.to_csv('outputs/rainbow_dynamic_rolling_results.csv', index=False)
df_linear.to_csv('outputs/rainbow_dynamic_linear_results.csv', index=False)
df_halving.to_csv('outputs/rainbow_dynamic_halving_results.csv', index=False)
df_wf.to_csv('outputs/rainbow_dynamic_walkforward.csv', index=False)
comparison.to_csv('outputs/rainbow_dynamic_comparison.csv', index=False)

print("💾 Résultats sauvegardés:")
print("   • outputs/rainbow_dynamic_rolling_results.csv")
print("   • outputs/rainbow_dynamic_linear_results.csv")
print("   • outputs/rainbow_dynamic_halving_results.csv")
print("   • outputs/rainbow_dynamic_walkforward.csv")
print("   • outputs/rainbow_dynamic_comparison.csv")
print()

# ============================================================================
# CONCLUSION
# ============================================================================

print("="*100)
print("🎯 CONCLUSION")
print("="*100)
print()

winner = comparison[comparison['OOS Validé'] == 'Oui ✅'].sort_values('Ratio vs B&H', ascending=False).iloc[0]

if avg_test_ratio >= 18:
    print("🎉🎉🎉 OBJECTIF 18x ATTEINT EN OOS!")
    print(f"   Stratégie: {best_overall[0]}")
    print(f"   Ratio moyen OOS: {avg_test_ratio:.1f}x vs B&H")
    print()
    print("✅ Cette stratégie DYNAMIQUE est validée et prête pour déploiement!")
else:
    print(f"🏆 CHAMPIONNE (validée OOS): {winner['Stratégie']}")
    print(f"   Equity: {winner['Equity (EUR)']:.2f} EUR")
    print(f"   Ratio vs B&H: {winner['Ratio vs B&H']:.2f}x")
    print()

    if avg_test_ratio > 1.84:
        improvement = ((avg_test_ratio - 1.84) / 1.84) * 100
        print(f"✅ Stratégie dynamique améliore le threshold fixe de +{improvement:.1f}%!")
        print(f"   Fixe (0.25): 1.84x OOS")
        print(f"   Dynamique ({best_overall[0]}): {avg_test_ratio:.2f}x OOS")
    else:
        print(f"⚠️  Stratégie dynamique: {avg_test_ratio:.2f}x OOS")
        print(f"   Pas d'amélioration vs threshold fixe (1.84x)")

print("\n✨ Validation stratégie dynamique terminée!")
