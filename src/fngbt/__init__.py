"""
Package fngbt - Bitcoin strategy based on Fear & Greed Index and Rainbow Chart
"""

# Pas d'imports automatiques pour éviter les dépendances inutiles
# Les utilisateurs doivent importer explicitement ce dont ils ont besoin

__all__ = [
    "load_fng_alt",
    "load_btc_prices",
    "merge_daily",
    "to_weekly",
    "StrategyConfig",
    "RainbowOnlyConfig",
    "build_signals",
    "build_rainbow_only_signals",
    "run_backtest",
    "grid_search",
    "optuna_search",
    "evaluate_config",
    "default_search_space",
    "rainbow_only_search_space",
    "grid_search_rainbow_only",
    "optuna_search_rainbow_only",
]
