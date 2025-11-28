# BTC FNG -> Bitcoin Rainbow (sizing progressif)

Stratégie long-only contrarienne :
- FNG choisit le **régime** : en-dessous du buy -> accumulation ; au-dessus du sell -> distribution ; entre les deux = mix (courbure ajustable).
- Rainbow fixe le **sizing** : plus on est près du ruban bas, plus l'allocation monte ; plus on s'approche du ruban haut, plus on coupe (courbures achat/vente ajustables).

Ce que tu as :
- Backtest rapide CLI : `scripts/run_backtest.py`.
- Optimisation grille ou Optuna (avec validation temporelle) : `scripts/run_optimize.py`.
- UI Streamlit interactive : `streamlit run streamlit_app.py`.

## Installation
```bash
pip install -r requirements.txt
```

## Backtest d’une config
```bash
python3 scripts/run_backtest.py \
  --fng-buy 25 --fng-sell 70 --fng-curve 1.2 \
  --buy-curve 1.4 --sell-curve 2.2 \
  --max-alloc 100 --trade-cooldown 4 --min-hold-days 7 \
  --out outputs/backtest.png
```
Options : `--weekly`, `--no-fng`, `--no-rainbow`, `--same-day` (sinon J+1).

## Optimisation (Optuna ou grille)
```bash
python3 scripts/run_optimize.py \
  --search optuna --n-trials 400 \
  --fng-buy-grid 10:35:5 --fng-sell-grid 55:90:5 --fng-curve-grid 1.0,1.3,1.6 \
  --buy-curve-grid 1.0,1.4,1.8 --sell-curve-grid 1.5,2.0,2.5 --max-alloc-grid 80,100 \
  --cv-mode walkforward --cv-folds 4 --cv-warmup-days 365 \
  --min-trades-per-year 3 \
  --out-csv outputs/opt_results.csv
```
- Score = ratio d’equity finale vs Buy & Hold (médiane des folds). Filtre trades/an appliqué sur la médiane.
- Grilles : `a,b,c` ou `start:end:step`. Mettre `none` ou `0` pour un R illimité.

## GUI Streamlit
```bash
streamlit run streamlit_app.py
```
- Backtest interactif : FNG (régime) + Rainbow (sizing progressif), courbures ajustables.
- Optimisation : grilles FNG/Rainbow, validation temporelle (walkforward/kfold), filtre trades/an.
- Graphiques : prix (log) + Rainbow + allocation, FNG, equity vs B&H.

## Paramètres principaux
- `fng_buy/fng_sell`, `fng_curve_exp`, `fng_smoothing_days`.
- `buy_curve_exp` (achat près du ruban bas), `sell_curve_exp` (patience avant ruban haut), `max_allocation_pct`, `ramp_step_pct`.
- `min_hold_days`, `execute_next_day` (signal J+1).

## Validation temporelle (anti-overfit)
- `--cv-mode none|kfold|walkforward` : recommandé `walkforward`.
- `--cv-folds` : nombre de segments (ex: 4 sur ~6 ans ≈ 1,5 an chacun).
- `--cv-warmup-days` : contexte ajouté avant chaque fold pour stabiliser les indicateurs.
- Les métriques préfixées `med_` sont la médiane des folds et alimentent le score.

## Architecture
- `src/fngbt/data.py` : FNG + prix BTC (yfinance), merge.
- `src/fngbt/strategy.py` : moteur FNG (régime) + Rainbow (sizing progressif).
- `src/fngbt/backtest.py` : backtest long-only avec frais proportionnels au turnover.
- `src/fngbt/optimize.py` : grille/Optuna + validation temporelle, score equity vs B&H.
- `src/fngbt/utils.py` : graphiques overview.
- `streamlit_app.py` : UI (backtest + optimisation).
