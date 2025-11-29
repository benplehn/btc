#!/usr/bin/env python3
"""
Test: Allocation avec MINIMUM 50% (jamais sortir complètement)

Hypothèse: En restant toujours investi à minimum 50%, on capture plus de gains
"""
import pandas as pd
import numpy as np
from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.strategy import calculate_rainbow_position
from src.fngbt.backtest import run_backtest

fng = load_fng_alt()
btc = load_btc_prices()
df = merge_daily(fng, btc)

# Baseline
bh = df.copy()
bh['pos'] = 100.0
bh['trade'] = 0
bh_result = run_backtest(bh, fees_bps=0.0)
bh_equity = bh_result['metrics']['EquityFinal']

print("="*100)
print("🎯 TEST: Allocation Minimum 50% (Jamais Sortir Complètement)")
print("="*100)
print(f"\n📊 Buy & Hold: {bh_equity:.2f}x\n")

# Test différents minimums
min_allocs = [0, 20, 30, 40, 50, 60, 70, 80]
results = []

for min_alloc in min_allocs:
    max_alloc = 100
    buy_thresh = 0.3
    sell_thresh = 0.7

    d = df.copy()
    d = calculate_rainbow_position(d)

    rainbow_pos = d['rainbow_position'].values

    # Allocation: min_alloc à max_alloc
    allocation = np.where(
        rainbow_pos <= buy_thresh,
        max_alloc,
        np.where(
            rainbow_pos >= sell_thresh,
            min_alloc,
            max_alloc - (max_alloc - min_alloc) * (rainbow_pos - buy_thresh) / (sell_thresh - buy_thresh)
        )
    )

    d['pos'] = allocation
    d['trade'] = (d['pos'].diff().abs() > 5).astype(int)

    result = run_backtest(d, fees_bps=10.0)
    metrics = result['metrics']

    ratio = metrics['EquityFinal'] / bh_equity

    results.append({
        'min_alloc': min_alloc,
        'equity': metrics['EquityFinal'],
        'ratio': ratio,
        'cagr': metrics['CAGR'],
        'max_dd': metrics['MaxDD'],
        'sharpe': metrics['Sharpe'],
        'trades': metrics['trades'],
        'avg_alloc': metrics['avg_allocation']
    })

    marker = "🎉" if ratio > 1.0 else "  "
    print(f"{marker} Min {min_alloc:3d}% → Equity {metrics['EquityFinal']:5.2f}x | Ratio {ratio:5.3f}x | "
          f"CAGR {metrics['CAGR']*100:5.1f}% | Trades {metrics['trades']:4d} | Avg alloc {metrics['avg_allocation']:.1f}%")

print(f"\n{'='*100}")
print(f"🏆 MEILLEUR RÉSULTAT")
print(f"{'='*100}")

best = max(results, key=lambda x: x['ratio'])
print(f"\nAllocation minimum: {best['min_alloc']}%")
print(f"Equity: {best['equity']:.2f}x")
print(f"Ratio vs B&H: {best['ratio']:.3f}x")
print(f"CAGR: {best['cagr']*100:.1f}%")
print(f"Max DD: {best['max_dd']*100:.1f}%")
print(f"Sharpe: {best['sharpe']:.2f}")
print(f"Trades: {best['trades']}")
print(f"Allocation moyenne: {best['avg_alloc']:.1f}%")

if best['ratio'] > 1.0:
    print(f"\n🎉 VICTOIRE! Cette stratégie BAT le B&H de {best['ratio']:.3f}x!")
    print(f"\nClé du succès:")
    print(f"  • Ne JAMAIS sortir complètement (min {best['min_alloc']}%)")
    print(f"  • Capturer tous les bulls avec allocation partielle")
    print(f"  • Réduire seulement en zone très haute du Rainbow")
else:
    print(f"\n⚠️  Même avec min allocation, sous-performe: {best['ratio']:.3f}x")
    print(f"\n💡 Essayer:")
    print(f"  • Seuils différents (ex: 0.2-0.8 au lieu de 0.3-0.7)")
    print(f"  • Allocation asymétrique (plus agressif à l'achat)")

# Sauvegarder
df_results = pd.DataFrame(results)
df_results.to_csv('outputs/min_allocation_test.csv', index=False)
print(f"\n💾 Résultats sauvegardés: outputs/min_allocation_test.csv")
