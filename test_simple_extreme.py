#!/usr/bin/env python3
"""
Test d'une stratégie ULTRA-SIMPLE et EXTRÊME

Logique:
- Rainbow < 0.3: 100% BTC (ALL-IN)
- Rainbow > 0.7: 0% BTC (TOUT vendre)
- Entre 0.3-0.7: Interpolation linéaire

SI cette stratégie simple ne bat pas B&H, alors il faut comprendre POURQUOI
"""
import pandas as pd
import numpy as np
from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.strategy import calculate_rainbow_position
from src.fngbt.backtest import run_backtest

def test_extreme_simple_strategy(df):
    """
    Stratégie la plus simple possible:
    - Bas Rainbow = 100%
    - Haut Rainbow = 0%
    """
    print("="*100)
    print("🧪 TEST: Stratégie Ultra-Simple (100% bas, 0% haut)")
    print("="*100)

    # Baseline B&H
    bh = df.copy()
    bh['pos'] = 100.0
    bh['trade'] = 0
    bh_result = run_backtest(bh, fees_bps=0.0)
    bh_equity = bh_result['metrics']['EquityFinal']
    bh_cagr = bh_result['metrics']['CAGR']

    print(f"\n📊 Buy & Hold:")
    print(f"   Equity: {bh_equity:.2f}x")
    print(f"   CAGR: {bh_cagr*100:.1f}%")

    # Stratégie simple
    d = df.copy()
    d = calculate_rainbow_position(d)

    rainbow_pos = d['rainbow_position'].values

    # Allocation: 100% si Rainbow < 0.3, 0% si > 0.7, linéaire entre
    allocation = np.where(
        rainbow_pos <= 0.3,
        100.0,  # 100% en zone basse
        np.where(
            rainbow_pos >= 0.7,
            0.0,  # 0% en zone haute
            # Interpolation linéaire
            100.0 - (100.0 * (rainbow_pos - 0.3) / (0.7 - 0.3))
        )
    )

    d['pos'] = allocation
    d['trade'] = (d['pos'].diff().abs() > 5).astype(int)

    # Backtest SANS frais d'abord
    result_no_fees = run_backtest(d, fees_bps=0.0)
    metrics_no_fees = result_no_fees['metrics']

    # Backtest AVEC frais
    result_with_fees = run_backtest(d, fees_bps=10.0)
    metrics_with_fees = result_with_fees['metrics']

    print(f"\n📊 Stratégie Simple (Rainbow 0.3-0.7):")
    print(f"\n   SANS FRAIS:")
    print(f"      Equity: {metrics_no_fees['EquityFinal']:.2f}x")
    print(f"      CAGR: {metrics_no_fees['CAGR']*100:.1f}%")
    print(f"      Ratio vs B&H: {metrics_no_fees['EquityFinal']/bh_equity:.3f}x")
    print(f"      Max DD: {metrics_no_fees['MaxDD']*100:.1f}%")
    print(f"      Trades: {metrics_no_fees['trades']}")

    print(f"\n   AVEC FRAIS (10 bps):")
    print(f"      Equity: {metrics_with_fees['EquityFinal']:.2f}x")
    print(f"      CAGR: {metrics_with_fees['CAGR']*100:.1f}%")
    print(f"      Ratio vs B&H: {metrics_with_fees['EquityFinal']/bh_equity:.3f}x")
    print(f"      Max DD: {metrics_with_fees['MaxDD']*100:.1f}%")
    print(f"      Trades: {metrics_with_fees['trades']}")

    # Impact des frais
    fees_impact = metrics_no_fees['EquityFinal'] - metrics_with_fees['EquityFinal']
    fees_impact_pct = (fees_impact / metrics_no_fees['EquityFinal']) * 100

    print(f"\n💰 Impact des frais:")
    print(f"   Equity perdue: {fees_impact:.2f}x ({fees_impact_pct:.1f}%)")

    # Analyse détaillée
    print(f"\n🔍 ANALYSE:")

    if metrics_no_fees['EquityFinal'] / bh_equity > 1.0:
        print(f"   ✅ SANS frais, stratégie BAT B&H: {metrics_no_fees['EquityFinal']/bh_equity:.3f}x")
        print(f"   ⚠️  Mais avec frais, sous-performe: {metrics_with_fees['EquityFinal']/bh_equity:.3f}x")
        print(f"   → Les frais ({metrics_with_fees['trades']} trades × 10 bps) mangent {fees_impact_pct:.1f}% de la performance")
    else:
        print(f"   ❌ Même SANS frais, stratégie sous-performe B&H")
        print(f"   → Problème: allocation moyenne trop basse pendant le bull")

    # Calculer allocation moyenne
    avg_allocation = d['pos'].mean()
    print(f"\n📊 Allocation moyenne: {avg_allocation:.1f}%")
    print(f"   → Si allocation moyenne < 100%, on manque des gains sur bull market")

    # Analyser par période
    print(f"\n📅 Allocation par année:")
    for year in range(2018, 2026):
        year_data = d[d['date'].dt.year == year]
        if len(year_data) > 0:
            year_avg = year_data['pos'].mean()
            year_price_start = year_data['close'].iloc[0]
            year_price_end = year_data['close'].iloc[-1]
            year_return = (year_price_end / year_price_start - 1) * 100
            print(f"   {year}: Alloc moyenne {year_avg:.1f}% | BTC return {year_return:+.1f}%")

    # Sauvegarder
    d.to_csv('outputs/extreme_simple_strategy.csv', index=False)
    print(f"\n💾 Détails sauvegardés: outputs/extreme_simple_strategy.csv")

    return d, metrics_with_fees, bh_equity

def verify_backtest_logic(df):
    """
    Vérifier que le backtest fonctionne correctement
    """
    print(f"\n{'='*100}")
    print(f"🔬 VÉRIFICATION DU BACKTEST")
    print(f"{'='*100}")

    # Test 1: 100% constant = B&H
    print(f"\n✅ Test 1: 100% constant doit = B&H")
    d1 = df.copy()
    d1['pos'] = 100.0
    d1['trade'] = 0
    r1 = run_backtest(d1, fees_bps=0.0)

    btc_return = df['close'].iloc[-1] / df['close'].iloc[0]
    backtest_equity = r1['metrics']['EquityFinal']

    print(f"   BTC return brut: {btc_return:.2f}x")
    print(f"   Backtest equity: {backtest_equity:.2f}x")
    print(f"   Match: {'✅ OUI' if abs(btc_return - backtest_equity) < 0.01 else '❌ NON'}")

    # Test 2: 50% constant
    print(f"\n✅ Test 2: 50% constant doit = ~moitié du return")
    d2 = df.copy()
    d2['pos'] = 50.0
    d2['trade'] = 0
    r2 = run_backtest(d2, fees_bps=0.0)

    expected = 1 + (btc_return - 1) * 0.5
    actual = r2['metrics']['EquityFinal']

    print(f"   Attendu: {expected:.2f}x")
    print(f"   Obtenu: {actual:.2f}x")
    print(f"   Match: {'✅ OUI' if abs(expected - actual) < 0.1 else '❌ NON'}")

    # Test 3: Vérifier impact des frais
    print(f"\n✅ Test 3: Impact des frais")
    d3 = df.copy()
    d3['pos'] = 100.0
    d3['trade'] = 0
    r3_no_fees = run_backtest(d3, fees_bps=0.0)
    r3_with_fees = run_backtest(d3, fees_bps=10.0)

    print(f"   Sans frais: {r3_no_fees['metrics']['EquityFinal']:.2f}x")
    print(f"   Avec frais: {r3_with_fees['metrics']['EquityFinal']:.2f}x")
    print(f"   Différence: {r3_no_fees['metrics']['EquityFinal'] - r3_with_fees['metrics']['EquityFinal']:.4f}x")
    print(f"   (Devrait être ~0 car pas de trades)")

    print(f"\n{'='*100}")

if __name__ == "__main__":
    print("Chargement données...")
    fng = load_fng_alt()
    btc = load_btc_prices()
    df = merge_daily(fng, btc)
    print(f"✅ {len(df)} jours\n")

    # Vérifier que le backtest est correct
    verify_backtest_logic(df)

    # Tester stratégie simple
    strategy_df, metrics, bh_equity = test_extreme_simple_strategy(df)

    print(f"\n{'='*100}")
    print(f"💡 CONCLUSION")
    print(f"{'='*100}")

    ratio = metrics['EquityFinal'] / bh_equity

    if ratio > 1.0:
        print(f"\n🎉 VICTOIRE! Stratégie bat B&H: {ratio:.3f}x")
    else:
        print(f"\n⚠️  Stratégie sous-performe: {ratio:.3f}x")
        print(f"\nPourquoi?")
        print(f"1. Allocation moyenne trop basse pendant bull market")
        print(f"2. Frais de trading ({metrics['trades']} trades)")
        print(f"3. Timing imparfait (ne vend pas exactement au top)")
        print(f"\nPour battre B&H, il faudrait:")
        print(f"- Soit des tops/bottoms plus précis")
        print(f"- Soit moins de réduction d'allocation")
        print(f"- Soit une période avec plus de volatilité sideways")
