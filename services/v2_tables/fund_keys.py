# -*- coding: utf-8 -*-
"""持倉體檢（hld）接真資料 S1：試算表的 `fund_code` → MoneyDJ `full_key`／`portal` 的決定性對照。

`nav_dividend.py` 要求呼叫端**明確**給 `full_key`（`49` §2.2：「Sheets 的 `fund_code` 能不能直接當
`full_key` 用，本組沒有查」）。本檔就是那個「明確給」的地方：照舊頁的決定性做法逐步轉換，
**對不上就回錯誤，不截斷、不猜**。本檔不取數、不寫試算表、不另疊快取，**不改任何 L1**。

**對照鏈（總管裁定，依序；每一步都是決定性的）**：
1. `str.strip()` → 2. `str.upper()`；
3. `repositories/fund/sources.py::parse_moneydj_input`（取 `code`；`page_type` 本檔不用）；
4. `repositories/fund/sources.py::load_fund_code_mapping`（或呼叫端注入的對照表）：
   `code` 命中 → `full_key` 取對照值的 `public_code`；未命中 → `full_key` 原樣用 `code`；
5. `portal` 一律 `""`。
⚠️ 舊單檔頁的編排（`repositories/fund/fund_orchestration.py`）在第 3 步之前**另有**
   `canonicalize_moneydj_url`（只動行動版／平台行動頁的網址，會把平台後綴去掉）。
   總管裁定的鏈**不含**這一步，本檔照裁定，不自行加上。

**兜底判法（`parse_moneydj_input` 的 `_raw[:30]` 那一支）**：
讀 L1 原始碼（非網址分支）：先 `_raw = text.upper().strip()`，再以
`^([A-Z0-9]{3,30}(?:-[A-Z0-9]{2,20})?)$` 做 `re.match`；**合 → `code` 為整段**；
**不合 → `code = _raw[:30]`**（兜底，可能截斷，也可能把空白、標點原樣留著）。
L1 的回傳字典**沒有**標記走了哪一支，所以本檔照同一條規則重判一次（`_is_pure_code`）：
- 非網址輸入：正規化後的輸入符合該規則**且** L1 給的 `code` 與它逐字相同 → 成功；
  否則一律判為「走到兜底」→ 錯誤（不取 `_raw[:30]`）。
- 網址輸入：L1 以 `[?&][aA]=([A-Z0-9a-z][A-Z0-9a-z\\-]{1,29})` 做**未錨定**的 `search`，
  `a=` 的值超過 30 字元時會**靜默截成前 30 字元**（與兜底同一種病）。本檔另查
  `?A=<code>`／`&A=<code>` 後面緊接的字元：沒有任何一處是「字串結尾或非代碼字元」→ 判為截斷 → 錯誤。
  抽不出代碼 → 錯誤。
⚠️ `services/v2_tables` 的 import 白名單（`tests/test_v2_tables_market_indicator.py`）不含 `re`，
   所以 `_is_pure_code` 以字元集合手寫同一條規則；`PURE_CODE_PATTERN` 只當文件與測試的比對基準：
   測試會 (a) 逐字比對它與 L1 原始碼、(b) 拿 `re.fullmatch(PURE_CODE_PATTERN, …)` 與 `_is_pure_code` 對拍。

**provenance（對照表用的是哪一份）**：`load_fund_code_mapping` 讀 `fund_code_mapping.csv`
（相對於當下工作目錄）；檔不存在時**不出聲**、讀取失敗時只 `print` 後退回內建表；回傳不帶來源。
總管裁定**不改 L1**，本檔以「回傳內容是否與 L1 內建表 `_DEFAULT_MAPPING` 完全相同」判別：
- 相同 → `"builtin"`（csv 不存在，**或** csv 讀取失敗而退回內建表 —— 這兩種本層**分辨不出來**；
  也包括 csv 內容恰與內建表一致的情形）。L1 的 `print` 照原樣印在標準輸出，本檔不攔、不吞；
- 不同 → `"csv+builtin"`（csv 有讀進來並改動了對照內容）；
- 呼叫端注入對照表 → `"injected"`（不呼叫 L1）。

規則（`CLAUDE.md` §1）：不補值、不吞例外（L1 拋例外就往上拋）。逐檔失敗只放錯誤原因，
不給 `full_key`；`fund_codes` 本身不是串列／元組 → 直接 `TypeError`（字串會被逐字拆開，不能收）。
"""

from __future__ import annotations

from typing import Optional

from repositories.fund.sources import _DEFAULT_MAPPING, load_fund_code_mapping, parse_moneydj_input


# 與 `parse_moneydj_input` 非網址分支的正則逐字相同（測試以原始碼比對、並與 `_is_pure_code` 對拍）。
PURE_CODE_PATTERN = r"^([A-Z0-9]{3,30}(?:-[A-Z0-9]{2,20})?)$"
_CODE_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
_URL_CODE_CHARS = _CODE_CHARS | frozenset("abcdefghijklmnopqrstuvwxyz-")

PORTAL_DEFAULT = ""  # 總管裁定：portal 一律空字串

MAPPING_SOURCE_BUILTIN = "builtin"
MAPPING_SOURCE_CSV = "csv+builtin"
MAPPING_SOURCE_INJECTED = "injected"

PARSER_NAME = "repositories.fund.sources.parse_moneydj_input"


def _chars_ok(part: str, lo: int, hi: int) -> bool:
    return lo <= len(part) <= hi and all(ch in _CODE_CHARS for ch in part)


def _is_pure_code(text: str) -> bool:
    """`PURE_CODE_PATTERN` 的手寫等價：主碼 3–30 個大寫英數，可再接一個 `-` 與 2–20 個大寫英數。"""
    if not isinstance(text, str):
        return False
    head, sep, tail = text.partition("-")
    if not sep:
        return _chars_ok(head, 3, 30)
    return _chars_ok(head, 3, 30) and _chars_ok(tail, 2, 20)


def _load_mapping_with_provenance():
    mapping = load_fund_code_mapping()  # L1 例外不攔，往上拋
    source = MAPPING_SOURCE_BUILTIN if mapping == _DEFAULT_MAPPING else MAPPING_SOURCE_CSV
    return mapping, source


def _fail(raw, reason: str, code: Optional[str] = None) -> dict:
    return {"input": raw, "ok": False, "full_key": None, "portal": None,
            "parsed_code": code, "mapping_hit": False, "error": reason}


def _url_code_truncated(text: str, code: str) -> bool:
    """L1 的網址正則未錨定：`a=` 後的值超過 30 字元時會被截。

    `text` 已轉大寫。找 `?A=<code>`／`&A=<code>`：只要有一處後面是字串結尾或非代碼字元 → 未截斷。
    """
    for prefix in ("?A=", "&A="):
        needle = prefix + code
        start = text.find(needle)
        while start != -1:
            nxt = start + len(needle)
            if nxt == len(text) or text[nxt] not in _URL_CODE_CHARS:
                return False
            start = text.find(needle, start + 1)
    return True


def _resolve_one(raw, mapping: dict) -> dict:
    if not isinstance(raw, str):
        return _fail(raw, f"fund_code 須為字串（收到 {type(raw).__name__}：{raw!r}）")
    text = raw.strip().upper()
    if not text:
        return _fail(raw, "fund_code 為空字串（或只有空白）")

    info = parse_moneydj_input(text)
    code = info.get("code", "")
    if not isinstance(code, str):
        return _fail(raw, f"parse_moneydj_input 回傳的 code 不是字串（{code!r}）")

    if info.get("is_url"):
        if not code:
            return _fail(raw, "網址中抽不出 MoneyDJ 代碼（找不到 ?a= 或 &a= 參數）")
        if _url_code_truncated(text, code):
            return _fail(raw, f"網址的 a= 參數超過 30 字元，parse_moneydj_input 會截成 {code!r}；"
                              "不截斷、不猜", code)
    else:
        if code != text or not _is_pure_code(text):
            return _fail(raw, f"代碼格式不符 {PURE_CODE_PATTERN}，parse_moneydj_input 會走 30 字元兜底"
                              f"（得 {code!r}）；不截斷、不猜", code)

    hit = code in mapping
    if hit:
        entry = mapping[code]
        pub = entry.get("public_code") if isinstance(entry, dict) else None
        if not isinstance(pub, str) or not pub.strip() or pub != pub.strip():
            return _fail(raw, f"對照表 {code!r} 的 public_code 不合格（{pub!r}）；不補值", code)
        full_key = pub
    else:
        full_key = code
    return {"input": raw, "ok": True, "full_key": full_key, "portal": PORTAL_DEFAULT,
            "parsed_code": code, "mapping_hit": hit, "error": None}


def resolve_full_keys(fund_codes, *, mapping=None) -> dict:
    """`fund_codes`（串列／元組）→ 逐檔 `full_key`／`portal` 或錯誤原因，另附 provenance。

    回傳::

        {
          "results": [            # 與輸入同序、同長度；重複輸入各自一筆
            {"input": 原值, "ok": bool,
             "full_key": str | None, "portal": "" | None,
             "parsed_code": parse_moneydj_input 給的 code（失敗時可能為 None）,
             "mapping_hit": bool, "error": str | None},
            ...
          ],
          "provenance": {
            "mapping_source": "builtin" | "csv+builtin" | "injected"（判法見檔頭）,
            "mapping_size": 對照表筆數,
            "parser": "repositories.fund.sources.parse_moneydj_input",
          },
        }

    `mapping`：注入的對照表（`{代碼: {"public_code": ...}}`，形狀同 `load_fund_code_mapping`）；
    給了就不呼叫 L1。對照表在單次呼叫內只讀一次。
    """
    if not isinstance(fund_codes, (list, tuple)):
        raise TypeError(f"fund_codes 須為 list 或 tuple（收到 {type(fund_codes).__name__}）")
    if mapping is None:
        table, source = _load_mapping_with_provenance()
    else:
        if not isinstance(mapping, dict):
            raise TypeError(f"mapping 須為 dict（收到 {type(mapping).__name__}）")
        table, source = mapping, MAPPING_SOURCE_INJECTED
    results = [_resolve_one(raw, table) for raw in fund_codes]
    return {
        "results": results,
        "provenance": {"mapping_source": source, "mapping_size": len(table),
                       "parser": PARSER_NAME},
    }
