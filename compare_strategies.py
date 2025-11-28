#!/usr/bin/env python3
"""
Compare l'ancienne stratégie vs la stratégie améliorée

Affiche côte à côte:
- Métriques de performance
- Comportement dans différentes conditions de marché
- Graphiques comparatifs
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.strategy import StrategyConfig, build_signals
from src.fngbt.strategy_improved import ImprovedStrategyConfig, build_improved_signals
from src.fngbt.backtest import run_backtest


def compare_strategies():
    """Compare les deux versions de la stratégie"""

    print("="*80)
    print("⚔️  COMPARAISON: Ancienne vs Nouvelle Stratégie")
    print("="*80)

    # Chargement données
    print("\n📊 Chargement des données...")
    fng = load_fng_alt()
    btc = load_btc_prices()
    df = merge_daily(fng, btc)
    print(f"✅ {len(df)} jours chargés ({df['date'].min().date()} → {df['date'].max().date()})")

    # ========================================================================
    # ANCIENNE STRATÉGIE
    # ========================================================================
    print("\n" + "="*80)
    print("📊 ANCIENNE STRATÉGIE (Simple)")
    print("="*80)

    old_cfg = StrategyConfig(
        fng_buy_threshold=25,
        fng_sell_threshold=75,
        rainbow_buy_threshold=0.3,
        rainbow_sell_threshold=0.7,
        min_position_change_pct=10.0
    )

    print(f"\nParamètres:")
    print(f"   FNG Buy: {old_cfg.fng_buy_threshold} | Sell: {old_cfg.fng_sell_threshold}")
    print(f"   Rainbow Buy: {old_cfg.rainbow_buy_threshold} | Sell: {old_cfg.rainbow_sell_threshold}")
    print(f"   Logique: Moyenne simple FNG + Rainbow")

    old_signals = build_signals(df, old_cfg)
    old_result = run_backtest(old_signals, fees_bps=10.0)
    old_metrics = old_result['metrics']

    print(f"\nRésultats:")
    print(f"   Equity Finale:   {old_metrics['EquityFinal']:.2f}x")
    print(f"   B&H Equity:      {old_metrics['BHEquityFinal']:.2f}x")
    print(f"   Ratio vs B&H:    {old_metrics['EquityFinal']/old_metrics['BHEquityFinal']:.3f}x")
    print(f"   CAGR:            {old_metrics['CAGR']*100:.1f}%")
    print(f"   Max DD:          {old_metrics['MaxDD']*100:.1f}%")
    print(f"   Sharpe:          {old_metrics['Sharpe']:.2f}")
    print(f"   Trades:          {old_metrics['trades']}")

    # ========================================================================
    # NOUVELLE STRATÉGIE
    # ========================================================================
    print("\n" + "="*80)
    print("🚀 NOUVELLE STRATÉGIE (Améliorée - Investisseur)")
    print("="*80)

    new_cfg = ImprovedStrategyConfig(
        # Zones FNG (plus fines)
        fng_extreme_fear=20,
        fng_fear=35,
        fng_neutral_low=45,
        fng_neutral_high=65,
        fng_greed=80,
        fng_extreme_greed=90,

        # Zones Rainbow (plus fines)
        rainbow_extreme_low=0.2,
        rainbow_low=0.35,
        rainbow_mid_low=0.45,
        rainbow_mid_high=0.65,
        rainbow_high=0.75,
        rainbow_extreme_high=0.85,

        # Allocation
        min_allocation_pct=20,  # TOUJOURS au moins 20%
        max_allocation_pct=100,
        neutral_allocation_pct=60,

        # Logique
        buy_logic_or=True,   # OR pour acheter (agressif)
        sell_logic_and=True,  # AND pour vendre (patient)

        min_position_change_pct=10.0
    )

    print(f"\nParamètres:")
    print(f"   FNG Zones: {new_cfg.fng_extreme_fear}/{new_cfg.fng_fear}/{new_cfg.fng_greed}/{new_cfg.fng_extreme_greed}")
    print(f"   Rainbow Zones: {new_cfg.rainbow_extreme_low:.2f}/{new_cfg.rainbow_low:.2f}/{new_cfg.rainbow_high:.2f}/{new_cfg.rainbow_extreme_high:.2f}")
    print(f"   Allocation: {new_cfg.min_allocation_pct}% → {new_cfg.max_allocation_pct}%")
    print(f"   Logique: OR pour acheter (agressif), AND pour vendre (patient)")

    new_signals = build_improved_signals(df, new_cfg)
    new_result = run_backtest(new_signals, fees_bps=10.0)
    new_metrics = new_result['metrics']

    print(f"\nRésultats:")
    print(f"   Equity Finale:   {new_metrics['EquityFinal']:.2f}x")
    print(f"   B&H Equity:      {new_metrics['BHEquityFinal']:.2f}x")
    print(f"   Ratio vs B&H:    {new_metrics['EquityFinal']/new_metrics['BHEquityFinal']:.3f}x")
    print(f"   CAGR:            {new_metrics['CAGR']*100:.1f}%")
    print(f"   Max DD:          {new_metrics['MaxDD']*100:.1f}%")
    print(f"   Sharpe:          {new_metrics['Sharpe']:.2f}")
    print(f"   Trades:          {new_metrics['trades']}")

    # ========================================================================
    # COMPARAISON
    # ========================================================================
    print("\n" + "="*80)
    print("📊 COMPARAISON DÉTAILLÉE")
    print("="*80)

    improvements = {
        'Equity Finale': (new_metrics['EquityFinal'] - old_metrics['EquityFinal']) / old_metrics['EquityFinal'] * 100,
        'Ratio vs B&H': (new_metrics['EquityFinal']/new_metrics['BHEquityFinal'] - old_metrics['EquityFinal']/old_metrics['BHEquityFinal']) / (old_metrics['EquityFinal']/old_metrics['BHEquityFinal']) * 100,
        'CAGR': (new_metrics['CAGR'] - old_metrics['CAGR']) / old_metrics['CAGR'] * 100,
        'Max DD': (new_metrics['MaxDD'] - old_metrics['MaxDD']) / abs(old_metrics['MaxDD']) * 100,
        'Sharpe': (new_metrics['Sharpe'] - old_metrics['Sharpe']) / old_metrics['Sharpe'] * 100,
    }

    print("\nAméliorations (Nouvelle vs Ancienne):")
    for metric, improvement in improvements.items():
        sign = "✅" if improvement > 0 else "❌"
        if metric == "Max DD":
            # Pour Max DD, une augmentation est mauvaise
            sign = "✅" if improvement < 0 else "❌"
        print(f"   {metric:15s}: {improvement:+6.1f}% {sign}")

    # Analyser les comportements dans différentes conditions
    print("\n" + "="*80)
    print("🔍 COMPORTEMENT PAR CONDITION DE MARCHÉ")
    print("="*80)

    conditions = [
        ("FEAR extrême (FNG < 20)", df['fng'] < 20),
        ("FEAR (FNG 20-35)", (df['fng'] >= 20) & (df['fng'] < 35)),
        ("Neutre (FNG 45-65)", (df['fng'] >= 45) & (df['fng'] <= 65)),
        ("GREED (FNG 65-80)", (df['fng'] > 65) & (df['fng'] <= 80)),
        ("GREED extrême (FNG > 80)", df['fng'] > 80),
    ]

    for condition_name, mask in conditions:
        if mask.sum() == 0:
            continue

        old_alloc = old_signals[mask]['pos'].mean()
        new_alloc = new_signals[mask]['pos'].mean()
        days = mask.sum()

        print(f"\n{condition_name} ({days} jours):")
        print(f"   Ancienne allocation moyenne: {old_alloc:.1f}%")
        print(f"   Nouvelle allocation moyenne: {new_alloc:.1f}%")
        print(f"   Différence: {new_alloc - old_alloc:+.1f}%")

    # ========================================================================
    # GRAPHIQUES COMPARATIFS
    # ========================================================================
    print("\n📊 Génération des graphiques comparatifs...")

    fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True)
    fig.suptitle('Comparaison Ancienne vs Nouvelle Stratégie', fontsize=16, fontweight='bold')

    dates = pd.to_datetime(df['date'])

    # Graphique 1: Allocations
    ax1 = axes[0]
    ax1.plot(dates, old_signals['pos'], 'b-', alpha=0.7, linewidth=1.5, label='Ancienne Stratégie')
    ax1.plot(dates, new_signals['pos'], 'g-', alpha=0.8, linewidth=2, label='Nouvelle Stratégie')
    ax1.axhline(new_cfg.min_allocation_pct, color='red', linestyle='--', alpha=0.5, label=f'Min {new_cfg.min_allocation_pct}%')
    ax1.set_ylabel('Allocation BTC (%)', fontweight='bold')
    ax1.set_title('Allocation au fil du temps', fontweight='bold')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(0, 105)

    # Graphique 2: Equity curves
    ax2 = axes[1]
    ax2.plot(dates, old_result['df']['equity'], 'b-', alpha=0.7, linewidth=1.5, label='Ancienne Stratégie')
    ax2.plot(dates, new_result['df']['equity'], 'g-', alpha=0.8, linewidth=2, label='Nouvelle Stratégie')
    ax2.plot(dates, old_result['df']['bh_equity'], 'gray', alpha=0.7, linewidth=1.5, linestyle='--', label='Buy & Hold')
    ax2.set_ylabel('Equity (x)', fontweight='bold')
    ax2.set_title('Performance cumulée', fontweight='bold')
    ax2.legend(loc='upper left')
    ax2.grid(True, alpha=0.3)

    # Graphique 3: Écart de performance
    ax3 = axes[2]
    old_ratio = old_result['df']['equity'] / old_result['df']['bh_equity']
    new_ratio = new_result['df']['equity'] / new_result['df']['bh_equity']
    ax3.plot(dates, old_ratio, 'b-', alpha=0.7, linewidth=1.5, label='Ancienne / B&H')
    ax3.plot(dates, new_ratio, 'g-', alpha=0.8, linewidth=2, label='Nouvelle / B&H')
    ax3.axhline(1.0, color='red', linestyle='--', alpha=0.5, label='Break-even vs B&H')
    ax3.set_ylabel('Ratio vs B&H', fontweight='bold')
    ax3.set_xlabel('Date', fontweight='bold')
    ax3.set_title('Performance relative vs Buy & Hold', fontweight='bold')
    ax3.legend(loc='upper left')
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()

    # Sauvegarde
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    filename = f"outputs/strategy_comparison_{timestamp}.png"
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    print(f"✅ Graphiques sauvegardés: {filename}")

    plt.show()

    # ========================================================================
    # VERDICT FINAL
    # ========================================================================
    print("\n" + "="*80)
    print("🎯 VERDICT FINAL")
    print("="*80)

    new_better = new_metrics['EquityFinal'] / new_metrics['BHEquityFinal'] > old_metrics['EquityFinal'] / old_metrics['BHEquityFinal']

    if new_better:
        improvement_pct = improvements['Ratio vs B&H']
        print(f"\n✅ La NOUVELLE stratégie est MEILLEURE (+{improvement_pct:.1f}%)")
        print("\nAvantages clés:")
        print("   • Allocation minimale de 20% (ne rate jamais complètement un bull)")
        print("   • Logique OR pour acheter (plus agressif en FEAR)")
        print("   • Zones progressives (pas de seuils binaires)")
        print("   • Plus patient pour vendre (garde plus longtemps)")
    else:
        print(f"\n⚠️  L'ancienne stratégie reste meilleure")
        print("   Mais les améliorations conceptuelles sont valides")
        print("   → Essayer d'optimiser les paramètres de la nouvelle stratégie")

    print("\n💡 Prochaines étapes:")
    print("   1. Si meilleure: Optimiser les paramètres de la nouvelle stratégie")
    print("   2. Tester différentes valeurs de min_allocation_pct (15%, 20%, 25%)")
    print("   3. Ajuster les zones FNG et Rainbow")
    print("   4. Valider avec Walk-Forward CV")


if __name__ == "__main__":
    compare_strategies()
