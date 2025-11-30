#!/usr/bin/env python3
"""
🌈 STRATÉGIE PURE RAINBOW ZONES: Acheter au minimum, Vendre au maximum

Principe ultra-simple:
- ACHETER (100% BTC) quand Bitcoin entre dans la zone ROUGE (cheap, rainbow < 0.2-0.3)
- VENDRE (réduire à 70-80%) quand Bitcoin entre dans la zone BLEUE (expensive, rainbow > 0.8-0.9)
- TENIR entre les deux (zone neutre)

Objectif: Capturer les gros cycles, minimiser les trades, maximiser le gain
"""
import pandas as pd
import numpy as np
from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.strategy import calculate_rainbow_position
from src.fngbt.backtest_realistic_fees import run_backtest_realistic_fees
import warnings
warnings.filterwarnings('ignore')

print("="*100)
print("🌈 STRATÉGIE PURE RAINBOW ZONES: Acheter Minimum, Vendre Maximum")
print("="*100)
print()

# Load data
print("Chargement données...")
fng = load_fng_alt()
btc = load_btc_prices()
df = merge_daily(fng, btc)
df = calculate_rainbow_position(df)
print(f"✅ {len(df)} jours\n")

# Baseline
bh_ratio = df['close'].iloc[-1] / df['close'].iloc[0]
print(f"📊 Buy & Hold: {bh_ratio:.2f}x")
print(f"🎯 Objectif: 18x vs B&H = {18 * bh_ratio:.0f}x capital initial\n")

# Analyser distribution Rainbow
print("="*100)
print("📊 ANALYSE RAINBOW DISTRIBUTION")
print("="*100)
print()

percentiles = [1, 5, 10, 25, 50, 75, 90, 95, 99]
rainbow_percentiles = df['rainbow_position'].quantile([p/100 for p in percentiles])

print("Rainbow Position Percentiles:")
for p, val in zip(percentiles, rainbow_percentiles):
    print(f"  {p:2d}%: {val:.3f}")
print()

print(f"Min Rainbow: {df['rainbow_position'].min():.3f}")
print(f"Max Rainbow: {df['rainbow_position'].max():.3f}")
print()

# ============================================================================
# STRATÉGIE 1: Zones Extrêmes Simples
# ============================================================================

print("="*100)
print("🎯 STRATÉGIE 1: Zones Extrêmes (Buy/Sell Switches)")
print("="*100)
print()

def rainbow_extreme_zones_switch(df, buy_threshold=0.3, sell_threshold=0.8,
                                  alloc_cheap=100, alloc_expensive=70):
    """
    Stratégie switch basée sur zones extrêmes:
    - Acheter (switch to alloc_cheap) quand rainbow < buy_threshold
    - Vendre (switch to alloc_expensive) quand rainbow > sell_threshold
    - Maintenir allocation actuelle entre les deux
    """
    d = df.copy()

    # State machine: on commence à 100% (neutre)
    current_alloc = 100
    allocations = []

    for i in range(len(d)):
        rainbow = d['rainbow_position'].iloc[i]

        if rainbow < buy_threshold:
            current_alloc = alloc_cheap  # ACHETER
        elif rainbow > sell_threshold:
            current_alloc = alloc_expensive  # VENDRE
        # Sinon, maintenir current_alloc

        allocations.append(current_alloc)

    d['pos'] = allocations
    return d

# Grid search zones extrêmes
print("Grid search zones extrêmes...\n")

results_zones = []

buy_thresholds = [0.1, 0.15, 0.2, 0.25, 0.3]
sell_thresholds = [0.7, 0.75, 0.8, 0.85, 0.9]
allocation_configs = [
    (100, 70),  # Buy 100%, Sell down to 70%
    (100, 80),  # Buy 100%, Sell down to 80%
    (100, 85),  # Buy 100%, Sell down to 85%
]

for buy_thresh in buy_thresholds:
    for sell_thresh in sell_thresholds:
        for alloc_buy, alloc_sell in allocation_configs:

            signals = rainbow_extreme_zones_switch(df,
                                                   buy_threshold=buy_thresh,
                                                   sell_threshold=sell_thresh,
                                                   alloc_cheap=alloc_buy,
                                                   alloc_expensive=alloc_sell)

            result = run_backtest_realistic_fees(signals, initial_capital=100.0, fee_rate=0.001)
            metrics = result['metrics']
            ratio_bh = metrics['EquityFinal'] / (bh_ratio * 100)

            results_zones.append({
                'buy_thresh': buy_thresh,
                'sell_thresh': sell_thresh,
                'alloc_buy': alloc_buy,
                'alloc_sell': alloc_sell,
                'equity': metrics['EquityFinal'],
                'ratio_bh': ratio_bh,
                'trades': metrics['trades'],
                'fees': metrics['total_fees_paid'],
                'sharpe': metrics['Sharpe']
            })

df_zones = pd.DataFrame(results_zones).sort_values('equity', ascending=False)

print("🏆 TOP 10 (Equity EUR):")
print(df_zones[['buy_thresh', 'sell_thresh', 'alloc_buy', 'alloc_sell',
                 'equity', 'ratio_bh', 'trades', 'fees']].head(10).to_string(index=False))
print()

best_zones = df_zones.iloc[0]

print(f"🥇 MEILLEURE CONFIG:")
print(f"   Buy zone: Rainbow < {best_zones['buy_thresh']:.2f}")
print(f"   Sell zone: Rainbow > {best_zones['sell_thresh']:.2f}")
print(f"   Allocations: {best_zones['alloc_buy']:.0f}% (buy) → {best_zones['alloc_sell']:.0f}% (sell)")
print()
print(f"   💰 Equity finale: {best_zones['equity']:.2f} EUR")
print(f"   📊 Ratio vs capital: {best_zones['equity']/100:.2f}x")
print(f"   📊 Ratio vs B&H: {best_zones['ratio_bh']:.2f}x")
if best_zones['ratio_bh'] >= 18:
    print(f"   🎯 vs Objectif 18x: ✅ ATTEINT!")
else:
    print(f"   🎯 vs Objectif 18x: ❌ Manque {18 - best_zones['ratio_bh']:.1f}x")
print(f"   🔄 Trades: {int(best_zones['trades'])}")
print(f"   💸 Fees: {best_zones['fees']:.2f} EUR")
print()

# ============================================================================
# STRATÉGIE 2: Gradual (Multi-zones)
# ============================================================================

print("="*100)
print("🎯 STRATÉGIE 2: Multi-Zones Rainbow (Graduel)")
print("="*100)
print()

def rainbow_multi_zones(df, zones=[0.2, 0.4, 0.6, 0.8],
                        allocations=[100, 98, 95, 90, 85]):
    """
    Stratégie multi-zones:
    - Rainbow < zones[0]: allocations[0]
    - zones[0] <= Rainbow < zones[1]: allocations[1]
    - zones[1] <= Rainbow < zones[2]: allocations[2]
    - zones[2] <= Rainbow < zones[3]: allocations[3]
    - Rainbow >= zones[3]: allocations[4]
    """
    d = df.copy()

    d['pos'] = allocations[4]  # Default: expensive

    for i in range(len(zones)-1, -1, -1):
        d.loc[d['rainbow_position'] < zones[i], 'pos'] = allocations[i]

    return d

# Test plusieurs configurations multi-zones
print("Test configurations multi-zones...\n")

results_multi = []

multi_configs = [
    # (zones, allocations)
    ([0.15, 0.35, 0.65, 0.85], [100, 98, 95, 90, 85]),
    ([0.2, 0.4, 0.6, 0.8], [100, 97, 93, 88, 82]),
    ([0.25, 0.45, 0.65, 0.85], [100, 96, 90, 85, 80]),
    ([0.1, 0.3, 0.7, 0.9], [100, 98, 95, 88, 75]),
]

for zones, allocs in multi_configs:
    signals = rainbow_multi_zones(df, zones=zones, allocations=allocs)

    result = run_backtest_realistic_fees(signals, initial_capital=100.0, fee_rate=0.001)
    metrics = result['metrics']
    ratio_bh = metrics['EquityFinal'] / (bh_ratio * 100)

    results_multi.append({
        'zones': str(zones),
        'allocs': str(allocs),
        'equity': metrics['EquityFinal'],
        'ratio_bh': ratio_bh,
        'trades': metrics['trades'],
        'fees': metrics['total_fees_paid']
    })

df_multi = pd.DataFrame(results_multi).sort_values('equity', ascending=False)

print("Résultats Multi-Zones:")
print(df_multi.to_string(index=False))
print()

best_multi = df_multi.iloc[0]
print(f"🥇 Meilleure multi-zones: {best_multi['equity']:.2f} EUR ({best_multi['ratio_bh']:.2f}x vs B&H)")
print()

# ============================================================================
# STRATÉGIE 3: Buy & Hold in Cheap Zone
# ============================================================================

print("="*100)
print("🎯 STRATÉGIE 3: Buy & Hold UNIQUEMENT en Zone Cheap")
print("="*100)
print()

def rainbow_buy_hold_cheap_only(df, cheap_threshold=0.3):
    """
    Stratégie ultra-simple:
    - 100% BTC si rainbow < threshold (cheap)
    - 0% BTC (cash) si rainbow >= threshold

    = Acheter et tenir seulement quand BTC est cheap
    """
    d = df.copy()
    d['pos'] = np.where(d['rainbow_position'] < cheap_threshold, 100, 0)
    return d

print("Test Buy & Hold in Cheap Zone...\n")

results_cheap_only = []

for threshold in [0.15, 0.2, 0.25, 0.3, 0.35, 0.4]:
    signals = rainbow_buy_hold_cheap_only(df, cheap_threshold=threshold)

    result = run_backtest_realistic_fees(signals, initial_capital=100.0, fee_rate=0.001)
    metrics = result['metrics']
    ratio_bh = metrics['EquityFinal'] / (bh_ratio * 100)

    results_cheap_only.append({
        'cheap_threshold': threshold,
        'equity': metrics['EquityFinal'],
        'ratio_bh': ratio_bh,
        'trades': metrics['trades'],
        'fees': metrics['total_fees_paid']
    })

df_cheap = pd.DataFrame(results_cheap_only).sort_values('equity', ascending=False)

print("Résultats Buy & Hold Cheap Only:")
print(df_cheap.to_string(index=False))
print()

best_cheap = df_cheap.iloc[0]
print(f"🥇 Meilleur threshold: {best_cheap['cheap_threshold']:.2f}")
print(f"   Equity: {best_cheap['equity']:.2f} EUR ({best_cheap['ratio_bh']:.2f}x vs B&H)")
print()

# ============================================================================
# COMPARAISON FINALE
# ============================================================================

print("="*100)
print("⚖️  COMPARAISON FINALE")
print("="*100)
print()

all_strategies = pd.DataFrame([
    {
        'Stratégie': 'Buy & Hold',
        'Equity (EUR)': bh_ratio * 100,
        'Ratio vs B&H': 1.0,
        'Trades': 0,
        'Fees (EUR)': 0,
        'vs 18x': '❌'
    },
    {
        'Stratégie': 'Rainbow Zones Switch (meilleur)',
        'Equity (EUR)': best_zones['equity'],
        'Ratio vs B&H': best_zones['ratio_bh'],
        'Trades': best_zones['trades'],
        'Fees (EUR)': best_zones['fees'],
        'vs 18x': '✅' if best_zones['ratio_bh'] >= 18 else '❌'
    },
    {
        'Stratégie': 'Rainbow Multi-Zones (meilleur)',
        'Equity (EUR)': best_multi['equity'],
        'Ratio vs B&H': best_multi['ratio_bh'],
        'Trades': best_multi['trades'],
        'Fees (EUR)': best_multi['fees'],
        'vs 18x': '✅' if best_multi['ratio_bh'] >= 18 else '❌'
    },
    {
        'Stratégie': 'Buy & Hold Cheap Only (meilleur)',
        'Equity (EUR)': best_cheap['equity'],
        'Ratio vs B&H': best_cheap['ratio_bh'],
        'Trades': best_cheap['trades'],
        'Fees (EUR)': best_cheap['fees'],
        'vs 18x': '✅' if best_cheap['ratio_bh'] >= 18 else '❌'
    }
]).sort_values('Equity (EUR)', ascending=False)

print(all_strategies.to_string(index=False))
print()

# Winner
winner = all_strategies.iloc[0]
print(f"🏆 CHAMPIONNE: {winner['Stratégie']}")
print(f"   Equity finale: {winner['Equity (EUR)']:.2f} EUR")
print(f"   Ratio vs capital initial: {winner['Equity (EUR)']/100:.2f}x")
print(f"   Ratio vs B&H: {winner['Ratio vs B&H']:.2f}x")
print()

if winner['Ratio vs B&H'] >= 18:
    print(f"🎉 OBJECTIF 18x ATTEINT!")
else:
    print(f"⚠️  Objectif 18x pas atteint (manque {18 - winner['Ratio vs B&H']:.1f}x)")
    print(f"   Mais {winner['Ratio vs B&H']:.2f}x vs B&H reste excellent!")
print()

# Sauvegarder
df_zones.to_csv('outputs/rainbow_zones_results.csv', index=False)
df_multi.to_csv('outputs/rainbow_multi_zones_results.csv', index=False)
df_cheap.to_csv('outputs/rainbow_cheap_only_results.csv', index=False)
all_strategies.to_csv('outputs/rainbow_strategies_comparison.csv', index=False)

print("💾 Résultats sauvegardés:")
print("   • outputs/rainbow_zones_results.csv")
print("   • outputs/rainbow_multi_zones_results.csv")
print("   • outputs/rainbow_cheap_only_results.csv")
print("   • outputs/rainbow_strategies_comparison.csv")
print()

print("✨ Analyse Rainbow pure terminée!")
