from datetime import date
from decimal import Decimal as D

from app.services.history import build_history
from app.services.portfolio import Trade, TxType

BUY, SELL = TxType.BUY, TxType.SELL
M1 = Trade(date(2025, 9, 26), BUY, D("0.036566"), D("508.94"), D("1.39"))
M2 = Trade(date(2025, 10, 9), BUY, D("0.094106"), D("719.72"), D("2.35"))
CLOSES = {
    "MSFT": {date(2025, 9, 26): D("510"), date(2025, 9, 29): D("520"),
             date(2025, 10, 9): D("700")}
}


def _history(closes=CLOSES, trades=(M1, M2), end=date(2025, 10, 10)):
    return build_history({"MSFT": list(trades)}, closes, date(2025, 9, 26), end)


def test_un_punto_por_dia():
    pts = _history()
    assert len(pts) == 15
    assert pts[0].date == date(2025, 9, 26)
    assert pts[-1].date == date(2025, 10, 10)


def test_primer_dia():
    p = _history()[0]
    assert p.market_value == D("0.036566") * D("510")
    assert p.total_cost == D("0.036566") * D("508.94") + D("1.39")
    assert p.unrealized_pnl == p.market_value - p.total_cost


def test_fin_de_semana_arrastra_ultimo_cierre():
    pts = _history()
    assert pts[1].date == date(2025, 9, 27)  # sábado
    assert pts[1].market_value == pts[0].market_value
    assert pts[3].market_value == D("0.036566") * D("520")  # lunes 29


def test_segunda_compra_se_refleja():
    p = _history()[13]  # 9/10
    assert p.date == date(2025, 10, 9)
    assert p.market_value == D("0.130672") * D("700")
    assert p.total_cost.quantize(D("0.01")) == D("90.08")


def test_sin_cierres_usa_precio_de_la_ultima_operacion():
    p = _history(closes={})[-1]
    # Sin cierres, toda la posición se valúa al último precio operado.
    assert p.market_value == D("0.130672") * D("719.72")


def test_venta_acumula_ganancia_realizada():
    sell = Trade(date(2025, 10, 10), SELL, D("0.130672"), D("700"))
    pts = _history(trades=(M1, M2, sell))
    assert pts[-2].realized_pnl == 0
    assert pts[-1].market_value == 0 and pts[-1].total_cost == 0
    expected = D("0.130672") * D("700") - (
        D("0.036566") * D("508.94") + D("1.39") + D("0.094106") * D("719.72") + D("2.35")
    )
    assert abs(pts[-1].realized_pnl - expected) < D("0.0000001")
