"""Precios con caché en memoria. Fuente: yfinance (no oficial)."""
import time
from datetime import date, timedelta
from decimal import Decimal

TTL_SECONDS = 600
HISTORY_TTL_SECONDS = 3600
_cache: dict[str, tuple[Decimal, float]] = {}
_history_cache: dict[tuple[str, date, date], tuple[dict[date, Decimal], float]] = {}


def get_price(ticker: str) -> Decimal | None:
    cached = _cache.get(ticker)
    if cached and time.time() - cached[1] < TTL_SECONDS:
        return cached[0]
    try:
        import yfinance as yf

        raw = yf.Ticker(ticker).fast_info["last_price"]
        price = Decimal(str(raw))
        _cache[ticker] = (price, time.time())
        return price
    except Exception:
        # Si falla la fuente, devolvemos el último valor conocido (si hay).
        return cached[0] if cached else None


def get_history(ticker: str, start: date, end: date) -> dict[date, Decimal]:
    """Cierres diarios (sin ajustar por dividendos) entre start y end."""
    key = (ticker, start, end)
    cached = _history_cache.get(key)
    if cached and time.time() - cached[1] < HISTORY_TTL_SECONDS:
        return cached[0]
    try:
        import yfinance as yf

        df = yf.Ticker(ticker).history(
            start=start.isoformat(),
            end=(end + timedelta(days=1)).isoformat(),
            auto_adjust=False,
        )
        closes = {
            idx.date(): Decimal(str(value))
            for idx, value in df["Close"].dropna().items()
        }
        _history_cache[key] = (closes, time.time())
        return closes
    except Exception:
        return cached[0] if cached else {}
