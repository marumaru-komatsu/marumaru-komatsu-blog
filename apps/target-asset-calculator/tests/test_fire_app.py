"""test_fire_app.py — fire_app 計算層の追加テスト（新挙動・エッジケース固定）。

SPEC.md 第6章の「エッジ」要件と、口頭の主張ではなくテストで数字を固定する作法に対応。
Part 3 ゴールデン（test_app_layer.py）と重複しない範囲を補完する。
"""
import math

import pytest

import fire_app
from fire_app import engine, finance, recommend


# --- annual_withdrawal --------------------------------------------------
class TestAnnualWithdrawal:
    def test_basic(self):
        assert fire_app.annual_withdrawal(18, 5) == 156

    def test_side_income_equals_living_is_zero(self):
        assert fire_app.annual_withdrawal(18, 18) == 0

    def test_side_income_exceeds_living_clamped_to_zero(self):
        assert fire_app.annual_withdrawal(18, 25) == 0

    def test_full_fire_zero_side_income(self):
        assert fire_app.annual_withdrawal(20, 0) == 240


# --- tax_grossed_withdrawal --------------------------------------------
class TestTaxGrossed:
    def test_golden(self):
        assert fire_app.tax_grossed_withdrawal(156, taxable=1500, gain=0.5,
                                               years=30) == pytest.approx(161.7, abs=0.5)

    def test_zero_net_returns_zero(self):
        assert fire_app.tax_grossed_withdrawal(0) == 0

    def test_zero_gain_no_uplift(self):
        assert fire_app.tax_grossed_withdrawal(156, taxable=1500, gain=0.0) == pytest.approx(156)

    def test_uplift_is_nonnegative_and_monotonic_in_gain(self):
        g0 = fire_app.tax_grossed_withdrawal(156, gain=0.2)
        g1 = fire_app.tax_grossed_withdrawal(156, gain=0.8)
        assert 156 <= g0 <= g1

    def test_taxable_phase_capped_at_one(self):
        huge = fire_app.tax_grossed_withdrawal(156, taxable=10**9, gain=0.5)
        per_year = 1 / (1 - 0.5 * 0.20315) - 1
        assert huge == pytest.approx(156 * (1 + per_year))


# --- portfolio_weights --------------------------------------------------
class TestPortfolioWeights:
    def test_golden(self):
        sw, dw = fire_app.portfolio_weights(1800, 1500, 825)
        assert (sw, dw) == pytest.approx((0.8, 0.2), abs=0.005)

    def test_weights_sum_to_one(self):
        sw, dw = fire_app.portfolio_weights(1000, 500, 500)
        assert sw + dw == pytest.approx(1.0)

    def test_all_stock(self):
        assert fire_app.portfolio_weights(1000, 1000, 0) == (1.0, 0.0)

    def test_all_cash(self):
        assert fire_app.portfolio_weights(0, 0, 500) == (0.0, 1.0)

    def test_zero_total_no_division_error(self):
        assert fire_app.portfolio_weights(0, 0, 0) == (0.0, 0.0)


# --- current_success ----------------------------------------------------
class TestCurrentSuccess:
    @pytest.mark.parametrize("g,exp", [(0.05, 78), (0.06, 84), (0.07, 89)])
    def test_golden_default_nsims(self, g, exp):
        pct = fire_app.current_success(total=4125, stock_geo=g, defensive="cash",
                                       defensive_weight=0.2) * 100
        assert pct == pytest.approx(exp, abs=3)

    def test_more_assets_more_success(self):
        lo = fire_app.current_success(3000, stock_geo=0.05, nsims=8000)
        hi = fire_app.current_success(6000, stock_geo=0.05, nsims=8000)
        assert hi > lo

    def test_zero_total_returns_zero(self):
        assert fire_app.current_success(0) == 0.0

    def test_bond_at_least_as_good_as_cash(self):
        s_cash = fire_app.current_success(4125, defensive="cash", nsims=8000)
        s_bond = fire_app.current_success(4125, defensive="bond", nsims=8000)
        assert s_bond >= s_cash - 0.01

    def test_invalid_defensive_raises(self):
        with pytest.raises(ValueError):
            fire_app.current_success(4125, defensive="gold")


# --- recommend layer ----------------------------------------------------
class TestRecommend:
    def test_required_identity(self):
        swr, need = recommend.required_asset(0.05, "cash", 0.2, 0.90, 161.7, nsims=8000)
        assert need == pytest.approx(161.7 / swr, rel=1e-9)

    def test_required_table_shape(self):
        t = recommend.required_table(nsims=4000)
        assert set(t.keys()) >= {(0.05, 0.90), (0.07, 0.95)}

    def test_required_table_matches_per_target(self):
        """#6: gross 再利用の表が per-target 直接計算と完全一致（数値不変）。"""
        tbl = recommend.required_table(stock_geos=(0.05,), targets=(0.80, 0.90),
                                       nsims=8000)
        for t in (0.80, 0.90):
            direct = recommend.required_asset(0.05, "cash", 0.2, t, 161.7, nsims=8000)[1]
            assert tbl[(0.05, t)][1] == pytest.approx(direct, rel=1e-12)

    def test_cash_to_bond_reduction_nonnegative(self):
        eff = recommend.cash_to_bond_effect(0.05, 0.2, 0.90, 161.7, nsims=8000)
        assert eff["reduction"] >= -1.0

    def test_recommend_actions_keys(self):
        a = recommend.recommend_actions(4125, nsims=8000)
        assert {"current_success", "required_asset", "gap", "on_track"} <= set(a)


# --- engine invariants --------------------------------------------------
class TestEngineInvariants:
    def test_portfolio_gross_is_weighted_arithmetic_mean(self):
        """不変条件2: 1年グロス = 加重算術平均（加重幾何平均ではない）。"""
        import numpy as np
        rng = np.random.default_rng(2026)
        w_def = 0.3
        gross = engine._portfolio_gross(0.05, 0.18, 0.025, 0.06, w_def, 5, 1000, rng)
        rng2 = np.random.default_rng(2026)
        sg = engine._gross_matrix(0.05, 0.18, 5, 1000, rng2)
        dg = engine._gross_matrix(0.025, 0.06, 5, 1000, rng2)
        expected = (1 - w_def) * sg + w_def * dg
        assert np.allclose(gross, expected)

    def test_uses_reference_engine(self):
        assert engine._USING_REFERENCE is True

    def test_success_monotonic_in_rate(self):
        hi = engine.success_at(0.03, 0.05, "cash", 0.2, nsims=8000)
        lo = engine.success_at(0.06, 0.05, "cash", 0.2, nsims=8000)
        assert hi > lo

    def test_extreme_rate_does_not_crash(self):
        assert engine.success_at(0.50, 0.05, "cash", 0.2, nsims=2000) == pytest.approx(0.0, abs=0.01)
        assert engine.success_at(0.001, 0.07, "cash", 0.0, nsims=2000) > 0.5


# --- #1 years 伝播 ------------------------------------------------------
class TestYearsPropagation:
    def test_required_asset_monotonic_in_years(self):
        n10 = recommend.required_asset(0.05, "cash", 0.2, 0.90, 161.7, years=10, nsims=8000)[1]
        n30 = recommend.required_asset(0.05, "cash", 0.2, 0.90, 161.7, years=30, nsims=8000)[1]
        n50 = recommend.required_asset(0.05, "cash", 0.2, 0.90, 161.7, years=50, nsims=8000)[1]
        assert n10 < n30 < n50

    def test_current_success_decreases_with_years(self):
        s10 = recommend.current_success(4125, 0.05, "cash", 0.2, years=10, nsims=8000)
        s50 = recommend.current_success(4125, 0.05, "cash", 0.2, years=50, nsims=8000)
        assert s10 > s50

    @pytest.mark.parametrize("years", [10, 30, 50])
    def test_required_table_respects_years(self, years):
        tbl = recommend.required_table(stock_geos=(0.05,), targets=(0.90,),
                                       years=years, nsims=8000)
        direct = recommend.required_asset(0.05, "cash", 0.2, 0.90, 161.7,
                                          years=years, nsims=8000)[1]
        assert tbl[(0.05, 0.90)][1] == pytest.approx(direct, rel=1e-12)


# --- #2 端点検証・target 制限 ------------------------------------------
class TestEndpointsAndTarget:
    def test_target_one_rejected(self):
        with pytest.raises(ValueError):
            recommend.required_asset(0.05, "cash", 0.2, target=1.0, nsims=4000)

    def test_target_zero_rejected(self):
        with pytest.raises(ValueError):
            recommend.required_asset(0.05, "cash", 0.2, target=0.0, nsims=4000)

    def test_infeasible_target_raises(self):
        with pytest.raises(engine.InfeasibleTargetError):
            engine.safe_withdrawal_rate(-0.20, 0.50, -0.02, 0.0, 0.2,
                                        target=0.99, years=100, nsims=8000, seed=2026)

    def test_feasible_target_returns_valid_swr(self):
        gross = engine.make_gross(0.05, "cash", 0.2, nsims=8000)
        swr = engine.swr_from_gross(gross, 0.90)
        assert engine._success_given_gross(swr, gross) >= 0.90 - 1e-9
        assert engine.SWR_LO < swr < engine.SWR_HI


# --- #4 入力範囲検証 ----------------------------------------------------
class TestInputValidation:
    def test_negative_balance_rejected(self):
        with pytest.raises(ValueError):
            finance.portfolio_weights(100, -200, 50)

    def test_negative_net_rejected(self):
        with pytest.raises(ValueError):
            finance.tax_grossed_withdrawal(-10)

    def test_negative_taxable_rejected(self):
        with pytest.raises(ValueError):
            finance.tax_grossed_withdrawal(156, taxable=-100)

    def test_gain_out_of_range_rejected(self):
        with pytest.raises(ValueError):
            finance.tax_grossed_withdrawal(156, gain=1.5)

    def test_negative_monthly_rejected(self):
        with pytest.raises(ValueError):
            finance.annual_withdrawal(-5, 0)

    def test_weight_out_of_range_rejected(self):
        with pytest.raises(ValueError):
            engine.success_at(0.04, 0.05, "cash", defensive_weight=1.5, nsims=2000)

    def test_nonpositive_years_rejected(self):
        with pytest.raises(ValueError):
            engine.success_at(0.04, 0.05, "cash", 0.2, years=0, nsims=2000)

    def test_negative_rate_rejected(self):
        with pytest.raises(ValueError):
            engine.success_at(-0.01, 0.05, "cash", 0.2, nsims=2000)


# --- 再レビュー #1: 端点・入力検証が正典に統合され、engine が再利用すること --
class TestCanonHardening:
    def test_canon_rejects_infeasible_target(self):
        """正典 swr_simulator を直接呼んでも端点検証が効く（前回の分裂を解消）。"""
        import numpy as np
        import swr_simulator as s
        with pytest.raises(ValueError):
            s.safe_withdrawal_rate(-0.20, 0.50, -0.02, 0.0, 0.2,
                                   target=1.0, years=100, nsims=20000, seed=2026)

    def test_engine_reuses_canon(self):
        """engine は正典の関数をそのまま再利用している（二重実装でない）。"""
        import swr_simulator as s
        assert engine._USING_REFERENCE is True
        assert engine.safe_withdrawal_rate is s.safe_withdrawal_rate
        assert engine.swr_from_gross is s.swr_from_gross
        assert engine.InfeasibleTargetError is s.InfeasibleTargetError

    def test_canon_and_engine_agree_feasible(self):
        """feasible なケースでは正典とアプリ層が同一の SWR を返す。"""
        import swr_simulator as s
        a = s.safe_withdrawal_rate(0.05, 0.18, -0.02, 0.0, 0.2, 0.90, 30, 8000, 2026)
        b = engine.safe_withdrawal_rate(0.05, 0.18, -0.02, 0.0, 0.2, 0.90, 30, 8000, 2026)
        assert a == b


# --- 再レビュー #2: years/nsims の整数検証（暗黙の切り捨て禁止） -------------
class TestIntegerValidation:
    def test_float_years_rejected_engine(self):
        with pytest.raises(ValueError):
            engine.make_gross(0.05, years=0.9, nsims=10)

    def test_float_nsims_rejected_engine(self):
        with pytest.raises(ValueError):
            engine.make_gross(0.05, years=1, nsims=0.1)

    def test_float_years_rejected_canon(self):
        import swr_simulator as s
        with pytest.raises(ValueError):
            s.make_gross(0.05, 0.18, -0.02, 0.0, 0.2, years=0.9, nsims=10, seed=2026)

    def test_integral_float_accepted(self):
        """30.0 のような整数値 float は許容（shape は整数次元）。"""
        g = engine.make_gross(0.05, years=30.0, nsims=100.0)
        assert g.shape == (30, 100)

    def test_nan_inf_rejected(self):
        for bad in (float("nan"), float("inf")):
            with pytest.raises(ValueError):
                engine.make_gross(0.05, years=bad, nsims=10)

    def test_required_asset_float_years_rejected(self):
        with pytest.raises(ValueError):
            recommend.required_asset(0.05, "cash", 0.2, 0.90, 161.7, years=10.5, nsims=4000)


# --- 3度目レビュー #1: 有限性・幾何リターン定義域（NaN/inf/geo<=-1） ----------
class TestFiniteAndDomain:
    def test_nan_withdrawal_rejected_canon(self):
        import swr_simulator as s
        with pytest.raises(ValueError):
            s.required_asset(0.05, 0.18, -0.02, 0, 0.2, withdrawal=float("nan"), nsims=1000)

    def test_nan_withdrawal_rejected_app(self):
        with pytest.raises(ValueError):
            recommend.required_asset(0.05, "cash", 0.2, 0.90,
                                     withdrawal_gross=float("nan"), nsims=1000)

    def test_nan_vol_rejected(self):
        import swr_simulator as s
        with pytest.raises(ValueError):
            s.make_gross(0.05, float("nan"), -0.02, 0, 0.2, 30, 1000, 2026)
        with pytest.raises(ValueError):
            engine.make_gross(0.05, "cash", 0.2, stock_vol=float("inf"), nsims=1000)

    def test_geo_at_or_below_minus_one_rejected(self):
        import swr_simulator as s
        with pytest.raises(ValueError):
            s.make_gross(-1.5, 0, -0.02, 0, 0.2, 30, 1000, 2026)
        with pytest.raises(ValueError):
            s.make_gross(-1.0, 0, -0.02, 0, 0.2, 30, 1000, 2026)

    def test_nan_rate_rejected(self):
        with pytest.raises(ValueError):
            engine.success_at(float("nan"), 0.05, "cash", 0.2, nsims=1000)

    def test_valid_geo_just_above_minus_one_ok(self):
        g = engine.make_gross(-0.9, "cash", 0.2, nsims=500)
        import numpy as np
        assert np.isfinite(g).all() and (g > 0).all()


# --- 3度目レビュー #2: swr_from_gross の行列・探索区間検証 -------------------
class TestGrossMatrixValidation:
    def test_empty_scenarios_rejected(self):
        import numpy as np
        import swr_simulator as s
        with pytest.raises(ValueError):
            s.swr_from_gross(np.empty((30, 0)), target=0.90)

    def test_zero_years_rejected(self):
        import numpy as np
        import swr_simulator as s
        with pytest.raises(ValueError):
            s.swr_from_gross(np.empty((0, 100)), target=0.90)

    def test_non_2d_rejected(self):
        import numpy as np
        import swr_simulator as s
        with pytest.raises(ValueError):
            s.swr_from_gross(np.ones(30), target=0.90)

    def test_non_finite_matrix_rejected(self):
        import numpy as np
        import swr_simulator as s
        m = np.ones((30, 100)); m[0, 0] = np.nan
        with pytest.raises(ValueError):
            s.swr_from_gross(m, target=0.90)

    def test_non_positive_matrix_rejected(self):
        import numpy as np
        import swr_simulator as s
        m = np.ones((30, 100)); m[5, 5] = -0.1
        with pytest.raises(ValueError):
            s.swr_from_gross(m, target=0.90)

    def test_bad_interval_rejected(self):
        import numpy as np
        import swr_simulator as s
        m = np.full((30, 100), 1.05)
        with pytest.raises(ValueError):
            s.swr_from_gross(m, target=0.90, lo=0.12, hi=0.005)   # lo >= hi
        with pytest.raises(ValueError):
            s.swr_from_gross(m, target=0.90, lo=float("nan"), hi=0.12)


# --- 4度目レビュー #1: 財務層・推奨層の有限性／整数性検証の統一 --------------
class TestFinanceFiniteValidation:
    def test_annual_withdrawal_nan_rejected(self):
        with pytest.raises(ValueError):
            finance.annual_withdrawal(float("nan"), 0)
        with pytest.raises(ValueError):
            finance.annual_withdrawal(18, float("inf"))

    def test_tax_grossed_nan_net_rejected(self):
        with pytest.raises(ValueError):
            finance.tax_grossed_withdrawal(float("nan"))

    def test_tax_grossed_nan_taxable_rejected(self):
        with pytest.raises(ValueError):
            finance.tax_grossed_withdrawal(156, taxable=float("nan"))

    def test_tax_grossed_noninteger_years_rejected(self):
        with pytest.raises(ValueError):
            finance.tax_grossed_withdrawal(156, years=0.5)

    def test_tax_grossed_integral_float_years_ok(self):
        assert finance.tax_grossed_withdrawal(156, years=30.0) == pytest.approx(161.7, abs=0.5)

    def test_portfolio_weights_nan_rejected(self):
        with pytest.raises(ValueError):
            finance.portfolio_weights(float("nan"), 0, 0)
        with pytest.raises(ValueError):
            finance.portfolio_weights(1800, float("inf"), 825)


class TestRecommendTotalValidation:
    def test_current_success_inf_rejected(self):
        with pytest.raises(ValueError):
            recommend.current_success(float("inf"), nsims=1000)

    def test_current_success_nan_rejected(self):
        with pytest.raises(ValueError):
            recommend.current_success(float("nan"), nsims=1000)

    def test_current_success_negative_rejected(self):
        with pytest.raises(ValueError):
            recommend.current_success(-100, nsims=1000)

    def test_current_success_zero_is_valid_zero(self):
        """total==0 は正当なエッジ（成功率0.0）として許容（例外にしない）。"""
        assert recommend.current_success(0) == 0.0

    def test_recommend_actions_nan_total_rejected(self):
        with pytest.raises(ValueError):
            recommend.recommend_actions(float("nan"), nsims=1000)
