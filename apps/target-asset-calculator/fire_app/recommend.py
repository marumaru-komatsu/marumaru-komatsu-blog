"""recommend.py — 現状達成確度・必要額テーブル・推奨アクション。

数値エンジン（engine.py）を呼ぶ純粋関数。UI はこの層を呼ぶだけにする。
本番既定は SPEC 第2章どおり nsims=60000・seed=2026。
テストはゴールデン再現のため自前で nsims を渡す（例: test_golden.py の N=40000）。
"""
from __future__ import annotations

from . import engine

DEFAULT_NSIMS = engine.DEFAULT_NSIMS   # = 60000（SPEC 本番既定）
DEFAULT_SEED = engine.DEFAULT_SEED
DEFAULT_GROSS_WITHDRAWAL = 161.7       # 既定の税込年取崩（万円）


def current_success(total, stock_geo=0.05, defensive="cash", defensive_weight=0.2,
                    withdrawal_gross=DEFAULT_GROSS_WITHDRAWAL,
                    stock_vol=engine.STOCK_VOL, years=30,
                    nsims=DEFAULT_NSIMS, seed=DEFAULT_SEED):
    """現在の総資産での達成確度（0..1）。SPEC 5.4。

    現状の取崩率 = 税込年取崩 / 現在総資産 を、共通乱数パス上で評価する。
    total は有限な非負（負・NaN・inf は ValueError）。total==0 は成功率0（正当なエッジ）。
    """
    engine._check_finite("total", total)
    engine._check_nonneg("total", total)
    if total <= 0:
        return 0.0
    rate = withdrawal_gross / total
    return engine.success_at(rate, stock_geo, defensive, defensive_weight,
                             stock_vol, years, nsims, seed)


def required_asset(stock_geo=0.05, defensive="cash", defensive_weight=0.2,
                   target=0.90, withdrawal_gross=DEFAULT_GROSS_WITHDRAWAL,
                   stock_vol=engine.STOCK_VOL, years=30,
                   nsims=DEFAULT_NSIMS, seed=DEFAULT_SEED):
    """(安全取崩率, 必要資産額) を返す。恒等式 required == withdrawal / swr。"""
    engine._check_finite("withdrawal_gross", withdrawal_gross)
    if withdrawal_gross <= 0:
        raise ValueError(f"withdrawal_gross must be > 0, got {withdrawal_gross!r}")
    gross = engine.make_gross(stock_geo, defensive, defensive_weight, stock_vol,
                              years, nsims, seed)
    swr = engine.swr_from_gross(gross, target)
    return swr, withdrawal_gross / swr


def required_table(defensive="cash", defensive_weight=0.2,
                   stock_geos=(0.05, 0.06, 0.07), targets=(0.80, 0.90, 0.95),
                   withdrawal_gross=DEFAULT_GROSS_WITHDRAWAL,
                   stock_vol=engine.STOCK_VOL, years=30,
                   nsims=DEFAULT_NSIMS, seed=DEFAULT_SEED):
    """目標額レンジ表: {(stock_geo, target): (swr, need)}（SPEC 出力4）。

    #6: 株リターン・防御条件ごとに乱数行列を 1 回だけ生成し、複数 target で共有する。
    seed 固定のため数値は per-target 生成と完全一致（ゴールデン不変）。
    """
    engine._check_finite("withdrawal_gross", withdrawal_gross)
    if withdrawal_gross <= 0:
        raise ValueError(f"withdrawal_gross must be > 0, got {withdrawal_gross!r}")
    out = {}
    for g in stock_geos:
        gross = engine.make_gross(g, defensive, defensive_weight, stock_vol,
                                  years, nsims, seed)   # 1回だけ生成して共有
        for t in targets:
            swr = engine.swr_from_gross(gross, t)
            out[(g, t)] = (swr, withdrawal_gross / swr)
    return out


def cash_to_bond_effect(stock_geo=0.05, defensive_weight=0.2, target=0.90,
                        withdrawal_gross=DEFAULT_GROSS_WITHDRAWAL,
                        stock_vol=engine.STOCK_VOL, years=30,
                        nsims=DEFAULT_NSIMS, seed=DEFAULT_SEED):
    """現金→債券の置換効果（SPEC 出力5）。必要額の減少分を返す。

    戻り値: dict(need_cash, need_bond, reduction)  reduction = need_cash - need_bond。
    """
    _, need_cash = required_asset(stock_geo, "cash", defensive_weight, target,
                                  withdrawal_gross, stock_vol, years, nsims, seed)
    _, need_bond = required_asset(stock_geo, "bond", defensive_weight, target,
                                  withdrawal_gross, stock_vol, years, nsims, seed)
    return dict(need_cash=need_cash, need_bond=need_bond,
                reduction=need_cash - need_bond)


def recommend_actions(total, stock_geo=0.05, defensive="cash", defensive_weight=0.2,
                      target=0.90, withdrawal_gross=DEFAULT_GROSS_WITHDRAWAL,
                      stock_vol=engine.STOCK_VOL, years=30,
                      nsims=DEFAULT_NSIMS, seed=DEFAULT_SEED):
    """推奨アクション（SPEC 出力5）。現状確度・必要額・不足額・債券置換効果をまとめる。"""
    engine._check_finite("total", total)
    engine._check_nonneg("total", total)
    success = current_success(total, stock_geo, defensive, defensive_weight,
                              withdrawal_gross, stock_vol, years, nsims, seed)
    _, need = required_asset(stock_geo, defensive, defensive_weight, target,
                             withdrawal_gross, stock_vol, years, nsims, seed)
    gap = max(0.0, need - total)
    bond = cash_to_bond_effect(stock_geo, defensive_weight, target,
                               withdrawal_gross, stock_vol, years, nsims, seed)
    return dict(
        current_total=total,
        current_success=success,
        target_success=target,
        required_asset=need,
        gap=gap,
        on_track=total >= need,
        bond_switch_reduction=bond["reduction"] if defensive == "cash" else 0.0,
    )
