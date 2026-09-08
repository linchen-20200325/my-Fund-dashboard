"""新增持倉的**純函式** —— 把使用者打進來的幾行字，變成 `portfolio_funds` 的骨架條目。

為什麼要有這一支（客戶 2026-09-08 拍板：「加入基金入口整合至 ⑨『保單與扣款標的』」）
--------------------------------------------------------------------------------
**⑨ 新頁在此之前物理上加不了一檔基金** —— 實測全 repo 寫進 `portfolio_funds` 的
呼叫點只有兩處，都在舊分頁裡（`ui/tab3_portfolio.py` 的批次加入、
`ui/tab3_t7_ledger.py` 的帳本補 spine）。舊 ④ 一旦依退場順序拔掉，新頁就沒有入口。

**這一支只做「把字變成條目」，不做取數、不碰網路、不碰磁碟、不碰 Google Sheet。**
渲染與 session 讀寫留在 `ui/views/page_04_portfolio.py`。

⚠️ **零 streamlit、零 IO、零 `repositories`、零 `pandas`** —— 這不是自我宣稱：
`tests/test_wf04_portfolio_skeleton.py::test_the_named_exemption_is_still_a_pure_ssot`
會**每次跑都重新讀這個檔案的 import**，一旦這裡多 import 一個 `streamlit`／
`requests`／`repositories`，那條當場轉紅、⑨ 對本模組的具名豁免同時失效。

它與既有兩份寫入語意的關係（**沿用，不是另寫一份**）
------------------------------------------------------
本 repo 對「一筆 `portfolio_funds` 條目長什麼樣」已經有兩份既有語意，
本模組**逐項對齊其中一份**、並就地寫明為什麼選它：

======================== ================================ ==============================
欄位                      舊 ④ 批次加入                     `sync_policies_to_portfolio_funds`
                         （`ui/tab3_portfolio.py`）        （`repositories/policy/v1.py`）
======================== ================================ ==============================
``code``                 ``.upper()``                      ``.upper()``
``policy_id``            使用者輸入（可空）                 Sheet 的 `policy_id`
``policy_name``          **等於** `policy_id`               Sheet 的 `policy_name`
``invest_twd``           ``0``                             Sheet 的金額
``loaded``               ``True``（它當場抓完了）           **``False``**（等使用者按載入）
``load_error``           ``None``                          ``None``
======================== ================================ ==============================

⭐ **本模組取 `loaded=False` 那一份，這是本檔最承重的一個決定，理由三條**：

1. **我們沒有抓資料，寫 `True` 就是說謊。** `loaded=True` 的意思是「這一檔的淨值、
   名稱、幣別、指標都已經在手上」。舊 ④ 之所以敢寫 `True`，是因為它在同一個按鈕裡
   跑完了 MoneyDJ 抓取；本模組**一次網路都不打**。寫 `True` 會讓
   `page_04_portfolio._holdings()` 把一筆什麼都沒有的條目當成有效持倉，
   核心／衛星比例、總投入、集中度全部會把它算進去 —— 那正是 `CLAUDE.md §1`
   「錯誤的數字比沒有數字更危險」點名的形狀。
2. **`loaded=False` 有現成的下一步。** 既有的
   `ui/helpers/portfolio/load.py::batch_load_unloaded_funds()` 正是為這個狀態寫的，
   雲端讀回（`sync_policies_to_portfolio_funds`）留下的也是同一個狀態。
   **同一種待辦只有一種形狀，使用者與程式都只要學一次。**
3. **它讓「新增」與「取數」分開失敗。** 抓取失敗不會讓新增這件事一起失敗；
   使用者打的字**一定**留得住。

⛔ **不要因為「舊 ④ 寫的是 True」就改成 True** —— 那兩個 `True` 的前提不一樣，
   照抄欄位值而不照抄前提，就是把一句真話搬到會變成假話的地方。

⚠️ **本模組不寫 Google Sheet，也不宣稱寫得到**（`CLAUDE.md §-2` 規則 6）。
   舊 ④ 的批次加入在**有保單編號且 OAuth 可用**時會順手 `upsert_fund_in_policy`；
   本模組**沒有**那一段。這是刻意的：⑨ 的整條渲染鏈目前是零寫入
   （`tests/test_wf04_portfolio_no_writes.py` 在守），把一條 Google Sheet 寫入面
   接進來是另一個題目、另一批的授權。**已知落差，不是漏做** —— 完整登記見
   `ui/views/page_04_portfolio.ADD_FUND_SCOPE_NOTE`。
"""
from __future__ import annotations

#: 一行裡「代碼」與「保單編號」的分隔符。與舊 ④ 批次加入同一個字元。
FIELD_SEP: str = ","

#: 新條目的 `loaded` 值。**具名而不 inline**：它是本模組最承重的一個決定
#: （理由見模組 docstring），具名之後測試可以直接對它斷言，
#: 而不是去比對一個埋在 dict literal 裡的 `False`。
NEW_ENTRY_LOADED: bool = False

#: 新條目的初始投入金額。**刻意是 0 而不是「讓使用者在這裡填」** ——
#: 金額的真相源是保單表（`repositories/policy/` 的 `invest_twd` 欄），
#: 在這裡再開一個輸入格會讓同一個數字有兩個出處，
#: 正是客戶 2026-09-07 決定 ① 的理由（「不一致時使用者不知道信哪個」）。
NEW_ENTRY_INVEST_TWD: int = 0


def entry_key(code: str, policy_id: str) -> tuple[str, str]:
    """去重鍵 ＝ ``(代碼, 保單編號)`` 複合鍵。

    ⛔ **不是單獨的 `code`。** 這一點是舊 ④ v18.56 修 bug 修出來的：
    同一檔基金可以同時出現在好幾張保單底下，用單鍵會讓它們互相覆蓋
    （`repositories/policy/v1.py::sync_policies_to_portfolio_funds` 的 docstring
    逐字記著「使用者報告 19 筆跨 4 保單，讀回後變 7 檔 unique code」）。
    """
    return (str(code or "").strip().upper(), str(policy_id or "").strip())


def parse_lines(raw: object, default_policy_id: object = "") -> tuple[
        list[tuple[str, str]], list[str]]:
    """把多行文字切成 ``[(代碼, 保單編號), …]``，並回報**看不懂的行**。

    每一行接受兩種寫法（與舊 ④ 批次加入相同）::

        00713                 → 用 `default_policy_id`
        00713,某某保單A        → 這一行自己指定保單編號

    Returns
    -------
    (entries, invalid)
        `entries` 依輸入順序、**尚未去重**；`invalid` 是原封不動的問題行。

    ⚠️ **空白行不是「看不懂」，直接跳過** —— 使用者貼一段文字帶著空行是常態，
       把它報成錯誤只會製造噪音。
    ⚠️ **看不懂的行不會被丟掉，也不會被猜** —— 它們原封回傳給呼叫端去講
       （`CLAUDE.md §1`：不猜、不靜默吞）。目前唯一「看不懂」的形狀是
       **逗號前面沒有代碼**（例如 `,某某保單`）。
    ⛔ **本函式刻意不驗「這個代碼存不存在」** —— 那要連線，而連線是另一件事。
       代碼打錯的下場是載入時抓不到，`load_error` 會誠實地寫在那一筆上。
    """
    _default = str(default_policy_id or "").strip()
    _entries: list[tuple[str, str]] = []
    _invalid: list[str] = []
    for _line in str(raw or "").splitlines():
        _stripped = _line.strip()
        if not _stripped:
            continue
        if FIELD_SEP in _stripped:
            _code_raw, _, _pid_raw = _stripped.partition(FIELD_SEP)
        else:
            _code_raw, _pid_raw = _stripped, _default
        # ⭐ **正規化只有一處實作**（:func:`entry_key`）。
        # ⚠️ 這一行原本是 `_code_raw.strip().upper()` —— 也就是**第二份**大小寫規則。
        #    突變測試當場示範了那份重複的代價：把它拿掉，**沒有一條測試轉紅**
        #    （因為下游 `new_holding()` 又走了一次 `entry_key`）。
        #    一份「拿掉也不會有人發現」的實作，就是一份遲早會與另一份漂移的實作。
        _code, _pid = entry_key(_code_raw, _pid_raw)
        if not _code:
            _invalid.append(_stripped)
            continue
        _entries.append((_code, _pid))
    return _entries, _invalid


def new_holding(code: str, policy_id: str) -> dict[str, object]:
    """一筆**骨架**條目。欄位與值的出處見模組 docstring 的對照表。

    ⚠️ **`policy_name` 填的是 `policy_id`，不是空字串** —— 與舊 ④ 相同。
       保單一覽那一欄之後會被雲端讀回的真名蓋掉（`sync_policies_to_portfolio_funds`
       走 `base.update(...)`），在那之前顯示使用者自己打的編號，比顯示空白有用。
    """
    _code, _pid = entry_key(code, policy_id)
    return {
        "code": _code,
        "invest_twd": NEW_ENTRY_INVEST_TWD,
        "policy_id": _pid,
        "policy_name": _pid,
        "loaded": NEW_ENTRY_LOADED,
        "load_error": None,
    }


def plan_new_holdings(raw: object, existing: object,
                      *, default_policy_id: object = "") -> dict[str, object]:
    """把使用者打的字，算成「這一批要加什麼、跳過什麼、看不懂什麼」。

    **純函式：不改 `existing`、不碰 session、不連線。** 呼叫端拿 `merged` 去寫。

    Returns
    -------
    dict
        ``rows``     新條目（依輸入順序）
        ``merged``   `existing` ＋ `rows`（呼叫端要寫回去的那一份）
        ``added``    新增的 ``(代碼, 保單編號)``
        ``skipped``  已經在清單裡、因此沒有重複加的 ``(代碼, 保單編號)``
        ``invalid``  看不懂的原始行

    ⚠️ **同一批裡重複的也算 `skipped`** —— 使用者貼上時同一行貼兩次是常態，
       第二次不該再長出一筆。
    ⚠️ **`existing` 裡形狀不對的元素（不是 dict）一律原樣保留、不參與去重** ——
       它不是我們寫的，我們不猜它的意思，也不悄悄把它丟掉（§1）。
    """
    _existing = list(existing or [])
    _seen: set[tuple[str, str]] = {
        entry_key(_f.get("code"), _f.get("policy_id"))
        for _f in _existing if isinstance(_f, dict)
    }
    _entries, _invalid = parse_lines(raw, default_policy_id)

    _rows: list[dict[str, object]] = []
    _added: list[tuple[str, str]] = []
    _skipped: list[tuple[str, str]] = []
    for _code, _pid in _entries:
        _key = entry_key(_code, _pid)
        if _key in _seen:
            _skipped.append(_key)
            continue
        _seen.add(_key)
        _rows.append(new_holding(_code, _pid))
        _added.append(_key)

    return {
        "rows": _rows,
        "merged": _existing + _rows,
        "added": _added,
        "skipped": _skipped,
        "invalid": _invalid,
    }


def pending_rows(funds: object) -> list[dict[str, object]]:
    """**已經在清單裡、但還沒有淨值資料**的那幾筆（含抓取失敗的）。

    ⭐ 這是 `page_04_portfolio._holdings()` **濾掉**的那一半 ——
    兩支合起來才是整份清單。單獨看任何一支都會少講一件事：
    `_holdings()` 少講「有東西沒被算進去」，本函式少講「算進去的是哪些」。

    ⚠️ **抓取失敗（`load_error`）與還沒抓（`loaded` 為假）都收進來，但要分得出來** ——
       呼叫端拿 `load_error` 判斷該講哪一句：前者按幾次都一樣，後者按一下就好。
    """
    _raw = funds or []
    if not isinstance(_raw, list):
        return []
    return [_f for _f in _raw
            if isinstance(_f, dict) and (not _f.get("loaded") or _f.get("load_error"))]


def pending_split(funds: object) -> tuple[list[dict[str, object]],
                                          list[dict[str, object]]]:
    """把 :func:`pending_rows` 再分成 ``(還沒抓的, 抓過但失敗的)``。

    **兩者的下一步完全不同**，所以畫面上不能混成一句：
    - 還沒抓的 → 去按一次載入就好；
    - 抓過但失敗的 → 再按一百次也一樣，要看的是 `load_error` 說了什麼。
    把它們寫成同一句「N 檔未載入」，等於叫使用者去做一件對其中一半沒有用的事。
    """
    _pending = pending_rows(funds)
    _failed = [_f for _f in _pending if _f.get("load_error")]
    _waiting = [_f for _f in _pending if not _f.get("load_error")]
    return _waiting, _failed
