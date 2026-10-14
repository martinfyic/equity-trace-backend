from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Enum, ForeignKey, Numeric, String, TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.services.portfolio import TxType


class DecimalType(TypeDecorator):
    """Decimal exacto: NUMERIC en PostgreSQL, texto en SQLite (que no tiene
    decimales nativos y los convertiría a float)."""

    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "sqlite":
            return dialect.type_descriptor(String(40))
        return dialect.type_descriptor(Numeric(24, 10))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value) if dialect.name == "sqlite" else value

    def process_result_value(self, value, dialect):
        return None if value is None else Decimal(str(value))


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    currency: Mapped[str] = mapped_column(String(3), default="USD")

    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="asset",
        order_by="(Transaction.date, Transaction.id)",
        cascade="all, delete-orphan",
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    type: Mapped[TxType] = mapped_column(Enum(TxType))
    date: Mapped[date] = mapped_column(Date)
    quantity: Mapped[Decimal] = mapped_column(DecimalType)
    price: Mapped[Decimal] = mapped_column(DecimalType)
    fee: Mapped[Decimal] = mapped_column(DecimalType, default=Decimal("0"))
    notes: Mapped[str | None] = mapped_column(String(255), default=None)

    asset: Mapped[Asset] = relationship(back_populates="transactions")

    @property
    def ticker(self) -> str:
        return self.asset.ticker
