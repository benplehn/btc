#!/usr/bin/env python3
"""Create realistic sample BTC and FNG data for testing"""
import pandas as pd
import numpy as np

# Create dates from 2018-01-01 to 2025-11-29
dates = pd.date_range('2018-01-01', '2025-11-29', freq='D')
n = len(dates)

# Realistic Bitcoin price trajectory (based on actual history)
# Key price points: 2018 start: ~15k, bottom: ~3k (Dec 2018)
# 2019: recovery to ~7k, 2020: halving, bull to ~29k
# 2021: peak ~69k (Nov), crash to ~47k
# 2022: bear to ~16k (Nov)
# 2023: recovery to ~44k
# 2024: halving, bull to ~95k
# 2025: current ~95k

prices = []
for i, date in enumerate(dates):
    year = date.year
    day_of_year = date.dayofyear

    if year == 2018:
        # Crash from 15k to 3.5k
        progress = (day_of_year + (date.month > 6) * 180) / 365
        price = 15000 - 11500 * progress + np.random.randn() * 500
    elif year == 2019:
        # Recovery 3.5k to 7k
        progress = day_of_year / 365
        price = 3500 + 3500 * progress + np.random.randn() * 300
    elif year == 2020:
        # Bull run: 7k to 29k (halving in May)
        progress = day_of_year / 365
        price = 7000 + 22000 * progress ** 2 + np.random.randn() * 800
    elif year == 2021:
        # Peak: 29k to 69k (Nov) then crash to 47k
        progress = day_of_year / 365
        if progress < 0.85:  # Up to Nov
            price = 29000 + 40000 * progress ** 1.5 + np.random.randn() * 1500
        else:  # Crash
            price = 69000 - 22000 * ((progress - 0.85) / 0.15) ** 2 + np.random.randn() * 2000
    elif year == 2022:
        # Bear: 47k to 16k
        progress = day_of_year / 365
        price = 47000 - 31000 * progress + np.random.randn() * 1000
    elif year == 2023:
        # Recovery: 16k to 44k
        progress = day_of_year / 365
        price = 16000 + 28000 * progress ** 1.2 + np.random.randn() * 1200
    elif year == 2024:
        # Bull: 44k to 95k (halving in April)
        progress = day_of_year / 365
        price = 44000 + 51000 * progress ** 1.3 + np.random.randn() * 2000
    else:  # 2025
        # Current: ~95k with high volatility
        progress = day_of_year / 365
        price = 93000 + 4000 * np.sin(progress * 10) + np.random.randn() * 3000

    prices.append(max(3000, price))  # Floor at 3k

btc_df = pd.DataFrame({'date': dates, 'close': prices})

# Create FNG data (inversely correlated with price momentum and height)
fng_values = []
for i in range(n):
    if i < 30:
        fng_values.append(50)  # Default
        continue

    # Calculate 30-day price change
    price_change_pct = (prices[i] - prices[i-30]) / prices[i-30] * 100

    # Calculate distance from all-time high
    ath = max(prices[:i+1])
    drawdown_pct = (prices[i] - ath) / ath * 100

    # FNG formula: higher price momentum = higher FNG (greed)
    # Bigger drawdown = lower FNG (fear)
    fng = 50 + price_change_pct * 0.8 - drawdown_pct * 0.5 + np.random.randn() * 10
    fng = int(np.clip(fng, 5, 95))
    fng_values.append(fng)

fng_df = pd.DataFrame({'date': dates, 'fng': fng_values})

# Save to cache
btc_df.to_csv('outputs/btc_cache.csv', index=False)
fng_df.to_csv('outputs/fng_cache.csv', index=False)

print(f"✅ Created BTC cache: {len(btc_df)} days")
print(f"   Price: ${btc_df['close'].iloc[0]:.0f} → ${btc_df['close'].iloc[-1]:.0f}")
print(f"   Range: ${btc_df['close'].min():.0f} - ${btc_df['close'].max():.0f}")
print(f"   Buy & Hold: {btc_df['close'].iloc[-1] / btc_df['close'].iloc[0]:.1f}x")
print(f"\n✅ Created FNG cache: {len(fng_df)} days")
print(f"   Range: {fng_df['fng'].min()} - {fng_df['fng'].max()}")
print(f"   Mean: {fng_df['fng'].mean():.1f}")
