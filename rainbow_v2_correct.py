#!/usr/bin/env python3
"""
🌈 RAINBOW CHART V2 - CORRECT

Contrainte CRITIQUE:
- Le prix BTC doit TOUJOURS être entre courbe haute et basse
- Courbe haute = enveloppe qui passe AU-DESSUS de tous les highs
- Courbe basse = enveloppe qui passe EN-DESSOUS de tous les lows

Méthode:
1. Trouver le max absolu et min absolu sur tout le dataset
2. Faire une régression log-log
3. Ajuster les coefficients pour que:
   - Courbe haute >= max(prix) pour toutes les dates
   - Courbe basse <= min(prix) pour toutes les dates
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from src.fngbt.data import load_btc_prices
from scipy.optimize import differential_evolution
import warnings
warnings.filterwarnings('ignore')

print("="*100)
print("🌈 RAINBOW CHART V2 - ENVELOPPES HAUTE/BASSE")
print("="*100)
print()

# ============================================================================
# 1. CHARGER LES DONNÉES
# ============================================================================

print("Chargement données BTC...")
btc = load_btc_prices()
print(f"✅ {len(btc)} jours")
print()

# Genesis
genesis = pd.Timestamp("2009-01-03")
btc['days_since_genesis'] = (btc['date'] - genesis).dt.days.clip(lower=1)

# Log scale
btc['log_days'] = np.log10(btc['days_since_genesis'])
btc['log_price'] = np.log10(btc['close'].clip(lower=1e-9))

# ============================================================================
# 2. RÉGRESSION AVEC CONTRAINTES: Enveloppe supérieure
# ============================================================================

print("="*100)
print("📈 RÉGRESSION ENVELOPPE HAUTE (tous les prix SOUS la courbe)")
print("="*100)
print()

def fit_upper_envelope(x, y, deg=2):
    """
    Trouve la courbe polynomiale qui passe AU-DESSUS de tous les points

    Méthode: optimisation avec contrainte min(curve - y) >= 0
    """
    # Initial guess: polyfit standard
    coeffs_init = np.polyfit(x, y, deg=deg)

    # Fonction objectif: minimiser la distance moyenne tout en restant au-dessus
    def objective(coeffs):
        if deg == 2:
            y_pred = coeffs[0] * x**2 + coeffs[1] * x + coeffs[2]
        elif deg == 1:
            y_pred = coeffs[0] * x + coeffs[1]
        else:
            y_pred = np.polyval(coeffs, x)

        # On veut minimiser la distance mais rester au-dessus
        # Pénalité énorme si on passe en-dessous
        violations = np.maximum(0, y - y_pred)  # Points où curve < y

        if violations.max() > 0:
            # Si on viole, pénalité massive
            return 1e10 + violations.sum() * 1e6
        else:
            # Sinon, minimiser la distance au-dessus
            distance = (y_pred - y).sum()
            return distance

    # Optimiser
    if deg == 2:
        bounds = [(-100, 100), (-200, 200), (-200, 200)]
    else:
        bounds = [(-50, 50), (-100, 100)]

    result = differential_evolution(objective, bounds, maxiter=1000, seed=42)

    return result.x

print("Calcul enveloppe haute (deg=2)...")
coeffs_high = fit_upper_envelope(btc['log_days'].values, btc['log_price'].values, deg=2)
print(f"Coefficients HAUTE: a={coeffs_high[0]:.6f}, b={coeffs_high[1]:.6f}, c={coeffs_high[2]:.6f}")

# Vérifier qu'on est bien au-dessus partout
log_price_high = coeffs_high[0] * btc['log_days']**2 + coeffs_high[1] * btc['log_days'] + coeffs_high[2]
violations_high = (btc['log_price'] - log_price_high).clip(lower=0).sum()

if violations_high < 0.001:
    print("✅ Courbe haute valide: tous les prix sont EN-DESSOUS")
else:
    print(f"⚠️  Violations: {violations_high:.3f}")
print()

# ============================================================================
# 3. RÉGRESSION AVEC CONTRAINTES: Enveloppe inférieure
# ============================================================================

print("="*100)
print("📉 RÉGRESSION ENVELOPPE BASSE (tous les prix AU-DESSUS de la courbe)")
print("="*100)
print()

def fit_lower_envelope(x, y, deg=2):
    """
    Trouve la courbe polynomiale qui passe EN-DESSOUS de tous les points
    """
    coeffs_init = np.polyfit(x, y, deg=deg)

    def objective(coeffs):
        if deg == 2:
            y_pred = coeffs[0] * x**2 + coeffs[1] * x + coeffs[2]
        elif deg == 1:
            y_pred = coeffs[0] * x + coeffs[1]
        else:
            y_pred = np.polyval(coeffs, x)

        # On veut maximiser y_pred (rester en-dessous de y)
        violations = np.maximum(0, y_pred - y)  # Points où curve > y

        if violations.max() > 0:
            return 1e10 + violations.sum() * 1e6
        else:
            # Minimiser la distance en-dessous (on veut être le plus haut possible sous les points)
            distance = (y - y_pred).sum()
            return distance

    if deg == 2:
        bounds = [(-100, 100), (-200, 200), (-200, 200)]
    else:
        bounds = [(-50, 50), (-100, 100)]

    result = differential_evolution(objective, bounds, maxiter=1000, seed=42)
    return result.x

print("Calcul enveloppe basse (deg=2)...")
coeffs_low = fit_lower_envelope(btc['log_days'].values, btc['log_price'].values, deg=2)
print(f"Coefficients BASSE: a={coeffs_low[0]:.6f}, b={coeffs_low[1]:.6f}, c={coeffs_low[2]:.6f}")

# Vérifier
log_price_low = coeffs_low[0] * btc['log_days']**2 + coeffs_low[1] * btc['log_days'] + coeffs_low[2]
violations_low = (log_price_low - btc['log_price']).clip(lower=0).sum()

if violations_low < 0.001:
    print("✅ Courbe basse valide: tous les prix sont AU-DESSUS")
else:
    print(f"⚠️  Violations: {violations_low:.3f}")
print()

# ============================================================================
# 4. CALCULER LES BANDES RAINBOW
# ============================================================================

print("="*100)
print("🌈 CALCUL DES BANDES")
print("="*100)
print()

# Courbes haute et basse en prix réel
price_high = 10 ** log_price_high
price_low = 10 ** log_price_low

# 8 bandes par interpolation linéaire
btc['rainbow_v2_fire_sale'] = price_low  # 0/7
btc['rainbow_v2_buy'] = price_low + 1/7 * (price_high - price_low)  # 1/7
btc['rainbow_v2_accumulate'] = price_low + 2/7 * (price_high - price_low)  # 2/7
btc['rainbow_v2_still_cheap'] = price_low + 3/7 * (price_high - price_low)  # 3/7
btc['rainbow_v2_is_bubble'] = price_low + 4/7 * (price_high - price_low)  # 4/7
btc['rainbow_v2_fomo'] = price_low + 5/7 * (price_high - price_low)  # 5/7
btc['rainbow_v2_sell'] = price_low + 6/7 * (price_high - price_low)  # 6/7
btc['rainbow_v2_max_bubble'] = price_high  # 7/7

# Position normalisée (0-1) en échelle log
rainbow_position_v2 = (btc['log_price'] - log_price_low) / (log_price_high - log_price_low)
rainbow_position_v2 = rainbow_position_v2.clip(0.0, 1.0)
btc['rainbow_position_v2'] = rainbow_position_v2

print("✅ Bandes calculées")
print()

# Vérification: prix doit être entre min et max
assert (btc['close'] >= btc['rainbow_v2_fire_sale']).all(), "❌ Prix sous fire sale!"
assert (btc['close'] <= btc['rainbow_v2_max_bubble']).all(), "❌ Prix au-dessus max bubble!"
print("✅ VALIDATION: Prix toujours entre Fire Sale et Max Bubble")
print()

# ============================================================================
# 5. STATISTIQUES
# ============================================================================

print("="*100)
print("📊 STATISTIQUES PAR ANNÉE")
print("="*100)
print()

print("Année | Min   | P25   | Médiane | P75   | Max   | % Fire Sale | % Buy")
print("-" * 80)

for year in range(2018, 2026):
    df_year = btc[btc['date'].dt.year == year]
    if len(df_year) > 0:
        r = df_year['rainbow_position_v2']
        pct_fire = (r < 1/7).sum() / len(df_year) * 100
        pct_buy = ((r >= 1/7) & (r < 2/7)).sum() / len(df_year) * 100

        print(f"{year}  | {r.min():.3f} | {r.quantile(0.25):.3f} | "
              f"{r.median():.3f} | {r.quantile(0.75):.3f} | {r.max():.3f} | "
              f"{pct_fire:6.1f}% | {pct_buy:5.1f}%")

print()

# Nov 2024-2025
recent = btc[btc['date'] >= '2024-11-01']
print(f"Position actuelle (Nov 2024-2025):")
print(f"   Rainbow V2: {recent['rainbow_position_v2'].median():.3f}")

if recent['rainbow_position_v2'].median() < 1/7:
    band = "🟣 FIRE SALE"
elif recent['rainbow_position_v2'].median() < 2/7:
    band = "🔵 BUY!"
elif recent['rainbow_position_v2'].median() < 3/7:
    band = "🔵 ACCUMULATE"
elif recent['rainbow_position_v2'].median() < 4/7:
    band = "🟢 STILL CHEAP"
else:
    band = "Plus haut"

print(f"   Bande: {band}")
print()

# ============================================================================
# 6. GRAPHIQUE
# ============================================================================

print("="*100)
print("📊 GÉNÉRATION GRAPHIQUE")
print("="*100)
print()

df_plot = btc[btc['date'] >= '2018-01-01'].copy()

fig, ax = plt.subplots(figsize=(16, 10))

# Bandes rainbow
colors = ['#8B00FF', '#0000FF', '#4169E1', '#00FF00', '#90EE90', '#FFFF00', '#FFA500', '#FF0000']
band_names = ['Fire Sale', 'Buy!', 'Accumulate', 'Still Cheap', 'Is bubble?', 'FOMO', 'Sell!', 'Max Bubble']
bands = ['rainbow_v2_fire_sale', 'rainbow_v2_buy', 'rainbow_v2_accumulate', 'rainbow_v2_still_cheap',
         'rainbow_v2_is_bubble', 'rainbow_v2_fomo', 'rainbow_v2_sell', 'rainbow_v2_max_bubble']

for i in range(len(bands) - 1):
    ax.fill_between(df_plot['date'], df_plot[bands[i]], df_plot[bands[i+1]],
                    color=colors[i], alpha=0.3, label=band_names[i])

# Courbes enveloppes
ax.plot(df_plot['date'], df_plot['rainbow_v2_max_bubble'],
        color='red', linewidth=2, linestyle='--', alpha=0.8, label='Enveloppe HAUTE', zorder=5)
ax.plot(df_plot['date'], df_plot['rainbow_v2_fire_sale'],
        color='blue', linewidth=2, linestyle='--', alpha=0.8, label='Enveloppe BASSE', zorder=5)

# Prix BTC
ax.plot(df_plot['date'], df_plot['close'], color='black', linewidth=2.5, label='Prix BTC', zorder=10)

ax.set_yscale('log')
ax.set_xlabel('Date', fontsize=12, fontweight='bold')
ax.set_ylabel('Prix BTC (EUR, échelle log)', fontsize=12, fontweight='bold')
ax.set_title('🌈 Bitcoin Rainbow Chart V2 - Enveloppes Correctes (2018-2025)', fontsize=16, fontweight='bold')
ax.grid(True, alpha=0.3, linestyle='--')
ax.legend(loc='upper left', fontsize=9, ncol=2)
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
ax.xaxis.set_major_locator(mdates.YearLocator())
plt.xticks(rotation=45, ha='right')

plt.tight_layout()

output_path = 'outputs/rainbow_v2_correct_enveloppes.png'
plt.savefig(output_path, dpi=150, bbox_inches='tight')
print(f"💾 Graphique: {output_path}")

# Export CSV
df_export = btc[['date', 'close', 'rainbow_position_v2'] + bands].copy()
df_export.to_csv('outputs/rainbow_v2_correct_data.csv', index=False)
print(f"💾 Données: outputs/rainbow_v2_correct_data.csv")
print()

print("="*100)
print("✅ RAINBOW V2 CORRECT - Prix TOUJOURS entre enveloppes!")
print("="*100)
