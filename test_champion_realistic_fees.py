#!/usr/bin/env python3
"""
Test de la STRATÉGIE CHAMPIONNE avec FEES RÉALISTES

Nouveau système de fees:
- Capital initial: 100 EUR
- Fees: 0.1% sur CHAQUE achat et vente
- Tracking réel de cash et BTC

Stratégie championne:
- FNG Vélocité: window=7, threshold=8, alloc=94%
- Rainbow Accélération: window=14, threshold=0.02, alloc=96%
"""
import pandas as pd
import numpy as np
from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.strategy import calculate_rainbow_position
from src.fngbt.backtest_realistic_fees import run_backtest_realistic_fees

def champion_strategy(df: pd.DataFrame,
                      fng_vel_window=7, fng_vel_thresh=8, fng_alloc=94,
                      rainbow_accel_window=14, rainbow_accel_thresh=0.02, rainbow_alloc=96) -> pd.DataFrame:
    """
    Stratégie championne: FNG Vélocité + Rainbow Accélération
    """
    d = df.copy()
    d = calculate_rainbow_position(d)

    # FNG Vélocité
    d['fng_velocity'] = d['fng'].diff(fng_vel_window).abs()
    fng_volatile = d['fng_velocity'] > fng_vel_thresh

    # Rainbow Accélération
    d['rainbow_velocity'] = d['rainbow_position'].diff(rainbow_accel_window)
    d['rainbow_acceleration'] = d['rainbow_velocity'].diff(rainbow_accel_window).abs()
    rainbow_high_accel = d['rainbow_acceleration'] > rainbow_accel_thresh

    # Allocation
    allocation = np.ones(len(d)) * 100  # Défaut 100%

    # Un signal
    either_signal = fng_volatile | rainbow_high_accel
    allocation[either_signal] = max(fng_alloc, rainbow_alloc)

    # Deux signaux
    both_signals = fng_volatile & rainbow_high_accel
    allocation[both_signals] = min(fng_alloc, rainbow_alloc) - 2

    d['pos'] = allocation

    return d

# Load data
print("Chargement des données...")
fng = load_fng_alt()
btc = load_btc_prices()
df = merge_daily(fng, btc)
print(f"✅ {len(df)} jours\n")

print("="*100)
print("🏆 STRATÉGIE CHAMPIONNE avec FEES RÉALISTES (0.1% par trade)")
print("="*100)
print()

# Générer signaux
signals = champion_strategy(df)

# Backtest avec fees réalistes
print("📊 Running backtest avec fees réalistes (capital initial: 100 EUR)...\n")
result = run_backtest_realistic_fees(signals, initial_capital=100.0, fee_rate=0.001)

metrics = result['metrics']
df_result = result['df']

# Affichage résultats
print("="*100)
print("📈 RÉSULTATS")
print("="*100)
print()

print("💰 Capital et Performance:")
print(f"   • Capital initial: 100.00 EUR")
print(f"   • Capital final: {metrics['final_portfolio']:.2f} EUR")
print(f"   • Equity multiple: {metrics['EquityFinal']:.4f}x")
print()

print("🎯 Comparaison vs Buy & Hold:")
bh_final = df_result['bh_equity'].iloc[-1]
print(f"   • Buy & Hold equity: {bh_final:.4f}x")
print(f"   • Stratégie equity: {metrics['EquityFinal']:.4f}x")
ratio = metrics['EquityFinal'] / bh_final
print(f"   • Ratio: {ratio:.5f}x")
print(f"   • Amélioration: {(ratio - 1.0) * 100:+.2f}%")
print()

if ratio > 1.0:
    print(f"   ✅ VICTOIRE! Stratégie bat B&H de {(ratio - 1.0) * 100:.2f}%")
else:
    print(f"   ⚠️  Stratégie sous-performe B&H de {(1.0 - ratio) * 100:.2f}%")
print()

print("📊 Métriques de Performance:")
print(f"   • CAGR: {metrics['CAGR']*100:.2f}%")
print(f"   • Sharpe Ratio: {metrics['Sharpe']:.2f}")
print(f"   • Max Drawdown: {metrics['MaxDD']*100:.1f}%")
print()

print("💸 Frais et Trading:")
print(f"   • Nombre de trades: {metrics['trades']}")
print(f"   • Frais totaux payés: {metrics['total_fees_paid']:.2f} EUR")
print(f"   • Frais en % du capital initial: {metrics['total_fees_paid']/100*100:.2f}%")
print(f"   • Frais moyens par trade: {metrics['total_fees_paid']/metrics['trades']:.4f} EUR")
print()

print("🔄 Allocation:")
print(f"   • Allocation BTC moyenne: {metrics['avg_allocation']:.2f}%")
print(f"   • Cash final: {metrics['final_cash']:.2f} EUR")
print(f"   • BTC final: {metrics['final_btc']:.6f} BTC")
print(f"   • Valeur BTC finale: {df_result['btc_value'].iloc[-1]:.2f} EUR")
print()

# Comparaison avec ancien système de fees
print("="*100)
print("📊 COMPARAISON: Fees Réalistes vs Ancien Système Turnover")
print("="*100)
print()

from src.fngbt.backtest import run_backtest

# Re-run avec ancien système
result_old = run_backtest(signals, fees_bps=10.0)
metrics_old = result_old['metrics']
bh_equity_old = result_old['df']['bh_equity'].iloc[-1]
ratio_old = metrics_old['EquityFinal'] / bh_equity_old

print("Ancien système (turnover-based, 10 bps):")
print(f"   • Equity: {metrics_old['EquityFinal']:.4f}x")
print(f"   • Ratio vs B&H: {ratio_old:.5f}x")
print(f"   • Amélioration: {(ratio_old - 1.0) * 100:+.2f}%")
print()

print("Nouveau système (fees réalistes, 0.1% par trade):")
print(f"   • Equity: {metrics['EquityFinal']:.4f}x")
print(f"   • Ratio vs B&H: {ratio:.5f}x")
print(f"   • Amélioration: {(ratio - 1.0) * 100:+.2f}%")
print()

print("Différence:")
diff_equity = metrics['EquityFinal'] - metrics_old['EquityFinal']
diff_ratio = ratio - ratio_old
print(f"   • Différence equity: {diff_equity:+.4f}x ({diff_equity/metrics_old['EquityFinal']*100:+.2f}%)")
print(f"   • Différence ratio: {diff_ratio:+.5f}x")
print()

if abs(diff_ratio) < 0.05:
    print("   ✅ Résultats similaires - stratégie robuste aux deux systèmes de fees!")
elif diff_ratio > 0:
    print("   🎉 Meilleurs résultats avec fees réalistes!")
else:
    print("   ⚠️  Moins bons résultats avec fees réalistes (plus de trades coûte plus cher)")
print()

# Sauvegarder
df_result.to_csv('outputs/champion_realistic_fees_details.csv', index=False)
print("💾 Résultats sauvegardés: outputs/champion_realistic_fees_details.csv")

print()
print("✨ Analyse terminée!")
