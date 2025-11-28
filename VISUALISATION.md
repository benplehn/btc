# 📊 Guide de Visualisation

## 3 façons de visualiser ta stratégie

### 1️⃣ **Automatique** (après optimisation)

Les graphiques s'affichent **automatiquement** après `run_optimization.py` !

```bash
python3 run_optimization.py
```

**Ce que tu verras** :
- 🔥 **2 fenêtres de graphiques** s'ouvrent automatiquement
- 📈 **Graphique 1** : Analyse complète de la meilleure stratégie
  - Prix BTC + Rainbow Chart
  - Fear & Greed Index avec seuils
  - Allocation au fil du temps
  - Equity curves (Stratégie vs Buy&Hold)
  - Métriques encadrées

- 📊 **Graphique 2** : Comparaison Top 10 configs
  - Score par configuration
  - Sharpe Ratio
  - Max Drawdown
  - Trades par an

**Fichiers sauvegardés** :
```
outputs/
├── best_strategy_20251128_153045.png      ← Graphique stratégie
├── optimization_comparison_20251128_153045.png  ← Comparaison configs
├── best_backtest_20251128_153045.csv      ← Données détaillées
└── optimization_results_20251128_153045.csv    ← Tous les résultats
```

---

### 2️⃣ **Dashboard Web Interactif** 🚀 (RECOMMANDÉ)

Interface web complète sur `http://localhost:8501` avec graphiques **INTERACTIFS** Plotly !

#### Lancement

```bash
streamlit run app_dashboard.py
```

Ton navigateur s'ouvre automatiquement sur `http://localhost:8501`

#### Fonctionnalités

**📊 Mode Backtest Simple**
- Sliders pour ajuster les paramètres en temps réel
- Voir l'impact immédiat sur la stratégie
- Graphiques interactifs (zoom, hover, etc.)
- Métriques live

**🔍 Mode Optimisation**
- Lance Optuna ou Grid Search depuis l'interface
- Barre de progression en temps réel
- Visualisation automatique des résultats
- Top 10 configurations triées

#### Avantages

✅ Graphiques **interactifs** (zoom, pan, hover)
✅ Pas besoin de fermer des fenêtres matplotlib
✅ Interface moderne et intuitive
✅ Tout dans le navigateur
✅ Comparaison facile de différents paramètres

---

### 3️⃣ **Script Python personnalisé**

Si tu veux créer tes propres graphiques :

```python
from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.strategy import StrategyConfig, build_signals
from src.fngbt.backtest import run_backtest
from src.fngbt.visualize import plot_strategy_results, show_plots

# Charge les données
fng = load_fng_alt()
btc = load_btc_prices()
df = merge_daily(fng, btc)

# Configure la stratégie
cfg = StrategyConfig(
    fng_buy_threshold=25,
    fng_sell_threshold=75,
    rainbow_buy_threshold=0.3,
    rainbow_sell_threshold=0.7,
    min_position_change_pct=10.0
)

# Backtest
signals = build_signals(df, cfg)
result = run_backtest(signals, fees_bps=10.0)

# Graphiques
fig = plot_strategy_results(
    df=result["df"],
    metrics=result["metrics"],
    config=cfg.to_dict(),
    title="Ma Stratégie Perso"
)

# Afficher
show_plots()
```

---

## 🎨 Ce que tu vois dans les graphiques

### Graphique 1 : Prix BTC + Rainbow

- **Ligne noire épaisse** : Prix BTC (échelle log)
- **Zone violette** : Rainbow Chart (min à max)
- **Ligne violette pointillée** : Rainbow médiane
- **Points orange** : Trades exécutés
- **Encadré** : Toutes les métriques

### Graphique 2 : Fear & Greed Index

- **Zone bleue** : FNG au fil du temps
- **Ligne verte pointillée** : Seuil d'achat
- **Ligne rouge pointillée** : Seuil de vente
- **Zone verte claire** : Extreme Fear (0-25)
- **Zone rouge claire** : Extreme Greed (75-100)

### Graphique 3 : Allocation

- **Zone verte** : % d'allocation BTC
- **Ligne verte** : Allocation effective
- **Ligne pointillée** : Allocation cible (avant filtre)
- **Ligne violette** (axe droit) : Position dans Rainbow (0-100)

### Graphique 4 : Performance

- **Ligne verte épaisse** : Equity stratégie
- **Ligne grise** : Equity Buy & Hold
- **Zone verte** : Périodes de surperformance
- **Zone rouge** : Périodes de sous-performance

---

## 💡 Conseils d'utilisation

### Pour l'analyse rapide

Utilise le **Dashboard Streamlit** :
```bash
streamlit run app_dashboard.py
```

**Pourquoi ?**
- Graphiques interactifs (zoom sur une période)
- Ajuste les paramètres en live
- Pas de fichiers à gérer
- Interface moderne

### Pour l'optimisation

Utilise `run_optimization.py` **puis** ouvre les PNG générés :
```bash
python3 run_optimization.py
# Ensuite ouvre les fichiers dans outputs/
```

**Pourquoi ?**
- Walk-forward robuste
- Sauvegarde automatique
- Graphiques haute résolution (150 dpi)
- Comparaison facile des configs

### Pour l'intégration

Utilise le module `visualize.py` dans ton code :
```python
from src.fngbt.visualize import plot_strategy_results
```

**Pourquoi ?**
- Personnalisation totale
- Intégration dans tes workflows
- Export vers différents formats

---

## 🔧 Dépendances

```bash
# Matplotlib (graphiques automatiques)
pip install matplotlib

# Plotly (dashboard interactif)
pip install plotly

# Streamlit (interface web)
pip install streamlit
```

Ou tout en une fois :
```bash
pip install -r requirements.txt
```

---

## 📱 Capture d'écran du Dashboard

**URL** : `http://localhost:8501`

**Mode Backtest** :
- Sliders pour tous les paramètres
- Bouton "Lancer le backtest"
- 4 graphiques interactifs empilés
- Métriques en cards

**Mode Optimisation** :
- Choix Optuna ou Grid Search
- Configuration Walk-Forward
- Barre de progression live
- Top 10 automatique

---

## ❓ FAQ

### Les graphiques ne s'affichent pas

**Problème** : Fenêtre matplotlib bloquée

**Solution** :
```bash
# Vérifie ton backend matplotlib
python3 -c "import matplotlib; print(matplotlib.get_backend())"

# Si c'est 'agg', change-le
export MPLBACKEND=TkAgg
python3 run_optimization.py
```

### Streamlit ne démarre pas

**Problème** : `ModuleNotFoundError: No module named 'streamlit'`

**Solution** :
```bash
pip install streamlit plotly
streamlit run app_dashboard.py
```

### Je veux sauvegarder un graphique

**Automatique** : Les PNG sont déjà dans `outputs/`

**Manuel** :
```python
from src.fngbt.visualize import save_plot

save_plot(fig, "mon_graphique.png")
```

### Je veux changer les couleurs

Édite `src/fngbt/visualize.py` :
```python
# Ligne ~50
ax1.semilogy(dates, df['close'], 'k-', ...)  # 'k' = noir, change en 'b' = bleu
```

---

## 🎯 Recommandations

| Cas d'usage | Outil recommandé |
|-------------|------------------|
| Exploration rapide | **Dashboard Streamlit** |
| Optimisation sérieuse | **run_optimization.py** |
| Présentation | PNG dans `outputs/` |
| Développement | Module `visualize.py` |
| Comparaison paramètres | **Dashboard Streamlit** |
| Publication résultats | PNG haute résolution |

---

**Happy Trading ! 📈**
