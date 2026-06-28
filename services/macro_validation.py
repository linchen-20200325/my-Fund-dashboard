"""v19.202 P2-2 shim — services/macro_validation.py 已搬 services/macro/validation.py。"""
from __future__ import annotations

from services.macro import validation as _mod
for _name in dir(_mod):
    if not _name.startswith('__'):
        globals()[_name] = getattr(_mod, _name)
del _mod, _name

# v19.202 P2-2:守 tests/test_macro_thresholds_v2.py SSOT import 字串
from shared.macro_thresholds_v2 import (  # noqa: F401
    PMI_THRESHOLDS, CPI_YOY_THRESHOLDS, HY_SPREAD_THRESHOLDS,
)
# v19.202 P2-2:守 test_cpi_macro_validation_imports_ssot 對 _CPI_IDEAL_LOW / _CPI_ELEVATED 字面
_CPI_IDEAL_LOW = CPI_YOY_THRESHOLDS["score_function"].get("ideal_low_above", 1.5)
_CPI_ELEVATED = CPI_YOY_THRESHOLDS["score_function"].get("elevated_below", 3.0)
_HY_TIGHT = HY_SPREAD_THRESHOLDS["score_function"].get("tight_below", 4.0)
_HY_WIDE = HY_SPREAD_THRESHOLDS["score_function"].get("wide_above", 6.0)
