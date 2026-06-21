"""fire_app — FIRE/Side-FIRE 目標資産計算アプリの計算層。

公開インターフェース（tests/test_golden.py Part 3 が呼ぶ。シグネチャ厳守）:
  annual_withdrawal(monthly_living, monthly_side_income) -> float
  tax_grossed_withdrawal(net, taxable=1500, gain=0.5, years=30) -> float
  portfolio_weights(nisa=1800, taxable=1500, cash=825) -> (stock_w, def_w)
  current_success(total=4125, stock_geo=0.05, defensive="cash", defensive_weight=0.2) -> float

数値ロジックは engine/finance/recommend に隔離され、UI は本層を呼ぶだけ。
本アプリは投資助言ではない。結果は確率であって保証ではない。投資は自己責任で。
"""
from __future__ import annotations

from . import engine, finance, recommend
from .finance import annual_withdrawal, portfolio_weights, tax_grossed_withdrawal
from .recommend import (
    cash_to_bond_effect,
    current_success,
    recommend_actions,
    required_asset,
    required_table,
)

__all__ = [
    "annual_withdrawal",
    "tax_grossed_withdrawal",
    "portfolio_weights",
    "current_success",
    "required_asset",
    "required_table",
    "cash_to_bond_effect",
    "recommend_actions",
    "engine",
    "finance",
    "recommend",
]
