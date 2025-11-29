#!/usr/bin/env python3
"""
RAINBOW VÉLOCITÉ + Combinaison FNG & Rainbow Vélocité

Tests:
1. Rainbow VÉLOCITÉ seule
2. Rainbow MOMENTUM seule
3. FNG Vélocité + Rainbow Vélocité (COMBINÉ)
4. FNG Momentum + Rainbow Momentum (COMBINÉ)

Objectif: Battre la championne actuelle (FNG vélocité: 1.27852x)
"""
import pandas as pd
import numpy as np
from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.strategy import calculate_rainbow_position
from src.fngbt.backtest import run_backtest

def rainbow_velocity_strategy(df, velocity_window=7, velocity_thresh=0.1, alloc_volatile=96):
    """
    Stratégie VÉLOCITÉ RAINBOW

    Changements rapides de Rainbow = volatilité de valorisation
    → Réduire légèrement allocation
    """
    d = df.copy()
    d = calculate_rainbow_position(d)

    # Vélocité Rainbow = changement absolu sur N jours
    d['rainbow_velocity'] = d['rainbow_position'].diff(velocity_window).abs()

    allocation = np.ones(len(d)) * 100.0

    # Haute vélocité Rainbow = valorisation volatile
    high_velocity_mask = d['rainbow_velocity'] > velocity_thresh
    allocation[high_velocity_mask] = alloc_volatile

    d['pos'] = allocation
    d['trade'] = (d['pos'].diff().abs() > 0.5).astype(int)

    return d

def rainbow_momentum_strategy(df, ma_window=14, alloc_rising=96, alloc_falling=100):
    """
    Stratégie MOMENTUM RAINBOW

    Rainbow > MA = Valorisation monte (bull) → Peut-être réduire si trop haut
    Rainbow < MA = Valorisation descend (bear) → Opportunité
    """
    d = df.copy()
    d = calculate_rainbow_position(d)

    # MA Rainbow
    d['rainbow_ma'] = d['rainbow_position'].rolling(window=ma_window, min_periods=1).mean()
    d['rainbow_momentum'] = d['rainbow_position'] - d['rainbow_ma']

    allocation = np.ones(len(d)) * 100.0

    # Rainbow monte (valorisation augmente)
    rising_mask = d['rainbow_momentum'] > 0.05
    allocation[rising_mask] = alloc_rising

    # Rainbow descend (valorisation baisse)
    falling_mask = d['rainbow_momentum'] < -0.05
    allocation[falling_mask] = alloc_falling

    d['pos'] = allocation
    d['trade'] = (d['pos'].diff().abs() > 0.5).astype(int)

    return d

def combined_velocity_strategy(df,
                                fng_window=7, fng_thresh=10, fng_alloc=96,
                                rainbow_window=7, rainbow_thresh=0.1, rainbow_alloc=97):
    """
    Stratégie COMBINÉE: FNG Vélocité + Rainbow Vélocité

    Logique:
    - Si FNG volatile ET Rainbow volatile: TRÈS prudent (93%)
    - Si FNG volatile OU Rainbow volatile: Prudent (96-97%)
    - Si les deux stables: Full (100%)
    """
    d = df.copy()
    d = calculate_rainbow_position(d)

    # Vélocités
    d['fng_velocity'] = d['fng'].diff(fng_window).abs()
    d['rainbow_velocity'] = d['rainbow_position'].diff(rainbow_window).abs()

    # Masques
    fng_volatile = d['fng_velocity'] > fng_thresh
    rainbow_volatile = d['rainbow_velocity'] > rainbow_thresh

    # Allocation par défaut
    allocation = np.ones(len(d)) * 100.0

    # FNG OU Rainbow volatile: Légère réduction
    either_volatile = fng_volatile | rainbow_volatile
    allocation[either_volatile] = max(fng_alloc, rainbow_alloc)

    # BOTH volatile: Réduction plus forte
    both_volatile = fng_volatile & rainbow_volatile
    allocation[both_volatile] = min(fng_alloc, rainbow_alloc) - 3

    d['pos'] = allocation
    d['trade'] = (d['pos'].diff().abs() > 0.5).astype(int)

    return d

def combined_momentum_strategy(df,
                                fng_ma=14, rainbow_ma=14,
                                alloc_both_rising=94,
                                alloc_one_rising=97,
                                alloc_both_falling=100):
    """
    Stratégie COMBINÉE: FNG Momentum + Rainbow Momentum

    Logique:
    - FNG monte ET Rainbow monte: Greed + Overvalued → Réduire (94%)
    - Un des deux monte: Prudent (97%)
    - Les deux descendent: Opportunité (100%)
    """
    d = df.copy()
    d = calculate_rainbow_position(d)

    # MAs
    d['fng_ma'] = d['fng'].rolling(window=fng_ma, min_periods=1).mean()
    d['rainbow_ma'] = d['rainbow_position'].rolling(window=rainbow_ma, min_periods=1).mean()

    # Momentums
    d['fng_momentum'] = d['fng'] - d['fng_ma']
    d['rainbow_momentum'] = d['rainbow_position'] - d['rainbow_ma']

    # Masques
    fng_rising = d['fng_momentum'] > 5
    rainbow_rising = d['rainbow_momentum'] > 0.05

    allocation = np.ones(len(d)) * 100.0

    # Un des deux monte
    one_rising = (fng_rising & ~rainbow_rising) | (~fng_rising & rainbow_rising)
    allocation[one_rising] = alloc_one_rising

    # Les deux montent (greed + overvalued)
    both_rising = fng_rising & rainbow_rising
    allocation[both_rising] = alloc_both_rising

    # Les deux descendent (fear + undervalued)
    both_falling = (~fng_rising) & (~rainbow_rising)
    allocation[both_falling] = alloc_both_falling

    d['pos'] = allocation
    d['trade'] = (d['pos'].diff().abs() > 0.5).astype(int)

    return d

# Load data
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
print("🎯 RAINBOW VÉLOCITÉ + COMBINAISONS FNG+RAINBOW")
print("="*100)
print(f"\n📊 Buy & Hold: {bh_equity:.2f}x")
print(f"🏆 À battre: FNG Vélocité 1.27852x (+27.9%)\n")

results = []

# 1. RAINBOW VÉLOCITÉ
print("="*100)
print("🔍 TEST 1: RAINBOW VÉLOCITÉ SEULE")
print("="*100)
print()

for velocity_window in [5, 7, 10, 14]:
    for velocity_thresh in [0.05, 0.1, 0.15, 0.2]:
        for alloc_volatile in [94, 95, 96, 97, 98]:
            signals = rainbow_velocity_strategy(df, velocity_window, velocity_thresh, alloc_volatile)
            result = run_backtest(signals, fees_bps=10.0)
            metrics = result['metrics']
            ratio = metrics['EquityFinal'] / bh_equity

            if ratio > 1.0:
                marker = "🎉"
                name = f"Rainbow Velocity w={velocity_window}, thresh={velocity_thresh:.2f}, alloc={alloc_volatile}%"
                print(f"{marker} {name:<75} → Ratio {ratio:.5f}x | Trades {metrics['trades']:4d}")

                results.append({
                    'strategy': 'Rainbow Velocity',
                    'config': f"w={velocity_window},t={velocity_thresh},a={alloc_volatile}",
                    'ratio': ratio,
                    'equity': metrics['EquityFinal'],
                    'trades': metrics['trades'],
                    'avg_alloc': metrics['avg_allocation']
                })

# 2. RAINBOW MOMENTUM
print(f"\n{'='*100}")
print("🔍 TEST 2: RAINBOW MOMENTUM SEULE")
print("="*100)
print()

for ma_window in [7, 10, 14, 21]:
    for alloc_rising in [94, 95, 96, 97, 98]:
        for alloc_falling in [98, 99, 100]:
            signals = rainbow_momentum_strategy(df, ma_window, alloc_rising, alloc_falling)
            result = run_backtest(signals, fees_bps=10.0)
            metrics = result['metrics']
            ratio = metrics['EquityFinal'] / bh_equity

            if ratio > 1.0:
                marker = "🎉"
                name = f"Rainbow Momentum MA={ma_window}, rising={alloc_rising}%, falling={alloc_falling}%"
                print(f"{marker} {name:<75} → Ratio {ratio:.5f}x | Trades {metrics['trades']:4d}")

                results.append({
                    'strategy': 'Rainbow Momentum',
                    'config': f"ma={ma_window},r={alloc_rising},f={alloc_falling}",
                    'ratio': ratio,
                    'equity': metrics['EquityFinal'],
                    'trades': metrics['trades'],
                    'avg_alloc': metrics['avg_allocation']
                })

# 3. COMBINÉE VÉLOCITÉ
print(f"\n{'='*100}")
print("🔍 TEST 3: FNG + RAINBOW VÉLOCITÉ COMBINÉE")
print("="*100)
print()

for fng_w in [7, 10]:
    for fng_t in [10, 15]:
        for fng_a in [95, 96, 97]:
            for rainbow_w in [7, 10]:
                for rainbow_t in [0.1, 0.15]:
                    for rainbow_a in [96, 97, 98]:
                        signals = combined_velocity_strategy(
                            df, fng_w, fng_t, fng_a,
                            rainbow_w, rainbow_t, rainbow_a
                        )
                        result = run_backtest(signals, fees_bps=10.0)
                        metrics = result['metrics']
                        ratio = metrics['EquityFinal'] / bh_equity

                        if ratio > 1.27:  # Afficher seulement si bat la championne
                            marker = "🚀" if ratio > 1.27852 else "🎉"
                            name = f"Combiné Velocity FNG(w={fng_w},t={fng_t},a={fng_a}) + Rainbow(w={rainbow_w},t={rainbow_t},a={rainbow_a})"
                            print(f"{marker} {name:<80} → Ratio {ratio:.5f}x | Trades {metrics['trades']:4d}")

                            results.append({
                                'strategy': 'Combined Velocity',
                                'config': f"FNG({fng_w},{fng_t},{fng_a})+Rainbow({rainbow_w},{rainbow_t},{rainbow_a})",
                                'ratio': ratio,
                                'equity': metrics['EquityFinal'],
                                'trades': metrics['trades'],
                                'avg_alloc': metrics['avg_allocation']
                            })

# 4. COMBINÉE MOMENTUM
print(f"\n{'='*100}")
print("🔍 TEST 4: FNG + RAINBOW MOMENTUM COMBINÉE")
print("="*100)
print()

for fng_ma in [10, 14, 21]:
    for rainbow_ma in [10, 14, 21]:
        for alloc_both_rising in [92, 93, 94, 95]:
            for alloc_one_rising in [96, 97, 98]:
                for alloc_both_falling in [99, 100]:
                    signals = combined_momentum_strategy(
                        df, fng_ma, rainbow_ma,
                        alloc_both_rising, alloc_one_rising, alloc_both_falling
                    )
                    result = run_backtest(signals, fees_bps=10.0)
                    metrics = result['metrics']
                    ratio = metrics['EquityFinal'] / bh_equity

                    if ratio > 1.27:
                        marker = "🚀" if ratio > 1.27852 else "🎉"
                        name = f"Combiné Momentum FNG_MA={fng_ma}, Rainbow_MA={rainbow_ma}, allocs=({alloc_both_rising},{alloc_one_rising},{alloc_both_falling})"
                        print(f"{marker} {name:<80} → Ratio {ratio:.5f}x | Trades {metrics['trades']:4d}")

                        results.append({
                            'strategy': 'Combined Momentum',
                            'config': f"FNG_MA{fng_ma},Rainbow_MA{rainbow_ma},({alloc_both_rising},{alloc_one_rising},{alloc_both_falling})",
                            'ratio': ratio,
                            'equity': metrics['EquityFinal'],
                            'trades': metrics['trades'],
                            'avg_alloc': metrics['avg_allocation']
                        })

# Meilleure stratégie
print(f"\n{'='*100}")
print("🏆 MEILLEURE STRATÉGIE GLOBALE")
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

    if best['ratio'] > 1.27852:
        print(f"\n🚀🚀🚀 NOUVELLE CHAMPIONNE! Bat FNG Vélocité de {(best['ratio']-1.27852)*100:.3f}%!")
    elif best['ratio'] > 1.0:
        print(f"\n🎉 Bat B&H de {(best['ratio']-1)*100:.3f}% (mais pas la championne FNG Vélocité)")
    else:
        print(f"\n⚠️  Sous-performe B&H")

    # Sauvegarder
    df_results.to_csv('outputs/rainbow_velocity_combined_results.csv', index=False)
    print(f"\n💾 Résultats sauvegardés: outputs/rainbow_velocity_combined_results.csv")

    print("\n📊 Top 10 stratégies:")
    print(df_results.nlargest(10, 'ratio')[['strategy', 'ratio', 'trades', 'avg_alloc']].to_string(index=False))
else:
    print("\n⚠️  Aucune stratégie ne bat B&H")
