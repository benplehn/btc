#!/usr/bin/env python3
"""
🔮 TIMING PARFAIT: Quelle est la LIMITE THÉORIQUE?

Si on pouvait prédire le futur et acheter à CHAQUE minimum local
et vendre à CHAQUE maximum local, combien on gagnerait?

Cela nous donne la BORNE SUPÉRIEURE de ce qui est possible.
"""
import pandas as pd
import numpy as np
from scipy.signal import argrelextrema
from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
import warnings
warnings.filterwarnings('ignore')

print("="*100)
print("🔮 TIMING PARFAIT: Limite Théorique de Performance")
print("="*100)
print()

# Load data
print("Chargement données...")
fng = load_fng_alt()
btc = load_btc_prices()
df = merge_daily(fng, btc)
print(f"✅ {len(df)} jours\n")

# Calculer Buy & Hold baseline
bh_ratio = df['close'].iloc[-1] / df['close'].iloc[0]
print(f"📊 Buy & Hold baseline:")
print(f"   Prix initial: {df['close'].iloc[0]:.2f} EUR")
print(f"   Prix final: {df['close'].iloc[-1]:.2f} EUR")
print(f"   Ratio: {bh_ratio:.2f}x")
print()

# ============================================================================
# MÉTHODE 1: Perfect Timing avec Détection de Peaks/Troughs
# ============================================================================

print("="*100)
print("🎯 MÉTHODE 1: Perfect Timing (Peaks & Troughs Detection)")
print("="*100)
print()

# Détecter minimums et maximums locaux
# order = combien de jours autour doivent être plus hauts/bas
for order in [5, 10, 21, 30]:
    print(f"\n--- Window = {order} jours ---")

    # Trouver minimums locaux (acheter)
    local_mins = argrelextrema(df['close'].values, np.less, order=order)[0]
    # Trouver maximums locaux (vendre)
    local_maxs = argrelextrema(df['close'].values, np.greater, order=order)[0]

    print(f"Minimums trouvés: {len(local_mins)}")
    print(f"Maximums trouvés: {len(local_maxs)}")

    # Stratégie: alterner achats (mins) et ventes (maxs)
    # On commence en cash (0% BTC)
    capital = 100.0
    btc_amount = 0.0
    in_position = False
    trades = 0

    # Combiner et trier tous les signaux
    signals = []
    for idx in local_mins:
        signals.append((idx, 'BUY', df['close'].iloc[idx]))
    for idx in local_maxs:
        signals.append((idx, 'SELL', df['close'].iloc[idx]))

    signals = sorted(signals, key=lambda x: x[0])

    # Exécuter les trades
    for idx, action, price in signals:
        if action == 'BUY' and not in_position:
            # Acheter tout avec le cash
            fee = capital * 0.001
            btc_amount = (capital - fee) / price
            capital = 0
            in_position = True
            trades += 1
        elif action == 'SELL' and in_position:
            # Vendre tout le BTC
            capital = btc_amount * price
            fee = capital * 0.001
            capital -= fee
            btc_amount = 0
            in_position = False
            trades += 1

    # Valeur finale
    if in_position:
        # Toujours en BTC, convertir en cash au prix final
        final_value = btc_amount * df['close'].iloc[-1]
    else:
        final_value = capital

    ratio_bh = final_value / (bh_ratio * 100)

    print(f"Valeur finale: {final_value:.2f} EUR")
    print(f"Ratio vs B&H: {ratio_bh:.2f}x")
    print(f"Trades: {trades}")

# ============================================================================
# MÉTHODE 2: Perfect Timing ABSOLU (Hindsight Complet)
# ============================================================================

print("\n" + "="*100)
print("🔮 MÉTHODE 2: Perfect Timing ABSOLU (Oracle)")
print("="*100)
print()

print("Stratégie: À chaque instant, être 100% BTC si prix va monter demain,")
print("           être 0% BTC (cash) si prix va baisser demain.\n")

# Calculer si demain monte ou descend
df['tomorrow_return'] = df['close'].pct_change().shift(-1)

# Allocation parfaite: 100% si monte, 0% si descend
df['perfect_allocation'] = np.where(df['tomorrow_return'] > 0, 100, 0)

# Simuler avec fees
capital = 100.0
btc_amount = 0.0
trades = 0
total_fees = 0

for i in range(len(df) - 1):  # -1 car pas de tomorrow pour dernier jour
    price = df['close'].iloc[i]
    target_alloc = df['perfect_allocation'].iloc[i] / 100.0

    current_value = capital + btc_amount * price
    current_alloc = (btc_amount * price) / current_value if current_value > 0 else 0

    # Rebalance si changement
    if abs(current_alloc - target_alloc) > 0.01:
        if target_alloc > current_alloc:  # Acheter BTC
            cash_to_invest = (target_alloc - current_alloc) * current_value
            cash_to_invest = min(cash_to_invest, capital)
            fee = cash_to_invest * 0.001
            btc_bought = (cash_to_invest - fee) / price
            btc_amount += btc_bought
            capital -= cash_to_invest
            total_fees += fee
            trades += 1
        else:  # Vendre BTC
            btc_to_sell = (current_alloc - target_alloc) * current_value / price
            btc_to_sell = min(btc_to_sell, btc_amount)
            proceeds = btc_to_sell * price
            fee = proceeds * 0.001
            capital += proceeds - fee
            btc_amount -= btc_to_sell
            total_fees += fee
            trades += 1

# Valeur finale
final_value = capital + btc_amount * df['close'].iloc[-1]
ratio_bh = final_value / (bh_ratio * 100)

print(f"📊 Résultats Perfect Timing Absolu:")
print(f"   Valeur finale: {final_value:.2f} EUR")
print(f"   Gain: +{final_value - 100:.2f} EUR")
print(f"   Ratio vs capital initial: {final_value/100:.2f}x")
print(f"   Ratio vs B&H: {ratio_bh:.2f}x")
print(f"   Trades: {trades}")
print(f"   Fees: {total_fees:.2f} EUR")
print()

# ============================================================================
# MÉTHODE 3: Perfect Swings (Swing Trading Parfait)
# ============================================================================

print("="*100)
print("🎯 MÉTHODE 3: Perfect Swing Trading")
print("="*100)
print()

print("Stratégie: Acheter aux creux significatifs (baisse >X%),")
print("           Vendre aux pics significatifs (hausse >Y%).\n")

for buy_threshold in [5, 10, 15, 20]:  # % de baisse pour acheter
    for sell_threshold in [5, 10, 15, 20]:  # % de hausse pour vendre

        # Calculer drawdown depuis ATH
        df['rolling_max'] = df['close'].expanding().max()
        df['drawdown'] = (df['close'] / df['rolling_max'] - 1) * 100

        # Calculer gain depuis dernier creux
        df['rolling_min'] = df['close'].expanding().min()
        df['gain_from_bottom'] = (df['close'] / df['rolling_min'] - 1) * 100

        capital = 100.0
        btc_amount = 0.0
        in_position = False
        trades = 0
        total_fees = 0

        for i in range(len(df)):
            price = df['close'].iloc[i]
            dd = df['drawdown'].iloc[i]
            gain = df['gain_from_bottom'].iloc[i]

            if not in_position and dd <= -buy_threshold:
                # Acheter (baisse significative)
                fee = capital * 0.001
                btc_amount = (capital - fee) / price
                capital = 0
                in_position = True
                trades += 1
                total_fees += fee
            elif in_position and gain >= sell_threshold:
                # Vendre (hausse significative)
                capital = btc_amount * price
                fee = capital * 0.001
                capital -= fee
                btc_amount = 0
                in_position = False
                trades += 1
                total_fees += fee

        # Valeur finale
        if in_position:
            final_value = btc_amount * df['close'].iloc[-1]
        else:
            final_value = capital

        ratio_bh = final_value / (bh_ratio * 100)

        # Afficher seulement si > 10x B&H
        if ratio_bh >= 10:
            print(f"Buy @ -{buy_threshold}%, Sell @ +{sell_threshold}%:")
            print(f"   Final: {final_value:.2f} EUR, Ratio: {ratio_bh:.2f}x, Trades: {trades}")

# ============================================================================
# COMPARAISON FINALE
# ============================================================================

print("\n" + "="*100)
print("📊 RÉSUMÉ: Quelle est la LIMITE THÉORIQUE?")
print("="*100)
print()

print(f"Buy & Hold (100 EUR):        {bh_ratio * 100:.2f} EUR ({bh_ratio:.2f}x)")
print(f"Perfect Timing Absolu:       {final_value:.2f} EUR ({ratio_bh:.2f}x vs B&H)")
print()

print("🎯 POUR BATTRE 18x B&H:")
print(f"   Il faudrait une equity finale de: {18 * bh_ratio * 100:.2f} EUR")
print(f"   Soit un ratio vs capital initial: {18 * bh_ratio:.2f}x")
print()

if ratio_bh >= 18:
    print(f"✅ Perfect timing ({ratio_bh:.0f}x) PEUT atteindre 18x B&H!")
    print(f"   Mais nécessite {trades} trades avec timing PARFAIT.")
else:
    print(f"❌ Même avec perfect timing ({ratio_bh:.0f}x), 18x B&H est IMPOSSIBLE!")
    print(f"   Maximum possible: {ratio_bh:.0f}x vs B&H")

print()
print("💡 CONCLUSION:")
print("   18x B&H signifie faire " + f"{18 * bh_ratio:.0f}x le capital initial.")
print("   Avec fees réalistes, c'est EXTRÊMEMENT difficile même avec timing parfait.")
print()

# ============================================================================
# STRATÉGIE ULTRA-AGRESSIVE RÉALISTE
# ============================================================================

print("="*100)
print("🚀 STRATÉGIE ULTRA-AGRESSIVE (Sans Hindsight)")
print("="*100)
print()

print("Testons des stratégies très agressives mais SANS hindsight:\n")

from src.fngbt.strategy import calculate_rainbow_position
from src.fngbt.backtest_realistic_fees import run_backtest_realistic_fees

df = calculate_rainbow_position(df)

strategies = []

# 1. Full leverage sur FNG fear extrême
df_test = df.copy()
df_test['pos'] = np.where(df_test['fng'] < 20, 100,  # Fear extrême
                 np.where(df_test['fng'] < 40, 95,
                 np.where(df_test['fng'] < 60, 85, 70)))  # Greed
result = run_backtest_realistic_fees(df_test, initial_capital=100.0, fee_rate=0.001)
strategies.append({
    'name': 'FNG Ultra-Agressive (20/40/60)',
    'equity': result['metrics']['EquityFinal'],
    'ratio_bh': result['metrics']['EquityFinal'] / (bh_ratio * 100),
    'trades': result['metrics']['trades'],
    'fees': result['metrics']['total_fees_paid']
})

# 2. Rainbow ultra-agressive
df_test = df.copy()
df_test['pos'] = np.where(df_test['rainbow_position'] < 0.3, 100,  # Super cheap
                 np.where(df_test['rainbow_position'] < 0.5, 95,
                 np.where(df_test['rainbow_position'] < 0.7, 85, 70)))  # Expensive
result = run_backtest_realistic_fees(df_test, initial_capital=100.0, fee_rate=0.001)
strategies.append({
    'name': 'Rainbow Ultra-Agressive (0.3/0.5/0.7)',
    'equity': result['metrics']['EquityFinal'],
    'ratio_bh': result['metrics']['EquityFinal'] / (bh_ratio * 100),
    'trades': result['metrics']['trades'],
    'fees': result['metrics']['total_fees_paid']
})

# 3. Combo ultra-agressive
df_test = df.copy()
rainbow_score = (df_test['rainbow_position'] < 0.4).astype(int)
fng_score = (df_test['fng'] < 30).astype(int)
total_score = rainbow_score + fng_score
df_test['pos'] = np.where(total_score == 2, 100,  # Les 2 bullish
                 np.where(total_score == 1, 90, 75))  # 1 ou 0 bullish
result = run_backtest_realistic_fees(df_test, initial_capital=100.0, fee_rate=0.001)
strategies.append({
    'name': 'Combo Ultra-Agressive (Rainbow<0.4 + FNG<30)',
    'equity': result['metrics']['EquityFinal'],
    'ratio_bh': result['metrics']['EquityFinal'] / (bh_ratio * 100),
    'trades': result['metrics']['trades'],
    'fees': result['metrics']['total_fees_paid']
})

# 4. Momentum extreme
df_test = df.copy()
df_test['momentum'] = df_test['close'].pct_change(7)
df_test['pos'] = np.where(df_test['momentum'] < -0.15, 100,  # Baisse >15%
                 np.where(df_test['momentum'] < -0.05, 95,
                 np.where(df_test['momentum'] > 0.15, 80, 90)))  # Hausse >15%
result = run_backtest_realistic_fees(df_test, initial_capital=100.0, fee_rate=0.001)
strategies.append({
    'name': 'Momentum Contrarian (-15%/+15%)',
    'equity': result['metrics']['EquityFinal'],
    'ratio_bh': result['metrics']['EquityFinal'] / (bh_ratio * 100),
    'trades': result['metrics']['trades'],
    'fees': result['metrics']['total_fees_paid']
})

# Afficher résultats
df_strats = pd.DataFrame(strategies).sort_values('ratio_bh', ascending=False)
print("Stratégies ultra-agressives (SANS hindsight):\n")
print(df_strats.to_string(index=False))
print()

best = df_strats.iloc[0]
if best['ratio_bh'] >= 18:
    print(f"🎉 TROUVÉ! {best['name']} atteint {best['ratio_bh']:.1f}x vs B&H!")
else:
    print(f"⚠️  Meilleure stratégie: {best['name']}")
    print(f"   Ratio vs B&H: {best['ratio_bh']:.2f}x (objectif: 18x)")
    print(f"   Il manque encore {18 - best['ratio_bh']:.1f}x pour atteindre 18x!")

print("\n✨ Analyse terminée!")
