from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Asset
from app.services import prices
from app.services.history import build_history
from app.services.ledger import to_trade

router = APIRouter(tags=["history"])

CENT = Decimal("0.01")


class HistoryPointOut(BaseModel):
    date: date
    total_cost: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal


@router.get("/portfolio/history", response_model=list[HistoryPointOut])
def portfolio_history(
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
):
    trades = {
        a.ticker: [to_trade(t) for t in a.transactions]
        for a in db.scalars(select(Asset))
        if a.transactions
    }
    if not trades:
        return []

    first = min(t.date for ts in trades.values() for t in ts)
    start = date_from or first
    end = date_to or date.today()
    if start > end:
        raise HTTPException(status_code=422, detail="date_from es posterior a date_to")

    closes = {tk: prices.get_history(tk, first, end) for tk in trades}
    points = build_history(trades, closes, start, end)
    return [
        HistoryPointOut(
            date=p.date,
            total_cost=p.total_cost.quantize(CENT),
            market_value=p.market_value.quantize(CENT),
            unrealized_pnl=p.unrealized_pnl.quantize(CENT),
            realized_pnl=p.realized_pnl.quantize(CENT),
        )
        for p in points
    ]
