from pathlib import Path
from typing import Literal

import pandas as pd
import requests

def load_fng_alt() -> pd.DataFrame:
    """Alternative.me Fear & Greed — timestamps UNIX (secs) -> daily date (naïf)."""
    r = requests.get("https://api.alternative.me/fng/", params={"limit": 0, "format": "json"}, timeout=30)
    r.raise_for_status()
    js = r.json()["data"]
    df = pd.DataFrame(js)
    dt = pd.to_datetime(df["timestamp"].astype("int64"), unit="s", utc=True).dt.normalize().dt.tz_localize(None)
    out = pd.DataFrame({"date": dt, "fng": pd.to_numeric(df["value"], errors="coerce")})
    return out.dropna().drop_duplicates("date").sort_values("date").reset_index(drop=True)

def _to_utc_timestamp(dt) -> int:
    ts = pd.to_datetime(dt, utc=True)
    return int(ts.timestamp())


def _load_prices_from_csv(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    if not {"date", "close"}.issubset(df.columns):
        raise ValueError("Le fichier CSV doit contenir les colonnes 'date' et 'close'.")
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce").dt.tz_localize(None)
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    return df.dropna(subset=["date", "close"]).drop_duplicates("date").sort_values("date").reset_index(drop=True)


def load_btc_prices(start=None, end=None, csv_path: str | Path | None = None) -> pd.DataFrame:
    """
    BTC-USD daily close fetched from CoinGecko (no yfinance dependency).

    Parameters
    ----------
    start, end : str | datetime-like
        Intervalle de dates (inclus, en timezone naïve).
    csv_path : str | Path, optional
        Si fourni, charge les prix depuis un CSV local (colonnes `date`, `close`).
    """

    start_dt = pd.to_datetime(start or "2013-01-01")
    end_dt = pd.to_datetime(end) if end is not None else pd.Timestamp.utcnow().normalize() + pd.Timedelta(days=1)

    # CoinGecko ne retourne rien dans le futur → on borne à "demain"
    today_plus_one = pd.Timestamp.utcnow().normalize() + pd.Timedelta(days=1)
    end_dt = min(end_dt, today_plus_one)

    if csv_path is not None:
        df = _load_prices_from_csv(Path(csv_path))
        mask = (df["date"] >= start_dt.tz_localize(None)) & (df["date"] <= end_dt.tz_localize(None))
        df = df.loc[mask].reset_index(drop=True)
        if df.empty:
            raise ValueError("Le CSV local ne couvre pas l'intervalle demandé.")
        return df

    params = {
        "vs_currency": "usd",
        "from": _to_utc_timestamp(start_dt),
        "to": _to_utc_timestamp(end_dt),
    }

    url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart/range"
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    js = resp.json()
    prices = js.get("prices", [])
    if not prices:
        raise RuntimeError("CoinGecko BTC-USD vide ou indisponible.")

    df = pd.DataFrame(prices, columns=["timestamp_ms", "close"])
    df["date"] = pd.to_datetime(df["timestamp_ms"], unit="ms", utc=True).dt.normalize().dt.tz_localize(None)
    out = df[["date", "close"]]
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
