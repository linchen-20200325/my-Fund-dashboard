"""repositories/fund 子套件 — v19.200 P1-5 從 fund_repository.py 5117 LOC god module 拆出。

結構:
- `_helpers`:module-level imports + 常數
- `sources`:全部 _src_* + tdcc_* + code mapping(80-2451)
- `fund_orchestration`:_fetch_fund_single + fetch_fund_from_moneydj_url + search(2452-3554)
- `nav_metrics`:NAV history + perf/risk/holdings/div(3555-4546)
- `fx_and_main`:fetch_fund_by_* + get_latest_fx + get_latest_nav(4547-5117)
- 本 __init__:re-export 全部公開 fn(含 _* 私函)

70+ caller 透過 repositories/fund_repository.py shim re-export 取得 fn,patch path 不需改。
"""
from __future__ import annotations

from repositories.fund import sources, fund_orchestration, nav_metrics, fx_and_main

# Re-export 全部 attributes(含 _* 私函)— `import *` 預設不會 re-export _ 開頭,
# 改用 setattr globals 動態 expose 保持 backward compat
for _mod in (sources, fund_orchestration, nav_metrics, fx_and_main):
    for _name in dir(_mod):
        if not _name.startswith('__'):
            globals()[_name] = getattr(_mod, _name)
del _mod, _name
