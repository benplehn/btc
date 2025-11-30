#!/usr/bin/env python3
"""
🤖 MACHINE LEARNING avec S&P 500

Reprise du ML Decision Tree mais AVEC S&P 500 inclus!

Features totales:
- FNG: raw, MAs, velocity, acceleration, z-score (7 features)
- Rainbow: position, MAs, velocity (5 features)
- S&P 500: MAs, momentum, trend, RSI, volatility (16 features)
- Cross-features: FNG × Rainbow, FNG × S&P, concordance (3 features)

Total: ~30 features

Objectif: Est-ce que S&P 500 améliore la performance ML?
"""
import pandas as pd
import numpy as np
from sklearn.tree import DecisionTreeRegressor, export_text
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from src.fngbt.backtest_realistic_fees import run_backtest_realistic_fees
from src.fngbt.strategy import calculate_rainbow_position
import warnings
warnings.filterwarnings('ignore')

print("="*100)
print("🤖 MACHINE LEARNING avec S&P 500")
print("="*100)
print()

# Load data with S&P 500 features
print("Chargement données avec features S&P 500...")
df = pd.read_csv('outputs/data_with_sp500_features.csv', parse_dates=['date'])
print(f"✅ {len(df)} jours de données\n")

# Calculate Rainbow position
df = calculate_rainbow_position(df)

# Feature Engineering (FNG + Rainbow + S&P 500)
print("="*100)
print("🔧 FEATURE ENGINEERING (FNG + Rainbow + S&P 500)")
print("="*100)
print()

# FNG features
df['fng_ma7'] = df['fng'].rolling(7).mean()
df['fng_ma14'] = df['fng'].rolling(14).mean()
df['fng_ma21'] = df['fng'].rolling(21).mean()
df['fng_velocity_7'] = df['fng'].diff(7)
df['fng_velocity_14'] = df['fng'].diff(14)
df['fng_acceleration_7'] = df['fng_velocity_7'].diff(7)
df['fng_above_ma'] = (df['fng'] > df['fng_ma21']).astype(int)
df['fng_zscore'] = (df['fng'] - df['fng'].rolling(30).mean()) / df['fng'].rolling(30).std()

# Rainbow features
df['rainbow_ma7'] = df['rainbow_position'].rolling(7).mean()
df['rainbow_ma14'] = df['rainbow_position'].rolling(14).mean()
df['rainbow_ma21'] = df['rainbow_position'].rolling(21).mean()
df['rainbow_velocity_7'] = df['rainbow_position'].diff(7)
df['rainbow_velocity_14'] = df['rainbow_position'].diff(14)
df['rainbow_above_ma'] = (df['rainbow_position'] > df['rainbow_ma21']).astype(int)

# S&P 500 features (already created in analyze_sp500_btc_correlation.py)
# sp500_ma7, sp500_ma14, sp500_ma21, sp500_ma50
# sp500_above_ma7, sp500_above_ma21, sp500_above_ma50
# sp500_dist_ma21, sp500_dist_ma50
# sp500_ma7_above_ma21, sp500_ma21_above_ma50
# sp500_volatility_14
# sp500_momentum_7, sp500_momentum_14, sp500_momentum_21
# sp500_rsi

# Cross-features
df['fng_x_rainbow'] = df['fng'] * df['rainbow_position']
df['fng_x_sp500_momentum'] = df['fng'] * df['sp500_momentum_14']
df['rainbow_x_sp500_trend'] = df['rainbow_position'] * df['sp500_ma7_above_ma21']

# Volatility BTC
df['price_volatility_14'] = df['close'].pct_change().rolling(14).std() * np.sqrt(365) * 100

# Define all features
feature_cols = [
    # FNG (8)
    'fng', 'fng_ma7', 'fng_ma14', 'fng_ma21',
    'fng_velocity_7', 'fng_velocity_14', 'fng_acceleration_7',
    'fng_above_ma',
    # Rainbow (6)
    'rainbow_position', 'rainbow_ma7', 'rainbow_ma14', 'rainbow_ma21',
    'rainbow_velocity_7', 'rainbow_velocity_14',
    # S&P 500 (16)
    'sp500_ma7', 'sp500_ma14', 'sp500_ma21', 'sp500_ma50',
    'sp500_above_ma7', 'sp500_above_ma21', 'sp500_above_ma50',
    'sp500_dist_ma21', 'sp500_dist_ma50',
    'sp500_ma7_above_ma21', 'sp500_ma21_above_ma50',
    'sp500_volatility_14',
    'sp500_momentum_7', 'sp500_momentum_14', 'sp500_momentum_21',
    'sp500_rsi',
    # Cross-features (4)
    'fng_x_rainbow', 'fng_x_sp500_momentum', 'rainbow_x_sp500_trend',
    'price_volatility_14'
]

print(f"Total features: {len(feature_cols)}")
print()

# Calculate optimal allocation (hindsight)
def calculate_optimal_allocation_hindsight(df, lookforward_days=30):
    """Calculate optimal allocation based on future returns"""
    d = df.copy()

    # Future return
    d['future_return'] = d['close'].pct_change(lookforward_days).shift(-lookforward_days)
    d['future_volatility'] = d['close'].pct_change().rolling(lookforward_days).std().shift(-lookforward_days)

    # Sharpe-like metric
    sharpe_future = d['future_return'] / (d['future_volatility'] + 1e-6)

    # Map Sharpe to allocation
    allocations = []
    for sharpe in sharpe_future:
        if pd.isna(sharpe):
            alloc = 98
        elif sharpe > 2.0:
            alloc = 100
        elif sharpe > 1.0:
            alloc = 98
        elif sharpe > 0.5:
            alloc = 95
        elif sharpe > 0:
            alloc = 90
        elif sharpe > -0.5:
            alloc = 85
        elif sharpe > -1.0:
            alloc = 80
        else:
            alloc = 75
        allocations.append(alloc)

    d['optimal_allocation'] = allocations
    return d

print("Calcul optimal allocation (hindsight - lookforward 30 jours)...")
df = calculate_optimal_allocation_hindsight(df, lookforward_days=30)
print("✅ Optimal allocation calculée\n")

# Remove NaN
df = df.dropna(subset=feature_cols + ['optimal_allocation'])
print(f"Données après dropna: {len(df)} jours\n")

# Walk-Forward Validation
print("="*100)
print("🚶 WALK-FORWARD VALIDATION avec S&P 500")
print("="*100)
print()

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
    print(f"\n{window['name']}")
    print("-" * 80)

    # Split data
    train = df[df['date'] <= window['train_end']].copy()
    test = df[(df['date'] >= window['test_start']) & (df['date'] <= window['test_end'])].copy()

    print(f"Train: {len(train)} jours, Test: {len(test)} jours")

    # Prepare features
    X_train = train[feature_cols].values
    y_train = train['optimal_allocation'].values
    X_test = test[feature_cols].values

    # Train Decision Tree
    dt = DecisionTreeRegressor(max_depth=5, min_samples_leaf=50, random_state=42)
    dt.fit(X_train, y_train)

    # Train Random Forest
    rf = RandomForestRegressor(n_estimators=50, max_depth=5, min_samples_leaf=50, random_state=42, n_jobs=-1)
    rf.fit(X_train, y_train)

    # Predict
    test['dt_allocation'] = np.clip(dt.predict(X_test), 75, 100)
    test['rf_allocation'] = np.clip(rf.predict(X_test), 75, 100)

    # Backtest Decision Tree
    test_dt = test.copy()
    test_dt['pos'] = test_dt['dt_allocation']
    result_dt = run_backtest_realistic_fees(test_dt, initial_capital=100.0, fee_rate=0.001)
    metrics_dt = result_dt['metrics']
    bh_equity = result_dt['df']['bh_equity'].iloc[-1]
    ratio_dt = metrics_dt['EquityFinal'] / bh_equity

    # Backtest Random Forest
    test_rf = test.copy()
    test_rf['pos'] = test_rf['rf_allocation']
    result_rf = run_backtest_realistic_fees(test_rf, initial_capital=100.0, fee_rate=0.001)
    metrics_rf = result_rf['metrics']
    ratio_rf = metrics_rf['EquityFinal'] / bh_equity

    print(f"Decision Tree: {ratio_dt:.4f}x ({(ratio_dt-1)*100:+.2f}%)")
    print(f"Random Forest: {ratio_rf:.4f}x ({(ratio_rf-1)*100:+.2f}%)")

    wf_results.append({
        'window': window['name'],
        'dt_ratio': ratio_dt,
        'rf_ratio': ratio_rf,
        'dt_trades': metrics_dt['trades'],
        'rf_trades': metrics_rf['trades']
    })

# Summary
print("\n" + "="*100)
print("📊 RÉSUMÉ WALK-FORWARD")
print("="*100)
print()

df_wf = pd.DataFrame(wf_results)
print(df_wf.to_string(index=False))
print()

dt_avg = df_wf['dt_ratio'].mean()
rf_avg = df_wf['rf_ratio'].mean()

print(f"Decision Tree OOS moyen: {dt_avg:.4f}x ({(dt_avg-1)*100:+.2f}%)")
print(f"Random Forest OOS moyen: {rf_avg:.4f}x ({(rf_avg-1)*100:+.2f}%)")
print()

# Feature Importance (Random Forest on full data)
print("="*100)
print("🔍 FEATURE IMPORTANCE avec S&P 500")
print("="*100)
print()

X_full = df[feature_cols].values
y_full = df['optimal_allocation'].values

rf_full = RandomForestRegressor(n_estimators=100, max_depth=5, min_samples_leaf=50, random_state=42, n_jobs=-1)
rf_full.fit(X_full, y_full)

importances = pd.DataFrame({
    'feature': feature_cols,
    'importance': rf_full.feature_importances_
}).sort_values('importance', ascending=False)

print("TOP 15 Features les plus importantes:")
print(importances.head(15).to_string(index=False))
print()

# Séparer par catégorie
sp500_importance = importances[importances['feature'].str.startswith('sp500')]['importance'].sum()
fng_importance = importances[importances['feature'].str.startswith('fng')]['importance'].sum()
rainbow_importance = importances[importances['feature'].str.startswith('rainbow')]['importance'].sum()
cross_importance = importances[importances['feature'].str.contains('_x_')]['importance'].sum()

print("Importance par catégorie:")
print(f"  • S&P 500: {sp500_importance*100:.1f}%")
print(f"  • FNG: {fng_importance*100:.1f}%")
print(f"  • Rainbow: {rainbow_importance*100:.1f}%")
print(f"  • Cross-features: {cross_importance*100:.1f}%")
print()

# Sauvegarder
importances.to_csv('outputs/ml_sp500_feature_importance.csv', index=False)
df_wf.to_csv('outputs/ml_sp500_walkforward_results.csv', index=False)

# Comparaison avec ML sans S&P 500
print("="*100)
print("⚖️  COMPARAISON: ML avec vs sans S&P 500")
print("="*100)
print()

comparison = pd.DataFrame([
    {
        'Model': 'ML SANS S&P 500 (Decision Tree)',
        'OOS Moyen': '1.005x',
        'Performance': '+0.5%'
    },
    {
        'Model': 'ML AVEC S&P 500 (Decision Tree)',
        'OOS Moyen': f'{dt_avg:.3f}x',
        'Performance': f'{(dt_avg-1)*100:+.2f}%'
    },
    {
        'Model': 'ML AVEC S&P 500 (Random Forest)',
        'OOS Moyen': f'{rf_avg:.3f}x',
        'Performance': f'{(rf_avg-1)*100:+.2f}%'
    }
])

print(comparison.to_string(index=False))
print()

if dt_avg > 1.005 or rf_avg > 1.005:
    improvement_dt = ((dt_avg - 1.005) / 1.005) * 100
    improvement_rf = ((rf_avg - 1.005) / 1.005) * 100
    print(f"✅ S&P 500 améliore la performance ML!")
    print(f"   • Decision Tree: +{improvement_dt:.1f}% vs ML sans S&P 500")
    print(f"   • Random Forest: +{improvement_rf:.1f}% vs ML sans S&P 500")
else:
    print(f"⚠️  S&P 500 n'améliore pas significativement le ML")
print()

print("💾 Résultats sauvegardés:")
print("   • outputs/ml_sp500_feature_importance.csv")
print("   • outputs/ml_sp500_walkforward_results.csv")
print()

print("✨ Analyse ML avec S&P 500 terminée!")
