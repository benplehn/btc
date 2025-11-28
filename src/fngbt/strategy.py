from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd


@dataclass
class StrategyConfig:
    """
    Nouveau moteur : le FNG décide du régime (accumuler vs distribuer),
    le Rainbow gère le sizing progressif entre ruban bas et ruban haut.
    """
    fng_source_col: str = "fng"   # colonne à utiliser comme FNG (ex: "ema200_soft")
    use_fng: bool = True
    fng_buy: int = 25               # en-dessous : on est en mode "accumuler"
    fng_sell: int = 70              # au-dessus : on est en mode "distribuer"
    fng_buy_levels: list[int] | None = None  # paliers multiples d'achat (ex: 30,20,10)
    fng_sell_levels: list[int] | None = None # paliers multiples de vente (ex: 60,70,80)
    fng_curve_exp: float = 1.0      # forme de la rampe FNG (1 = linéaire, >1 = plus binaire)
    fng_smoothing_days: int = 1     # lissage EMA du F&G (1 = aucun / brut)

    use_rainbow: bool = True
    rainbow_k: float = 1.5            # courbure de la fonction A(x) (achat bas / vente haut)
    max_allocation_pct: int = 100   # plafond d'expo (en %)
    ramp_step_pct: int = 5          # quantification des pas d'expo (en %)

    execute_next_day: bool = True   # exécution J+1 pour éviter le look-ahead
    min_hold_days: int = 3          # durée minimale avant d'accepter un nouveau changement de position

    def to_dict(self) -> dict:
        return asdict(self)


def build_signals(df: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    """
    Construit un signal où :
    - Le FNG choisit le régime (accumulation vs distribution).
    - Le Rainbow gère la taille d'allocation (plus on est proche du ruban bas, plus on alloue; plus on est proche du ruban haut, plus on allège).
    L'allocation est exprimée en % (0..100).
    """
    d = df.copy()
    fng_col = cfg.fng_source_col or "fng"
    fng_series = d[fng_col] if fng_col in d.columns else d["fng"]  # brut ou colonne alternative
    if cfg.fng_smoothing_days and cfg.fng_smoothing_days > 1:
        fng_used = fng_series.ewm(span=cfg.fng_smoothing_days, adjust=False).mean()
    else:
        fng_used = fng_series
    d["fng_used"] = fng_used

    # --- Bitcoin Rainbow (approx) ---
    if cfg.use_rainbow:
        genesis = pd.Timestamp("2009-01-09")
        days = (d["date"] - genesis).dt.days.clip(lower=1).astype(float)
        x = np.log10(days)
        y = np.log10(d["close"].clip(lower=1e-9))
        try:
            slope, intercept = np.polyfit(x, y, 1)
            mid_log = intercept + slope * x
            rainbow_base = 10 ** mid_log
        except Exception:
            # Repli : conserver le prix comme baseline
            rainbow_base = d["close"]
        d["rainbow_base"] = rainbow_base
        # Bandes complètes pour visualisation : 5 sous le mid, 5 au-dessus, bornées par l'historique
        log_mid = np.log10(rainbow_base.clip(lower=1e-12))
        log_px = np.log10(d["close"].clip(lower=1e-12))
        delta_series = log_px - log_mid
        min_delta = float(delta_series.min()) if len(delta_series) else -1.0
        max_delta = float(delta_series.max()) if len(delta_series) else 1.0
        if not np.isfinite(min_delta):
            min_delta = -1.0
        if not np.isfinite(max_delta):
            max_delta = 1.0
        if min_delta >= 0:
            min_delta = -0.5
        if max_delta <= 0:
            max_delta = 0.5
        below = np.linspace(min_delta, 0.0, 6)[:-1]  # 5 valeurs < 0
        above = np.linspace(0.0, max_delta, 6)[1:]  # 5 valeurs > 0
        all_deltas = list(below) + [0.0] + list(above)
        for delta in all_deltas:
            band = rainbow_base * (10 ** delta)
            d[f"rainbow_band_{delta:+.2f}"] = band
        band_cols = sorted([c for c in d.columns if c.startswith("rainbow_band_")])
        rainbow_min = d[band_cols[0]] if band_cols else d["close"]
        rainbow_max = d[band_cols[-1]] if band_cols else d["close"]
    else:
        rainbow_min = d["close"]
        rainbow_max = d["close"]
        d["rainbow_base"] = d["close"]
        band_cols = []

    # Normalisation Rainbow -> position 0 (ruban min) à 1 (ruban max)
    rainbow_span = (rainbow_max - rainbow_min).replace(0, np.nan)
    rainbow_pos = ((d["close"] - rainbow_min) / rainbow_span).clip(lower=0.0, upper=1.0).fillna(0.0)

    # Courbe d'allocation Rainbow explicite (monotone décroissante)
    # Position dans le ruban en log (0 = bas, 1 = haut)
    log_p = np.log(d["close"].clip(lower=1e-12))
    log_min = np.log(rainbow_min.clip(lower=1e-12))
    log_max = np.log(rainbow_max.clip(lower=1e-12))
    rainbow_pos = ((log_p - log_min) / (log_max - log_min)).clip(lower=0.0, upper=1.0)

    # Fonction A(x) contrarienne, symétrique autour de 0.5, paramétrée par k
    k = max(cfg.rainbow_k, 1e-6)
    def _A(x):
        x = np.clip(x, 0.0, 1.0)
        below = 0.5 + 0.5 * np.power((0.5 - x) / 0.5, k)
        above = 0.5 - 0.5 * np.power((x - 0.5) / 0.5, k)
        return np.where(x < 0.5, below, above)

    rainbow_factor = _A(rainbow_pos)

    # Poids FNG : 1 = plein régime achat (peur), 0 = régime distribution (greed)
    if cfg.use_fng:
        buy_levels = sorted([int(x) for x in (cfg.fng_buy_levels or [cfg.fng_buy])])
        sell_levels = sorted([int(x) for x in (cfg.fng_sell_levels or [cfg.fng_sell])])
        n_buy = max(1, len(buy_levels))
        n_sell = max(1, len(sell_levels))
        buy_steps = np.array([(fng_used.values <= thr).astype(int) for thr in buy_levels]).sum(axis=0) / n_buy
        sell_steps = np.array([(fng_used.values >= thr).astype(int) for thr in sell_levels]).sum(axis=0) / n_sell
        if cfg.fng_curve_exp and cfg.fng_curve_exp != 1.0:
            buy_steps = np.power(buy_steps, cfg.fng_curve_exp)
            sell_steps = np.power(sell_steps, cfg.fng_curve_exp)
        net_fng_weight = np.clip(buy_steps - sell_steps, 0.0, 1.0)
    else:
        buy_steps = np.ones(len(d))
        sell_steps = np.zeros(len(d))
        net_fng_weight = np.ones(len(d))

    # Allocation dépend uniquement du Rainbow (courbe explicite)
    alloc = net_fng_weight * rainbow_factor
    alloc = np.clip(alloc, 0.0, 1.0)
    alloc *= min(max(cfg.max_allocation_pct, 0), 100) / 100.0
    ramp_step = max(1, int(cfg.ramp_step_pct or 1))
    alloc = np.round(alloc * 100.0 / ramp_step) * ramp_step / 100.0
    pos = [int(round(a * 100)) for a in alloc]

    d["rainbow_min"] = rainbow_min
    d["rainbow_max"] = rainbow_max
    d["rainbow_pos"] = rainbow_pos
    d["buy_steps"] = buy_steps
    d["sell_steps"] = sell_steps
    d["net_fng_weight"] = net_fng_weight
    d["rainbow_factor"] = rainbow_factor
    d["alloc_buy_curve"] = rainbow_factor
    d["alloc_raw"] = alloc

    # Hold time minimal avant d'accepter un changement de position
    min_hold = max(0, int(cfg.min_hold_days or 0))
    if min_hold > 1 and pos:
        held = []
        prev = None
        age = 0
        for p in pos:
            if prev is None:
                held.append(p)
                prev = p
                age = 1
                continue
            if p != prev and age < min_hold:
                held.append(prev)
                age += 1
            else:
                held.append(p)
                prev = held[-1]
                age = 1
        pos = held

    d["pos_base"] = pd.Series(pos, index=d.index, dtype="float64")
    d["pos_obs"] = d["pos_base"]
    d["pos"] = (d["pos_obs"].shift(1) if cfg.execute_next_day else d["pos_obs"]).fillna(0).astype(float)
    d["trade"] = (d["pos"].diff().fillna(d["pos"]).abs() > 1e-6).astype(int)

    if cfg.use_fng:
        d["fng_buy_thr"] = cfg.fng_buy
        d["fng_sell_thr"] = cfg.fng_sell

    return d
