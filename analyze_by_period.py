#!/usr/bin/env python3
"""
Analyse par période pour comprendre où les stratégies performent vs B&H
"""
import pandas as pd
import numpy as np
from datetime import datetime
from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.strategy import StrategyConfig, build_signals
from src.fngbt.strategy_improved import ImprovedStrategyConfig, build_improved_signals
from src.fngbt.backtest import run_backtest

def analyze_by_period(df: pd.DataFrame):
    """Analyse performance par période clé de Bitcoin"""

    periods = [
        ("2018 Bear Market", "2018-02-01", "2018-12-31"),
        ("2019 Recovery", "2019-01-01", "2019-12-31"),
        ("2020 Bull Start", "2020-01-01", "2020-12-31"),
        ("2021 Peak", "2021-01-01", "2021-12-31"),
        ("2022 Bear", "2022-01-01", "2022-12-31"),
        ("2023 Recovery", "2023-01-01", "2023-12-31"),
        ("2024-2025 Bull", "2024-01-01", "2025-11-28"),
        ("Full Period", "2018-02-01", "2025-11-28"),
    ]

    print("="*100)
    print("📊 ANALYSE PAR PÉRIODE: Où les stratégies battent-elles le B&H?")
    print("="*100)

    # Stratégie Simple
    simple_cfg = StrategyConfig(
        fng_buy_threshold=25,
        fng_sell_threshold=75,
        rainbow_buy_threshold=0.3,
        rainbow_sell_threshold=0.7,
        min_position_change_pct=10.0
    )

    # Stratégie Améliorée
    improved_cfg = ImprovedStrategyConfig(
        fng_extreme_fear=20,
        fng_fear=35,
        fng_greed=80,
        fng_extreme_greed=90,
        min_allocation_pct=20,
        buy_logic_or=True,
        sell_logic_and=True,
        min_position_change_pct=10.0
    )

    results = []

    for period_name, start, end in periods:
        # Filter data for period
        period_df = df[(df['date'] >= start) & (df['date'] <= end)].copy().reset_index(drop=True)

        if len(period_df) < 30:
            continue

        # Buy & Hold
        bh_df = period_df.copy()
        bh_df['pos'] = 100.0
        bh_df['trade'] = 0
        bh_result = run_backtest(bh_df, fees_bps=0.0)
        bh_equity = bh_result['metrics']['EquityFinal']
        bh_cagr = bh_result['metrics']['CAGR']

        # Stratégie Simple
        simple_signals = build_signals(period_df, simple_cfg)
        simple_result = run_backtest(simple_signals, fees_bps=10.0)
        simple_equity = simple_result['metrics']['EquityFinal']
        simple_ratio = simple_equity / bh_equity

        # Stratégie Améliorée
        improved_signals = build_improved_signals(period_df, improved_cfg)
        improved_result = run_backtest(improved_signals, fees_bps=10.0)
        improved_equity = improved_result['metrics']['EquityFinal']
        improved_ratio = improved_equity / bh_equity

        results.append({
            'period': period_name,
            'days': len(period_df),
            'btc_return': (period_df['close'].iloc[-1] / period_df['close'].iloc[0] - 1) * 100,
            'bh_equity': bh_equity,
            'bh_cagr': bh_cagr * 100,
            'simple_ratio': simple_ratio,
            'improved_ratio': improved_ratio,
            'best_ratio': max(simple_ratio, improved_ratio),
            'best_strategy': 'Simple' if simple_ratio > improved_ratio else 'Améliorée'
        })

    # Affichage
    print("\n{:<20} {:>8} {:>12} {:>12} {:>12} {:>12} {:>15}".format(
        "Période", "Jours", "BTC %", "B&H CAGR", "Simple", "Améliorée", "Meilleure"
    ))
    print("-" * 100)

    for r in results:
        marker = "✅" if r['best_ratio'] > 1.0 else "❌"
        print("{:<20} {:>8} {:>11.1f}% {:>11.1f}% {:>11.2f}x {:>11.2f}x {:>15} {}".format(
            r['period'],
            r['days'],
            r['btc_return'],
            r['bh_cagr'],
            r['simple_ratio'],
            r['improved_ratio'],
            r['best_strategy'],
            marker
        ))

    # Analyse
    print("\n" + "="*100)
    print("🔍 ANALYSE")
    print("="*100)

    winning_periods = [r for r in results if r['best_ratio'] > 1.0]

    if winning_periods:
        print(f"\n✅ Périodes où une stratégie BAT le B&H:")
        for r in winning_periods:
            print(f"   • {r['period']}: {r['best_strategy']} = {r['best_ratio']:.2f}x vs B&H")
    else:
        print("\n❌ AUCUNE période où une stratégie bat le B&H!")

    print(f"\n📊 Statistiques:")
    print(f"   • Périodes testées: {len(results)}")
    print(f"   • Périodes gagnantes: {len(winning_periods)}")
    print(f"   • Taux de réussite: {len(winning_periods)/len(results)*100:.1f}%")

    # Meilleure performance
    best = max(results, key=lambda x: x['best_ratio'])
    print(f"\n🏆 Meilleure performance:")
    print(f"   • Période: {best['period']}")
    print(f"   • Stratégie: {best['best_strategy']}")
    print(f"   • Ratio: {best['best_ratio']:.2f}x vs B&H")
    print(f"   • BTC return: {best['btc_return']:.1f}%")

    # Explication
    print("\n" + "="*100)
    print("💡 EXPLICATION")
    print("="*100)
    print("""
Sur 2018-2025, Bitcoin a été majoritairement HAUSSIER:
   • 2018: Bear -73%
   • 2019-2025: Bull massif +3400%

Sur un marché HAUSSIER fort, toute réduction d'allocation = opportunité manquée.

Les stratégies qui vendent (même partiellement) sous-performent car:
   1. Elles sortent pendant les rallyes (FNG élevé)
   2. Elles manquent les pumps verticaux
   3. Les frais de trading grèvent la performance

Pour BATTRE le B&H, il faudrait:
   1. Une période BEAR→BULL (ex: 2018-2021 uniquement)
   2. Timing parfait des tops et bottoms
   3. Ou un marché sideways/range-bound

Sur un bull massif comme 2018-2025: B&H est roi 👑
    """)

if __name__ == "__main__":
    print("Chargement des données...")
    fng = load_fng_alt()
    btc = load_btc_prices()
    df = merge_daily(fng, btc)
    print(f"✅ {len(df)} jours chargés\n")

    analyze_by_period(df)
