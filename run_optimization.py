#!/usr/bin/env python3
"""
Script simple pour trouver les meilleurs paramètres de stratégie Bitcoin

Utilise Walk-Forward Analysis pour éviter l'overfitting
"""
import sys
import pandas as pd
from datetime import datetime

# Import des modules
from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.optimize import grid_search, optuna_search, default_search_space
from src.fngbt.strategy import StrategyConfig
from src.fngbt.backtest import run_backtest
from src.fngbt.strategy import build_signals


def main():
    print("=" * 80)
    print("🚀 OPTIMISATION STRATÉGIE BITCOIN - FNG + RAINBOW CHART")
    print("=" * 80)

    # ========================================================================
    # 1. CHARGEMENT DES DONNÉES
    # ========================================================================
    print("\n📊 Chargement des données...")

    try:
        fng_df = load_fng_alt()
        print(f"   ✓ Fear & Greed Index: {len(fng_df)} jours")

        btc_df = load_btc_prices()
        print(f"   ✓ Prix Bitcoin: {len(btc_df)} jours")

        # Merge
        df = merge_daily(fng_df, btc_df)
        print(f"   ✓ Données fusionnées: {len(df)} jours")
        print(f"   ✓ Période: {df['date'].min().date()} → {df['date'].max().date()}")

    except Exception as e:
        print(f"\n❌ Erreur lors du chargement des données: {e}")
        sys.exit(1)

    # ========================================================================
    # 2. ESPACE DE RECHERCHE
    # ========================================================================
    print("\n🔍 Définition de l'espace de recherche...")

    # Vous pouvez personnaliser ces valeurs
    search_space = {
        # Seuils Fear & Greed (0-100)
        "fng_buy_threshold": [10, 15, 20, 25, 30, 35],  # FEAR → achat
        "fng_sell_threshold": [65, 70, 75, 80, 85, 90],  # GREED → vente

        # Seuils Rainbow Chart (0-1, position dans les bandes)
        "rainbow_buy_threshold": [0.15, 0.20, 0.25, 0.30, 0.35, 0.40],  # Prix bas → achat
        "rainbow_sell_threshold": [0.60, 0.65, 0.70, 0.75, 0.80, 0.85],  # Prix haut → vente

        # Allocation
        "max_allocation_pct": [100],
        "min_allocation_pct": [0],
        "min_position_change_pct": [5.0, 10.0, 15.0, 20.0],  # Changement min pour trader

        # Exécution
        "execute_next_day": [True],  # Toujours J+1 pour éviter look-ahead
    }

    total_combos = 1
    for key, values in search_space.items():
        total_combos *= len(values)
        print(f"   • {key}: {len(values)} valeurs")

    print(f"\n   📊 Total de combinaisons: {total_combos:,}")

    # ========================================================================
    # 3. CHOIX DE LA MÉTHODE D'OPTIMISATION
    # ========================================================================
    print("\n⚙️  Choisissez la méthode d'optimisation:")
    print("   1. Grid Search (teste toutes les combinaisons)")
    print("   2. Optuna (plus rapide, intelligent)")
    print("   3. Test rapide (une seule config par défaut)")

    choice = input("\nVotre choix (1/2/3) [défaut=2]: ").strip() or "2"

    # ========================================================================
    # 4. OPTIMISATION
    # ========================================================================
    fees_bps = 10.0  # 0.1% de frais
    use_walk_forward = True
    wf_n_folds = 5  # 5 périodes de test
    wf_train_ratio = 0.6  # 60% train, 40% test
    min_trades_per_year = 0.5  # Au moins un trade tous les 2 ans

    if choice == "1":
        # Grid Search
        print(f"\n🔍 Lancement du Grid Search...")
        print(f"   ⚠️  Attention: {total_combos:,} combinaisons à tester!")
        confirm = input("   Continuer? (y/n) [n]: ").strip().lower()

        if confirm != "y":
            print("\n❌ Annulé")
            sys.exit(0)

        results_df = grid_search(
            df=df,
            search_space=search_space,
            fees_bps=fees_bps,
            use_walk_forward=use_walk_forward,
            wf_n_folds=wf_n_folds,
            wf_train_ratio=wf_train_ratio,
            min_trades_per_year=min_trades_per_year,
        )

    elif choice == "2":
        # Optuna
        n_trials = int(input(f"\nNombre de trials Optuna [défaut=200]: ").strip() or "200")

        print(f"\n🔍 Lancement d'Optuna avec {n_trials} trials...")

        results_df = optuna_search(
            df=df,
            search_space=search_space,
            n_trials=n_trials,
            fees_bps=fees_bps,
            use_walk_forward=use_walk_forward,
            wf_n_folds=wf_n_folds,
            wf_train_ratio=wf_train_ratio,
            min_trades_per_year=min_trades_per_year,
        )

    else:
        # Test rapide
        print("\n⚡ Test rapide avec config par défaut...")
        cfg = StrategyConfig()

        from src.fngbt.optimize import walk_forward_cv

        result = walk_forward_cv(
            df=df,
            cfg=cfg,
            fees_bps=fees_bps,
            n_folds=wf_n_folds,
            train_ratio=wf_train_ratio
        )

        print("\n" + "=" * 80)
        print("📊 RÉSULTATS (Médiane des folds)")
        print("=" * 80)

        metrics = result["median_metrics"]
        print(f"Equity Finale:     {metrics['EquityFinal']:.2f}x")
        print(f"Buy & Hold:        {metrics['BHEquityFinal']:.2f}x")
        print(f"Ratio vs B&H:      {metrics['EquityFinal']/metrics['BHEquityFinal']:.2f}x")
        print(f"CAGR:              {metrics['CAGR']*100:.1f}%")
        print(f"Max Drawdown:      {metrics['MaxDD']*100:.1f}%")
        print(f"Sharpe Ratio:      {metrics['Sharpe']:.2f}")
        print(f"Trades/an:         {metrics['trades_per_year']:.1f}")

        print("\n✅ Test terminé!")
        sys.exit(0)

    # ========================================================================
    # 5. AFFICHAGE DES RÉSULTATS
    # ========================================================================
    if results_df.empty:
        print("\n❌ Aucun résultat trouvé!")
        sys.exit(1)

    print("\n" + "=" * 80)
    print("🏆 TOP 10 MEILLEURES CONFIGURATIONS")
    print("=" * 80)

    # Colonnes importantes à afficher
    display_cols = [
        "fng_buy_threshold",
        "fng_sell_threshold",
        "rainbow_buy_threshold",
        "rainbow_sell_threshold",
        "score",
        "cv_EquityFinal",
        "cv_CAGR",
        "cv_MaxDD",
        "cv_Sharpe",
        "cv_trades_per_year",
    ]

    available_cols = [col for col in display_cols if col in results_df.columns]

    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    pd.set_option('display.max_colwidth', 20)

    print("\n" + results_df[available_cols].head(10).to_string(index=True))

    # ========================================================================
    # 6. SAUVEGARDE DES RÉSULTATS
    # ========================================================================
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"outputs/optimization_results_{timestamp}.csv"

    results_df.to_csv(output_file, index=False)
    print(f"\n💾 Résultats sauvegardés: {output_file}")

    # ========================================================================
    # 7. MEILLEURE CONFIGURATION
    # ========================================================================
    best = results_df.iloc[0]

    print("\n" + "=" * 80)
    print("🥇 MEILLEURE CONFIGURATION")
    print("=" * 80)

    print("\nParamètres:")
    print(f"   FNG Buy Threshold:     {best['fng_buy_threshold']:.0f}")
    print(f"   FNG Sell Threshold:    {best['fng_sell_threshold']:.0f}")
    print(f"   Rainbow Buy Threshold: {best['rainbow_buy_threshold']:.2f}")
    print(f"   Rainbow Sell Threshold:{best['rainbow_sell_threshold']:.2f}")

    print("\nPerformance (Walk-Forward CV):")
    print(f"   Score:             {best['score']:.3f}x vs B&H")
    print(f"   Equity Finale:     {best.get('cv_EquityFinal', 0):.2f}x")
    print(f"   CAGR:              {best.get('cv_CAGR', 0)*100:.1f}%")
    print(f"   Max Drawdown:      {best.get('cv_MaxDD', 0)*100:.1f}%")
    print(f"   Sharpe Ratio:      {best.get('cv_Sharpe', 0):.2f}")
    print(f"   Trades/an:         {best.get('cv_trades_per_year', 0):.1f}")

    print("\nPerformance (Full Dataset):")
    print(f"   Equity Finale:     {best.get('full_EquityFinal', 0):.2f}x")
    print(f"   CAGR:              {best.get('full_CAGR', 0)*100:.1f}%")
    print(f"   Max Drawdown:      {best.get('full_MaxDD', 0)*100:.1f}%")
    print(f"   Sharpe Ratio:      {best.get('full_Sharpe', 0):.2f}")

    # ========================================================================
    # 8. BACKTEST DE LA MEILLEURE CONFIG
    # ========================================================================
    print("\n📈 Génération du backtest complet de la meilleure config...")

    best_cfg = StrategyConfig(
        fng_buy_threshold=int(best['fng_buy_threshold']),
        fng_sell_threshold=int(best['fng_sell_threshold']),
        rainbow_buy_threshold=float(best['rainbow_buy_threshold']),
        rainbow_sell_threshold=float(best['rainbow_sell_threshold']),
        max_allocation_pct=int(best['max_allocation_pct']),
        min_allocation_pct=int(best['min_allocation_pct']),
        execute_next_day=bool(best['execute_next_day']),
    )

    signals_df = build_signals(df, best_cfg)
    backtest_result = run_backtest(signals_df, fees_bps=fees_bps)

    # Sauvegarde du backtest
    backtest_file = f"outputs/best_backtest_{timestamp}.csv"
    backtest_result["df"].to_csv(backtest_file, index=False)
    print(f"💾 Backtest sauvegardé: {backtest_file}")

    print("\n" + "=" * 80)
    print("✅ OPTIMISATION TERMINÉE!")
    print("=" * 80)
    print(f"\nFichiers générés:")
    print(f"   • {output_file}")
    print(f"   • {backtest_file}")
    print("\n💡 Conseil: Analysez les résultats et vérifiez que les paramètres")
    print("   ont du sens économiquement (pas juste du curve-fitting!)")


if __name__ == "__main__":
    main()
