#!/usr/bin/env python3
"""
FNG AVANCÉ: Au-delà des paliers simples

Nouvelles approches à tester:
1. GRADIENT: Interpolation continue basée sur FNG (pas de paliers)
2. VÉLOCITÉ: Vitesse de changement du FNG
3. MOMENTUM: Tendance/direction du FNG
4. MOYENNES MOBILES: FNG MA vs FNG spot
5. EXTRÊMES: Réagir différemment aux extrêmes FNG
"""
import pandas as pd
import numpy as np
from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.strategy import calculate_rainbow_position
from src.fngbt.backtest import run_backtest

def fng_gradient_strategy(df, fng_low, fng_high, alloc_low, alloc_high, use_rainbow=True, rainbow_thresh=0.6):
    """
    Stratégie GRADIENT: Allocation linéaire continue basée sur FNG

    Args:
        fng_low: FNG bas (ex: 20)
        fng_high: FNG haut (ex: 80)
        alloc_low: Allocation quand FNG bas (ex: 100%)
        alloc_high: Allocation quand FNG haut (ex: 90%)
        use_rainbow: Si True, Rainbow module l'allocation
    """
    d = df.copy()
    if use_rainbow:
        d = calculate_rainbow_position(d)

    fng_values = d['fng'].values
    allocation = np.zeros(len(d))

    for i in range(len(d)):
        fng = fng_values[i]

        # Gradient linéaire basé sur FNG
        if fng <= fng_low:
            base_alloc = alloc_low
        elif fng >= fng_high:
            base_alloc = alloc_high
        else:
            # Interpolation linéaire
            fng_score = (fng - fng_low) / (fng_high - fng_low)
            base_alloc = alloc_low - fng_score * (alloc_low - alloc_high)

        # Rainbow modulation optionnelle
        if use_rainbow and d['rainbow_position'].iloc[i] >= rainbow_thresh:
            base_alloc = max(base_alloc - 2, alloc_high)  # Réduire de 2% si Rainbow haut

        allocation[i] = base_alloc

    d['pos'] = allocation
    d['trade'] = (d['pos'].diff().abs() > 0.5).astype(int)

    return d

def fng_velocity_strategy(df, velocity_window=7, high_velocity_thresh=10, alloc_volatile=98):
    """
    Stratégie VÉLOCITÉ: Réagir aux changements rapides de FNG

    Si FNG change rapidement (haute vélocité), réduire légèrement allocation
    = Prudence en période de volatilité de sentiment
    """
    d = df.copy()
    d = calculate_rainbow_position(d)

    # Calculer vélocité FNG (changement sur N jours)
    d['fng_velocity'] = d['fng'].diff(velocity_window).abs()

    allocation = np.ones(len(d)) * 100.0  # Défaut 100%

    # Réduire en période de haute vélocité
    high_velocity_mask = d['fng_velocity'] > high_velocity_thresh
    allocation[high_velocity_mask] = alloc_volatile

    # Rainbow modulation
    high_rainbow_mask = d['rainbow_position'] >= 0.6
    allocation[high_rainbow_mask & high_velocity_mask] = alloc_volatile - 2

    d['pos'] = allocation
    d['trade'] = (d['pos'].diff().abs() > 0.5).astype(int)

    return d

def fng_momentum_strategy(df, ma_window=14, alloc_base=100, alloc_reduced=95):
    """
    Stratégie MOMENTUM: FNG vs sa moyenne mobile

    - FNG > MA: Sentiment monte (greed augmente) → Réduire
    - FNG < MA: Sentiment descend (fear augmente) → Augmenter
    """
    d = df.copy()
    d = calculate_rainbow_position(d)

    # Moyenne mobile FNG
    d['fng_ma'] = d['fng'].rolling(window=ma_window, min_periods=1).mean()

    # Momentum = FNG - MA
    d['fng_momentum'] = d['fng'] - d['fng_ma']

    allocation = np.ones(len(d)) * alloc_base

    # Si FNG > MA (greed monte), réduire
    greed_rising = d['fng_momentum'] > 5
    allocation[greed_rising] = alloc_reduced

    # Rainbow modulation
    high_rainbow = d['rainbow_position'] >= 0.6
    allocation[greed_rising & high_rainbow] = alloc_reduced - 2

    d['pos'] = allocation
    d['trade'] = (d['pos'].diff().abs() > 0.5).astype(int)

    return d

def fng_extremes_strategy(df, extreme_fear=20, extreme_greed=80):
    """
    Stratégie EXTRÊMES: Réagir aux zones extrêmes de FNG

    - FNG < 20: Extreme Fear → ALL-IN 100%
    - FNG > 80: Extreme Greed → Réduire à 90%
    - Entre les deux: 100% avec Rainbow modulation
    """
    d = df.copy()
    d = calculate_rainbow_position(d)

    fng_values = d['fng'].values
    rainbow_values = d['rainbow_position'].values
    allocation = np.ones(len(d)) * 100.0

    for i in range(len(d)):
        fng = fng_values[i]
        rainbow = rainbow_values[i]

        if fng < extreme_fear:
            # Extreme Fear: ALL-IN
            allocation[i] = 100
        elif fng > extreme_greed:
            # Extreme Greed: Réduire
            if rainbow >= 0.6:
                allocation[i] = 90
            else:
                allocation[i] = 95
        else:
            # Zone neutre: Rainbow seul
            if rainbow >= 0.6:
                allocation[i] = 97
            else:
                allocation[i] = 100

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
print("🎯 FNG AVANCÉ: Gradient, Vélocité, Momentum, Extrêmes")
print("="*100)
print(f"\n📊 Buy & Hold: {bh_equity:.2f}x\n")

results = []

# 1. Test GRADIENT strategies
print("="*100)
print("🔍 TEST 1: GRADIENT (Interpolation continue FNG)")
print("="*100)
print()

gradient_configs = [
    {'fng_low': 20, 'fng_high': 80, 'alloc_low': 100, 'alloc_high': 90, 'use_rainbow': False},
    {'fng_low': 20, 'fng_high': 80, 'alloc_low': 100, 'alloc_high': 95, 'use_rainbow': False},
    {'fng_low': 25, 'fng_high': 75, 'alloc_low': 100, 'alloc_high': 95, 'use_rainbow': False},
    {'fng_low': 20, 'fng_high': 80, 'alloc_low': 100, 'alloc_high': 95, 'use_rainbow': True},
    {'fng_low': 25, 'fng_high': 75, 'alloc_low': 100, 'alloc_high': 97, 'use_rainbow': True},
]

for config in gradient_configs:
    signals = fng_gradient_strategy(df, **config)
    result = run_backtest(signals, fees_bps=10.0)
    metrics = result['metrics']
    ratio = metrics['EquityFinal'] / bh_equity

    name = f"Gradient FNG [{config['fng_low']},{config['fng_high']}] → [{config['alloc_low']},{config['alloc_high']}]%"
    if config['use_rainbow']:
        name += " +Rainbow"

    marker = "🎉" if ratio > 1.0 else "  "
    print(f"{marker} {name:<70} → Ratio {ratio:.5f}x | Trades {metrics['trades']:4d}")

    results.append({
        'strategy': 'Gradient',
        'config': str(config),
        'ratio': ratio,
        'equity': metrics['EquityFinal'],
        'trades': metrics['trades'],
        'avg_alloc': metrics['avg_allocation']
    })

# 2. Test VÉLOCITÉ strategies
print(f"\n{'='*100}")
print("🔍 TEST 2: VÉLOCITÉ (Réagir aux changements rapides FNG)")
print("="*100)
print()

for velocity_window in [5, 7, 10, 14]:
    for velocity_thresh in [10, 15, 20]:
        for alloc_volatile in [96, 97, 98]:
            signals = fng_velocity_strategy(df, velocity_window, velocity_thresh, alloc_volatile)
            result = run_backtest(signals, fees_bps=10.0)
            metrics = result['metrics']
            ratio = metrics['EquityFinal'] / bh_equity

            if ratio > 0.99:  # Afficher seulement les bons
                marker = "🎉" if ratio > 1.0 else "🔥"
                name = f"Vélocité window={velocity_window}, thresh={velocity_thresh}, alloc={alloc_volatile}%"
                print(f"{marker} {name:<70} → Ratio {ratio:.5f}x | Trades {metrics['trades']:4d}")

                results.append({
                    'strategy': 'Velocity',
                    'config': f"w={velocity_window},t={velocity_thresh},a={alloc_volatile}",
                    'ratio': ratio,
                    'equity': metrics['EquityFinal'],
                    'trades': metrics['trades'],
                    'avg_alloc': metrics['avg_allocation']
                })

# 3. Test MOMENTUM strategies
print(f"\n{'='*100}")
print("🔍 TEST 3: MOMENTUM (FNG vs Moyenne Mobile)")
print("="*100)
print()

for ma_window in [7, 10, 14, 21, 30]:
    for alloc_reduced in [94, 95, 96, 97, 98]:
        signals = fng_momentum_strategy(df, ma_window, 100, alloc_reduced)
        result = run_backtest(signals, fees_bps=10.0)
        metrics = result['metrics']
        ratio = metrics['EquityFinal'] / bh_equity

        if ratio > 0.99:
            marker = "🎉" if ratio > 1.0 else "🔥"
            name = f"Momentum MA={ma_window}, alloc_reduced={alloc_reduced}%"
            print(f"{marker} {name:<70} → Ratio {ratio:.5f}x | Trades {metrics['trades']:4d}")

            results.append({
                'strategy': 'Momentum',
                'config': f"ma={ma_window},a={alloc_reduced}",
                'ratio': ratio,
                'equity': metrics['EquityFinal'],
                'trades': metrics['trades'],
                'avg_alloc': metrics['avg_allocation']
            })

# 4. Test EXTRÊMES strategies
print(f"\n{'='*100}")
print("🔍 TEST 4: EXTRÊMES (Zones extrêmes FNG)")
print("="*100)
print()

for extreme_fear in [15, 20, 25]:
    for extreme_greed in [75, 80, 85]:
        signals = fng_extremes_strategy(df, extreme_fear, extreme_greed)
        result = run_backtest(signals, fees_bps=10.0)
        metrics = result['metrics']
        ratio = metrics['EquityFinal'] / bh_equity

        marker = "🎉" if ratio > 1.0 else "  "
        name = f"Extrêmes Fear<{extreme_fear}, Greed>{extreme_greed}"
        print(f"{marker} {name:<70} → Ratio {ratio:.5f}x | Trades {metrics['trades']:4d}")

        results.append({
            'strategy': 'Extremes',
            'config': f"fear<{extreme_fear},greed>{extreme_greed}",
            'ratio': ratio,
            'equity': metrics['EquityFinal'],
            'trades': metrics['trades'],
            'avg_alloc': metrics['avg_allocation']
        })

# Meilleure stratégie globale
print(f"\n{'='*100}")
print("🏆 MEILLEURE STRATÉGIE AVANCÉE TROUVÉE")
print("="*100)

df_results = pd.DataFrame(results)
best = df_results.loc[df_results['ratio'].idxmax()]

print(f"\nType: {best['strategy']}")
print(f"Config: {best['config']}")
print(f"Ratio vs B&H: {best['ratio']:.5f}x")
print(f"Equity: {best['equity']:.4f}x")
print(f"Trades: {best['trades']}")
print(f"Allocation moyenne: {best['avg_alloc']:.2f}%")

if best['ratio'] > 1.0:
    print(f"\n🎉 VICTOIRE! Bat B&H de {(best['ratio']-1)*100:.3f}%")
else:
    print(f"\n⚠️  Sous-performe B&H de {(1-best['ratio'])*100:.3f}%")

# Sauvegarder
df_results.to_csv('outputs/fng_advanced_results.csv', index=False)
print(f"\n💾 Résultats sauvegardés: outputs/fng_advanced_results.csv")

print("\n📊 Top 10 stratégies:")
print(df_results.nlargest(10, 'ratio')[['strategy', 'config', 'ratio', 'trades']].to_string(index=False))
