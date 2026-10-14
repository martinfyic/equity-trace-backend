"""Evolución diaria del portafolio (función pura, sin base ni red)."""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from app.services.portfolio import ZERO, Trade, compute_position


@dataclass(frozen=True)
class HistoryPoint:
    date: date
    total_cost: Decimal       # costo base de lo que se posee ese día
    market_value: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal     # acumulado hasta ese día


def build_history(
    trades_by_ticker: dict[str, list[Trade]],
    closes_by_ticker: dict[str, dict[date, Decimal]],
    start: date,
    end: date,
) -> list[HistoryPoint]:
    """Un punto por día entre start y end (ambos incluidos).

    Precio de cada día: último cierre disponible hasta esa fecha (así fines de
    semana y feriados arrastran el último cierre). Si todavía no hay cierres,
    se usa el precio de la última operación registrada.
    """
    snaps = {}
    for ticker, trades in trades_by_ticker.items():
        ordered = sorted(trades, key=lambda t: t.date)  # estable
        dates = sorted({t.date for t in ordered})
        positions, last_prices = [], []
        for d in dates:
            upto = [t for t in ordered if t.date <= d]
            positions.append(compute_position(upto))
            last_prices.append(upto[-1].price)
        closes = closes_by_ticker.get(ticker, {})
        snaps[ticker] = (dates, positions, last_prices, sorted(closes), closes)

    points: list[HistoryPoint] = []
    day = start
    while day <= end:
        cost = value = realized = ZERO
        for dates, positions, last_prices, close_dates, closes in snaps.values():
            i = bisect_right(dates, day) - 1
            if i < 0:
                continue
            pos = positions[i]
            realized += pos.realized_pnl
            if pos.quantity > 0:
                j = bisect_right(close_dates, day) - 1
                price = closes[close_dates[j]] if j >= 0 else last_prices[i]
                cost += pos.total_cost
                value += pos.quantity * price
        points.append(HistoryPoint(day, cost, value, value - cost, realized))
        day += timedelta(days=1)
    return points
