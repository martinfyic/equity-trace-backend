"""Lógica de cálculo del portafolio (funciones puras, sin base de datos).

Método: costo promedio ponderado. Las comisiones de compra se suman al costo;
las comisiones de venta se restan del ingreso.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

ZERO = Decimal("0")


class TxType(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class PortfolioError(ValueError):
    pass


class InsufficientQuantityError(PortfolioError):
    pass


@dataclass(frozen=True)
class Trade:
    date: date
    type: TxType
    quantity: Decimal
    price: Decimal
    fee: Decimal = ZERO


@dataclass(frozen=True)
class Position:
    quantity: Decimal
    total_cost: Decimal      # costo base de lo que se posee (incluye comisiones)
    avg_cost: Decimal
    realized_pnl: Decimal    # ganancia/pérdida ya realizada por ventas


@dataclass(frozen=True)
class Valuation:
    market_value: Decimal
    unrealized_pnl: Decimal
    unrealized_pnl_pct: Decimal | None


def compute_position(trades: Iterable[Trade]) -> Position:
    """Recorre las operaciones en orden cronológico.

    En la misma fecha, las compras se procesan antes que las ventas.
    Lanza InsufficientQuantityError si alguna venta excede lo que se
    poseía en ese momento.
    """
    ordered = sorted(
        enumerate(trades),
        key=lambda it: (it[1].date, it[1].type is TxType.SELL, it[0]),
    )

    qty = ZERO
    cost = ZERO
    realized = ZERO

    for _, t in ordered:
        if t.type is TxType.BUY:
            qty += t.quantity
            cost += t.quantity * t.price + t.fee
        else:
            if t.quantity > qty:
                raise InsufficientQuantityError(
                    f"Venta de {t.quantity} el {t.date} excede la cantidad "
                    f"disponible ({qty})."
                )
            avg = cost / qty
            cost_removed = avg * t.quantity
            proceeds = t.quantity * t.price - t.fee
            realized += proceeds - cost_removed
            qty -= t.quantity
            cost -= cost_removed
            if qty == 0:
                cost = ZERO

    avg_cost = cost / qty if qty > 0 else ZERO
    return Position(qty, cost, avg_cost, realized)


def value_position(position: Position, current_price: Decimal) -> Valuation:
    market_value = position.quantity * current_price
    unrealized = market_value - position.total_cost
    pct = (
        unrealized / position.total_cost * 100 if position.total_cost > 0 else None
    )
    return Valuation(market_value, unrealized, pct)
