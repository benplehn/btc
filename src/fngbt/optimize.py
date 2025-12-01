"""
Optimisation des paramètres de stratégie avec Walk-Forward Analysis

Grid Search et Optuna pour trouver les meilleurs seuils FNG et Rainbow
"""
from __future__ import annotations
import itertools
from typing import Callable, Dict, Iterable, List, Tuple, Optional, Union
import optuna
import pandas as pd
import numpy as np

from .backtest import run_backtest
from .strategy import StrategyConfig, RainbowOnlyConfig, build_signals, build_rainbow_only_signals


def param_grid(space: Dict[str, Iterable]) -> List[Dict]:
    """Génère toutes les combinaisons possibles de paramètres"""
    keys = list(space.keys())
    vals = [list(space[k]) for k in keys]
    return [dict(zip(keys, comb)) for comb in itertools.product(*vals)]


def default_search_space() -> Dict[str, Iterable]:
    """
    Espace de recherche par défaut pour les paramètres

    On cherche les meilleurs seuils pour:
    - FNG buy/sell thresholds (quand acheter/vendre basé sur Fear & Greed)
    - Rainbow buy/sell thresholds (quand acheter/vendre basé sur position dans Rainbow)
    - min_position_change_pct (éviter les micro-ajustements)
    """
    return {
        # Seuils Fear & Greed (0-100)
        "fng_buy_threshold": [15, 20, 25, 30, 35],  # Zone FEAR → achat
        "fng_sell_threshold": [65, 70, 75, 80, 85],  # Zone GREED → vente

        # Seuils Rainbow (0-1)
        "rainbow_buy_threshold": [0.2, 0.25, 0.3, 0.35, 0.4],  # Prix bas → achat
        "rainbow_sell_threshold": [0.6, 0.65, 0.7, 0.75, 0.8],  # Prix haut → vente

        # Allocation
        "max_allocation_pct": [100],  # Toujours 100% max pour l'instant
        "min_allocation_pct": [0],    # Toujours 0% min pour l'instant
        "min_position_change_pct": [5.0, 10.0, 15.0, 20.0],  # Seuil de changement min

        # Exécution
        "execute_next_day": [True],  # Toujours J+1 pour éviter look-ahead
    }


def _augment_with_rainbow_diagnostics(
    metrics: Dict[str, float],
    df: pd.DataFrame,
    buy_threshold: Optional[float] = None,
    sell_threshold: Optional[float] = None,
) -> Dict[str, float]:
    if "rainbow_position" in df:
        pos = df["rainbow_position"].astype(float)
        metrics["rainbow_pos_mean"] = float(pos.mean())
        metrics["rainbow_pos_median"] = float(pos.median())
        metrics["rainbow_pos_std"] = float(pos.std())

        pos_diff = pos.diff().fillna(0.0)
        metrics["rainbow_pos_velocity"] = float(pos_diff.abs().mean())
        metrics["rainbow_pos_drift"] = float(pos_diff.mean())
        metrics["rainbow_pos_up_speed"] = float(pos_diff[pos_diff > 0].mean() or 0.0)
        metrics["rainbow_pos_down_speed"] = float(pos_diff[pos_diff < 0].abs().mean() or 0.0)

        if buy_threshold is not None:
            metrics["rainbow_time_in_buy_zone"] = float((pos <= buy_threshold).mean())
        if sell_threshold is not None:
            metrics["rainbow_time_in_sell_zone"] = float((pos >= sell_threshold).mean())

    if "rainbow_band" in df:
        band = df["rainbow_band"].astype(float)
        velocity = band.diff().abs().fillna(0.0)
        metrics["rainbow_band_velocity"] = float(velocity.mean())
        days = max(len(df), 1)
        years = max(days / 365.0, 1e-9)
        metrics["rainbow_band_cross_per_year"] = float((velocity > 0).sum() / years)

    return metrics


ConfigType = Union[StrategyConfig, RainbowOnlyConfig]


def _build_signals_for_cfg(df: pd.DataFrame, cfg: ConfigType) -> pd.DataFrame:
    """Routes vers le bon constructeur de signaux selon le type de config."""

    if isinstance(cfg, RainbowOnlyConfig):
        return build_rainbow_only_signals(df, cfg)
    return build_signals(df, cfg)


def evaluate_config(df: pd.DataFrame, cfg: ConfigType, fees_bps: float, initial_capital: float = 100.0) -> Dict:
    """
    Évalue une configuration sur tout le dataset

    Returns:
        dict avec 'metrics', 'df', 'config'
    """
    # Génération des signaux
    signals_df = _build_signals_for_cfg(df, cfg)

    # Backtest
    result = run_backtest(signals_df, fees_bps=fees_bps, initial_capital=initial_capital)

    # Calcul de trades par an
    metrics = result["metrics"]
    days = metrics.get("Days", 1)
    years = max(days / 365.0, 1e-9)
    metrics["trades_per_year"] = metrics.get("trades", 0) / years

    metrics = _augment_with_rainbow_diagnostics(
        metrics,
        result["df"],
        buy_threshold=getattr(cfg, "rainbow_buy_threshold", None),
        sell_threshold=getattr(cfg, "rainbow_sell_threshold", None),
    )

    return {
        "metrics": metrics,
        "df": result["df"],
        "config": cfg
    }


def score_result(
    metrics: Dict[str, float],
    objective: str = "equity_ratio",
    turnover_penalty: float = 0.0,
) -> float:
    """
    Score d'une configuration.

    objective:
      - equity_ratio (EquityFinal / BHEquityFinal)
      - equity_final (EquityFinal)
      - equity_value (EquityFinalValue)
      - cagr / sharpe / sortino / calmar (selon la métrique homonyme)
    turnover_penalty: pénalité multiplicative appliquée au turnover total
    """
    equity_final = metrics.get("EquityFinal", 0.0)
    bh_equity_final = metrics.get("BHEquityFinal", 1.0)
    equity_value = metrics.get("EquityFinalValue", equity_final)

    base_score = {
        "equity_ratio": equity_final / max(bh_equity_final, 1e-12),
        "equity_final": equity_final,
        "equity_value": equity_value,
        "cagr": metrics.get("CAGR", 0.0),
        "sharpe": metrics.get("Sharpe", 0.0),
        "sortino": metrics.get("Sortino", 0.0),
        "calmar": metrics.get("Calmar", 0.0),
    }.get(objective, equity_final / max(bh_equity_final, 1e-12))

    penalty = turnover_penalty * metrics.get("turnover_total", 0.0)
    return float(base_score - penalty)


def walk_forward_cv(
    df: pd.DataFrame,
    cfg: ConfigType,
    fees_bps: float,
    initial_capital: float = 100.0,
    n_folds: int = 5,
    train_ratio: float = 0.6
) -> Dict:
    """
    Walk-Forward Cross-Validation

    Divise les données en n_folds périodes successives.
    Pour chaque fold:
    - Train sur train_ratio% des données
    - Test sur le reste

    Args:
        df: DataFrame complet
        cfg: Configuration à tester
        fees_bps: Frais en basis points
        n_folds: Nombre de périodes de test
        train_ratio: Ratio train/test (ex: 0.6 = 60% train, 40% test)

    Returns:
        dict avec métriques agrégées et détails par fold
    """
    d = df.sort_values("date").reset_index(drop=True)
    n = len(d)

    if n < 100:
        raise ValueError("Pas assez de données pour walk-forward")

    # Calcul de la taille de chaque fenêtre
    fold_size = n // n_folds
    train_size = int(fold_size * train_ratio)
    test_size = fold_size - train_size

    fold_results = []

    for i in range(n_folds):
        # Indices de la fenêtre
        fold_start = i * fold_size
        train_start = fold_start
        train_end = fold_start + train_size
        test_start = train_end
        test_end = min(fold_start + fold_size, n)

        # Si pas assez de données pour ce fold, on skip
        if test_end - test_start < 30:
            continue

        # Données de test (on garde aussi un peu de contexte pour les calculs)
        # On prend 365 jours avant test_start si possible pour avoir le contexte Rainbow
        context_start = max(0, test_start - 365)
        test_df = d.iloc[context_start:test_end].copy()

        # Évaluation sur cette période de test
        result = evaluate_config(test_df, cfg, fees_bps, initial_capital=initial_capital)

        # On garde seulement les métriques de la période de test pure
        # (après le contexte)
        actual_test_start = test_start - context_start
        test_only_df = result["df"].iloc[actual_test_start:].copy()

        # Recalcul des métriques sur la période de test pure
        from .metrics import compute_metrics
        test_metrics = compute_metrics(test_only_df, initial_capital=initial_capital)
        test_metrics["trades"] = int(test_only_df["trade"].sum())
        days = len(test_only_df)
        years = max(days / 365.0, 1e-9)
        test_metrics["trades_per_year"] = test_metrics["trades"] / years
        test_metrics = _augment_with_rainbow_diagnostics(
            test_metrics,
            test_only_df,
            buy_threshold=getattr(cfg, "rainbow_buy_threshold", None),
            sell_threshold=getattr(cfg, "rainbow_sell_threshold", None),
        )

        fold_results.append({
            "fold": i,
            "train_start": train_start,
            "train_end": train_end,
            "test_start": test_start,
            "test_end": test_end,
            "metrics": test_metrics
        })

    if not fold_results:
        # Fallback: évaluation sur tout le dataset
        result = evaluate_config(d, cfg, fees_bps, initial_capital=initial_capital)
        return {
            "folds": [],
            "median_metrics": result["metrics"],
            "all_folds_metrics": [],
            "full_metrics": result["metrics"]
        }

    # Agrégation: médiane des métriques sur tous les folds
    all_folds_metrics = [f["metrics"] for f in fold_results]
    metric_keys = all_folds_metrics[0].keys()

    median_metrics = {}
    for key in metric_keys:
        values = [m[key] for m in all_folds_metrics if key in m]
        median_metrics[key] = float(np.median(values))

    # Évaluation sur le dataset complet pour référence
    full_result = evaluate_config(d, cfg, fees_bps, initial_capital=initial_capital)

    return {
        "folds": fold_results,
        "median_metrics": median_metrics,
        "all_folds_metrics": all_folds_metrics,
        "full_metrics": full_result["metrics"]
    }


def grid_search(
    df: pd.DataFrame,
    search_space: Dict[str, Iterable],
    fees_bps: float = 10.0,
    use_walk_forward: bool = True,
    wf_n_folds: int = 5,
    wf_train_ratio: float = 0.6,
    min_trades_per_year: float = 1.0,
    initial_capital: float = 100.0,
    objective: str = "equity_ratio",
    turnover_penalty: float = 0.0,
    progress_cb: Optional[Callable[[int, int, Optional[float]], None]] = None,
) -> pd.DataFrame:
    """
    Grid Search avec Walk-Forward ou évaluation simple

    Args:
        df: DataFrame avec prix et FNG
        search_space: Dictionnaire des paramètres à tester
        fees_bps: Frais de transaction
        use_walk_forward: Si True, utilise walk-forward CV
        wf_n_folds: Nombre de folds pour walk-forward
        wf_train_ratio: Ratio train/test
        min_trades_per_year: Filtre minimum de trades/an
        progress_cb: Callback(current, total, best_score)

    Returns:
        DataFrame avec résultats triés par score
    """
    combos = param_grid(search_space)
    total = len(combos)

    print(f"\n🔍 Grid Search: {total} combinaisons à tester")
    print(f"📊 Walk-Forward: {'OUI' if use_walk_forward else 'NON'}")
    if use_walk_forward:
        print(f"   - Folds: {wf_n_folds}")
        print(f"   - Train/Test ratio: {wf_train_ratio:.0%}/{1-wf_train_ratio:.0%}")

    results = []
    best_score = -float("inf")

    for idx, params in enumerate(combos, start=1):
        cfg = StrategyConfig(**params)

        if use_walk_forward:
            # Walk-forward cross-validation
            wf_result = walk_forward_cv(
                df, cfg, fees_bps,
                initial_capital=initial_capital,
                n_folds=wf_n_folds,
                train_ratio=wf_train_ratio
            )
            metrics = wf_result["median_metrics"]
            full_metrics = wf_result["full_metrics"]
        else:
            # Évaluation simple sur tout le dataset
            result = evaluate_config(df, cfg, fees_bps, initial_capital=initial_capital)
            metrics = result["metrics"]
            full_metrics = metrics

        # Filtre: nombre minimum de trades par an
        trades_per_year = metrics.get("trades_per_year", 0.0)
        if trades_per_year < min_trades_per_year:
            continue

        # Score
        current_score = score_result(metrics, objective=objective, turnover_penalty=turnover_penalty)

        # Stockage des résultats
        row = {
            **cfg.to_dict(),
            "score": current_score,
            **{f"cv_{k}": v for k, v in metrics.items()},
            **{f"full_{k}": v for k, v in full_metrics.items()},
        }
        results.append(row)

        # Mise à jour du meilleur score
        if current_score > best_score:
            best_score = current_score

        # Callback de progression
        if progress_cb:
            progress_cb(idx, total, best_score if best_score != -float("inf") else None)

        # Affichage progression
        if idx % 10 == 0 or idx == total:
            print(f"   Progression: {idx}/{total} ({idx/total*100:.1f}%) - Best score: {best_score:.3f}")

    # Conversion en DataFrame et tri
    results_df = pd.DataFrame(results)

    if not results_df.empty:
        results_df = results_df.sort_values("score", ascending=False).reset_index(drop=True)

    print(f"\n✅ Grid Search terminé: {len(results_df)} configurations valides trouvées")

    return results_df


def optuna_search(
    df: pd.DataFrame,
    search_space: Dict[str, Iterable],
    n_trials: int = 100,
    fees_bps: float = 10.0,
    use_walk_forward: bool = True,
    wf_n_folds: int = 5,
    wf_train_ratio: float = 0.6,
    min_trades_per_year: float = 1.0,
    initial_capital: float = 100.0,
    objective: str = "equity_ratio",
    turnover_penalty: float = 0.0,
    progress_cb: Optional[Callable[[int, int, Optional[float]], None]] = None,
) -> pd.DataFrame:
    """
    Optimisation avec Optuna

    Plus efficace que Grid Search pour grands espaces de recherche
    """
    print(f"\n🔍 Optuna Search: {n_trials} trials")
    print(f"📊 Walk-Forward: {'OUI' if use_walk_forward else 'NON'}")

    # Conversion des listes en catégories Optuna
    param_keys = list(search_space.keys())

    def objective(trial: optuna.Trial):
        """Fonction objectif à maximiser"""
        # Sélection des paramètres
        params = {}
        for key in param_keys:
            values = list(search_space[key])
            params[key] = trial.suggest_categorical(key, values)

        cfg = StrategyConfig(**params)

        # Évaluation
        if use_walk_forward:
            wf_result = walk_forward_cv(
                df, cfg, fees_bps,
                initial_capital=initial_capital,
                n_folds=wf_n_folds,
                train_ratio=wf_train_ratio
            )
            metrics = wf_result["median_metrics"]
        else:
            result = evaluate_config(df, cfg, fees_bps, initial_capital=initial_capital)
            metrics = result["metrics"]

        # Filtre trades/an
        trades_per_year = metrics.get("trades_per_year", 0.0)
        if trades_per_year < min_trades_per_year:
            raise optuna.TrialPruned()

        # Score à maximiser
        return score_result(metrics, objective=objective, turnover_penalty=turnover_penalty)

    # Création de l'étude Optuna
    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=42)
    )

    # Callback de progression
    completed = 0
    best_val: Optional[float] = None

    def _callback(study: optuna.Study, trial: optuna.Trial):
        nonlocal completed, best_val
        if trial.state == optuna.trial.TrialState.COMPLETE:
            completed += 1
            best_val = study.best_value

            if completed % 10 == 0:
                print(f"   Trial {completed}/{n_trials} - Best: {best_val:.3f}")

        if progress_cb:
            progress_cb(completed, n_trials, best_val)

    # Optimisation
    study.optimize(objective, n_trials=n_trials, callbacks=[_callback], show_progress_bar=False)

    print(f"\n✅ Optuna terminé: {len(study.trials)} trials")

    # Extraction des résultats
    results = []
    for trial in study.trials:
        if trial.state != optuna.trial.TrialState.COMPLETE:
            continue

        params = trial.params
        cfg = StrategyConfig(**params)

        # Ré-évaluation pour avoir toutes les métriques
        if use_walk_forward:
            wf_result = walk_forward_cv(
                df,
                cfg,
                fees_bps,
                initial_capital=initial_capital,
                n_folds=wf_n_folds,
                train_ratio=wf_train_ratio,
            )
            metrics = wf_result["median_metrics"]
            full_metrics = wf_result["full_metrics"]
        else:
            result = evaluate_config(df, cfg, fees_bps, initial_capital=initial_capital)
            metrics = result["metrics"]
            full_metrics = metrics

        row = {
            **cfg.to_dict(),
            "score": trial.value,
            **{f"cv_{k}": v for k, v in metrics.items()},
            **{f"full_{k}": v for k, v in full_metrics.items()},
        }
        results.append(row)

    results_df = pd.DataFrame(results)
    if not results_df.empty:
        results_df = results_df.sort_values("score", ascending=False).reset_index(drop=True)

    return results_df


# === Rainbow-only optimisation ==================================================


def rainbow_only_search_space(
    buy_thresholds: Iterable[float] | None = None,
    sell_thresholds: Iterable[float] | None = None,
    allocation_powers: Iterable[float] | None = None,
    top_decays: Iterable[float] | None = None,
    max_allocations: Iterable[int] | None = None,
    min_allocations: Iterable[int] | None = None,
    min_position_changes: Iterable[float] | None = None,
    execute_next_day: Iterable[bool] | None = None,
    band_counts: Iterable[int] | None = None,
) -> Dict[str, Iterable]:
    return {
        "rainbow_buy_threshold": list(buy_thresholds or [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]),
        "rainbow_sell_threshold": list(sell_thresholds or [0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85]),
        "allocation_power": list(allocation_powers or [0.8, 1.0, 1.2, 1.5]),
        "rainbow_top_decay": list(top_decays or [0.0, 0.01, 0.02, 0.03]),
        "max_allocation_pct": list(max_allocations or [75, 100]),
        "min_allocation_pct": list(min_allocations or [0, 10, 20]),
        "min_position_change_pct": list(min_position_changes or [2.5, 5.0, 10.0, 15.0]),
        "execute_next_day": list(execute_next_day or [True]),
        "band_count": list(band_counts or [8]),
    }


def _evaluate_rainbow_only(
    df: pd.DataFrame,
    cfg: RainbowOnlyConfig,
    fees_bps: float,
    initial_capital: float,
) -> Dict:
    signals_df = build_rainbow_only_signals(df, cfg)
    result = run_backtest(signals_df, fees_bps=fees_bps, initial_capital=initial_capital)
    metrics = result["metrics"]
    days = metrics.get("Days", 1)
    years = max(days / 365.0, 1e-9)
    metrics["trades_per_year"] = metrics.get("trades", 0) / years
    metrics = _augment_with_rainbow_diagnostics(
        metrics,
        result["df"],
        buy_threshold=cfg.rainbow_buy_threshold,
        sell_threshold=cfg.rainbow_sell_threshold,
    )
    return {"metrics": metrics, "df": result["df"], "config": cfg}


def grid_search_rainbow_only(
    df: pd.DataFrame,
    search_space: Dict[str, Iterable],
    fees_bps: float = 10.0,
    use_walk_forward: bool = True,
    wf_n_folds: int = 5,
    wf_train_ratio: float = 0.6,
    min_trades_per_year: float = 0.5,
    initial_capital: float = 100.0,
    objective: str = "equity_ratio",
    turnover_penalty: float = 0.0,
    progress_cb: Optional[Callable[[int, int, Optional[float]], None]] = None,
) -> pd.DataFrame:
    combos = param_grid(search_space)
    total = len(combos)

    print(f"\n🔍 Grid Search Rainbow-only: {total} combinaisons à tester")
    print(f"📊 Walk-Forward: {'OUI' if use_walk_forward else 'NON'}")
    if use_walk_forward:
        print(f"   - Folds: {wf_n_folds}")
        print(f"   - Train/Test ratio: {wf_train_ratio:.0%}/{1-wf_train_ratio:.0%}")

    results = []
    best_score = -float("inf")

    for idx, params in enumerate(combos, start=1):
        cfg = RainbowOnlyConfig(**params)

        if cfg.rainbow_buy_threshold >= cfg.rainbow_sell_threshold:
            continue

        if use_walk_forward:
            wf_result = walk_forward_cv(
                df,
                cfg,  # type: ignore[arg-type]
                fees_bps,
                initial_capital=initial_capital,
                n_folds=wf_n_folds,
                train_ratio=wf_train_ratio,
            )
            metrics = wf_result["median_metrics"]
            full_metrics = wf_result["full_metrics"]
        else:
            result = _evaluate_rainbow_only(df, cfg, fees_bps, initial_capital)
            metrics = result["metrics"]
            full_metrics = metrics

        trades_per_year = metrics.get("trades_per_year", 0.0)
        if trades_per_year < min_trades_per_year:
            continue

        current_score = score_result(metrics, objective=objective, turnover_penalty=turnover_penalty)

        row = {
            **cfg.to_dict(),
            "score": current_score,
            **{f"cv_{k}": v for k, v in metrics.items()},
            **{f"full_{k}": v for k, v in full_metrics.items()},
        }
        results.append(row)

        best_score = max(best_score, current_score)

        if progress_cb:
            progress_cb(idx, total, best_score if best_score != -float("inf") else None)

        if idx % 10 == 0 or idx == total:
            print(f"   Progression: {idx}/{total} ({idx/total*100:.1f}%) - Best score: {best_score:.3f}")

    results_df = pd.DataFrame(results)
    if not results_df.empty:
        results_df = results_df.sort_values("score", ascending=False).reset_index(drop=True)

    print(f"\n✅ Grid Search Rainbow terminé: {len(results_df)} configurations valides trouvées")
    return results_df


def optuna_search_rainbow_only(
    df: pd.DataFrame,
    search_space: Dict[str, Iterable],
    n_trials: int = 120,
    fees_bps: float = 10.0,
    use_walk_forward: bool = True,
    wf_n_folds: int = 5,
    wf_train_ratio: float = 0.6,
    min_trades_per_year: float = 0.5,
    initial_capital: float = 100.0,
    objective: str = "equity_ratio",
    turnover_penalty: float = 0.0,
    progress_cb: Optional[Callable[[int, int, Optional[float]], None]] = None,
) -> pd.DataFrame:
    print(f"\n🔍 Optuna Rainbow-only: {n_trials} trials")
    print(f"📊 Walk-Forward: {'OUI' if use_walk_forward else 'NON'}")

    param_keys = list(search_space.keys())

    def objective(trial: optuna.Trial):
        params = {key: trial.suggest_categorical(key, list(search_space[key])) for key in param_keys}
        cfg = RainbowOnlyConfig(**params)

        if cfg.rainbow_buy_threshold >= cfg.rainbow_sell_threshold:
            raise optuna.TrialPruned()

        if use_walk_forward:
            wf_result = walk_forward_cv(
                df,
                cfg,  # type: ignore[arg-type]
                fees_bps,
                initial_capital=initial_capital,
                n_folds=wf_n_folds,
                train_ratio=wf_train_ratio,
            )
            metrics = wf_result["median_metrics"]
        else:
            result = _evaluate_rainbow_only(df, cfg, fees_bps, initial_capital)
            metrics = result["metrics"]

        trades_per_year = metrics.get("trades_per_year", 0.0)
        if trades_per_year < min_trades_per_year:
            raise optuna.TrialPruned()

        return score_result(metrics, objective=objective, turnover_penalty=turnover_penalty)

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=42))

    completed = 0
    best_val: Optional[float] = None

    def _callback(study: optuna.Study, trial: optuna.Trial):
        nonlocal completed, best_val
        if trial.state == optuna.trial.TrialState.COMPLETE:
            completed += 1
            best_val = study.best_value
            if completed % 10 == 0:
                print(f"   Trial {completed}/{n_trials} - Best: {best_val:.3f}")
        if progress_cb:
            progress_cb(completed, n_trials, best_val)

    study.optimize(objective, n_trials=n_trials, callbacks=[_callback], show_progress_bar=False)

    print(f"\n✅ Optuna Rainbow terminé: {len(study.trials)} trials")

    results = []
    for trial in study.trials:
        if trial.state != optuna.trial.TrialState.COMPLETE:
            continue

        params = trial.params
        cfg = RainbowOnlyConfig(**params)

        if use_walk_forward:
            wf_result = walk_forward_cv(
                df,
                cfg,  # type: ignore[arg-type]
                fees_bps,
                initial_capital=initial_capital,
                n_folds=wf_n_folds,
                train_ratio=wf_train_ratio,
            )
            metrics = wf_result["median_metrics"]
            full_metrics = wf_result["full_metrics"]
        else:
            result = _evaluate_rainbow_only(df, cfg, fees_bps, initial_capital)
            metrics = result["metrics"]
            full_metrics = metrics

        row = {
            **cfg.to_dict(),
            "score": trial.value,
            **{f"cv_{k}": v for k, v in metrics.items()},
            **{f"full_{k}": v for k, v in full_metrics.items()},
        }
        results.append(row)

    results_df = pd.DataFrame(results)
    if not results_df.empty:
        results_df = results_df.sort_values("score", ascending=False).reset_index(drop=True)

    return results_df
