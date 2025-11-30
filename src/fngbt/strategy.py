"""
Stratégie d'investissement Bitcoin basée sur Fear & Greed Index et Rainbow Chart

LOGIQUE INVESTISSEUR LONG TERME:
- ACHETER: FNG bas (FEAR) + Prix proche ruban BAS → Allocation élevée
- VENDRE: FNG haut (GREED) + Prix proche ruban HAUT → Allocation basse
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import numpy as np
import pandas as pd


@dataclass
class StrategyConfig:
    """Configuration de la stratégie"""
    # Seuils Fear & Greed (0-100)
    fng_buy_threshold: int = 25     # En-dessous = FEAR → zone d'achat
    fng_sell_threshold: int = 75    # Au-dessus = GREED → zone de vente

    # Seuils Rainbow Chart (0-1, position dans les bandes)
    rainbow_buy_threshold: float = 0.3   # En-dessous = prix bas → zone d'achat
    rainbow_sell_threshold: float = 0.7  # Au-dessus = prix haut → zone de vente

    # Allocation
    max_allocation_pct: int = 100   # Allocation maximale en %
    min_allocation_pct: int = 0     # Allocation minimale en %
    min_position_change_pct: float = 5.0  # Changement minimum pour trader (évite micro-ajustements)

    # Exécution
    execute_next_day: bool = True   # Signal J+1 pour éviter look-ahead bias

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RainbowOnlyConfig:
    """Configuration d'une stratégie uniquement basée sur le Rainbow Chart."""

    rainbow_buy_threshold: float = 0.25
    rainbow_sell_threshold: float = 0.75
    allocation_power: float = 1.0  # >1 = agressif sur les extrêmes

    max_allocation_pct: int = 100
    min_allocation_pct: int = 0
    min_position_change_pct: float = 5.0
    execute_next_day: bool = True

    band_count: int = 8  # Utilisé pour les métriques/diagnostics

    def to_dict(self) -> dict:
        return asdict(self)


def calculate_rainbow_position(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcule la position du prix dans le Rainbow Chart

    Rainbow Chart = régression log-log du prix BTC depuis genesis
    Position 0 = ruban le plus bas, Position 1 = ruban le plus haut
    """
    d = df.copy()

    # Genesis Bitcoin: 3 janvier 2009
    genesis = pd.Timestamp("2009-01-03")

    # Jours depuis genesis
    days_since_genesis = (d["date"] - genesis).dt.days.clip(lower=1).astype(float)

    # Régression log-log: log(price) = a * log(days) + b
    x = np.log10(days_since_genesis)
    y = np.log10(d["close"].clip(lower=1e-9))

    # Calcul de la ligne de régression (milieu du Rainbow)
    coeffs = np.polyfit(x, y, deg=1)
    slope, intercept = coeffs[0], coeffs[1]

    # Ligne médiane en log
    log_mid = intercept + slope * x
    mid_price = 10 ** log_mid

    # Calcul des bandes min et max basées sur l'historique
    log_price = np.log10(d["close"].clip(lower=1e-12))
    deviation = log_price - log_mid

    # Min et Max historiques
    min_dev = float(deviation.min())
    max_dev = float(deviation.max())

    # Sécurité : si pas assez de variance
    if abs(max_dev - min_dev) < 0.1:
        min_dev = -0.5
        max_dev = 0.5

    # Bandes du Rainbow
    log_min = log_mid + min_dev
    log_max = log_mid + max_dev

    min_price = 10 ** log_min
    max_price = 10 ** log_max

    # Position normalisée (0 = ruban bas, 1 = ruban haut)
    # On utilise l'échelle log pour une meilleure distribution
    rainbow_position = (log_price - log_min) / (log_max - log_min)
    rainbow_position = rainbow_position.clip(0.0, 1.0).fillna(0.5)

    # Ajout au dataframe
    d["rainbow_mid"] = mid_price
    d["rainbow_min"] = min_price
    d["rainbow_max"] = max_price
    d["rainbow_position"] = rainbow_position

    return d


def calculate_allocation(df: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    """
    Calcule l'allocation en fonction du FNG et Rainbow Chart

    LOGIQUE:
    - FNG bas + Rainbow bas → Allocation HAUTE (acheter)
    - FNG haut + Rainbow haut → Allocation BASSE (vendre)
    """
    d = df.copy()

    # Normalisation FNG (0-100 → 0-1)
    fng_normalized = d["fng"] / 100.0

    # Score d'achat basé sur FNG (1 = max FEAR, 0 = max GREED)
    # Interpolation linéaire entre les seuils
    fng_buy_score = np.where(
        d["fng"] <= cfg.fng_buy_threshold,
        1.0,  # FEAR maximum → achat fort
        np.where(
            d["fng"] >= cfg.fng_sell_threshold,
            0.0,  # GREED maximum → pas d'achat
            (cfg.fng_sell_threshold - d["fng"]) / (cfg.fng_sell_threshold - cfg.fng_buy_threshold)
        )
    )

    # Score d'achat basé sur Rainbow (1 = prix très bas, 0 = prix très haut)
    rainbow_pos = d["rainbow_position"]
    rainbow_buy_score = np.where(
        rainbow_pos <= cfg.rainbow_buy_threshold,
        1.0,  # Prix bas → achat fort
        np.where(
            rainbow_pos >= cfg.rainbow_sell_threshold,
            0.0,  # Prix haut → pas d'achat
            (cfg.rainbow_sell_threshold - rainbow_pos) / (cfg.rainbow_sell_threshold - cfg.rainbow_buy_threshold)
        )
    )

    # Score combiné: on prend la moyenne des deux signaux
    # Les deux doivent être alignés pour un signal fort
    combined_score = (fng_buy_score + rainbow_buy_score) / 2.0

    # Allocation en % (0-100)
    allocation_pct = cfg.min_allocation_pct + combined_score * (cfg.max_allocation_pct - cfg.min_allocation_pct)
    allocation_pct = np.clip(allocation_pct, cfg.min_allocation_pct, cfg.max_allocation_pct)

    # Ajout des colonnes de diagnostic
    d["fng_normalized"] = fng_normalized
    d["fng_buy_score"] = fng_buy_score
    d["rainbow_buy_score"] = rainbow_buy_score
    d["combined_score"] = combined_score
    d["allocation_pct"] = allocation_pct

    return d


def _quantize_bands(rainbow_pos: pd.Series, band_count: int) -> tuple[pd.Series, pd.Series]:
    band_edges = np.linspace(0, 1, band_count + 1)
    band_ids = pd.Series(
        np.digitize(rainbow_pos.clip(0.0, 1.0), band_edges[1:-1], right=False),
        index=rainbow_pos.index,
        dtype=int,
    )
    labels = [
        "🔥 Fortement survendu",
        "Survendu",
        "Bonne valeur",
        "Zone neutre",
        "Chaleur modérée",
        "Suracheté",
        "Bull euphérique",
        "🚀 Bulle",
    ]
    if band_count > len(labels):
        labels = labels + [f"Bande {i+1}" for i in range(len(labels), band_count)]
    label_map = {i: labels[i] for i in range(min(band_count, len(labels)))}
    band_labels = band_ids.map(label_map)
    return band_ids, band_labels


def build_rainbow_only_signals(df: pd.DataFrame, cfg: RainbowOnlyConfig) -> pd.DataFrame:
    """
    Génère une stratégie long-only basée uniquement sur la position dans le Rainbow Chart.

    Logique :
    - En dessous de `rainbow_buy_threshold` → allocation max
    - Au-dessus de `rainbow_sell_threshold` → allocation min
    - Entre les deux → interpolation lissée par `allocation_power`
    """

    if cfg.rainbow_buy_threshold >= cfg.rainbow_sell_threshold:
        raise ValueError("Le seuil d'achat doit être inférieur au seuil de vente pour le Rainbow.")

    d = calculate_rainbow_position(df)
    rainbow_pos = d["rainbow_position"].clip(0.0, 1.0)

    span = cfg.rainbow_sell_threshold - cfg.rainbow_buy_threshold
    interp = ((cfg.rainbow_sell_threshold - rainbow_pos) / max(span, 1e-9)).clip(0.0, 1.0)
    rainbow_score = interp ** cfg.allocation_power

    allocation_pct = cfg.min_allocation_pct + rainbow_score * (cfg.max_allocation_pct - cfg.min_allocation_pct)
    allocation_pct = np.clip(allocation_pct, cfg.min_allocation_pct, cfg.max_allocation_pct)

    # Application du seuil de changement minimum
    pos_filtered = []
    current_pos = 0.0
    for target in allocation_pct:
        at_extreme = target <= cfg.min_allocation_pct + 1e-9 or target >= cfg.max_allocation_pct - 1e-9
        if at_extreme or abs(target - current_pos) >= cfg.min_position_change_pct:
            current_pos = target
        pos_filtered.append(current_pos)

    d["rainbow_score"] = rainbow_score
    d["pos_raw"] = allocation_pct
    d["pos_target"] = pd.Series(pos_filtered, index=d.index)
    d["pos"] = d["pos_target"].shift(1).fillna(0.0) if cfg.execute_next_day else d["pos_target"]
    d["pos_change"] = d["pos"].diff().fillna(0.0)
    d["trade"] = (d["pos_change"].abs() > 0.01).astype(int)

    # Diagnostic: bande actuelle dans le dégradé
    band_ids, band_labels = _quantize_bands(rainbow_pos, cfg.band_count)
    d["rainbow_band"] = band_ids
    d["rainbow_band_label"] = band_labels

    return d


def build_signals(df: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    """
    Construit les signaux de trading complets

    1. Calcule la position Rainbow
    2. Calcule l'allocation optimale
    3. Applique le seuil de changement minimum
    4. Applique l'exécution J+1 si nécessaire
    """
    # Calcul Rainbow Chart
    d = calculate_rainbow_position(df)

    # Calcul de l'allocation
    d = calculate_allocation(d, cfg)

    # Position cible (avant filtrage)
    d["pos_raw"] = d["allocation_pct"]

    # Filtrage: on ne change de position que si le changement est > seuil
    min_change = cfg.min_position_change_pct
    pos_filtered = []
    current_pos = 0.0

    for target in d["pos_raw"]:
        # Si changement > seuil, on ajuste
        if abs(target - current_pos) >= min_change:
            current_pos = target
        pos_filtered.append(current_pos)

    d["pos_target"] = pd.Series(pos_filtered, index=d.index)

    # Position réelle (avec décalage J+1 si nécessaire)
    if cfg.execute_next_day:
        d["pos"] = d["pos_target"].shift(1).fillna(0.0)
    else:
        d["pos"] = d["pos_target"]

    # Détection des trades (changement de position)
    d["pos_change"] = d["pos"].diff().fillna(0.0)
    d["trade"] = (d["pos_change"].abs() > 0.01).astype(int)

    return d
