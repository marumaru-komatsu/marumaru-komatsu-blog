"""engine.py — 数値エンジンのアプリ向け薄いラッパ（純粋関数・乱数管理）。

数値の正典・端点検証・入力検証はすべて参照エンジン swr_simulator.py に集約されている。
本モジュールはそれを import して再利用し（二重実装を避ける）、アプリ固有の便宜のみ提供する:
  - 防御資産の名前（"cash"/"bond"）→ (geo, vol) のマップ
  - 名前指定の make_gross / success_at ラッパ
  - 既定パラメータ（STOCK_VOL / DEFAULT_NSIMS / DEFAULT_SEED）

import 可能なら swr_simulator を正典として再利用（テスト Part 1/2 と同一 RNG・同一検証）。
無い環境では同等のフォールバックを用いる（その場合も検証ロジックは正典と同じ実装を複製）。

不変条件（SPEC.md 第2章）:
  1. すべて実質ベース。株リターンは幾何平均として入力（算術平均にしない）。
  2. 年次リバランスの1年グロスは各資産グロスの加重算術平均。
  3. 安全取崩率の二分探索は乱数パスを探索前に一度だけ生成して全判定で共通化する。
"""
from __future__ import annotations

import numpy as np

try:
    import swr_simulator as _ref
    _USING_REFERENCE = True
except Exception:  # pragma: no cover - フォールバック
    _ref = None
    _USING_REFERENCE = False

if _USING_REFERENCE:
    # 正典をそのまま再利用（端点検証・整数検証・二分探索はすべて _ref 側の単一実装）
    _gross_matrix = _ref._gross_matrix
    _portfolio_gross = _ref._portfolio_gross
    _success_given_gross = _ref._success_given_gross
    _check_unit = _ref._check_unit
    _check_open_unit = _ref._check_open_unit
    _check_pos = _ref._check_pos
    _check_nonneg = _ref._check_nonneg
    _check_finite = _ref._check_finite
    _check_geo = _ref._check_geo
    _as_pos_int = _ref._as_pos_int
    InfeasibleTargetError = _ref.InfeasibleTargetError
    SWR_LO = _ref.SWR_LO
    SWR_HI = _ref.SWR_HI
    SWR_ITERS = _ref.SWR_ITERS
    swr_from_gross = _ref.swr_from_gross
    safe_withdrawal_rate = _ref.safe_withdrawal_rate
    required_asset = _ref.required_asset
    _raw_make_gross = _ref.make_gross
else:  # pragma: no cover
    # swr_simulator が無い環境向けの最小フォールバック（正典と同一ロジックを複製）
    import math as _math

    SWR_LO, SWR_HI, SWR_ITERS = 0.005, 0.12, 40

    class InfeasibleTargetError(ValueError):
        pass

    def _check_unit(name, val):
        if not (0.0 <= val <= 1.0):
            raise ValueError(f"{name} must be in [0, 1], got {val!r}")

    def _check_open_unit(name, val):
        if not (0.0 < val < 1.0):
            raise ValueError(f"{name} must be in the open interval (0, 1), got {val!r}")

    def _check_pos(name, val):
        if val <= 0:
            raise ValueError(f"{name} must be > 0, got {val!r}")

    def _check_nonneg(name, val):
        if val < 0:
            raise ValueError(f"{name} must be >= 0, got {val!r}")

    def _check_finite(name, val):
        if not _math.isfinite(val):
            raise ValueError(f"{name} must be finite, got {val!r}")

    def _check_geo(name, val):
        _check_finite(name, val)
        if val <= -1.0:
            raise ValueError(f"{name} (geo) must be > -1, got {val!r}")

    def _as_pos_int(name, val):
        if isinstance(val, bool):
            raise ValueError(f"{name} must be a positive integer, got {val!r}")
        if isinstance(val, int):
            iv = val
        elif isinstance(val, float):
            if not _math.isfinite(val) or not val.is_integer():
                raise ValueError(f"{name} must be a positive integer, got {val!r}")
            iv = int(val)
        else:
            raise ValueError(f"{name} must be a positive integer, got {val!r}")
        if iv <= 0:
            raise ValueError(f"{name} must be > 0, got {val!r}")
        return iv

    def _gross_matrix(geo, vol, years, nsims, rng):
        mu_log = np.log(1.0 + geo)
        if vol == 0:
            return np.full((years, nsims), 1.0 + geo)
        return np.exp(rng.normal(mu_log, vol, (years, nsims)))

    def _portfolio_gross(stock_geo, stock_vol, defensive_geo, defensive_vol,
                         defensive_weight, years, nsims, rng):
        w_def = defensive_weight
        sg = _gross_matrix(stock_geo, stock_vol, years, nsims, rng)
        dg = _gross_matrix(defensive_geo, defensive_vol, years, nsims, rng)
        return (1.0 - w_def) * sg + w_def * dg

    def _success_given_gross(rate, gross):
        years, nsims = gross.shape
        port = np.ones(nsims)
        alive = np.ones(nsims, dtype=bool)
        for y in range(years):
            port = port - rate
            alive &= port > 0
            port = np.clip(port, 0, None)
            port = port * gross[y]
        return float(alive.mean())

    def _raw_make_gross(stock_geo, stock_vol, defensive_geo, defensive_vol,
                        defensive_weight, years, nsims, seed):
        _check_geo("stock_geo", stock_geo)
        _check_geo("defensive_geo", defensive_geo)
        _check_finite("stock_vol", stock_vol)
        _check_nonneg("stock_vol", stock_vol)
        _check_finite("defensive_vol", defensive_vol)
        _check_nonneg("defensive_vol", defensive_vol)
        _check_unit("defensive_weight", defensive_weight)
        yrs = _as_pos_int("years", years)
        n = _as_pos_int("nsims", nsims)
        rng = np.random.default_rng(seed)
        return _portfolio_gross(stock_geo, stock_vol, defensive_geo, defensive_vol,
                                defensive_weight, yrs, n, rng)

    def swr_from_gross(gross, target=0.90, lo=SWR_LO, hi=SWR_HI):
        _check_open_unit("target", target)
        _check_finite("lo", lo); _check_finite("hi", hi)
        if not (0.0 <= lo < hi):
            raise ValueError(f"interval must satisfy 0<=lo<hi, got {lo!r},{hi!r}")
        gross = np.asarray(gross)
        if gross.ndim != 2 or gross.shape[0] <= 0 or gross.shape[1] <= 0:
            raise ValueError(f"gross must be 2-D with positive dims, got {gross.shape}")
        if not np.isfinite(gross).all() or (gross <= 0).any():
            raise ValueError("gross must be all finite and positive")
        if _success_given_gross(lo, gross) < target:
            raise InfeasibleTargetError("下端取崩率でも目標成功率に届きません。")
        if _success_given_gross(hi, gross) >= target:
            raise InfeasibleTargetError("真の SWR が探索区間上端を超えます。")
        for _ in range(SWR_ITERS):
            mid = (lo + hi) / 2
            if _success_given_gross(mid, gross) >= target:
                lo = mid
            else:
                hi = mid
        return lo

    def safe_withdrawal_rate(stock_geo, stock_vol, defensive_geo, defensive_vol,
                             defensive_weight, target=0.90, years=30, nsims=60000, seed=2026):
        gross = _raw_make_gross(stock_geo, stock_vol, defensive_geo, defensive_vol,
                                defensive_weight, years, nsims, seed)
        return swr_from_gross(gross, target)

    def required_asset(stock_geo, stock_vol, defensive_geo, defensive_vol, defensive_weight,
                       target=0.90, withdrawal=161.7, years=30, nsims=60000, seed=2026):
        _check_pos("withdrawal", withdrawal)
        swr = safe_withdrawal_rate(stock_geo, stock_vol, defensive_geo, defensive_vol,
                                   defensive_weight, target, years, nsims, seed)
        return swr, withdrawal / swr


# --- 既定パラメータ（SPEC.md 第2章） ---------------------------------------
STOCK_VOL = 0.18
DEFENSIVE = {
    "cash": dict(defensive_geo=-0.02, defensive_vol=0.0),   # 名目0% − インフレ2%
    "bond": dict(defensive_geo=0.025, defensive_vol=0.06),  # 実質 +2.5%
}
DEFAULT_SEED = 2026
DEFAULT_NSIMS = 60000   # SPEC 第2章の本番既定値


def defensive_params(defensive):
    """防御資産の種類名 -> dict(defensive_geo, defensive_vol)。"""
    key = str(defensive).lower()
    if key not in DEFENSIVE:
        raise ValueError(f"defensive must be one of {list(DEFENSIVE)}, got {defensive!r}")
    return DEFENSIVE[key]


def make_gross(stock_geo, defensive="cash", defensive_weight=0.2,
               stock_vol=STOCK_VOL, years=30, nsims=DEFAULT_NSIMS, seed=DEFAULT_SEED):
    """名前指定の防御資産で共通乱数パスを生成（正典 make_gross へ委譲＝検証も委譲）。"""
    dp = defensive_params(defensive)
    return _raw_make_gross(stock_geo, stock_vol, dp["defensive_geo"],
                           dp["defensive_vol"], defensive_weight, years, nsims, seed)


def success_at(rate, stock_geo, defensive="cash", defensive_weight=0.2,
               stock_vol=STOCK_VOL, years=30, nsims=DEFAULT_NSIMS, seed=DEFAULT_SEED):
    """指定取崩率 rate での成功率。共通乱数パスを生成して評価する純粋関数。"""
    _check_finite("rate", rate)
    _check_nonneg("rate", rate)
    gross = make_gross(stock_geo, defensive, defensive_weight, stock_vol,
                       years, nsims, seed)
    return _success_given_gross(rate, gross)
