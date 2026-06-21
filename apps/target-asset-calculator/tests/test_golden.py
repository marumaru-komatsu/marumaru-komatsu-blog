"""
ゴールデン値テスト雛形 — 目標資産計算アプリ

2層構成（SPEC.md 第6章に対応）:
  Part 1  性質テスト（実装非依存・許容幅つき）……どんな正しい実装でも満たすべき不変条件
  Part 2  ゴールデン回帰（参照エンジン swr_simulator・nsims=40000 seed=2026 の実測値）
  Part 3  アプリ層ゴールデン（fire_app）は tests/test_app_layer.py へ分離（下部の注記参照）

実行:
  cd 20260617_目標資産計算アプリ
  pip install pytest numpy
  pytest -q

注意:
- Part 1/2 は同梱の参照エンジン `swr_simulator.py` をテスト対象にしている。
  アプリの数値エンジンを別実装した場合は import 先を差し替えるか、エンジンを
  この関数群と同じインターフェースに合わせること。
- モンテカルロのため許容幅（TOL）を設けている。同一 seed/nsims なら決定的。
"""
import math
import numpy as np
import pytest

# --- 参照エンジン（数値の正典）。別実装に差し替える場合はここを変更 -------------
import swr_simulator as eng

N = 40000          # テスト用シナリオ本数（速度と安定性のバランス）
SEED = 2026
WG = 161.7         # 税込み年取崩（万円）

# 既定の資産前提
STOCK_VOL = 0.18
CASH = dict(defensive_geo=-0.02, defensive_vol=0.0)
BOND = dict(defensive_geo=0.025, defensive_vol=0.06)


def swr(stock_geo, def_kw, def_weight, target):
    return eng.safe_withdrawal_rate(stock_geo, STOCK_VOL,
                                    def_kw["defensive_geo"], def_kw["defensive_vol"],
                                    def_weight, target, 30, N, SEED)


def need(stock_geo, def_kw, def_weight, target):
    s = swr(stock_geo, def_kw, def_weight, target)
    return s, WG / s


def success_at(rate, stock_geo, def_kw, def_weight):
    rng = np.random.default_rng(SEED)
    gross = eng._portfolio_gross(stock_geo, STOCK_VOL, def_kw["defensive_geo"],
                                 def_kw["defensive_vol"], def_weight, 30, N, rng)
    return eng._success_given_gross(rate, gross)


# =====================================================================
# Part 1 — 性質テスト（実装非依存）
# =====================================================================
class TestProperties:
    def test_calibration_trinity_reproduces_4pct(self):
        """古典PF(株75/債25・実質株7%/債2.5%)で90%成功のSWRが4.0〜4.6%＝4%ルール再現。"""
        s = eng.safe_withdrawal_rate(0.07, 0.18, 0.025, 0.06, 0.25, 0.90, 30, N, SEED)
        assert 0.040 <= s <= 0.046, f"SWR={s:.4f} は4%ルール再現域外"

    def test_success_monotonic_in_withdrawal(self):
        """取崩率を上げると成功率は下がる（単調減少）。"""
        hi = success_at(0.03, 0.05, CASH, 0.2)
        lo = success_at(0.05, 0.05, CASH, 0.2)
        assert hi > lo

    def test_bond_needs_no_more_than_cash(self):
        """同じ防御比率なら、債券の必要額 ≤ 現金の必要額（90%成功）。"""
        _, need_cash = need(0.05, CASH, 0.2, 0.90)
        _, need_bond = need(0.05, BOND, 0.2, 0.90)
        assert need_bond <= need_cash + 1.0  # 1万円の数値誤差を許容

    def test_required_equals_withdrawal_over_swr(self):
        """恒等式 required == withdrawal / swr。"""
        s, n = need(0.05, CASH, 0.2, 0.90)
        assert math.isclose(n, WG / s, rel_tol=1e-6)

    def test_zero_defensive_cash_equals_bond(self):
        """防御0%（株100%）は cash/bond で同一になる。"""
        _, n_cash = need(0.05, CASH, 0.0, 0.90)
        _, n_bond = need(0.05, BOND, 0.0, 0.90)
        assert math.isclose(n_cash, n_bond, rel_tol=1e-9)

    def test_reproducible_same_seed(self):
        """同一 seed/nsims で再現一致。"""
        a = swr(0.05, CASH, 0.2, 0.90)
        b = swr(0.05, CASH, 0.2, 0.90)
        assert a == b

    def test_higher_target_needs_more(self):
        """求める成功率が高いほど必要額は増える。"""
        _, n80 = need(0.05, CASH, 0.2, 0.80)
        _, n90 = need(0.05, CASH, 0.2, 0.90)
        _, n95 = need(0.05, CASH, 0.2, 0.95)
        assert n80 < n90 < n95


# =====================================================================
# Part 2 — ゴールデン回帰（参照エンジン・nsims=40000 seed=2026）
# =====================================================================
class TestGoldenEngine:
    @pytest.mark.parametrize("target,exp_swr,exp_need", [
        (0.80, 3.80, 4256),
        (0.90, 3.15, 5135),
        (0.95, 2.68, 6026),
    ])
    def test_user_pf_stock5_cash20(self, target, exp_swr, exp_need):
        s, n = need(0.05, CASH, 0.2, target)
        assert s * 100 == pytest.approx(exp_swr, abs=0.10)
        assert n == pytest.approx(exp_need, rel=0.01)

    @pytest.mark.parametrize("g,exp_need", [(0.05, 5135), (0.06, 4630), (0.07, 4195)])
    def test_stock_sensitivity_90_cash20(self, g, exp_need):
        _, n = need(g, CASH, 0.2, 0.90)
        assert n == pytest.approx(exp_need, rel=0.01)

    def test_bond20_90_stock5(self):
        _, n = need(0.05, BOND, 0.2, 0.90)
        assert n == pytest.approx(4524, rel=0.01)

    def test_bond40_90_stock5_hits_current_target(self):
        """債券40%・90%成功で約4,125万（現行目標）に一致。"""
        _, n = need(0.05, BOND, 0.4, 0.90)
        assert n == pytest.approx(4125, rel=0.015)

    @pytest.mark.parametrize("g,exp_pct", [(0.05, 76), (0.06, 83), (0.07, 88)])
    def test_4pct_success_user_pf(self, g, exp_pct):
        assert success_at(0.04, g, CASH, 0.2) * 100 == pytest.approx(exp_pct, abs=2)

    def test_4pct_success_classic(self):
        rng = np.random.default_rng(SEED)
        gross = eng._portfolio_gross(0.07, 0.18, 0.025, 0.06, 0.25, 30, N, rng)
        assert eng._success_given_gross(0.04, gross) * 100 == pytest.approx(94, abs=2)


# =====================================================================
# Part 3 — アプリ層ゴールデン（fire_app）は tests/test_app_layer.py へ分離した。
#   理由: モジュール直下の importorskip("fire_app") があると、fire_app の import
#   失敗時に本ファイルの Part 1・2（性質＋ゴールデン回帰）まで収集ごと skip され、
#   「Part 1・2 は常に正典を検査する」前提が崩れるため（レビュー #5）。
#   ゴールデン値そのものは SPEC 6.3 のまま不変で test_app_layer.py に移設している。
# =====================================================================
