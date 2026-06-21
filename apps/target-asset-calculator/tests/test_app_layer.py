"""test_app_layer.py — Part 3 アプリ層ゴールデン（fire_app）。

元は test_golden.py 末尾にあったが、モジュール直下の importorskip が fire_app の
import 失敗時に Part 1・2（性質＋ゴールデン回帰）まで収集ごと skip させてしまうため
別ファイルへ分離した（レビュー #5）。これにより test_golden.py は fire_app の有無に
かかわらず常に正典エンジンを検査する。ゴールデン値は SPEC 6.3 のまま不変。

current_success は nsims を渡さず本番既定（60000, seed=2026）で評価する。
既定 60000 でも 78/84/89% の許容 ±3pt 内に収まることを確認済み。
"""
import pytest

fire_app = pytest.importorskip(
    "fire_app",
    reason="アプリ層 fire_app は未実装。SPEC.md 5章のインターフェースで実装すると有効化される。",
)


class TestAppLayer:
    def test_annual_withdrawal(self):
        assert fire_app.annual_withdrawal(18, 5) == pytest.approx(156)

    def test_tax_grossed_withdrawal(self):
        g = fire_app.tax_grossed_withdrawal(156, taxable=1500, gain=0.5, years=30)
        assert g == pytest.approx(161.7, abs=0.5)

    def test_portfolio_weights(self):
        sw, dw = fire_app.portfolio_weights(nisa=1800, taxable=1500, cash=825)
        assert sw == pytest.approx(0.8, abs=0.005)
        assert dw == pytest.approx(0.2, abs=0.005)

    @pytest.mark.parametrize("g,exp_pct", [(0.05, 78), (0.06, 84), (0.07, 89)])
    def test_current_success_4125(self, g, exp_pct):
        pct = fire_app.current_success(total=4125, stock_geo=g, defensive="cash",
                                       defensive_weight=0.2) * 100
        assert pct == pytest.approx(exp_pct, abs=3)
