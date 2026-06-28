"""v19.200 P1-5 shim — repositories/fund_repository.py 已拆 repositories/fund/ 子套件。

原 5117 LOC god module 拆 5 子檔 + __init__:
- `repositories/fund/_helpers.py`(60 LOC)— module-level imports + 常數
- `repositories/fund/sources.py`(2406)— 全部 _src_* + 各 source helper
- `repositories/fund/fund_orchestration.py`(1137)— 主編排 + search
- `repositories/fund/nav_metrics.py`(1024)— NAV history + perf/risk/holdings/div
- `repositories/fund/fx_and_main.py`(603)— fetch_fund_by_* + FX/NAV helper
- `repositories/fund/__init__.py`(~25)— re-export 全部公開 fn + _* 私函

本檔保留為 backward-compat shim 確保 70+ caller 不需改 import path。
OOP `FundSourceAdapter` ABC + 10 子類重構(藍圖 §3.4)留 P2 後續迭代。
"""
from __future__ import annotations

from repositories import fund as _fund_pkg

# 透明 forward 全部 attribute(含 _* 私函)— `from X import *` 預設不 re-export
# `_` 開頭,改用 setattr globals 動態 expose
for _name in dir(_fund_pkg):
    if not _name.startswith('__'):
        globals()[_name] = getattr(_fund_pkg, _name)
del _name
