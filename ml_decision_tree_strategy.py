#!/usr/bin/env python3
"""
🤖 MACHINE LEARNING APPROACH: Decision Tree pour Stratégie Optimale

Approche Hedge Fund Moderne:
1. Feature Engineering (FNG + Rainbow + dérivés)
2. Calcul allocation optimale rétrospective (hindsight)
3. Train Decision Tree pour apprendre les règles
4. Walk-Forward Validation
5. Backtest avec fees réalistes

C'est comme ça qu'un quant fund ferait!
"""
import pandas as pd
import numpy as np
from sklearn.tree import DecisionTreeRegressor, export_text
from sklearn.ensemble import RandomForestRegressor
from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.strategy import calculate_rainbow_position
from src.fngbt.backtest_realistic_fees import run_backtest_realistic_fees
import warnings
warnings.filterwarnings('ignore')

def create_features(df):
    """
    Feature Engineering: Créer features riches à partir de FNG et Rainbow
    """
    d = df.copy()
    d = calculate_rainbow_position(d)

    # FNG Features
    d['fng_ma7'] = d['fng'].rolling(7, min_periods=1).mean()
    d['fng_ma14'] = d['fng'].rolling(14, min_periods=1).mean()
    d['fng_ma21'] = d['fng'].rolling(21, min_periods=1).mean()
    d['fng_velocity_7'] = d['fng'].diff(7).fillna(0)
    d['fng_velocity_14'] = d['fng'].diff(14).fillna(0)
    d['fng_above_ma'] = (d['fng'] > d['fng_ma14']).astype(int)

    # Rainbow Features
    d['rainbow_ma7'] = d['rainbow_position'].rolling(7, min_periods=1).mean()
    d['rainbow_ma14'] = d['rainbow_position'].rolling(14, min_periods=1).mean()
    d['rainbow_ma21'] = d['rainbow_position'].rolling(21, min_periods=1).mean()
    d['rainbow_velocity_7'] = d['rainbow_position'].diff(7).fillna(0)
    d['rainbow_velocity_14'] = d['rainbow_position'].diff(14).fillna(0)
    d['rainbow_above_ma'] = (d['rainbow_position'] > d['rainbow_ma14']).astype(int)

    # Cross Features (Interactions)
    d['fng_x_rainbow'] = d['fng'] * d['rainbow_position']
    d['fng_rainbow_concordance'] = ((d['fng_above_ma'] == d['rainbow_above_ma'])).astype(int)

    # Volatility
    d['price_volatility_14'] = d['close'].pct_change().rolling(14, min_periods=1).std()

    return d

def calculate_optimal_allocation_hindsight(df, lookforward_days=30):
    """
    Calcul allocation OPTIMALE avec hindsight (rétrospectif)

    Pour chaque jour, on regarde les N prochains jours et on calcule:
    - Si prix monte beaucoup → optimal était 100%
    - Si prix baisse beaucoup → optimal était 50-70%
    - Basé sur Sharpe futur
    """
    d = df.copy()
    d['future_return'] = d['close'].pct_change(lookforward_days).shift(-lookforward_days)
    d['future_volatility'] = d['close'].pct_change().rolling(lookforward_days).std().shift(-lookforward_days)

    # Allocation optimale basée sur return/risk futur
    # Si Sharpe futur élevé → 100%
    # Si Sharpe futur faible ou négatif → 70-90%

    optimal_alloc = []
    for i in range(len(d)):
        fut_ret = d['future_return'].iloc[i]
        fut_vol = d['future_volatility'].iloc[i]

        if pd.isna(fut_ret) or pd.isna(fut_vol) or fut_vol == 0:
            optimal_alloc.append(95)  # Défaut
        else:
            sharpe_future = fut_ret / (fut_vol + 1e-6)

            # Mapping Sharpe → Allocation
            if sharpe_future > 2.0:
                alloc = 100  # Excellent Sharpe → Full
            elif sharpe_future > 1.0:
                alloc = 98
            elif sharpe_future > 0.5:
                alloc = 95
            elif sharpe_future > 0:
                alloc = 92
            elif sharpe_future > -0.5:
                alloc = 88
            elif sharpe_future > -1.0:
                alloc = 85
            else:
                alloc = 80  # Très mauvais → Réduire fort

            optimal_alloc.append(alloc)

    d['optimal_allocation'] = optimal_alloc
    return d

def train_test_split_temporal(df, train_end_date, test_start_date, test_end_date):
    """
    Split temporel (pas de shuffle!)
    """
    train = df[df['date'] < train_end_date].copy()
    test = df[(df['date'] >= test_start_date) & (df['date'] <= test_end_date)].copy()
    return train, test

print("="*100)
print("🤖 MACHINE LEARNING APPROACH: Decision Tree pour Allocation Optimale")
print("="*100)
print()

# Load data
print("Chargement données...")
fng = load_fng_alt()
btc = load_btc_prices()
df = merge_daily(fng, btc)
print(f"✅ {len(df)} jours (2018-2025)\n")

# Feature engineering
print("🔬 Feature Engineering...")
df = create_features(df)
print("✅ Features créés\n")

# Calcul allocation optimale hindsight
print("🎯 Calcul allocation optimale rétrospective...")
df = calculate_optimal_allocation_hindsight(df, lookforward_days=30)
print("✅ Optimal allocation calculée\n")

# Features pour ML
feature_cols = [
    'fng', 'fng_ma7', 'fng_ma14', 'fng_ma21',
    'fng_velocity_7', 'fng_velocity_14', 'fng_above_ma',
    'rainbow_position', 'rainbow_ma7', 'rainbow_ma14', 'rainbow_ma21',
    'rainbow_velocity_7', 'rainbow_velocity_14', 'rainbow_above_ma',
    'fng_x_rainbow', 'fng_rainbow_concordance',
    'price_volatility_14'
]

print(f"📊 Features utilisés ({len(feature_cols)}):")
for f in feature_cols:
    print(f"   • {f}")
print()

# Walk-Forward Validation
print("="*100)
print("🚶 WALK-FORWARD VALIDATION")
print("="*100)
print()

walk_forward_windows = [
    {
        'name': 'Window 1',
        'train_end': '2021-12-31',
        'test_start': '2022-01-01',
        'test_end': '2022-12-31'
    },
    {
        'name': 'Window 2',
        'train_end': '2022-12-31',
        'test_start': '2023-01-01',
        'test_end': '2023-12-31'
    },
    {
        'name': 'Window 3',
        'train_end': '2023-12-31',
        'test_start': '2024-01-01',
        'test_end': '2025-11-29'
    }
]

results_wf = []

for window in walk_forward_windows:
    print(f"\n{'='*100}")
    print(f"📅 {window['name']}: Train jusqu'à {window['train_end']}, Test {window['test_start']} → {window['test_end']}")
    print(f"{'='*100}\n")

    # Split
    train_df, test_df = train_test_split_temporal(
        df, window['train_end'], window['test_start'], window['test_end']
    )

    print(f"   Train: {len(train_df)} jours, Test: {len(test_df)} jours")

    # Préparer X, y
    X_train = train_df[feature_cols].fillna(0)
    y_train = train_df['optimal_allocation']

    X_test = test_df[feature_cols].fillna(0)

    # Train Decision Tree
    print(f"   🌳 Training Decision Tree...")
    dt_model = DecisionTreeRegressor(
        max_depth=6,  # Pas trop profond (éviter overfitting)
        min_samples_split=50,
        min_samples_leaf=20,
        random_state=42
    )
    dt_model.fit(X_train, y_train)

    # Predict sur test
    test_df_copy = test_df.copy()
    test_df_copy['pos'] = dt_model.predict(X_test)
    test_df_copy['pos'] = test_df_copy['pos'].clip(70, 100)  # Limiter 70-100%

    # Backtest avec fees réalistes
    result = run_backtest_realistic_fees(test_df_copy, initial_capital=100.0, fee_rate=0.001)
    metrics = result['metrics']

    bh_equity = result['df']['bh_equity'].iloc[-1]
    ratio = metrics['EquityFinal'] / bh_equity

    print(f"   📈 Test Results:")
    print(f"      Equity: {metrics['EquityFinal']:.2f}x")
    print(f"      Ratio vs B&H: {ratio:.4f}x ({(ratio-1)*100:+.2f}%)")
    print(f"      CAGR: {metrics['CAGR']*100:.2f}%")
    print(f"      Sharpe: {metrics['Sharpe']:.2f}")
    print(f"      Trades: {metrics['trades']}")
    print(f"      Fees: {metrics['total_fees_paid']:.2f} EUR")

    results_wf.append({
        'window': window['name'],
        'ratio': ratio,
        'equity': metrics['EquityFinal'],
        'trades': metrics['trades'],
        'fees': metrics['total_fees_paid'],
        'sharpe': metrics['Sharpe']
    })

# Résumé Walk-Forward
print(f"\n{'='*100}")
print("📊 RÉSUMÉ WALK-FORWARD VALIDATION")
print(f"{'='*100}\n")

df_wf = pd.DataFrame(results_wf)
print(df_wf.to_string(index=False))

avg_ratio = df_wf['ratio'].mean()
print(f"\n   📊 Ratio moyen OOS: {avg_ratio:.4f}x ({(avg_ratio-1)*100:+.2f}%)")

if avg_ratio > 1.0:
    print(f"   ✅ Stratégie ML BAT B&H en moyenne OOS!")
else:
    print(f"   ⚠️  Stratégie ML ne bat pas B&H en moyenne OOS")

# Train sur TOUTES les données pour modèle final
print(f"\n{'='*100}")
print("🎓 TRAINING MODÈLE FINAL (toutes données)")
print(f"{'='*100}\n")

X_all = df[feature_cols].fillna(0)
y_all = df['optimal_allocation']

# Decision Tree Final
print("🌳 Decision Tree...")
dt_final = DecisionTreeRegressor(
    max_depth=6,
    min_samples_split=50,
    min_samples_leaf=20,
    random_state=42
)
dt_final.fit(X_all, y_all)

# Random Forest (ensemble pour comparaison)
print("🌲 Random Forest (ensemble)...")
rf_final = RandomForestRegressor(
    n_estimators=50,
    max_depth=6,
    min_samples_split=50,
    min_samples_leaf=20,
    random_state=42,
    n_jobs=-1
)
rf_final.fit(X_all, y_all)

# Backtest full period
print(f"\n{'='*100}")
print("📊 BACKTEST PÉRIODE COMPLÈTE (2018-2025)")
print(f"{'='*100}\n")

# Decision Tree
df_dt = df.copy()
df_dt['pos'] = dt_final.predict(X_all)
df_dt['pos'] = df_dt['pos'].clip(70, 100)

result_dt = run_backtest_realistic_fees(df_dt, initial_capital=100.0, fee_rate=0.001)
metrics_dt = result_dt['metrics']
bh_equity_dt = result_dt['df']['bh_equity'].iloc[-1]
ratio_dt = metrics_dt['EquityFinal'] / bh_equity_dt

print("🌳 Decision Tree:")
print(f"   Equity: {metrics_dt['EquityFinal']:.2f}x")
print(f"   Ratio vs B&H: {ratio_dt:.4f}x ({(ratio_dt-1)*100:+.2f}%)")
print(f"   CAGR: {metrics_dt['CAGR']*100:.2f}%")
print(f"   Sharpe: {metrics_dt['Sharpe']:.2f}")
print(f"   Trades: {metrics_dt['trades']}")
print(f"   Fees: {metrics_dt['total_fees_paid']:.2f} EUR")
print()

# Random Forest
df_rf = df.copy()
df_rf['pos'] = rf_final.predict(X_all)
df_rf['pos'] = df_rf['pos'].clip(70, 100)

result_rf = run_backtest_realistic_fees(df_rf, initial_capital=100.0, fee_rate=0.001)
metrics_rf = result_rf['metrics']
ratio_rf = metrics_rf['EquityFinal'] / bh_equity_dt

print("🌲 Random Forest:")
print(f"   Equity: {metrics_rf['EquityFinal']:.2f}x")
print(f"   Ratio vs B&H: {ratio_rf:.4f}x ({(ratio_rf-1)*100:+.2f}%)")
print(f"   CAGR: {metrics_rf['CAGR']*100:.2f}%")
print(f"   Sharpe: {metrics_rf['Sharpe']:.2f}")
print(f"   Trades: {metrics_rf['trades']}")
print(f"   Fees: {metrics_rf['total_fees_paid']:.2f} EUR")
print()

# Feature Importance
print(f"{'='*100}")
print("🔍 FEATURE IMPORTANCE (Random Forest)")
print(f"{'='*100}\n")

feature_importance = pd.DataFrame({
    'feature': feature_cols,
    'importance': rf_final.feature_importances_
}).sort_values('importance', ascending=False)

print(feature_importance.to_string(index=False))

# Afficher les règles du Decision Tree
print(f"\n{'='*100}")
print("📜 RÈGLES APPRISES PAR LE DECISION TREE")
print(f"{'='*100}\n")

tree_rules = export_text(dt_final, feature_names=feature_cols, max_depth=3)
print(tree_rules[:1000])  # Premières lignes
print("\n... (règles complètes dans outputs/)")

# Sauvegarder
result_dt['df'].to_csv('outputs/ml_decision_tree_strategy_details.csv', index=False)
feature_importance.to_csv('outputs/ml_feature_importance.csv', index=False)

with open('outputs/ml_decision_tree_rules.txt', 'w') as f:
    f.write(tree_rules)

print(f"\n💾 Résultats sauvegardés:")
print(f"   • outputs/ml_decision_tree_strategy_details.csv")
print(f"   • outputs/ml_feature_importance.csv")
print(f"   • outputs/ml_decision_tree_rules.txt")

print(f"\n✨ Analyse ML terminée!")

# Comparaison finale
print(f"\n{'='*100}")
print("🏆 COMPARAISON FINALE: ML vs Meilleures Stratégies Manuelles")
print(f"{'='*100}\n")

comparison = pd.DataFrame([
    {'Strategy': 'FNG+Rainbow Hybrid (manuel)', 'Ratio': 1.18183, 'Trades': 2165, 'Fees': 3.64},
    {'Strategy': 'Rainbow Bands (manuel)', 'Ratio': 1.15529, 'Trades': 658, 'Fees': 0.65},
    {'Strategy': 'Decision Tree (ML)', 'Ratio': ratio_dt, 'Trades': metrics_dt['trades'], 'Fees': metrics_dt['total_fees_paid']},
    {'Strategy': 'Random Forest (ML)', 'Ratio': ratio_rf, 'Trades': metrics_rf['trades'], 'Fees': metrics_rf['total_fees_paid']},
])

print(comparison.to_string(index=False))

best_strategy = comparison.loc[comparison['Ratio'].idxmax()]
print(f"\n🥇 GAGNANTE: {best_strategy['Strategy']}")
print(f"   Ratio: {best_strategy['Ratio']:.4f}x")
print(f"   Trades: {int(best_strategy['Trades'])}")
print(f"   Fees: {best_strategy['Fees']:.2f} EUR")
