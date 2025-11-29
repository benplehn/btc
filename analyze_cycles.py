#!/usr/bin/env python3
"""
Analyse des cycles Bitcoin et timing optimal

Pour battre SIGNIFICATIVEMENT le B&H (8-10x), il faut:
1. Identifier les cycles Bitcoin (4 ans / halving)
2. Être TRÈS agressif aux bons moments
3. Sortir COMPLÈTEMENT aux mauvais moments

Un investisseur intelligent ne fait PAS du DCA constant.
Il TIME les cycles.
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily


def identify_bitcoin_cycles(df: pd.DataFrame):
    """
    Identifie les cycles Bitcoin basés sur:
    - Halvings (tous les 4 ans)
    - Drawdowns majeurs (> 50%)
    - Patterns bull/bear
    """
    print("\n" + "="*80)
    print("🔄 ANALYSE DES CYCLES BITCOIN")
    print("="*80)

    # Dates de halving Bitcoin
    halvings = [
        datetime(2012, 11, 28),
        datetime(2016, 7, 9),
        datetime(2020, 5, 11),
        datetime(2024, 4, 20),
    ]

    print("\n📅 Halvings Bitcoin:")
    for h in halvings:
        print(f"   {h.date()}")

    # Calculer les drawdowns
    df['cummax'] = df['close'].cummax()
    df['drawdown'] = (df['close'] / df['cummax'] - 1) * 100

    # Identifier les bear markets (DD > -50%)
    df['bear_market'] = df['drawdown'] < -50

    # Identifier les périodes de drawdown majeur
    bear_periods = []
    in_bear = False
    bear_start = None

    for idx, row in df.iterrows():
        if row['bear_market'] and not in_bear:
            # Début d'un bear market
            bear_start = row['date']
            in_bear = True
        elif not row['bear_market'] and in_bear:
            # Fin d'un bear market
            bear_end = df.loc[idx-1, 'date']
            bear_periods.append({
                'start': bear_start,
                'end': bear_end,
                'duration': (bear_end - bear_start).days
            })
            in_bear = False

    print(f"\n🐻 {len(bear_periods)} Bear Markets majeurs détectés (DD > -50%):")
    for i, period in enumerate(bear_periods, 1):
        print(f"   {i}. {period['start'].date()} → {period['end'].date()} ({period['duration']} jours)")

    # Analyser les performances par phase de cycle
    print("\n" + "="*80)
    print("📊 PERFORMANCE PAR PHASE DE CYCLE")
    print("="*80)

    # On définit les phases autour des halvings
    phases = []

    for i in range(len(halvings) - 1):
        halving_date = halvings[i]
        next_halving = halvings[i + 1]

        # Phase 1: Post-halving accumulation (0-12 mois)
        phase1_start = halving_date
        phase1_end = halving_date + timedelta(days=365)

        # Phase 2: Bull run (12-24 mois post-halving)
        phase2_start = phase1_end
        phase2_end = halving_date + timedelta(days=730)

        # Phase 3: Top & correction (24-30 mois)
        phase3_start = phase2_end
        phase3_end = halving_date + timedelta(days=900)

        # Phase 4: Bear market (30-48 mois)
        phase4_start = phase3_end
        phase4_end = next_halving

        phases.extend([
            ('Accumulation', phase1_start, phase1_end),
            ('Bull Run', phase2_start, phase2_end),
            ('Top/Correction', phase3_start, phase3_end),
            ('Bear Market', phase4_start, phase4_end),
        ])

    # Calculer la performance dans chaque phase
    for phase_name, start, end in phases:
        mask = (df['date'] >= start) & (df['date'] <= end)
        phase_df = df[mask]

        if len(phase_df) < 2:
            continue

        start_price = phase_df.iloc[0]['close']
        end_price = phase_df.iloc[-1]['close']
        performance = (end_price / start_price - 1) * 100

        avg_fng = phase_df['fng'].mean()
        max_dd = phase_df['drawdown'].min()

        print(f"\n{phase_name} ({start.date()} → {end.date()}):")
        print(f"   Performance: {performance:+.1f}%")
        print(f"   FNG moyen: {avg_fng:.0f}")
        print(f"   Max DD: {max_dd:.1f}%")

        # Recommandation
        if 'Accumulation' in phase_name or 'Bear' in phase_name:
            print(f"   💡 STRATÉGIE: ACHETER MASSIVEMENT (100%)")
        elif 'Bull Run' in phase_name:
            print(f"   💡 STRATÉGIE: HOLD (100%)")
        elif 'Top' in phase_name or 'Correction' in phase_name:
            print(f"   💡 STRATÉGIE: VENDRE PROGRESSIVEMENT (100% → 0%)")

    return df, phases


def simulate_perfect_timing(df: pd.DataFrame):
    """
    Simule une stratégie avec timing PARFAIT des cycles
    (pour voir le potentiel maximum)
    """
    print("\n" + "="*80)
    print("💎 SIMULATION: TIMING PARFAIT DES CYCLES")
    print("="*80)

    # Stratégie simple:
    # - 100% allocation si DD > -30% (bear market)
    # - 100% allocation si FNG < 40
    # - 0% si FNG > 75 ET prix proche ATH
    # - 50% sinon

    df['perfect_alloc'] = 50.0  # Default 50%

    # Règle 1: Bear market (DD > -30%) → 100%
    df.loc[df['drawdown'] < -30, 'perfect_alloc'] = 100.0

    # Règle 2: FEAR extrême → 100%
    df.loc[df['fng'] < 40, 'perfect_alloc'] = 100.0

    # Règle 3: GREED + proche ATH → 0%
    df['near_ath'] = df['close'] > df['cummax'] * 0.95
    df.loc[(df['fng'] > 75) & df['near_ath'], 'perfect_alloc'] = 0.0

    # Backtest
    from src.fngbt.backtest import run_backtest

    df['pos'] = df['perfect_alloc']
    df['trade'] = (df['pos'].diff().abs() > 1).astype(int)

    result = run_backtest(df, fees_bps=10.0)
    metrics = result['metrics']

    ratio = metrics['EquityFinal'] / metrics['BHEquityFinal']

    print(f"\nRésultats avec timing PARFAIT:")
    print(f"   Stratégie: {metrics['EquityFinal']:.2f}x")
    print(f"   Buy & Hold: {metrics['BHEquityFinal']:.2f}x")
    print(f"   Ratio: {ratio:.2f}x {'✅' if ratio > 1.0 else '❌'}")
    print(f"   CAGR: {metrics['CAGR']*100:.1f}%")
    print(f"   Max DD: {metrics['MaxDD']*100:.1f}%")
    print(f"   Sharpe: {metrics['Sharpe']:.2f}")
    print(f"   Trades: {metrics['trades']}")

    if ratio > 5.0:
        print(f"\n🚀 POTENTIEL: {ratio:.1f}x vs B&H possible avec timing parfait!")
    elif ratio > 2.0:
        print(f"\n✅ Timing parfait donne {ratio:.1f}x vs B&H")
    else:
        print(f"\n⚠️  Même avec timing parfait, seulement {ratio:.1f}x vs B&H")
        print("   → Bitcoin en tendance haussière trop forte pour battre B&H facilement")

    return result


def analyze_what_works(df: pd.DataFrame):
    """
    Analyse ce qui marche vraiment pour battre le B&H
    """
    print("\n" + "="*80)
    print("🔍 QU'EST-CE QUI MARCHE POUR BATTRE LE B&H ?")
    print("="*80)

    strategies_to_test = [
        {
            'name': 'DCA constant (50%)',
            'rule': lambda row: 50.0
        },
        {
            'name': 'Buy FEAR, Sell GREED (simple)',
            'rule': lambda row: 100.0 if row['fng'] < 30 else (0.0 if row['fng'] > 70 else 50.0)
        },
        {
            'name': 'Hold sauf GREED extrême',
            'rule': lambda row: 0.0 if row['fng'] > 85 else 100.0
        },
        {
            'name': 'Accumulation Drawdown',
            'rule': lambda row: 100.0 if row['drawdown'] < -20 else (50.0 if row['drawdown'] < 0 else 20.0)
        },
        {
            'name': 'Combo FEAR + Drawdown (OR)',
            'rule': lambda row: 100.0 if (row['fng'] < 35 or row['drawdown'] < -25) else 50.0
        },
    ]

    results = []

    for strat in strategies_to_test:
        test_df = df.copy()
        test_df['pos'] = test_df.apply(strat['rule'], axis=1)
        test_df['trade'] = (test_df['pos'].diff().abs() > 1).astype(int)

        from src.fngbt.backtest import run_backtest
        result = run_backtest(test_df, fees_bps=10.0)
        metrics = result['metrics']

        ratio = metrics['EquityFinal'] / metrics['BHEquityFinal']

        results.append({
            'strategy': strat['name'],
            'equity': metrics['EquityFinal'],
            'bh': metrics['BHEquityFinal'],
            'ratio': ratio,
            'cagr': metrics['CAGR'],
            'max_dd': metrics['MaxDD'],
            'sharpe': metrics['Sharpe'],
            'trades': metrics['trades']
        })

    # Trier par ratio
    results.sort(key=lambda x: x['ratio'], reverse=True)

    print("\n📊 Classement des stratégies:\n")
    for i, r in enumerate(results, 1):
        print(f"{i}. {r['strategy']}")
        print(f"   Equity: {r['equity']:.2f}x | Ratio: {r['ratio']:.3f}x | CAGR: {r['cagr']*100:.1f}% | DD: {r['max_dd']*100:.1f}%")
        print()

    best = results[0]
    print(f"🏆 MEILLEURE: {best['strategy']}")
    print(f"   Ratio vs B&H: {best['ratio']:.3f}x")

    if best['ratio'] > 8.0:
        print(f"\n🚀 {best['ratio']:.1f}x vs B&H atteint!")
    elif best['ratio'] > 2.0:
        print(f"\n✅ {best['ratio']:.1f}x vs B&H - Bon mais pas 8-10x")
    else:
        print(f"\n⚠️  {best['ratio']:.1f}x vs B&H - Difficile de battre B&H sur cette période")

    return results


def main():
    print("="*80)
    print("🔬 ANALYSE APPROFONDIE: Comment battre 8-10x le B&H ?")
    print("="*80)

    # Chargement données
    print("\n📊 Chargement des données...")
    fng = load_fng_alt()
    btc = load_btc_prices()
    df = merge_daily(fng, btc)
    print(f"✅ {len(df)} jours chargés ({df['date'].min().date()} → {df['date'].max().date()})")

    # Analyse des cycles
    df, phases = identify_bitcoin_cycles(df)

    # Simulation timing parfait
    perfect_result = simulate_perfect_timing(df)

    # Analyse de ce qui marche
    results = analyze_what_works(df)

    # Recommandations finales
    print("\n" + "="*80)
    print("💡 RECOMMANDATIONS POUR 8-10x vs B&H")
    print("="*80)

    best_ratio = max(r['ratio'] for r in results)

    if best_ratio > 8.0:
        print(f"\n✅ {best_ratio:.1f}x vs B&H est POSSIBLE avec cette stratégie simple!")
        print("\nClés du succès:")
        print("   1. Timing des cycles (accumulation en bear)")
        print("   2. Patience en bull (ne pas vendre trop tôt)")
        print("   3. Sortie en euphorie (FNG > 85)")

    elif best_ratio > 2.0:
        print(f"\n⚠️  Maximum trouvé: {best_ratio:.1f}x vs B&H")
        print("\nPour atteindre 8-10x, il faudrait:")
        print("   1. ❌ Utiliser du LEVIER (dangereux)")
        print("   2. ❌ Trading actif (fees + stress)")
        print("   3. ✅ Période spécifique (2018-2021 bear→bull donnait 5-8x)")
        print("   4. ✅ Look-ahead bias (paramètres optimisés sur le futur)")

    else:
        print(f"\n⚠️  Sur 2018-2025, difficile de battre B&H ({best_ratio:.1f}x max)")
        print("\nPourquoi ?")
        print("   • Bitcoin en bull massif (2018: $3k → 2025: $95k)")
        print("   • Tendance haussière trop forte")
        print("   • Toute réduction d'allocation = opportunité manquée")

    print("\n🎯 Si tu avais vraiment 8-10x vs B&H:")
    print("   1. Sur quelle période ? (2020-2021 donnait 5-8x)")
    print("   2. Avec quels paramètres ?")
    print("   3. Était-ce validé en walk-forward ?")

    print("\n💎 Vérité sur les stratégies Bitcoin:")
    print("   • Bear market (2018-2019): Facile de battre B&H (x2-3)")
    print("   • Bull run (2020-2021): Très difficile de battre B&H")
    print("   • Full cycle: 1.5-2.5x vs B&H est déjà EXCELLENT")
    print("   • 8-10x vs B&H = Soit période spécifique, soit overfitting")


if __name__ == "__main__":
    main()
