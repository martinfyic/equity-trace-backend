from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Asset, Transaction
from app.schemas import TransactionCreate, TransactionOut, TransactionUpdate
from app.services.ledger import validate_ledger
from app.services.portfolio import PortfolioError, Trade

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _check(asset: Asset, **kwargs) -> None:
    try:
        validate_ledger(asset, **kwargs)
    except PortfolioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("", response_model=TransactionOut, status_code=201)
def create_transaction(payload: TransactionCreate, db: Session = Depends(get_db)):
    asset = db.scalar(select(Asset).where(Asset.ticker == payload.ticker))
    if asset is None:
        asset = Asset(ticker=payload.ticker, name=payload.ticker)
        db.add(asset)
        db.flush()

    try:
        _check(
            asset,
            extra=Trade(payload.date, payload.type, payload.quantity, payload.price, payload.fee),
        )
    except HTTPException:
        db.rollback()  # no dejar un activo vacío si la primera operación es inválida
        raise
    tx = Transaction(asset=asset, **payload.model_dump(exclude={"ticker"}))
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    ticker: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
):
    q = select(Transaction).join(Asset).order_by(Transaction.date, Transaction.id)
    if ticker:
        q = q.where(Asset.ticker == ticker.upper())
    if date_from:
        q = q.where(Transaction.date >= date_from)
    if date_to:
        q = q.where(Transaction.date <= date_to)
    return list(db.scalars(q))


def _get_or_404(db: Session, tx_id: int) -> Transaction:
    tx = db.get(Transaction, tx_id)
    if tx is None:
        raise HTTPException(status_code=404, detail="Operación no encontrada")
    return tx


@router.put("/{tx_id}", response_model=TransactionOut)
def update_transaction(tx_id: int, payload: TransactionUpdate, db: Session = Depends(get_db)):
    tx = _get_or_404(db, tx_id)
    new = Trade(payload.date, payload.type, payload.quantity, payload.price, payload.fee)
    _check(tx.asset, replace={tx.id: new})
    for k, v in payload.model_dump().items():
        setattr(tx, k, v)
    db.commit()
    db.refresh(tx)
    return tx


@router.delete("/{tx_id}", status_code=204)
def delete_transaction(tx_id: int, db: Session = Depends(get_db)):
    tx = _get_or_404(db, tx_id)
    _check(tx.asset, replace={tx.id: None})
    db.delete(tx)
    db.commit()
    return Response(status_code=204)
