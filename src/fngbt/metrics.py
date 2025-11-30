import pandas as pd, numpy as np

ANN = 365

def _max_dd(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = equity/peak - 1.0
    return float(dd.min())

def compute_metrics(d: pd.DataFrame, initial_capital: float = 100.0) -> dict:
    eq = d["equity"]; bh = d["bh_equity"]
    n = max(len(d), 1)
    cagr = eq.iloc[-1]**(ANN/n) - 1
    bh_cagr = bh.iloc[-1]**(ANN/n) - 1
    vol = d["strategy_ret"].std()*np.sqrt(ANN)
    bh_vol = d["ret"].std()*np.sqrt(ANN)
    mdd = _max_dd(eq); bh_mdd = _max_dd(bh)
    mean = d["strategy_ret"].mean()*ANN
    sharpe = mean/(vol + 1e-12)
    # Sortino (downside)
    neg = d.loc[d["strategy_ret"]<0,"strategy_ret"]
    dvol = neg.std()*np.sqrt(ANN)
    sortino = mean/(dvol + 1e-12)
    calmar = (cagr)/(abs(mdd)+1e-12)
    return {
        "EquityFinal": float(eq.iloc[-1]),
        "EquityFinalValue": float(eq.iloc[-1] * initial_capital),
        "BHEquityFinal": float(bh.iloc[-1]),
        "BHEquityFinalValue": float(bh.iloc[-1] * initial_capital),
        "CAGR": float(cagr),
        "BHCAGR": float(bh_cagr),
        "Vol": float(vol),
        "BHVol": float(bh_vol),
        "MaxDD": float(mdd),
        "BHMaxDD": float(bh_mdd),
        "Sharpe": float(sharpe),
        "Sortino": float(sortino),
        "Calmar": float(calmar),
        "Days": int(n),
    }
