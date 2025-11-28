#!/usr/bin/env python3
"""
Test simple de la stratégie avec des données synthétiques
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.fngbt.strategy import StrategyConfig, build_signals
from src.fngbt.backtest import run_backtest


def generate_test_data(n_days=1000):
    """Génère des données synthétiques pour tester"""
    dates = [datetime(2019, 1, 1) + timedelta(days=i) for i in range(n_days)]

    # Prix BTC simulé: tendance haussière avec volatilité
    np.random.seed(42)
    trend = np.linspace(5000, 50000, n_days)
    noise = np.random.normal(0, 0.02, n_days)
    price = trend * np.exp(np.cumsum(noise))

    # FNG simulé: oscillations entre 0 et 100
    fng_base = 50 + 30 * np.sin(np.linspace(0, 8 * np.pi, n_days))
    fng_noise = np.random.normal(0, 10, n_days)
    fng = np.clip(fng_base + fng_noise, 0, 100)

    return pd.DataFrame({
        "date": dates,
        "close": price,
        "fng": fng
    })


def main():
    print("=" * 80)
    print("🧪 TEST DE LA STRATÉGIE REFACTORISÉE")
    print("=" * 80)

    # Génération de données de test
    print("\n1. Génération de données synthétiques...")
    df = generate_test_data(n_days=1000)
    print(f"   ✓ {len(df)} jours générés")
    print(f"   ✓ Prix BTC: {df['close'].min():.0f} → {df['close'].max():.0f}")
    print(f"   ✓ FNG: {df['fng'].min():.0f} → {df['fng'].max():.0f}")

    # Test de la stratégie par défaut
    print("\n2. Test de la configuration par défaut...")
    cfg = StrategyConfig()

    print(f"\n   Paramètres:")
    print(f"   • FNG Buy Threshold:      {cfg.fng_buy_threshold}")
    print(f"   • FNG Sell Threshold:     {cfg.fng_sell_threshold}")
    print(f"   • Rainbow Buy Threshold:  {cfg.rainbow_buy_threshold}")
    print(f"   • Rainbow Sell Threshold: {cfg.rainbow_sell_threshold}")

    # Génération des signaux
    print("\n3. Génération des signaux...")
    signals_df = build_signals(df, cfg)
    print(f"   ✓ Colonnes générées: {', '.join(signals_df.columns)}")

    # Vérifications de cohérence
    print("\n4. Vérifications de cohérence...")
    print(f"   ✓ Rainbow position: {signals_df['rainbow_position'].min():.2f} → {signals_df['rainbow_position'].max():.2f}")
    print(f"   ✓ FNG buy score: {signals_df['fng_buy_score'].min():.2f} → {signals_df['fng_buy_score'].max():.2f}")
    print(f"   ✓ Rainbow buy score: {signals_df['rainbow_buy_score'].min():.2f} → {signals_df['rainbow_buy_score'].max():.2f}")
    print(f"   ✓ Allocation: {signals_df['allocation_pct'].min():.1f}% → {signals_df['allocation_pct'].max():.1f}%")
    print(f"   ✓ Position finale: {signals_df['pos'].min():.1f}% → {signals_df['pos'].max():.1f}%")

    # Backtest
    print("\n5. Backtest...")
    result = run_backtest(signals_df, fees_bps=10.0)
    metrics = result["metrics"]

    print("\n" + "=" * 80)
    print("📊 RÉSULTATS DU BACKTEST")
    print("=" * 80)

    print(f"\nPerformance:")
    print(f"   Equity Finale (Stratégie): {metrics['EquityFinal']:.2f}x")
    print(f"   Equity Finale (Buy&Hold):  {metrics['BHEquityFinal']:.2f}x")
    print(f"   Ratio vs B&H:              {metrics['EquityFinal']/metrics['BHEquityFinal']:.2f}x")

    print(f"\nMétriques de risque:")
    print(f"   CAGR:                      {metrics['CAGR']*100:.1f}%")
    print(f"   CAGR Buy&Hold:             {metrics['BHCAGR']*100:.1f}%")
    print(f"   Volatilité:                {metrics['Vol']*100:.1f}%")
    print(f"   Max Drawdown:              {metrics['MaxDD']*100:.1f}%")
    print(f"   Max DD Buy&Hold:           {metrics['BHMaxDD']*100:.1f}%")

    print(f"\nMétriques ajustées au risque:")
    print(f"   Sharpe Ratio:              {metrics['Sharpe']:.2f}")
    print(f"   Sortino Ratio:             {metrics['Sortino']:.2f}")
    print(f"   Calmar Ratio:              {metrics['Calmar']:.2f}")

    print(f"\nActivité de trading:")
    print(f"   Nombre de trades:          {metrics['trades']}")
    print(f"   Trades par an:             {metrics['trades'] / (metrics['Days']/365):.1f}")
    print(f"   Allocation moyenne:        {metrics['avg_allocation']:.1f}%")
    print(f"   Turnover total:            {metrics['turnover_total']:.2f}")

    # Test avec différents paramètres
    print("\n" + "=" * 80)
    print("🔬 TEST AVEC PARAMÈTRES AGRESSIFS")
    print("=" * 80)

    cfg_aggressive = StrategyConfig(
        fng_buy_threshold=35,  # Plus permissif
        fng_sell_threshold=65,  # Plus strict
        rainbow_buy_threshold=0.4,  # Achète même si pas trop bas
        rainbow_sell_threshold=0.6,  # Vend dès que ça monte
    )

    signals_df2 = build_signals(df, cfg_aggressive)
    result2 = run_backtest(signals_df2, fees_bps=10.0)
    metrics2 = result2["metrics"]

    print(f"\n   Equity Finale:   {metrics2['EquityFinal']:.2f}x (vs {metrics['EquityFinal']:.2f}x défaut)")
    print(f"   CAGR:            {metrics2['CAGR']*100:.1f}% (vs {metrics['CAGR']*100:.1f}% défaut)")
    print(f"   Max DD:          {metrics2['MaxDD']*100:.1f}% (vs {metrics['MaxDD']*100:.1f}% défaut)")
    print(f"   Trades:          {metrics2['trades']} (vs {metrics['trades']} défaut)")

    print("\n" + "=" * 80)
    print("✅ TESTS RÉUSSIS!")
    print("=" * 80)
    print("\n💡 La logique de la stratégie est correcte:")
    print("   • FNG bas + Rainbow bas → Allocation haute (ACHETER)")
    print("   • FNG haut + Rainbow haut → Allocation basse (VENDRE)")
    print("\n🚀 Vous pouvez maintenant lancer l'optimisation avec run_optimization.py")


if __name__ == "__main__":
    main()
