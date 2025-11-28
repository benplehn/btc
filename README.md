# 🚀 Bitcoin Strategy Optimizer - FNG + Rainbow Chart

**Stratégie d'investissement long terme Bitcoin basée sur 2 indicateurs:**
1. **Fear & Greed Index** (sentiment de marché)
2. **Rainbow Chart** (position du prix vs régression historique)

## 📊 Logique de la stratégie

### Principe investisseur long terme
- **ACHETER** : FNG bas (FEAR) + Prix proche du ruban BAS → Allocation élevée
- **VENDRE** : FNG haut (GREED) + Prix proche du ruban HAUT → Allocation basse

### Exemple concret
```
FNG = 20 (FEAR) + Rainbow Position = 0.2 (prix très bas) → Allocation 100% BTC
FNG = 80 (GREED) + Rainbow Position = 0.8 (prix très haut) → Allocation 0% BTC
FNG = 50 (neutre) + Rainbow Position = 0.5 (milieu) → Allocation ~50% BTC
```

## 🛠️ Installation

```bash
pip install pandas numpy requests optuna matplotlib
# Note: yfinance peut avoir des problèmes, mais le code fonctionne sans
```

## 🧪 Test rapide

```bash
python3 test_strategy.py
```

Cela teste la stratégie avec des données synthétiques et affiche:
- ✅ Validation de la logique
- 📊 Métriques de performance
- 🔍 Comparaison avec Buy & Hold

## 🔍 Optimisation (trouver les meilleurs paramètres)

### Lancement interactif

```bash
python3 run_optimization.py
```

Le script vous guide pas à pas:
1. **Chargement des données** (Fear & Greed + Prix BTC)
2. **Choix de la méthode**:
   - Grid Search (teste toutes les combinaisons)
   - Optuna (plus rapide, intelligent)
   - Test rapide (config par défaut)
3. **Résultats**:
   - Top 10 meilleures configs
   - Performance détaillée
   - Fichiers CSV sauvegardés

### Exemple de sortie

```
🏆 MEILLEURE CONFIGURATION
================================================================================

Paramètres:
   FNG Buy Threshold:     25
   FNG Sell Threshold:    75
   Rainbow Buy Threshold: 0.30
   Rainbow Sell Threshold:0.70
   Min Position Change:   10%

Performance (Walk-Forward CV):
   Score:             1.25x vs B&H
   Equity Finale:     18.21x
   CAGR:              52.3%
   Max Drawdown:      -35.2%
   Sharpe Ratio:      1.82
   Trades/an:         12.3
```

## 📁 Structure du code

### Fichiers principaux

```
src/fngbt/
├── data.py          # Chargement FNG et prix BTC
├── strategy.py      # Logique de la stratégie (CŒUR)
├── backtest.py      # Simulation avec frais
├── optimize.py      # Walk-forward + Grid/Optuna
└── metrics.py       # Calcul CAGR, Sharpe, etc.

run_optimization.py  # Script principal
test_strategy.py     # Tests avec données synthétiques
```

### Code simplifié et clair

Le code a été **entièrement refactorisé** pour être:
- ✅ **Simple**: chaque fonction fait UNE chose
- ✅ **Clair**: noms explicites, commentaires en français
- ✅ **Correct**: logique investisseur long terme respectée
- ✅ **Testable**: facile à comprendre et débugger

## 🎯 Paramètres à optimiser

| Paramètre | Description | Plage typique |
|-----------|-------------|---------------|
| `fng_buy_threshold` | Seuil FNG pour acheter (FEAR) | 15-35 |
| `fng_sell_threshold` | Seuil FNG pour vendre (GREED) | 65-85 |
| `rainbow_buy_threshold` | Position Rainbow pour acheter | 0.2-0.4 |
| `rainbow_sell_threshold` | Position Rainbow pour vendre | 0.6-0.8 |
| `min_position_change_pct` | Changement min pour trader | 5-20% |

## 📈 Walk-Forward Analysis

Pour éviter l'**overfitting**, l'optimisation utilise un Walk-Forward:

```
Période 1: ████████░░░░  60% train → 40% test
Période 2:    ████████░░░░  60% train → 40% test
Période 3:       ████████░░░░  60% train → 40% test
...
```

Le **score final** est la **médiane** des performances sur tous les folds de test.

## 🎓 Comprendre les résultats

### Métriques importantes

- **Score**: Ratio Equity finale / Buy&Hold (> 1.0 = on bat le B&H)
- **CAGR**: Rendement annualisé composé
- **Max Drawdown**: Perte maximale depuis le sommet
- **Sharpe Ratio**: Rendement ajusté au risque (> 1.0 = bon)
- **Trades/an**: Fréquence de trading (10-50 = raisonnable)

### ⚠️ Attention à l'overfitting !

Si les meilleurs paramètres donnent:
- ✅ Performance stable sur tous les folds → BON
- ❌ Performance folle sur un fold, nulle sur les autres → OVERFITTING

**Toujours vérifier** que les paramètres ont du **sens économique**:
- Acheter en FEAR + prix bas = ✅ logique
- Vendre en GREED + prix haut = ✅ logique
- Paramètres bizarres (ex: acheter à 99 FNG) = ❌ suspect

## 🔧 Personnalisation

### Modifier l'espace de recherche

Éditez `run_optimization.py` ligne 47:

```python
search_space = {
    "fng_buy_threshold": [10, 15, 20, 25, 30],  # Vos valeurs
    "fng_sell_threshold": [70, 75, 80, 85, 90],
    "rainbow_buy_threshold": [0.2, 0.3, 0.4],
    "rainbow_sell_threshold": [0.6, 0.7, 0.8],
    "min_position_change_pct": [5.0, 10.0, 15.0],
}
```

### Modifier les frais de transaction

Ligne 79:
```python
fees_bps = 10.0  # 10 basis points = 0.1%
```

### Modifier le Walk-Forward

Lignes 81-83:
```python
wf_n_folds = 5          # Nombre de périodes
wf_train_ratio = 0.6    # 60% train, 40% test
```

## 📚 Exemple d'utilisation en code

```python
from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.strategy import StrategyConfig, build_signals
from src.fngbt.backtest import run_backtest

# Chargement des données
fng = load_fng_alt()
btc = load_btc_prices()
df = merge_daily(fng, btc)

# Configuration
cfg = StrategyConfig(
    fng_buy_threshold=25,
    fng_sell_threshold=75,
    rainbow_buy_threshold=0.3,
    rainbow_sell_threshold=0.7,
    min_position_change_pct=10.0
)

# Génération des signaux
signals = build_signals(df, cfg)

# Backtest
result = run_backtest(signals, fees_bps=10.0)
print(result["metrics"])
```

## 🐛 Debug / Problèmes

### "ModuleNotFoundError: No module named 'yfinance'"

```bash
# Essayez d'installer sans build isolation
pip install --no-build-isolation yfinance

# Ou utilisez des données locales
```

### "ValueError: Pas assez de données"

Il faut au moins 100 jours de données. Vérifiez que:
- Le FNG API est accessible
- Les dates correspondent

### Les résultats sont bizarres

1. Vérifiez que la logique est correcte avec `python3 test_strategy.py`
2. Regardez les colonnes `fng_buy_score` et `rainbow_buy_score` dans le backtest
3. Vérifiez que `execute_next_day=True` (évite look-ahead bias)

## 💡 Conseils

1. **Commencez petit**: testez d'abord avec la config par défaut
2. **Visualisez**: ajoutez des graphiques pour comprendre les signaux
3. **Soyez sceptique**: si c'est trop beau, c'est suspect
4. **Testez live**: paper trading avant de risquer de l'argent réel
5. **Diversifiez**: ne mettez JAMAIS tous vos œufs dans un panier

## 📄 Licence

Code libre, utilisez à vos risques et périls. Pas de conseil en investissement !

---

**Note**: Ce code est à des fins éducatives. Le trading de cryptomonnaies est risqué. Faites vos propres recherches (DYOR).
