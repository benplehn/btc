from typing import Literal

import pandas as pd
import requests
import yfinance as yf

def load_fng_alt() -> pd.DataFrame:
    """Alternative.me Fear & Greed — timestamps UNIX (secs) -> daily date (naïf)."""
    r = requests.get("https://api.alternative.me/fng/", params={"limit": 0, "format": "json"}, timeout=30)
    r.raise_for_status()
    js = r.json()["data"]
    df = pd.DataFrame(js)
    dt = pd.to_datetime(df["timestamp"].astype("int64"), unit="s", utc=True).dt.normalize().dt.tz_localize(None)
    out = pd.DataFrame({"date": dt, "fng": pd.to_numeric(df["value"], errors="coerce")})
    return out.dropna().drop_duplicates("date").sort_values("date").reset_index(drop=True)

def _fetch_yfinance_history(start_dt: pd.Timestamp, end_dt: pd.Timestamp) -> pd.DataFrame:
    """Charge l'historique BTC-USD (quotidien) via Yahoo Finance.

    `yfinance` retourne un index DatetimeIndex ; on normalise en dates naïves.
    L'API accepte un paramètre `end` exclusif, d'où le +1 jour pour inclure la
    date de fin demandée.
    """

    df = yf.download(
        "BTC-USD",
        start=start_dt,
        end=end_dt + pd.Timedelta(days=1),
        interval="1d",
        auto_adjust=False,
        progress=False,
    )
    if df.empty:
        raise RuntimeError("Aucune donnée renvoyée par Yahoo Finance.")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    out = (
        df.reset_index()
        .rename(columns={"Date": "date", "Close": "close"})
        .loc[:, ["date", "close"]]
    )
    out["date"] = pd.to_datetime(out["date"], utc=True, errors="coerce").dt.tz_localize(None)
    out["close"] = pd.to_numeric(out["close"], errors="coerce")
    out = out.dropna(subset=["date", "close"]).drop_duplicates("date")
    return out.sort_values("date").reset_index(drop=True)


def load_btc_prices(
    start=None,
    end=None,
) -> pd.DataFrame:
    """
    BTC-USD daily close fetched from Yahoo Finance.

    Parameters
    ----------
    start, end : str | datetime-like
        Intervalle de dates (inclus, en timezone naïve).
    """

    start_dt = pd.to_datetime(start or "2013-01-01")
    end_dt = pd.to_datetime(end) if end is not None else pd.Timestamp.utcnow().normalize()

    today_plus_one = pd.Timestamp.utcnow().normalize() + pd.Timedelta(days=1)
    end_dt = min(end_dt, today_plus_one)

    df = _fetch_yfinance_history(start_dt, end_dt)
    mask = (df["date"] >= start_dt.tz_localize(None)) & (df["date"] <= end_dt.tz_localize(None))
    df = df.loc[mask].reset_index(drop=True)
    if df.empty:
        raise RuntimeError("Yahoo Finance n'a pas renvoyé d'historique sur l'intervalle demandé.")
    return df

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
