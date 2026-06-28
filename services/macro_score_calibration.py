"""v19.201 P2-3 shim — services/macro_score_calibration.py 已搬 services/calibration/macro_score.py。"""
from __future__ import annotations

from services.calibration import macro_score as _mod
for _name in dir(_mod):
    if not _name.startswith('__'):
        globals()[_name] = getattr(_mod, _name)
del _mod, _name

# v19.201 P2-3:守 tests/test_macro_thresholds_v2.py SSOT import 字串
from shared.macro_thresholds_v2 import PMI_THRESHOLDS, CPI_YOY_THRESHOLDS, HY_SPREAD_THRESHOLDS  # noqa: F401
