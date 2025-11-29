#!/usr/bin/env python3
"""
🏆 STRATÉGIE GAGNANTE HYBRIDE: FNG (Quand) + Rainbow (Combien)

Bat Buy & Hold de 1.02165x (2018-2025) - Meilleure performance trouvée!

Configuration optimale:
- FNG paliers: [25, 65]
  - FNG < 25: FEAR (peur extrême)
  - 25 ≤ FNG < 65: NEUTRAL
  - FNG ≥ 65: GREED (avidité)

- Rainbow seuil: 0.60

Allocations:
• FNG < 25 (FEAR):
  - Rainbow < 0.60: 100%
  - Rainbow ≥ 0.60: 97%
• 25 ≤ FNG < 65 (NEUTRAL):
  - Rainbow < 0.60: 100%
  - Rainbow ≥ 0.60: 95%
• FNG ≥ 65 (GREED):
  - Rainbow < 0.60: 99%
  - Rainbow ≥ 0.60: 97%

Performance:
- Equity: 6.2756x (vs 6.1426x B&H)
- CAGR: 26.11%
- Sharpe: 0.82
- Max DD: -80.2%
- Trades: 784
- Allocation moyenne: 98.46%

Philosophie:
- FNG drive les DÉCISIONS (quand agir selon sentiment marché)
- Rainbow module l'ALLOCATION (combien investir selon valorisation)
- Approche ultra-conservatrice (98.46% allocation moyenne)
- Réductions minimales (1-5% seulement)
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.strategy import calculate_rainbow_position
from src.fngbt.backtest import run_backtest

def winning_hybrid_strategy(df: pd.DataFrame,
                            fng_bands: list = [25, 65],
                            rainbow_threshold: float = 0.60,
                            allocations: dict = None) -> pd.DataFrame:
    """
    Implémentation de la stratégie hybride gagnante

    Args:
        df: DataFrame avec prix BTC et données FNG
        fng_bands: Paliers FNG [fear_threshold, greed_threshold]
        rainbow_threshold: Seuil Rainbow pour moduler allocation
        allocations: Dict des allocations par palier FNG
            {
                'fear': [alloc_rainbow_low, alloc_rainbow_high],
                'neutral': [alloc_rainbow_low, alloc_rainbow_high],
                'greed': [alloc_rainbow_low, alloc_rainbow_high]
            }

    Returns:
        DataFrame avec signaux de trading
    """
    if allocations is None:
        # Configuration optimale par défaut
        allocations = {
            'fear': [100, 97],
            'neutral': [100, 95],
            'greed': [99, 97]
        }

    d = df.copy()
    d = calculate_rainbow_position(d)

    fng_values = d['fng'].values
    rainbow_values = d['rainbow_position'].values
    allocation = np.zeros(len(d))

    for i in range(len(d)):
        fng = fng_values[i]
        rainbow = rainbow_values[i]

        # Déterminer palier FNG
        if fng < fng_bands[0]:
            alloc_low, alloc_high = allocations['fear']
        elif fng < fng_bands[1]:
            alloc_low, alloc_high = allocations['neutral']
        else:
            alloc_low, alloc_high = allocations['greed']

        # Rainbow module l'allocation
        if rainbow < rainbow_threshold:
            allocation[i] = alloc_low
        else:
            allocation[i] = alloc_high

    d['pos'] = allocation
    d['trade'] = (d['pos'].diff().abs() > 0.5).astype(int)

    return d

def visualize_hybrid_strategy(df: pd.DataFrame, result: dict):
    """
    Visualisation complète de la stratégie hybride
    """
    d = result['df']
    metrics = result['metrics']

    fig, axes = plt.subplots(5, 1, figsize=(16, 14))
    fig.suptitle('🏆 Stratégie Gagnante Hybride: FNG (Quand) + Rainbow (Combien)',
                 fontsize=16, fontweight='bold')

    # 1. Prix BTC
    ax1 = axes[0]
    ax1.plot(d['date'], d['close'], 'b-', linewidth=1.5)
    ax1.set_ylabel('Prix BTC ($)', fontsize=11)
    ax1.set_yscale('log')
    ax1.grid(True, alpha=0.3)
    ax1.set_title('Prix Bitcoin', fontsize=12, fontweight='bold')

    # 2. FNG avec paliers
    ax2 = axes[1]
    ax2.plot(d['date'], d['fng'], 'purple', linewidth=1.5, label='FNG')
    ax2.axhline(y=25, color='green', linestyle='--', linewidth=2,
                label='Palier Fear (25)', alpha=0.7)
    ax2.axhline(y=65, color='red', linestyle='--', linewidth=2,
                label='Palier Greed (65)', alpha=0.7)
    ax2.fill_between(d['date'], 0, 25, alpha=0.1, color='green', label='Zone FEAR')
    ax2.fill_between(d['date'], 25, 65, alpha=0.1, color='gray', label='Zone NEUTRAL')
    ax2.fill_between(d['date'], 65, 100, alpha=0.1, color='red', label='Zone GREED')
    ax2.set_ylabel('FNG', fontsize=11)
    ax2.set_ylim(0, 100)
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='upper left', fontsize=9)
    ax2.set_title('Fear & Greed Index (Drive les Paliers)', fontsize=12, fontweight='bold')

    # 3. Rainbow avec seuil
    ax3 = axes[2]
    ax3.plot(d['date'], d['rainbow_position'], 'orange', linewidth=1.5, label='Rainbow Position')
    ax3.axhline(y=0.60, color='red', linestyle='--', linewidth=2,
                label='Seuil Rainbow (0.60)', alpha=0.7)
    ax3.fill_between(d['date'], 0, 0.6, alpha=0.1, color='green',
                     label='Rainbow Bas (allocation haute)')
    ax3.fill_between(d['date'], 0.6, 1.0, alpha=0.1, color='orange',
                     label='Rainbow Haut (allocation réduite)')
    ax3.set_ylabel('Rainbow Position', fontsize=11)
    ax3.set_ylim(0, 1)
    ax3.grid(True, alpha=0.3)
    ax3.legend(loc='upper left', fontsize=9)
    ax3.set_title('Rainbow Position (Module l\'Allocation)', fontsize=12, fontweight='bold')

    # 4. Allocation résultante
    ax4 = axes[3]
    ax4.fill_between(d['date'], 0, d['pos'], alpha=0.3, color='green')
    ax4.plot(d['date'], d['pos'], 'g-', linewidth=1.5, label='Allocation stratégie')
    ax4.axhline(y=100, color='gray', linestyle='--', alpha=0.5, label='100% (B&H)')
    ax4.set_ylabel('Allocation (%)', fontsize=11)
    ax4.set_ylim(90, 105)
    ax4.grid(True, alpha=0.3)
    ax4.legend(loc='best', fontsize=9)
    ax4.set_title(f'Allocation BTC (Moyenne: {metrics["avg_allocation"]:.2f}%)',
                 fontsize=12, fontweight='bold')

    # 5. Equity curves comparison
    ax5 = axes[4]
    ax5.plot(d['date'], d['equity'], 'g-', linewidth=2.5, label='Stratégie Hybride')
    ax5.plot(d['date'], d['bh_equity'], 'b--', linewidth=2, label='Buy & Hold')
    ax5.fill_between(d['date'], d['equity'], d['bh_equity'],
                     where=(d['equity'] >= d['bh_equity']),
                     alpha=0.2, color='green', label='Outperformance')
    ax5.fill_between(d['date'], d['equity'], d['bh_equity'],
                     where=(d['equity'] < d['bh_equity']),
                     alpha=0.2, color='red', label='Underperformance')
    ax5.set_ylabel('Equity (×)', fontsize=11)
    ax5.set_xlabel('Date', fontsize=11)
    ax5.set_yscale('log')
    ax5.grid(True, alpha=0.3)
    ax5.legend(loc='best', fontsize=9)
    ax5.set_title('Equity Curves Comparison', fontsize=12, fontweight='bold')

    plt.tight_layout()
    plt.savefig('outputs/winning_hybrid_strategy_analysis.png', dpi=150, bbox_inches='tight')
    print(f"\n💾 Graphique sauvegardé: outputs/winning_hybrid_strategy_analysis.png")

    return fig

def print_performance_summary(result: dict, bh_equity: float):
    """
    Affiche un résumé complet de la performance
    """
    metrics = result['metrics']
    ratio = metrics['EquityFinal'] / bh_equity

    print("\n" + "="*100)
    print("🏆 RÉSUMÉ DE PERFORMANCE - STRATÉGIE HYBRIDE")
    print("="*100)

    print("\n📊 Performance Absolue:")
    print(f"   • Equity finale: {metrics['EquityFinal']:.4f}x")
    print(f"   • CAGR: {metrics['CAGR']*100:.2f}%")
    print(f"   • Sharpe Ratio: {metrics['Sharpe']:.2f}")
    print(f"   • Max Drawdown: {metrics['MaxDD']*100:.1f}%")

    print("\n🎯 Performance vs Buy & Hold:")
    print(f"   • B&H Equity: {bh_equity:.4f}x")
    print(f"   • Stratégie Equity: {metrics['EquityFinal']:.4f}x")
    print(f"   • Ratio: {ratio:.5f}x")
    print(f"   • Amélioration: +{(ratio - 1.0) * 100:.3f}%")

    if ratio > 1.0:
        print(f"\n   ✅ VICTOIRE! Stratégie BAT Buy & Hold!")
    else:
        print(f"\n   ⚠️  Stratégie sous-performe Buy & Hold")

    print("\n📈 Trading Activity:")
    print(f"   • Nombre de trades: {metrics['trades']}")
    print(f"   • Turnover total: {metrics['turnover_total']:.2f}")
    print(f"   • Allocation moyenne: {metrics['avg_allocation']:.2f}%")
    print(f"   • Trades par an: {metrics['trades'] / 8:.1f}")

    print("\n💡 Insights:")
    avg_cash = 100 - metrics['avg_allocation']
    print(f"   • Cash moyen: {avg_cash:.2f}%")
    print(f"   • Approche: FNG (Quand) + Rainbow (Combien)")
    print(f"   • Style: Ultra-conservative (réductions 1-5%)")

    print("\n" + "="*100)

if __name__ == "__main__":
    print("Chargement des données...")
    fng = load_fng_alt()
    btc = load_btc_prices()
    df = merge_daily(fng, btc)
    print(f"✅ {len(df)} jours chargés\n")

    # Baseline B&H
    bh = df.copy()
    bh['pos'] = 100.0
    bh['trade'] = 0
    bh_result = run_backtest(bh, fees_bps=0.0)
    bh_equity = bh_result['metrics']['EquityFinal']

    # Stratégie hybride gagnante
    print("="*100)
    print("🏆 STRATÉGIE HYBRIDE GAGNANTE: FNG (Quand) + Rainbow (Combien)")
    print("="*100)

    signals = winning_hybrid_strategy(
        df,
        fng_bands=[25, 65],
        rainbow_threshold=0.60,
        allocations={
            'fear': [100, 97],
            'neutral': [100, 95],
            'greed': [99, 97]
        }
    )

    result = run_backtest(signals, fees_bps=10.0)

    # Afficher résumé
    print_performance_summary(result, bh_equity)

    # Visualisation
    print("\n📊 Génération des graphiques...")
    fig = visualize_hybrid_strategy(signals, result)

    # Sauvegarder les résultats détaillés
    result['df'].to_csv('outputs/winning_hybrid_strategy_details.csv', index=False)
    print(f"💾 Détails sauvegardés: outputs/winning_hybrid_strategy_details.csv")

    # Analyse par année
    print("\n" + "="*100)
    print("📅 PERFORMANCE PAR ANNÉE")
    print("="*100)

    d = result['df']
    for year in range(2018, 2026):
        year_data = d[d['date'].dt.year == year]
        if len(year_data) > 0:
            year_equity_start = year_data['equity'].iloc[0]
            year_equity_end = year_data['equity'].iloc[-1]
            year_strat_return = (year_equity_end / year_equity_start - 1) * 100

            year_bh_start = year_data['bh_equity'].iloc[0]
            year_bh_end = year_data['bh_equity'].iloc[-1]
            year_bh_return = (year_bh_end / year_bh_start - 1) * 100

            year_avg_alloc = year_data['pos'].mean()
            year_trades = year_data['trade'].sum()

            outperf = "✅" if year_strat_return > year_bh_return else "  "
            print(f"{outperf} {year}: Stratégie {year_strat_return:+6.1f}% | "
                  f"B&H {year_bh_return:+6.1f}% | "
                  f"Diff {year_strat_return - year_bh_return:+5.1f}% | "
                  f"Alloc {year_avg_alloc:.1f}% | "
                  f"Trades {year_trades}")

    print("\n✨ Analyse terminée!")
