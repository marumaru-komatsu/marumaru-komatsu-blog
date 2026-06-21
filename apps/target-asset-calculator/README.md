# 目標資産計算アプリ — 仕様＆ゴールデンテスト一式

FIRE / Side-FIRE の目標資産額と資産構成を、月の生活費・事業所得と
現在の金融資産（NISA・特定・現金）から計算するアプリの**開発キット**。

実装そのものはまだ無い。ここにあるのは、複数のAIコーディングエージェント
（Claude Code / Codex など）に渡すための「正典」一式：

| ファイル | 役割 |
| --- | --- |
| `SPEC.md` | 仕様書（前提・入出力・受け入れ基準） |
| `tests/test_golden.py` | ゴールデン値テスト雛形（受け入れ基準を機械化） |
| `swr_simulator.py` | 数値エンジンの参照実装（検証済み・テストの土台） |

## 使い方（AIエージェントへの渡し方）

1. **人間が前提を確定**：`SPEC.md` 第2章の前提を確認・調整する（ここはAIに任せない）。
2. **実装役のAIに渡す**：`SPEC.md` ＋ `swr_simulator.py` を「正典」として渡し、
   `SPEC.md` 第8章のモジュール構成と第5章の関数仕様で `fire_app` ＋ UI を実装させる。
3. **レビュー役のAIに渡す**：別エージェントに「この実装の前提の穴・数値バグを批判的に
   指摘して」とレビューさせる（実装役とは別のAIにするのがコツ）。
4. **テストで採点**：`pytest -q` が全緑になるまで往復。数値はテストが真偽を握る。

## テスト実行

```bash
pip install pytest numpy
pytest -q                 # tests/ をルートから実行（swr_simulator が import できる位置で）
```

- **Part 1（性質テスト）**：実装非依存の不変条件（校正・単調性・方向性・恒等式・決定性）。
- **Part 2（ゴールデン回帰）**：参照エンジンの実測値（nsims=40000, seed=2026）。
- **Part 3（アプリ層）**：`fire_app` を実装すると自動で有効化（未実装なら skip）。

現状、Part 1・2 は参照エンジンに対して**全21項目パス**を確認済み。
Part 3 は `fire_app` 実装後に有効になる。

## 実装（fire_app）

計算層は `fire_app/` に実装済み（SPEC.md 第8章の構成）。UI は計算層を呼ぶだけ。

| ファイル | 役割 |
| --- | --- |
| `fire_app/engine.py` | 数値エンジン。`swr_simulator.py` を正典として再利用（純粋関数・乱数管理） |
| `fire_app/finance.py` | `annual_withdrawal` / `tax_grossed_withdrawal` / `portfolio_weights` |
| `fire_app/recommend.py` | `current_success` / `required_asset` / `required_table` / `cash_to_bond_effect` / `recommend_actions` |
| `fire_app/ui.py` | Streamlit UI（入力フォーム＋結果表示） |

### セットアップ & テスト

```bash
pip install -r requirements.txt
pytest -q                 # Part 1・2・3（test_golden.py）+ test_fire_app.py が全緑
```

### アプリ起動

```bash
streamlit run fire_app/ui.py
```

入力：月生活費・月事業所得・NISA/特定/現金残高・防御資産(cash/bond)・株リターン(5/6/7%)・
目標成功率(80/90/95%)。
出力：年取崩額（税抜/税込）／現状資産の達成確度／目標額レンジ（成功率×株リターン）／
現金→債券の置換効果／注意書き。重いスイープは必要時のみ・キャッシュ付き。

## 注意

本アプリは投資助言ではない。結果は確率であって保証ではない。投資は自己責任で。
