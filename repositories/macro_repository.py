"""v19.205 B1 shim — repositories/macro_repository.py 已拆 repositories/macro/ 子套件。

原 1078 LOC god module(FRED + Yahoo Finance + China + DefiLlama + AAII + ISM PMI +
macro_compass + 純數學工具)拆 5 子檔:
- repositories/macro/fred.py        (~320 LOC)
- repositories/macro/yf.py           (~80 LOC)
- repositories/macro/china.py        (~60 LOC)
- repositories/macro/alternate.py   (~500 LOC)
- repositories/macro/math_utils.py  (~155 LOC)

本檔留 shim re-export 確保 43+ production caller backward compat(`from
repositories.macro_repository import fetch_fred, fetch_yf_close, zscore, ...`)。

第三階段 B1 同步:test patch path 從 `repositories.macro_repository.X` 改成
`repositories.macro.<submodule>.X`(類 P1-1~P1-4 違憲修補模式),不再 patch
shim attribute(規避 P2-5 v19.199 revert 主因:patch.object(shim, attr) 不
穿透 sub-module 內部 reference)。
"""
from __future__ import annotations

from repositories import macro as _macro_pkg

for _name in dir(_macro_pkg):
    if not _name.startswith('__'):
        globals()[_name] = getattr(_macro_pkg, _name)
del _macro_pkg, _name
