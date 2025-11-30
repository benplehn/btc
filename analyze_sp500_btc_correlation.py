#!/usr/bin/env python3
"""
🔍 ANALYSE: Corrélation S&P 500 vs BTC avec Lags

Hypothèse: S&P 500 est en avance sur BTC de quelques jours/semaines
Si S&P 500 monte, BTC suit avec un délai (lag)

Ce script teste:
1. Corrélation S&P 500 vs BTC returns avec différents lags (0-30 jours)
2. Quelle lag donne la meilleure corrélation?
3. Visualisation de la relation
"""
import pandas as pd
import numpy as np
from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.data_sp500 import load_sp500_prices, merge_sp500_with_data
import matplotlib.pyplot as plt

print("="*100)
print("🔍 ANALYSE: Corrélation S&P 500 vs BTC avec Lags")
print("="*100)
print()

# Load data
print("Chargement données...")
fng = load_fng_alt()
btc = load_btc_prices()
sp500 = load_sp500_prices()

df = merge_daily(fng, btc)
df = merge_sp500_with_data(df, sp500)

print(f"✅ {len(df)} jours de données (2018-2025)\n")

# Calculer returns
df['btc_return'] = df['close'].pct_change()
df['sp500_return'] = df['sp500_close'].pct_change()

# Calculer returns cumulés
df['btc_cumret'] = (1 + df['btc_return']).cumprod()
df['sp500_cumret'] = (1 + df['sp500_return']).cumprod()

print("📊 Performance Globale:")
print(f"   • BTC: {df['btc_cumret'].iloc[-1]:.2f}x")
print(f"   • S&P 500: {df['sp500_cumret'].iloc[-1]:.2f}x")
print()

# Test correlation avec différents lags
print("="*100)
print("🔍 Test Corrélation avec Lags (0-30 jours)")
print("="*100)
print()

lags_to_test = list(range(0, 31))  # 0 à 30 jours
correlations = []

for lag in lags_to_test:
    # S&P 500 return à t-lag vs BTC return à t
    # Lag positif = S&P 500 en avance
    sp500_lagged = df['sp500_return'].shift(lag)
    corr = sp500_lagged.corr(df['btc_return'])
    correlations.append({
        'lag': lag,
        'correlation': corr
    })

df_corr = pd.DataFrame(correlations)

print("Corrélations par lag:")
print(df_corr.to_string(index=False))
print()

# Meilleure corrélation
best_lag = df_corr.loc[df_corr['correlation'].idxmax()]
print(f"🥇 Meilleure corrélation: LAG {int(best_lag['lag'])} jours")
print(f"   Corrélation: {best_lag['correlation']:.4f}")
print()

if best_lag['lag'] > 0:
    print(f"✅ CONFIRMATION: S&P 500 est en avance de {int(best_lag['lag'])} jour(s) sur BTC!")
elif best_lag['lag'] == 0:
    print("⚠️  Corrélation simultanée (lag 0) - pas de leading effect détecté")
print()

# Sauvegarder
df_corr.to_csv('outputs/sp500_btc_lag_correlations.csv', index=False)

# Tester avec returns cumulés sur différentes périodes
print("="*100)
print("🔍 Test Corrélation Forward Returns (Prédictif)")
print("="*100)
print()

# S&P 500 return aujourd'hui vs BTC return dans N jours
forward_periods = [1, 3, 5, 7, 14, 21, 30]
forward_corrs = []

for period in forward_periods:
    # S&P 500 return aujourd'hui
    sp500_ret = df['sp500_return']
    # BTC return futur (dans N jours)
    btc_future_ret = df['close'].pct_change(period).shift(-period)

    corr = sp500_ret.corr(btc_future_ret)
    forward_corrs.append({
        'forward_days': period,
        'correlation': corr,
        'interpretation': f"S&P 500 return aujourd'hui → BTC return dans {period}j"
    })

df_forward = pd.DataFrame(forward_corrs)
print("Corrélations forward (prédictives):")
print(df_forward[['forward_days', 'correlation']].to_string(index=False))
print()

best_forward = df_forward.loc[df_forward['correlation'].idxmax()]
print(f"🥇 Meilleur forward period: {int(best_forward['forward_days'])} jours")
print(f"   Corrélation: {best_forward['correlation']:.4f}")
print(f"   → {best_forward['interpretation']}")
print()

df_forward.to_csv('outputs/sp500_btc_forward_correlations.csv', index=False)

# Créer features basées sur S&P 500 momentum/tendance
print("="*100)
print("📊 Features S&P 500 à Créer")
print("="*100)
print()

# Calculer plusieurs features S&P 500
df['sp500_ma7'] = df['sp500_close'].rolling(7).mean()
df['sp500_ma14'] = df['sp500_close'].rolling(14).mean()
df['sp500_ma21'] = df['sp500_close'].rolling(21).mean()
df['sp500_ma50'] = df['sp500_close'].rolling(50).mean()

# Momentum (prix vs MA)
df['sp500_above_ma7'] = (df['sp500_close'] > df['sp500_ma7']).astype(int)
df['sp500_above_ma21'] = (df['sp500_close'] > df['sp500_ma21']).astype(int)
df['sp500_above_ma50'] = (df['sp500_close'] > df['sp500_ma50']).astype(int)

# Distance from MA (%)
df['sp500_dist_ma21'] = (df['sp500_close'] / df['sp500_ma21'] - 1) * 100
df['sp500_dist_ma50'] = (df['sp500_close'] / df['sp500_ma50'] - 1) * 100

# Trend strength (MA crossovers)
df['sp500_ma7_above_ma21'] = (df['sp500_ma7'] > df['sp500_ma21']).astype(int)
df['sp500_ma21_above_ma50'] = (df['sp500_ma21'] > df['sp500_ma50']).astype(int)

# Volatility
df['sp500_volatility_14'] = df['sp500_return'].rolling(14).std() * np.sqrt(365) * 100

# Momentum multi-period
df['sp500_momentum_7'] = df['sp500_close'].pct_change(7) * 100
df['sp500_momentum_14'] = df['sp500_close'].pct_change(14) * 100
df['sp500_momentum_21'] = df['sp500_close'].pct_change(21) * 100

# RSI (Relative Strength Index)
def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

df['sp500_rsi'] = calculate_rsi(df['sp500_close'], 14)

print("✅ Features S&P 500 créées:")
features = [
    'sp500_ma7', 'sp500_ma14', 'sp500_ma21', 'sp500_ma50',
    'sp500_above_ma7', 'sp500_above_ma21', 'sp500_above_ma50',
    'sp500_dist_ma21', 'sp500_dist_ma50',
    'sp500_ma7_above_ma21', 'sp500_ma21_above_ma50',
    'sp500_volatility_14',
    'sp500_momentum_7', 'sp500_momentum_14', 'sp500_momentum_21',
    'sp500_rsi'
]
for feat in features:
    print(f"   • {feat}")
print()

# Sauvegarder dataset enrichi
df.to_csv('outputs/data_with_sp500_features.csv', index=False)
print("💾 Dataset avec features S&P 500 sauvegardé:")
print("   • outputs/data_with_sp500_features.csv")
print()

# Analyse des features les plus corrélées avec BTC returns
print("="*100)
print("🔍 Features S&P 500 Corrélées avec BTC Returns")
print("="*100)
print()

# Corrélation de chaque feature avec BTC future returns (7 jours)
btc_future_7d = df['close'].pct_change(7).shift(-7)

feature_corrs = []
for feat in features:
    if feat in df.columns:
        corr = df[feat].corr(btc_future_7d)
        feature_corrs.append({
            'feature': feat,
            'correlation': corr
        })

df_feat_corr = pd.DataFrame(feature_corrs).sort_values('correlation', ascending=False, key=abs)

print("Corrélation features S&P 500 avec BTC returns (7 jours forward):")
print(df_feat_corr.to_string(index=False))
print()

top_feature = df_feat_corr.iloc[-1]  # Last (highest abs correlation)
print(f"🥇 Feature S&P 500 la plus corrélée avec BTC future:")
print(f"   • {top_feature['feature']}")
print(f"   • Corrélation: {top_feature['correlation']:.4f}")
print()

df_feat_corr.to_csv('outputs/sp500_features_correlation_btc.csv', index=False)

# Summary
print("="*100)
print("📊 RÉSUMÉ DÉCOUVERTES S&P 500")
print("="*100)
print()

print(f"1️⃣ Performance globale:")
print(f"   • S&P 500: {df['sp500_cumret'].iloc[-1]:.2f}x")
print(f"   • BTC: {df['btc_cumret'].iloc[-1]:.2f}x")
print(f"   • BTC/S&P ratio: {df['btc_cumret'].iloc[-1] / df['sp500_cumret'].iloc[-1]:.2f}x")
print()

print(f"2️⃣ Meilleur lag (S&P 500 en avance):")
print(f"   • {int(best_lag['lag'])} jours")
print(f"   • Corrélation: {best_lag['correlation']:.4f}")
print()

print(f"3️⃣ Meilleur forward period (prédictif):")
print(f"   • {int(best_forward['forward_days'])} jours")
print(f"   • Corrélation: {best_forward['correlation']:.4f}")
print()

print(f"4️⃣ Feature S&P 500 la plus prédictive:")
print(f"   • {top_feature['feature']}")
print(f"   • Corrélation: {top_feature['correlation']:.4f}")
print()

print("✅ Prêt pour intégrer S&P 500 dans ML et stratégies!")
