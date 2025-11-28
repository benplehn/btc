import os
import sys
import itertools
from typing import List

import pandas as pd
import streamlit as st

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from fngbt import (
    StrategyConfig,
    build_signals,
    default_search_space,
    grid_search_full,
    load_btc_prices,
    load_fng_alt,
    merge_daily,
    optuna_search,
    plot_overview,
    run_backtest,
    to_weekly,
)


st.set_page_config(page_title="BTC FNG -> Rainbow sizing", layout="wide")


@st.cache_data(show_spinner=True, ttl=12 * 3600)
def load_data(weekly: bool, lookback_years: float | None):
    fng = load_fng_alt()
    px = load_btc_prices(start=fng["date"].min())
    df = merge_daily(fng, px)
    if weekly:
        df = to_weekly(df, how="last")
    if lookback_years:
        cutoff = df["date"].max() - pd.Timedelta(days=int(lookback_years * 365))
        df = df[df["date"] >= cutoff].reset_index(drop=True)
    if "fng" in df.columns:
        df["ema200_soft"] = df["fng"].ewm(span=200, adjust=False).mean()
    return df


def overview_figure(d: pd.DataFrame, cfg: StrategyConfig):
    import matplotlib.pyplot as plt
    return plot_overview(d, cfg)


def risk_figure(d: pd.DataFrame, cfg: StrategyConfig):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(d["date"], d["pos"] / 100.0, color="#18a957", alpha=0.7, label="Allocation (0-1)")
    ax.set_ylabel("Allocation")
    ax.legend(loc="upper left")
    fig.tight_layout()
    return fig


def _parse_grid(val: str, cast=float) -> List:
    """
    Accepte "1,2,3" ou "start:end:step".
    """
    if ":" in val:
        parts = val.split(":")
        if len(parts) not in (2, 3):
            raise ValueError(f"Format de range invalide: {val}")
        start = cast(parts[0])
        end = cast(parts[1])
        step = cast(parts[2]) if len(parts) == 3 else 1
        return [cast(x) for x in frange(start, end, step)]
    return [cast(x) for x in val.split(",") if str(x).strip() != ""]


def _parse_str_list(val: str) -> list[str]:
    return [x.strip() for x in val.split(",") if x.strip()]


def frange(start, end, step):
    out = []
    x = start
    forward = step > 0
    while (forward and x <= end) or ((not forward) and x >= end):
        out.append(x)
        x = x + step
    return out


def _all_combos_step(min_val: int, max_val: int, step: int, n_levels: int) -> list[list[int]]:
    import itertools

    vals = list(range(min_val, max_val + step, step))
    if len(vals) < n_levels:
        raise ValueError(f"Pas assez de valeurs pour {n_levels} paliers (réduis le pas ou le nombre de paliers)")
    return [list(c) for c in itertools.combinations(vals, n_levels)]


def _parse_int_list(val: str) -> list[int]:
    if not val.strip():
        return []
    return [int(x.strip()) for x in val.split(",") if x.strip()]


def main():
    st.title("BTC : FNG pilote le régime, Rainbow pilote le sizing")
    st.caption("FNG décide si on accumule ou on distribue; le Rainbow module combien on investit selon la distance au ruban bas/haut.")

    with st.sidebar:
        st.header("Données")
        lookback = st.number_input("Lookback (années)", min_value=1.0, max_value=12.0, value=6.0, step=0.5, key="lookback_years")
        weekly = st.checkbox("Mode hebdo (W-FRI)", value=False)
        fees = st.number_input("Frais (bps aller-retour)", min_value=0.0, max_value=100.0, value=10.0, step=1.0, key="fees_bps")
        min_trades = st.number_input("Min trades/an (filtre)", min_value=0.0, max_value=50.0, value=3.0, step=0.5, key="min_trades_filter")
        with st.expander("Principe de la strat"):
            st.markdown(
                """
                - FNG seul décide du **régime** : en-dessous du buy -> on accumule ; au-dessus du sell -> on distribue ; entre les deux = mix.
                - Rainbow détermine le **sizing** : plus on est près du ruban bas, plus l'allocation cible monte ; plus on est près du ruban haut, plus on réduit.
                - La courbure des rampes FNG/Rainbow est paramétrable (exposant).
                """
            )

    df = load_data(weekly=weekly, lookback_years=lookback)

    tab_bt, tab_opt, tab_help = st.tabs(["Backtest rapide", "Optimisation (grid/Optuna)", "Guide paramètres"])

    with tab_bt:
        st.subheader("Backtest d'une configuration")
        st.caption("FNG fixe la direction, Rainbow fixe la taille. Agressivité réglable via les exposants.")
        col_fng, col_rbw = st.columns(2)
        with col_fng:
            st.markdown("**Bloc FNG (régime invest/cash)**")
            use_fng = st.checkbox("Activer FNG", value=True, key="use_fng_bt")
            fng_buys_txt = st.text_input("Seuils achat FNG (ex: 30,20,10)", value="25,15", key="fng_buys_bt")
            fng_sells_txt = st.text_input("Seuils vente FNG (ex: 60,70,80)", value="60,70,80", key="fng_sells_bt")
            fng_buys = _parse_int_list(fng_buys_txt)
            fng_sells = _parse_int_list(fng_sells_txt)
            fng_buy = fng_buys[0] if fng_buys else 25
            fng_sell = fng_sells[0] if fng_sells else 70
            fng_curve = st.number_input("Courbure FNG (exp)", min_value=0.5, max_value=5.0, value=1.2, step=0.1, help=">1 = plus binaire; <1 = plus lisse.")
            fng_sources = [c for c in df.columns if "fng" in c.lower()] or ["fng"]
            fng_source = st.selectbox("Colonne FNG utilisée", fng_sources, index=0)
        with col_rbw:
            st.markdown("**Bloc Rainbow (sizing)**")
            use_rainbow = st.checkbox("Activer Rainbow", value=True, key="use_rainbow_bt")
            rainbow_k = st.number_input("Paramètre k courbe A(x)", min_value=0.5, max_value=5.0, value=1.5, step=0.1)
            max_alloc = st.slider("Allocation max (%)", min_value=20, max_value=100, value=100, step=5)
            ramp_step = st.number_input("Pas de quantification (%)", min_value=1, max_value=25, value=5, step=1, key="ramp_step_bt")
            min_hold_days = st.number_input("Hold minimum (jours)", min_value=0, max_value=60, value=3, step=1, key="hold_bt")
        exec_next = st.checkbox("Exécution J+1", value=True)
        if st.button("Lancer le backtest"):
            cfg = StrategyConfig(
                use_fng=use_fng,
                fng_buy=fng_buy,
                fng_sell=fng_sell,
                fng_buy_levels=fng_buys or None,
                fng_sell_levels=fng_sells or None,
                fng_curve_exp=float(fng_curve),
                fng_source_col=fng_source,
                fng_smoothing_days=1,
                use_rainbow=use_rainbow,
                rainbow_k=float(rainbow_k),
                max_allocation_pct=int(max_alloc),
                ramp_step_pct=int(ramp_step),
                min_hold_days=int(min_hold_days),
                execute_next_day=exec_next,
            )
            with st.spinner("Calcul en cours..."):
                sig = build_signals(df, cfg)
                res = run_backtest(sig, fees_bps=fees)
            st.success("Backtest terminé.")
            cols = st.columns(4)
            metrics = res["metrics"]
            cols[0].metric("CAGR", f"{metrics['CAGR']*100:.2f}%")
            cols[1].metric("Calmar", f"{metrics['Calmar']:.2f}")
            cols[2].metric("Sharpe", f"{metrics['Sharpe']:.2f}")
            cols[3].metric("MaxDD", f"{metrics['MaxDD']*100:.2f}%")
            cols2 = st.columns(4)
            cols2[0].metric("Réallocs", f"{metrics.get('trades',0)}")
            trades_py = metrics.get("trades", 0) / max(metrics.get("Days", 1) / 365.0, 1e-9)
            cols2[1].metric("Réalloc/an", f"{trades_py:.1f}")
            cols2[2].metric("Vol", f"{metrics['Vol']*100:.2f}%")
            cols2[3].metric("Equity finale", f"{metrics['EquityFinal']:.2f}x")
            cols3 = st.columns(2)
            cols3[0].metric("Turnover cumulé", f"{metrics.get('turnover',0):.2f}")
            cols3[1].metric("BH CAGR", f"{metrics.get('BHCAGR',0)*100:.2f}%")

            fig = overview_figure(res["df"], cfg)
            st.pyplot(fig, clear_figure=True)
            fig2 = risk_figure(res["df"], cfg)
            st.pyplot(fig2, clear_figure=True)

    with tab_opt:
        st.subheader("Optimisation (grille exhaustive ou Optuna)")
        st.caption(
            "Score = ratio d'equity finale vs Buy & Hold (médiane des folds). "
            "FNG choisit le régime, Rainbow module la taille."
        )
        st.markdown("**Bloc FNG (opti)** : teste 3 ou 4 paliers achat/vente (fear→buy, greed→sell) et différentes colonnes FNG.")
        col_rbw, col_misc = st.columns(2)
        with col_rbw:
            st.markdown("**Bloc Rainbow (opti)**")
            rainbow_k_grid = st.text_input("Grille k (courbe A(x))", value="1.0,1.5,2.0")
            max_alloc_grid = st.text_input("Grille allocation max (%)", value="80,100", key="max_alloc_grid_opt")
            min_hold_days = st.number_input("Hold minimum (jours) [Opti]", min_value=0, max_value=60, value=3, step=1, key="hold_opt")
        with col_misc:
            st.markdown("**Autres**")
            fng_step_opt = st.number_input("Pas (%) pour paliers FNG", min_value=1, max_value=20, value=5, step=1, key="fng_step_opt")
            fng_levels_txt = st.text_input("Nb de paliers FNG (3 ou 4)", value="3,4")
            fng_source_cols_txt = st.text_input("Colonnes FNG candidates", value="fng,ema200_soft")
            ramp_step_grid = st.text_input("Grille pas de quantification (%)", value="5,10")
            search_mode = st.selectbox("Méthode", ["optuna", "grid"], index=0)
            n_trials = st.number_input("Optuna n_trials", min_value=50, max_value=2000, value=400, step=50, key="optuna_trials")
            cv_mode = st.selectbox("Validation temporelle", ["walkforward", "kfold", "none"], index=0)
            cv_folds = st.number_input("Nombre de folds", min_value=2, max_value=10, value=4, step=1, key="cv_folds")
            cv_warmup = st.number_input("Jours de warmup avant chaque fold", min_value=0, max_value=800, value=160, step=20, key="cv_warmup")

        if st.button("Lancer l'optimisation"):
            progress_bar = st.progress(0.0)
            status = st.empty()
            best_so_far = st.empty()
            try:
                fng_curve_vals = [1.0]
                fng_step = max(1, int(fng_step_opt))
                level_counts = [max(3, int(x)) for x in _parse_grid(fng_levels_txt, int)]
                fng_buy_combos = list(
                    itertools.chain.from_iterable(_all_combos_step(0, 50, fng_step, n) for n in level_counts)
                )
                fng_sell_combos = list(
                    itertools.chain.from_iterable(_all_combos_step(50, 100, fng_step, n) for n in level_counts)
                )
                fng_smooth_vals = [1]
                fng_source_cols = _parse_str_list(fng_source_cols_txt)
                rainbow_k_vals = _parse_grid(rainbow_k_grid, float)
                max_alloc_vals = _parse_grid(max_alloc_grid, int)
                ramp_steps = _parse_grid(ramp_step_grid, int)
            except Exception as e:
                st.error(f"Erreur dans les grilles : {e}")
                return

            space = default_search_space(
                use_fng=True,
                fng_source_cols=fng_source_cols,
                fng_buy_vals=[0],
                fng_sell_vals=[100],
                fng_buy_levels_vals=fng_buy_combos,
                fng_sell_levels_vals=fng_sell_combos,
                fng_curve_exp_vals=fng_curve_vals,
                fng_smoothing_vals=fng_smooth_vals,
                use_rainbow=True,
                rainbow_k_vals=rainbow_k_vals,
                max_allocation_pct_vals=max_alloc_vals,
                ramp_step_pct_vals=ramp_steps,
                min_hold_days_vals=[int(min_hold_days)],
            )

            if search_mode == "grid":
                total = 1
                for v in space.values():
                    total *= len(list(v)) if isinstance(v, (list, tuple)) else 1
                st.info(f"Combinaisons à tester (approx) : {total}")
                if total > 80000:
                    st.warning("Grille très large; ça peut être long.")
                if total == 0:
                    st.error("Aucune combinaison à tester (grille vide).")
                    return
                best_local = {"score": None}
                status.write("Initialisation du grid search...")
                progress_bar.progress(0.0)

                def _cb(done, tot, best_score):
                    if tot:
                        progress_bar.progress(min(1.0, done / tot))
                        status.write(f"Progression grid : {done}/{tot}")
                    if best_score is not None:
                        best_local["score"] = best_score
                        best_so_far.write(f"Meilleur score actuel : {best_score:.3f}")

                res = grid_search_full(
                    df,
                    search_space=space,
                    fees_bps=fees,
                    min_trades_per_year=min_trades,
                    cv_mode=cv_mode,
                    cv_folds=int(cv_folds),
                    cv_warmup_days=int(cv_warmup),
                    progress_cb=_cb,
                )
                progress_bar.progress(1.0)
                if best_local["score"] is not None:
                    best_so_far.write(f"Meilleur score final : {best_local['score']:.3f}")
            else:
                st.info(f"Optuna avec {n_trials} trials sur l'espace défini.")
                status.write("Initialisation Optuna...")
                progress_bar.progress(0.0)

                def _cb(done, tot, best_score):
                    if tot:
                        progress_bar.progress(min(1.0, done / tot))
                        status.write(f"Trials complétés : {done}/{tot}")
                    if best_score is not None:
                        best_so_far.write(f"Meilleur score actuel : {best_score:.3f}")

                res = optuna_search(
                    df,
                    search_space=space,
                    n_trials=int(n_trials),
                    fees_bps=fees,
                    min_trades_per_year=min_trades,
                    cv_mode=cv_mode,
                    cv_folds=int(cv_folds),
                    cv_warmup_days=int(cv_warmup),
                    progress_cb=_cb,
                )
                progress_bar.progress(1.0)

            if res.empty:
                st.warning("Aucune stratégie ne passe le filtre trades/an ou pas assez de données.")
            else:
                st.success("Optimisation terminée.")
                st.dataframe(res.head(20))
                best = res.iloc[0]
                cfg_kwargs = {field: best[field] for field in StrategyConfig.__annotations__ if field in best.index}
                cfg = StrategyConfig(**cfg_kwargs)
                st.write("### Meilleure configuration")
                st.json(cfg.to_dict())

                sig = build_signals(df, cfg)
                final = run_backtest(sig, fees_bps=fees)
                fig = overview_figure(final["df"], cfg)
                st.pyplot(fig, clear_figure=True)
                fig2 = risk_figure(final["df"], cfg)
                st.pyplot(fig2, clear_figure=True)
                st.caption(
                    f"Score combiné (walk-forward + full) : {best.get('score', 0):.3f} | "
                    f"Trades/an (médian) ~ {best.get('med_trades_per_year',0):.2f}"
                )

    with tab_help:
        st.subheader("Guide rapide")
        st.markdown(
            """
            **Logique**
            - FNG < buy -> régime accumulation. FNG > sell -> régime distribution. Entre les deux = mix linéaire (modifiable via l'exposant FNG).
            - Rainbow position (0 = ruban min, 1 = ruban max) convertie en allocation via deux courbes : achat (1 - pos)^exp, vente (1 - pos^exp).
            - Allocation finale = mix(FNG, Rainbow), plafonnée par `allocation max` puis quantifiée par `pas (%)`.

            **Conseils de calibration**
            - Courbe FNG >1 pour limiter les trades en zone neutre, <1 pour une rampe plus progressive.
            - Courbe vente Rainbow élevée pour **attendre** d'être proche du ruban max avant de couper fortement.
            - Courbe achat Rainbow faible pour acheter plus tôt ou élevée pour n'entrer qu'au contact du ruban bas.
            - Cooldown + hold min pour lisser le turnover.
            """
        )


if __name__ == "__main__":
    main()
