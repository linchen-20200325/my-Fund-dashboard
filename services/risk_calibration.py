"""v19.201 P2-3 shim — services/risk_calibration.py 已搬 services/calibration/risk.py。"""
from __future__ import annotations

from services.calibration import risk as _mod
for _name in dir(_mod):
    if not _name.startswith('__'):
        globals()[_name] = getattr(_mod, _name)
del _mod, _name
