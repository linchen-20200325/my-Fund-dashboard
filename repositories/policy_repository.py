"""v19.206 B2 shim — repositories/policy_repository.py 已拆 repositories/policy/ 子套件。

原 1372 LOC god module(V1 schema + V2 schema worksheet 管理 + sheet utilities +
V2 data normalization + backup)拆 3 子檔:
- repositories/policy/_helpers.py  (~190 LOC)
- repositories/policy/v1.py        (~280 LOC)
- repositories/policy/v2.py        (~940 LOC)

本檔留 shim re-export 確保 19+ production caller backward compat(`from
repositories.policy_repository import load_policies, ALL_COLS, ...`)。

第三階段 B2 同 B1 pattern:caller 端 module-level import,從 shim attribute 取
function references,patch shim attribute 對 caller 端 snapshot 有效;v1/v2
之間共用的 `_*` 私函集中 _helpers.py,規避 P2-4 v19.199 revert 主因
(from X import * 不取 `_*`)。
"""
from __future__ import annotations

from repositories import policy as _policy_pkg

for _name in dir(_policy_pkg):
    if not _name.startswith('__'):
        globals()[_name] = getattr(_policy_pkg, _name)
del _policy_pkg, _name
