#!/usr/bin/env python3
"""
🌈 EXPORT Rainbow pour VALIDATION

Export les valeurs Rainbow actuelles pour comparaison avec blockchaincenter.net
"""
import pandas as pd
from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.strategy import calculate_rainbow_position

print("="*80)
print("🌈 EXPORT Rainbow pour VALIDATION")
print("="*80)
print()

# Load data
fng = load_fng_alt()
btc = load_btc_prices()
df = merge_daily(fng, btc)
df = calculate_rainbow_position(df)

# Export derniers jours pour validation
df_recent = df[df['date'] >= '2024-01-01'].copy()

print(f"Données exportées: {len(df_recent)} jours depuis 2024-01-01\n")

# Afficher quelques exemples récents
print("Exemples RÉCENTS (Novembre 2024-2025):")
print("-" * 80)
print("Date       | Prix BTC  | Rainbow Pos | Band")
print("-" * 80)

for idx in df_recent.tail(20).index:
    row = df_recent.loc[idx]
    date_str = row['date'].strftime('%Y-%m-%d')
    price = row['close']
    rainbow = row['rainbow_position']

    # Déterminer la "band" approximative
    if rainbow < 0.125:
        band = "🟣 Fire Sale"
    elif rainbow < 0.25:
        band = "🔵 Buy!"
    elif rainbow < 0.375:
        band = "🔵 Accumulate"
    elif rainbow < 0.5:
        band = "🟢 Still Cheap"
    elif rainbow < 0.625:
        band = "🟡 Is this a bubble?"
    elif rainbow < 0.75:
        band = "🟡 FOMO"
    elif rainbow < 0.875:
        band = "🟠 Sell!"
    else:
        band = "🔴 Max Bubble"

    print(f"{date_str} | {price:9,.0f} | {rainbow:11.3f} | {band}")

print()

# Statistiques 2024
df_2024 = df_recent[df_recent['date'].dt.year == 2024].copy()

print("STATISTIQUES 2024:")
print("-" * 80)
print(f"Rainbow min: {df_2024['rainbow_position'].min():.3f}")
print(f"Rainbow median: {df_2024['rainbow_position'].median():.3f}")
print(f"Rainbow max: {df_2024['rainbow_position'].max():.3f}")
print()

print(f"Prix BTC min: {df_2024['close'].min():,.0f} EUR")
print(f"Prix BTC median: {df_2024['close'].median():,.0f} EUR")
print(f"Prix BTC max: {df_2024['close'].max():,.0f} EUR")
print()

# Distribution par bande
print("Distribution par bande (2024):")
bands = []
for idx in df_2024.index:
    rainbow = df_2024.loc[idx, 'rainbow_position']
    if rainbow < 0.125:
        bands.append("Fire Sale")
    elif rainbow < 0.25:
        bands.append("Buy!")
    elif rainbow < 0.375:
        bands.append("Accumulate")
    elif rainbow < 0.5:
        bands.append("Still Cheap")
    elif rainbow < 0.625:
        bands.append("Is bubble?")
    elif rainbow < 0.75:
        bands.append("FOMO")
    elif rainbow < 0.875:
        bands.append("Sell!")
    else:
        bands.append("Max Bubble")

df_2024['band'] = bands
band_counts = df_2024['band'].value_counts()

for band, count in band_counts.items():
    pct = count / len(df_2024) * 100
    print(f"  {band:15s}: {count:3d} jours ({pct:5.1f}%)")
print()

# Export CSV complet
df_export = df[['date', 'close', 'rainbow_position', 'rainbow_min', 'rainbow_mid', 'rainbow_max']].copy()
df_export.to_csv('outputs/rainbow_values_for_validation.csv', index=False)

print("💾 Export complet: outputs/rainbow_values_for_validation.csv")
print()

print("="*80)
print("🎯 VALIDATION REQUISE")
print("="*80)
print()
print("Étapes:")
print("1. Va sur https://www.blockchaincenter.net/en/bitcoin-rainbow-chart/")
print("2. Regarde la position actuelle du BTC (fin novembre 2024)")
print("3. Compare avec les valeurs ci-dessus")
print()
print("Questions:")
print("  • Le Rainbow position actuel (~0.45-0.50) correspond-il?")
print("  • Est-ce que BTC est dans 'Still Cheap' ou 'Is this a bubble'?")
print("  • 2024 devrait avoir combien de jours en 'Still Cheap' vs autres?")
print()
print("✅ Si les valeurs matchent → mon Rainbow est correct")
print("❌ Si différent → je dois corriger la formule")
print()
