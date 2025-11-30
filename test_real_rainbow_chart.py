#!/usr/bin/env python3
"""
🌈 TEST: VRAI Rainbow Chart (formule officielle)

Comparaison:
1. Rainbow actuel (régression personnalisée)
2. Rainbow officiel V1 (Trolololo 2014)
3. Rainbow officiel V2 (Rohmeo 2022 - si formule trouvée)

Objectif: Valider quelle formule utiliser
"""
import pandas as pd
import numpy as np
from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.strategy import calculate_rainbow_position
import warnings
warnings.filterwarnings('ignore')

print("="*100)
print("🌈 TEST: Quel Rainbow Chart utiliser?")
print("="*100)
print()

# Load data
print("Chargement données...")
fng = load_fng_alt()
btc = load_btc_prices()
df = merge_daily(fng, btc)
print(f"✅ {len(df)} jours\n")

# ============================================================================
# RAINBOW ACTUEL (Régression personnalisée)
# ============================================================================

print("="*100)
print("📊 RAINBOW ACTUEL (Régression sur données)")
print("="*100)
print()

df_current = calculate_rainbow_position(df)

print("Statistiques Rainbow ACTUEL par année:")
print("-" * 80)
for year in [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]:
    df_year = df_current[df_current['date'].dt.year == year]
    if len(df_year) > 0:
        r = df_year['rainbow_position']
        print(f"{year}: min={r.min():.3f}, median={r.median():.3f}, max={r.max():.3f}")
print()

# ============================================================================
# RAINBOW OFFICIEL V1 (Trolololo 2014)
# ============================================================================

print("="*100)
print("🎯 RAINBOW OFFICIEL V1 (Trolololo 2014)")
print("="*100)
print()

print("Formule: 10^(3.109106 * ln(weeks_since_genesis) - 8.164198)")
print()

def calculate_rainbow_v1_official(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rainbow Chart officiel V1 (Trolololo 2014)

    Formule: price_center = 10^(3.109106 * ln(weeks) - 8.164198)

    Bandes (d'après blockchain center):
    - Maximum bubble (red): center * 4.0
    - Sell. Seriously, SELL! (orange): center * 3.0
    - FOMO intensifies (yellow): center * 2.0
    - Is this a bubble? (light green): center * 1.5
    - Still cheap (green): center * 1.0 (CENTER)
    - Accumulate (blue): center * 0.5
    - Buy! (dark blue): center * 0.25
    - Fire sale! (violet): center * 0.125
    """
    d = df.copy()

    # Genesis: 2009-01-09 (date du bloc genesis pour le rainbow)
    genesis = pd.Timestamp("2009-01-09")

    # Semaines depuis genesis
    days_since_genesis = (d["date"] - genesis).dt.days.clip(lower=1)
    weeks_since_genesis = days_since_genesis / 7.0

    # Formule Trolololo (utilise ln = log naturel)
    # price = 10^(3.109106 * ln(weeks) - 8.164198)
    log_center = 3.109106 * np.log(weeks_since_genesis) - 8.164198
    price_center = 10 ** log_center

    # Bandes Rainbow (multiplicateurs)
    # D'après blockchain center, les bandes sont des multiples de la ligne centrale
    band_multipliers = {
        'fire_sale': 0.125,      # Violet (Fire sale!)
        'buy': 0.25,             # Dark blue (Buy!)
        'accumulate': 0.5,       # Blue (Accumulate)
        'still_cheap': 1.0,      # Green (Still cheap) = CENTER
        'is_bubble': 1.5,        # Light green (Is this a bubble?)
        'fomo': 2.0,             # Yellow (FOMO intensifies)
        'sell': 3.0,             # Orange (Sell. Seriously, SELL!)
        'max_bubble': 4.0        # Red (Maximum bubble territory)
    }

    # Calculer les bandes
    d['rainbow_v1_center'] = price_center
    d['rainbow_v1_fire_sale'] = price_center * band_multipliers['fire_sale']
    d['rainbow_v1_buy'] = price_center * band_multipliers['buy']
    d['rainbow_v1_accumulate'] = price_center * band_multipliers['accumulate']
    d['rainbow_v1_still_cheap'] = price_center * band_multipliers['still_cheap']
    d['rainbow_v1_is_bubble'] = price_center * band_multipliers['is_bubble']
    d['rainbow_v1_fomo'] = price_center * band_multipliers['fomo']
    d['rainbow_v1_sell'] = price_center * band_multipliers['sell']
    d['rainbow_v1_max_bubble'] = price_center * band_multipliers['max_bubble']

    # Position normalisée (0-1)
    # 0 = Fire sale (violet), 1 = Maximum bubble (red)
    min_price = d['rainbow_v1_fire_sale']
    max_price = d['rainbow_v1_max_bubble']

    # Position en échelle log (meilleure distribution)
    log_price = np.log10(d['close'].clip(lower=1e-9))
    log_min = np.log10(min_price.clip(lower=1e-9))
    log_max = np.log10(max_price.clip(lower=1e-9))

    rainbow_position_v1 = (log_price - log_min) / (log_max - log_min)
    rainbow_position_v1 = rainbow_position_v1.clip(0.0, 1.0).fillna(0.5)

    d['rainbow_position_v1'] = rainbow_position_v1

    return d

df_v1 = calculate_rainbow_v1_official(df)

print("Statistiques Rainbow OFFICIEL V1 par année:")
print("-" * 80)
for year in [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]:
    df_year = df_v1[df_v1['date'].dt.year == year]
    if len(df_year) > 0:
        r = df_year['rainbow_position_v1']
        print(f"{year}: min={r.min():.3f}, median={r.median():.3f}, max={r.max():.3f}")
print()

# Vérifier dans quelle bande on est
print("Analyse détaillée 2024-2025:")
print("-" * 80)

df_recent = df_v1[df_v1['date'] >= '2024-01-01'].copy()

# Déterminer la bande pour chaque jour
def get_rainbow_band(row):
    price = row['close']
    if price < row['rainbow_v1_buy']:
        return 'Fire Sale (violet)' if price < row['rainbow_v1_fire_sale'] else 'Buy! (dark blue)'
    elif price < row['rainbow_v1_accumulate']:
        return 'Accumulate (blue)'
    elif price < row['rainbow_v1_still_cheap']:
        return 'Still Cheap (green)'
    elif price < row['rainbow_v1_is_bubble']:
        return 'Is this a bubble? (light green)'
    elif price < row['rainbow_v1_fomo']:
        return 'FOMO intensifies (yellow)'
    elif price < row['rainbow_v1_sell']:
        return 'Sell. Seriously, SELL! (orange)'
    else:
        return 'Maximum bubble (red)'

df_recent['band'] = df_recent.apply(get_rainbow_band, axis=1)

# Distribution des bandes en 2024-2025
band_counts = df_recent['band'].value_counts()
total_days = len(df_recent)

print("Distribution des jours par bande (2024-2025):")
for band, count in band_counts.items():
    pct = count / total_days * 100
    print(f"  {band:40s}: {count:3d} jours ({pct:5.1f}%)")
print()

# ============================================================================
# COMPARAISON: Actuel vs Officiel V1
# ============================================================================

print("="*100)
print("⚖️  COMPARAISON: Rainbow Actuel vs Officiel V1")
print("="*100)
print()

comparison = pd.DataFrame()
for year in [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]:
    df_year = df_v1[df_v1['date'].dt.year == year]
    if len(df_year) > 0:
        comparison = pd.concat([comparison, pd.DataFrame([{
            'Année': year,
            'Actuel_min': df_year['rainbow_position'].min(),
            'Actuel_median': df_year['rainbow_position'].median(),
            'V1_min': df_year['rainbow_position_v1'].min(),
            'V1_median': df_year['rainbow_position_v1'].median(),
            'Diff_min': df_year['rainbow_position_v1'].min() - df_year['rainbow_position'].min(),
            'Diff_median': df_year['rainbow_position_v1'].median() - df_year['rainbow_position'].median()
        }])], ignore_index=True)

print(comparison.to_string(index=False))
print()

# ============================================================================
# TEST: Rainbow V1 avec stratégie "Buy Cheap Only"
# ============================================================================

print("="*100)
print("🧪 TEST: Buy Cheap Only avec Rainbow OFFICIEL V1")
print("="*100)
print()

from src.fngbt.backtest_realistic_fees import run_backtest_realistic_fees

bh_ratio = df['close'].iloc[-1] / df['close'].iloc[0]

# Test différents thresholds avec Rainbow V1
print("Test thresholds avec Rainbow OFFICIEL V1:\n")

results_v1 = []

for threshold in [0.15, 0.18, 0.20, 0.22, 0.25, 0.28, 0.30, 0.33, 0.35]:
    d = df_v1.copy()
    d['pos'] = np.where(d['rainbow_position_v1'] < threshold, 100, 0)

    result = run_backtest_realistic_fees(d, initial_capital=100.0, fee_rate=0.001)
    metrics = result['metrics']
    ratio_bh = metrics['EquityFinal'] / (bh_ratio * 100)

    time_in_btc = (d['pos'] == 100).sum() / len(d) * 100

    results_v1.append({
        'threshold': threshold,
        'equity': metrics['EquityFinal'],
        'ratio_bh': ratio_bh,
        'trades': metrics['trades'],
        'fees': metrics['total_fees_paid'],
        'time_in_btc': time_in_btc
    })

df_results_v1 = pd.DataFrame(results_v1).sort_values('ratio_bh', ascending=False)

print("Résultats avec Rainbow OFFICIEL V1:")
print(df_results_v1.to_string(index=False))
print()

best_v1 = df_results_v1.iloc[0]
print(f"🥇 Meilleur threshold (V1): {best_v1['threshold']:.2f}")
print(f"   Equity: {best_v1['equity']:.2f} EUR ({best_v1['ratio_bh']:.2f}x vs B&H)")
print(f"   Temps en BTC: {best_v1['time_in_btc']:.1f}%")
print()

# Comparaison avec actuel
print("Comparaison Actuel vs V1:")
print("-" * 80)

# Refaire avec actuel (threshold 0.25)
d_current = df_current.copy()
d_current['pos'] = np.where(d_current['rainbow_position'] < 0.25, 100, 0)
result_current = run_backtest_realistic_fees(d_current, initial_capital=100.0, fee_rate=0.001)
metrics_current = result_current['metrics']
ratio_current = metrics_current['EquityFinal'] / (bh_ratio * 100)

print(f"Rainbow ACTUEL (threshold 0.25):  {metrics_current['EquityFinal']:.2f} EUR ({ratio_current:.2f}x)")
print(f"Rainbow V1 (threshold {best_v1['threshold']:.2f}): {best_v1['equity']:.2f} EUR ({best_v1['ratio_bh']:.2f}x)")
print()

if best_v1['ratio_bh'] > ratio_current:
    improvement = ((best_v1['ratio_bh'] - ratio_current) / ratio_current) * 100
    print(f"✅ Rainbow V1 est MEILLEUR de +{improvement:.1f}%!")
else:
    degradation = ((ratio_current - best_v1['ratio_bh']) / ratio_current) * 100
    print(f"⚠️  Rainbow V1 est PIRE de -{degradation:.1f}%")
print()

# Analyse 2024-2025 spécifiquement
print("="*100)
print("🔍 ANALYSE 2024-2025 avec Rainbow V1")
print("="*100)
print()

df_2024 = df_v1[df_v1['date'] >= '2024-01-01'].copy()

print(f"Rainbow V1 en 2024-2025:")
print(f"   Min: {df_2024['rainbow_position_v1'].min():.3f}")
print(f"   Médiane: {df_2024['rainbow_position_v1'].median():.3f}")
print(f"   Max: {df_2024['rainbow_position_v1'].max():.3f}")
print()

for threshold in [0.20, 0.25, 0.30, 0.35]:
    pct_below = (df_2024['rainbow_position_v1'] < threshold).sum() / len(df_2024) * 100
    print(f"   % jours < {threshold:.2f}: {pct_below:.1f}%")
print()

# Sauvegarder pour inspection
df_v1[['date', 'close', 'rainbow_position', 'rainbow_position_v1',
       'rainbow_v1_fire_sale', 'rainbow_v1_buy', 'rainbow_v1_accumulate',
       'rainbow_v1_still_cheap', 'rainbow_v1_center']].to_csv(
    'outputs/rainbow_comparison_v1.csv', index=False
)

print("💾 Sauvegardé: outputs/rainbow_comparison_v1.csv")
print()

print("="*100)
print("🎯 CONCLUSION")
print("="*100)
print()

print("Rainbow ACTUEL (régression personnalisée):")
print(f"   - Basé sur polyfit des données historiques")
print(f"   - Min/max adaptatifs")
print(f"   - 2024: min={df_current[df_current['date'].dt.year==2024]['rainbow_position'].min():.3f}")
print()

print("Rainbow OFFICIEL V1 (Trolololo 2014):")
print(f"   - Formule fixe: 10^(3.109106 * ln(weeks) - 8.164198)")
print(f"   - Bandes fixes (multiplicateurs de 0.125 à 4.0)")
print(f"   - 2024: min={df_2024['rainbow_position_v1'].min():.3f}")
print()

print("💡 Validation requise:")
print("   ✅ Vérifie outputs/rainbow_comparison_v1.csv")
print("   ✅ Compare les valeurs avec blockchaincenter.net")
print("   ✅ Confirme quelle formule utiliser")
print()

print("✨ Test Rainbow Chart terminé!")
