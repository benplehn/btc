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

def _load_prices_from_csv(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    if not {"date", "close"}.issubset(df.columns):
        raise ValueError("Le fichier CSV doit contenir les colonnes 'date' et 'close'.")
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce").dt.tz_localize(None)
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    return df.dropna(subset=["date", "close"]).drop_duplicates("date").sort_values("date").reset_index(drop=True)


def _parse_alt_history(payload) -> pd.DataFrame:
    """Convertit la réponse Alternative.me en DataFrame (souple sur la forme).

    L'API n'a pas de schéma unique: v1 renvoie une liste, v2 un dictionnaire.
    On essaie d'extraire `timestamp`/`last_updated` + un prix USD plausible.
    """

    data = payload.get("data") if isinstance(payload, dict) else None
    if not data:
        raise RuntimeError("Réponse Alternative.me vide ou sans champ 'data'.")

    entries: list[dict] = []
    if isinstance(data, list):
        entries = [e for e in data if isinstance(e, dict)]
    elif isinstance(data, dict):
        entries = [e for e in data.values() if isinstance(e, dict)]
    else:
        raise RuntimeError("Format Alternative.me non supporté.")

    rows: list[dict] = []
    for entry in entries:
        ts = entry.get("timestamp") or entry.get("last_updated") or entry.get("date")
        price = None
        quotes = entry.get("quotes") if isinstance(entry, dict) else None
        if isinstance(quotes, dict):
            usd = quotes.get("USD") or quotes.get("usd")
            if isinstance(usd, dict):
                price = usd.get("price") or usd.get("close") or usd.get("value")
            elif usd is not None:
                price = usd
        price = price or entry.get("price_usd") or entry.get("close")

        if ts is None or price is None:
            continue

        date = pd.to_datetime(ts, utc=True, errors="coerce")
        if pd.isna(date):
            date = pd.to_datetime(ts, errors="coerce")
        if pd.isna(date):
            continue

        rows.append(
            {
                "date": date.tz_localize(None).normalize(),
                "close": pd.to_numeric(price, errors="coerce"),
            }
        )

    df = pd.DataFrame(rows).dropna(subset=["date", "close"]).drop_duplicates("date")
    if df.empty:
        raise RuntimeError("Pas de points de prix exploitables dans la réponse Alternative.me.")
    return df.sort_values("date").reset_index(drop=True)


def _fetch_alt_history(start_dt: pd.Timestamp, end_dt: pd.Timestamp) -> pd.DataFrame:
    """Essaie de récupérer l'historique BTC-USD via l'API Alternative.me.

    L'API publique documente surtout les prix courants. Certains déploiements
    exposent toutefois un endpoint `ticker/bitcoin/history/` utilisé ici.
    """

    params = {
        "convert": "USD",
        "start": start_dt.strftime("%Y%m%d"),
        "end": end_dt.strftime("%Y%m%d"),
        "structure": "array",
    }
    url = "https://api.alternative.me/v2/ticker/bitcoin/history/"
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    df = _parse_alt_history(resp.json())

    mask = (df["date"] >= start_dt.tz_localize(None)) & (df["date"] <= end_dt.tz_localize(None))
    return df.loc[mask].reset_index(drop=True)


def load_btc_prices(
    start=None,
    end=None,
    csv_path: str | Path | None = None,
) -> pd.DataFrame:
    """
    BTC-USD daily close fetched from Alternative.me (ou CSV local).

    Parameters
    ----------
    start, end : str | datetime-like
        Intervalle de dates (inclus, en timezone naïve).
    csv_path : str | Path, optional
        Si fourni, charge les prix depuis un CSV local (colonnes `date`, `close`).
    """

    start_dt = pd.to_datetime(start or "2013-01-01")
    end_dt = pd.to_datetime(end) if end is not None else pd.Timestamp.utcnow().normalize() + pd.Timedelta(days=1)

    # L'API peut limiter le futur → on borne à "demain"
    today_plus_one = pd.Timestamp.utcnow().normalize() + pd.Timedelta(days=1)
    end_dt = min(end_dt, today_plus_one)

    if csv_path is not None:
        df = _load_prices_from_csv(Path(csv_path))
        mask = (df["date"] >= start_dt.tz_localize(None)) & (df["date"] <= end_dt.tz_localize(None))
        df = df.loc[mask].reset_index(drop=True)
        if df.empty:
            raise ValueError("Le CSV local ne couvre pas l'intervalle demandé.")
        return df

    df = _fetch_alt_history(start_dt, end_dt)
    if df["date"].min() > start_dt.tz_localize(None) + pd.Timedelta(days=10):
        raise RuntimeError(
            "L'API Alternative.me ne renvoie que des données récentes; fournissez un CSV local pour l'historique complet."
        )
    return df.reset_index(drop=True)

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
