#!/usr/bin/env python3
"""
🔬 VALIDATION COMPLÈTE: Rainbow Cheap Only Strategy

Objectifs:
1. Walk-forward validation (éviter overfitting)
2. Analyse détaillée des 252 trades
3. Optimisation thresholds (0.15-0.35) avec validation OOS

Cette stratégie a montré 105x vs B&H (!) - VALIDATION CRITIQUE NÉCESSAIRE
"""
import pandas as pd
import numpy as np
from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.strategy import calculate_rainbow_position
from src.fngbt.backtest_realistic_fees import run_backtest_realistic_fees
import warnings
warnings.filterwarnings('ignore')

print("="*100)
print("🔬 VALIDATION COMPLÈTE: Rainbow Cheap Only Strategy")
print("="*100)
print()

# Load data
print("Chargement données...")
fng = load_fng_alt()
btc = load_btc_prices()
df = merge_daily(fng, btc)
df = calculate_rainbow_position(df)
print(f"✅ {len(df)} jours\n")

bh_ratio = df['close'].iloc[-1] / df['close'].iloc[0]

# ============================================================================
# PARTIE 1: WALK-FORWARD VALIDATION
# ============================================================================

print("="*100)
print("🚶 PARTIE 1: WALK-FORWARD VALIDATION")
print("="*100)
print()

def rainbow_cheap_only(df, threshold=0.25):
    """100% BTC si rainbow < threshold, sinon 0% (cash)"""
    d = df.copy()
    d['pos'] = np.where(d['rainbow_position'] < threshold, 100, 0)
    return d

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

# Thresholds à tester
thresholds_to_test = [0.15, 0.18, 0.20, 0.22, 0.25, 0.28, 0.30, 0.33, 0.35]

wf_results = []

for window in walk_forward_windows:
    print(f"\n{'='*100}")
    print(f"WINDOW: {window['name']}")
    print(f"{'='*100}\n")

    # Split data
    train = df[(df['date'] >= window['train_start']) & (df['date'] <= window['train_end'])].copy()
    test = df[(df['date'] >= window['test_start']) & (df['date'] <= window['test_end'])].copy()

    print(f"Train: {len(train)} jours, Test: {len(test)} jours")

    # Grid search sur TRAIN
    train_results = []
    for threshold in thresholds_to_test:
        signals = rainbow_cheap_only(train, threshold=threshold)
        result = run_backtest_realistic_fees(signals, initial_capital=100.0, fee_rate=0.001)
        metrics = result['metrics']
        bh_train = result['df']['bh_equity'].iloc[-1]

        train_results.append({
            'threshold': threshold,
            'equity': metrics['EquityFinal'],
            'ratio_bh': metrics['EquityFinal'] / bh_train,
            'trades': metrics['trades']
        })

    df_train = pd.DataFrame(train_results).sort_values('equity', ascending=False)
    best_train = df_train.iloc[0]

    print(f"\n🏆 Meilleur threshold sur TRAIN: {best_train['threshold']:.2f}")
    print(f"   Equity: {best_train['equity']:.2f} EUR ({best_train['ratio_bh']:.2f}x vs B&H)")
    print(f"   Trades: {int(best_train['trades'])}")

    # Test avec meilleur threshold sur TEST (OOS)
    signals_test = rainbow_cheap_only(test, threshold=best_train['threshold'])
    result_test = run_backtest_realistic_fees(signals_test, initial_capital=100.0, fee_rate=0.001)
    metrics_test = result_test['metrics']
    bh_test = result_test['df']['bh_equity'].iloc[-1]
    ratio_test = metrics_test['EquityFinal'] / bh_test

    print(f"\n📊 Performance sur TEST (OOS):")
    print(f"   Equity: {metrics_test['EquityFinal']:.2f} EUR")
    print(f"   Ratio vs B&H: {ratio_test:.2f}x ({(ratio_test-1)*100:+.1f}%)")
    print(f"   Trades: {metrics_test['trades']}")
    print(f"   Fees: {metrics_test['total_fees_paid']:.2f} EUR")

    wf_results.append({
        'window': window['name'],
        'best_threshold_train': best_train['threshold'],
        'train_equity': best_train['equity'],
        'train_ratio': best_train['ratio_bh'],
        'test_equity': metrics_test['EquityFinal'],
        'test_ratio': ratio_test,
        'test_trades': metrics_test['trades'],
        'test_fees': metrics_test['total_fees_paid']
    })

# Summary walk-forward
print("\n" + "="*100)
print("📊 RÉSUMÉ WALK-FORWARD VALIDATION")
print("="*100)
print()

df_wf = pd.DataFrame(wf_results)
print(df_wf[['window', 'best_threshold_train', 'test_equity', 'test_ratio', 'test_trades']].to_string(index=False))
print()

avg_test_ratio = df_wf['test_ratio'].mean()
print(f"📈 Ratio moyen OOS: {avg_test_ratio:.2f}x vs B&H")
print(f"🎯 vs Objectif 18x: {'✅ ATTEINT!' if avg_test_ratio >= 18 else f'❌ Manque {18 - avg_test_ratio:.1f}x'}")
print()

# ============================================================================
# PARTIE 2: ANALYSE DÉTAILLÉE DES TRADES (Full Dataset)
# ============================================================================

print("="*100)
print("📊 PARTIE 2: ANALYSE DÉTAILLÉE DES TRADES")
print("="*100)
print()

# Utiliser threshold le plus fréquent du walk-forward
most_common_threshold = df_wf['best_threshold_train'].mode()[0]
print(f"Threshold le plus stable (walk-forward): {most_common_threshold:.2f}\n")

# Backtest complet avec détails
signals_full = rainbow_cheap_only(df, threshold=most_common_threshold)
result_full = run_backtest_realistic_fees(signals_full, initial_capital=100.0, fee_rate=0.001)
metrics_full = result_full['metrics']
df_detail = result_full['df']

print(f"Performance Full Dataset (threshold {most_common_threshold:.2f}):")
print(f"   Equity finale: {metrics_full['EquityFinal']:.2f} EUR")
print(f"   Ratio vs capital: {metrics_full['EquityFinal']/100:.2f}x")
print(f"   Ratio vs B&H: {metrics_full['EquityFinal']/(bh_ratio*100):.2f}x")
print(f"   Trades: {metrics_full['trades']}")
print(f"   Fees: {metrics_full['total_fees_paid']:.2f} EUR")
print()

# Analyser les trades
df_detail['signal_change'] = df_detail['pos'].diff().abs() > 0

trades_df = df_detail[df_detail['signal_change']].copy()
trades_df = trades_df.reset_index(drop=True)

print(f"Total changements de position: {len(trades_df)}")
print()

# Identifier entrées (0→100) et sorties (100→0)
entries = []
exits = []

for i in range(len(trades_df)):
    if i > 0:
        prev_pos = df_detail.loc[df_detail['date'] == trades_df['date'].iloc[i-1], 'pos'].iloc[0] if i > 0 else 0
        curr_pos = trades_df['pos'].iloc[i]

        if prev_pos == 0 and curr_pos == 100:
            entries.append({
                'date': trades_df['date'].iloc[i],
                'price': trades_df['close'].iloc[i],
                'rainbow': trades_df['rainbow_position'].iloc[i]
            })
        elif prev_pos == 100 and curr_pos == 0:
            exits.append({
                'date': trades_df['date'].iloc[i],
                'price': trades_df['close'].iloc[i],
                'rainbow': trades_df['rainbow_position'].iloc[i]
            })

print(f"Nombre d'entrées (achats): {len(entries)}")
print(f"Nombre de sorties (ventes): {len(exits)}")
print()

# Analyser les cycles complets (achat → vente)
if len(entries) > 0 and len(exits) > 0:
    cycles = []
    for i in range(min(len(entries), len(exits))):
        entry = entries[i]
        exit_trade = exits[i]

        gain = (exit_trade['price'] / entry['price'] - 1) * 100
        duration = (exit_trade['date'] - entry['date']).days

        cycles.append({
            'entry_date': entry['date'],
            'entry_price': entry['price'],
            'entry_rainbow': entry['rainbow'],
            'exit_date': exit_trade['date'],
            'exit_price': exit_trade['price'],
            'exit_rainbow': exit_trade['rainbow'],
            'gain_pct': gain,
            'duration_days': duration
        })

    df_cycles = pd.DataFrame(cycles)

    print("🔄 TOP 10 MEILLEURS CYCLES (Gain %):")
    print(df_cycles.nlargest(10, 'gain_pct')[['entry_date', 'entry_price', 'exit_date',
                                                'exit_price', 'gain_pct', 'duration_days']].to_string(index=False))
    print()

    print("📊 STATISTIQUES CYCLES:")
    print(f"   Cycles totaux: {len(df_cycles)}")
    print(f"   Gain moyen par cycle: {df_cycles['gain_pct'].mean():.1f}%")
    print(f"   Gain médian par cycle: {df_cycles['gain_pct'].median():.1f}%")
    print(f"   Meilleur cycle: {df_cycles['gain_pct'].max():.1f}%")
    print(f"   Pire cycle: {df_cycles['gain_pct'].min():.1f}%")
    print(f"   Cycles positifs: {(df_cycles['gain_pct'] > 0).sum()} ({(df_cycles['gain_pct'] > 0).sum()/len(df_cycles)*100:.1f}%)")
    print(f"   Durée moyenne: {df_cycles['duration_days'].mean():.0f} jours")
    print()

    # Sauvegarder cycles
    df_cycles.to_csv('outputs/rainbow_cheap_cycles.csv', index=False)
    print("💾 Cycles sauvegardés: outputs/rainbow_cheap_cycles.csv")
    print()

# Temps en BTC vs Cash
time_in_btc = (df_detail['pos'] == 100).sum() / len(df_detail) * 100
print(f"⏱️  ALLOCATION DU TEMPS:")
print(f"   Temps en BTC: {time_in_btc:.1f}%")
print(f"   Temps en Cash: {100-time_in_btc:.1f}%")
print()

# ============================================================================
# PARTIE 3: COMPARAISON FINALE
# ============================================================================

print("="*100)
print("⚖️  COMPARAISON FINALE")
print("="*100)
print()

comparison = pd.DataFrame([
    {
        'Stratégie': 'Buy & Hold',
        'Equity (EUR)': bh_ratio * 100,
        'Ratio vs B&H': 1.0,
        'OOS Validé': 'N/A',
        'Atteint 18x': '❌'
    },
    {
        'Stratégie': 'Rainbow Cheap Only (full dataset)',
        'Equity (EUR)': metrics_full['EquityFinal'],
        'Ratio vs B&H': metrics_full['EquityFinal'] / (bh_ratio * 100),
        'OOS Validé': 'Non',
        'Atteint 18x': '✅' if metrics_full['EquityFinal'] / (bh_ratio * 100) >= 18 else '❌'
    },
    {
        'Stratégie': 'Rainbow Cheap Only (OOS moyen)',
        'Equity (EUR)': df_wf['test_equity'].mean(),
        'Ratio vs B&H': avg_test_ratio,
        'OOS Validé': 'Oui ✅',
        'Atteint 18x': '✅' if avg_test_ratio >= 18 else '❌'
    },
    {
        'Stratégie': 'ML avec S&P (OOS validé)',
        'Equity (EUR)': 1.284 * bh_ratio * 100,
        'Ratio vs B&H': 1.284,
        'OOS Validé': 'Oui ✅',
        'Atteint 18x': '❌'
    }
]).sort_values('Ratio vs B&H', ascending=False)

print(comparison.to_string(index=False))
print()

# Winner
winner = comparison[comparison['OOS Validé'] == 'Oui ✅'].sort_values('Ratio vs B&H', ascending=False).iloc[0]
print(f"🏆 CHAMPIONNE (validée OOS): {winner['Stratégie']}")
print(f"   Equity: {winner['Equity (EUR)']:.2f} EUR")
print(f"   Ratio vs B&H: {winner['Ratio vs B&H']:.2f}x")
print()

# Sauvegarder
df_wf.to_csv('outputs/rainbow_cheap_walkforward.csv', index=False)
df_detail.to_csv('outputs/rainbow_cheap_full_details.csv', index=False)
comparison.to_csv('outputs/rainbow_cheap_comparison.csv', index=False)

print("💾 Résultats sauvegardés:")
print("   • outputs/rainbow_cheap_walkforward.csv")
print("   • outputs/rainbow_cheap_full_details.csv")
print("   • outputs/rainbow_cheap_cycles.csv")
print("   • outputs/rainbow_cheap_comparison.csv")
print()

# ============================================================================
# CONCLUSION
# ============================================================================

print("="*100)
print("🎯 CONCLUSION")
print("="*100)
print()

if avg_test_ratio >= 18:
    print("🎉🎉🎉 OBJECTIF 18x ATTEINT EN OOS!")
    print(f"   Ratio moyen OOS: {avg_test_ratio:.1f}x vs B&H")
    print(f"   Threshold optimal: {most_common_threshold:.2f}")
    print()
    print("✅ Cette stratégie est VALIDÉE et prête pour déploiement!")
else:
    print(f"Performance OOS: {avg_test_ratio:.2f}x vs B&H")
    if avg_test_ratio > 1.0:
        print(f"✅ Bat quand même B&H de {(avg_test_ratio-1)*100:.1f}%")
    else:
        print(f"❌ Ne bat pas B&H en OOS")
    print()

    print(f"⚠️  Full dataset montrait {metrics_full['EquityFinal']/(bh_ratio*100):.0f}x vs B&H")
    print(f"   Mais OOS seulement {avg_test_ratio:.1f}x")
    print(f"   → Overfitting détecté!")

print("\n✨ Validation complète terminée!")
