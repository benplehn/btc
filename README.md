# 🚀 Bitcoin Strategy Optimizer

Outils pour analyser une stratégie long-terme Bitcoin basée sur le **Fear & Greed Index** et un **Rainbow Chart v2** (régression log + bandes de quantiles). Les scripts principaux permettent de vérifier les données, tracer le Rainbow et lancer des optimisations.

## Sommaire rapide
- [Installation](#installation)
- [Sources de données](#sources-de-données)
- [Commandes clés](#commandes-clés)
- [Utilisation détaillée](#utilisation-détaillée)
- [Personnalisation](#personnalisation)
- [Conseils & dépannage](#conseils--dépannage)
- [Avertissement](#avertissement)

## Installation
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Python 3.10+ conseillé. Les dépendances principales sont `pandas`, `numpy`, `requests`, `matplotlib` et `optuna`.

## Sources de données
- **Prix BTC** : API publique `https://api.alternative.me/v2/ticker/bitcoin/history/` (USD). L'API peut ne pas couvrir tout l'historique 2013 → aujourd'hui. Dans ce cas, utilisez un CSV local.
- **Fear & Greed Index** : `https://api.alternative.me/fng/` (timestamps UNIX). Chargé automatiquement par le code.

### CSV local (offline ou historique complet)
Les scripts acceptent `--csv chemin.csv` pour fournir vos propres prix BTC. Format attendu :
```csv
date,close
2013-01-01,13.30
2013-01-02,13.45
...
```
Les dates doivent être au format ISO (timezone naïve) et la colonne `close` numérique.

## Commandes clés
Vérifier que les données sont cohérentes et générer des graphiques :
```bash
# Contrôle des données BTC depuis 2013
python scripts/check_data.py --start 2013-01-01 --plot outputs/btc_prices.png

# Tracer le Rainbow Chart v2 prolongé jusqu'à 2025
python scripts/rainbow_chart_v2.py --start 2013-01-01 --extend-to 2025-12-31 --out outputs/rainbow_v2.png
```
Si l'API ne fournit pas assez d'historique, ajoutez `--csv mon_fichier.csv` aux deux commandes.

Tester la logique stratégique sur des données synthétiques :
```bash
python test_strategy.py
```

Lancer une optimisation interactive :
```bash
python run_optimization.py
```

## Utilisation détaillée
### `scripts/check_data.py`
- Objet : vérifier la continuité des prix BTC (doublons, jours manquants, gaps) et optionnellement sauvegarder un graphique.
- Options principales :
  - `--start YYYY-MM-DD` : début de la période (défaut : 2013-01-01)
  - `--end YYYY-MM-DD` : fin de la période (inclus)
  - `--csv chemin.csv` : fichier local `date,close` si l'API est inaccessible ou incomplète
  - `--plot chemin.png` : enregistre le graphique des prix

### `scripts/rainbow_chart_v2.py`
- Objet : construire le Rainbow Chart v2 (régression log + bandes de quantiles) et l'étendre jusqu'à une date future.
- Options principales :
  - `--start YYYY-MM-DD` : première date de prix utilisée (défaut : 2013-01-01)
  - `--end YYYY-MM-DD` : dernière date réelle à charger
  - `--extend-to YYYY-MM-DD` : projection du Rainbow (défaut : 2025-12-31)
  - `--csv chemin.csv` : fichier local `date,close`
  - `--out chemin.png` : destination du graphique (défaut : `outputs/rainbow_v2.png`)

### `run_optimization.py`
- Objet : optimisation interactive des paramètres FNG/Rainbow (Grid Search ou Optuna) avec walk-forward.
- Fonctionnement :
  1. Télécharge les données FNG et BTC (ou utilise vos CSV locaux via les fonctions de `src/fngbt/data.py`).
  2. Propose plusieurs méthodes : grid exhaustif, Optuna ou test rapide.
  3. Affiche les meilleures configurations, métriques et sauvegarde les résultats en CSV.
- Paramètres par défaut : voir le dictionnaire `search_space` dans le script pour ajuster les bornes.

### `test_strategy.py`
- Objet : scénario de test synthétique pour valider la logique (signaux, frais, exécution T+1).
- Sortie : assertions + métriques de contrôle pour détecter les régressions.

## Personnalisation
- **Espace de recherche** : modifiez `search_space` dans `run_optimization.py` pour ajouter vos propres seuils.
- **Frais de transaction** : ajustez `fees_bps` (basis points) dans `run_optimization.py`.
- **Agrégation hebdo** : la fonction `to_weekly` dans `src/fngbt/data.py` permet de resampler les données en hebdomadaire (`mean` ou `last`).
- **Rainbow Chart** : dans `scripts/rainbow_chart_v2.py`, changez la liste des quantiles dans `build_rainbow_v2` si vous souhaitez d'autres bandes.

## Conseils & dépannage
- L'API Alternative.me peut renvoyer uniquement les prix récents. Si vous voyez un message indiquant un historique partiel, fournissez un CSV couvrant la période souhaitée.
- Assurez-vous d'avoir au moins ~100 jours de données pour les backtests.
- Pour toute incohérence de dates, vérifiez que vos fichiers CSV sont en UTC ou naïfs cohérents (les dates sont normalisées côté code).
- Si un script échoue par manque de dépendance, relancez `pip install -r requirements.txt` dans votre environnement actif.

## Avertissement
Ce projet est fourni à des fins éducatives. Aucune recommandation financière n'est fournie. Le trading de cryptomonnaies comporte des risques importants : faites vos propres recherches et n'investissez que ce que vous pouvez vous permettre de perdre.
