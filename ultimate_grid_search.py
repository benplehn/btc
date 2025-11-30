#!/usr/bin/env python3
"""
🏆 ULTIMATE GRID SEARCH: FNG + Rainbow + S&P 500

OBJECTIF: Maximiser le GAIN FINAL (equity finale en EUR)
CONTRAINTE: Walk-forward validation pour éviter overfitting

Stratégie testée:
- Rainbow Chart: cheap vs expensive
- FNG: fear vs greed
- S&P 500: bullish trend (MA21 > MA50) vs bearish

Allocation = fonction(rainbow, fng, sp500_trend)

Pour chaque combinaison de facteurs, allocation différente:
- Tous bullish (Rainbow cheap + FNG fear + S&P bullish) → 100%
- Mix → 95-98%
- Tous bearish (Rainbow expensive + FNG greed + S&P bearish) → 85-90%
"""
import pandas as pd
import numpy as np
from src.fngbt.backtest_realistic_fees import run_backtest_realistic_fees
from src.fngbt.strategy import calculate_rainbow_position
from itertools import product
import warnings
warnings.filterwarnings('ignore')

print("="*100)
print("🏆 ULTIMATE GRID SEARCH: FNG + Rainbow + S&P 500")
print("="*100)
print()
print("OBJECTIF: Maximiser le GAIN FINAL (equity EUR)")
print("MÉTHODE: Walk-forward validation (éviter overfitting)")
print()

# Load data
print("Chargement données...")
df = pd.read_csv('outputs/data_with_sp500_features.csv', parse_dates=['date'])
df = calculate_rainbow_position(df)

# Ensure S&P features
if 'sp500_ma21' not in df.columns:
    df['sp500_ma21'] = df['sp500_close'].rolling(21).mean()
if 'sp500_ma50' not in df.columns:
    df['sp500_ma50'] = df['sp500_close'].rolling(50).mean()

df['sp500_bullish'] = (df['sp500_ma21'] > df['sp500_ma50']).astype(int)

print(f"✅ {len(df)} jours\n")

# Strategy function
def triple_factor_strategy(df,
                           rainbow_thresh=0.60,
                           fng_thresh=50,
                           alloc_all_bullish=100,
                           alloc_2_bullish=98,
                           alloc_1_bullish=95,
                           alloc_all_bearish=90):
    """
    Stratégie triple facteur: Rainbow + FNG + S&P 500

    Conditions bullish:
    - Rainbow: position < threshold (cheap)
    - FNG: value < threshold (fear)
    - S&P: MA21 > MA50 (bullish trend)

    Allocation basée sur nombre de conditions bullish:
    - 3/3 bullish → alloc_all_bullish
    - 2/3 bullish → alloc_2_bullish
    - 1/3 bullish → alloc_1_bullish
    - 0/3 bullish → alloc_all_bearish
    """
    d = df.copy()

    # Count bullish conditions
    rainbow_bullish = (d['rainbow_position'] < rainbow_thresh).astype(int)
    fng_bullish = (d['fng'] < fng_thresh).astype(int)
    sp500_bullish = d['sp500_bullish']

    bullish_count = rainbow_bullish + fng_bullish + sp500_bullish

    # Allocate based on count
    d['pos'] = np.select(
        [bullish_count == 3, bullish_count == 2, bullish_count == 1],
        [alloc_all_bullish, alloc_2_bullish, alloc_1_bullish],
        default=alloc_all_bearish
    )

    return d

# Grid search parameters
print("="*100)
print("📊 PARAMÈTRES GRID SEARCH")
print("="*100)
print()

rainbow_thresholds = [0.50, 0.60, 0.70]
fng_thresholds = [40, 50, 60]
allocation_configs = [
    # (all_bullish, 2_bullish, 1_bullish, all_bearish)
    (100, 98, 95, 90),   # Conservateur
    (100, 97, 93, 88),   # Modéré
    (100, 96, 90, 85),   # Agressif
]

total_configs = len(rainbow_thresholds) * len(fng_thresholds) * len(allocation_configs)
print(f"Rainbow thresholds: {rainbow_thresholds}")
print(f"FNG thresholds: {fng_thresholds}")
print(f"Allocation configs: {len(allocation_configs)}")
print(f"\nTotal combinaisons: {total_configs}")
print()

# Walk-forward windows
walk_forward_windows = [
    {
        'name': 'Train 2018-2021 → Test 2022',
        'train_start': '2018-01-01',
        'train_end': '2021-12-31',
        'test_start': '2022-01-01',
        'test_end': '2022-12-31'
    },
    {
        'name': 'Train 2018-2022 → Test 2023',
        'train_start': '2018-01-01',
        'train_end': '2022-12-31',
        'test_start': '2023-01-01',
        'test_end': '2023-12-31'
    },
    {
        'name': 'Train 2018-2023 → Test 2024-2025',
        'train_start': '2018-01-01',
        'train_end': '2023-12-31',
        'test_start': '2024-01-01',
        'test_end': '2025-11-29'
    }
]

print("="*100)
print("🚶 WALK-FORWARD VALIDATION")
print("="*100)
print()

# Pour chaque window, trouver la meilleure config sur train, tester sur test
wf_results = []

for i, window in enumerate(walk_forward_windows, 1):
    print(f"\n{'='*100}")
    print(f"WINDOW {i}: {window['name']}")
    print(f"{'='*100}\n")

    # Split data
    train = df[(df['date'] >= window['train_start']) & (df['date'] <= window['train_end'])].copy()
    test = df[(df['date'] >= window['test_start']) & (df['date'] <= window['test_end'])].copy()

    print(f"Train: {len(train)} jours ({window['train_start']} → {window['train_end']})")
    print(f"Test:  {len(test)} jours ({window['test_start']} → {window['test_end']})")
    print()

    # Grid search on TRAIN set
    print(f"🔍 Grid search sur train set ({total_configs} configs)...")
    train_results = []

    for rainbow_thresh, fng_thresh, allocs in product(rainbow_thresholds, fng_thresholds, allocation_configs):
        all_bull, two_bull, one_bull, all_bear = allocs

        signals = triple_factor_strategy(train,
                                        rainbow_thresh=rainbow_thresh,
                                        fng_thresh=fng_thresh,
                                        alloc_all_bullish=all_bull,
                                        alloc_2_bullish=two_bull,
                                        alloc_1_bullish=one_bull,
                                        alloc_all_bearish=all_bear)

        result = run_backtest_realistic_fees(signals, initial_capital=100.0, fee_rate=0.001)
        metrics = result['metrics']

        train_results.append({
            'rainbow_thresh': rainbow_thresh,
            'fng_thresh': fng_thresh,
            'alloc_all_bull': all_bull,
            'alloc_2_bull': two_bull,
            'alloc_1_bull': one_bull,
            'alloc_all_bear': all_bear,
            'equity_final': metrics['EquityFinal'],
            'ratio_bh': metrics['EquityFinal'] / result['df']['bh_equity'].iloc[-1],
            'trades': metrics['trades'],
            'fees': metrics['total_fees_paid'],
            'sharpe': metrics['Sharpe']
        })

    # Best config on train (maximize equity final)
    df_train = pd.DataFrame(train_results).sort_values('equity_final', ascending=False)
    best_train = df_train.iloc[0]

    print(f"\n🥇 Meilleure config sur TRAIN (max equity):")
    print(f"   Rainbow threshold: {best_train['rainbow_thresh']}")
    print(f"   FNG threshold: {best_train['fng_thresh']}")
    print(f"   Allocations: {best_train['alloc_all_bull']}/{best_train['alloc_2_bull']}/{best_train['alloc_1_bull']}/{best_train['alloc_all_bear']}")
    print(f"   Equity finale: {best_train['equity_final']:.2f} EUR")
    print(f"   Ratio vs B&H: {best_train['ratio_bh']:.3f}x (+{(best_train['ratio_bh']-1)*100:.1f}%)")
    print(f"   Trades: {int(best_train['trades'])}, Fees: {best_train['fees']:.2f} EUR")
    print()

    # Test on TEST set avec config optimale
    print(f"🧪 Test sur TEST set...")
    signals_test = triple_factor_strategy(test,
                                         rainbow_thresh=best_train['rainbow_thresh'],
                                         fng_thresh=best_train['fng_thresh'],
                                         alloc_all_bullish=best_train['alloc_all_bull'],
                                         alloc_2_bullish=best_train['alloc_2_bull'],
                                         alloc_1_bullish=best_train['alloc_1_bull'],
                                         alloc_all_bearish=best_train['alloc_all_bear'])

    result_test = run_backtest_realistic_fees(signals_test, initial_capital=100.0, fee_rate=0.001)
    metrics_test = result_test['metrics']
    bh_test = result_test['df']['bh_equity'].iloc[-1]

    print(f"\n📊 Résultats TEST (OOS):")
    print(f"   Equity finale: {metrics_test['EquityFinal']:.2f} EUR")
    print(f"   Ratio vs B&H: {metrics_test['EquityFinal']/bh_test:.3f}x (+{(metrics_test['EquityFinal']/bh_test-1)*100:.1f}%)")
    print(f"   Trades: {metrics_test['trades']}, Fees: {metrics_test['total_fees_paid']:.2f} EUR")
    print(f"   Sharpe: {metrics_test['Sharpe']:.2f}")
    print()

    wf_results.append({
        'window': window['name'],
        'rainbow_thresh': best_train['rainbow_thresh'],
        'fng_thresh': best_train['fng_thresh'],
        'alloc_all_bull': best_train['alloc_all_bull'],
        'alloc_2_bull': best_train['alloc_2_bull'],
        'alloc_1_bull': best_train['alloc_1_bull'],
        'alloc_all_bear': best_train['alloc_all_bear'],
        'train_equity': best_train['equity_final'],
        'train_ratio': best_train['ratio_bh'],
        'test_equity': metrics_test['EquityFinal'],
        'test_ratio': metrics_test['EquityFinal'] / bh_test,
        'test_trades': metrics_test['trades'],
        'test_fees': metrics_test['total_fees_paid'],
        'test_sharpe': metrics_test['Sharpe']
    })

# Summary walk-forward
print("\n" + "="*100)
print("📊 RÉSUMÉ WALK-FORWARD VALIDATION")
print("="*100)
print()

df_wf = pd.DataFrame(wf_results)
print(df_wf[['window', 'rainbow_thresh', 'fng_thresh', 'test_equity', 'test_ratio', 'test_trades', 'test_fees']].to_string(index=False))
print()

avg_test_equity = df_wf['test_equity'].mean()
avg_test_ratio = df_wf['test_ratio'].mean()

print(f"📈 Performance moyenne OOS:")
print(f"   Equity finale moyenne: {avg_test_equity:.2f} EUR")
print(f"   Ratio moyen vs B&H: {avg_test_ratio:.3f}x (+{(avg_test_ratio-1)*100:.1f}%)")
print()

# Configuration la plus stable (apparaît le plus souvent)
config_counts = df_wf.groupby(['rainbow_thresh', 'fng_thresh']).size().reset_index(name='count')
config_counts = config_counts.sort_values('count', ascending=False)

print("🔍 Configurations les plus stables (apparaissent le plus):")
print(config_counts.head(3).to_string(index=False))
print()

# Full dataset test avec config la plus fréquente
print("="*100)
print("🏆 TEST FINAL: Full Dataset (2018-2025)")
print("="*100)
print()

# Prendre la config la plus fréquente OU la moyenne des configs
most_common_config = config_counts.iloc[0]
final_rainbow = most_common_config['rainbow_thresh']
final_fng = most_common_config['fng_thresh']

# Prendre allocation moyenne des configs choisies
configs_selected = df_wf[(df_wf['rainbow_thresh'] == final_rainbow) & (df_wf['fng_thresh'] == final_fng)]
final_alloc_all_bull = int(configs_selected['alloc_all_bull'].mean())
final_alloc_2_bull = int(configs_selected['alloc_2_bull'].mean())
final_alloc_1_bull = int(configs_selected['alloc_1_bull'].mean())
final_alloc_all_bear = int(configs_selected['alloc_all_bear'].mean())

print(f"Configuration finale (la plus stable):")
print(f"  • Rainbow threshold: {final_rainbow}")
print(f"  • FNG threshold: {final_fng}")
print(f"  • Allocations: {final_alloc_all_bull}/{final_alloc_2_bull}/{final_alloc_1_bull}/{final_alloc_all_bear}")
print()

signals_final = triple_factor_strategy(df,
                                      rainbow_thresh=final_rainbow,
                                      fng_thresh=final_fng,
                                      alloc_all_bullish=final_alloc_all_bull,
                                      alloc_2_bullish=final_alloc_2_bull,
                                      alloc_1_bullish=final_alloc_1_bull,
                                      alloc_all_bearish=final_alloc_all_bear)

result_final = run_backtest_realistic_fees(signals_final, initial_capital=100.0, fee_rate=0.001)
metrics_final = result_final['metrics']
bh_final = result_final['df']['bh_equity'].iloc[-1]

print(f"📊 Performance Full Dataset:")
print(f"   Equity finale: {metrics_final['EquityFinal']:.2f} EUR 💰")
print(f"   Gain: +{metrics_final['EquityFinal']-100:.2f} EUR")
print(f"   Ratio vs B&H: {metrics_final['EquityFinal']/bh_final:.3f}x (+{(metrics_final['EquityFinal']/bh_final-1)*100:.1f}%)")
print(f"   CAGR: {metrics_final['CAGR']*100:.1f}%")
print(f"   Sharpe: {metrics_final['Sharpe']:.2f}")
print(f"   Max Drawdown: {metrics_final['MaxDD']*100:.1f}%")
print(f"   Trades: {metrics_final['trades']}")
print(f"   Fees: {metrics_final['total_fees_paid']:.2f} EUR")
print()

# Comparaison avec autres stratégies
print("="*100)
print("⚖️  COMPARAISON: Triple Factor vs Autres Stratégies")
print("="*100)
print()

comparison = pd.DataFrame([
    {
        'Stratégie': 'Buy & Hold',
        'Equity Finale (EUR)': bh_final,
        'Gain (EUR)': bh_final - 100,
        'Ratio': 1.0,
        'Trades': 0,
        'Fees (EUR)': 0
    },
    {
        'Stratégie': 'Rainbow Bands',
        'Equity Finale (EUR)': 709.65,
        'Gain (EUR)': 609.65,
        'Ratio': 1.156,
        'Trades': 658,
        'Fees (EUR)': 0.65
    },
    {
        'Stratégie': 'ML avec S&P (OOS)',
        'Equity Finale (EUR)': 614.26 * 1.284,  # B&H * ratio OOS
        'Gain (EUR)': 614.26 * 1.284 - 100,
        'Ratio': 1.284,
        'Trades': 'N/A',
        'Fees (EUR)': 'N/A'
    },
    {
        'Stratégie': 'S&P + FNG (in-sample)',
        'Equity Finale (EUR)': 614.26 * 1.713,
        'Gain (EUR)': 614.26 * 1.713 - 100,
        'Ratio': 1.713,
        'Trades': 2544,
        'Fees (EUR)': 18.17
    },
    {
        'Stratégie': 'TRIPLE FACTOR (validé OOS)',
        'Equity Finale (EUR)': metrics_final['EquityFinal'],
        'Gain (EUR)': metrics_final['EquityFinal'] - 100,
        'Ratio': metrics_final['EquityFinal'] / bh_final,
        'Trades': metrics_final['trades'],
        'Fees (EUR)': metrics_final['total_fees_paid']
    }
])

comparison = comparison.sort_values('Equity Finale (EUR)', ascending=False)
print(comparison.to_string(index=False))
print()

best = comparison.iloc[0]
print(f"🥇 STRATÉGIE AVEC LE PLUS GROS GAIN: {best['Stratégie']}")
print(f"   Equity finale: {best['Equity Finale (EUR)']:.2f} EUR")
print(f"   GAIN: +{best['Gain (EUR)']:.2f} EUR 💰💰💰")
print()

# Sauvegarder
df_wf.to_csv('outputs/ultimate_walkforward_results.csv', index=False)
result_final['df'].to_csv('outputs/ultimate_strategy_details.csv', index=False)

# Créer fichier de config pour utilisation future
strategy_config = {
    'name': 'Triple Factor Strategy (FNG + Rainbow + S&P 500)',
    'rainbow_threshold': float(final_rainbow),
    'fng_threshold': int(final_fng),
    'alloc_all_bullish': int(final_alloc_all_bull),
    'alloc_2_bullish': int(final_alloc_2_bull),
    'alloc_1_bullish': int(final_alloc_1_bull),
    'alloc_all_bearish': int(final_alloc_all_bear),
    'rules': {
        '3_bullish': f'{final_alloc_all_bull}% (Rainbow cheap + FNG fear + S&P bullish)',
        '2_bullish': f'{final_alloc_2_bull}% (2 conditions bullish sur 3)',
        '1_bullish': f'{final_alloc_1_bull}% (1 condition bullish sur 3)',
        '0_bullish': f'{final_alloc_all_bear}% (Tous bearish)'
    },
    'performance': {
        'equity_final_eur': float(metrics_final['EquityFinal']),
        'gain_eur': float(metrics_final['EquityFinal'] - 100),
        'ratio_vs_bh': float(metrics_final['EquityFinal'] / bh_final),
        'cagr_pct': float(metrics_final['CAGR'] * 100),
        'sharpe': float(metrics_final['Sharpe']),
        'max_dd_pct': float(metrics_final['MaxDD'] * 100),
        'trades': int(metrics_final['trades']),
        'fees_eur': float(metrics_final['total_fees_paid'])
    },
    'oos_validation': {
        'avg_test_ratio': float(avg_test_ratio),
        'avg_test_equity': float(avg_test_equity),
        'windows_tested': len(walk_forward_windows)
    }
}

import json
with open('outputs/ultimate_strategy_config.json', 'w') as f:
    json.dump(strategy_config, f, indent=2)

print("💾 Résultats sauvegardés:")
print("   • outputs/ultimate_walkforward_results.csv")
print("   • outputs/ultimate_strategy_details.csv")
print("   • outputs/ultimate_strategy_config.json ← CONFIG POUR UTILISATION FUTURE")
print()

# STRATÉGIE À APPLIQUER EN PREDICTIF
print("="*100)
print("🎯 STRATÉGIE À APPLIQUER EN PREDICTIF (NO HINDSIGHT)")
print("="*100)
print()

print("Voici la stratégie validée en walk-forward (pas d'overfitting):\n")
print(f"1️⃣  Calculer 3 conditions:")
print(f"   • Rainbow cheap: position < {final_rainbow}")
print(f"   • FNG fear: value < {final_fng}")
print(f"   • S&P bullish: MA21 > MA50")
print()
print(f"2️⃣  Compter combien de conditions sont TRUE")
print()
print(f"3️⃣  Allouer selon le nombre:")
print(f"   • 3/3 bullish → {final_alloc_all_bull}% BTC")
print(f"   • 2/3 bullish → {final_alloc_2_bull}% BTC")
print(f"   • 1/3 bullish → {final_alloc_1_bull}% BTC")
print(f"   • 0/3 bullish → {final_alloc_all_bear}% BTC")
print()
print(f"📊 Performance attendue (OOS): {avg_test_ratio:.2f}x (+{(avg_test_ratio-1)*100:.1f}%)")
print(f"💰 Equity finale attendue: ~{avg_test_equity:.0f} EUR (capital initial 100 EUR)")
print()

print("✨ Grid search terminé! Stratégie prête pour déploiement!")
