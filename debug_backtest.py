#!/usr/bin/env python3
"""
Debug du backtest pour comprendre le bug
"""
import pandas as pd
import numpy as np
from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.backtest import run_backtest

# Load data
fng = load_fng_alt()
btc = load_btc_prices()
df = merge_daily(fng, btc)

print(f"Données: {len(df)} jours")
print(f"Prix début: ${df['close'].iloc[0]:.0f}")
print(f"Prix fin: ${df['close'].iloc[-1]:.0f}")
print(f"Return BTC: {df['close'].iloc[-1] / df['close'].iloc[0]:.2f}x")

# Test 1: 100% constant
print(f"\n{'='*80}")
print(f"TEST 1: 100% CONSTANT (doit = BTC return)")
print(f"{'='*80}")

d1 = df.copy()
d1['pos'] = 100.0
d1['trade'] = 0
r1 = run_backtest(d1, fees_bps=0.0)

print(f"Equity finale: {r1['metrics']['EquityFinal']:.2f}x")
print(f"Attendu: {df['close'].iloc[-1] / df['close'].iloc[0]:.2f}x")
print(f"✅ OK" if abs(r1['metrics']['EquityFinal'] - df['close'].iloc[-1] / df['close'].iloc[0]) < 0.01 else "❌ BUG")

# Test 2: 50% constant
print(f"\n{'='*80}")
print(f"TEST 2: 50% CONSTANT")
print(f"{'='*80}")

d2 = df.copy()
d2['pos'] = 50.0
d2['trade'] = 0
r2 = run_backtest(d2, fees_bps=0.0)

btc_return = df['close'].iloc[-1] / df['close'].iloc[0]

# Calcul manuel attendu pour 50%
# Méthode 1: Arithmetic (simple)
expected_simple = 1 + 0.5 * (btc_return - 1)

# Méthode 2: Geometric (compounding correct)
# Si chaque jour return = r, alors (1+r)^n = btc_return
# Avec 50%, chaque jour: (1 + 0.5*r) compoundé
# En log: sum(log(1 + 0.5*r_i)) = sum(0.5 * log(1 + r_i))

# Calculons manuellement
manual_equity = 1.0
for i in range(1, len(d2)):
    daily_ret = (d2['close'].iloc[i] - d2['close'].iloc[i-1]) / d2['close'].iloc[i-1]
    strategy_ret = 0.5 * daily_ret
    manual_equity *= (1 + strategy_ret)

print(f"BTC return: {btc_return:.2f}x")
print(f"Attendu (arithmetic): {expected_simple:.2f}x")
print(f"Attendu (manual geometric): {manual_equity:.2f}x")
print(f"Backtest donne: {r2['metrics']['EquityFinal']:.2f}x")

if abs(r2['metrics']['EquityFinal'] - manual_equity) < 0.01:
    print(f"✅ Backtest correct")
else:
    print(f"❌ BUG DÉTECTÉ!")
    print(f"   Différence: {r2['metrics']['EquityFinal'] - manual_equity:.2f}x")

# Debug détaillé - regarder les premières lignes
print(f"\n{'='*80}")
print(f"DEBUG: Premières 10 lignes du backtest 50%")
print(f"{'='*80}")

print(d2[['date', 'close', 'ret', 'pos', 'strategy_ret', 'equity']].head(10).to_string())

# Vérifier turnover
print(f"\n{'='*80}")
print(f"TURNOVER: 50% constant ne devrait avoir AUCUN turnover après jour 1")
print(f"{'='*80}")

print(f"Turnover total: {r2['metrics']['turnover_total']:.4f}")
print(f"Attendu: ~0.50 (juste le jour 1)")
print(f"Trades comptés: {r2['metrics']['trades']}")

# Test 3: Allocation qui change
print(f"\n{'='*80}")
print(f"TEST 3: ALLOCATION VARIABLE (100% -> 50% -> 100%)")
print(f"{'='*80}")

d3 = df.copy()
d3['pos'] = 100.0
mid = len(d3) // 2
d3.loc[d3.index[mid:mid+365], 'pos'] = 50.0
d3['trade'] = (d3['pos'].diff().abs() > 1).astype(int)

r3 = run_backtest(d3, fees_bps=0.0)

print(f"Equity finale: {r3['metrics']['EquityFinal']:.2f}x")
print(f"Trades: {r3['metrics']['trades']}")
print(f"Turnover total: {r3['metrics']['turnover_total']:.2f}")

# Calcul manuel
manual3 = 1.0
for i in range(1, len(d3)):
    weight = d3['pos'].iloc[i] / 100.0
    daily_ret = (d3['close'].iloc[i] - d3['close'].iloc[i-1]) / d3['close'].iloc[i-1]
    strategy_ret = weight * daily_ret
    manual3 *= (1 + strategy_ret)

print(f"Manuel: {manual3:.2f}x")
print(f"Match: {'✅' if abs(r3['metrics']['EquityFinal'] - manual3) < 0.01 else '❌'}")
