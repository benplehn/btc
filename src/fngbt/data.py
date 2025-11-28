import pandas as pd, requests, yfinance as yf
from typing import Literal, Tuple

def load_fng_alt() -> pd.DataFrame:
    """Alternative.me Fear & Greed — timestamps UNIX (secs) -> daily date (naïf)."""
    r = requests.get("https://api.alternative.me/fng/", params={"limit": 0, "format": "json"}, timeout=30)
    r.raise_for_status()
    js = r.json()["data"]
    df = pd.DataFrame(js)
    dt = pd.to_datetime(df["timestamp"].astype("int64"), unit="s", utc=True).dt.normalize().dt.tz_localize(None)
    out = pd.DataFrame({"date": dt, "fng": pd.to_numeric(df["value"], errors="coerce")})
    return out.dropna().drop_duplicates("date").sort_values("date").reset_index(drop=True)

def load_btc_prices(start="2018-01-01", end=None) -> pd.DataFrame:
    """BTC-USD daily close (naïf date), robuste aux MultiIndex et suffixes."""
    px = yf.download("BTC-USD", start=start, end=end, interval="1d", progress=False, auto_adjust=False, group_by="column")
    if px.empty: raise RuntimeError("yfinance BTC-USD vide.")
    # pick close robustly
    if isinstance(px.columns, pd.MultiIndex):
        lvl0 = px.columns.get_level_values(0)
        cand = "Adj Close" if "Adj Close" in lvl0 else ("Close" if "Close" in lvl0 else next(c for c in set(lvl0) if "close" in str(c).lower()))
        s = px[cand]; 
        if isinstance(s, pd.DataFrame): s = s["BTC-USD"] if "BTC-USD" in s.columns else s.iloc[:,0]
    else:
        cols = list(px.columns)
        cand = "Adj Close" if "Adj Close" in cols else ("Close" if "Close" in cols else next(c for c in cols if "close" in str(c).lower()))
        s = px[cand]
    df = s.to_frame("close").reset_index()
    date_col = "Date" if "Date" in df.columns else df.columns[0]
    d = pd.to_datetime(df[date_col], utc=True, errors="coerce").dt.normalize().dt.tz_localize(None)
    out = pd.DataFrame({"date": d, "close": pd.to_numeric(df["close"], errors="coerce")})
    return out.dropna().drop_duplicates("date").sort_values("date").reset_index(drop=True)

def merge_daily(fng: pd.DataFrame, px: pd.DataFrame) -> pd.DataFrame:
    df = pd.merge(fng, px, on="date", how="inner").sort_values("date").reset_index(drop=True)
    return df

def to_weekly(df: pd.DataFrame, how: Literal["last","mean"]="last") -> pd.DataFrame:
    """Option hebdo : FNG agrégé et prix close de fin de semaine (ou moyenne)."""
    g = df.set_index("date").resample("W-FRI")
    f = g["fng"].mean() if how=="mean" else g["fng"].last()
    c = g["close"].last()
    out = pd.DataFrame({"date": f.index, "fng": f.values, "close": c.values}).dropna().reset_index(drop=True)
    return out
