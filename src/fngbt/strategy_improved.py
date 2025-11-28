"""
Stratégie AMÉLIORÉE - Logique d'investisseur long terme réaliste

PRINCIPES:
1. ASYMÉTRIE: Agressif à l'achat, patient à la vente
2. JAMAIS À 0%: Toujours garder une base (20% minimum)
3. OR pour acheter: FNG bas OU Rainbow bas → Acheter
4. AND pour vendre: FNG haut ET Rainbow haut → Vendre
5. ZONES PROGRESSIVES: Pas de seuils binaires
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import numpy as np
import pandas as pd


@dataclass
class ImprovedStrategyConfig:
    """Configuration de la stratégie améliorée"""

    # Zones Fear & Greed
    fng_extreme_fear: int = 20      # < 20 = FEAR extrême → max allocation
    fng_fear: int = 35              # < 35 = FEAR → forte allocation
    fng_neutral_low: int = 45       # Zone neutre basse
    fng_neutral_high: int = 65      # Zone neutre haute
    fng_greed: int = 80             # > 80 = GREED → réduire
    fng_extreme_greed: int = 90     # > 90 = GREED extrême → forte réduction

    # Zones Rainbow Chart
    rainbow_extreme_low: float = 0.2    # < 0.2 = prix très bas → max allocation
    rainbow_low: float = 0.35           # < 0.35 = prix bas → forte allocation
    rainbow_mid_low: float = 0.45       # Zone neutre basse
    rainbow_mid_high: float = 0.65      # Zone neutre haute
    rainbow_high: float = 0.75          # > 0.75 = prix haut → réduire
    rainbow_extreme_high: float = 0.85  # > 0.85 = prix très haut → forte réduction

    # Allocation
    min_allocation_pct: int = 20    # Ne JAMAIS descendre en-dessous (base obligatoire)
    max_allocation_pct: int = 100   # Allocation maximale
    neutral_allocation_pct: int = 60  # Allocation en zone neutre

    # Paramètres de combinaison
    buy_logic_or: bool = True       # True = OR (FNG OU Rainbow), False = AND
    sell_logic_and: bool = True     # True = AND (FNG ET Rainbow), False = OR

    # Trading
    min_position_change_pct: float = 10.0
    execute_next_day: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


def calculate_fng_score(fng: np.ndarray, cfg: ImprovedStrategyConfig) -> np.ndarray:
    """
    Calcule le score d'allocation basé sur FNG

    Returns: 0-1 où 1 = allocation maximale
    """
    score = np.zeros_like(fng, dtype=float)

    # FEAR extrême → 1.0 (100% allocation)
    mask_extreme_fear = fng <= cfg.fng_extreme_fear
    score[mask_extreme_fear] = 1.0

    # FEAR → Rampe de extreme_fear à fear
    mask_fear = (fng > cfg.fng_extreme_fear) & (fng <= cfg.fng_fear)
    score[mask_fear] = 0.8 + 0.2 * (cfg.fng_fear - fng[mask_fear]) / (cfg.fng_fear - cfg.fng_extreme_fear)

    # Zone neutre basse → Rampe de fear à neutral_low
    mask_neutral_low = (fng > cfg.fng_fear) & (fng <= cfg.fng_neutral_low)
    score[mask_neutral_low] = 0.6 + 0.2 * (cfg.fng_neutral_low - fng[mask_neutral_low]) / (cfg.fng_neutral_low - cfg.fng_fear)

    # Zone neutre → 0.5 (allocation neutre)
    mask_neutral = (fng > cfg.fng_neutral_low) & (fng <= cfg.fng_neutral_high)
    score[mask_neutral] = 0.5

    # Zone neutre haute → Rampe de neutral_high à greed
    mask_neutral_high = (fng > cfg.fng_neutral_high) & (fng <= cfg.fng_greed)
    score[mask_neutral_high] = 0.3 + 0.2 * (cfg.fng_greed - fng[mask_neutral_high]) / (cfg.fng_greed - cfg.fng_neutral_high)

    # GREED → Rampe de greed à extreme_greed
    mask_greed = (fng > cfg.fng_greed) & (fng <= cfg.fng_extreme_greed)
    score[mask_greed] = 0.1 + 0.2 * (cfg.fng_extreme_greed - fng[mask_greed]) / (cfg.fng_extreme_greed - cfg.fng_greed)

    # GREED extrême → 0.0 (allocation minimale)
    mask_extreme_greed = fng > cfg.fng_extreme_greed
    score[mask_extreme_greed] = 0.0

    return score


def calculate_rainbow_score(rainbow_pos: np.ndarray, cfg: ImprovedStrategyConfig) -> np.ndarray:
    """
    Calcule le score d'allocation basé sur Rainbow position

    Returns: 0-1 où 1 = allocation maximale
    """
    score = np.zeros_like(rainbow_pos, dtype=float)

    # Prix TRÈS bas → 1.0
    mask_extreme_low = rainbow_pos <= cfg.rainbow_extreme_low
    score[mask_extreme_low] = 1.0

    # Prix bas → Rampe
    mask_low = (rainbow_pos > cfg.rainbow_extreme_low) & (rainbow_pos <= cfg.rainbow_low)
    score[mask_low] = 0.8 + 0.2 * (cfg.rainbow_low - rainbow_pos[mask_low]) / (cfg.rainbow_low - cfg.rainbow_extreme_low)

    # Zone neutre basse → Rampe
    mask_mid_low = (rainbow_pos > cfg.rainbow_low) & (rainbow_pos <= cfg.rainbow_mid_low)
    score[mask_mid_low] = 0.6 + 0.2 * (cfg.rainbow_mid_low - rainbow_pos[mask_mid_low]) / (cfg.rainbow_mid_low - cfg.rainbow_low)

    # Zone neutre → 0.5
    mask_mid = (rainbow_pos > cfg.rainbow_mid_low) & (rainbow_pos <= cfg.rainbow_mid_high)
    score[mask_mid] = 0.5

    # Zone neutre haute → Rampe
    mask_mid_high = (rainbow_pos > cfg.rainbow_mid_high) & (rainbow_pos <= cfg.rainbow_high)
    score[mask_mid_high] = 0.3 + 0.2 * (cfg.rainbow_high - rainbow_pos[mask_mid_high]) / (cfg.rainbow_high - cfg.rainbow_mid_high)

    # Prix haut → Rampe
    mask_high = (rainbow_pos > cfg.rainbow_high) & (rainbow_pos <= cfg.rainbow_extreme_high)
    score[mask_high] = 0.1 + 0.2 * (cfg.rainbow_extreme_high - rainbow_pos[mask_high]) / (cfg.rainbow_extreme_high - cfg.rainbow_high)

    # Prix TRÈS haut → 0.0
    mask_extreme_high = rainbow_pos > cfg.rainbow_extreme_high
    score[mask_extreme_high] = 0.0

    return score


def build_improved_signals(df: pd.DataFrame, cfg: ImprovedStrategyConfig) -> pd.DataFrame:
    """
    Construit les signaux avec la logique améliorée

    LOGIQUE ASYMÉTRIQUE:
    - ACHAT: OR (si FNG bas OU Rainbow bas) → Prend le MAX des deux
    - VENTE: AND (seulement si FNG haut ET Rainbow haut) → Prend le MIN des deux
    """
    # Import de la fonction de base pour Rainbow
    from .strategy import calculate_rainbow_position

    # Calcul Rainbow position
    d = calculate_rainbow_position(df)

    # Scores individuels
    fng_score = calculate_fng_score(d["fng"].values, cfg)
    rainbow_score = calculate_rainbow_score(d["rainbow_position"].values, cfg)

    # Combinaison ASYMÉTRIQUE
    if cfg.buy_logic_or:
        # OR pour acheter: si l'un des deux dit "acheter fort", on achète fort
        # On prend le MAX des deux scores
        combined_score = np.maximum(fng_score, rainbow_score)
    else:
        # AND pour acheter: les deux doivent être alignés
        combined_score = np.minimum(fng_score, rainbow_score)

    # Conversion en allocation
    min_alloc = cfg.min_allocation_pct / 100.0
    max_alloc = cfg.max_allocation_pct / 100.0

    # Score 0-1 → min_alloc-max_alloc
    allocation = min_alloc + combined_score * (max_alloc - min_alloc)
    allocation_pct = allocation * 100.0

    # Ajout colonnes de diagnostic
    d["fng_score"] = fng_score
    d["rainbow_score"] = rainbow_score
    d["combined_score"] = combined_score
    d["allocation_pct"] = allocation_pct
    d["pos_raw"] = allocation_pct

    # Filtrage du changement minimum
    min_change = cfg.min_position_change_pct
    pos_filtered = []
    current_pos = cfg.neutral_allocation_pct  # On commence à l'allocation neutre

    for target in d["pos_raw"]:
        if abs(target - current_pos) >= min_change:
            current_pos = target
        pos_filtered.append(current_pos)

    d["pos_target"] = pd.Series(pos_filtered, index=d.index)

    # Exécution J+1
    if cfg.execute_next_day:
        d["pos"] = d["pos_target"].shift(1).fillna(cfg.neutral_allocation_pct)
    else:
        d["pos"] = d["pos_target"]

    # Trades
    d["pos_change"] = d["pos"].diff().fillna(0.0)
    d["trade"] = (d["pos_change"].abs() > 0.01).astype(int)

    return d
