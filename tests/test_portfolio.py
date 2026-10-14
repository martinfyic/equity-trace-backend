from datetime import date
from decimal import Decimal as D

import pytest

from app.services.portfolio import (
    InsufficientQuantityError,
    Trade,
    TxType,
    compute_position,
    value_position,
)

BUY, SELL = TxType.BUY, TxType.SELL

MSFT_1 = Trade(date(2025, 9, 26), BUY, D("0.036566"), D("508.94"), D("1.39"))
MSFT_2 = Trade(date(2025, 10, 9), BUY, D("0.094106"), D("719.72"), D("2.35"))


def test_dos_compras_msft():
    pos = compute_position([MSFT_1, MSFT_2])
    expected_cost = (
        D("0.036566") * D("508.94") + D("1.39")
        + D("0.094106") * D("719.72") + D("2.35")
    )
    assert pos.quantity == D("0.130672")
    assert pos.total_cost == expected_cost
    assert pos.total_cost.quantize(D("0.01")) == D("90.08")
    assert pos.avg_cost.quantize(D("0.01")) == D("689.36")
    assert pos.realized_pnl == 0


def test_valuacion_no_realizada():
    pos = compute_position([MSFT_1, MSFT_2])
    val = value_position(pos, D("700"))
    assert val.market_value == D("0.130672") * D("700")
    assert val.unrealized_pnl == val.market_value - pos.total_cost


def test_venta_parcial_realiza_ganancia_y_mantiene_costo_promedio():
    avg_before = compute_position([MSFT_1, MSFT_2]).avg_cost
    sell = Trade(date(2025, 11, 1), SELL, D("0.03"), D("750"), D("0.50"))
    pos = compute_position([MSFT_1, MSFT_2, sell])

    assert pos.quantity == D("0.100672")
    assert pos.avg_cost.quantize(D("0.0001")) == avg_before.quantize(D("0.0001"))
    expected = (D("0.03") * D("750") - D("0.50")) - D("0.03") * avg_before
    assert abs(pos.realized_pnl - expected) < D("0.0000001")


def test_venta_total_deja_posicion_en_cero():
    sell = Trade(date(2025, 11, 1), SELL, D("0.130672"), D("700"))
    pos = compute_position([MSFT_1, MSFT_2, sell])
    assert pos.quantity == 0
    assert pos.total_cost == 0
    assert pos.avg_cost == 0


def test_no_se_puede_vender_mas_de_lo_que_se_tiene():
    sell = Trade(date(2025, 11, 1), SELL, D("1"), D("700"))
    with pytest.raises(InsufficientQuantityError):
        compute_position([MSFT_1, MSFT_2, sell])


def test_validacion_cronologica():
    # La venta es anterior a la 2ª compra: solo había 0.036566 en ese momento.
    sell = Trade(date(2025, 10, 1), SELL, D("0.05"), D("700"))
    with pytest.raises(InsufficientQuantityError):
        compute_position([MSFT_1, MSFT_2, sell])


def test_misma_fecha_compra_antes_que_venta():
    buy = Trade(date(2025, 10, 9), BUY, D("1"), D("100"))
    sell = Trade(date(2025, 10, 9), SELL, D("1"), D("110"))
    pos = compute_position([sell, buy])  # orden de entrada invertido
    assert pos.quantity == 0
    assert pos.realized_pnl == D("10")
