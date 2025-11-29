#!/usr/bin/env python3
"""
COMBINAISON ULTIME: FNG Vélocité + Rainbow Accélération

On a trouvé:
- FNG Vélocité seule: 1.27852x
- Rainbow Accélération seule: 1.33407x
- FNG Vélocité + Rainbow Vélocité: 1.36158x (championne actuelle)

Testons: FNG Vélocité + Rainbow ACCÉLÉRATION (au lieu de vélocité)
Peut-être que l'accélération Rainbow capte mieux les tops?
"""
import pandas as pd
import numpy as np
from itertools import product
from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.strategy import calculate_rainbow_position
from src.fngbt.backtest import run_backtest

def fng_velocity_rainbow_acceleration(df,
                                       fng_vel_window, fng_vel_thresh, fng_alloc,
                                       rainbow_accel_window, rainbow_accel_thresh, rainbow_alloc,
                                       alloc_calm=100, alloc_very_volatile=92):
    """
    Combine FNG Vélocité + Rainbow Accélération

    Logique:
    - FNG vélocité = volatilité sentiment
    - Rainbow accélération = changement de la vitesse de valorisation
    - Double signal = très prudent
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
    allocation = np.ones(len(d)) * alloc_calm

    # Un signal
    either_signal = fng_volatile | rainbow_high_accel
    allocation[either_signal] = max(fng_alloc, rainbow_alloc)

    # Deux signaux
    both_signals = fng_volatile & rainbow_high_accel
    allocation[both_signals] = min(fng_alloc, rainbow_alloc) - 2

    d['pos'] = allocation
    d['trade'] = (d['pos'].diff().abs() > 0.5).astype(int)

    return d

# Load data
print("Chargement...")
fng = load_fng_alt()
btc = load_btc_prices()
df = merge_daily(fng, btc)
print(f"✅ {len(df)} jours\n")

# Baseline
bh = df.copy()
bh['pos'] = 100.0
bh['trade'] = 0
bh_result = run_backtest(bh, fees_bps=0.0)
bh_equity = bh_result['metrics']['EquityFinal']

print("="*100)
print("🚀 COMBINAISON: FNG Vélocité + Rainbow Accélération")
print("="*100)
print(f"\n📊 Buy & Hold: {bh_equity:.2f}x")
print(f"🏆 À battre: 1.36158x (FNG Vélocité + Rainbow Vélocité)\n")

results = []

# Grid search
fng_vel_windows = [5, 7, 10]
fng_vel_threshs = [8, 10, 12, 15]
fng_allocs = [94, 95, 96]

rainbow_accel_windows = [7, 10, 14]
rainbow_accel_threshs = [0.005, 0.01, 0.015, 0.02]
rainbow_allocs = [94, 95, 96]

print("🔍 Grid search en cours...\n")

count = 0
for params in product(fng_vel_windows, fng_vel_threshs, fng_allocs,
                      rainbow_accel_windows, rainbow_accel_threshs, rainbow_allocs):

    fng_w, fng_t, fng_a, rainbow_w, rainbow_t, rainbow_a = params

    signals = fng_velocity_rainbow_acceleration(
        df, fng_w, fng_t, fng_a,
        rainbow_w, rainbow_t, rainbow_a
    )
    result = run_backtest(signals, fees_bps=10.0)
    metrics = result['metrics']
    ratio = metrics['EquityFinal'] / bh_equity

    if ratio > 1.35:
        count += 1
        marker = "🚀" if ratio > 1.36158 else "🎉"
        config_str = f"FNG_Vel({fng_w},{fng_t},{fng_a}) + Rainbow_Accel({rainbow_w},{rainbow_t:.3f},{rainbow_a})"
        print(f"{marker} {config_str:<75} → {ratio:.5f}x | Trades {metrics['trades']:4d}")

        results.append({
            'fng_w': fng_w,
            'fng_t': fng_t,
            'fng_a': fng_a,
            'rainbow_w': rainbow_w,
            'rainbow_t': rainbow_t,
            'rainbow_a': rainbow_a,
            'ratio': ratio,
            'equity': metrics['EquityFinal'],
            'trades': metrics['trades'],
            'avg_alloc': metrics['avg_allocation']
        })

print(f"\n{count} configurations > 1.35x trouvées")

# MEILLEURE
print(f"\n{'='*100}")
print("🏆 MEILLEURE COMBINAISON")
print("="*100)

if results:
    df_results = pd.DataFrame(results)
    best = df_results.loc[df_results['ratio'].idxmax()]

    print(f"\nFNG Vélocité:")
    print(f"  Window: {best['fng_w']}, Threshold: {best['fng_t']}, Alloc: {best['fng_a']}%")
    print(f"\nRainbow Accélération:")
    print(f"  Window: {best['rainbow_w']}, Threshold: {best['rainbow_t']:.3f}, Alloc: {best['rainbow_a']}%")

    print(f"\nPerformance:")
    print(f"  Ratio vs B&H: {best['ratio']:.5f}x")
    print(f"  Equity: {best['equity']:.4f}x")
    print(f"  Trades: {best['trades']}")
    print(f"  Allocation moyenne: {best['avg_alloc']:.2f}%")

    if best['ratio'] > 1.36158:
        improvement = (best['ratio'] - 1.36158) * 100
        print(f"\n🚀🚀🚀 NOUVELLE CHAMPIONNE ABSOLUE!")
        print(f"   Bat l'ancienne championne de {improvement:.3f}%!")
        print(f"   Amélioration totale vs B&H: +{(best['ratio']-1)*100:.2f}%")
    elif best['ratio'] > 1.0:
        print(f"\n🎉 Bat B&H de {(best['ratio']-1)*100:.3f}%")
        print(f"   Mais championne actuelle reste meilleure")
    else:
        print(f"\n⚠️  Sous-performe B&H")

    # Sauvegarder
    df_results = df_results.sort_values('ratio', ascending=False)
    df_results.to_csv('outputs/velocity_acceleration_combo_results.csv', index=False)
    print(f"\n💾 Résultats: outputs/velocity_acceleration_combo_results.csv")

    print(f"\n📊 Top 10:")
    print(df_results.head(10).to_string(index=False))

else:
    print("\n⚠️  Aucune configuration > 1.35x")

print(f"\n✨ Terminé!")
