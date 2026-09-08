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
1. **不加快取。** 在這裡包一層 TTL ＝ 與 L1 既有的那一層疊加，之後沒有人推理得出
   「畫面上這份清單是多久以前的」（憲法 §8.2.A.1 `EX-UICACHE-1` 的升級條件 (3)）。
   ⚠️ **上一版這句話寫得偏鬆，就地更正**（有意識的更正，不是漏刪）：舊表述說
   「兩層 TTL 疊加」—— **第一層根本沒有 TTL**（見下方 `GAP-SEARCH-CACHE-1` 的實測），
   所以真正的問題比「疊加」更難推理：**上層過期了，下層永遠不過期。**
   ⛔ **與取數頻率有關的缺口，具名登記於下 —— 不是一句附註。**
2. **不做任何業務加工。** 多 endpoint 整合、去重、NAV 併入、關鍵字比對
   **全部已經在 L1 做完**；在這裡再做一次就是第二份真相源（§2.1）。
3. **不 try/except。** L1 若拋例外，**原封往上拋** —— 由 UI 端的
   `ui.helpers.render_state.safe_section()` 畫真的紅框（§1 Fail Loud）。
   ⛔ 尤其**不得**把例外收成 `[]`：那會讓「查詢炸了」長得跟「查無結果」一模一樣。
4. **不排序、不截斷。** 「畫面上要顯示幾張卡」是版面問題，屬 UI 端。

⚠️ **`GAP-SEARCH-CACHE-1`｜取數頻率的缺口（具名登記；本檔不處置）**
--------------------------------------------------------------------
**這一段刻意寫成登記項而不是附註**，因為它有兩半，而**第二半是新頁的設計選擇造成的**
—— 上一版只寫了第一半，讀起來像「純粹是上游的問題」。**那句話少了最重要的一半。**

**(a) L1 的快取覆蓋不全，而且覆蓋到的那一半永不過期**（本組逐行讀 `sources.py` 實測）：

* ``_tdcc_cache = {}`` 是**裸 dict** —— **沒有 TTL、沒有 eviction**，
  process 活多久它就存多久。它只蓋住三個 TDCC endpoint 的 HTTP 回應。
* ✅ **失敗不會 poison**：`_tdcc_get()` 的 `except` 分支是 `return []`，
  **在寫 cache 之前就返回**（符合 v3 §02「只快取成功結果」）。
* ⚠️ **但成功路徑有另一種永久性問題**：上游若回 200 卻不是 list，
  ``data if isinstance(data, list) else []`` 會把 ``[]`` **永久**寫進 cache。
* ⛔ **FundClear 備援分支完全沒有快取** —— 它只在 TDCC 兩個 endpoint 都沒有命中時才跑，
  而那條路**每一次呼叫都真的送一次 HTTPS（`timeout=8`）**。
* ⚠️ 就算 TDCC 命中，`tdcc_search_fund()` 仍會**每次重跑整份名錄的比對／去重／NAV 併入**
  —— **被快取的是回應，不是那幾個迴圈。**

**(b) 呼叫頻率：新 ⑧ 與舊 ③ 不一樣，而這一半是新頁自己造成的**

====================  =======================================  =========================
比較項                 舊 ③ `code_finder.py::_search`            新 ⑧ `_render_results()`
====================  =======================================  =========================
何時打 L1              **只在 `if do_search and …:` 之內**        **每一次 render**
結果存哪               `st.session_state["tdcc_results"]`        **不存**，每次重算
====================  =======================================  =========================

而 `app.py` 用的是 `st.tabs`（**一次 run 渲染全部分頁**），所以：
**只要使用者送出過一次「TDCC 名錄命不中」的關鍵字，此後 App 裡任何一個 widget 的
任何一次互動，都會再送出一次未快取的 FundClear 請求。**
而「名錄命不中」正是空狀態那一屏 —— **也正是使用者最會反覆操作的那一屏**
（改關鍵字、按逃生門）。

⚠️ **這與憲法 `EX-UICACHE-1` 就地記載的事故是同一個形狀**：「未加此層前，任一分頁的
任一次互動都會重打 Google Sheets；25 檔實測 rerun 起算 **17 秒後 `WebSocket onclose`**，
2026-08-14 實機兩次重現」。

⛔ **正解不在本層，也不在 UI 層**：
* **不得**在這裡加 TTL —— 見上面第 1 點；
* **不得**在 UI 層用 `@st.cache_data` 包外部 HTTP —— `EX-UICACHE-1` 升級條件 (1) 明禁；
* **家在 L1**：`tdcc_search_fund` 的 FundClear 分支該有自己的快取／退避，
  而那會動到舊 ③ 正在跑的路徑，屬 §8.4 步驟 4 的**範圍決定**。
**本檔只登記、不處置；已具名回報總管。**

⚠️ 本登記的每一條都是**本組讀原始碼**得到的，**未經第二組驗證**（`CLAUDE.md §-2` 規則 6）。

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
