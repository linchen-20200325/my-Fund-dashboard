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
   （例 `ACDD01-EQTAL005`）。這一句只講 canonicalize 這一步的差別；**兩邊結果還有其他不同之處**，
   集中列在下一段，不得把本段讀成「其餘輸入兩邊都一樣」。

**⚠️ 本檔比舊頁嚴的地方（本組逐項讀 `fund_orchestration.py` 核對過的；不是窮舉）**：
舊頁在**代碼解析這一步**只在 `code` 為空時才報錯，其餘照用（第 5 步那種最終複驗舊頁沒有）。
下列輸入舊頁會給出 `full_key`，本檔判失敗：
1. **兜底**：`TLZF9 X`（中間空白）舊頁用 `TLZF9 X`；31 個 `A` 舊頁截成 30 個 `A`；`AB`、`AB-CD`
   （主碼 2 字元）舊頁原樣用。
2. **非 ASCII**：`actı171` 舊頁經 `upper()` 變成 `ACTI171`，再查表得 `ACTI71`。
3. **網址 `a=` 核對**：`?a=ACTI71%20X` 舊頁用 `ACTI71`；`a=` 超過 30 字元舊頁截成前 30；
   兩個 `a=` 值不同時舊頁取 L1 正則第一個符合的那一個；`?a=AB`、`?a=A-` 舊頁照用。
4. **查詢字串限定**：`https://x/p1&a=FOO123`、`https://x/#&a=FOO123`、`https://x/?x=1?a=FOO123`
   （第二個 `?` 不是參數分隔，`a=` 落在 `x` 的值裡）、`https://u:p?w@x/?a=FOO123`
   （第一個 `?` 在帳密裡，查詢字串從那裡起算，`a` 成了第一個參數名稱 `w@x/?a` 的一部分）
   這幾例的 `a=` 都不屬於查詢字串裡名稱為 `a` 的參數，舊頁照用 L1 抽到的 `FOO123`。
5. **對照表值**：`public_code` 是 `NAN` 或空字串時，舊頁照用該值（`code = _m.get("public_code", code)`）。
   舊頁只讀 L1 的表，L1 對值做的是 `upper().strip()`：
   - 小寫、**前後**空白 → 舊頁碰不到（L1 已轉大寫、去掉前後空白），只會出現在本檔的注入表；
   - **中間**空白 → L1 不處理，舊頁照用。本組 2026-10-02 實測：csv 的 `public_code` 填 `acti 71`，
     L1 讀出 `'ACTI 71'`，舊頁的 `full_key` 就是 `ACTI 71`；本檔由第 5 步最終關卡擋下。
其他輸入兩邊是否一致，本組沒有逐一比對。

**兜底判法（`parse_moneydj_input` 的 `_raw[:30]` 那一支）**：
讀 L1 原始碼（非網址分支）：先 `_raw = text.upper().strip()`，再以
`^([A-Z0-9]{3,30}(?:-[A-Z0-9]{2,20})?)$` 做 `re.match`；**合 → `code` 為整段**；
**不合 → `code = _raw[:30]`**（兜底，可能截斷，也可能把空白、標點原樣留著）。
L1 的回傳字典**沒有**標記走了哪一支，所以本檔照同一條規則重判一次（`_is_pure_code`）：
非網址輸入符合該規則**且** L1 給的 `code` 與它逐字相同 → 成功；否則一律判為「走到兜底」→ 錯誤。
（比舊頁嚴，見上一段第 1 項。）

**網址輸入**：L1 以 `[?&][aA]=([A-Z0-9a-z][A-Z0-9a-z\\-]{1,29})` 做**未錨定**的 `search`，
有下列漏洞，本檔分別擋：
- 不分位置：`?` 或 `&` 後面接 `a=`、且值以英數字開頭的，L1 取第一個符合的，不論它在路徑、
  查詢字串或 `#` 之後（例 `https://x/p1&a=FOO123`）。值以 `-` 或 `%` 開頭的不符合
  （`?a=-FOO123`、`?a=%20FOO123` 抽不到）；`?a=-X&a=FOO123` 會跳過第一個、取到 `FOO123`。
  本檔只看**查詢字串**：先在第一個 `#` 處切掉片段，再取剩下那段裡第一個 `?` 之後的部分；
  其中以 `&` 分隔（`;` 不當分隔）、名稱為 `A`（已轉大寫，故 `a=`／`A=` 混用都算）的參數才算數。
  名稱是 `A` 但沒有等號的參數（例 `?a=FOO123&a`、`?a&a=FOO123`）也算一個 `a`，其值記為「無值」，
  與任何代碼都不同 → 判失敗（與另一個 `a=` 並存時走下面「多個 `a=` 值不同」；
  單獨出現時：若 L1 也抽不到代碼，走「抽不出」；若 L1 從查詢字串以外抽到代碼
  （例 `https://x/p&a=FOO123?a`），走「值與 L1 的 `code` 不同」）。
  查詢字串裡一個名稱為 `a` 的參數都沒有 → 判失敗，**即使 L1 抽到了代碼也一樣**。
  ⚠️ 百分比編碼不解碼：`%3F` 不當 `?`（例 `https://x/p%3FBAR456+&A=…` 判失敗）。
- 值後面接什麼都收 → 例 `?a=ACTI71%20X` L1 給 `ACTI71`、`?a=` 超過 30 字元靜默截斷。
  本檔取的值是該參數到下一個 `&`（或查詢字串結尾）為止的整段，**必須與 L1 的 `code` 逐字相同**，
  否則判失敗。
- 查詢字串裡出現兩個以上的 `a=`：值都相同 → 照收；任一不同 → 判失敗（不猜 L1 取了哪一個）。
  片段裡的 `a=` 不算（例 `?a=FOO#frag&a=BAR` 只看到 `FOO`）。
- L1 的字元類除第一個字元外允許 `-` 任意出現、長度下限 2 → `AB`、`A-`、`A--------` 都能被抽出來。
  由第 5 步擋。
抽不出代碼 → 錯誤。

**對照表的值**：`public_code` 須為字串、通過 `_is_pure_code`，且不是 `NAN`／`NONE`。
理由：L1 讀 csv 時寫的是 `str(row.get("public_code", k)).upper().strip()`。
本組 2026-10-02 實測：csv 的 `public_code` 格留空 → pandas 讀成 NaN → `str(nan)` ＝ `"nan"` →
`"NAN"`，而 `NAN` 本身符合代碼字元規則，`_is_pure_code` 擋不下。`NONE` 是同一條路徑上
`str(None)` 的產物；本組實測 `read_csv` 留空格得到的是 NaN 而不是 None，`NONE` 是防禦性一併擋下。
（只有空白的格經 L1 的 `.strip()` 會變成 `""`；本檔在讀 `public_code` 那一步**沒有**另設非空檢查，
`""` 是由第 5 步最終關卡 `_is_pure_code` 擋下的。）

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


def _fail(raw, reason: str, code: Optional[str] = None, hit: Optional[bool] = None) -> dict:
    """`hit`：None ＝ 還沒走到查表那一步；True／False ＝ 查了，命中與否照實寫。"""
    return {"input": raw, "ok": False, "full_key": None, "portal": None,
            "parsed_code": code, "mapping_hit": hit, "error": reason}


def _url_a_values(text: str) -> list:
    """回傳查詢字串裡名稱為 `A` 的參數值，依出現順序；沒有等號者回 `None`。

    `text` 已轉大寫。查詢字串＝第一個 `#` 之前、第一個 `?` 之後的那一段。
    """
    before_fragment = text.split("#", 1)[0]
    _path, sep, query = before_fragment.partition("?")
    if not sep:
        return []
    values = []
    for param in query.split("&"):
        if param.startswith("A="):
            values.append(param[2:])
        elif param == "A":
            values.append(None)  # 名稱是 a、沒有等號：無值，與任何代碼都不同
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
            return _fail(raw, "網址中抽不出 MoneyDJ 代碼（parse_moneydj_input 找不到以英數字開頭的 ?a=／&a= 值）")
        values = _url_a_values(text)
        if not values:
            return _fail(raw, f"網址的查詢字串（? 之後、# 之前）裡沒有 a= 參數；parse_moneydj_input 抽到的"
                              f" {code!r} 不在查詢字串裡，不收", code)
        if len(set(values)) > 1:
            return _fail(raw, f"網址裡有多個 a= 且值不同（{values!r}）；不猜取哪一個", code)
        if values[0] != code:
            return _fail(raw, f"網址查詢字串裡 a= 的值 {values[0]!r}（取到下一個 & 或查詢字串結尾為止的整段）"
                              f"與 parse_moneydj_input 抽出的 {code!r} 不同；不截斷、不猜", code)
    else:
        if code != text or not _is_pure_code(text):
            return _fail(raw, f"代碼格式不符 {PURE_CODE_PATTERN}，parse_moneydj_input 會走 30 字元兜底"
                              f"（得 {code!r}）；不截斷、不猜", code)

    hit = code in mapping
    if hit:
        entry = mapping[code]
        pub = entry.get("public_code") if isinstance(entry, dict) else None
        if not isinstance(pub, str) or pub in _STRINGIFIED_MISSING:
            return _fail(raw, f"對照表 {code!r} 的 public_code 不合格（{pub!r}）；不補值", code, hit)
        full_key = pub
    else:
        full_key = code

    if not _is_pure_code(full_key):  # 最終關卡：三條路徑一律再驗
        source = f"對照表 {code!r} 的 public_code" if hit else "抽出的代碼"
        return _fail(raw, f"{source} {full_key!r} 不符 {PURE_CODE_PATTERN}；不補值、不猜", code, hit)
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
             "mapping_hit": bool | None（None ＝ 還沒走到查表那一步就失敗；
                            要判斷「查了但沒命中」請用 `is False`，不要用 `not`——`not None` 也為真）,
             "error": str | None},
            ...
          ],
          "provenance": {
            "mapping_source": "builtin" | "csv+builtin" | "injected"（判法見檔頭）,
            "mapping_size": 對照表筆數,
            "parser": "repositories.fund.sources.parse_moneydj_input",
          },
        }

    `mapping`：注入的對照表（`{代碼: {"public_code": ...}}`，形狀同 `load_fund_code_mapping`）；
    給了就不呼叫 L1；鍵不合格 → `TypeError`／`ValueError`。csv 在單次呼叫內只讀一次
    （另以 `path=""` 呼叫 L1 一次取內建表做比對，那一次不讀檔）。
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
