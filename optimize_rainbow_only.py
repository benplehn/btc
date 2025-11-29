#!/usr/bin/env python3
"""
Stratégie UNIQUEMENT basée sur Rainbow Chart

Logique:
1. Allocation 100% dépendante de la position Rainbow
2. FNG utilisé UNIQUEMENT comme filtre de confirmation (optionnel)
3. Avec le temps, les hauts du Rainbow diminuent (cycles moins extrêmes)

Principe:
- Prix dans bandes BASSES du Rainbow (0.0-0.3) → 100% allocation
- Prix dans bandes MOYENNES (0.3-0.7) → allocation linéaire décroissante
- Prix dans bandes HAUTES (0.7-1.0) → 0-20% allocation

IMPORTANT: Avec le temps (halving cycles), les tops sont moins hauts.
2017: Rainbow top ~1.0
2021: Rainbow top ~0.9
2024: Rainbow top ~0.8
→ Les bandes hautes deviennent moins accessibles
"""
import pandas as pd
import numpy as np
from datetime import datetime
from itertools import product
from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.strategy import calculate_rainbow_position
from src.fngbt.backtest import run_backtest

def build_rainbow_only_strategy(df, buy_threshold, sell_threshold,
                                 alloc_min, alloc_max, use_fng_filter=False,
                                 fng_confirm_threshold=50):
    """
    Stratégie PURE Rainbow Chart

    Args:
        buy_threshold: Position Rainbow en-dessous = zone d'achat (ex: 0.3)
        sell_threshold: Position Rainbow au-dessus = zone de vente (ex: 0.7)
        alloc_min: Allocation minimale en zone haute (ex: 0-20%)
        alloc_max: Allocation maximale en zone basse (ex: 100%)
        use_fng_filter: Si True, FNG utilisé comme confirmation
        fng_confirm_threshold: Seuil FNG pour confirmer (ex: 50)

    Logique:
        - rainbow_pos < buy_threshold: alloc_max (100%)
        - rainbow_pos > sell_threshold: alloc_min (0-20%)
        - Entre les deux: interpolation linéaire
        - [Optionnel] Si FNG > fng_confirm_threshold: réduire légèrement allocation
    """
    d = df.copy()
    d = calculate_rainbow_position(d)

    rainbow_pos = d['rainbow_position'].values

    # Allocation basée UNIQUEMENT sur Rainbow
    allocation = np.where(
        rainbow_pos <= buy_threshold,
        alloc_max,  # Zone basse = MAX allocation
        np.where(
            rainbow_pos >= sell_threshold,
            alloc_min,  # Zone haute = MIN allocation
            # Interpolation linéaire entre buy et sell thresholds
            alloc_max - (alloc_max - alloc_min) * (rainbow_pos - buy_threshold) / (sell_threshold - buy_threshold)
        )
    )

    # [Optionnel] Filtre FNG pour confirmation
    if use_fng_filter:
        fng_penalty = np.where(
            d['fng'] > fng_confirm_threshold,
            0.9,  # Réduire allocation de 10% si FNG élevé
            1.0
        )
        allocation = allocation * fng_penalty

    d['pos'] = np.clip(allocation, alloc_min, alloc_max)
    d['trade'] = (d['pos'].diff().abs() > 5).astype(int)

    return d

def build_rainbow_time_decay_strategy(df, buy_threshold, sell_threshold,
                                       alloc_min, alloc_max, decay_rate=0.95):
    """
    Stratégie Rainbow avec dégradation temporelle des tops

    Concept: Avec le temps, Bitcoin atteint de moins en moins les bandes hautes
    → Les cycles de halving successifs ont des tops plus bas en Rainbow position

    Args:
        decay_rate: Facteur de dégradation par an (ex: 0.95 = -5%/an)
                   Appliqué au sell_threshold au fil du temps
    """
    d = df.copy()
    d = calculate_rainbow_position(d)

    # Calculer années depuis début
    start_date = d['date'].min()
    years_elapsed = (d['date'] - start_date).dt.total_seconds() / (365.25 * 24 * 3600)

    # Dégradation du sell_threshold au fil du temps
    # Exemple: sell_threshold=0.8 avec decay_rate=0.95
    # Année 0: 0.8
    # Année 1: 0.8 * 0.95 = 0.76
    # Année 4: 0.8 * 0.95^4 = 0.65
    adjusted_sell_threshold = sell_threshold * (decay_rate ** years_elapsed)

    # Allocation
    rainbow_pos = d['rainbow_position'].values
    allocation = np.zeros(len(d))

    for i in range(len(d)):
        sell_thresh = adjusted_sell_threshold.iloc[i]

        if rainbow_pos[i] <= buy_threshold:
            allocation[i] = alloc_max
        elif rainbow_pos[i] >= sell_thresh:
            allocation[i] = alloc_min
        else:
            # Interpolation linéaire
            allocation[i] = alloc_max - (alloc_max - alloc_min) * \
                           (rainbow_pos[i] - buy_threshold) / (sell_thresh - buy_threshold)

    d['pos'] = np.clip(allocation, alloc_min, alloc_max)
    d['trade'] = (d['pos'].diff().abs() > 5).astype(int)

    return d

def grid_search_rainbow_only(df, top_n=20):
    """
    Grid search UNIQUEMENT sur Rainbow Chart
    """
    print("="*100)
    print("🌈 GRID SEARCH: Stratégie 100% Rainbow Chart")
    print("="*100)

    # Baseline
    bh = df.copy()
    bh['pos'] = 100.0
    bh['trade'] = 0
    bh_result = run_backtest(bh, fees_bps=0.0)
    bh_equity = bh_result['metrics']['EquityFinal']

    print(f"\n📊 Baseline B&H: {bh_equity:.2f}x")

    # Grille Rainbow-only
    buy_thresholds = [0.15, 0.2, 0.25, 0.3, 0.35, 0.4]
    sell_thresholds = [0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9]
    alloc_mins = [0, 5, 10, 15, 20, 25, 30]  # Allocation min en zone haute
    alloc_maxs = [95, 100]  # Allocation max en zone basse
    use_fng_filters = [False, True]  # Tester avec et sans filtre FNG
    fng_thresholds = [50, 60, 70, 80]  # Seuils FNG si filtre activé

    total = (len(buy_thresholds) * len(sell_thresholds) * len(alloc_mins) *
             len(alloc_maxs) * len(use_fng_filters) * len(fng_thresholds))

    print(f"\n⏳ Total combinaisons: {total:,}")

    results = []
    tested = 0

    for buy_t, sell_t in product(buy_thresholds, sell_thresholds):
        if buy_t >= sell_t:
            continue

        for alloc_min, alloc_max in product(alloc_mins, alloc_maxs):
            if alloc_min >= alloc_max:
                continue

            for use_fng in use_fng_filters:
                for fng_t in fng_thresholds if use_fng else [50]:  # 50 = dummy si pas utilisé
                    tested += 1

                    try:
                        signals = build_rainbow_only_strategy(
                            df, buy_t, sell_t, alloc_min, alloc_max,
                            use_fng_filter=use_fng,
                            fng_confirm_threshold=fng_t
                        )

                        result = run_backtest(signals, fees_bps=10.0)
                        metrics = result['metrics']
                        ratio = metrics['EquityFinal'] / bh_equity

                        results.append({
                            'buy_threshold': buy_t,
                            'sell_threshold': sell_t,
                            'alloc_min': alloc_min,
                            'alloc_max': alloc_max,
                            'use_fng_filter': use_fng,
                            'fng_threshold': fng_t if use_fng else None,
                            'equity': metrics['EquityFinal'],
                            'ratio': ratio,
                            'cagr': metrics['CAGR'],
                            'max_dd': metrics['MaxDD'],
                            'sharpe': metrics['Sharpe'],
                            'trades': metrics['trades']
                        })

                        if tested % 500 == 0:
                            best_so_far = max(results, key=lambda x: x['ratio'])
                            print(f"   Testé: {tested:,} | Meilleur: {best_so_far['ratio']:.3f}x", end='\r')

                    except Exception:
                        continue

    print(f"\n✅ Tests terminés: {tested:,} combinaisons")

    # Trier
    results.sort(key=lambda x: x['ratio'], reverse=True)

    # Top N
    print(f"\n{'='*100}")
    print(f"🏆 TOP {top_n} STRATÉGIES (Rainbow uniquement)")
    print(f"{'='*100}\n")

    print(f"{'Rank':<6} {'Ratio':>8} {'Equity':>8} {'CAGR':>7} {'DD':>7} {'Trades':>7} | "
          f"Rainbow      Alloc    | FNG Filter")
    print("-" * 100)

    for i, r in enumerate(results[:top_n], 1):
        marker = "🥇" if i == 1 else ("🥈" if i == 2 else ("🥉" if i == 3 else "  "))
        fng_str = f"FNG>{r['fng_threshold']}" if r['use_fng_filter'] else "No FNG"

        print(f"{marker} {i:<3} {r['ratio']:>7.3f}x {r['equity']:>7.2f}x {r['cagr']*100:>6.1f}% "
              f"{r['max_dd']*100:>6.1f}% {r['trades']:>7} | "
              f"{r['buy_threshold']:.2f}-{r['sell_threshold']:.2f}  "
              f"{r['alloc_min']:>3}%-{r['alloc_max']:>3}% | {fng_str}")

    best = results[0]

    print(f"\n{'='*100}")
    print(f"🎯 MEILLEURE STRATÉGIE (Rainbow only)")
    print(f"{'='*100}")

    print(f"\n📊 Performance:")
    print(f"   Equity: {best['equity']:.2f}x | Ratio: {best['ratio']:.3f}x vs B&H")
    print(f"   CAGR: {best['cagr']*100:.1f}% | Max DD: {best['max_dd']*100:.1f}%")
    print(f"   Sharpe: {best['sharpe']:.2f} | Trades: {best['trades']}")

    print(f"\n🌈 Paramètres Rainbow:")
    print(f"   Buy threshold: {best['buy_threshold']:.2f} (acheter quand Rainbow < {best['buy_threshold']:.2f})")
    print(f"   Sell threshold: {best['sell_threshold']:.2f} (vendre quand Rainbow > {best['sell_threshold']:.2f})")
    print(f"   Allocation range: {best['alloc_min']}% - {best['alloc_max']}%")

    if best['use_fng_filter']:
        print(f"\n📌 Filtre FNG activé:")
        print(f"   Réduire allocation si FNG > {best['fng_threshold']}")
    else:
        print(f"\n📌 Pas de filtre FNG (Rainbow pur)")

    if best['ratio'] > 1.0:
        print(f"\n🚀 SUCCÈS! Cette stratégie BAT le B&H de {best['ratio']:.2f}x!")
    else:
        print(f"\n⚠️  Sous-performe B&H ({best['ratio']:.2f}x)")
        print(f"    → Tester stratégie avec time decay")

    # Sauvegarder
    results_df = pd.DataFrame(results[:100])
    results_df.to_csv('outputs/rainbow_only_results.csv', index=False)
    print(f"\n💾 Résultats sauvegardés: outputs/rainbow_only_results.csv")

    return results, best

def test_time_decay_strategies(df, top_n=10):
    """
    Test stratégies avec dégradation temporelle
    """
    print(f"\n{'='*100}")
    print(f"⏰ TEST: Stratégies Rainbow avec Time Decay")
    print(f"{'='*100}")

    bh = df.copy()
    bh['pos'] = 100.0
    bh['trade'] = 0
    bh_result = run_backtest(bh, fees_bps=0.0)
    bh_equity = bh_result['metrics']['EquityFinal']

    buy_thresholds = [0.2, 0.25, 0.3, 0.35]
    sell_thresholds = [0.7, 0.75, 0.8, 0.85]
    alloc_mins = [0, 10, 20]
    alloc_maxs = [100]
    decay_rates = [0.90, 0.92, 0.94, 0.96, 0.98, 1.0]  # 1.0 = pas de decay

    results = []
    tested = 0

    for buy_t, sell_t, alloc_min, alloc_max, decay_r in product(
        buy_thresholds, sell_thresholds, alloc_mins, alloc_maxs, decay_rates
    ):
        if buy_t >= sell_t or alloc_min >= alloc_max:
            continue

        tested += 1

        try:
            signals = build_rainbow_time_decay_strategy(
                df, buy_t, sell_t, alloc_min, alloc_max, decay_rate=decay_r
            )

            result = run_backtest(signals, fees_bps=10.0)
            metrics = result['metrics']
            ratio = metrics['EquityFinal'] / bh_equity

            results.append({
                'buy_threshold': buy_t,
                'sell_threshold': sell_t,
                'alloc_min': alloc_min,
                'alloc_max': alloc_max,
                'decay_rate': decay_r,
                'equity': metrics['EquityFinal'],
                'ratio': ratio,
                'cagr': metrics['CAGR'],
                'max_dd': metrics['MaxDD'],
                'sharpe': metrics['Sharpe'],
                'trades': metrics['trades']
            })

            if tested % 50 == 0:
                best_so_far = max(results, key=lambda x: x['ratio'])
                print(f"   Testé: {tested} | Meilleur: {best_so_far['ratio']:.3f}x", end='\r')

        except Exception:
            continue

    print(f"\n✅ Tests terminés: {tested} combinaisons")

    results.sort(key=lambda x: x['ratio'], reverse=True)

    print(f"\n🏆 TOP {top_n} (Time Decay)\n")
    print(f"{'Rank':<6} {'Ratio':>8} {'Equity':>8} | Rainbow      Alloc    | Decay/an")
    print("-" * 80)

    for i, r in enumerate(results[:top_n], 1):
        marker = "🥇" if i == 1 else ("🥈" if i == 2 else ("🥉" if i == 3 else "  "))
        decay_pct = (1 - r['decay_rate']) * 100

        print(f"{marker} {i:<3} {r['ratio']:>7.3f}x {r['equity']:>7.2f}x | "
              f"{r['buy_threshold']:.2f}-{r['sell_threshold']:.2f}  "
              f"{r['alloc_min']:>3}%-{r['alloc_max']:>3}% | -{decay_pct:.0f}%")

    best = results[0]

    if best['ratio'] > 1.0:
        print(f"\n🚀 Stratégie Time Decay BAT B&H: {best['ratio']:.3f}x!")
    else:
        print(f"\n⚠️  Time decay sous-performe: {best['ratio']:.3f}x")

    results_df = pd.DataFrame(results[:50])
    results_df.to_csv('outputs/rainbow_time_decay_results.csv', index=False)
    print(f"\n💾 Sauvegardé: outputs/rainbow_time_decay_results.csv")

    return results, best

if __name__ == "__main__":
    print("Chargement données...")
    fng = load_fng_alt()
    btc = load_btc_prices()
    df = merge_daily(fng, btc)
    print(f"✅ {len(df)} jours\n")

    # Test 1: Rainbow pur
    results_rainbow, best_rainbow = grid_search_rainbow_only(df, top_n=30)

    # Test 2: Rainbow avec time decay
    results_decay, best_decay = test_time_decay_strategies(df, top_n=20)

    # Comparaison finale
    print(f"\n{'='*100}")
    print(f"🏁 COMPARAISON FINALE")
    print(f"{'='*100}")
    print(f"\n📊 Rainbow pur:      {best_rainbow['ratio']:.3f}x vs B&H")
    print(f"⏰ Rainbow time decay: {best_decay['ratio']:.3f}x vs B&H")

    if max(best_rainbow['ratio'], best_decay['ratio']) > 1.0:
        winner = "Rainbow pur" if best_rainbow['ratio'] > best_decay['ratio'] else "Time Decay"
        winner_ratio = max(best_rainbow['ratio'], best_decay['ratio'])
        print(f"\n🎉 VICTOIRE! {winner} bat le B&H: {winner_ratio:.3f}x!")
    else:
        print(f"\n⚠️  Aucune stratégie ne bat le B&H sur cette période")
