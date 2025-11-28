#!/usr/bin/env python3
"""
Analyse détaillée de la stratégie : où perd-on de l'argent ?

Identifie:
- Périodes de sous-performance
- Ventes trop tôt
- Achats manqués
- Problèmes de timing
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.strategy import StrategyConfig, build_signals
from src.fngbt.backtest import run_backtest


def analyze_performance_periods(df: pd.DataFrame):
    """
    Analyse les périodes de sur/sous-performance
    """
    print("\n" + "="*80)
    print("📊 ANALYSE DES PÉRIODES DE PERFORMANCE")
    print("="*80)

    # Calcul des performances relatives
    df['strategy_vs_bh'] = df['equity'] / df['bh_equity']
    df['underperformance'] = df['strategy_vs_bh'] < 0.95  # Sous-performe de plus de 5%

    # Identifier les périodes continues de sous-performance
    df['period_change'] = (df['underperformance'] != df['underperformance'].shift(1)).astype(int)
    df['period_id'] = df['period_change'].cumsum()

    # Analyser chaque période de sous-performance
    bad_periods = []
    for period_id, group in df.groupby('period_id'):
        if group['underperformance'].iloc[0]:  # Période de sous-perf
            start_date = group['date'].iloc[0]
            end_date = group['date'].iloc[-1]
            duration = len(group)

            if duration > 30:  # Au moins 30 jours
                # Performance pendant cette période
                start_equity = group['equity'].iloc[0]
                end_equity = group['equity'].iloc[-1]
                start_bh = group['bh_equity'].iloc[0]
                end_bh = group['bh_equity'].iloc[-1]

                strat_perf = (end_equity / start_equity - 1) * 100
                bh_perf = (end_bh / start_bh - 1) * 100
                gap = bh_perf - strat_perf

                # Prix BTC
                start_price = group['close'].iloc[0]
                end_price = group['close'].iloc[-1]
                price_change = (end_price / start_price - 1) * 100

                # FNG et Rainbow moyens
                avg_fng = group['fng'].mean()
                avg_rainbow_pos = group['rainbow_position'].mean()
                avg_allocation = group['pos'].mean()

                bad_periods.append({
                    'start': start_date,
                    'end': end_date,
                    'days': duration,
                    'strat_perf': strat_perf,
                    'bh_perf': bh_perf,
                    'gap': gap,
                    'price_change': price_change,
                    'avg_fng': avg_fng,
                    'avg_rainbow': avg_rainbow_pos,
                    'avg_alloc': avg_allocation
                })

    # Trier par gap (pire d'abord)
    bad_periods.sort(key=lambda x: x['gap'], reverse=True)

    print(f"\n🔴 {len(bad_periods)} périodes de sous-performance significative trouvées:\n")

    for i, period in enumerate(bad_periods[:10], 1):  # Top 10 pires
        print(f"{i}. {period['start'].date()} → {period['end'].date()} ({period['days']} jours)")
        print(f"   Stratégie: {period['strat_perf']:+.1f}% | B&H: {period['bh_perf']:+.1f}% | GAP: {period['gap']:.1f}%")
        print(f"   Prix BTC: {period['price_change']:+.1f}%")
        print(f"   FNG moyen: {period['avg_fng']:.0f} | Rainbow: {period['avg_rainbow']:.2f} | Allocation: {period['avg_alloc']:.1f}%")

        # Diagnostic
        if period['price_change'] > 20 and period['avg_alloc'] < 50:
            print(f"   💡 DIAGNOSTIC: Bull market raté (allocation trop basse)")
        elif period['price_change'] < -20 and period['avg_alloc'] > 50:
            print(f"   💡 DIAGNOSTIC: Bear market mal protégé (allocation trop haute)")
        elif period['avg_fng'] > 70 and period['avg_alloc'] < 30:
            print(f"   💡 DIAGNOSTIC: Vente trop agressive en GREED")
        elif period['avg_fng'] < 30 and period['avg_alloc'] < 70:
            print(f"   💡 DIAGNOSTIC: Achat pas assez agressif en FEAR")

        print()

    return bad_periods


def analyze_trades(df: pd.DataFrame):
    """
    Analyse la qualité des trades
    """
    print("\n" + "="*80)
    print("🔄 ANALYSE DES TRADES")
    print("="*80)

    trades = df[df['trade'] == 1].copy()

    print(f"\nNombre total de trades: {len(trades)}")

    if len(trades) == 0:
        print("⚠️  Aucun trade détecté!")
        return

    # Analyser les changements d'allocation
    good_trades = 0
    bad_trades = 0

    for idx in trades.index:
        if idx == 0:
            continue

        # Changement d'allocation
        old_alloc = df.loc[idx-1, 'pos']
        new_alloc = df.loc[idx, 'pos']
        change = new_alloc - old_alloc

        # Performance sur les 30 jours suivants
        future_idx = min(idx + 30, len(df) - 1)
        future_price_change = (df.loc[future_idx, 'close'] / df.loc[idx, 'close'] - 1) * 100

        # Bon trade si on augmente avant hausse ou diminue avant baisse
        if (change > 0 and future_price_change > 5) or (change < 0 and future_price_change < -5):
            good_trades += 1
        elif (change > 0 and future_price_change < -5) or (change < 0 and future_price_change > 5):
            bad_trades += 1

    total_scored = good_trades + bad_trades
    if total_scored > 0:
        print(f"\nQualité des trades (30 jours forward):")
        print(f"   ✅ Bons trades: {good_trades} ({good_trades/total_scored*100:.1f}%)")
        print(f"   ❌ Mauvais trades: {bad_trades} ({bad_trades/total_scored*100:.1f}%)")
        print(f"   ⚪ Neutres: {len(trades) - total_scored}")


def identify_missed_opportunities(df: pd.DataFrame):
    """
    Identifie les opportunités manquées
    """
    print("\n" + "="*80)
    print("💸 OPPORTUNITÉS MANQUÉES")
    print("="*80)

    # Périodes où on aurait dû être plus investi
    df['should_be_higher'] = (
        (df['fng'] < 30) &  # FEAR
        (df['rainbow_position'] < 0.4) &  # Prix bas
        (df['pos'] < 80)  # Mais allocation < 80%
    )

    # Périodes où on aurait dû réduire
    df['should_be_lower'] = (
        (df['fng'] > 70) &  # GREED
        (df['rainbow_position'] > 0.6) &  # Prix haut
        (df['pos'] > 20)  # Mais allocation > 20%
    )

    missed_buys = df[df['should_be_higher']].copy()
    missed_sells = df[df['should_be_lower']].copy()

    print(f"\n🔵 {len(missed_buys)} jours où l'allocation aurait dû être PLUS HAUTE")
    if len(missed_buys) > 0:
        print(f"   Allocation moyenne durant ces périodes: {missed_buys['pos'].mean():.1f}%")
        print(f"   FNG moyen: {missed_buys['fng'].mean():.0f}")
        print(f"   Prix BTC moyen: ${missed_buys['close'].mean():,.0f}")

    print(f"\n🔴 {len(missed_sells)} jours où l'allocation aurait dû être PLUS BASSE")
    if len(missed_sells) > 0:
        print(f"   Allocation moyenne durant ces périodes: {missed_sells['pos'].mean():.1f}%")
        print(f"   FNG moyen: {missed_sells['fng'].mean():.0f}")
        print(f"   Prix BTC moyen: ${missed_sells['close'].mean():,.0f}")


def main():
    print("="*80)
    print("🔍 ANALYSE DÉTAILLÉE DE LA STRATÉGIE")
    print("="*80)

    # Chargement données
    print("\n📊 Chargement des données...")
    fng = load_fng_alt()
    btc = load_btc_prices()
    df = merge_daily(fng, btc)
    print(f"✅ {len(df)} jours chargés")

    # Configuration actuelle (celle qui pose problème)
    print("\n⚙️  Configuration analysée:")
    cfg = StrategyConfig(
        fng_buy_threshold=25,
        fng_sell_threshold=75,
        rainbow_buy_threshold=0.3,
        rainbow_sell_threshold=0.7,
        min_position_change_pct=10.0
    )

    print(f"   FNG Buy: {cfg.fng_buy_threshold} | Sell: {cfg.fng_sell_threshold}")
    print(f"   Rainbow Buy: {cfg.rainbow_buy_threshold} | Sell: {cfg.rainbow_sell_threshold}")

    # Backtest
    print("\n🔄 Exécution du backtest...")
    signals = build_signals(df, cfg)
    result = run_backtest(signals, fees_bps=10.0)

    metrics = result['metrics']
    ratio = metrics['EquityFinal'] / metrics['BHEquityFinal']

    print(f"\n📈 Résultats globaux:")
    print(f"   Stratégie: {metrics['EquityFinal']:.2f}x")
    print(f"   Buy & Hold: {metrics['BHEquityFinal']:.2f}x")
    print(f"   Ratio: {ratio:.3f}x {'✅' if ratio > 1.0 else '❌'}")
    print(f"   CAGR: {metrics['CAGR']*100:.1f}%")
    print(f"   Max DD: {metrics['MaxDD']*100:.1f}%")
    print(f"   Trades: {metrics['trades']}")

    # Analyses détaillées
    bad_periods = analyze_performance_periods(result['df'])
    analyze_trades(result['df'])
    identify_missed_opportunities(result['df'])

    # Recommandations
    print("\n" + "="*80)
    print("💡 RECOMMANDATIONS D'AMÉLIORATION")
    print("="*80)

    # Analyse des mauvaises périodes
    if bad_periods:
        bull_losses = sum(1 for p in bad_periods if p['price_change'] > 20 and p['avg_alloc'] < 50)
        fear_underinvest = sum(1 for p in bad_periods if p['avg_fng'] < 30 and p['avg_alloc'] < 70)

        print("\n🎯 Problèmes identifiés:")

        if bull_losses > len(bad_periods) * 0.3:
            print(f"\n1. ❌ VENTE TROP TÔT EN BULL MARKET ({bull_losses} périodes)")
            print("   Solutions:")
            print("   • Augmenter fng_sell_threshold à 80-85 (vendre plus tard)")
            print("   • Augmenter rainbow_sell_threshold à 0.75-0.80")
            print("   • Garder minimum 20-30% même en GREED extrême")

        if fear_underinvest > len(bad_periods) * 0.3:
            print(f"\n2. ❌ PAS ASSEZ AGRESSIF EN FEAR ({fear_underinvest} périodes)")
            print("   Solutions:")
            print("   • Diminuer fng_buy_threshold à 20-25")
            print("   • Diminuer rainbow_buy_threshold à 0.25")
            print("   • Allocation minimum 50% en FEAR extrême")

        print("\n3. 💡 STRATÉGIE ASYMÉTRIQUE")
        print("   Problème: Actuellement symétrique (moyenne simple)")
        print("   Solution: Être AGRESSIF à l'achat, PATIENT à la vente")
        print("   • Achat: Si FNG < 30 OU Rainbow < 0.3 → Allouer fort")
        print("   • Vente: Seulement si FNG > 80 ET Rainbow > 0.75 → Réduire progressivement")

    print("\n✅ Prochain pas:")
    print("   1. Exécuter: python3 improve_strategy.py")
    print("   2. Tester la stratégie améliorée")
    print("   3. Comparer les résultats")


if __name__ == "__main__":
    main()
