"""
Backtest avec fees réalistes: 0.1% sur CHAQUE achat et vente

Simule un portefeuille réel avec:
- Capital initial: 100 EUR
- Cash et BTC trackés séparément
- Fees: 0.1% sur le montant de CHAQUE transaction
"""
import pandas as pd
import numpy as np
from .metrics import compute_metrics


def run_backtest_realistic_fees(df: pd.DataFrame,
                                 initial_capital: float = 100.0,
                                 fee_rate: float = 0.001) -> dict:
    """
    Backtest avec fees réalistes sur chaque trade

    Args:
        df: DataFrame avec colonnes 'close', 'pos' (allocation cible en %)
        initial_capital: Capital initial en EUR (défaut: 100)
        fee_rate: Taux de frais par trade (défaut: 0.001 = 0.1%)

    Returns:
        dict avec 'df' (résultats jour par jour) et 'metrics' (métriques)
    """
    d = df.copy()

    # Initialisation
    cash = initial_capital
    btc_amount = 0.0
    portfolio_values = []
    cash_values = []
    btc_values = []
    fees_paid = []
    trades_made = []

    for i in range(len(d)):
        price = d['close'].iloc[i]
        target_allocation = d['pos'].iloc[i] / 100.0  # 0-1

        # Valeur actuelle du portefeuille
        btc_value = btc_amount * price
        portfolio_value = cash + btc_value

        # Allocation actuelle
        if portfolio_value > 0:
            current_allocation = btc_value / portfolio_value
        else:
            current_allocation = 0.0

        # Calculer le rebalancing nécessaire
        target_btc_value = portfolio_value * target_allocation
        current_btc_value = btc_value

        rebalance_amount = target_btc_value - current_btc_value

        # Seuil minimal pour éviter micro-trades (0.01 EUR)
        if abs(rebalance_amount) > 0.01:
            if rebalance_amount > 0:
                # ACHAT de BTC
                amount_to_buy = min(rebalance_amount, cash)  # Ne peut pas acheter plus que cash disponible
                fees = amount_to_buy * fee_rate

                # Exécution de l'achat
                cash -= (amount_to_buy + fees)
                btc_amount += (amount_to_buy - fees) / price  # BTC acheté après fees

                fees_paid.append(fees)
                trades_made.append(1)
            else:
                # VENTE de BTC
                btc_to_sell = min(abs(rebalance_amount) / price, btc_amount)  # Ne peut pas vendre plus que BTC possédé
                proceeds = btc_to_sell * price
                fees = proceeds * fee_rate

                # Exécution de la vente
                btc_amount -= btc_to_sell
                cash += (proceeds - fees)

                fees_paid.append(fees)
                trades_made.append(1)
        else:
            fees_paid.append(0.0)
            trades_made.append(0)

        # Sauvegarder les valeurs
        btc_value_end = btc_amount * price
        portfolio_value_end = cash + btc_value_end

        portfolio_values.append(portfolio_value_end)
        cash_values.append(cash)
        btc_values.append(btc_value_end)

    # Ajouter au DataFrame
    d['portfolio_value'] = portfolio_values
    d['cash'] = cash_values
    d['btc_value'] = btc_values
    d['fees_paid'] = fees_paid
    d['trade'] = trades_made

    # Calculer equity normalisée (multiple du capital initial)
    d['equity'] = d['portfolio_value'] / initial_capital

    # Buy & Hold pour comparaison (100% BTC dès le début)
    initial_btc = initial_capital / d['close'].iloc[0]
    d['bh_equity'] = (initial_btc * d['close']) / initial_capital

    # Calculer rendements pour metrics
    d['ret'] = d['close'].pct_change().fillna(0.0)
    d['strategy_ret'] = d['portfolio_value'].pct_change().fillna(0.0)

    # Métriques
    metrics = compute_metrics(d)
    metrics['trades'] = int(d['trade'].sum())
    metrics['total_fees_paid'] = float(sum(fees_paid))
    metrics['avg_allocation'] = float((d['btc_value'] / d['portfolio_value']).mean() * 100)
    metrics['final_cash'] = float(cash)
    metrics['final_btc'] = float(btc_amount)
    metrics['final_portfolio'] = float(d['portfolio_value'].iloc[-1])

    return {
        'df': d,
        'metrics': metrics
    }
