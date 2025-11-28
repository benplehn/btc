"""
Optimisation des paramètres de stratégie avec Walk-Forward Analysis

Grid Search et Optuna pour trouver les meilleurs seuils FNG et Rainbow
"""
from __future__ import annotations
import itertools
from typing import Callable, Dict, Iterable, List, Tuple, Optional
import optuna
import pandas as pd
import numpy as np

from .backtest import run_backtest
from .strategy import StrategyConfig, build_signals


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


def evaluate_config(df: pd.DataFrame, cfg: StrategyConfig, fees_bps: float) -> Dict:
    """
    Évalue une configuration sur tout le dataset

    Returns:
        dict avec 'metrics', 'df', 'config'
    """
    # Génération des signaux
    signals_df = build_signals(df, cfg)

    # Backtest
    result = run_backtest(signals_df, fees_bps=fees_bps)

    # Calcul de trades par an
    metrics = result["metrics"]
    days = metrics.get("Days", 1)
    years = max(days / 365.0, 1e-9)
    metrics["trades_per_year"] = metrics.get("trades", 0) / years

    return {
        "metrics": metrics,
        "df": result["df"],
        "config": cfg
    }


def score_result(metrics: Dict[str, float]) -> float:
    """
    Score d'une configuration

    Objectif: maximiser le ratio Equity finale / Buy&Hold
    """
    equity_final = metrics.get("EquityFinal", 0.0)
    bh_equity_final = metrics.get("BHEquityFinal", 1.0)

    # Ratio de performance vs Buy & Hold
    ratio = equity_final / max(bh_equity_final, 1e-12)

    return ratio


def walk_forward_cv(
    df: pd.DataFrame,
    cfg: StrategyConfig,
    fees_bps: float,
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

    # Calcul du minimum de jours nécessaires
    min_days_needed = n_folds * 50  # Au moins 50 jours par fold

    if n < min_days_needed:
        raise ValueError(
            f"Pas assez de données pour walk-forward: {n} jours disponibles, "
            f"besoin de {min_days_needed} minimum pour {n_folds} folds. "
            f"Période disponible: {d['date'].min().date()} → {d['date'].max().date()}"
        )

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
        result = evaluate_config(test_df, cfg, fees_bps)

        # On garde seulement les métriques de la période de test pure
        # (après le contexte)
        actual_test_start = test_start - context_start
        test_only_df = result["df"].iloc[actual_test_start:].copy()

        # Recalcul des métriques sur la période de test pure
        from .metrics import compute_metrics
        test_metrics = compute_metrics(test_only_df)
        test_metrics["trades"] = int(test_only_df["trade"].sum())
        days = len(test_only_df)
        years = max(days / 365.0, 1e-9)
        test_metrics["trades_per_year"] = test_metrics["trades"] / years

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
        result = evaluate_config(d, cfg, fees_bps)
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
    full_result = evaluate_config(d, cfg, fees_bps)

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
                n_folds=wf_n_folds,
                train_ratio=wf_train_ratio
            )
            metrics = wf_result["median_metrics"]
            full_metrics = wf_result["full_metrics"]
        else:
            # Évaluation simple sur tout le dataset
            result = evaluate_config(df, cfg, fees_bps)
            metrics = result["metrics"]
            full_metrics = metrics

        # Filtre: nombre minimum de trades par an
        trades_per_year = metrics.get("trades_per_year", 0.0)
        if trades_per_year < min_trades_per_year:
            continue

        # Score
        current_score = score_result(metrics)

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
                n_folds=wf_n_folds,
                train_ratio=wf_train_ratio
            )
            metrics = wf_result["median_metrics"]
        else:
            result = evaluate_config(df, cfg, fees_bps)
            metrics = result["metrics"]

        # Filtre trades/an
        trades_per_year = metrics.get("trades_per_year", 0.0)
        if trades_per_year < min_trades_per_year:
            raise optuna.TrialPruned()

        # Score à maximiser
        return score_result(metrics)

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
            wf_result = walk_forward_cv(df, cfg, fees_bps, n_folds=wf_n_folds, train_ratio=wf_train_ratio)
            metrics = wf_result["median_metrics"]
            full_metrics = wf_result["full_metrics"]
        else:
            result = evaluate_config(df, cfg, fees_bps)
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
