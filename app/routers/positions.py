from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Asset
from app.schemas import PortfolioSummary, PositionOut
from app.services import prices
from app.services.ledger import to_trade
from app.services.portfolio import Position, compute_position, value_position

router = APIRouter(tags=["positions"])

CENT = Decimal("0.01")
FOUR = Decimal("0.0001")


def _build(asset: Asset, pos: Position) -> PositionOut:
    # El redondeo se aplica solo acá, al presentar.
    out = PositionOut(
        ticker=asset.ticker,
        quantity=pos.quantity,
        avg_cost=pos.avg_cost.quantize(FOUR),
        total_cost=pos.total_cost.quantize(CENT),
        realized_pnl=pos.realized_pnl.quantize(CENT),
    )
    price = prices.get_price(asset.ticker) if pos.quantity > 0 else None
    if price is not None:
        val = value_position(pos, price)
        out.current_price = price
        out.market_value = val.market_value.quantize(CENT)
        out.unrealized_pnl = val.unrealized_pnl.quantize(CENT)
        if val.unrealized_pnl_pct is not None:
            out.unrealized_pnl_pct = val.unrealized_pnl_pct.quantize(CENT)
    return out


@router.get("/positions", response_model=list[PositionOut])
def list_positions(include_closed: bool = False, db: Session = Depends(get_db)):
    result = []
    for asset in db.scalars(select(Asset).order_by(Asset.ticker)):
        pos = compute_position(to_trade(t) for t in asset.transactions)
        if pos.quantity == 0 and not include_closed:
            continue
        result.append(_build(asset, pos))
    return result


@router.get("/positions/{ticker}", response_model=PositionOut)
def get_position(ticker: str, db: Session = Depends(get_db)):
    asset = db.scalar(select(Asset).where(Asset.ticker == ticker.upper()))
    if asset is None:
        raise HTTPException(status_code=404, detail="Activo no encontrado")
    pos = compute_position(to_trade(t) for t in asset.transactions)
    return _build(asset, pos)


@router.get("/portfolio/summary", response_model=PortfolioSummary)
def portfolio_summary(db: Session = Depends(get_db)):
    total_cost = market_value = unrealized = realized = Decimal("0")
    missing: list[str] = []
    for asset in db.scalars(select(Asset)):
        pos = compute_position(to_trade(t) for t in asset.transactions)
        realized += pos.realized_pnl
        if pos.quantity == 0:
            continue
        total_cost += pos.total_cost
        price = prices.get_price(asset.ticker)
        if price is None:
            missing.append(asset.ticker)
            continue
        val = value_position(pos, price)
        market_value += val.market_value
        unrealized += val.unrealized_pnl
    return PortfolioSummary(
        total_cost=total_cost.quantize(CENT),
        market_value=market_value.quantize(CENT),
        unrealized_pnl=unrealized.quantize(CENT),
        realized_pnl=realized.quantize(CENT),
        tickers_without_price=missing,
    )
