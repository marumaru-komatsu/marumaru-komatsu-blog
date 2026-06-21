"""finance.py — 取崩額・税グロスアップ・資産構成（純粋関数）。

計算式は SPEC.md 第5章のとおり。UI からはこの層を呼ぶだけにする。
すべて実質（インフレ調整後・今日の円）ベース、単位は万円。
入力範囲は明示的に検証する（SPEC 第7章「比率範囲外を明確に扱う」）。
"""
from __future__ import annotations

from . import engine

CAPITAL_GAINS_TAX = 0.20315  # 譲渡益課税（所得税15.315% + 住民税5%）

# 検証ヘルパは正典（swr_simulator）由来のものを engine 経由で再利用し、層ごとの重複実装を避ける。
_check_nonneg = engine._check_nonneg
_check_unit = engine._check_unit
_check_pos = engine._check_pos
_check_finite = engine._check_finite
_as_pos_int = engine._as_pos_int


def annual_withdrawal(monthly_living: float, monthly_side_income: float) -> float:
    """年間取崩額（税抜き） = (月生活費 - 月事業所得) * 12  [万円/年]。

    月額はいずれも非負。事業所得 >= 生活費 のとき取崩は不要なので 0 を返す
    （SPEC 第6章エッジ「取崩0以下→0扱い」。負値は返さない）。
    """
    _check_finite("monthly_living", monthly_living)
    _check_finite("monthly_side_income", monthly_side_income)
    _check_nonneg("monthly_living", monthly_living)
    _check_nonneg("monthly_side_income", monthly_side_income)
    net = (monthly_living - monthly_side_income) * 12.0
    return max(0.0, net)


def tax_grossed_withdrawal(net: float, taxable: float = 1500.0,
                           gain: float = 0.5, years: int = 30) -> float:
    """税グロスアップ後の実効取崩額（税込）[万円/年]。SPEC 5.2 の簡易ブレンド法。

    特定口座を年取崩で割って課税フェーズ比率を出し、上乗せ率をブレンドする。
    厳密な申告計算ではない（UI に明示）。net<=0 ならゼロ除算せず 0 を返す。
    既定（net=156, taxable=1500, gain=0.5, years=30）で gross ≈ 161.7。
    """
    _check_finite("net", net)
    _check_finite("taxable", taxable)
    _check_nonneg("taxable", taxable)
    _check_unit("gain", gain)
    years = _as_pos_int("years", years)
    if net < 0:
        raise ValueError(f"net must be >= 0, got {net!r}")
    if net == 0:
        return 0.0
    years_taxable = taxable / net
    taxable_phase_frac = min(years_taxable / years, 1.0)
    per_year_uplift = 1.0 / (1.0 - gain * CAPITAL_GAINS_TAX) - 1.0
    blended_uplift = taxable_phase_frac * per_year_uplift
    return net * (1.0 + blended_uplift)


def portfolio_weights(nisa: float = 1800.0, taxable: float = 1500.0,
                      cash: float = 825.0) -> tuple[float, float]:
    """残高 -> (株式比率, 防御資産比率)。SPEC 5.3。

    各残高は非負（負残高は異常入力として ValueError。黙って 0 扱いしない）。
    総額0のときは (0, 0) を返す（ゼロ除算回避）。これは「比率未定義」のセンチネルであり、
    比率の和は1にならない。呼び出し側は total>0 を確認してから感度計算へ渡すこと
    （防御比率0 を株式100% と誤解させないため。レビュー再対応 #3）。
    """
    _check_finite("nisa", nisa)
    _check_finite("taxable", taxable)
    _check_finite("cash", cash)
    _check_nonneg("nisa", nisa)
    _check_nonneg("taxable", taxable)
    _check_nonneg("cash", cash)
    stock_balance = nisa + taxable
    defensive_balance = cash
    total = stock_balance + defensive_balance
    if total <= 0:
        return (0.0, 0.0)
    return (stock_balance / total, defensive_balance / total)
