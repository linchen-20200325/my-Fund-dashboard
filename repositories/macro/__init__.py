"""repositories/macro 子套件 — v19.203 P2-5 從 macro_repository.py 1078 LOC 拆出。"""
from __future__ import annotations

from repositories.macro import _helpers, fred, yf, alternate, math_utils

for _mod in (_helpers, fred, yf, alternate, math_utils):
    for _name in dir(_mod):
        if not _name.startswith('__'):
            globals()[_name] = getattr(_mod, _name)
del _mod, _name
