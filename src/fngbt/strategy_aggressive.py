"""
Stratégie ULTRA AGRESSIVE - Pour battre massivement le B&H

LOGIQUE D'INVESTISSEUR AGRESSIF:
1. ALL-IN pendant les crashs (accumulation massive)
2. HOLD pendant le bull run (ne jamais vendre trop tôt)
3. SORTIE TOTALE en euphorie extrême (top du cycle)

Cette stratégie vise 5-10x vs B&H en timing les cycles.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import numpy as np
import pandas as pd


@dataclass
class AggressiveStrategyConfig:
    """Configuration stratégie agressive"""

    # Zones d'accumulation MASSIVE (ALL-IN)
    fng_extreme_fear: int = 25          # < 25 → 100% ALL-IN
    drawdown_buy_threshold: float = -20.0  # DD < -20% → 100% ALL-IN

    # Zones HOLD (garder 100%)
    fng_hold_low: int = 30              # Entre 25-70 → HOLD 100%
    fng_hold_high: int = 70

    # Zones de SORTIE (réduction agressive)
    fng_reduce_start: int = 75          # > 75 → Commencer à réduire
    fng_euphoria: int = 85              # > 85 → Sortie massive
    near_ath_threshold: float = 0.95    # Prix > 95% ATH = proche sommet

    # Allocation par zone
    all_in_pct: int = 100               # ALL-IN en accumulation
    hold_pct: int = 100                 # HOLD pendant bull
    reduce_pct: int = 50                # Première réduction
    exit_pct: int = 0                   # Sortie totale en euphorie

    # Logique d'accumulation
    accumulation_or_logic: bool = True  # OR: DD OU FNG suffit

    # Trading
    min_position_change_pct: float = 25.0  # Changements + agressifs
    execute_next_day: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


def calculate_market_phase(df: pd.DataFrame, cfg: AggressiveStrategyConfig) -> np.ndarray:
    """
    Détermine la phase de marché:
    - ACCUMULATION: Acheter massivement
    - HOLD: Garder 100%
    - REDUCE: Réduire progressivement
    - EXIT: Sortir

    Returns: Array de phases
    """
    # Calcul du drawdown
    cummax = df['close'].expanding().max()
    drawdown = (df['close'] / cummax - 1) * 100

    # Calcul proche ATH
    near_ath = df['close'] > cummax * cfg.near_ath_threshold

    fng = df['fng'].values
    phases = np.array(['HOLD'] * len(df), dtype=object)

    # Phase ACCUMULATION (priorité la plus haute)
    if cfg.accumulation_or_logic:
        # OR: Si FNG bas OU DD important
        accumulation_mask = (fng < cfg.fng_extreme_fear) | (drawdown < cfg.drawdown_buy_threshold)
    else:
        # AND: Les deux doivent être là
        accumulation_mask = (fng < cfg.fng_extreme_fear) & (drawdown < cfg.drawdown_buy_threshold)

    phases[accumulation_mask] = 'ACCUMULATION'

    # Phase EXIT (euphorie)
    exit_mask = (fng > cfg.fng_euphoria) & near_ath.values
    phases[exit_mask] = 'EXIT'

    # Phase REDUCE (commence à vendre)
    reduce_mask = (fng > cfg.fng_reduce_start) & (fng <= cfg.fng_euphoria) & near_ath.values
    phases[reduce_mask] = 'REDUCE'

    # Phase HOLD (par défaut)
    hold_mask = (fng >= cfg.fng_hold_low) & (fng <= cfg.fng_hold_high)
    phases[hold_mask & (phases == 'HOLD')] = 'HOLD'

    return phases


def build_aggressive_signals(df: pd.DataFrame, cfg: AggressiveStrategyConfig) -> pd.DataFrame:
    """
    Construit les signaux avec logique ultra agressive

    ALLOCATION PAR PHASE:
    - ACCUMULATION: 100% (ALL-IN)
    - HOLD: 100% (garder)
    - REDUCE: 50% (première réduction)
    - EXIT: 0% (sortie totale)
    """
    # Import pour Rainbow
    from .strategy import calculate_rainbow_position

    d = calculate_rainbow_position(df)

    # Déterminer les phases de marché
    phases = calculate_market_phase(d, cfg)
    d['market_phase'] = phases

    # Allocation basée sur la phase
    allocation = np.zeros(len(d))

    for i, phase in enumerate(phases):
        if phase == 'ACCUMULATION':
            allocation[i] = cfg.all_in_pct
        elif phase == 'HOLD':
            allocation[i] = cfg.hold_pct
        elif phase == 'REDUCE':
            allocation[i] = cfg.reduce_pct
        elif phase == 'EXIT':
            allocation[i] = cfg.exit_pct

    d['allocation_pct'] = allocation
    d['pos_raw'] = allocation

    # Filtrage du changement minimum (plus agressif)
    min_change = cfg.min_position_change_pct
    pos_filtered = []
    current_pos = cfg.hold_pct  # On commence à HOLD

    for target in d['pos_raw']:
        if abs(target - current_pos) >= min_change:
            current_pos = target
        pos_filtered.append(current_pos)

    d['pos_target'] = pd.Series(pos_filtered, index=d.index)

    # Exécution J+1
    if cfg.execute_next_day:
        d['pos'] = d['pos_target'].shift(1).fillna(cfg.hold_pct)
    else:
        d['pos'] = d['pos_target']

    # Trades
    d['pos_change'] = d['pos'].diff().fillna(0.0)
    d['trade'] = (d['pos_change'].abs() > 0.01).astype(int)

    return d


def build_cycle_strategy(df: pd.DataFrame) -> pd.DataFrame:
    """
    Stratégie basée UNIQUEMENT sur les cycles Bitcoin (4 ans)

    Logique:
    - Année 1 post-halving: 100% (accumulation)
    - Année 2: 100% (bull run)
    - Année 3: 50% (top + correction)
    - Année 4: 0-50% (bear market)
    """
    from .strategy import calculate_rainbow_position

    d = calculate_rainbow_position(df)

    # Dates de halving
    halvings = [
        pd.Timestamp('2012-11-28'),
        pd.Timestamp('2016-07-09'),
        pd.Timestamp('2020-05-11'),
        pd.Timestamp('2024-04-20'),
    ]

    allocation = np.ones(len(d)) * 50.0  # Default 50%

    for i, date in enumerate(d['date']):
        # Trouver le dernier halving
        last_halving = None
        for h in reversed(halvings):
            if date >= h:
                last_halving = h
                break

        if last_halving is None:
            continue

        # Jours depuis le dernier halving
        days_since_halving = (date - last_halving).days

        # Allocation basée sur le cycle
        if days_since_halving < 365:  # Année 1: Accumulation
            allocation[i] = 100.0
        elif days_since_halving < 730:  # Année 2: Bull run
            allocation[i] = 100.0
        elif days_since_halving < 1095:  # Année 3: Top
            allocation[i] = 50.0
        else:  # Année 4: Bear
            # Diminuer progressivement
            allocation[i] = max(0.0, 100.0 - (days_since_halving - 1095) / 3.65)

    d['pos'] = allocation
    d['pos_target'] = allocation
    d['pos_raw'] = allocation
    d['trade'] = (d['pos'].diff().abs() > 1).astype(int)

    return d
