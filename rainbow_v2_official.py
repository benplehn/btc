#!/usr/bin/env python3
"""
🌈 RAINBOW CHART V2 OFFICIEL (Rohmeo 2022)

Logique V2 (blockchaincenter.net):
1. Courbe HAUTE (rouge) = régression sur tous les HIGHS de l'histoire BTC
2. Courbe BASSE (bleue) = régression sur tous les LOWS de l'histoire BTC
3. Interpolation linéaire entre les deux pour créer les 8 bandes

Différence vs mon Rainbow actuel:
- Actuel: régression sur TOUT le dataset (moyenne)
- V2: deux courbes séparées (min et max) → meilleur fit des extrêmes
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from src.fngbt.data import load_btc_prices
import warnings
warnings.filterwarnings('ignore')

print("="*100)
print("🌈 RAINBOW CHART V2 OFFICIEL (2022)")
print("="*100)
print()

# ============================================================================
# 1. CHARGER LES DONNÉES
# ============================================================================

print("Chargement données BTC...")
btc = load_btc_prices()
print(f"✅ {len(btc)} jours (depuis {btc['date'].min()} jusqu'à {btc['date'].max()})")
print()

# Genesis Bitcoin: 2009-01-03
genesis = pd.Timestamp("2009-01-03")

# Ajouter jours depuis genesis
btc['days_since_genesis'] = (btc['date'] - genesis).dt.days.clip(lower=1)

# ============================================================================
# 2. IDENTIFIER LES HIGHS ET LOWS LOCAUX
# ============================================================================

print("="*100)
print("📊 IDENTIFICATION DES HIGHS ET LOWS")
print("="*100)
print()

# Highs locaux: prix > voisins dans une fenêtre
window = 30  # 30 jours pour identifier un pic

btc['rolling_max'] = btc['close'].rolling(window=window*2+1, center=True, min_periods=1).max()
btc['rolling_min'] = btc['close'].rolling(window=window*2+1, center=True, min_periods=1).min()

btc['is_high'] = (btc['close'] == btc['rolling_max']) & (btc['close'] > btc['close'].shift(1))
btc['is_low'] = (btc['close'] == btc['rolling_min']) & (btc['close'] < btc['close'].shift(1))

highs = btc[btc['is_high']].copy()
lows = btc[btc['is_low']].copy()

print(f"Highs locaux identifiés: {len(highs)}")
print(f"Lows locaux identifiés: {len(lows)}")
print()

# Afficher quelques exemples
print("Exemples de HIGHS majeurs:")
print(highs.nlargest(10, 'close')[['date', 'close', 'days_since_genesis']].to_string(index=False))
print()

print("Exemples de LOWS majeurs:")
print(lows.nsmallest(10, 'close')[['date', 'close', 'days_since_genesis']].to_string(index=False))
print()

# ============================================================================
# 3. RÉGRESSION LOG-LOG SUR HIGHS ET LOWS
# ============================================================================

print("="*100)
print("📈 RÉGRESSION LOG-LOG")
print("="*100)
print()

# Régression sur HIGHS
x_highs = np.log10(highs['days_since_genesis'])
y_highs = np.log10(highs['close'].clip(lower=1e-9))

# Polyfit degré 1 (ligne) ou degré 2 (courbe) ?
# Essayons degré 2 pour mieux capturer la courbure
coeffs_high = np.polyfit(x_highs, y_highs, deg=2)
print(f"Coefficients HIGHS (deg=2): a={coeffs_high[0]:.6f}, b={coeffs_high[1]:.6f}, c={coeffs_high[2]:.6f}")
print(f"  → log10(price_high) = {coeffs_high[0]:.6f} * log10(days)^2 + {coeffs_high[1]:.6f} * log10(days) + {coeffs_high[2]:.6f}")
print()

# Régression sur LOWS
x_lows = np.log10(lows['days_since_genesis'])
y_lows = np.log10(lows['close'].clip(lower=1e-9))

coeffs_low = np.polyfit(x_lows, y_lows, deg=2)
print(f"Coefficients LOWS (deg=2): a={coeffs_low[0]:.6f}, b={coeffs_low[1]:.6f}, c={coeffs_low[2]:.6f}")
print(f"  → log10(price_low) = {coeffs_low[0]:.6f} * log10(days)^2 + {coeffs_low[1]:.6f} * log10(days) + {coeffs_low[2]:.6f}")
print()

# ============================================================================
# 4. CALCULER LES BANDES RAINBOW V2
# ============================================================================

print("="*100)
print("🌈 CALCUL DES BANDES RAINBOW V2")
print("="*100)
print()

def calculate_rainbow_v2(df, coeffs_high, coeffs_low):
    """
    Rainbow V2: interpolation entre courbe haute et basse

    8 bandes (de bas en haut):
    0. Fire Sale (violet) = LOW
    1. Buy! (dark blue) = LOW + 1/7 * (HIGH - LOW)
    2. Accumulate (blue) = LOW + 2/7 * (HIGH - LOW)
    3. Still Cheap (green) = LOW + 3/7 * (HIGH - LOW)
    4. Is this a bubble? (light green) = LOW + 4/7 * (HIGH - LOW)
    5. FOMO intensifies (yellow) = LOW + 5/7 * (HIGH - LOW)
    6. Sell! (orange) = LOW + 6/7 * (HIGH - LOW)
    7. Maximum Bubble (red) = HIGH
    """
    d = df.copy()

    # Log des jours
    log_days = np.log10(d['days_since_genesis'])

    # Courbe HAUTE (régression deg=2)
    log_price_high = coeffs_high[0] * log_days**2 + coeffs_high[1] * log_days + coeffs_high[2]
    price_high = 10 ** log_price_high

    # Courbe BASSE (régression deg=2)
    log_price_low = coeffs_low[0] * log_days**2 + coeffs_low[1] * log_days + coeffs_low[2]
    price_low = 10 ** log_price_low

    # 8 bandes par interpolation
    d['rainbow_v2_fire_sale'] = price_low  # 0/7
    d['rainbow_v2_buy'] = price_low + 1/7 * (price_high - price_low)  # 1/7
    d['rainbow_v2_accumulate'] = price_low + 2/7 * (price_high - price_low)  # 2/7
    d['rainbow_v2_still_cheap'] = price_low + 3/7 * (price_high - price_low)  # 3/7
    d['rainbow_v2_is_bubble'] = price_low + 4/7 * (price_high - price_low)  # 4/7
    d['rainbow_v2_fomo'] = price_low + 5/7 * (price_high - price_low)  # 5/7
    d['rainbow_v2_sell'] = price_low + 6/7 * (price_high - price_low)  # 6/7
    d['rainbow_v2_max_bubble'] = price_high  # 7/7

    # Position normalisée (0-1)
    # En échelle LOG pour meilleure distribution
    log_price_actual = np.log10(d['close'].clip(lower=1e-9))

    # Normaliser entre log_price_low et log_price_high
    rainbow_position_v2 = (log_price_actual - log_price_low) / (log_price_high - log_price_low)
    rainbow_position_v2 = rainbow_position_v2.clip(0.0, 1.0).fillna(0.5)

    d['rainbow_position_v2'] = rainbow_position_v2

    return d

btc_v2 = calculate_rainbow_v2(btc, coeffs_high, coeffs_low)

print("✅ Bandes Rainbow V2 calculées")
print()

# ============================================================================
# 5. STATISTIQUES PAR ANNÉE
# ============================================================================

print("="*100)
print("📊 STATISTIQUES RAINBOW V2 PAR ANNÉE")
print("="*100)
print()

print("Année | Min   | P25   | Médiane | P75   | Max   | % Fire Sale | % Buy")
print("-" * 80)

for year in range(2018, 2026):
    df_year = btc_v2[btc_v2['date'].dt.year == year]
    if len(df_year) > 0:
        r = df_year['rainbow_position_v2']
        pct_fire = (r < 1/7).sum() / len(df_year) * 100
        pct_buy = ((r >= 1/7) & (r < 2/7)).sum() / len(df_year) * 100

        print(f"{year}  | {r.min():.3f} | {r.quantile(0.25):.3f} | "
              f"{r.median():.3f} | {r.quantile(0.75):.3f} | {r.max():.3f} | "
              f"{pct_fire:6.1f}% | {pct_buy:5.1f}%")

print()

# Position actuelle (Nov 2024-2025)
recent = btc_v2[btc_v2['date'] >= '2024-11-01']
print(f"Position actuelle (Nov 2024-2025):")
print(f"   Rainbow V2 min: {recent['rainbow_position_v2'].min():.3f}")
print(f"   Rainbow V2 médiane: {recent['rainbow_position_v2'].median():.3f}")
print(f"   Rainbow V2 max: {recent['rainbow_position_v2'].max():.3f}")

if recent['rainbow_position_v2'].median() < 1/7:
    band = "🟣 FIRE SALE"
elif recent['rainbow_position_v2'].median() < 2/7:
    band = "🔵 BUY!"
elif recent['rainbow_position_v2'].median() < 3/7:
    band = "🔵 ACCUMULATE"
else:
    band = "🟢 STILL CHEAP ou plus haut"

print(f"   Bande médiane: {band}")
print()

# ============================================================================
# 6. GRAPHIQUE RAINBOW V2
# ============================================================================

print("="*100)
print("📊 GÉNÉRATION DU GRAPHIQUE RAINBOW V2")
print("="*100)
print()

# Filtrer depuis 2018 pour meilleure lisibilité
df_plot = btc_v2[btc_v2['date'] >= '2018-01-01'].copy()

fig, ax = plt.subplots(figsize=(16, 10))

# Prix BTC (ligne noire épaisse)
ax.plot(df_plot['date'], df_plot['close'], color='black', linewidth=2, label='Prix BTC', zorder=10)

# Bandes Rainbow (du bas vers le haut)
colors = [
    '#8B00FF',  # Violet (Fire Sale)
    '#0000FF',  # Blue foncé (Buy!)
    '#4169E1',  # Blue (Accumulate)
    '#00FF00',  # Vert (Still Cheap)
    '#90EE90',  # Vert clair (Is bubble?)
    '#FFFF00',  # Jaune (FOMO)
    '#FFA500',  # Orange (Sell!)
    '#FF0000',  # Rouge (Max Bubble)
]

band_names = [
    'Fire Sale',
    'Buy!',
    'Accumulate',
    'Still Cheap',
    'Is this a bubble?',
    'FOMO intensifies',
    'Sell!',
    'Maximum Bubble'
]

bands = [
    'rainbow_v2_fire_sale',
    'rainbow_v2_buy',
    'rainbow_v2_accumulate',
    'rainbow_v2_still_cheap',
    'rainbow_v2_is_bubble',
    'rainbow_v2_fomo',
    'rainbow_v2_sell',
    'rainbow_v2_max_bubble'
]

# Remplir les bandes
for i in range(len(bands) - 1):
    ax.fill_between(
        df_plot['date'],
        df_plot[bands[i]],
        df_plot[bands[i+1]],
        color=colors[i],
        alpha=0.3,
        label=band_names[i]
    )

# Courbes haute et basse (lignes pointillées)
ax.plot(df_plot['date'], df_plot['rainbow_v2_max_bubble'],
        color='red', linewidth=1.5, linestyle='--', alpha=0.7, label='Courbe HAUTE (highs)')
ax.plot(df_plot['date'], df_plot['rainbow_v2_fire_sale'],
        color='blue', linewidth=1.5, linestyle='--', alpha=0.7, label='Courbe BASSE (lows)')

# Échelle log pour mieux voir les variations
ax.set_yscale('log')

# Formatage axes
ax.set_xlabel('Date', fontsize=12, fontweight='bold')
ax.set_ylabel('Prix BTC (EUR, échelle log)', fontsize=12, fontweight='bold')
ax.set_title('🌈 Bitcoin Rainbow Chart V2 (2018-2025)', fontsize=16, fontweight='bold')

# Grille
ax.grid(True, alpha=0.3, linestyle='--')

# Légende
ax.legend(loc='upper left', fontsize=9, ncol=2)

# Format dates
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
ax.xaxis.set_major_locator(mdates.YearLocator())
plt.xticks(rotation=45, ha='right')

# Limites Y pour meilleure visibilité
ax.set_ylim(bottom=100, top=df_plot['rainbow_v2_max_bubble'].max() * 1.2)

plt.tight_layout()

# Sauvegarder
output_path = 'outputs/rainbow_v2_chart_2018_2025.png'
plt.savefig(output_path, dpi=150, bbox_inches='tight')
print(f"💾 Graphique sauvegardé: {output_path}")
print()

# Aussi sauvegarder les données
df_export = btc_v2[['date', 'close', 'rainbow_position_v2',
                     'rainbow_v2_fire_sale', 'rainbow_v2_buy', 'rainbow_v2_accumulate',
                     'rainbow_v2_still_cheap', 'rainbow_v2_is_bubble', 'rainbow_v2_fomo',
                     'rainbow_v2_sell', 'rainbow_v2_max_bubble']].copy()

df_export.to_csv('outputs/rainbow_v2_data.csv', index=False)
print(f"💾 Données sauvegardées: outputs/rainbow_v2_data.csv")
print()

# ============================================================================
# 7. COMPARAISON AVEC RAINBOW ACTUEL
# ============================================================================

print("="*100)
print("⚖️  COMPARAISON: Rainbow ACTUEL vs V2")
print("="*100)
print()

from src.fngbt.strategy import calculate_rainbow_position

btc_comparison = calculate_rainbow_position(btc)
btc_comparison = calculate_rainbow_v2(btc_comparison, coeffs_high, coeffs_low)

# Comparer pour 2024
df_2024 = btc_comparison[btc_comparison['date'].dt.year == 2024].copy()

print("2024 - Comparaison:")
print("-" * 80)
print(f"Rainbow ACTUEL:")
print(f"   Min: {df_2024['rainbow_position'].min():.3f}")
print(f"   Médiane: {df_2024['rainbow_position'].median():.3f}")
print(f"   Max: {df_2024['rainbow_position'].max():.3f}")
print()
print(f"Rainbow V2 OFFICIEL:")
print(f"   Min: {df_2024['rainbow_position_v2'].min():.3f}")
print(f"   Médiane: {df_2024['rainbow_position_v2'].median():.3f}")
print(f"   Max: {df_2024['rainbow_position_v2'].max():.3f}")
print()

# Différence
diff_median = df_2024['rainbow_position_v2'].median() - df_2024['rainbow_position'].median()
print(f"Différence médiane: {diff_median:+.3f}")
if abs(diff_median) > 0.1:
    print("⚠️  DIFFÉRENCE SIGNIFICATIVE!")
else:
    print("✅ Relativement similaires")
print()

print("="*100)
print("🎯 VALIDATION REQUISE")
print("="*100)
print()
print("📊 Graphique généré: outputs/rainbow_v2_chart_2018_2025.png")
print()
print("ÉTAPES:")
print("1. Ouvre le graphique PNG")
print("2. Compare visuellement avec blockchaincenter.net")
print("3. Vérifie que:")
print("   - Prix BTC actuel (~94k EUR) est dans la bonne bande")
print("   - Les courbes haute/basse matchent approximativement")
print("   - 2024 montre bien 'entre Fire Sale et Buy'")
print()
print("✅ Si ça matche → utiliser Rainbow V2 pour la stratégie")
print("❌ Si différent → ajuster les paramètres de régression")
print()

print("✨ Rainbow V2 généré!")
