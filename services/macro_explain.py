"""v19.202 P2-2 shim — services/macro_explain.py 已搬 services/macro/explain.py。"""
from __future__ import annotations

from services.macro import explain as _mod
for _name in dir(_mod):
    if not _name.startswith('__'):
        globals()[_name] = getattr(_mod, _name)
del _mod, _name
