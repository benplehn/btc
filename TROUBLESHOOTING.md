# 🔧 Guide de dépannage

## Erreur: "Pas assez de données pour walk-forward"

### Symptômes
```
ValueError: Pas assez de données pour walk-forward
```

### Diagnostic

**Étape 1**: Lancez le script de diagnostic
```bash
python3 debug_data.py
```

Ce script va vérifier:
- ✅ Les imports nécessaires
- ✅ Le chargement du Fear & Greed Index
- ✅ Le chargement du prix Bitcoin
- ✅ La fusion des données
- ✅ Si assez de données pour walk-forward

### Causes possibles

#### 1. Problème avec yfinance

**Symptôme**: `ModuleNotFoundError: No module named 'yfinance'`

**Solution**:
```bash
# Méthode 1: Installation normale
pip install yfinance

# Méthode 2: Si échec, sans build isolation
pip install --no-build-isolation yfinance

# Méthode 3: Version spécifique
pip install yfinance==0.2.32
```

**Alternative**: Si yfinance ne fonctionne pas, utilisez des données locales (voir section ci-dessous).

#### 2. Pas assez de jours de données

**Symptôme**: `100 jours disponibles, besoin de 250 minimum`

**Causes**:
- API temporairement indisponible
- Données récentes seulement
- Problème de connexion Internet

**Solutions**:

1. **Réessayez plus tard** (parfois les APIs sont temporairement down)

2. **Utilisez moins de folds** (éditer `run_optimization.py`):
```python
wf_n_folds = 2  # Au lieu de 5
```

3. **Désactivez le walk-forward temporairement**:
```python
use_walk_forward = False
```

4. **Utilisez le mode "Test rapide"** (option 3 dans le menu)

#### 3. Problème de connexion Internet

**Test**:
```bash
# Test API Fear & Greed
curl "https://api.alternative.me/fng/?limit=1"

# Devrait retourner du JSON
```

**Solution**: Vérifiez votre connexion et proxy

### Solutions de contournement

#### Option A: Utiliser des données synthétiques (pour tester)

```bash
python3 test_strategy.py
```

Cela teste la stratégie avec 1000 jours de données simulées.

#### Option B: Charger des données locales

Si vous avez des données CSV:

1. Créez un fichier `data/fng.csv`:
```csv
date,fng
2024-01-01,45
2024-01-02,47
...
```

2. Créez un fichier `data/btc.csv`:
```csv
date,close
2024-01-01,45000
2024-01-02,46000
...
```

3. Modifiez `run_optimization.py` pour charger depuis CSV:
```python
# Remplacer:
fng_df = load_fng_alt()
btc_df = load_btc_prices()

# Par:
fng_df = pd.read_csv('data/fng.csv', parse_dates=['date'])
btc_df = pd.read_csv('data/btc.csv', parse_dates=['date'])
```

#### Option C: Réduire les exigences

Éditez `src/fngbt/optimize.py` ligne 122:
```python
# Avant
min_days_needed = n_folds * 50  # Au moins 50 jours par fold

# Après (plus permissif)
min_days_needed = n_folds * 30  # Au moins 30 jours par fold
```

### Vérifications

Après avoir appliqué une solution, vérifiez:

```bash
# 1. Diagnostic
python3 debug_data.py

# 2. Si OK, lancez l'optimisation
python3 run_optimization.py
```

### Besoin d'aide ?

1. Copiez la sortie complète de `debug_data.py`
2. Incluez le message d'erreur complet
3. Précisez votre système (Mac, Linux, Windows)
4. Ouvrez une issue sur GitHub

## Autres problèmes courants

### "ModuleNotFoundError: No module named 'pandas'"

```bash
pip install pandas numpy requests optuna matplotlib
```

### "KeyError: 'date'"

Vérifiez que vos données ont bien une colonne 'date' au format datetime.

### Optimisation très lente

**Normal**: Grid Search avec 5,184 combinaisons peut prendre du temps.

**Solutions**:
1. Utilisez **Optuna** (option 2) au lieu de Grid Search
2. Réduisez l'espace de recherche
3. Utilisez moins de trials (50-100 au lieu de 200)

### Résultats bizarres (stratégie ne bat jamais B&H)

**Vérifications**:
1. Exécutez `python3 test_strategy.py` - les métriques doivent être cohérentes
2. Vérifiez que `execute_next_day=True` (évite look-ahead bias)
3. Sur données synthétiques, c'est normal de ne pas battre B&H
4. Sur vraies données BTC avec cycles, les résultats seront différents

### Pas de graphiques

Les graphiques nécessitent matplotlib:
```bash
pip install matplotlib
```

## Données minimales requises

| Nombre de folds | Jours minimum | Recommandé |
|-----------------|---------------|------------|
| 2 folds | 100 jours | 150 jours |
| 3 folds | 150 jours | 250 jours |
| 4 folds | 200 jours | 350 jours |
| 5 folds | 250 jours | 500 jours |

**Note**: Plus vous avez de données, plus les résultats sont fiables !
