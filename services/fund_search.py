"""L2 ── 基金搜尋的服務層入口（**thin facade**，唯一職責是把 L1 的搜尋接出來）。

為什麼會有這一檔（背景，讀完再改）
--------------------------------
③ 標的探索（`ui/views/page_03_research.py`）的線框第一塊就是「唯一搜尋入口」，
但在本檔出現之前，**`services/**` 裡沒有任何基金搜尋函式** —— 現行實作住在 **L1**
（`repositories.fund.tdcc_search_fund`），而 UI 直呼它靠的是憲法 §8.2.A.1 的
**`EX-PASSTHRU-1`** 例外（登記的呼叫點是 `ui/helpers/fund_research/code_finder.py::_search`）。

**總管 2026-09-08 裁決：建 L2 入口，新頁呼叫它；`code_finder.py` 一個字都不動。**
依據是 `EX-PASSTHRU-1` 自己寫的升級觸發條件逐字：
「…**或本 fetcher 出現第二個 UI caller**（fan-out 一旦出現，(a) 的理由即失效，
**應比照 R16 上提 L2**）」—— 也就是「直接多開一個 UI 呼叫點」這條路，
**憲法自己把它導向 L2**。

⚠️ **過渡期會有兩個消費者，這是預期狀態、不是違憲**：
   舊 ③（`ui/helpers/fund_research/code_finder.py`）仍**直呼 L1**，
   新 ⑧（`ui/views/page_03_research.py`）走本檔。
   客戶明令「絕對禁止修改現有線上正常運作的舊版 Tab 代碼」，所以舊路徑原封不動。
   **兩者呼叫的是同一份 L1 實作，不是兩份實作** —— v3 §01-2「同一個資料來源
   全站只能有一處取數實作」管的是後者。⛔ 不要為了「收斂成一條」去改舊 ③。

⛔ 本檔**刻意不做**的四件事（每一條都有理由，不要順手加回來）
------------------------------------------------------------
1. **不加快取。** L1 端 `_tdcc_get()` 已用 module 層 `_tdcc_cache` 存住三個 TDCC
   endpoint 的回應；在這裡再包一層 TTL ＝ 兩層失效語意疊加，之後沒有人推理得出
   「畫面上這份清單是多久以前的」（憲法 §8.2.A.1 `EX-UICACHE-1` 的升級條件 (3)）。
   ⚠️ **據實揭露一個本組實測到、但依裁決不自行處置的缺口**：L1 的
   **FundClear 備援分支沒有被任何快取蓋到** —— 它只在 TDCC 兩個 endpoint
   都沒有命中時才跑，但那條路每一次 rerun 都會真的送一次 HTTP。
   **本組不在 L2 補快取**（那正是上一段禁止的事），**已具名回報總管**。
2. **不做任何業務加工。** 多 endpoint 整合、去重、NAV 併入、關鍵字比對
   **全部已經在 L1 做完**；在這裡再做一次就是第二份真相源（§2.1）。
3. **不 try/except。** L1 若拋例外，**原封往上拋** —— 由 UI 端的
   `ui.helpers.render_state.safe_section()` 畫真的紅框（§1 Fail Loud）。
   ⛔ 尤其**不得**把例外收成 `[]`：那會讓「查詢炸了」長得跟「查無結果」一模一樣。
4. **不排序、不截斷。** 「畫面上要顯示幾張卡」是版面問題，屬 UI 端。

⚠️ **本層分不出「查無結果」與「查詢失敗」—— 這是本檔最重要的一句話**
-----------------------------------------------------------------
`repositories.fund.tdcc_search_fund` 內部把所有例外都吞掉了（本組逐行讀過原始碼）：

* `_tdcc_get()` —— `except Exception as e: print(...); return []`
* FundClear 備援 —— `except Exception: pass`

⇒ **三個來源全部連不上，與「名錄裡真的沒有這個關鍵字」，回傳值一模一樣是 `[]`。**
本層**沒有辦法**分辨，所以**不會**假裝分辨得出來：:data:`EMPTY_MEANS_UNKNOWN`
就是給呼叫端照抄的那句實話。
⛔ **不得**把空清單畫成「查無此基金」——那是替上游編了一個它沒說過的結論（§1）。
⛔ 也**不得**為了消掉這個含混而在這裡自己重寫一份取數 —— 那會變成第二份實作。
✅ 要真的分得出來，唯一的正解是**讓 L1 不要吞例外**；那會動到舊 ③ 正在跑的路徑，
   屬 §8.4 步驟 4 的範圍決定，**要客戶／總管拍板，不是本檔自己改**。

⚠️ **本檔的宣稱由資料工程組單組產出，未經第二組獨立驗證**（`CLAUDE.md §-2` 規則 6）。
"""
from __future__ import annotations

from typing import Any

#: L1 每一列的鍵名 —— **SSOT**：呼叫端一律從這裡取，不要在 UI 檔裡再抄一份中文字面值。
#: （L1 `tdcc_search_fund()` 的三個 `results.append({...})` 與 FundClear 備援分支
#: 吐的都是這六個鍵，本組逐一讀過原始碼。）
KEY_NAME: str = "基金名稱"
KEY_CODE: str = "基金代碼"
KEY_AGENT: str = "總代理"
KEY_NAV: str = "淨值"
KEY_NAV_DATE: str = "日期"
KEY_SOURCE: str = "來源"

#: 上列六個鍵的完整順序（守衛拿它比對；呼叫端可以拿它做欄位巡覽）。
RESULT_KEYS: tuple[str, ...] = (
    KEY_NAME, KEY_CODE, KEY_AGENT, KEY_NAV, KEY_NAV_DATE, KEY_SOURCE)

#: **空清單的意思，逐字**。呼叫端把這句放進空狀態的「缺什麼」，
#: 不要自己改寫成「查無結果」——本層真的不知道是哪一種（理由見模組 docstring）。
EMPTY_MEANS_UNKNOWN: str = (
    "上游把「名錄裡真的沒有這個關鍵字」與「名錄來源當下取不到」都回成空清單，"
    "本頁分不出是哪一種")


def search_funds(term: str) -> list[dict[str, Any]]:
    """依關鍵字（基金名稱或代碼）向 L1 取候選清單。**thin，不加工。**

    Parameters
    ----------
    term : 使用者輸入的關鍵字。前後空白會被去掉。

    Returns
    -------
    list[dict]
        L1 原樣回傳的候選列，每一列的鍵見 :data:`RESULT_KEYS`。
        **空清單的語意是含混的** —— 見 :data:`EMPTY_MEANS_UNKNOWN`。

    Raises
    ------
    ValueError
        `term` 去掉空白之後是空的。**不回空清單** —— 「你沒給關鍵字」與
        「查不到」是兩件事，回同一個值等於把前者偽裝成後者（§1）。
    TypeError
        L1 回的不是 list，或列不是 dict。**不降級、不過濾** ——
        契約變了就當場炸，讓紅框指向真正的原因，而不是靜靜少畫幾張卡。

    Notes
    -----
    ⚠️ 本函式**每次呼叫都會走到 L1**（本層無快取，理由見模組 docstring）。
    """
    _term = (term or "").strip()
    if not _term:
        raise ValueError(
            "search_funds() 收到空白關鍵字 —— 呼叫端必須先擋掉「還沒輸入」這個處境，"
            "不要送一個空字串進來再把結果讀成「查無結果」（§1）。")

    # ⚠️ **lazy import，與本 repo 既有慣例一致**（`ui/helpers/fund_research/code_finder.py`
    #    的同一個呼叫就地寫著「避免 module load 時拉起整條抓取相依鏈」）。
    #    寫在模組頂端的話，任何 `import services.fund_search` 都會連帶把
    #    `repositories.fund` 整包（含 `bs4`）拉起來 —— ③ 那一頁的靜態 import 閉包
    #    已經是 102 個模組（`tests/test_wf03_research_no_writes.py` 就地量測），
    #    沒有理由再讓它變長。
    from repositories.fund import tdcc_search_fund

    _rows = tdcc_search_fund(_term)

    if not isinstance(_rows, list):
        raise TypeError(
            f"repositories.fund.tdcc_search_fund() 應回 list，實際得到 "
            f"{type(_rows).__name__} —— 上游契約變了，本層不自行降級。")
    _bad = [type(_r).__name__ for _r in _rows if not isinstance(_r, dict)]
    if _bad:
        raise TypeError(
            f"搜尋結果裡有不是 dict 的列：{_bad} —— 上游契約變了。"
            "本層不過濾掉它們：靜靜少畫幾張卡，比當場炸掉更難查。")
    return _rows
