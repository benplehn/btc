#!/usr/bin/env python3
"""
Script de debug pour vérifier le chargement des données
"""
import sys

print("=" * 80)
print("🔍 DEBUG - VÉRIFICATION DES DONNÉES")
print("=" * 80)

# Test des imports
print("\n1. Test des imports...")
try:
    import pandas as pd
    print("   ✓ pandas")
except ImportError as e:
    print(f"   ❌ pandas: {e}")
    sys.exit(1)

try:
    import numpy as np
    print("   ✓ numpy")
except ImportError as e:
    print(f"   ❌ numpy: {e}")
    sys.exit(1)

try:
    import requests
    print("   ✓ requests")
except ImportError as e:
    print(f"   ❌ requests: {e}")
    sys.exit(1)

try:
    import yfinance as yf
    print("   ✓ yfinance")
except ImportError as e:
    print(f"   ⚠️  yfinance: {e}")
    print("   → Installation: pip install yfinance")

# Test du chargement Fear & Greed
print("\n2. Test chargement Fear & Greed Index...")
try:
    from src.fngbt.data import load_fng_alt
    fng_df = load_fng_alt()
    print(f"   ✓ {len(fng_df)} jours chargés")
    print(f"   ✓ Période: {fng_df['date'].min().date()} → {fng_df['date'].max().date()}")
    print(f"   ✓ FNG min: {fng_df['fng'].min():.0f}, max: {fng_df['fng'].max():.0f}")

    # Afficher les dernières valeurs
    print("\n   Dernières valeurs:")
    for idx, row in fng_df.tail(5).iterrows():
        print(f"     {row['date'].date()}: FNG = {row['fng']:.0f}")

except Exception as e:
    print(f"   ❌ Erreur: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test du chargement Bitcoin
print("\n3. Test chargement prix Bitcoin...")
try:
    from src.fngbt.data import load_btc_prices
    btc_df = load_btc_prices()
    print(f"   ✓ {len(btc_df)} jours chargés")
    print(f"   ✓ Période: {btc_df['date'].min().date()} → {btc_df['date'].max().date()}")
    print(f"   ✓ Prix min: ${btc_df['close'].min():.2f}, max: ${btc_df['close'].max():.2f}")

    # Afficher les dernières valeurs
    print("\n   Derniers prix:")
    for idx, row in btc_df.tail(5).iterrows():
        print(f"     {row['date'].date()}: ${row['close']:,.2f}")

except Exception as e:
    print(f"   ❌ Erreur: {e}")
    import traceback
    traceback.print_exc()

    print("\n   💡 Si yfinance ne fonctionne pas, vous pouvez:")
    print("      1. Réessayer: parfois ça passe après plusieurs tentatives")
    print("      2. Utiliser des données locales (CSV)")
    print("      3. Utiliser test_strategy.py avec données synthétiques")
    sys.exit(1)

# Test du merge
print("\n4. Test fusion des données...")
try:
    from src.fngbt.data import merge_daily
    df = merge_daily(fng_df, btc_df)
    print(f"   ✓ {len(df)} jours après fusion")
    print(f"   ✓ Période: {df['date'].min().date()} → {df['date'].max().date()}")

    # Vérification de la qualité
    missing_fng = df['fng'].isna().sum()
    missing_btc = df['close'].isna().sum()

    if missing_fng > 0:
        print(f"   ⚠️  {missing_fng} valeurs FNG manquantes")
    if missing_btc > 0:
        print(f"   ⚠️  {missing_btc} valeurs prix manquantes")

    if missing_fng == 0 and missing_btc == 0:
        print(f"   ✓ Aucune valeur manquante")

    # Statistiques
    print("\n   Statistiques:")
    print(f"     FNG moyen: {df['fng'].mean():.1f} (écart-type: {df['fng'].std():.1f})")
    print(f"     Prix moyen: ${df['close'].mean():,.2f}")
    print(f"     Rendement total B&H: {(df['close'].iloc[-1] / df['close'].iloc[0] - 1) * 100:.1f}%")

except Exception as e:
    print(f"   ❌ Erreur: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test de la stratégie
print("\n5. Test de la stratégie...")
try:
    from src.fngbt.strategy import StrategyConfig, build_signals
    from src.fngbt.backtest import run_backtest

    cfg = StrategyConfig()
    signals = build_signals(df, cfg)
    print(f"   ✓ Signaux générés: {len(signals)} jours")

    result = run_backtest(signals, fees_bps=10.0)
    metrics = result["metrics"]

    print(f"\n   Performance rapide:")
    print(f"     Equity finale: {metrics['EquityFinal']:.2f}x")
    print(f"     Buy & Hold: {metrics['BHEquityFinal']:.2f}x")
    print(f"     Ratio vs B&H: {metrics['EquityFinal']/metrics['BHEquityFinal']:.2f}x")
    print(f"     Trades: {metrics['trades']}")

except Exception as e:
    print(f"   ❌ Erreur: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Validation pour walk-forward
print("\n6. Validation pour walk-forward...")
min_days_per_fold = 50
possible_folds = len(df) // min_days_per_fold

print(f"   Données disponibles: {len(df)} jours")
print(f"   Folds possibles (50 jours/fold): {possible_folds}")

if possible_folds >= 5:
    print(f"   ✓ Assez de données pour 5 folds")
elif possible_folds >= 2:
    print(f"   ⚠️  Seulement {possible_folds} folds possibles")
    print(f"      Recommandation: utiliser {possible_folds} folds dans run_optimization.py")
else:
    print(f"   ❌ Pas assez de données pour walk-forward")
    print(f"      Il faut au minimum 100 jours")

print("\n" + "=" * 80)
print("✅ DIAGNOSTIC TERMINÉ")
print("=" * 80)

if len(df) >= 250:
    print("\n🚀 Vous pouvez lancer: python3 run_optimization.py")
elif len(df) >= 100:
    print("\n⚠️  Données limitées. Utilisez l'option 'Test rapide' dans run_optimization.py")
else:
    print("\n❌ Pas assez de données. Utilisez test_strategy.py avec données synthétiques")
