# -*- coding: utf-8 -*-
"""`tests/fixtures/nav_table_golden_before_c3a.json`（C3a 淨值單表黃金檔）的錄製腳本（測試共用；不是測試檔）。

用途：`build_nav_table`（`with_dividends=False`；alo 與設定頁走這條，取數經 `fetch_nav_chain_with_error`）在 C3a
改動前後輸出**逐位元組相同**。`tests/fixtures/nav_dividend_golden_before_c3a.json` 只錄了
`build_nav_dividend_tables`（`fetch_chain_with_error` 那條），淨值單表那條沒有基準 —— 本檔補上。

情境沿用 `tests/_nav_dividend_golden_c3a.py` 的 `chain:*` 與 `res:*` 兩組（呼叫端只給 `holding_ccy`，全部是 hld 會走到的
程式碼）；`pure:*` 是直接呼叫純函式、不經 `build_nav_table`，不適用、不收。

用法（repo 根目錄，在**要當基準的那個版本**上執行；不打網路、不讀試算表）::

    python tests/_nav_table_golden_c3a.py <輸出 JSON 路徑>

需要同目錄的 `tests/_nav_dividend_golden_c3a.py`（情境矩陣）與 `tests/_a_chain_stub.py`（A 鏈來源替身）。
⚠️ 不得用改動後的程式重錄來「讓測試變綠」—— 那會讓「改動前後逐位元組相同」變成循環論證。
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _nav_dividend_golden_c3a as G  # noqa: E402


def case_names() -> list:
    G._setup_path()
    return sorted([*G.chain_cases(), *G.res_cases()])


def run_case(name):
    """跑單一情境：`build_nav_table(funds, now=NOW)` 的整個回傳值（未序列化）。"""
    G._setup_path()
    from _pytest.monkeypatch import MonkeyPatch
    import _a_chain_stub as H
    from services.v2_tables import nav_dividend as ND

    kind = name.split(":", 1)[0]
    mp = MonkeyPatch()
    try:
        if kind == "chain":
            funds, scenario = G.chain_cases()[name]
            H.install(mp, scenario)
        elif kind == "res":
            funds, by_code = G.res_cases()[name]
            mp.setattr(ND, "auto_fetch_moneydj", lambda code, return_page_type=False: (by_code[code], "yp010000"))
        else:
            raise ValueError(f"淨值單表黃金檔不收這種情境：{name!r}")
        return G._quiet(ND.build_nav_table, funds, now=G.NOW)
    finally:
        mp.undo()


def record(out_path: str) -> dict:
    golden = {name: json.loads(G.dumps(run_case(name))) for name in case_names()}
    pathlib.Path(out_path).write_text(G.dumps(golden), encoding="utf-8")
    return golden


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("用法：python tests/_nav_table_golden_c3a.py <輸出 JSON 路徑>")
    g = record(sys.argv[1])
    print("ok", len(g), "cases")
