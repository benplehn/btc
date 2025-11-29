#!/usr/bin/env python3
"""
GRID SEARCH EXHAUSTIF: Moyennes Mobiles FNG + Rainbow

Tests:
1. Moyennes mobiles FNG (crossovers, distance, etc.)
2. Moyennes mobiles Rainbow (crossovers, distance, etc.)
3. Combinaisons MA + Vélocité
4. Grid search sur tous les paramètres

Objectif: Battre la championne actuelle (1.36158x)
"""
import pandas as pd
import numpy as np
from itertools import product
from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.strategy import calculate_rainbow_position
from src.fngbt.backtest import run_backtest

def fng_ma_crossover_strategy(df, fast_window, slow_window, alloc_bull=100, alloc_bear=95):
    """
    Stratégie: Croisement moyennes mobiles FNG

    FNG_fast > FNG_slow = Sentiment monte (greed augmente) → Réduire
    FNG_fast < FNG_slow = Sentiment descend (fear augmente) → Augmenter
    """
    d = df.copy()

    d['fng_fast'] = d['fng'].rolling(window=fast_window, min_periods=1).mean()
    d['fng_slow'] = d['fng'].rolling(window=slow_window, min_periods=1).mean()

    # Signal: fast > slow = sentiment monte (prudence)
    d['pos'] = np.where(d['fng_fast'] > d['fng_slow'], alloc_bear, alloc_bull)
    d['trade'] = (d['pos'].diff().abs() > 0.5).astype(int)

    return d

def rainbow_ma_crossover_strategy(df, fast_window, slow_window, alloc_bull=100, alloc_bear=95):
    """
    Stratégie: Croisement moyennes mobiles Rainbow

    Rainbow_fast > Rainbow_slow = Valorisation monte → Réduire
    Rainbow_fast < Rainbow_slow = Valorisation descend → Augmenter
    """
    d = df.copy()
    d = calculate_rainbow_position(d)

    d['rainbow_fast'] = d['rainbow_position'].rolling(window=fast_window, min_periods=1).mean()
    d['rainbow_slow'] = d['rainbow_position'].rolling(window=slow_window, min_periods=1).mean()

    # Signal: fast > slow = valorisation monte (prudence)
    d['pos'] = np.where(d['rainbow_fast'] > d['rainbow_slow'], alloc_bear, alloc_bull)
    d['trade'] = (d['pos'].diff().abs() > 0.5).astype(int)

    return d

def fng_ma_distance_strategy(df, ma_window, distance_threshold, alloc_far=95, alloc_near=100):
    """
    Stratégie: Distance FNG vs sa MA

    FNG loin de sa MA = Mouvement extrême → Prudence
    FNG proche de sa MA = Stabilité → Full allocation
    """
    d = df.copy()

    d['fng_ma'] = d['fng'].rolling(window=ma_window, min_periods=1).mean()
    d['fng_distance'] = (d['fng'] - d['fng_ma']).abs()

    # Distance grande = mouvement extrême
    d['pos'] = np.where(d['fng_distance'] > distance_threshold, alloc_far, alloc_near)
    d['trade'] = (d['pos'].diff().abs() > 0.5).astype(int)

    return d

def rainbow_ma_distance_strategy(df, ma_window, distance_threshold, alloc_far=95, alloc_near=100):
    """
    Stratégie: Distance Rainbow vs sa MA
    """
    d = df.copy()
    d = calculate_rainbow_position(d)

    d['rainbow_ma'] = d['rainbow_position'].rolling(window=ma_window, min_periods=1).mean()
    d['rainbow_distance'] = (d['rainbow_position'] - d['rainbow_ma']).abs()

    d['pos'] = np.where(d['rainbow_distance'] > distance_threshold, alloc_far, alloc_near)
    d['trade'] = (d['pos'].diff().abs() > 0.5).astype(int)

    return d

def combined_ma_velocity_strategy(df,
                                   fng_ma_window, fng_vel_window, fng_vel_thresh,
                                   rainbow_ma_window, rainbow_vel_window, rainbow_vel_thresh,
                                   alloc_calm=100, alloc_volatile=95, alloc_very_volatile=92):
    """
    Stratégie COMBINÉE: MA + Vélocité

    Combine:
    - Croisements MA pour tendance
    - Vélocité pour volatilité
    """
    d = df.copy()
    d = calculate_rainbow_position(d)

    # Moyennes mobiles
    d['fng_ma'] = d['fng'].rolling(window=fng_ma_window, min_periods=1).mean()
    d['rainbow_ma'] = d['rainbow_position'].rolling(window=rainbow_ma_window, min_periods=1).mean()

    # Vélocités
    d['fng_velocity'] = d['fng'].diff(fng_vel_window).abs()
    d['rainbow_velocity'] = d['rainbow_position'].diff(rainbow_vel_window).abs()

    # Signaux
    fng_above_ma = d['fng'] > d['fng_ma']
    rainbow_above_ma = d['rainbow_position'] > d['rainbow_ma']
    fng_volatile = d['fng_velocity'] > fng_vel_thresh
    rainbow_volatile = d['rainbow_velocity'] > rainbow_vel_thresh

    # Allocation
    allocation = np.ones(len(d)) * alloc_calm

    # Si MA au-dessus (greed/overvalued) OU volatile
    warning = (fng_above_ma | rainbow_above_ma | fng_volatile | rainbow_volatile)
    allocation[warning] = alloc_volatile

    # Si PLUSIEURS signaux simultanés
    multiple_warnings = ((fng_above_ma & rainbow_above_ma) |
                        (fng_volatile & rainbow_volatile) |
                        (fng_above_ma & fng_volatile) |
                        (rainbow_above_ma & rainbow_volatile))
    allocation[multiple_warnings] = alloc_very_volatile

    d['pos'] = allocation
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
print("🔍 GRID SEARCH EXHAUSTIF: Moyennes Mobiles + Vélocité")
print("="*100)
print(f"\n📊 Buy & Hold: {bh_equity:.2f}x")
print(f"🏆 À battre: 1.36158x (+36.2%)\n")

results = []

# 1. FNG MA CROSSOVER
print("="*100)
print("🔍 TEST 1: FNG MA CROSSOVER (Croisements)")
print("="*100)
print()

fast_windows = [3, 5, 7, 10]
slow_windows = [14, 21, 30, 50]
alloc_bears = [92, 93, 94, 95, 96, 97, 98]

count = 0
for fast, slow, alloc_bear in product(fast_windows, slow_windows, alloc_bears):
    if fast >= slow:
        continue

    signals = fng_ma_crossover_strategy(df, fast, slow, alloc_bull=100, alloc_bear=alloc_bear)
    result = run_backtest(signals, fees_bps=10.0)
    metrics = result['metrics']
    ratio = metrics['EquityFinal'] / bh_equity

    if ratio > 1.30:  # Afficher seulement les très bons
        count += 1
        marker = "🚀" if ratio > 1.36158 else "🎉"
        print(f"{marker} FNG MA({fast},{slow}), alloc={alloc_bear}% → Ratio {ratio:.5f}x | Trades {metrics['trades']:4d}")

        results.append({
            'strategy': 'FNG_MA_Cross',
            'config': f"MA({fast},{slow}),a={alloc_bear}",
            'ratio': ratio,
            'equity': metrics['EquityFinal'],
            'trades': metrics['trades'],
            'avg_alloc': metrics['avg_allocation']
        })

print(f"\n{count} configurations > 1.30x trouvées")

# 2. RAINBOW MA CROSSOVER
print(f"\n{'='*100}")
print("🔍 TEST 2: RAINBOW MA CROSSOVER")
print("="*100)
print()

count = 0
for fast, slow, alloc_bear in product(fast_windows, slow_windows, alloc_bears):
    if fast >= slow:
        continue

    signals = rainbow_ma_crossover_strategy(df, fast, slow, alloc_bull=100, alloc_bear=alloc_bear)
    result = run_backtest(signals, fees_bps=10.0)
    metrics = result['metrics']
    ratio = metrics['EquityFinal'] / bh_equity

    if ratio > 1.30:
        count += 1
        marker = "🚀" if ratio > 1.36158 else "🎉"
        print(f"{marker} Rainbow MA({fast},{slow}), alloc={alloc_bear}% → Ratio {ratio:.5f}x | Trades {metrics['trades']:4d}")

        results.append({
            'strategy': 'Rainbow_MA_Cross',
            'config': f"MA({fast},{slow}),a={alloc_bear}",
            'ratio': ratio,
            'equity': metrics['EquityFinal'],
            'trades': metrics['trades'],
            'avg_alloc': metrics['avg_allocation']
        })

print(f"\n{count} configurations > 1.30x trouvées")

# 3. FNG MA DISTANCE
print(f"\n{'='*100}")
print("🔍 TEST 3: FNG MA DISTANCE (Distance vs MA)")
print("="*100)
print()

ma_windows = [7, 10, 14, 21, 30]
distance_thresholds = [5, 10, 15, 20, 25]
alloc_fars = [92, 93, 94, 95, 96, 97]

count = 0
for ma_w, dist_thresh, alloc_far in product(ma_windows, distance_thresholds, alloc_fars):
    signals = fng_ma_distance_strategy(df, ma_w, dist_thresh, alloc_far=alloc_far, alloc_near=100)
    result = run_backtest(signals, fees_bps=10.0)
    metrics = result['metrics']
    ratio = metrics['EquityFinal'] / bh_equity

    if ratio > 1.30:
        count += 1
        marker = "🚀" if ratio > 1.36158 else "🎉"
        print(f"{marker} FNG Distance MA={ma_w}, thresh={dist_thresh}, alloc={alloc_far}% → Ratio {ratio:.5f}x | Trades {metrics['trades']:4d}")

        results.append({
            'strategy': 'FNG_MA_Distance',
            'config': f"MA={ma_w},t={dist_thresh},a={alloc_far}",
            'ratio': ratio,
            'equity': metrics['EquityFinal'],
            'trades': metrics['trades'],
            'avg_alloc': metrics['avg_allocation']
        })

print(f"\n{count} configurations > 1.30x trouvées")

# 4. RAINBOW MA DISTANCE
print(f"\n{'='*100}")
print("🔍 TEST 4: RAINBOW MA DISTANCE")
print("="*100)
print()

distance_thresholds_rainbow = [0.05, 0.1, 0.15, 0.2]

count = 0
for ma_w, dist_thresh, alloc_far in product(ma_windows, distance_thresholds_rainbow, alloc_fars):
    signals = rainbow_ma_distance_strategy(df, ma_w, dist_thresh, alloc_far=alloc_far, alloc_near=100)
    result = run_backtest(signals, fees_bps=10.0)
    metrics = result['metrics']
    ratio = metrics['EquityFinal'] / bh_equity

    if ratio > 1.30:
        count += 1
        marker = "🚀" if ratio > 1.36158 else "🎉"
        print(f"{marker} Rainbow Distance MA={ma_w}, thresh={dist_thresh:.2f}, alloc={alloc_far}% → Ratio {ratio:.5f}x | Trades {metrics['trades']:4d}")

        results.append({
            'strategy': 'Rainbow_MA_Distance',
            'config': f"MA={ma_w},t={dist_thresh},a={alloc_far}",
            'ratio': ratio,
            'equity': metrics['EquityFinal'],
            'trades': metrics['trades'],
            'avg_alloc': metrics['avg_allocation']
        })

print(f"\n{count} configurations > 1.30x trouvées")

# 5. COMBINÉE MA + VÉLOCITÉ (Le plus prometteur!)
print(f"\n{'='*100}")
print("🔍 TEST 5: COMBINÉE MA + VÉLOCITÉ (Grid Search Optimal)")
print("="*100)
print()

fng_ma_ws = [7, 14, 21]
fng_vel_ws = [5, 7, 10]
fng_vel_threshs = [8, 10, 12, 15]

rainbow_ma_ws = [7, 14, 21]
rainbow_vel_ws = [5, 7, 10]
rainbow_vel_threshs = [0.08, 0.1, 0.12, 0.15]

alloc_calms = [100]
alloc_volatiles = [95, 96, 97]
alloc_very_volatiles = [90, 91, 92, 93]

count = 0
best_combined = None
best_combined_ratio = 0

for params in product(fng_ma_ws, fng_vel_ws, fng_vel_threshs,
                      rainbow_ma_ws, rainbow_vel_ws, rainbow_vel_threshs,
                      alloc_volatiles, alloc_very_volatiles):

    fng_ma_w, fng_vel_w, fng_vel_t, rainbow_ma_w, rainbow_vel_w, rainbow_vel_t, alloc_vol, alloc_very_vol = params

    signals = combined_ma_velocity_strategy(
        df, fng_ma_w, fng_vel_w, fng_vel_t,
        rainbow_ma_w, rainbow_vel_w, rainbow_vel_t,
        alloc_calm=100, alloc_volatile=alloc_vol, alloc_very_volatile=alloc_very_vol
    )
    result = run_backtest(signals, fees_bps=10.0)
    metrics = result['metrics']
    ratio = metrics['EquityFinal'] / bh_equity

    if ratio > best_combined_ratio:
        best_combined_ratio = ratio
        best_combined = {
            'params': params,
            'metrics': metrics,
            'ratio': ratio
        }

    if ratio > 1.35:
        count += 1
        marker = "🚀" if ratio > 1.36158 else "🎉"
        print(f"{marker} Combined MA+Vel FNG({fng_ma_w},{fng_vel_w},{fng_vel_t}) Rainbow({rainbow_ma_w},{rainbow_vel_w},{rainbow_vel_t:.2f}) allocs({alloc_vol},{alloc_very_vol}) → {ratio:.5f}x")

        results.append({
            'strategy': 'Combined_MA_Velocity',
            'config': f"FNG({fng_ma_w},{fng_vel_w},{fng_vel_t})+Rain({rainbow_ma_w},{rainbow_vel_w},{rainbow_vel_t})+a({alloc_vol},{alloc_very_vol})",
            'ratio': ratio,
            'equity': metrics['EquityFinal'],
            'trades': metrics['trades'],
            'avg_alloc': metrics['avg_allocation']
        })

print(f"\n{count} configurations > 1.35x trouvées")

# MEILLEURE GLOBALE
print(f"\n{'='*100}")
print("🏆 MEILLEURE STRATÉGIE TROUVÉE")
print("="*100)

if results:
    df_results = pd.DataFrame(results)
    best = df_results.loc[df_results['ratio'].idxmax()]

    print(f"\nType: {best['strategy']}")
    print(f"Config: {best['config']}")
    print(f"Ratio vs B&H: {best['ratio']:.5f}x")
    print(f"Equity: {best['equity']:.4f}x")
    print(f"Trades: {best['trades']}")
    print(f"Allocation moyenne: {best['avg_alloc']:.2f}%")

    if best['ratio'] > 1.36158:
        print(f"\n🚀🚀🚀 NOUVELLE CHAMPIONNE! Bat précédente de {(best['ratio']-1.36158)*100:.3f}%!")
        print(f"   Amélioration totale vs B&H: +{(best['ratio']-1)*100:.2f}%")
    elif best['ratio'] > 1.0:
        print(f"\n🎉 Bat B&H de {(best['ratio']-1)*100:.3f}%")
        print(f"   Mais championne actuelle reste meilleure ({1.36158:.5f}x)")

    # Sauvegarder
    df_results = df_results.sort_values('ratio', ascending=False)
    df_results.to_csv('outputs/ma_grid_search_results.csv', index=False)
    print(f"\n💾 Résultats sauvegardés: outputs/ma_grid_search_results.csv")

    print(f"\n📊 Top 15 stratégies:")
    print(df_results.head(15)[['strategy', 'config', 'ratio', 'trades']].to_string(index=False))

else:
    print("\n⚠️  Aucune stratégie prometteuse trouvée")

print(f"\n✨ Grid search terminé!")
