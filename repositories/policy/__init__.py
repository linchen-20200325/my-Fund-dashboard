"""repositories.policy — B2 v19.206 子套件,從 policy_repository 1372 LOC 拆 3 子檔。

子檔分配:
- _helpers.py    共用 imports/常數/PolicySheetError/retry/client/_normalize_*/_open_worksheet
- v1.py          V1 schema(load_policies + upsert_policy_row + delete_policy_row +
                 _find_row_index + _extract_code_from_url + sync_policies_to_portfolio_funds)
- v2.py          V2 schema(worksheet 管理 + sheet utilities + data normalization +
                 load/write_policy_v2 + load_all_policies_v2 + copy_sheet_as_backup)

dir+globals re-export 涵蓋 _* 私函,確保既有 `from repositories.policy_repository import X` work。
"""
from __future__ import annotations

from . import _helpers, v1, v2

for _mod in (_helpers, v1, v2):
    for _name in dir(_mod):
        if not _name.startswith('__'):
            globals()[_name] = getattr(_mod, _name)
del _mod, _name
