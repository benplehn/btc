#!/usr/bin/env python3
"""
Comparer TOUTES les stratégies avec FEES RÉALISTES

Objectif: Trouver celle qui bat B&H avec le moins de trades possible
"""
import pandas as pd
import numpy as np
from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.strategy import calculate_rainbow_position
from src.fngbt.backtest_realistic_fees import run_backtest_realistic_fees

def rainbow_bands_strategy(df):
    """Rainbow paliers ultra-conservateurs (0.60 threshold, 95% min)"""
    d = df.copy()
    d = calculate_rainbow_position(d)
    d['pos'] = np.where(d['rainbow_position'] < 0.60, 100, 95)
    return d

def fng_rainbow_hybrid(df):
    """FNG+Rainbow hybrid paliers"""
    d = df.copy()
    d = calculate_rainbow_position(d)

    fng_bands = [25, 65]
    rainbow_threshold = 0.60
    allocations = {'fear': [100, 97], 'neutral': [100, 95], 'greed': [99, 97]}

    allocation = np.ones(len(d)) * 100
    for i in range(len(d)):
        fng = d['fng'].iloc[i]
        rainbow = d['rainbow_position'].iloc[i]

        if fng < fng_bands[0]:
            alloc_low, alloc_high = allocations['fear']
        elif fng < fng_bands[1]:
            alloc_low, alloc_high = allocations['neutral']
        else:
            alloc_low, alloc_high = allocations['greed']

        allocation[i] = alloc_low if rainbow < rainbow_threshold else alloc_high

    d['pos'] = allocation
    return d

def fng_velocity_strategy(df):
    """FNG Vélocité seule"""
    d = df.copy()
    d = calculate_rainbow_position(d)

    d['fng_velocity'] = d['fng'].diff(7).abs()
    high_velocity = d['fng_velocity'] > 10

    allocation = np.ones(len(d)) * 100
    allocation[high_velocity] = 96

    rainbow_high = d['rainbow_position'] >= 0.6
    allocation[high_velocity & rainbow_high] = 94

    d['pos'] = allocation
    return d

def fng_rainbow_velocity(df):
    """FNG Vélocité + Rainbow Vélocité"""
    d = df.copy()
    d = calculate_rainbow_position(d)

    d['fng_velocity'] = d['fng'].diff(7).abs()
    d['rainbow_velocity'] = d['rainbow_position'].diff(7).abs()

    fng_volatile = d['fng_velocity'] > 10
    rainbow_volatile = d['rainbow_velocity'] > 0.1

    allocation = np.ones(len(d)) * 100
    either_volatile = fng_volatile | rainbow_volatile
    allocation[either_volatile] = 96

    both_volatile = fng_volatile & rainbow_volatile
    allocation[both_volatile] = 93

    d['pos'] = allocation
    return d

def champion_strategy(df):
    """FNG Vélocité + Rainbow Accélération"""
    d = df.copy()
    d = calculate_rainbow_position(d)

    d['fng_velocity'] = d['fng'].diff(7).abs()
    fng_volatile = d['fng_velocity'] > 8

    d['rainbow_velocity'] = d['rainbow_position'].diff(14)
    d['rainbow_acceleration'] = d['rainbow_velocity'].diff(14).abs()
    rainbow_high_accel = d['rainbow_acceleration'] > 0.02

    allocation = np.ones(len(d)) * 100
    either_signal = fng_volatile | rainbow_high_accel
    allocation[either_signal] = 96

    both_signals = fng_volatile & rainbow_high_accel
    allocation[both_signals] = 92

    d['pos'] = allocation
    return d

# Load data
print("Chargement...")
fng = load_fng_alt()
btc = load_btc_prices()
df = merge_daily(fng, btc)
print(f"✅ {len(df)} jours\n")

print("="*100)
print("📊 COMPARAISON: Toutes les Stratégies avec Fees Réalistes (0.1% par trade)")
print("="*100)
print()

strategies = [
    ("Rainbow Bands (0.60, 95%)", rainbow_bands_strategy),
    ("FNG+Rainbow Hybrid Paliers", fng_rainbow_hybrid),
    ("FNG Vélocité", fng_velocity_strategy),
    ("FNG+Rainbow Vélocité", fng_rainbow_velocity),
    ("Champion (FNG Vel + Rainbow Accel)", champion_strategy),
]

results = []

for name, strategy_func in strategies:
    print(f"Testing {name}...")

    signals = strategy_func(df)
    result = run_backtest_realistic_fees(signals, initial_capital=100.0, fee_rate=0.001)

    metrics = result['metrics']
    bh_equity = result['df']['bh_equity'].iloc[-1]
    ratio = metrics['EquityFinal'] / bh_equity

    results.append({
        'strategy': name,
        'equity': metrics['EquityFinal'],
        'ratio': ratio,
        'improvement_pct': (ratio - 1.0) * 100,
        'cagr': metrics['CAGR'] * 100,
        'sharpe': metrics['Sharpe'],
        'max_dd': metrics['MaxDD'] * 100,
        'trades': metrics['trades'],
        'total_fees': metrics['total_fees_paid'],
        'avg_alloc': metrics['avg_allocation']
    })

print()
print("="*100)
print("📊 RÉSULTATS COMPARATIFS")
print("="*100)
print()

df_results = pd.DataFrame(results)
df_results = df_results.sort_values('ratio', ascending=False)

print(df_results.to_string(index=False))

print()
print("="*100)
print("🏆 MEILLEURE STRATÉGIE")
print("="*100)

best = df_results.iloc[0]

print(f"\n{best['strategy']}")
print(f"   • Ratio vs B&H: {best['ratio']:.5f}x")
print(f"   • Amélioration: +{best['improvement_pct']:.2f}%")
print(f"   • Equity: {best['equity']:.2f}x")
print(f"   • CAGR: {best['cagr']:.2f}%")
print(f"   • Sharpe: {best['sharpe']:.2f}")
print(f"   • Trades: {int(best['trades'])}")
print(f"   • Frais totaux: {best['total_fees']:.2f} EUR")
print(f"   • Allocation moyenne: {best['avg_alloc']:.2f}%")

print()
print("💡 Insight:")
print(f"   Avec fees réalistes, les stratégies avec MOINS de trades performent mieux!")
print(f"   Trades/jour: {best['trades']/len(df):.3f}")
print(f"   Frais en % capital: {best['total_fees']:.2f}%")

# Sauvegarder
df_results.to_csv('outputs/all_strategies_realistic_fees_comparison.csv', index=False)
print()
print("💾 Résultats sauvegardés: outputs/all_strategies_realistic_fees_comparison.csv")
print()
print("✨ Terminé!")
