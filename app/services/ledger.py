"""Puente entre filas de la base de datos y el dominio."""
from app.models import Asset, Transaction
from app.services.portfolio import Trade, compute_position


def to_trade(tx: Transaction) -> Trade:
    return Trade(tx.date, tx.type, tx.quantity, tx.price, tx.fee)


def validate_ledger(
    asset: Asset,
    *,
    replace: dict[int, Trade | None] | None = None,
    extra: Trade | None = None,
) -> None:
    """Simula el historial resultante; lanza PortfolioError si es inválido.

    replace: {tx_id: nuevo Trade} para editar, {tx_id: None} para borrar.
    extra: operación nueva a agregar.
    """
    trades: list[Trade] = []
    for tx in asset.transactions:
        if replace and tx.id in replace:
            t = replace[tx.id]
            if t is None:
                continue
        else:
            t = to_trade(tx)
        trades.append(t)
    if extra is not None:
        trades.append(extra)
    compute_position(trades)
