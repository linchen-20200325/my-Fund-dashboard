"""repositories.macro — B1 v19.205 子套件,從 macro_repository 1078 LOC 拆 5 子檔。

子檔分配:
- fred.py        FRED series 抓取 (cache helpers + fetch_fred / fetch_fred_batch / next_release_date + MACRO_THRESHOLDS dict)
- yf.py          Yahoo Finance Chart API (fetch_yf_close / fetch_yf_latest)
- china.py       China macro batch (_CHINA_FRED_SPECS + fetch_china_macro)
- alternate.py   DefiLlama + AAII + ISM PMI + macro_compass
- math_utils.py  純數學工具 (zscore / trend_arrow / recession_probability / spread_series / make_indicator / flatten_snapshot)

dir+globals re-export 涵蓋 _* 私函,確保既有 `from repositories.macro_repository import X` 工作。
"""
from __future__ import annotations

from . import alternate, china, fred, math_utils, yf

for _mod in (fred, yf, china, alternate, math_utils):
    for _name in dir(_mod):
        if not _name.startswith('__'):
            globals()[_name] = getattr(_mod, _name)
del _mod, _name
