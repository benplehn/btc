#!/usr/bin/env python3
"""
💥 STRATÉGIE CRASH & RALLY: Viser 18x vs B&H

Inspirée du perfect swing trading (-5%/+15% = 481x vs B&H)

Principe:
1. Identifier les VRAIS crashes (drawdown profond depuis ATH)
2. Acheter massivement à ces crashes
3. Tenir jusqu'aux rallyes extrêmes
4. Vendre partiellement aux pics
5. Minimiser les trades inutiles

Objectif: Capturer les gros mouvements, ignorer le bruit
"""
import pandas as pd
import numpy as np
from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.strategy import calculate_rainbow_position
from src.fngbt.backtest_realistic_fees import run_backtest_realistic_fees
import warnings
warnings.filterwarnings('ignore')

print("="*100)
print("💥 STRATÉGIE CRASH & RALLY: Viser 18x vs B&H")
print("="*100)
print()

# Load data
print("Chargement données...")
fng = load_fng_alt()
btc = load_btc_prices()
df = merge_daily(fng, btc)
df = calculate_rainbow_position(df)
print(f"✅ {len(df)} jours\n")

# Calculate features
df['ath'] = df['close'].expanding().max()
df['drawdown'] = (df['close'] / df['ath'] - 1) * 100
df['rolling_low_30'] = df['close'].rolling(30).min()
df['gain_from_30d_low'] = (df['close'] / df['rolling_low_30'] - 1) * 100

# B&H baseline
bh_ratio = df['close'].iloc[-1] / df['close'].iloc[0]
print(f"📊 Buy & Hold: {bh_ratio:.2f}x")
print(f"🎯 Objectif: {18:.0f}x vs B&H = {18 * bh_ratio:.0f}x capital initial")
print()

# ============================================================================
# TEST DIFFÉRENTES CONFIGURATIONS CRASH & RALLY
# ============================================================================

print("="*100)
print("🔍 GRID SEARCH: Crash & Rally Parameters")
print("="*100)
print()

results = []

# Paramètres à tester
crash_thresholds = [-20, -30, -40, -50]  # Drawdown depuis ATH
rally_thresholds = [20, 30, 40, 50]       # Hausse depuis creux 30j
allocation_configs = [
    # (normal, crash, rally)
    (95, 100, 90),   # Conservateur
    (90, 100, 85),   # Modéré
    (85, 100, 80),   # Agressif
    (80, 100, 70),   # Très agressif
]

total_configs = len(crash_thresholds) * len(rally_thresholds) * len(allocation_configs)
print(f"Total configurations: {total_configs}\n")

tested = 0
for crash_dd in crash_thresholds:
    for rally_gain in rally_thresholds:
        for alloc_normal, alloc_crash, alloc_rally in allocation_configs:

            d = df.copy()

            # Allocation based on crash/rally
            is_crash = d['drawdown'] <= crash_dd
            is_rally = d['gain_from_30d_low'] >= rally_gain

            d['pos'] = np.where(is_crash, alloc_crash,
                      np.where(is_rally, alloc_rally, alloc_normal))

            # Backtest
            result = run_backtest_realistic_fees(d, initial_capital=100.0, fee_rate=0.001)
            metrics = result['metrics']
            ratio_bh = metrics['EquityFinal'] / (bh_ratio * 100)

            results.append({
                'crash_dd': crash_dd,
                'rally_gain': rally_gain,
                'alloc_normal': alloc_normal,
                'alloc_crash': alloc_crash,
                'alloc_rally': alloc_rally,
                'equity': metrics['EquityFinal'],
                'ratio_bh': ratio_bh,
                'trades': metrics['trades'],
                'fees': metrics['total_fees_paid'],
                'sharpe': metrics['Sharpe']
            })

            tested += 1
            if tested % 20 == 0:
                print(f"Progress: {tested}/{total_configs} ({tested/total_configs*100:.0f}%)")

print(f"\n✅ {len(results)} configurations testées\n")

# Trier par ratio vs B&H
df_results = pd.DataFrame(results).sort_values('ratio_bh', ascending=False)

print("="*100)
print("🏆 TOP 10 CONFIGURATIONS (Ratio vs B&H)")
print("="*100)
print()

print(df_results[['crash_dd', 'rally_gain', 'alloc_normal', 'alloc_crash', 'alloc_rally',
                   'equity', 'ratio_bh', 'trades', 'fees']].head(10).to_string(index=False))
print()

# Meilleure config
best = df_results.iloc[0]

print(f"🥇 MEILLEURE CONFIGURATION:")
print(f"   Crash threshold: Drawdown <= {best['crash_dd']:.0f}%")
print(f"   Rally threshold: Gain >= +{best['rally_gain']:.0f}%")
print(f"   Allocations: Normal {best['alloc_normal']:.0f}% / Crash {best['alloc_crash']:.0f}% / Rally {best['alloc_rally']:.0f}%")
print()
print(f"   💰 Equity finale: {best['equity']:.2f} EUR")
print(f"   📊 Ratio vs B&H: {best['ratio_bh']:.2f}x")
if best['ratio_bh'] >= 18:
    print(f"   🎯 vs Objectif 18x: ✅ ATTEINT!")
else:
    missing = 18 - best['ratio_bh']
    print(f"   🎯 vs Objectif 18x: ❌ Manque {missing:.1f}x")
print(f"   🔄 Trades: {int(best['trades'])}")
print(f"   💸 Fees: {best['fees']:.2f} EUR")
print(f"   📈 Sharpe: {best['sharpe']:.2f}")
print()

# ============================================================================
# STRATÉGIE HYBRIDE: Crash & Rally + FNG/Rainbow
# ============================================================================

print("="*100)
print("🎯 STRATÉGIE HYBRIDE: Crash & Rally + FNG/Rainbow/S&P")
print("="*100)
print()

# Ajouter S&P si disponible
if 'sp500_close' in df.columns:
    df['sp500_ma21'] = df['sp500_close'].rolling(21).mean()
    df['sp500_ma50'] = df['sp500_close'].rolling(50).mean()
    df['sp500_bullish'] = (df['sp500_ma21'] > df['sp500_ma50']).astype(int)
else:
    df['sp500_bullish'] = 1  # Assume bullish si pas de données

# Combiner facteurs
d = df.copy()

# Score de conditions bullish
crash_extreme = (d['drawdown'] <= -40).astype(int)
crash_moderate = (d['drawdown'] <= -20).astype(int) & (d['drawdown'] > -40).astype(int)
rally_extreme = (d['gain_from_30d_low'] >= 40).astype(int)

rainbow_cheap = (d['rainbow_position'] < 0.4).astype(int)
fng_fear = (d['fng'] < 25).astype(int)
sp500_bull = d['sp500_bullish']

# Allocation multi-facteurs
d['pos'] = 95  # Default

# Crashes = acheter fort
d.loc[crash_extreme == 1, 'pos'] = 100
d.loc[crash_moderate == 1, 'pos'] = 98

# Rallyes extrêmes = réduire
d.loc[rally_extreme == 1, 'pos'] = 80

# Ajuster selon FNG/Rainbow quand pas de crash/rally
normal_conditions = (crash_extreme == 0) & (crash_moderate == 0) & (rally_extreme == 0)
bullish_score = rainbow_cheap + fng_fear + sp500_bull
d.loc[normal_conditions & (bullish_score == 3), 'pos'] = 100
d.loc[normal_conditions & (bullish_score == 2), 'pos'] = 96
d.loc[normal_conditions & (bullish_score == 1), 'pos'] = 92
d.loc[normal_conditions & (bullish_score == 0), 'pos'] = 85

# Backtest
result = run_backtest_realistic_fees(d, initial_capital=100.0, fee_rate=0.001)
metrics = result['metrics']
ratio_bh = metrics['EquityFinal'] / (bh_ratio * 100)

print("📊 Performance Stratégie Hybride:")
print(f"   Equity finale: {metrics['EquityFinal']:.2f} EUR")
print(f"   Ratio vs B&H: {ratio_bh:.2f}x")
if ratio_bh >= 18:
    print(f"   vs Objectif 18x: ✅ ATTEINT!")
else:
    missing = 18 - ratio_bh
    print(f"   vs Objectif 18x: ❌ Manque {missing:.1f}x")
print(f"   Trades: {metrics['trades']}")
print(f"   Fees: {metrics['total_fees_paid']:.2f} EUR")
print(f"   Sharpe: {metrics['Sharpe']:.2f}")
print()

# ============================================================================
# COMPARAISON FINALE
# ============================================================================

print("="*100)
print("⚖️  COMPARAISON FINALE")
print("="*100)
print()

comparison = pd.DataFrame([
    {
        'Stratégie': 'Buy & Hold',
        'Equity (EUR)': bh_ratio * 100,
        'Ratio vs B&H': 1.0,
        'vs Objectif 18x': '❌'
    },
    {
        'Stratégie': 'Triple Factor (OOS validé)',
        'Equity (EUR)': 1.100 * bh_ratio * 100,
        'Ratio vs B&H': 1.100,
        'vs Objectif 18x': '❌'
    },
    {
        'Stratégie': 'Perfect Swing (-5%/+15%)',
        'Equity (EUR)': 295722,
        'Ratio vs B&H': 481,
        'vs Objectif 18x': '✅ (481x!)'
    },
    {
        'Stratégie': 'Crash & Rally (meilleur)',
        'Equity (EUR)': best['equity'],
        'Ratio vs B&H': best['ratio_bh'],
        'vs Objectif 18x': '✅' if float(best['ratio_bh']) >= 18 else '❌'
    },
    {
        'Stratégie': 'Hybride (Crash+Rally+FNG+Rainbow+S&P)',
        'Equity (EUR)': metrics['EquityFinal'],
        'Ratio vs B&H': ratio_bh,
        'vs Objectif 18x': '✅' if float(ratio_bh) >= 18 else '❌'
    }
])

print(comparison.to_string(index=False))
print()

# Sauvegarder résultats
df_results.to_csv('outputs/crash_rally_grid_search.csv', index=False)
result['df'].to_csv('outputs/crash_rally_hybrid_details.csv', index=False)

print("💾 Résultats sauvegardés:")
print("   • outputs/crash_rally_grid_search.csv")
print("   • outputs/crash_rally_hybrid_details.csv")
print()

print("="*100)
print("💡 CONCLUSION")
print("="*100)
print()

if best['ratio_bh'] >= 18 or ratio_bh >= 18:
    print("🎉 OBJECTIF ATTEINT!")
    winner = 'Crash & Rally' if best['ratio_bh'] > ratio_bh else 'Hybride'
    winner_ratio = max(best['ratio_bh'], ratio_bh)
    print(f"   Stratégie {winner}: {winner_ratio:.1f}x vs B&H")
    print(f"   (Équivalent à {winner_ratio * bh_ratio:.0f}x le capital initial)")
else:
    print("⚠️  18x vs B&H n'est PAS atteint avec ces stratégies.")
    print(f"   Meilleure: {max(best['ratio_bh'], ratio_bh):.1f}x vs B&H")
    print()
    print("💡 Rappel: Perfect swing trading peut faire 481x vs B&H,")
    print("   MAIS nécessite un timing parfait impossible sans hindsight.")
    print()
    print("   Pour atteindre 18x, il faudrait:")
    print("   • Prédire les vrais crashes (drawdown >30%)")
    print("   • Prédire les vrais rallyes (hausse >40%)")
    print("   • Minimiser les faux signaux")

print("\n✨ Analyse terminée!")
