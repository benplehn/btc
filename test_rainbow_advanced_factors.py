#!/usr/bin/env python3
"""
FACTEURS RAINBOW AVANCÉS

Tests de transformations du Rainbow Chart:
1. Accélération (dérivée seconde)
2. Percentile historique (où on est par rapport à l'historique)
3. Z-Score (écart normalisé vs moyenne)
4. Bandes de Bollinger Rainbow
5. RSI sur Rainbow
6. Rate of Change (ROC)

Objectif: Battre 1.36158x
"""
import pandas as pd
import numpy as np
from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.strategy import calculate_rainbow_position
from src.fngbt.backtest import run_backtest

def rainbow_acceleration_strategy(df, window=7, accel_threshold=0.01, alloc_high_accel=95):
    """
    Accélération Rainbow = dérivée seconde = changement de la vitesse

    Haute accélération = changement rapide de tendance → Prudence
    """
    d = df.copy()
    d = calculate_rainbow_position(d)

    # Vélocité = dérivée première
    d['rainbow_velocity'] = d['rainbow_position'].diff(window)

    # Accélération = dérivée seconde
    d['rainbow_acceleration'] = d['rainbow_velocity'].diff(window).abs()

    # Haute accélération = instabilité
    high_accel = d['rainbow_acceleration'] > accel_threshold

    d['pos'] = np.where(high_accel, alloc_high_accel, 100)
    d['trade'] = (d['pos'].diff().abs() > 0.5).astype(int)

    return d

def rainbow_percentile_strategy(df, lookback=365, high_percentile=0.75, alloc_high=95):
    """
    Percentile historique: Où est Rainbow par rapport aux N derniers jours?

    Si Rainbow > 75e percentile historique → Top zone → Réduire
    """
    d = df.copy()
    d = calculate_rainbow_position(d)

    # Percentile rolling sur lookback jours
    d['rainbow_percentile'] = d['rainbow_position'].rolling(
        window=lookback, min_periods=30
    ).apply(lambda x: (x.iloc[-1] > x).sum() / len(x) if len(x) > 0 else 0.5)

    # Si dans top percentile historique
    in_top = d['rainbow_percentile'] > high_percentile

    d['pos'] = np.where(in_top, alloc_high, 100)
    d['trade'] = (d['pos'].diff().abs() > 0.5).astype(int)

    return d

def rainbow_zscore_strategy(df, window=90, zscore_threshold=1.5, alloc_extreme=95):
    """
    Z-Score: Écart normalisé vs moyenne mobile

    Z-Score élevé = Rainbow très loin de sa moyenne → Extrême → Prudence
    """
    d = df.copy()
    d = calculate_rainbow_position(d)

    # Moyenne et std rolling
    d['rainbow_ma'] = d['rainbow_position'].rolling(window=window, min_periods=30).mean()
    d['rainbow_std'] = d['rainbow_position'].rolling(window=window, min_periods=30).std()

    # Z-Score = (valeur - moyenne) / std
    d['rainbow_zscore'] = (d['rainbow_position'] - d['rainbow_ma']) / (d['rainbow_std'] + 1e-6)

    # Si Z-Score élevé (dans les extrêmes)
    extreme = d['rainbow_zscore'].abs() > zscore_threshold

    d['pos'] = np.where(extreme, alloc_extreme, 100)
    d['trade'] = (d['pos'].diff().abs() > 0.5).astype(int)

    return d

def rainbow_bollinger_strategy(df, window=20, num_std=2.0, alloc_outside=95):
    """
    Bandes de Bollinger sur Rainbow

    Rainbow en dehors des bandes → Extrême → Réduire
    """
    d = df.copy()
    d = calculate_rainbow_position(d)

    # Bandes de Bollinger
    d['rainbow_ma'] = d['rainbow_position'].rolling(window=window, min_periods=10).mean()
    d['rainbow_std'] = d['rainbow_position'].rolling(window=window, min_periods=10).std()

    d['bb_upper'] = d['rainbow_ma'] + num_std * d['rainbow_std']
    d['bb_lower'] = d['rainbow_ma'] - num_std * d['rainbow_std']

    # En dehors des bandes
    outside = (d['rainbow_position'] > d['bb_upper']) | (d['rainbow_position'] < d['bb_lower'])

    d['pos'] = np.where(outside, alloc_outside, 100)
    d['trade'] = (d['pos'].diff().abs() > 0.5).astype(int)

    return d

def rainbow_rsi_strategy(df, window=14, overbought=70, oversold=30, alloc_ob=95, alloc_os=100):
    """
    RSI sur Rainbow position

    RSI > 70 = Rainbow overbought → Réduire
    RSI < 30 = Rainbow oversold → Full allocation
    """
    d = df.copy()
    d = calculate_rainbow_position(d)

    # RSI calculation
    delta = d['rainbow_position'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=window, min_periods=1).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=window, min_periods=1).mean()

    rs = gain / (loss + 1e-6)
    d['rainbow_rsi'] = 100 - (100 / (1 + rs))

    # Signaux
    allocation = np.ones(len(d)) * 100
    allocation[d['rainbow_rsi'] > overbought] = alloc_ob
    allocation[d['rainbow_rsi'] < oversold] = alloc_os

    d['pos'] = allocation
    d['trade'] = (d['pos'].diff().abs() > 0.5).astype(int)

    return d

def rainbow_roc_strategy(df, window=10, roc_threshold=0.15, alloc_high_roc=95):
    """
    Rate of Change (ROC) sur Rainbow

    ROC élevé = changement rapide → Volatilité → Prudence
    """
    d = df.copy()
    d = calculate_rainbow_position(d)

    # ROC = (valeur - valeur N jours avant) / valeur N jours avant
    d['rainbow_roc'] = d['rainbow_position'].pct_change(periods=window).abs()

    # ROC élevé = volatilité
    high_roc = d['rainbow_roc'] > roc_threshold

    d['pos'] = np.where(high_roc, alloc_high_roc, 100)
    d['trade'] = (d['pos'].diff().abs() > 0.5).astype(int)

    return d

# Load data
print("Chargement des données...")
fng = load_fng_alt()
btc = load_btc_prices()
df = merge_daily(fng, btc)
print(f"✅ {len(df)} jours chargés\n")

# Baseline
bh = df.copy()
bh['pos'] = 100.0
bh['trade'] = 0
bh_result = run_backtest(bh, fees_bps=0.0)
bh_equity = bh_result['metrics']['EquityFinal']

print("="*100)
print("🔬 FACTEURS RAINBOW AVANCÉS: Accélération, Percentile, Z-Score, etc.")
print("="*100)
print(f"\n📊 Buy & Hold: {bh_equity:.2f}x")
print(f"🏆 À battre: 1.36158x (+36.2%)\n")

results = []

# 1. ACCÉLÉRATION
print("="*100)
print("🔍 TEST 1: RAINBOW ACCÉLÉRATION (Dérivée Seconde)")
print("="*100)
print()

for window in [5, 7, 10, 14]:
    for accel_thresh in [0.005, 0.01, 0.015, 0.02]:
        for alloc in [94, 95, 96, 97]:
            signals = rainbow_acceleration_strategy(df, window, accel_thresh, alloc)
            result = run_backtest(signals, fees_bps=10.0)
            metrics = result['metrics']
            ratio = metrics['EquityFinal'] / bh_equity

            if ratio > 1.20:
                marker = "🚀" if ratio > 1.36158 else "🎉"
                print(f"{marker} Accélération w={window}, thresh={accel_thresh:.3f}, alloc={alloc}% → {ratio:.5f}x | Trades {metrics['trades']:4d}")

                results.append({
                    'strategy': 'Rainbow_Acceleration',
                    'config': f"w={window},t={accel_thresh},a={alloc}",
                    'ratio': ratio,
                    'equity': metrics['EquityFinal'],
                    'trades': metrics['trades']
                })

# 2. PERCENTILE HISTORIQUE
print(f"\n{'='*100}")
print("🔍 TEST 2: RAINBOW PERCENTILE HISTORIQUE")
print("="*100)
print()

for lookback in [180, 365, 730]:
    for percentile in [0.70, 0.75, 0.80, 0.85]:
        for alloc in [94, 95, 96, 97]:
            signals = rainbow_percentile_strategy(df, lookback, percentile, alloc)
            result = run_backtest(signals, fees_bps=10.0)
            metrics = result['metrics']
            ratio = metrics['EquityFinal'] / bh_equity

            if ratio > 1.20:
                marker = "🚀" if ratio > 1.36158 else "🎉"
                print(f"{marker} Percentile lookback={lookback}, p={percentile:.2f}, alloc={alloc}% → {ratio:.5f}x | Trades {metrics['trades']:4d}")

                results.append({
                    'strategy': 'Rainbow_Percentile',
                    'config': f"lb={lookback},p={percentile},a={alloc}",
                    'ratio': ratio,
                    'equity': metrics['EquityFinal'],
                    'trades': metrics['trades']
                })

# 3. Z-SCORE
print(f"\n{'='*100}")
print("🔍 TEST 3: RAINBOW Z-SCORE (Écart Normalisé)")
print("="*100)
print()

for window in [30, 60, 90, 180]:
    for zscore_thresh in [1.0, 1.5, 2.0, 2.5]:
        for alloc in [94, 95, 96, 97]:
            signals = rainbow_zscore_strategy(df, window, zscore_thresh, alloc)
            result = run_backtest(signals, fees_bps=10.0)
            metrics = result['metrics']
            ratio = metrics['EquityFinal'] / bh_equity

            if ratio > 1.20:
                marker = "🚀" if ratio > 1.36158 else "🎉"
                print(f"{marker} Z-Score w={window}, thresh={zscore_thresh:.1f}, alloc={alloc}% → {ratio:.5f}x | Trades {metrics['trades']:4d}")

                results.append({
                    'strategy': 'Rainbow_ZScore',
                    'config': f"w={window},z={zscore_thresh},a={alloc}",
                    'ratio': ratio,
                    'equity': metrics['EquityFinal'],
                    'trades': metrics['trades']
                })

# 4. BOLLINGER BANDS
print(f"\n{'='*100}")
print("🔍 TEST 4: RAINBOW BOLLINGER BANDS")
print("="*100)
print()

for window in [10, 14, 20, 30]:
    for num_std in [1.5, 2.0, 2.5]:
        for alloc in [94, 95, 96, 97]:
            signals = rainbow_bollinger_strategy(df, window, num_std, alloc)
            result = run_backtest(signals, fees_bps=10.0)
            metrics = result['metrics']
            ratio = metrics['EquityFinal'] / bh_equity

            if ratio > 1.20:
                marker = "🚀" if ratio > 1.36158 else "🎉"
                print(f"{marker} Bollinger w={window}, std={num_std:.1f}, alloc={alloc}% → {ratio:.5f}x | Trades {metrics['trades']:4d}")

                results.append({
                    'strategy': 'Rainbow_Bollinger',
                    'config': f"w={window},std={num_std},a={alloc}",
                    'ratio': ratio,
                    'equity': metrics['EquityFinal'],
                    'trades': metrics['trades']
                })

# 5. RSI
print(f"\n{'='*100}")
print("🔍 TEST 5: RAINBOW RSI")
print("="*100)
print()

for window in [7, 14, 21]:
    for overbought in [65, 70, 75]:
        for oversold in [25, 30, 35]:
            for alloc_ob in [94, 95, 96, 97]:
                signals = rainbow_rsi_strategy(df, window, overbought, oversold, alloc_ob, 100)
                result = run_backtest(signals, fees_bps=10.0)
                metrics = result['metrics']
                ratio = metrics['EquityFinal'] / bh_equity

                if ratio > 1.20:
                    marker = "🚀" if ratio > 1.36158 else "🎉"
                    print(f"{marker} RSI w={window}, OB={overbought}, OS={oversold}, alloc={alloc_ob}% → {ratio:.5f}x | Trades {metrics['trades']:4d}")

                    results.append({
                        'strategy': 'Rainbow_RSI',
                        'config': f"w={window},ob={overbought},os={oversold},a={alloc_ob}",
                        'ratio': ratio,
                        'equity': metrics['EquityFinal'],
                        'trades': metrics['trades']
                    })

# 6. ROC (Rate of Change)
print(f"\n{'='*100}")
print("🔍 TEST 6: RAINBOW RATE OF CHANGE (ROC)")
print("="*100)
print()

for window in [5, 7, 10, 14, 21]:
    for roc_thresh in [0.10, 0.15, 0.20, 0.25]:
        for alloc in [94, 95, 96, 97]:
            signals = rainbow_roc_strategy(df, window, roc_thresh, alloc)
            result = run_backtest(signals, fees_bps=10.0)
            metrics = result['metrics']
            ratio = metrics['EquityFinal'] / bh_equity

            if ratio > 1.20:
                marker = "🚀" if ratio > 1.36158 else "🎉"
                print(f"{marker} ROC w={window}, thresh={roc_thresh:.2f}, alloc={alloc}% → {ratio:.5f}x | Trades {metrics['trades']:4d}")

                results.append({
                    'strategy': 'Rainbow_ROC',
                    'config': f"w={window},t={roc_thresh},a={alloc}",
                    'ratio': ratio,
                    'equity': metrics['EquityFinal'],
                    'trades': metrics['trades']
                })

# MEILLEURE
print(f"\n{'='*100}")
print("🏆 MEILLEUR FACTEUR RAINBOW TROUVÉ")
print("="*100)

if results:
    df_results = pd.DataFrame(results)
    best = df_results.loc[df_results['ratio'].idxmax()]

    print(f"\nType: {best['strategy']}")
    print(f"Config: {best['config']}")
    print(f"Ratio vs B&H: {best['ratio']:.5f}x")
    print(f"Equity: {best['equity']:.4f}x")
    print(f"Trades: {best['trades']}")

    if best['ratio'] > 1.36158:
        print(f"\n🚀🚀🚀 NOUVELLE CHAMPIONNE! Bat précédente de {(best['ratio']-1.36158)*100:.3f}%!")
    elif best['ratio'] > 1.0:
        print(f"\n🎉 Bat B&H de {(best['ratio']-1)*100:.3f}%")

    # Sauvegarder
    df_results = df_results.sort_values('ratio', ascending=False)
    df_results.to_csv('outputs/rainbow_advanced_factors_results.csv', index=False)
    print(f"\n💾 Résultats: outputs/rainbow_advanced_factors_results.csv")

    print(f"\n📊 Top 10:")
    print(df_results.head(10)[['strategy', 'config', 'ratio', 'trades']].to_string(index=False))
else:
    print("\n⚠️  Aucun facteur > 1.20x")

print(f"\n✨ Tests terminés!")
