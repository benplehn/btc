from __future__ import annotations

import itertools
from typing import Callable, Dict, Iterable, List, Tuple, Optional

import optuna
import pandas as pd
import numpy as np

from .backtest import run_backtest
from .strategy import StrategyConfig, build_signals


def param_grid(space: Dict[str, Iterable]) -> List[Dict]:
    keys = list(space.keys())
    vals = [space[k] for k in keys]
    return [dict(zip(keys, comb)) for comb in itertools.product(*vals)]


def default_search_space(
    use_fng: bool = True,
    fng_source_cols: Iterable[str] | None = None,
    fng_buy_vals: Iterable[int] | None = None,
    fng_sell_vals: Iterable[int] | None = None,
    fng_buy_levels_vals: Iterable[Iterable[int] | None] | None = None,
    fng_sell_levels_vals: Iterable[Iterable[int] | None] | None = None,
    fng_curve_exp_vals: Iterable[float] | None = None,
    fng_smoothing_vals: Iterable[int] | None = None,
    use_rainbow: bool = True,
    rainbow_k_vals: Iterable[float] | None = None,
    max_allocation_pct_vals: Iterable[int] | None = None,
    ramp_step_pct_vals: Iterable[int] | None = None,
    min_hold_days_vals: Iterable[int] | None = None,
    execute_next_day_vals: Iterable[bool] | None = None,
) -> Dict[str, Iterable]:
    """
    Espace de recherche pour le nouveau moteur FNG (régime) + Rainbow (sizing).
    """
    fng_curve_vals = list(fng_curve_exp_vals or [1.0, 1.3, 1.6])
    rainbow_k_list = list(rainbow_k_vals or [1.0, 1.5, 2.0])
    max_alloc_vals = list(max_allocation_pct_vals or [80, 100])
    ramp_vals = list(ramp_step_pct_vals or [5, 10])
    fng_smooth_vals = list(fng_smoothing_vals or [1])
    exe_vals = list(execute_next_day_vals or [True])
    return {
        "use_fng": [use_fng],
        "fng_source_col": list(fng_source_cols or ["fng"]) if use_fng else ["fng"],
        "fng_buy": list(fng_buy_vals or [18, 22, 25, 28]) if use_fng else [0],
        "fng_sell": list(fng_sell_vals or [60, 65, 70, 75]) if use_fng else [0],
        "fng_buy_levels": list(fng_buy_levels_vals or [None]),
        "fng_sell_levels": list(fng_sell_levels_vals or [None]),
        "fng_curve_exp": fng_curve_vals if use_fng else [1.0],
        "fng_smoothing_days": fng_smooth_vals,
        "use_rainbow": [use_rainbow],
        "rainbow_k": rainbow_k_list,
        "max_allocation_pct": max_alloc_vals,
        "ramp_step_pct": ramp_vals,
        "min_hold_days": list(min_hold_days_vals or [3]),
        "execute_next_day": exe_vals,
    }


def evaluate_config(df: pd.DataFrame, cfg: StrategyConfig, fees_bps: float) -> Dict:
    """Backtest complet sur tout l'historique fourni."""
    sig = build_signals(df, cfg)
    res = run_backtest(sig, fees_bps=fees_bps)
    m = res["metrics"]
    trades_py = m.get("trades", 0) / max(m.get("Days", 1) / 365.0, 1e-9)
    m["trades_per_year"] = trades_py
    return {"metrics": m, "df": res["df"], "config": cfg}


def score_metrics(m: Dict[str, float]) -> float:
    """
    Score = ratio d'equity finale vs Buy&Hold, basé sur la médiane des folds si dispo.
    Objectif : maximiser l'argent final relatif au BH.
    """
    def _get(key: str) -> float:
        return float(
            m.get(key, m.get(f"med_{key}", 0.0)) or 0.0
        )

    equity = _get("EquityFinal")
    bh_equity = _get("BHEquityFinal")
    ratio = equity / max(bh_equity, 1e-12)
    return ratio


def _split_indices(n: int, k: int) -> List[Tuple[int, int]]:
    """Découpe n points en k segments contigus aussi équilibrés que possible."""
    if k <= 1:
        return [(0, n)]
    base = n // k
    rem = n % k
    splits = []
    start = 0
    for i in range(k):
        extra = 1 if i < rem else 0
        end = start + base + extra
        splits.append((start, end))
        start = end
    return splits


def _fold_slices(n: int, mode: str, n_folds: int) -> List[Tuple[int, int]]:
    """Renvoie des couples (start, end) pour les fenêtres de test."""
    splits = _split_indices(n, n_folds)
    if mode == "kfold":
        return splits
    if mode == "walkforward":
        # chevauchement zéro, segments qui avancent dans le temps (train implicite = tout avant)
        return splits
    return [(0, n)]


def evaluate_config_cv(
    df: pd.DataFrame,
    cfg: StrategyConfig,
    fees_bps: float,
    cv_mode: str = "none",
    cv_folds: int = 1,
    warmup_days: int = 365,
) -> Dict:
    """
    Évalue une config sur plusieurs segments temporels.
    - cv_mode "none": full sample.
    - "kfold": k segments contigus.
    - "walkforward": k segments successifs (train implicite avant, mais on n'ajuste pas les params).
    warmup_days: jours de contexte ajoutés avant chaque segment pour stabiliser les indicateurs.
    """
    d = df.sort_values("date").reset_index(drop=True)
    n = len(d)
    if n == 0:
        raise ValueError("Dataframe vide pour l'évaluation.")
    cv_mode = cv_mode.lower()
    test_windows = _fold_slices(n, cv_mode, max(1, cv_folds))

    fold_metrics: List[Dict] = []
    for start, end in test_windows:
        start = max(0, int(start))
        end = min(n, int(end))
        if end - start < 10:
            continue
        warmup_start = max(0, start - warmup_days)
        sub = d.iloc[warmup_start:end].reset_index(drop=True)
        res = evaluate_config(sub, cfg, fees_bps=fees_bps)
        # Coupe les métriques au bloc de test (après warmup) pour éviter le préchauffage.
        eval_sig = res["df"].iloc[start - warmup_start :].reset_index(drop=True)
        res_cut = run_backtest(eval_sig, fees_bps=fees_bps)
        m = res_cut["metrics"]
        trades_py = m.get("trades", 0) / max(m.get("Days", 1) / 365.0, 1e-9)
        m["trades_per_year"] = trades_py
        fold_metrics.append(m)

    if not fold_metrics:
        res_full = evaluate_config(d, cfg, fees_bps=fees_bps)
        med_metrics = {f"med_{k}": v for k, v in res_full["metrics"].items()}
        return {
            "full": res_full["metrics"],
            "median": med_metrics,
            "folds": [],
            "df": res_full["df"],
        }

    keys = set().union(*[m.keys() for m in fold_metrics])
    med_metrics = {f"med_{k}": float(np.median([m.get(k, np.nan) for m in fold_metrics])) for k in keys}
    res_full = evaluate_config(d, cfg, fees_bps=fees_bps)
    return {
        "full": res_full["metrics"],
        "median": med_metrics,
        "folds": fold_metrics,
        "df": res_full["df"],
    }


def grid_search_full(
    df: pd.DataFrame,
    search_space: Dict[str, Iterable],
    fees_bps: float = 10.0,
    min_trades_per_year: float = 0.0,
    progress_cb: Optional[Callable[[int, int, Optional[float]], None]] = None,
    cv_mode: str = "none",
    cv_folds: int = 1,
    cv_warmup_days: int = 365,
) -> pd.DataFrame:
    rows = []
    combos = param_grid(search_space)
    total = len(combos)
    best_score = -float("inf")
    for idx, params in enumerate(combos, start=1):
        cfg = StrategyConfig(**params)
        res = evaluate_config_cv(
            df,
            cfg,
            fees_bps=fees_bps,
            cv_mode=cv_mode,
            cv_folds=cv_folds,
            warmup_days=cv_warmup_days,
        )
        med = res["median"]
        full_m = res["full"]
        metric_for_score = med if med else full_m
        med_tpy = metric_for_score.get("med_trades_per_year", metric_for_score.get("trades_per_year", 0.0))
        full_tpy = full_m.get("trades_per_year", 0.0)
        if min_trades_per_year > 0 and (med_tpy < min_trades_per_year or full_tpy < min_trades_per_year):
            continue
        med_eq = med.get("med_EquityFinal", full_m.get("EquityFinal", 0.0))
        med_bh = med.get("med_BHEquityFinal", full_m.get("BHEquityFinal", 0.0))
        full_ratio = full_m.get("EquityFinal", 0.0) / max(full_m.get("BHEquityFinal", 0.0), 1e-12)
        med_ratio = med_eq / max(med_bh, 1e-12)
        row = {
            **cfg.to_dict(),
            **{f"full_{k}": v for k, v in full_m.items()},
            **med,
            "full_equity_ratio": full_ratio,
            "med_equity_ratio": med_ratio,
            "score": score_metrics(metric_for_score),
        }
        rows.append(row)
        if row["score"] > best_score:
            best_score = row["score"]
        if progress_cb:
            progress_cb(idx, total, best_score if best_score != -float("inf") else None)
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("score", ascending=False).reset_index(drop=True)
    return out


def optuna_search(
    df: pd.DataFrame,
    search_space: Dict[str, Iterable],
    n_trials: int = 200,
    fees_bps: float = 10.0,
    min_trades_per_year: float = 0.0,
    progress_cb: Optional[Callable[[int, int, Optional[float]], None]] = None,
    cv_mode: str = "none",
    cv_folds: int = 1,
    cv_warmup_days: int = 365,
) -> pd.DataFrame:
    """
    Optuna sur tout l'historique (lookback déjà appliqué en amont).
    L'espace est défini par des listes (catégorielles), ce qui évite les valeurs hors grille.
    """
    keys = list(search_space.keys())

    def objective(trial: optuna.Trial):
        params = {}
        for k in keys:
            vals = list(search_space[k])
            params[k] = trial.suggest_categorical(k, vals)
        cfg = StrategyConfig(**params)
        res = evaluate_config_cv(
            df,
            cfg,
            fees_bps=fees_bps,
            cv_mode=cv_mode,
            cv_folds=cv_folds,
            warmup_days=cv_warmup_days,
        )
        med = res["median"]
        metric_for_score = med if med else res["full"]
        med_tpy = metric_for_score.get("med_trades_per_year", metric_for_score.get("trades_per_year", 0.0))
        full_tpy = res["full"].get("trades_per_year", 0.0)
        if min_trades_per_year > 0 and (med_tpy < min_trades_per_year or full_tpy < min_trades_per_year):
            raise optuna.TrialPruned()
        return score_metrics(metric_for_score)

    study = optuna.create_study(direction="maximize")
    completed = 0
    best_val: Optional[float] = None

    def _cb(study: optuna.Study, trial: optuna.Trial):
        nonlocal completed, best_val
        if trial.state == optuna.trial.TrialState.COMPLETE:
            completed += 1
            best_val = study.best_value
        if progress_cb:
            progress_cb(completed, n_trials, best_val)

    study.optimize(objective, n_trials=n_trials, callbacks=[_cb])

    rows = []
    for t in study.trials:
        if t.state != optuna.trial.TrialState.COMPLETE:
            continue
        params = t.params
        cfg = StrategyConfig(**params)
        res = evaluate_config_cv(
            df,
            cfg,
            fees_bps=fees_bps,
            cv_mode=cv_mode,
            cv_folds=cv_folds,
            warmup_days=cv_warmup_days,
        )
        med = res["median"]
        full_m = res["full"]
        metric_for_score = med if med else full_m
        med_eq = med.get("med_EquityFinal", full_m.get("EquityFinal", 0.0))
        med_bh = med.get("med_BHEquityFinal", full_m.get("BHEquityFinal", 0.0))
        full_ratio = full_m.get("EquityFinal", 0.0) / max(full_m.get("BHEquityFinal", 0.0), 1e-12)
        med_ratio = med_eq / max(med_bh, 1e-12)
        rows.append(
            {
                **cfg.to_dict(),
                **{f"full_{k}": v for k, v in full_m.items()},
                **med,
                "full_equity_ratio": full_ratio,
                "med_equity_ratio": med_ratio,
                "score": score_metrics(metric_for_score),
                "trial_value": t.value,
            }
        )
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("score", ascending=False).reset_index(drop=True)
    return out
