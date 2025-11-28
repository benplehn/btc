"""
Visualisation complète de la stratégie Bitcoin

Graphiques:
- Prix BTC avec Rainbow Chart
- Fear & Greed Index
- Allocation de la stratégie
- Equity curves (Stratégie vs Buy&Hold)
- Trades et métriques
"""
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np
from datetime import datetime


def plot_strategy_results(df: pd.DataFrame, metrics: dict, config: dict, title: str = "Bitcoin Strategy Analysis"):
    """
    Affiche une analyse complète de la stratégie sur 4 graphiques

    Args:
        df: DataFrame avec tous les signaux et résultats
        metrics: Dictionnaire des métriques de performance
        config: Configuration de la stratégie
        title: Titre général
    """
    # Configuration du style
    plt.style.use('seaborn-v0_8-darkgrid')

    # Création de la figure avec 4 sous-graphiques
    fig, axes = plt.subplots(4, 1, figsize=(16, 12), sharex=True)
    fig.suptitle(title, fontsize=16, fontweight='bold')

    # Convertir date en datetime si nécessaire
    if 'date' in df.columns:
        dates = pd.to_datetime(df['date'])
    else:
        dates = df.index

    # ========================================================================
    # GRAPHIQUE 1: Prix BTC + Rainbow Chart
    # ========================================================================
    ax1 = axes[0]

    # Prix BTC
    ax1.semilogy(dates, df['close'], 'k-', linewidth=2, label='BTC Price', zorder=10)

    # Rainbow bands (si disponibles)
    if 'rainbow_min' in df.columns and 'rainbow_max' in df.columns:
        ax1.fill_between(dates, df['rainbow_min'], df['rainbow_max'],
                         alpha=0.2, color='purple', label='Rainbow Range')

        # Ligne médiane
        if 'rainbow_mid' in df.columns:
            ax1.semilogy(dates, df['rainbow_mid'], '--', color='purple',
                        alpha=0.5, linewidth=1, label='Rainbow Mid')

    # Marqueurs de trades
    if 'trade' in df.columns:
        trades_idx = df[df['trade'] == 1].index
        if len(trades_idx) > 0:
            ax1.scatter(dates[trades_idx], df.loc[trades_idx, 'close'],
                       c='orange', s=30, alpha=0.6, zorder=15, label='Trades')

    ax1.set_ylabel('Prix BTC (USD, log scale)', fontsize=11, fontweight='bold')
    ax1.legend(loc='upper left', fontsize=9)
    ax1.grid(True, alpha=0.3)
    ax1.set_title('Prix Bitcoin et Rainbow Chart', fontsize=12, fontweight='bold')

    # ========================================================================
    # GRAPHIQUE 2: Fear & Greed Index
    # ========================================================================
    ax2 = axes[1]

    # FNG
    ax2.plot(dates, df['fng'], 'b-', linewidth=1.5, label='Fear & Greed Index')
    ax2.fill_between(dates, 0, df['fng'], alpha=0.3, color='blue')

    # Zones de seuils
    if 'fng_buy_threshold' in config:
        ax2.axhline(config['fng_buy_threshold'], color='green', linestyle='--',
                   linewidth=1.5, alpha=0.7, label=f'Buy threshold ({config["fng_buy_threshold"]})')

    if 'fng_sell_threshold' in config:
        ax2.axhline(config['fng_sell_threshold'], color='red', linestyle='--',
                   linewidth=1.5, alpha=0.7, label=f'Sell threshold ({config["fng_sell_threshold"]})')

    # Zones colorées
    ax2.axhspan(0, 25, alpha=0.1, color='green', label='Extreme Fear')
    ax2.axhspan(75, 100, alpha=0.1, color='red', label='Extreme Greed')

    ax2.set_ylabel('FNG Index (0-100)', fontsize=11, fontweight='bold')
    ax2.set_ylim(0, 100)
    ax2.legend(loc='upper left', fontsize=9, ncol=2)
    ax2.grid(True, alpha=0.3)
    ax2.set_title('Fear & Greed Index', fontsize=12, fontweight='bold')

    # ========================================================================
    # GRAPHIQUE 3: Allocation de la stratégie
    # ========================================================================
    ax3 = axes[2]

    # Allocation
    ax3.plot(dates, df['pos'], 'g-', linewidth=2, label='Allocation BTC (%)')
    ax3.fill_between(dates, 0, df['pos'], alpha=0.3, color='green')

    # Allocation cible (avant filtrage) si disponible
    if 'pos_target' in df.columns:
        ax3.plot(dates, df['pos_target'], '--', color='lightgreen',
                linewidth=1, alpha=0.5, label='Target (before filter)')

    # Rainbow position
    if 'rainbow_position' in df.columns:
        ax3_twin = ax3.twinx()
        ax3_twin.plot(dates, df['rainbow_position'] * 100, 'purple',
                     linewidth=1, alpha=0.5, linestyle=':', label='Rainbow Position')
        ax3_twin.set_ylabel('Rainbow Position (0-100)', fontsize=10, color='purple')
        ax3_twin.tick_params(axis='y', labelcolor='purple')
        ax3_twin.set_ylim(0, 100)
        ax3_twin.legend(loc='upper right', fontsize=8)

    ax3.set_ylabel('Allocation BTC (%)', fontsize=11, fontweight='bold')
    ax3.set_ylim(0, 105)
    ax3.legend(loc='upper left', fontsize=9)
    ax3.grid(True, alpha=0.3)
    ax3.set_title('Allocation de la stratégie', fontsize=12, fontweight='bold')

    # ========================================================================
    # GRAPHIQUE 4: Equity Curves
    # ========================================================================
    ax4 = axes[3]

    # Equity curves
    ax4.plot(dates, df['equity'], 'g-', linewidth=2.5, label='Strategy', zorder=10)
    ax4.plot(dates, df['bh_equity'], 'gray', linewidth=2, alpha=0.7,
            label='Buy & Hold', zorder=5)

    # Zone de surperformance/sous-performance
    outperform = df['equity'] > df['bh_equity']
    ax4.fill_between(dates, df['equity'], df['bh_equity'],
                     where=outperform, alpha=0.2, color='green',
                     label='Outperformance')
    ax4.fill_between(dates, df['equity'], df['bh_equity'],
                     where=~outperform, alpha=0.2, color='red',
                     label='Underperformance')

    ax4.set_ylabel('Equity (1.0 = capital initial)', fontsize=11, fontweight='bold')
    ax4.set_xlabel('Date', fontsize=11, fontweight='bold')
    ax4.legend(loc='upper left', fontsize=9)
    ax4.grid(True, alpha=0.3)
    ax4.set_title('Performance de la stratégie', fontsize=12, fontweight='bold')

    # ========================================================================
    # Encadré avec métriques
    # ========================================================================
    metrics_text = f"""
PERFORMANCE
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Strategy Equity:  {metrics.get('EquityFinal', 0):.2f}x
B&H Equity:       {metrics.get('BHEquityFinal', 0):.2f}x
Ratio vs B&H:     {metrics.get('EquityFinal', 0)/max(metrics.get('BHEquityFinal', 1), 1e-12):.2f}x

CAGR:             {metrics.get('CAGR', 0)*100:.1f}%
B&H CAGR:         {metrics.get('BHCAGR', 0)*100:.1f}%

RISK
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Max Drawdown:     {metrics.get('MaxDD', 0)*100:.1f}%
B&H Max DD:       {metrics.get('BHMaxDD', 0)*100:.1f}%
Volatility:       {metrics.get('Vol', 0)*100:.1f}%

Sharpe Ratio:     {metrics.get('Sharpe', 0):.2f}
Sortino Ratio:    {metrics.get('Sortino', 0):.2f}
Calmar Ratio:     {metrics.get('Calmar', 0):.2f}

TRADING
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Trades:           {metrics.get('trades', 0)}
Trades/year:      {metrics.get('trades_per_year', 0):.1f}
Avg Allocation:   {metrics.get('avg_allocation', 0):.1f}%
    """.strip()

    # Ajout du texte sur le graphique 1 (en haut à droite)
    ax1.text(0.99, 0.97, metrics_text, transform=ax1.transAxes,
            verticalalignment='top', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8),
            fontfamily='monospace', fontsize=8)

    # ========================================================================
    # Configuration de l'axe X (dates)
    # ========================================================================
    ax4.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax4.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    plt.setp(ax4.xaxis.get_majorticklabels(), rotation=45, ha='right')

    # Ajustement de l'espacement
    plt.tight_layout()

    return fig


def show_plots():
    """Affiche tous les graphiques matplotlib"""
    plt.show()


def save_plot(fig, filepath: str):
    """Sauvegarde un graphique"""
    fig.savefig(filepath, dpi=150, bbox_inches='tight')
    print(f"   💾 Graphique sauvegardé: {filepath}")


def plot_optimization_results(results_df: pd.DataFrame, top_n: int = 10):
    """
    Visualise les résultats de l'optimisation

    Args:
        results_df: DataFrame avec tous les résultats triés par score
        top_n: Nombre de meilleurs résultats à afficher
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Résultats de l\'optimisation', fontsize=16, fontweight='bold')

    top_results = results_df.head(top_n)

    # ========================================================================
    # 1. Score des meilleures configs
    # ========================================================================
    ax1 = axes[0, 0]
    x = range(len(top_results))
    ax1.barh(x, top_results['score'], color='green', alpha=0.7)
    ax1.set_yticks(x)
    ax1.set_yticklabels([f"Config {i+1}" for i in x])
    ax1.set_xlabel('Score (Equity / B&H)')
    ax1.set_title(f'Top {top_n} configurations par score')
    ax1.axvline(1.0, color='red', linestyle='--', linewidth=1, alpha=0.5, label='B&H')
    ax1.legend()
    ax1.grid(True, alpha=0.3, axis='x')

    # ========================================================================
    # 2. Sharpe Ratio
    # ========================================================================
    ax2 = axes[0, 1]
    sharpe_col = 'cv_Sharpe' if 'cv_Sharpe' in top_results.columns else 'full_Sharpe'
    ax2.barh(x, top_results[sharpe_col], color='blue', alpha=0.7)
    ax2.set_yticks(x)
    ax2.set_yticklabels([f"Config {i+1}" for i in x])
    ax2.set_xlabel('Sharpe Ratio')
    ax2.set_title('Sharpe Ratio (rendement ajusté au risque)')
    ax2.grid(True, alpha=0.3, axis='x')

    # ========================================================================
    # 3. Max Drawdown
    # ========================================================================
    ax3 = axes[1, 0]
    dd_col = 'cv_MaxDD' if 'cv_MaxDD' in top_results.columns else 'full_MaxDD'
    ax3.barh(x, top_results[dd_col] * 100, color='red', alpha=0.7)
    ax3.set_yticks(x)
    ax3.set_yticklabels([f"Config {i+1}" for i in x])
    ax3.set_xlabel('Max Drawdown (%)')
    ax3.set_title('Max Drawdown (perte maximale)')
    ax3.grid(True, alpha=0.3, axis='x')

    # ========================================================================
    # 4. Trades par an
    # ========================================================================
    ax4 = axes[1, 1]
    tpy_col = 'cv_trades_per_year' if 'cv_trades_per_year' in top_results.columns else 'full_trades_per_year'
    ax4.barh(x, top_results[tpy_col], color='orange', alpha=0.7)
    ax4.set_yticks(x)
    ax4.set_yticklabels([f"Config {i+1}" for i in x])
    ax4.set_xlabel('Trades par an')
    ax4.set_title('Fréquence de trading')
    ax4.grid(True, alpha=0.3, axis='x')

    plt.tight_layout()

    return fig


def plot_walk_forward_stability(results_df: pd.DataFrame, best_config_idx: int = 0):
    """
    Visualise la stabilité d'une config sur les différents folds

    Args:
        results_df: DataFrame des résultats
        best_config_idx: Index de la config à visualiser (0 = meilleure)
    """
    # Note: cette fonction nécessiterait d'avoir accès aux détails par fold
    # Pour l'instant on fait un placeholder
    pass
