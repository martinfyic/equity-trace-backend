"""tablas iniciales: assets y transactions

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op

from app.models import DecimalType

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
    )
    op.create_index("ix_assets_ticker", "assets", ["ticker"], unique=True)

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("type", sa.Enum("BUY", "SELL", name="txtype"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("quantity", DecimalType(), nullable=False),
        sa.Column("price", DecimalType(), nullable=False),
        sa.Column("fee", DecimalType(), nullable=False),
        sa.Column("notes", sa.String(255), nullable=True),
    )
    op.create_index("ix_transactions_asset_id", "transactions", ["asset_id"])


def downgrade() -> None:
    op.drop_index("ix_transactions_asset_id", table_name="transactions")
    op.drop_table("transactions")
    op.drop_index("ix_assets_ticker", table_name="assets")
    op.drop_table("assets")
    sa.Enum(name="txtype").drop(op.get_bind(), checkfirst=True)
