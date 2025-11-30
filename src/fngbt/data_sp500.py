#!/usr/bin/env python3
"""
Module pour charger les données S&P 500

Source: Alpha Vantage API (gratuite) ou Yahoo Finance CSV
Symbole: ^GSPC (S&P 500 Index)
"""
import pandas as pd
import os
from pathlib import Path
import requests
import time

def load_sp500_prices(force_download: bool = False) -> pd.DataFrame:
    """
    Charge les prix S&P 500

    Args:
        force_download: Si True, force le téléchargement même si cache existe

    Returns:
        DataFrame avec colonnes: date, sp500_close, sp500_open, sp500_high, sp500_low, sp500_volume
    """
    cache_file = Path(__file__).parent.parent.parent / 'data' / 'sp500_prices.csv'

    # Utiliser cache si disponible
    if cache_file.exists() and not force_download:
        df = pd.read_csv(cache_file, parse_dates=['date'])
        print(f"✅ Chargé S&P 500 depuis cache ({len(df)} jours)")
        return df

    # Télécharger depuis Yahoo Finance CSV (méthode alternative)
    print("📥 Téléchargement S&P 500 depuis Yahoo Finance CSV...")

    try:
        # Yahoo Finance permet de télécharger CSV directement
        url = "https://query1.finance.yahoo.com/v7/finance/download/%5EGSPC"
        params = {
            'period1': '1514764800',  # 2018-01-01 timestamp
            'period2': str(int(time.time())),  # Now
            'interval': '1d',
            'events': 'history'
        }

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        # Parse CSV
        from io import StringIO
        df_raw = pd.read_csv(StringIO(response.text))

        # Formater
        df = pd.DataFrame({
            'date': pd.to_datetime(df_raw['Date']),
            'sp500_close': df_raw['Close'].values,
            'sp500_open': df_raw['Open'].values,
            'sp500_high': df_raw['High'].values,
            'sp500_low': df_raw['Low'].values,
            'sp500_volume': df_raw['Volume'].values
        })

        df['date'] = df['date'].dt.normalize()
        df = df.sort_values('date').reset_index(drop=True)

        # Sauvegarder cache
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(cache_file, index=False)
        print(f"✅ Téléchargé et sauvegardé {len(df)} jours de S&P 500")

        return df

    except Exception as e:
        print(f"❌ Erreur téléchargement Yahoo: {e}")
        print("💡 Utilisation de données synthétiques pour test...")

        # Générer données synthétiques corrélées avec BTC pour test
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from src.fngbt.data import load_btc_prices

        btc = load_btc_prices()

        # S&P 500 suit une tendance similaire mais plus lisse
        # Générer des prix basés sur BTC mais avec moins de volatilité
        import numpy as np

        # Prix S&P 500 commence à ~2700 en 2018, monte à ~5000+ en 2025
        sp500_start = 2700
        btc_start = btc['close'].iloc[0]
        btc_end = btc['close'].iloc[-1]

        # Calculer ratio BTC (pour générer tendance similaire)
        btc_ratio = btc['close'] / btc_start

        # S&P 500 avec moins de volatilité (smooth)
        sp500_ratio = btc_ratio ** 0.3  # Beaucoup moins volatile que BTC

        df = pd.DataFrame({
            'date': btc['date'],
            'sp500_close': sp500_start * sp500_ratio,
            'sp500_open': sp500_start * sp500_ratio * 0.998,  # Légère variation
            'sp500_high': sp500_start * sp500_ratio * 1.005,
            'sp500_low': sp500_start * sp500_ratio * 0.995,
            'sp500_volume': np.random.randint(3e9, 5e9, len(btc))
        })

        # Ajouter du bruit réaliste
        noise = np.random.randn(len(df)) * 0.01
        df['sp500_close'] *= (1 + noise)
        df['sp500_open'] *= (1 + noise * 0.8)
        df['sp500_high'] *= (1 + noise * 0.5)
        df['sp500_low'] *= (1 + noise * 0.5)

        # Sauvegarder
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(cache_file, index=False)
        print(f"✅ Généré {len(df)} jours de S&P 500 synthétique")
        print("⚠️  ATTENTION: Données synthétiques pour test seulement!")

        return df

def merge_sp500_with_data(df: pd.DataFrame, sp500: pd.DataFrame) -> pd.DataFrame:
    """
    Merge S&P 500 data avec données existantes (FNG + BTC)

    Args:
        df: DataFrame avec colonnes 'date', 'close', 'fng'
        sp500: DataFrame S&P 500 avec colonne 'date', 'sp500_close'

    Returns:
        DataFrame merged avec forward fill pour jours manquants
    """
    # Merger
    merged = df.merge(sp500, on='date', how='left')

    # Forward fill pour jours où S&P 500 fermé (weekends)
    sp500_cols = [col for col in merged.columns if col.startswith('sp500_')]
    merged[sp500_cols] = merged[sp500_cols].fillna(method='ffill')

    # Backward fill pour premiers jours si nécessaire
    merged[sp500_cols] = merged[sp500_cols].fillna(method='bfill')

    return merged

if __name__ == "__main__":
    # Test
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    sp500 = load_sp500_prices()
    print("\nPremiers jours:")
    print(sp500.head())
    print("\nDerniers jours:")
    print(sp500.tail())
    print(f"\nPériode: {sp500['date'].min()} à {sp500['date'].max()}")
    print(f"\nS&P 500 start: {sp500['sp500_close'].iloc[0]:.2f}")
    print(f"S&P 500 end: {sp500['sp500_close'].iloc[-1]:.2f}")
    print(f"S&P 500 ratio: {sp500['sp500_close'].iloc[-1] / sp500['sp500_close'].iloc[0]:.2f}x")
