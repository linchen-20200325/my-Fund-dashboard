# -*- coding: utf-8 -*-
"""持倉體檢（hld）接真資料 S1：試算表的 `fund_code` → MoneyDJ `full_key`／`portal` 的決定性對照。

`nav_dividend.py` 要求呼叫端**明確**給 `full_key`（`49` §2.2：「Sheets 的 `fund_code` 能不能直接當
`full_key` 用，本組沒有查」）。本檔就是那個「明確給」的地方：照舊頁的決定性做法逐步轉換，
**對不上就回錯誤，不截斷、不猜**。本檔不取數、不寫試算表、不另疊快取，**不改任何 L1**。

**對照鏈（總管裁定，依序；每一步都是決定性的）**：
0. 輸入須為字串、去掉前後空白後非空，且**全為 ASCII**（`str.isascii()`）—— 否則判失敗。
   理由：`str.upper()` 會做 Unicode 大小寫展開，`ß`→`SS`、`ı`（無點 i）→`I`、`ﬀ`→`FF`、`ſ`→`S`，
   非 ASCII 輸入會被轉成「看起來合格」的代碼（例：`actı171` 會變成內建表命中的 `ACTI171`）。
   檢查放在 `upper()` **之前**，轉換後就看不出來了。
1. `str.strip()` → 2. `str.upper()`；
3. `repositories/fund/sources.py::parse_moneydj_input`（取 `code`；`page_type` 本檔不用）；
4. `repositories/fund/sources.py::load_fund_code_mapping`（或呼叫端注入的對照表）：
   `code` 命中 → `full_key` 取對照值的 `public_code`；未命中 → `full_key` 原樣用 `code`；
5. **最終關卡**：不論走哪條路徑，`full_key` 都要再過一次 `_is_pure_code`，不合格判失敗；
6. `portal` 一律 `""`。

⚠️ **少掉的一步**：舊單檔頁的編排（`repositories/fund/fund_orchestration.py`）在第 3 步之前**另有**
   `canonicalize_moneydj_url`。總管裁定的鏈不含這一步，本檔照裁定，不自行加上。讀 L1 原始碼，該函式
   只對 `http` 開頭、且符合四種行動版樣式（`://m.moneydj.com/`、`.moneydj.com/mobile/`、`/a1.aspx`、
   `/mobile/b1.aspx`）的網址動手，把 `a=` 的值截到第一個 `-` 之前（去平台後綴）。所以**少掉這一步，
   只影響「行動版網址＋平台後綴」的輸入**：舊頁得到主碼（例 `ACDD01`），本檔得到含後綴的整段
   （例 `ACDD01-EQTAL005`）。純代碼、桌面版網址、沒有後綴的行動版網址，兩邊的 `full_key` 一樣
   （`page_type` 會不同，但本檔不用）。

**兜底判法（`parse_moneydj_input` 的 `_raw[:30]` 那一支）**：
讀 L1 原始碼（非網址分支）：先 `_raw = text.upper().strip()`，再以
`^([A-Z0-9]{3,30}(?:-[A-Z0-9]{2,20})?)$` 做 `re.match`；**合 → `code` 為整段**；
**不合 → `code = _raw[:30]`**（兜底，可能截斷，也可能把空白、標點原樣留著）。
L1 的回傳字典**沒有**標記走了哪一支，所以本檔照同一條規則重判一次（`_is_pure_code`）：
非網址輸入符合該規則**且** L1 給的 `code` 與它逐字相同 → 成功；否則一律判為「走到兜底」→ 錯誤。
⚠️ **這比舊頁嚴**：舊頁（`fund_orchestration.py`）只在 `code` 為空時才報錯，兜底給的值照用。
   例：`TLZF9 X`（中間空白）舊頁的 `full_key` 是 `TLZF9 X`；31 個 `A` 舊頁會截成 30 個 `A`；
   `AB`（主碼只有 2 字元）舊頁原樣用 `AB`。這三個本檔都判失敗。

**網址輸入**：L1 以 `[?&][aA]=([A-Z0-9a-z][A-Z0-9a-z\\-]{1,29})` 做**未錨定**的 `search`，
有三個漏洞，本檔分別擋：
- 值後面接什麼都收 → 例 `?a=ACTI71%20X` L1 給 `ACTI71`、`?a=` 超過 30 字元靜默截斷。
  本檔把每個 `?A=`／`&A=`（已轉大寫，故 `a=`／`A=` 混用都算）的值取到下一個 `&`、`#` 或字串結尾，
  **該值必須與 L1 的 `code` 逐字相同**，否則判失敗。
- 網址裡出現兩個以上的 `a=`：值都相同 → 照收；任一不同 → 判失敗（不猜 L1 取了哪一個）。
- L1 的字元類允許 `-` 任意出現、長度下限 2 → `AB`、`A-`、`A--------` 都能被抽出來。由第 5 步擋。
抽不出代碼 → 錯誤。

**對照表的值**：`public_code` 須為字串、通過 `_is_pure_code`，且不是 `NAN`／`NONE`。
理由：L1 讀 csv 時寫的是 `str(row.get("public_code", k)).upper().strip()`。
本組 2026-10-02 實測：csv 的 `public_code` 格留空 → pandas 讀成 NaN → `str(nan)` ＝ `"nan"` →
`"NAN"`，而 `NAN` 本身符合代碼字元規則，`_is_pure_code` 擋不下。`NONE` 是同一條路徑上
`str(None)` 的產物；本組實測 `read_csv` 留空格得到的是 NaN 而不是 None，`NONE` 是防禦性一併擋下。
（只有空白的格經 `.strip()` 會變成 `""`，由「非空」那一關擋。）

**注入的對照表**：鍵必須是字串（否則 `TypeError`）且通過 `_is_pure_code`（否則 `ValueError`）。
查表用的 `code` 一定是大寫且合格，鍵若是小寫或帶空白就永遠對不到 —— 不讓它靜默對不到。
（L1 讀出的表不做這項檢查：鍵由 L1 自己 `upper().strip()` 過。）

**`_is_pure_code` 與 L1 正則的對拍**：`services/v2_tables` 的 import 白名單
（`tests/test_v2_tables_market_indicator.py`）不含 `re`，所以手寫同一條規則；`PURE_CODE_PATTERN`
只當文件與測試的比對基準。測試用 `re.fullmatch` 對拍，**不用 `re.match`**：L1 的 `^…$` 配 `re.match`
時，`$` 會匹配字串尾端那一個 `\\n` 之前，所以 `"ABC\\n"` 在 `re.match` 下算符合；本檔進 L1 前已
`strip()`，結尾換行到不了那一行，等價的判準是「整段完全符合」＝ `fullmatch`。

**provenance（對照表用的是哪一份）**：`load_fund_code_mapping` 讀 `fund_code_mapping.csv`
（相對於當下工作目錄）；檔不存在時不出聲、讀取失敗時只 `print` 後退回內建表；回傳不帶來源。
總管裁定**不改 L1**，本檔把它的回傳與 `load_fund_code_mapping(path="")` 比對：讀 L1 原始碼，
`os.path.exists("")` 為假，直接回 `dict(_DEFAULT_MAPPING)` 的複本、不 `print`（本組 2026-10-02 實測：
無輸出、內容與內建表相同）。
- 相同 → `"builtin"`（csv 不存在，**或** csv 讀取失敗而退回內建表 —— 這兩種本層**分辨不出來**；
  也包括 csv 內容恰與內建表一致的情形）。L1 的 `print` 照原樣印在標準輸出，本檔不攔、不吞；
- 不同 → `"csv+builtin"`（csv 有讀進來並改動了對照內容）；
- 呼叫端注入對照表 → `"injected"`（不呼叫 L1）。

規則（`CLAUDE.md` §1）：不補值、不吞例外（L1 拋例外就往上拋）。逐檔失敗只放錯誤原因，
不給 `full_key`；`fund_codes` 本身不是串列／元組 → 直接 `TypeError`（字串會被逐字拆開，不能收）。
"""

from __future__ import annotations

from typing import Optional

from repositories.fund.sources import load_fund_code_mapping, parse_moneydj_input


# 與 `parse_moneydj_input` 非網址分支的正則逐字相同（測試以原始碼比對、並與 `_is_pure_code` 對拍）。
PURE_CODE_PATTERN = r"^([A-Z0-9]{3,30}(?:-[A-Z0-9]{2,20})?)$"
_CODE_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")

# L1 讀 csv 時 `str(NaN)`／`str(None)` 的產物，形狀合格但不是代碼（見檔頭）。
_STRINGIFIED_MISSING = frozenset({"NAN", "NONE"})

# 網址裡 `a=` 的值只能以這些字元（或字串結尾）收尾。
_URL_VALUE_TERMINATORS = ("&", "#")

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
    builtin = load_fund_code_mapping(path="")  # 不讀檔、不 print，只回內建表複本（見檔頭）
    source = MAPPING_SOURCE_BUILTIN if mapping == builtin else MAPPING_SOURCE_CSV
    return mapping, source


def _check_injected_mapping(mapping) -> None:
    if not isinstance(mapping, dict):
        raise TypeError(f"mapping 須為 dict（收到 {type(mapping).__name__}）")
    for key in mapping:
        if not isinstance(key, str):
            raise TypeError(f"mapping 的鍵須為字串（收到 {type(key).__name__}：{key!r}）")
        if not _is_pure_code(key):
            raise ValueError(f"mapping 的鍵 {key!r} 不符 {PURE_CODE_PATTERN}（須為大寫、無空白）；"
                             "查表用的代碼一定是大寫合格碼，這個鍵永遠對不到")


def _fail(raw, reason: str, code: Optional[str] = None) -> dict:
    return {"input": raw, "ok": False, "full_key": None, "portal": None,
            "parsed_code": code, "mapping_hit": False, "error": reason}


def _url_a_values(text: str) -> list:
    """`text` 已轉大寫。回傳每個 `?A=`／`&A=` 的值（取到下一個 `&`、`#` 或字串結尾），依出現順序。"""
    values = []
    for i in range(len(text) - 2):
        if text[i] in "?&" and text[i + 1:i + 3] == "A=":
            start = i + 3
            end = len(text)
            for term in _URL_VALUE_TERMINATORS:
                pos = text.find(term, start)
                if pos != -1 and pos < end:
                    end = pos
            values.append(text[start:end])
    return values


def _resolve_one(raw, mapping: dict) -> dict:
    if not isinstance(raw, str):
        return _fail(raw, f"fund_code 須為字串（收到 {type(raw).__name__}：{raw!r}）")
    stripped = raw.strip()
    if not stripped:
        return _fail(raw, "fund_code 為空字串（或只有空白）")
    if not stripped.isascii():
        return _fail(raw, "fund_code 含非 ASCII 字元；upper() 會做 Unicode 展開（例 ß→SS、ı→I），不猜")
    text = stripped.upper()

    info = parse_moneydj_input(text)
    code = info.get("code", "")
    if not isinstance(code, str):
        return _fail(raw, f"parse_moneydj_input 回傳的 code 不是字串（{code!r}）")

    if info.get("is_url"):
        if not code:
            return _fail(raw, "網址中抽不出 MoneyDJ 代碼（找不到 ?a= 或 &a= 參數）")
        values = _url_a_values(text)
        if len(set(values)) > 1:
            return _fail(raw, f"網址裡有多個 a= 且值不同（{values!r}）；不猜取哪一個", code)
        if values != [] and values[0] != code:
            return _fail(raw, f"網址的 a= 值 {values[0]!r} 與 parse_moneydj_input 抽出的 {code!r} 不同"
                              "（值後面只能接 &、# 或結尾；超過 30 字元會被截）；不截斷、不猜", code)
        if not values:
            return _fail(raw, f"網址裡找不到 ?a=／&a=，無法核對 parse_moneydj_input 抽出的 {code!r}", code)
    else:
        if code != text or not _is_pure_code(text):
            return _fail(raw, f"代碼格式不符 {PURE_CODE_PATTERN}，parse_moneydj_input 會走 30 字元兜底"
                              f"（得 {code!r}）；不截斷、不猜", code)

    hit = code in mapping
    if hit:
        entry = mapping[code]
        pub = entry.get("public_code") if isinstance(entry, dict) else None
        if not isinstance(pub, str) or pub in _STRINGIFIED_MISSING:
            return _fail(raw, f"對照表 {code!r} 的 public_code 不合格（{pub!r}）；不補值", code)
        full_key = pub
    else:
        full_key = code

    if not _is_pure_code(full_key):  # 最終關卡：三條路徑一律再驗
        source = f"對照表 {code!r} 的 public_code" if hit else "抽出的代碼"
        return _fail(raw, f"{source} {full_key!r} 不符 {PURE_CODE_PATTERN}；不補值、不猜", code)
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
    給了就不呼叫 L1；鍵不合格 → `TypeError`／`ValueError`。對照表在單次呼叫內只讀一次。
    """
    if not isinstance(fund_codes, (list, tuple)):
        raise TypeError(f"fund_codes 須為 list 或 tuple（收到 {type(fund_codes).__name__}）")
    if mapping is None:
        table, source = _load_mapping_with_provenance()
    else:
        _check_injected_mapping(mapping)
        table, source = mapping, MAPPING_SOURCE_INJECTED
    results = [_resolve_one(raw, table) for raw in fund_codes]
    return {
        "results": results,
        "provenance": {"mapping_source": source, "mapping_size": len(table),
                       "parser": PARSER_NAME},
    }
