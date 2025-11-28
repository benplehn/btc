#!/usr/bin/env python3
"""
Dashboard interactif Bitcoin Strategy

Lance un serveur web localhost pour visualiser et optimiser la stratégie

Usage:
    streamlit run app_dashboard.py
    Puis ouvrir: http://localhost:8501
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import sys

# Import des modules
from src.fngbt.data import load_fng_alt, load_btc_prices, merge_daily
from src.fngbt.strategy import StrategyConfig, build_signals
from src.fngbt.backtest import run_backtest
from src.fngbt.optimize import optuna_search, grid_search, default_search_space


# Configuration de la page
st.set_page_config(
    page_title="Bitcoin Strategy Dashboard",
    page_icon="₿",
    layout="wide",
    initial_sidebar_state="expanded"
)


# CSS personnalisé
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        color: #FF9800;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def load_data():
    """Charge les données avec cache"""
    try:
        with st.spinner("Chargement Fear & Greed Index..."):
            fng = load_fng_alt()

        with st.spinner("Chargement prix Bitcoin..."):
            btc = load_btc_prices()

        df = merge_daily(fng, btc)

        return df
    except Exception as e:
        st.error(f"Erreur lors du chargement des données: {e}")
        return None


def plot_interactive_strategy(df, metrics, config):
    """Crée des graphiques interactifs avec Plotly"""

    # Création de 4 sous-graphiques
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=(
            '📈 Prix Bitcoin & Rainbow Chart',
            '😨 Fear & Greed Index',
            '💰 Allocation BTC',
            '📊 Performance: Stratégie vs Buy & Hold'
        ),
        row_heights=[0.3, 0.2, 0.2, 0.3]
    )

    # ========================================================================
    # 1. Prix BTC + Rainbow
    # ========================================================================

    # Prix BTC
    fig.add_trace(
        go.Scatter(
            x=df['date'], y=df['close'],
            name='BTC Price',
            line=dict(color='black', width=2),
            hovertemplate='<b>Prix</b>: $%{y:,.2f}<br><b>Date</b>: %{x}<extra></extra>'
        ),
        row=1, col=1
    )

    # Rainbow bands
    if 'rainbow_min' in df.columns and 'rainbow_max' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df['date'], y=df['rainbow_max'],
                name='Rainbow Max',
                line=dict(width=0),
                showlegend=False,
                hoverinfo='skip'
            ),
            row=1, col=1
        )

        fig.add_trace(
            go.Scatter(
                x=df['date'], y=df['rainbow_min'],
                name='Rainbow Range',
                fill='tonexty',
                fillcolor='rgba(128, 0, 128, 0.2)',
                line=dict(width=0),
                hovertemplate='<b>Rainbow Min</b>: $%{y:,.2f}<extra></extra>'
            ),
            row=1, col=1
        )

        # Ligne médiane
        if 'rainbow_mid' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['date'], y=df['rainbow_mid'],
                    name='Rainbow Mid',
                    line=dict(color='purple', width=1, dash='dash'),
                    opacity=0.5,
                    hovertemplate='<b>Rainbow Mid</b>: $%{y:,.2f}<extra></extra>'
                ),
                row=1, col=1
            )

    # Trades
    if 'trade' in df.columns:
        trades_df = df[df['trade'] == 1]
        if len(trades_df) > 0:
            fig.add_trace(
                go.Scatter(
                    x=trades_df['date'], y=trades_df['close'],
                    mode='markers',
                    name='Trades',
                    marker=dict(color='orange', size=8, symbol='circle'),
                    hovertemplate='<b>Trade</b><br>Prix: $%{y:,.2f}<br>Date: %{x}<extra></extra>'
                ),
                row=1, col=1
            )

    # ========================================================================
    # 2. Fear & Greed
    # ========================================================================

    fig.add_trace(
        go.Scatter(
            x=df['date'], y=df['fng'],
            name='Fear & Greed',
            fill='tozeroy',
            fillcolor='rgba(0, 123, 255, 0.3)',
            line=dict(color='blue', width=2),
            hovertemplate='<b>FNG</b>: %{y:.0f}<br><b>Date</b>: %{x}<extra></extra>'
        ),
        row=2, col=1
    )

    # Seuils
    if 'fng_buy_threshold' in config:
        fig.add_hline(
            y=config['fng_buy_threshold'],
            line=dict(color='green', width=2, dash='dash'),
            annotation_text=f"Buy {config['fng_buy_threshold']}",
            annotation_position="right",
            row=2, col=1
        )

    if 'fng_sell_threshold' in config:
        fig.add_hline(
            y=config['fng_sell_threshold'],
            line=dict(color='red', width=2, dash='dash'),
            annotation_text=f"Sell {config['fng_sell_threshold']}",
            annotation_position="right",
            row=2, col=1
        )

    # ========================================================================
    # 3. Allocation
    # ========================================================================

    fig.add_trace(
        go.Scatter(
            x=df['date'], y=df['pos'],
            name='Allocation BTC',
            fill='tozeroy',
            fillcolor='rgba(0, 200, 0, 0.3)',
            line=dict(color='green', width=2),
            hovertemplate='<b>Allocation</b>: %{y:.1f}%<br><b>Date</b>: %{x}<extra></extra>'
        ),
        row=3, col=1
    )

    # ========================================================================
    # 4. Equity curves
    # ========================================================================

    fig.add_trace(
        go.Scatter(
            x=df['date'], y=df['equity'],
            name='Stratégie',
            line=dict(color='green', width=3),
            hovertemplate='<b>Strategy</b>: %{y:.2f}x<br><b>Date</b>: %{x}<extra></extra>'
        ),
        row=4, col=1
    )

    fig.add_trace(
        go.Scatter(
            x=df['date'], y=df['bh_equity'],
            name='Buy & Hold',
            line=dict(color='gray', width=2),
            opacity=0.7,
            hovertemplate='<b>Buy & Hold</b>: %{y:.2f}x<br><b>Date</b>: %{x}<extra></extra>'
        ),
        row=4, col=1
    )

    # Mise à jour du layout
    fig.update_yaxes(type="log", title_text="Prix (USD)", row=1, col=1)
    fig.update_yaxes(title_text="FNG (0-100)", range=[0, 100], row=2, col=1)
    fig.update_yaxes(title_text="Allocation (%)", range=[0, 105], row=3, col=1)
    fig.update_yaxes(title_text="Equity (x)", row=4, col=1)
    fig.update_xaxes(title_text="Date", row=4, col=1)

    fig.update_layout(
        height=1200,
        hovermode='x unified',
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    return fig


def main():
    """Application principale"""

    # Header
    st.markdown('<p class="main-header">₿ Bitcoin Strategy Dashboard</p>', unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:
        st.image("https://bitcoin.org/img/icons/opengraph.png", width=200)

        st.header("⚙️ Configuration")

        mode = st.radio(
            "Mode",
            ["📊 Backtest Simple", "🔍 Optimisation"],
            index=0
        )

    # Chargement des données
    df = load_data()

    if df is None:
        st.stop()

    st.success(f"✅ {len(df)} jours de données chargées ({df['date'].min().date()} → {df['date'].max().date()})")

    # ========================================================================
    # MODE 1: BACKTEST SIMPLE
    # ========================================================================

    if mode == "📊 Backtest Simple":

        st.header("📊 Backtest avec paramètres personnalisés")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Fear & Greed Index")
            fng_buy = st.slider("FNG Buy Threshold", 0, 50, 25, 5,
                               help="En-dessous de ce seuil = zone d'achat (FEAR)")
            fng_sell = st.slider("FNG Sell Threshold", 50, 100, 75, 5,
                                help="Au-dessus de ce seuil = zone de vente (GREED)")

        with col2:
            st.subheader("Rainbow Chart")
            rainbow_buy = st.slider("Rainbow Buy Threshold", 0.0, 0.5, 0.3, 0.05,
                                   help="Position Rainbow pour acheter (0 = bas, 1 = haut)")
            rainbow_sell = st.slider("Rainbow Sell Threshold", 0.5, 1.0, 0.7, 0.05,
                                    help="Position Rainbow pour vendre")

        col3, col4 = st.columns(2)

        with col3:
            st.subheader("Trading")
            min_change = st.slider("Min Position Change (%)", 0.0, 30.0, 10.0, 5.0,
                                  help="Changement minimum pour trader (évite micro-ajustements)")

        with col4:
            st.subheader("Frais")
            fees_bps = st.number_input("Frais (basis points)", 0.0, 100.0, 10.0, 1.0,
                                      help="10 bps = 0.1% par trade")

        # Bouton de lancement
        if st.button("🚀 Lancer le backtest", type="primary"):

            with st.spinner("Calcul en cours..."):

                # Configuration
                cfg = StrategyConfig(
                    fng_buy_threshold=fng_buy,
                    fng_sell_threshold=fng_sell,
                    rainbow_buy_threshold=rainbow_buy,
                    rainbow_sell_threshold=rainbow_sell,
                    min_position_change_pct=min_change,
                    execute_next_day=True
                )

                # Génération des signaux
                signals = build_signals(df, cfg)

                # Backtest
                result = run_backtest(signals, fees_bps=fees_bps)

                metrics = result['metrics']

                # Affichage des métriques
                st.header("📊 Résultats")

                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.metric(
                        "Equity Finale",
                        f"{metrics['EquityFinal']:.2f}x",
                        delta=f"vs {metrics['BHEquityFinal']:.2f}x B&H"
                    )

                with col2:
                    st.metric(
                        "CAGR",
                        f"{metrics['CAGR']*100:.1f}%",
                        delta=f"{(metrics['CAGR'] - metrics['BHCAGR'])*100:.1f}% vs B&H"
                    )

                with col3:
                    st.metric(
                        "Max Drawdown",
                        f"{metrics['MaxDD']*100:.1f}%",
                        delta=f"{(metrics['MaxDD'] - metrics['BHMaxDD'])*100:.1f}% vs B&H",
                        delta_color="inverse"
                    )

                with col4:
                    st.metric(
                        "Sharpe Ratio",
                        f"{metrics['Sharpe']:.2f}"
                    )

                col5, col6, col7, col8 = st.columns(4)

                with col5:
                    st.metric("Sortino Ratio", f"{metrics['Sortino']:.2f}")

                with col6:
                    st.metric("Calmar Ratio", f"{metrics['Calmar']:.2f}")

                with col7:
                    st.metric("Trades", f"{metrics['trades']}")

                with col8:
                    st.metric("Trades/an", f"{metrics.get('trades_per_year', 0):.1f}")

                # Graphiques interactifs
                st.header("📈 Visualisation")

                fig = plot_interactive_strategy(result['df'], metrics, cfg.to_dict())
                st.plotly_chart(fig, use_container_width=True)

    # ========================================================================
    # MODE 2: OPTIMISATION
    # ========================================================================

    else:  # mode == "🔍 Optimisation"

        st.header("🔍 Optimisation des paramètres")

        st.warning("⚠️ L'optimisation peut prendre plusieurs minutes selon le nombre de trials.")

        col1, col2 = st.columns(2)

        with col1:
            method = st.selectbox("Méthode", ["Optuna (recommandé)", "Grid Search"])
            n_trials = st.number_input("Nombre de trials", 10, 500, 100, 10)

        with col2:
            use_wf = st.checkbox("Walk-Forward CV", value=True,
                                help="Validation temporelle pour éviter l'overfitting")
            n_folds = st.slider("Nombre de folds", 2, 5, 5, 1) if use_wf else 1

        if st.button("🚀 Lancer l'optimisation", type="primary"):

            search_space = default_search_space()

            # Adapter les folds
            n_days = len(df)
            max_folds = n_days // 50
            actual_folds = min(n_folds, max_folds) if use_wf else 1

            st.info(f"Optimisation avec {actual_folds} folds sur {n_days} jours")

            progress_bar = st.progress(0)
            status_text = st.empty()

            def progress_callback(current, total, best_score):
                progress_bar.progress(current / total)
                if best_score:
                    status_text.text(f"Trial {current}/{total} - Best score: {best_score:.3f}")

            with st.spinner("Optimisation en cours..."):

                if method == "Optuna (recommandé)":
                    from src.fngbt.optimize import optuna_search

                    results = optuna_search(
                        df=df,
                        search_space=search_space,
                        n_trials=n_trials,
                        fees_bps=10.0,
                        use_walk_forward=use_wf,
                        wf_n_folds=actual_folds,
                        wf_train_ratio=0.6,
                        min_trades_per_year=0.5,
                        progress_cb=progress_callback
                    )
                else:
                    from src.fngbt.optimize import grid_search

                    results = grid_search(
                        df=df,
                        search_space=search_space,
                        fees_bps=10.0,
                        use_walk_forward=use_wf,
                        wf_n_folds=actual_folds,
                        wf_train_ratio=0.6,
                        min_trades_per_year=0.5,
                        progress_cb=progress_callback
                    )

            if results.empty:
                st.error("❌ Aucun résultat trouvé!")
            else:
                st.success(f"✅ Optimisation terminée! {len(results)} configurations trouvées.")

                # Top 10
                st.header("🏆 Top 10 configurations")

                st.dataframe(
                    results.head(10)[[
                        'fng_buy_threshold', 'fng_sell_threshold',
                        'rainbow_buy_threshold', 'rainbow_sell_threshold',
                        'min_position_change_pct',
                        'score', 'cv_CAGR', 'cv_MaxDD', 'cv_Sharpe', 'cv_trades_per_year'
                    ]].round(3),
                    use_container_width=True
                )

                # Meilleure config
                best = results.iloc[0]

                st.header("🥇 Meilleure configuration")

                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("FNG Buy", f"{best['fng_buy_threshold']:.0f}")
                    st.metric("FNG Sell", f"{best['fng_sell_threshold']:.0f}")

                with col2:
                    st.metric("Rainbow Buy", f"{best['rainbow_buy_threshold']:.2f}")
                    st.metric("Rainbow Sell", f"{best['rainbow_sell_threshold']:.2f}")

                with col3:
                    st.metric("Min Change", f"{best['min_position_change_pct']:.0f}%")
                    st.metric("Score CV", f"{best['score']:.3f}x")

                # Explication de la différence
                st.info("""
                **📊 Score CV vs Full Dataset:**
                - **Score CV** ({:.3f}x): Médiane des performances sur les {} folds (anti-overfitting)
                - **Full Dataset**: Performance sur TOUT l'historique (voir graphique ci-dessous)

                Si grosse différence → Variance entre périodes ou overfitting possible
                """.format(best['score'], actual_folds))

                # Backtest et graphique de la meilleure config
                st.header("📈 Visualisation de la meilleure configuration")

                with st.spinner("Génération du backtest..."):
                    best_cfg = StrategyConfig(
                        fng_buy_threshold=int(best['fng_buy_threshold']),
                        fng_sell_threshold=int(best['fng_sell_threshold']),
                        rainbow_buy_threshold=float(best['rainbow_buy_threshold']),
                        rainbow_sell_threshold=float(best['rainbow_sell_threshold']),
                        max_allocation_pct=int(best.get('max_allocation_pct', 100)),
                        min_allocation_pct=int(best.get('min_allocation_pct', 0)),
                        min_position_change_pct=float(best.get('min_position_change_pct', 10.0)),
                        execute_next_day=bool(best.get('execute_next_day', True)),
                    )

                    signals = build_signals(df, best_cfg)
                    result = run_backtest(signals, fees_bps=10.0)

                    # Métriques du full dataset
                    full_metrics = result['metrics']
                    full_ratio = full_metrics['EquityFinal'] / max(full_metrics['BHEquityFinal'], 1e-12)

                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        st.metric("Equity Finale", f"{full_metrics['EquityFinal']:.2f}x")

                    with col2:
                        st.metric("Ratio vs B&H", f"{full_ratio:.3f}x",
                                 delta=f"{(full_ratio - 1.0)*100:.1f}%")

                    with col3:
                        st.metric("CAGR", f"{full_metrics['CAGR']*100:.1f}%")

                    with col4:
                        st.metric("Max DD", f"{full_metrics['MaxDD']*100:.1f}%")

                    # Graphique interactif
                    fig = plot_interactive_strategy(
                        result['df'],
                        full_metrics,
                        best_cfg.to_dict()
                    )
                    st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    main()
