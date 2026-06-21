#!/usr/bin/env python3
"""swr_simulator.py — 目標資産（必要資産額）のモンテカルロ計算ツール（参照エンジン v4）

必要資産額 = 年間取崩額(税込) ÷ 安全取崩率。安全取崩率 = 指定成功率を満たす最大の初年度取崩率。
対数正規・幾何平均アンカー・年次リバランス(加重算術平均)・乱数パス共通化の二分探索。実質ベース。
詳細・前提は同フォルダ SPEC.md を参照。投資は自己責任で。

v4: 端点検証・入力範囲検証を本正典に統合（レビュー再対応 #1/#2）。
  - swr_from_gross() に探索区間の端点検証を追加（目標を満たさない rate を正常値として返さない）。
  - target は開区間 (0,1)、years/nsims は有限な正の整数、各比率/ボラは範囲検証。
  - アルゴリズム（lo=0.005, hi=0.12, 40反復, 期初取崩, 加重算術平均）は従来と同一。
  fire_app.engine はこれらを再利用し、二重実装を避ける。
"""
from __future__ import annotations
import argparse
import math
import numpy as np

# --- 二分探索の固定区間（従来と同一） ---------------------------------------
SWR_LO, SWR_HI = 0.005, 0.12
SWR_ITERS = 40


class InfeasibleTargetError(ValueError):
    """指定の前提では目標成功率を満たす取崩率が探索区間に存在しないことを表す。"""


# --- 入力検証ヘルパ（SPEC 第7章「比率範囲外を明確に扱う」） -------------------
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
    if not math.isfinite(val):
        raise ValueError(f"{name} must be finite, got {val!r}")


def _check_geo(name, val):
    """幾何リターンは有限かつ > -1（log(1+geo) の定義域）。"""
    _check_finite(name, val)
    if val <= -1.0:
        raise ValueError(f"{name} (幾何リターン) must be > -1, got {val!r}")


def _validate_gross(gross):
    """グロス行列を検証して ndarray を返す: 2次元・年数>0・シナリオ>0・全要素 有限かつ正。"""
    a = np.asarray(gross)
    if a.ndim != 2:
        raise ValueError(f"gross must be 2-D (years, nsims), got ndim={a.ndim}")
    yrs, n = a.shape
    if yrs <= 0 or n <= 0:
        raise ValueError(f"gross must have years>0 and nsims>0, got shape={a.shape}")
    if not np.isfinite(a).all():
        raise ValueError("gross must be all finite (NaN/inf を含まないこと)")
    if (a <= 0).any():
        raise ValueError("gross (=1+リターン) must be all positive")
    return a


def _check_interval(lo, hi):
    _check_finite("lo", lo)
    _check_finite("hi", hi)
    if not (0.0 <= lo < hi):
        raise ValueError(f"search interval must satisfy 0 <= lo < hi, got lo={lo!r}, hi={hi!r}")


def _as_pos_int(name, val):
    """有限な正の整数（int、または 30.0 等の整数値 float）を int で返す。

    0.9 や 0.1 のような非整数 float、NaN/inf、0 以下は ValueError（暗黙の切り捨てを禁止）。
    """
    if isinstance(val, bool):
        raise ValueError(f"{name} must be a positive integer, got {val!r}")
    if isinstance(val, int):
        iv = val
    elif isinstance(val, float):
        if not math.isfinite(val) or not val.is_integer():
            raise ValueError(f"{name} must be a positive integer, got {val!r}")
        iv = int(val)
    else:
        raise ValueError(f"{name} must be a positive integer, got {val!r}")
    if iv <= 0:
        raise ValueError(f"{name} must be > 0, got {val!r}")
    return iv


# --- 数値コア（プリミティブ・従来と同一） -----------------------------------
def _gross_matrix(geo, vol, years, nsims, rng):
    mu_log = np.log(1.0 + geo)
    if vol == 0:
        return np.full((years, nsims), 1.0 + geo)
    return np.exp(rng.normal(mu_log, vol, (years, nsims)))


def _portfolio_gross(stock_geo, stock_vol, defensive_geo, defensive_vol,
                     defensive_weight, years, nsims, rng):
    w_def = defensive_weight
    w_stk = 1.0 - w_def
    sg = _gross_matrix(stock_geo, stock_vol, years, nsims, rng)
    dg = _gross_matrix(defensive_geo, defensive_vol, years, nsims, rng)
    return w_stk * sg + w_def * dg  # 加重算術平均（不変条件2）


def _success_given_gross(rate, gross):
    years, nsims = gross.shape
    port = np.ones(nsims)
    alive = np.ones(nsims, dtype=bool)
    for y in range(years):
        port = port - rate          # 期初取崩（保守側）
        alive &= port > 0
        port = np.clip(port, 0, None)
        port = port * gross[y]
    return float(alive.mean())


# --- 乱数行列の生成（入力検証つき・再利用可能） -----------------------------
def make_gross(stock_geo, stock_vol, defensive_geo, defensive_vol,
               defensive_weight, years, nsims, seed):
    """共通乱数パス（年×シナリオのグロス行列）を生成。入力範囲・整数を検証する。"""
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


# --- 二分探索（端点検証つき） ----------------------------------------------
def swr_from_gross(gross, target=0.90, lo=SWR_LO, hi=SWR_HI):
    """生成済みグロス行列上で、target を満たす最大取崩率を二分探索する（端点検証つき）。

    成功率は取崩率に対し単調減少。下端 lo でも target 未満なら解は区間に存在せず
    InfeasibleTargetError。上端 hi で既に target 以上なら真の SWR は hi を超えるため同例外。
    それ以外は従来と同一の 40 反復二分探索で lo 側を返す。
    """
    _check_open_unit("target", target)
    _check_interval(lo, hi)
    gross = _validate_gross(gross)
    if _success_given_gross(lo, gross) < target:
        raise InfeasibleTargetError(
            f"下端取崩率 {lo:.3%} でも成功率が目標 {target:.0%} に届きません"
            "（前提が厳しすぎる／取崩期間が長すぎる等）。")
    if _success_given_gross(hi, gross) >= target:
        raise InfeasibleTargetError(
            f"上端取崩率 {hi:.0%} でも成功率が目標 {target:.0%} 以上です"
            f"（真の SWR が探索区間上端 {hi:.0%} を超える）。")
    for _ in range(SWR_ITERS):
        mid = (lo + hi) / 2
        if _success_given_gross(mid, gross) >= target:
            lo = mid
        else:
            hi = mid
    return lo


def safe_withdrawal_rate(stock_geo, stock_vol, defensive_geo, defensive_vol,
                         defensive_weight, target=0.90, years=30, nsims=60000, seed=2026):
    gross = make_gross(stock_geo, stock_vol, defensive_geo, defensive_vol,
                       defensive_weight, years, nsims, seed)
    return swr_from_gross(gross, target)


def required_asset(stock_geo, stock_vol, defensive_geo, defensive_vol, defensive_weight,
                   target=0.90, withdrawal=161.7, years=30, nsims=60000, seed=2026):
    _check_finite("withdrawal", withdrawal)
    _check_pos("withdrawal", withdrawal)
    swr = safe_withdrawal_rate(stock_geo, stock_vol, defensive_geo, defensive_vol,
                               defensive_weight, target, years, nsims, seed)
    return swr, withdrawal / swr


def calibrate(nsims=60000, seed=2026):
    print("=== 校正：古典トリニティ（株75/債25, 幾何実質 株7%・債2.5%）===")
    for tgt in (0.95, 0.90, 0.85):
        swr = safe_withdrawal_rate(0.07, 0.18, 0.025, 0.06, 0.25, tgt, 30, nsims, seed)
        print(f"  成功率{tgt*100:.0f}%: SWR {swr*100:.2f}%")
    print()


def main():
    p = argparse.ArgumentParser(description="株:防御資産PFの必要資産額を防御比率0〜40%でスイープ")
    p.add_argument("--withdrawal", type=float, default=161.7)
    p.add_argument("--years", type=int, default=30)
    p.add_argument("--nsims", type=int, default=60000)
    p.add_argument("--seed", type=int, default=2026)
    p.add_argument("--stock-vol", type=float, default=0.18)
    p.add_argument("--defensive-return", type=float, default=0.025)
    p.add_argument("--defensive-vol", type=float, default=0.06)
    p.add_argument("--no-calibrate", action="store_true")
    args = p.parse_args()
    if not args.no_calibrate:
        calibrate(args.nsims, args.seed)
    label = "債券" if args.defensive_return >= 0 else "現金"
    print(f"防御資産={label} 株ボラ{args.stock_vol*100:.0f}% 取崩{args.withdrawal}万 {args.years}年 年次リバランス")
    for g in [0.05, 0.06, 0.07]:
        print(f"=== 株 幾何実質{g*100:.0f}% ｜SWR / 必要額 ===")
        for w in [0.0, 0.10, 0.20, 0.30, 0.40]:
            row = f"防御{int(w*100):3d}%/株{int((1-w)*100):3d}% |"
            for t in [0.80, 0.90, 0.95]:
                swr, need = required_asset(g, args.stock_vol, args.defensive_return,
                                           args.defensive_vol, w, t, args.withdrawal,
                                           args.years, args.nsims, args.seed)
                row += f" {swr*100:5.2f}% {need:5.0f}万 |"
            print(row)
        print()


if __name__ == "__main__":
    main()
