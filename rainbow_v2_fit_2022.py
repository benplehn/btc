#!/usr/bin/env python3
"""
🌈 RAINBOW V2 - FIT 2022 (comme l'officiel)

Rainbow V2 a été créé en Nov 2022 avec données JUSQU'EN 2022.
On doit fitter les enveloppes sur 2009-2022, puis extrapoler pour 2023-2025.
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
print("🌈 RAINBOW V2 - FIT 2022 (Officiel)")
print("="*100)
print()

# Load data
btc = load_btc_prices()
print(f"✅ {len(btc)} jours total")

# Split: fit sur 2009-2022, extrapolation sur 2023-2025
btc_fit = btc[btc['date'] <= '2022-12-31'].copy()
print(f"✅ {len(btc_fit)} jours pour FIT (jusqu'à 2022)")
print()

# Genesis
genesis = pd.Timestamp("2009-01-03")
btc['days_since_genesis'] = (btc['date'] - genesis).dt.days.clip(lower=1)
btc_fit['days_since_genesis'] = (btc_fit['date'] - genesis).dt.days.clip(lower=1)

btc['log_days'] = np.log10(btc['days_since_genesis'])
btc_fit['log_days'] = np.log10(btc_fit['days_since_genesis'])
btc['log_price'] = np.log10(btc['close'].clip(lower=1e-9))
btc_fit['log_price'] = np.log10(btc_fit['close'].clip(lower=1e-9))

# ============================================================================
# FIT ENVELOPPES SUR 2009-2022 SEULEMENT
# ============================================================================

print("="*100)
print("📈 FIT ENVELOPPES (2009-2022)")
print("="*100)
print()

def fit_upper_envelope(x, y, deg=2):
    """Enveloppe supérieure: tous les points EN-DESSOUS"""
    def objective(coeffs):
        if deg == 2:
            y_pred = coeffs[0] * x**2 + coeffs[1] * x + coeffs[2]
        else:
            y_pred = coeffs[0] * x + coeffs[1]

        violations = np.maximum(0, y - y_pred)
        if violations.max() > 0:
            return 1e10 + violations.sum() * 1e6
        else:
            return (y_pred - y).sum()

    bounds = [(-100, 100), (-200, 200), (-200, 200)] if deg == 2 else [(-50, 50), (-100, 100)]
    result = differential_evolution(objective, bounds, maxiter=1000, seed=42, workers=1)
    return result.x

def fit_lower_envelope(x, y, deg=2):
    """Enveloppe inférieure: tous les points AU-DESSUS"""
    def objective(coeffs):
        if deg == 2:
            y_pred = coeffs[0] * x**2 + coeffs[1] * x + coeffs[2]
        else:
            y_pred = coeffs[0] * x + coeffs[1]

        violations = np.maximum(0, y_pred - y)
        if violations.max() > 0:
            return 1e10 + violations.sum() * 1e6
        else:
            return (y - y_pred).sum()

    bounds = [(-100, 100), (-200, 200), (-200, 200)] if deg == 2 else [(-50, 50), (-100, 100)]
    result = differential_evolution(objective, bounds, maxiter=1000, seed=42, workers=1)
    return result.x

print("Fit HAUTE sur 2009-2022...")
coeffs_high = fit_upper_envelope(btc_fit['log_days'].values, btc_fit['log_price'].values, deg=2)
print(f"Coeffs HAUTE: a={coeffs_high[0]:.6f}, b={coeffs_high[1]:.6f}, c={coeffs_high[2]:.6f}")

# Vérif
log_price_high_fit = coeffs_high[0] * btc_fit['log_days']**2 + coeffs_high[1] * btc_fit['log_days'] + coeffs_high[2]
violations = (btc_fit['log_price'] - log_price_high_fit).clip(lower=0).sum()
print(f"✅ Violations: {violations:.6f}")
print()

print("Fit BASSE sur 2009-2022...")
coeffs_low = fit_lower_envelope(btc_fit['log_days'].values, btc_fit['log_price'].values, deg=2)
print(f"Coeffs BASSE: a={coeffs_low[0]:.6f}, b={coeffs_low[1]:.6f}, c={coeffs_low[2]:.6f}")

# Vérif
log_price_low_fit = coeffs_low[0] * btc_fit['log_days']**2 + coeffs_low[1] * btc_fit['log_days'] + coeffs_low[2]
violations = (log_price_low_fit - btc_fit['log_price']).clip(lower=0).sum()
print(f"✅ Violations: {violations:.6f}")
print()

# ============================================================================
# APPLIQUER SUR TOUTES LES DONNÉES (2009-2025)
# ============================================================================

print("="*100)
print("🌈 APPLICATION SUR 2009-2025 (extrapolation)")
print("="*100)
print()

# Calculer les enveloppes pour TOUTES les dates (y compris 2023-2025)
log_price_high = coeffs_high[0] * btc['log_days']**2 + coeffs_high[1] * btc['log_days'] + coeffs_high[2]
log_price_low = coeffs_low[0] * btc['log_days']**2 + coeffs_low[1] * btc['log_days'] + coeffs_low[2]

price_high = 10 ** log_price_high
price_low = 10 ** log_price_low

# 8 bandes
btc['rainbow_v2_fire_sale'] = price_low
btc['rainbow_v2_buy'] = price_low + 1/7 * (price_high - price_low)
btc['rainbow_v2_accumulate'] = price_low + 2/7 * (price_high - price_low)
btc['rainbow_v2_still_cheap'] = price_low + 3/7 * (price_high - price_low)
btc['rainbow_v2_is_bubble'] = price_low + 4/7 * (price_high - price_low)
btc['rainbow_v2_fomo'] = price_low + 5/7 * (price_high - price_low)
btc['rainbow_v2_sell'] = price_low + 6/7 * (price_high - price_low)
btc['rainbow_v2_max_bubble'] = price_high

# Position
rainbow_position_v2 = (btc['log_price'] - log_price_low) / (log_price_high - log_price_low)
rainbow_position_v2 = rainbow_position_v2.clip(0.0, 1.0)
btc['rainbow_position_v2'] = rainbow_position_v2

# Vérification 2009-2022 (fit data)
btc_check = btc[btc['date'] <= '2022-12-31']
assert (btc_check['close'] >= btc_check['rainbow_v2_fire_sale']).all(), "Prix sous fire sale!"
assert (btc_check['close'] <= btc_check['rainbow_v2_max_bubble']).all(), "Prix au-dessus max bubble!"
print("✅ 2009-2022: Prix toujours entre enveloppes")

# Note pour 2023-2025
btc_future = btc[btc['date'] > '2022-12-31']
below_fire = (btc_future['close'] < btc_future['rainbow_v2_fire_sale']).sum()
above_max = (btc_future['close'] > btc_future['rainbow_v2_max_bubble']).sum()

if below_fire > 0 or above_max > 0:
    print(f"⚠️  2023-2025: {below_fire} jours sous fire sale, {above_max} jours au-dessus max bubble")
    print("   (Normal: extrapolation au-delà des données de fit)")
else:
    print("✅ 2023-2025: Prix encore entre enveloppes (chance!)")
print()

# ============================================================================
# STATISTIQUES
# ============================================================================

print("="*100)
print("📊 STATISTIQUES")
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
print(f"Nov 2024-2025:")
print(f"   Rainbow V2 médiane: {recent['rainbow_position_v2'].median():.3f}")
print(f"   Prix médian: {recent['close'].median():,.0f} EUR")
print()

for idx in recent.tail(5).index:
    row = btc.loc[idx]
    print(f"{row['date'].strftime('%Y-%m-%d')}: Prix {row['close']:>8,.0f} EUR, Rainbow {row['rainbow_position_v2']:.3f}")
    print(f"  Fire Sale: {row['rainbow_v2_fire_sale']:>8,.0f}, Buy: {row['rainbow_v2_buy']:>8,.0f}, "
          f"Accumulate: {row['rainbow_v2_accumulate']:>8,.0f}, Still Cheap: {row['rainbow_v2_still_cheap']:>8,.0f}")

print()

if recent['rainbow_position_v2'].median() < 1/7:
    band = "🟣 FIRE SALE"
elif recent['rainbow_position_v2'].median() < 2/7:
    band = "🔵 BUY!"
elif recent['rainbow_position_v2'].median() < 3/7:
    band = "🔵 ACCUMULATE"
elif recent['rainbow_position_v2'].median() < 4/7:
    band = "🟢 STILL CHEAP"
else:
    band = "🟡 Plus haut (Is Bubble / FOMO / Sell)"

print(f"Bande médiane: {band}")
print()

# ============================================================================
# GRAPHIQUE
# ============================================================================

print("="*100)
print("📊 GRAPHIQUE")
print("="*100)
print()

df_plot = btc[btc['date'] >= '2018-01-01'].copy()

fig, ax = plt.subplots(figsize=(16, 10))

# Bandes
colors = ['#8B00FF', '#0000FF', '#4169E1', '#00FF00', '#90EE90', '#FFFF00', '#FFA500', '#FF0000']
band_names = ['Fire Sale', 'Buy!', 'Accumulate', 'Still Cheap', 'Is bubble?', 'FOMO', 'Sell!', 'Max Bubble']
bands = ['rainbow_v2_fire_sale', 'rainbow_v2_buy', 'rainbow_v2_accumulate', 'rainbow_v2_still_cheap',
         'rainbow_v2_is_bubble', 'rainbow_v2_fomo', 'rainbow_v2_sell', 'rainbow_v2_max_bubble']

for i in range(len(bands) - 1):
    ax.fill_between(df_plot['date'], df_plot[bands[i]], df_plot[bands[i+1]],
                    color=colors[i], alpha=0.3, label=band_names[i])

# Enveloppes
ax.plot(df_plot['date'], df_plot['rainbow_v2_max_bubble'],
        color='red', linewidth=2, linestyle='--', alpha=0.8, label='Enveloppe HAUTE (fit 2022)', zorder=5)
ax.plot(df_plot['date'], df_plot['rainbow_v2_fire_sale'],
        color='blue', linewidth=2, linestyle='--', alpha=0.8, label='Enveloppe BASSE (fit 2022)', zorder=5)

# Prix BTC
ax.plot(df_plot['date'], df_plot['close'], color='black', linewidth=2.5, label='Prix BTC', zorder=10)

# Ligne verticale 2023 (début extrapolation)
ax.axvline(pd.Timestamp('2023-01-01'), color='gray', linestyle=':', linewidth=2, alpha=0.7, label='Début extrapolation')

ax.set_yscale('log')
ax.set_xlabel('Date', fontsize=12, fontweight='bold')
ax.set_ylabel('Prix BTC (EUR, échelle log)', fontsize=12, fontweight='bold')
ax.set_title('🌈 Bitcoin Rainbow Chart V2 - Fit 2022 + Extrapolation 2023-2025', fontsize=16, fontweight='bold')
ax.grid(True, alpha=0.3, linestyle='--')
ax.legend(loc='upper left', fontsize=9, ncol=2)
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
ax.xaxis.set_major_locator(mdates.YearLocator())
plt.xticks(rotation=45, ha='right')

plt.tight_layout()

output_path = 'outputs/rainbow_v2_fit2022.png'
plt.savefig(output_path, dpi=150, bbox_inches='tight')
print(f"💾 Graphique: {output_path}")

# CSV
df_export = btc[['date', 'close', 'rainbow_position_v2'] + bands].copy()
df_export.to_csv('outputs/rainbow_v2_fit2022_data.csv', index=False)
print(f"💾 Données: outputs/rainbow_v2_fit2022_data.csv")
print()

print("✨ Rainbow V2 (fit 2022) généré!")
