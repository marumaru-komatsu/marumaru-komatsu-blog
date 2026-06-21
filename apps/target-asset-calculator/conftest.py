"""conftest.py — pytest 実行時にリポジトリ直下を import パスへ追加する。

tests/test_golden.py が直下の `swr_simulator` を、test_fire_app.py / test_app_layer.py が
`fire_app` を import する。pytest の既定 import モードは tests/ ディレクトリのみを
sys.path に入れるため、直下のモジュールが見つからない（ModuleNotFoundError）。
本ファイル（直下に置く conftest.py）でリポジトリ直下を明示的にパスへ追加して解決する。
import モード・pytest バージョンに依存しない確実な方法。
"""
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
