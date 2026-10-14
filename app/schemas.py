from datetime import date as date_
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.portfolio import TxType


class TransactionBase(BaseModel):
    type: TxType
    date: date_
    quantity: Decimal = Field(gt=0)
    price: Decimal = Field(gt=0)
    fee: Decimal = Field(default=Decimal("0"), ge=0)
    notes: str | None = Field(default=None, max_length=255)

    @field_validator("date")
    @classmethod
    def not_future(cls, v: date_) -> date_:
        if v > date_.today():
            raise ValueError("La fecha no puede ser futura")
        return v


class TransactionCreate(TransactionBase):
    ticker: str = Field(min_length=1, max_length=20)

    @field_validator("ticker")
    @classmethod
    def upper(cls, v: str) -> str:
        return v.strip().upper()


class TransactionUpdate(TransactionBase):
    """Reemplazo completo; el ticker no se puede cambiar."""


class TransactionOut(TransactionBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ticker: str


class PositionOut(BaseModel):
    ticker: str
    quantity: Decimal
    avg_cost: Decimal
    total_cost: Decimal
    realized_pnl: Decimal
    current_price: Decimal | None = None
    market_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    unrealized_pnl_pct: Decimal | None = None


class PortfolioSummary(BaseModel):
    total_cost: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    tickers_without_price: list[str]
