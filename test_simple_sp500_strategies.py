#!/usr/bin/env python3
"""
🎯 STRATÉGIES SIMPLES: S&P 500 + Rainbow/FNG

Basées sur la découverte ML que sp500_ma21_above_ma50 est LA feature la plus importante (63.5%)!

Stratégies à tester:
1. S&P 500 trend seul (MA21 > MA50)
2. S&P 500 trend + Rainbow paliers
3. S&P 500 trend + FNG paliers
4. S&P 500 momentum + Rainbow

Objectif: Trouver une stratégie simple qui bat Rainbow Bands (1.156x) avec S&P 500!
"""
import pandas as pd
import numpy as np
from src.fngbt.backtest_realistic_fees import run_backtest_realistic_fees
from src.fngbt.strategy import calculate_rainbow_position
import warnings
warnings.filterwarnings('ignore')

print("="*100)
print("🎯 STRATÉGIES SIMPLES: S&P 500 + Rainbow/FNG")
print("="*100)
print()

# Load data
print("Chargement données...")
df = pd.read_csv('outputs/data_with_sp500_features.csv', parse_dates=['date'])
df = calculate_rainbow_position(df)
print(f"✅ {len(df)} jours\n")

# Recalculate features if needed
if 'sp500_ma21' not in df.columns:
    df['sp500_ma21'] = df['sp500_close'].rolling(21).mean()
if 'sp500_ma50' not in df.columns:
    df['sp500_ma50'] = df['sp500_close'].rolling(50).mean()

df['sp500_ma21_above_ma50'] = (df['sp500_ma21'] > df['sp500_ma50']).astype(int)

# ============================================================================
# STRATÉGIE 1: S&P 500 Trend Seul
# ============================================================================

def sp500_trend_only(df, alloc_bullish=100, alloc_bearish=95):
    """
    Stratégie basée uniquement sur trend S&P 500 (MA21 > MA50)

    - Bullish (MA21 > MA50): allocation haute
    - Bearish (MA21 <= MA50): allocation basse
    """
    d = df.copy()
    d['pos'] = np.where(d['sp500_ma21_above_ma50'] == 1, alloc_bullish, alloc_bearish)
    return d

print("="*100)
print("📊 STRATÉGIE 1: S&P 500 Trend Seul (MA21 > MA50)")
print("="*100)
print()

results_sp500_trend = []

for alloc_bullish in [100, 98]:
    for alloc_bearish in [95, 90, 85]:
        signals = sp500_trend_only(df, alloc_bullish, alloc_bearish)
        result = run_backtest_realistic_fees(signals, initial_capital=100.0, fee_rate=0.001)
        metrics = result['metrics']
        bh_equity = result['df']['bh_equity'].iloc[-1]
        ratio = metrics['EquityFinal'] / bh_equity

        results_sp500_trend.append({
            'alloc_bullish': alloc_bullish,
            'alloc_bearish': alloc_bearish,
            'ratio': ratio,
            'trades': metrics['trades'],
            'fees': metrics['total_fees_paid']
        })

df_sp500_trend = pd.DataFrame(results_sp500_trend).sort_values('ratio', ascending=False)
print(df_sp500_trend.to_string(index=False))
print()

best_sp500 = df_sp500_trend.iloc[0]
print(f"🥇 Meilleure: {best_sp500['alloc_bullish']}% / {best_sp500['alloc_bearish']}%")
print(f"   Ratio: {best_sp500['ratio']:.5f}x (+{(best_sp500['ratio']-1)*100:.2f}%)")
print(f"   Trades: {int(best_sp500['trades'])}, Fees: {best_sp500['fees']:.2f} EUR")
print()

# ============================================================================
# STRATÉGIE 2: S&P 500 Trend + Rainbow Paliers
# ============================================================================

def sp500_trend_rainbow(df, rainbow_threshold=0.60,
                        sp500_bullish_alloc=100, sp500_bearish_alloc=95,
                        rainbow_cheap_alloc=100, rainbow_expensive_alloc=95):
    """
    Combinaison S&P 500 trend + Rainbow paliers

    Allocation = minimum(S&P allocation, Rainbow allocation)
    → Plus conservateur des deux
    """
    d = df.copy()

    # S&P 500 allocation
    sp500_alloc = np.where(d['sp500_ma21_above_ma50'] == 1,
                           sp500_bullish_alloc,
                           sp500_bearish_alloc)

    # Rainbow allocation
    rainbow_alloc = np.where(d['rainbow_position'] < rainbow_threshold,
                             rainbow_cheap_alloc,
                             rainbow_expensive_alloc)

    # Prendre le minimum (plus conservateur)
    d['pos'] = np.minimum(sp500_alloc, rainbow_alloc)
    return d

print("="*100)
print("📊 STRATÉGIE 2: S&P 500 Trend + Rainbow Paliers")
print("="*100)
print()

results_sp500_rainbow = []

for rainbow_thresh in [0.50, 0.60, 0.70]:
    for sp500_bull in [100, 98]:
        for sp500_bear in [95, 90]:
            signals = sp500_trend_rainbow(df,
                                         rainbow_threshold=rainbow_thresh,
                                         sp500_bullish_alloc=sp500_bull,
                                         sp500_bearish_alloc=sp500_bear,
                                         rainbow_cheap_alloc=100,
                                         rainbow_expensive_alloc=95)

            result = run_backtest_realistic_fees(signals, initial_capital=100.0, fee_rate=0.001)
            metrics = result['metrics']
            bh_equity = result['df']['bh_equity'].iloc[-1]
            ratio = metrics['EquityFinal'] / bh_equity

            results_sp500_rainbow.append({
                'rainbow_thresh': rainbow_thresh,
                'sp500_bull': sp500_bull,
                'sp500_bear': sp500_bear,
                'ratio': ratio,
                'trades': metrics['trades'],
                'fees': metrics['total_fees_paid']
            })

df_sp500_rainbow = pd.DataFrame(results_sp500_rainbow).sort_values('ratio', ascending=False)
print(df_sp500_rainbow.head(10).to_string(index=False))
print()

best_combo = df_sp500_rainbow.iloc[0]
print(f"🥇 Meilleure combo:")
print(f"   Rainbow threshold: {best_combo['rainbow_thresh']}")
print(f"   S&P 500: {best_combo['sp500_bull']}% (bull) / {best_combo['sp500_bear']}% (bear)")
print(f"   Ratio: {best_combo['ratio']:.5f}x (+{(best_combo['ratio']-1)*100:.2f}%)")
print(f"   Trades: {int(best_combo['trades'])}, Fees: {best_combo['fees']:.2f} EUR")
print()

# ============================================================================
# STRATÉGIE 3: S&P 500 Trend + FNG Paliers
# ============================================================================

def sp500_trend_fng(df, fng_threshold=50,
                    sp500_bullish_alloc=100, sp500_bearish_alloc=95,
                    fng_fear_alloc=100, fng_greed_alloc=95):
    """
    Combinaison S&P 500 trend + FNG paliers
    """
    d = df.copy()

    # S&P 500 allocation
    sp500_alloc = np.where(d['sp500_ma21_above_ma50'] == 1,
                           sp500_bullish_alloc,
                           sp500_bearish_alloc)

    # FNG allocation
    fng_alloc = np.where(d['fng'] < fng_threshold,
                         fng_fear_alloc,
                         fng_greed_alloc)

    # Prendre le minimum
    d['pos'] = np.minimum(sp500_alloc, fng_alloc)
    return d

print("="*100)
print("📊 STRATÉGIE 3: S&P 500 Trend + FNG Paliers")
print("="*100)
print()

results_sp500_fng = []

for fng_thresh in [40, 50, 60]:
    for sp500_bull in [100, 98]:
        for sp500_bear in [95, 90]:
            signals = sp500_trend_fng(df,
                                     fng_threshold=fng_thresh,
                                     sp500_bullish_alloc=sp500_bull,
                                     sp500_bearish_alloc=sp500_bear,
                                     fng_fear_alloc=100,
                                     fng_greed_alloc=95)

            result = run_backtest_realistic_fees(signals, initial_capital=100.0, fee_rate=0.001)
            metrics = result['metrics']
            bh_equity = result['df']['bh_equity'].iloc[-1]
            ratio = metrics['EquityFinal'] / bh_equity

            results_sp500_fng.append({
                'fng_thresh': fng_thresh,
                'sp500_bull': sp500_bull,
                'sp500_bear': sp500_bear,
                'ratio': ratio,
                'trades': metrics['trades'],
                'fees': metrics['total_fees_paid']
            })

df_sp500_fng = pd.DataFrame(results_sp500_fng).sort_values('ratio', ascending=False)
print(df_sp500_fng.head(10).to_string(index=False))
print()

best_fng = df_sp500_fng.iloc[0]
print(f"🥇 Meilleure combo:")
print(f"   FNG threshold: {best_fng['fng_thresh']}")
print(f"   S&P 500: {best_fng['sp500_bull']}% (bull) / {best_fng['sp500_bear']}% (bear)")
print(f"   Ratio: {best_fng['ratio']:.5f}x (+{(best_fng['ratio']-1)*100:.2f}%)")
print(f"   Trades: {int(best_fng['trades'])}, Fees: {best_fng['fees']:.2f} EUR")
print()

# ============================================================================
# COMPARAISON FINALE
# ============================================================================

print("="*100)
print("📊 COMPARAISON FINALE: Toutes Stratégies")
print("="*100)
print()

comparison = pd.DataFrame([
    {
        'Stratégie': 'Rainbow Bands (baseline)',
        'Ratio': 1.15529,
        'Amélioration': '+15.53%',
        'Trades': 658,
        'Fees': 0.65
    },
    {
        'Stratégie': 'FNG+Rainbow Hybrid',
        'Ratio': 1.18183,
        'Amélioration': '+18.18%',
        'Trades': 2165,
        'Fees': 3.64
    },
    {
        'Stratégie': 'FNG MA21',
        'Ratio': 1.49656,
        'Amélioration': '+49.66%',
        'Trades': 2709,
        'Fees': 3.55
    },
    {
        'Stratégie': 'S&P 500 Trend seul',
        'Ratio': best_sp500['ratio'],
        'Amélioration': f"+{(best_sp500['ratio']-1)*100:.2f}%",
        'Trades': best_sp500['trades'],
        'Fees': best_sp500['fees']
    },
    {
        'Stratégie': 'S&P 500 + Rainbow',
        'Ratio': best_combo['ratio'],
        'Amélioration': f"+{(best_combo['ratio']-1)*100:.2f}%",
        'Trades': best_combo['trades'],
        'Fees': best_combo['fees']
    },
    {
        'Stratégie': 'S&P 500 + FNG',
        'Ratio': best_fng['ratio'],
        'Amélioration': f"+{(best_fng['ratio']-1)*100:.2f}%",
        'Trades': best_fng['trades'],
        'Fees': best_fng['fees']
    },
    {
        'Stratégie': 'ML avec S&P 500 (OOS)',
        'Ratio': 1.284,
        'Amélioration': '+28.35%',
        'Trades': 'N/A',
        'Fees': 'N/A'
    }
])

print(comparison.to_string(index=False))
print()

# Meilleure stratégie
best_strat = comparison.loc[comparison['Ratio'].idxmax()]
print(f"🥇 STRATÉGIE CHAMPIONNE (avec S&P 500): {best_strat['Stratégie']}")
print(f"   Ratio: {best_strat['Ratio']:.5f}x")
print(f"   Amélioration: {best_strat['Amélioration']}")
print()

# Sauvegarder
df_sp500_trend.to_csv('outputs/sp500_trend_only_results.csv', index=False)
df_sp500_rainbow.to_csv('outputs/sp500_rainbow_combo_results.csv', index=False)
df_sp500_fng.to_csv('outputs/sp500_fng_combo_results.csv', index=False)
comparison.to_csv('outputs/final_comparison_with_sp500.csv', index=False)

print("💾 Résultats sauvegardés:")
print("   • outputs/sp500_trend_only_results.csv")
print("   • outputs/sp500_rainbow_combo_results.csv")
print("   • outputs/sp500_fng_combo_results.csv")
print("   • outputs/final_comparison_with_sp500.csv")
print()

print("✨ Test stratégies simples S&P 500 terminé!")
