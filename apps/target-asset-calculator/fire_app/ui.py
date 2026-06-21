"""ui.py — 入力フォーム＋結果表示（Streamlit）。

計算は engine/finance/recommend を呼ぶだけ（ロジックを UI に書かない）。
起動: streamlit run fire_app/ui.py

本アプリは投資助言ではありません。結果は確率であって保証ではありません。投資は自己責任で。
"""
from __future__ import annotations

import streamlit as st

# パッケージ実行 / 単体ファイル実行のどちらでも import できるようにする
try:
    from fire_app import engine, finance, recommend
except Exception:  # streamlit run fire_app/ui.py 直接実行時
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from fire_app import engine, finance, recommend

DISCLAIMER = (
    "⚠️ 本アプリは投資助言ではありません。結果はモンテカルロ・シミュレーションに基づく"
    "**確率**であって将来を保証するものではありません。税計算は簡易法です。投資は自己責任で。"
)


@st.cache_data(show_spinner=False)
def _required_table(defensive, defensive_weight, withdrawal_gross, years, nsims, seed):
    """重い感度スイープはキャッシュ（同一入力なら再計算しない）。years もキーに含める。"""
    return recommend.required_table(
        defensive=defensive, defensive_weight=defensive_weight,
        withdrawal_gross=withdrawal_gross, years=years, nsims=nsims, seed=seed)


@st.cache_data(show_spinner=False)
def _current_success(total, stock_geo, defensive, defensive_weight, withdrawal_gross,
                     years, nsims, seed):
    return recommend.current_success(
        total, stock_geo=stock_geo, defensive=defensive,
        defensive_weight=defensive_weight, withdrawal_gross=withdrawal_gross,
        years=years, nsims=nsims, seed=seed)


@st.cache_data(show_spinner=False)
def _required_asset(stock_geo, defensive, defensive_weight, target, withdrawal_gross,
                    years, nsims, seed):
    return recommend.required_asset(
        stock_geo=stock_geo, defensive=defensive, defensive_weight=defensive_weight,
        target=target, withdrawal_gross=withdrawal_gross, years=years,
        nsims=nsims, seed=seed)


@st.cache_data(show_spinner=False)
def _cash_to_bond(stock_geo, defensive_weight, target, withdrawal_gross, years, nsims, seed):
    return recommend.cash_to_bond_effect(
        stock_geo=stock_geo, defensive_weight=defensive_weight, target=target,
        withdrawal_gross=withdrawal_gross, years=years, nsims=nsims, seed=seed)


def main():
    st.set_page_config(page_title="FIRE 目標資産計算", page_icon="🔥", layout="centered")
    st.title("🔥 FIRE / Side-FIRE 目標資産計算")
    st.caption(DISCLAIMER)

    # ---- 入力 ----
    with st.sidebar:
        st.header("入力")
        monthly_living = st.number_input("月の生活費（万円）", 0.0, 200.0, 18.0, 0.5)
        monthly_side = st.number_input("月の事業所得（万円）", 0.0, 200.0, 5.0, 0.5)
        st.divider()
        nisa = st.number_input("NISA残高（万円・株式）", 0.0, 100000.0, 1800.0, 50.0)
        taxable = st.number_input("特定口座残高（万円・株式）", 0.0, 100000.0, 1500.0, 50.0)
        cash = st.number_input("現金残高（万円・防御資産）", 0.0, 100000.0, 825.0, 25.0)
        st.divider()
        defensive = st.selectbox("防御資産の種類", ["cash", "bond"],
                                 format_func=lambda x: "現金（実質−2%）" if x == "cash"
                                 else "債券（実質+2.5%）")
        stock_geo = st.selectbox("株の期待リターン（実質・幾何）", [0.05, 0.06, 0.07],
                                 format_func=lambda x: f"{x*100:.0f}%", index=0)
        target = st.selectbox("目標成功率", [0.80, 0.90, 0.95],
                              format_func=lambda x: f"{x*100:.0f}%", index=1)
        gain = st.slider("特定口座の含み益割合", 0.0, 1.0, 0.5, 0.05)
        years = st.slider("取崩期間（年）", 10, 50, 30, 5)
        run_sweep = st.checkbox("目標額レンジ表（スイープ）を計算", value=True)

    # ---- 計算層を呼ぶだけ ----
    net = finance.annual_withdrawal(monthly_living, monthly_side)
    gross = finance.tax_grossed_withdrawal(net, taxable=taxable, gain=gain, years=years)
    stock_w, def_w = finance.portfolio_weights(nisa=nisa, taxable=taxable, cash=cash)
    total = nisa + taxable + cash

    # ---- 出力 ----
    st.subheader("年間取崩額")
    if net <= 0:
        st.success("月の事業所得が生活費以上のため、資産からの取崩は不要です（取崩額 0）。")
    c1, c2, c3 = st.columns(3)
    c1.metric("税抜き（万円/年）", f"{net:,.1f}")
    c2.metric("税込み・実効（万円/年）", f"{gross:,.1f}")
    c3.metric("総資産（万円）", f"{total:,.0f}")
    st.caption(f"資産構成: 株式 {stock_w*100:.1f}% / 防御 {def_w*100:.1f}%"
               f"（前提: 株{stock_geo*100:.0f}% / 成功率{target*100:.0f}% / 防御={defensive} / {years}年）")

    st.subheader("現在資産での達成確度")
    if total <= 0 or net <= 0:
        st.info("総資産0、または取崩不要のため確度計算は省略します。")
    else:
        try:
            with st.spinner("モンテカルロ計算中…"):
                success = _current_success(total, stock_geo, defensive, def_w, gross,
                                           years, recommend.DEFAULT_NSIMS,
                                           recommend.DEFAULT_SEED)
                swr, need = _required_asset(stock_geo, defensive, def_w, target, gross,
                                            years, recommend.DEFAULT_NSIMS,
                                            recommend.DEFAULT_SEED)
        except engine.InfeasibleTargetError as e:
            st.error(f"この前提では目標成功率 {target*100:.0f}% を満たす取崩率を算出できません: {e}")
        else:
            c1, c2 = st.columns(2)
            c1.metric("現状の達成確度", f"{success*100:.0f}%")
            gap = max(0.0, need - total)
            c2.metric(f"必要額（成功率{target*100:.0f}%）", f"{need:,.0f}万",
                      delta=f"{-gap:,.0f}万（不足）" if gap > 0 else "達成",
                      delta_color="inverse")
            st.caption(f"安全取崩率 SWR = {swr*100:.2f}%"
                       f"（必要額 = 税込取崩 {gross:.1f}万 ÷ SWR、{years}年）")

            if defensive == "cash":
                eff = _cash_to_bond(stock_geo, def_w, target, gross, years,
                                    recommend.DEFAULT_NSIMS, recommend.DEFAULT_SEED)
                st.write(f"💡 現金→債券に置換すると必要額は約 **{eff['reduction']:,.0f}万円** 減少"
                         f"（{eff['need_cash']:,.0f}万 → {eff['need_bond']:,.0f}万）。")

    if run_sweep and net > 0 and total <= 0:
        st.subheader("目標額レンジ（成功率 × 株リターン）")
        st.info("資産情報（NISA・特定・現金）が未入力のため、目標額レンジは表示できません。"
                "現在の資産配分が未定義のため、株100%として誤った値を出さないようにしています。")
    elif run_sweep and net > 0 and total > 0:
        st.subheader("目標額レンジ（成功率 × 株リターン）")
        with st.spinner("スイープ計算中…"):
            table = _required_table(defensive, def_w, gross, years,
                                    recommend.DEFAULT_NSIMS, recommend.DEFAULT_SEED)
        rows = []
        for g in (0.05, 0.06, 0.07):
            rows.append({"株リターン": f"{g*100:.0f}%",
                         **{f"成功率{int(t*100)}%": f"{table[(g, t)][1]:,.0f}万"
                            for t in (0.80, 0.90, 0.95)}})
        st.table(rows)
        st.caption(f"防御={defensive} 比率{def_w*100:.0f}% / 取崩(税込){gross:.1f}万 / {years}年・年次リバランス")

    st.divider()
    st.caption(DISCLAIMER)


if __name__ == "__main__":
    main()
