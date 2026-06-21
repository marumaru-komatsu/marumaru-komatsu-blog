# CHANGELOG

## [0.1.4] — 2026-06-21 — 4度目レビュー指摘（#1）対応

### #1 (Medium) 財務層・推奨層の有限性／整数性検証を統一
- 前回 #1/#2 で正典・engine 層に入れた有限性／整数性検証が、財務層（finance）と
  `current_success` の `total` に適用漏れだった。`finance.py` は正典由来の検証ヘルパを
  engine 経由で再利用するよう変更（層ごとの独自ヘルパ実装を廃止＝単一ソース化）。
- `annual_withdrawal`：両月額に `_check_finite`。`annual_withdrawal(NaN,0)` は 0.0 でなく `ValueError`。
- `tax_grossed_withdrawal`：`net`/`taxable` に `_check_finite`、`years` を `_check_pos`→`_as_pos_int`
  （正の整数）に。`tax_grossed_withdrawal(NaN)`→ValueError、`years=0.5`→ValueError、`years=30.0`→許容。
- `portfolio_weights`：3残高に `_check_finite`。`portfolio_weights(NaN,0,0)`→ValueError。
  有限な全0残高のときのみ `(0,0)` センチネルを返す挙動は維持。
- `recommend.current_success` / `recommend_actions`：`total` を `_check_finite`＋`_check_nonneg` で検証。
  `current_success(total=inf)`→ValueError、負値→ValueError。`total==0`→成功率0.0（正当なエッジ）は維持。

### テスト
- `test_fire_app.py` に `TestFinanceFiniteValidation`（NaN net/balance/月額・`years=0.5`拒否・`30.0`許容）と
  `TestRecommendTotalValidation`（inf/NaN/負 total 拒否・total=0 は 0.0）を追加。
- `test_golden.py`(19) + `test_app_layer.py`(6) + `test_fire_app.py`(79) = 104 件パス。

### 前提の変更
- なし。SPEC 第2章の前提・固定ロジック・ゴールデン値（4256/5135/6026・校正4.38%）は不変。

---

## [0.1.3] — 2026-06-21 — 3度目レビュー指摘（#1〜#2）対応

### #1 (Medium) 有限性・幾何リターン定義域の検証
- 正典 `swr_simulator.py` に `_check_finite`（NaN/±inf を拒否）と `_check_geo`（有限かつ > -1、
  `log(1+geo)` の定義域）を追加。`_check_pos`/`_check_nonneg` は `nan<=0` が False で NaN を
  すり抜けていたため、有限性は専用チェックで担保する。
- 適用：`make_gross` の `stock_geo`/`defensive_geo`→`_check_geo`、`stock_vol`/`defensive_vol`→
  `_check_finite`＋`_check_nonneg`。`required_asset` の `withdrawal`→`_check_finite`＋`_check_pos`。
  `engine.success_at` の `rate`、`recommend.required_asset`/`required_table` の `withdrawal_gross`
  にも有限性チェックを追加（アプリ層の独自ガードが `<=0` のみで NaN を通していたため）。
- これで `withdrawal=NaN`→NaN 必要額、`vol=NaN`→全 NaN 行列、`stock_geo<=-1`→負グロスを ValueError に。

### #2 (Medium) swr_from_gross の行列・探索区間検証
- 公開 `swr_from_gross` の冒頭に `_validate_gross`（2次元・年数>0・シナリオ>0・全要素 有限かつ正）と
  `_check_interval`（`lo`/`hi` 有限・`0<=lo<hi`）を追加。空行列 `(30,0)` 等は SWR0.5% の無根拠返却を
  せず ValueError に。検証後の二分探索ロジック・数値は不変。
- 検証コストは、既存の端点判定＋40反復が同じ行列を多数回走査する中での追加2走査で無視できる。

### テスト
- `test_fire_app.py` に `TestFiniteAndDomain`（NaN withdrawal/vol・geo<=-1・rate=NaN）と
  `TestGrossMatrixValidation`（空・非2次元・非有限・非正行列・不正 lo/hi）を追加。
- `test_golden.py`(19) + `test_app_layer.py`(6) + `test_fire_app.py`(68) = 93 件パス。

### 前提の変更
- なし。SPEC 第2章の前提・固定ロジック・ゴールデン値（4256/5135/6026・校正4.38%）は不変。
  正典は数値アルゴリズムを変えずに検証ガードのみ追加した。

---

## [0.1.2] — 2026-06-21 — 再レビュー指摘（#1〜#3）対応

### #1 (High) 端点・入力検証を正典 swr_simulator.py へ統合
- 前回は検証を `fire_app.engine` のみに置き正典を無編集にしていたが、SPEC 5.4 が参照先に指定する
  `swr_simulator.safe_withdrawal_rate` を直接呼ぶと端点未検証のバグが残り、正典とアプリ層で
  挙動が分裂していた。**方針を変更**し、検証を正典へ集約（元課題は正典の改変＝「再利用 or 同等再実装」を許容）。
- `swr_simulator.py` に `swr_from_gross`（端点検証つき二分探索）・`make_gross`（入力検証つき生成）・
  `InfeasibleTargetError`・各検証ヘルパを実装。`target` は開区間 (0,1)。
- `fire_app/engine.py` は自前の二分探索・例外定義を廃し、上記を正典から **import して再利用**
  （`engine.safe_withdrawal_rate is swr_simulator.safe_withdrawal_rate`）。二重実装を排除。
  engine にはアプリ便宜（DEFENSIVE マップ・名前指定 make_gross/success_at）のみ残す。
- アルゴリズム（lo=0.005 / hi=0.12 / 40反復）は不変。Part 1・2 ゴールデンは数値ドリフトなし
  （4256/5135/6026・校正4.38% を再確認）。`test_golden.py` は無編集。

### #2 (Medium) years・nsims の整数検証（暗黙の切り捨て禁止）
- 正典 `make_gross` に `_as_pos_int` を導入。`years`/`nsims` が有限な正の整数（int、または
  30.0 等の整数値 float）でなければ `ValueError`。`years=0.9` や `nsims=0.1` は空行列を作らず即エラー。
  engine/recommend は正典へ委譲するため全経路で有効。

### #3 (Medium) 総資産0での配分・感度表の扱い
- `portfolio_weights(0,0,0)` の `(0,0)` は「比率未定義」のセンチネル（和が1にならない）と docstring に明記。
- `ui.py`：感度表ブロックを `total > 0` でガード。総資産0のときは株100%の誤った必要額を出さず、
  「資産情報が未入力のため表示できない」旨を明示。現状確度ブロックは従来どおり `total<=0` で省略。

### テスト
- `test_fire_app.py` に `TestCanonHardening`（正典直呼びの例外・engine が正典を再利用・両者一致）と
  `TestIntegerValidation`（float 拒否・整数値 float 許容・NaN/inf 拒否）を追加。
- `test_golden.py`(19) + `test_app_layer.py`(6) + `test_fire_app.py`(56) = 81 件パス。

### 前提の変更
- なし（SPEC 第2章の前提・固定ロジック・ゴールデン値は不変）。正典 `swr_simulator.py` は
  数値アルゴリズムを変えずに検証ガードのみ追加した。

---

## [0.1.1] — 2026-06-21 — レビュー指摘（#1〜#6）対応

レビュー結果を受けて 6 件を修正。Part 1・2 のゴールデン値・`swr_simulator.py` は無編集。

### #1 (Critical) UI の取崩期間 years が全計算へ伝播していなかった
- `ui.py` の `current_success` / `required_asset` / `cash_to_bond_effect` /
  `required_table` 呼び出しと、対応する `st.cache_data` 関数のキャッシュキーに `years` を追加。
  これまで years は税計算のみに渡り、成功率・必要額・感度表は常に30年で計算され表示と食い違っていた。
- `test_fire_app.py::TestYearsPropagation` に years=10/30/50 の単調性・表反映テストを追加。

### #2 (High) 二分探索の端点未検証・target 無制限
- `engine.swr_from_gross` を新設し、探索前に下端 0.5%・上端 12% で達成可否を検証。
  解が区間外なら `InfeasibleTargetError`（`ValueError` サブクラス）を送出。
- `target` を開区間 (0,1) に制限（1.0 は対数正規で保証不能のため拒否）。
- 参照 `swr_simulator.py` は無編集のまま。ハードン版はアプリ計算層の入口（engine）に置き、
  Part 1・2 は従来どおり参照を直接検査する。アルゴリズム（lo/hi/40反復）は参照と同一。

### #3 (Medium) 本番 nsims を SPEC の 60000 へ是正
- `recommend.DEFAULT_NSIMS` を 40000 → `engine.DEFAULT_NSIMS`(=60000) に。
- テストは元から `N=40000` を明示的に渡しており（Part 1・2）、Part 3 の `current_success`
  も既定 60000 で許容 ±3pt 内（77.7/84.1/89.1%）を確認。当初 40000 にした経緯と是正を明記。

### #4 (Medium) 計算層の入力範囲検証を追加
- `finance` / `engine` の入口で 残高≥0・`years>0`・`gain/weight/target∈[0,1]`・`rate≥0`
  を検証し、範囲外は `ValueError` に統一。`portfolio_weights` の負残高は黙って (0,0) にせず例外。
- `annual_withdrawal` の「事業所得≥生活費→0」は SPEC 6章が認めるエッジ扱いとして維持（負入力は拒否）。

### #5 (Medium) Part 3 を別ファイルへ分離
- `tests/test_golden.py` 末尾の `importorskip("fire_app")` が fire_app の import 失敗時に
  Part 1・2 まで収集ごと skip させていた。Part 3 を `tests/test_app_layer.py` へ移設。
  `test_golden.py` は Part 1・2 とゴールデン値を不変のまま、fire_app の有無に関わらず正典を検査する。

### #6 (Low) 感度スイープの乱数行列を再利用
- `engine.make_gross`（生成）と `engine.swr_from_gross`（探索）に分離し、`required_table` は
  株リターン・防御条件ごとに gross を 1 回だけ生成して複数 target で共有。
  seed 固定のため数値は per-target 生成と完全一致（テストで rel=1e-12 を確認）。生成回数は 1/3。

### テスト
- `test_golden.py`(19) + `test_app_layer.py`(6) + `test_fire_app.py`(47) = 72 件パス。

---

## [0.1.0] — 2026-06-21 — fire_app 計算層 + Streamlit UI 実装

### 追加
- `fire_app/`（engine / finance / recommend / ui）を SPEC 第8章の構成で実装。
  `engine.py` は参照エンジン `swr_simulator.py` を単一の正典として再利用。
- `tests/test_fire_app.py`、`requirements.txt`、README 起動手順。

### 受け入れ
- `tests/test_golden.py` Part 1・2・3 全緑（nsims=40000, seed=2026）。
- 不変条件1〜4を維持。

### 前提の変更
- v0.1.0 時点では本番 nsims を 40000 にしていた（ゴールデン再現のため）。v0.1.1 で SPEC の
  60000 へ是正（#3）。それ以外の SPEC 第2章の前提・固定ロジックは未変更。`swr_simulator.py` も無編集。
