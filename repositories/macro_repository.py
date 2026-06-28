"""v19.203 P2-5 shim — repositories/macro_repository.py 已拆 repositories/macro/ 子套件。

原 1078 LOC 拆 5 子檔 + __init__:
- _helpers.py / fred.py / yf.py / alternate.py(Defillama+AAII+ISM+compass+China)/ math_utils.py

本檔保留為 backward-compat shim。
"""
from __future__ import annotations

from repositories import macro as _macro_pkg

for _name in dir(_macro_pkg):
    if not _name.startswith('__'):
        globals()[_name] = getattr(_macro_pkg, _name)
del _name
