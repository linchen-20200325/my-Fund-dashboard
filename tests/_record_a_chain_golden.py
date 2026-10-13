# -*- coding: utf-8 -*-
"""錄製 `tests/fixtures/a_chain_golden_before.json`（A 鏈黃金檔）的腳本（不是測試檔）。

用法（repo 根目錄，在**要當基準的那個版本**上執行；不打網路，全部來源走 `tests/_a_chain_stub.py` 的替身）::

    python tests/_record_a_chain_golden.py <輸出 JSON 路徑>

2026-10-13：黃金檔是在 `1586a45`（改動前）以本腳本的同一套邏輯錄的。stub 工具對 `cache_clear` 用 `getattr`
相容，所以本腳本可以在 base 上重錄（base 的 L1 沒有快取）。⚠️ 不得用改動後的程式重錄來「讓測試變綠」——
那會讓「改動前後逐欄相同」變成循環論證。
"""

from __future__ import annotations

import contextlib
import io
import json
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[1]


def record(out_path: str) -> dict:
    sys.path.insert(0, str(_ROOT))
    sys.path.insert(0, str(_ROOT / "tests"))
    import fund_fetcher  # noqa: F401  —— 先解開既有的循環 import（同 tests/conftest.py）
    from _pytest.monkeypatch import MonkeyPatch

    import _a_chain_stub as H
    from repositories.fund.fund_orchestration import fetch_fund_from_moneydj_url
    from services.moneydj_fetcher import auto_fetch_moneydj

    drop = H.VOLATILE_TOP_KEYS
    golden = {}
    for name, (code, sc) in H.scenarios().items():
        mp = MonkeyPatch()
        try:
            calls = H.install(mp, sc)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                res, pt = auto_fetch_moneydj(code, return_page_type=True)
            a_calls = list(calls)
            calls.clear()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                raw = fetch_fund_from_moneydj_url(code)
            golden[name] = {"page_type": pt, "auto": H.normalize(res, drop=drop),
                            "l1": H.normalize(raw, drop=drop), "auto_calls": [list(c) for c in a_calls],
                            "l1_calls": [list(c) for c in calls]}
        finally:
            mp.undo()
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(golden, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    return golden


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("用法：python tests/_record_a_chain_golden.py <輸出 JSON 路徑>")
    g = record(sys.argv[1])
    print("ok", {k: (v["page_type"], len(v["auto_calls"])) for k, v in g.items()})
