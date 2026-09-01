"""ui/helpers/story_nav.py — 分頁名 SSOT + 分區名 SSOT + 決策動線 + **四層流程導覽**

本檔提供四件互相關聯、但語意不同的東西：

1. **`tab_label(key)` — 全部 5 個【頂層分頁】名的唯一來源**
   `app.py` 的 `st.tabs([...])` 與各處「請至 X 分頁」指路文案共用它。
   2026-08-05 稽核 🔴 必修 2 的根因就是「標籤沒有 SSOT」，三處文案指向不存在
   的分頁名；2026-08-14 稽核又抓到 `ui/sidebar.py` 三處漏網。

2. **`section_label(key)` / `where_to_find(key)` — 【頁內分區】名的唯一來源**
   2026-08-31 客戶拍板線框把七分頁收成五分頁之後，原本的**頂層分頁**
   「個基深掘 / 批次分析 / 我的管理室 / 參考 · 診斷」降級成**合併頁裡的分區**
   （③ 標的探索的兩個模式、⑤ 設定與診斷的三個分區）。
   分區與分頁**必須分開兩張表**，理由見下方「為什麼是兩張表」。

3. **決策動線四站（`_STEPS` / `story_nav_markdown`）**
   ① 🌐 市場總覽 → ② 💊 持倉體檢 → ③ 🔍 標的探索 → ④ 📊 資產配置。
   回答「照順序讀，我下一步該看哪」。

4. **四層流程導覽（`_LAYERS` / `flow_nav_markdown`）— 2026-08-14 新增**
   對齊 user 提供的系統流程圖：
       ① 市場與全球總經層 → ② 基金核心分析模組
       → ③ 監控與評分區 → ④ 行動閉環（LINE 推送 → 用戶動作 → 回饋觀察池）
   回答「我現在在整個系統的哪一層、這層在做什麼、資料往哪流」。

   ⚠️ 流程層講的是**系統心智模型**，與分頁數量脫鉤 —— 2026-08-31 七→五之後
   這一點更明顯：`fund` 與 `batch` 都是 ③ 標的探索**頁內**的模式，但在流程圖上
   仍然同屬 ② 基金核心分析層。故 `_LAYERS` 的成員是**導覽 key**（分頁 key 或
   分區 key 皆可），不是「分頁 key」—— 見 `_LAYERS` 上方註解。

為什麼是兩張表（而不是把 5 個分區塞回 `_TAB_LABELS` 湊成 10 個 key）
--------------------------------------------------------------------
`tab_label()` 的**全部價值**在於「它回傳的字串一定是使用者在分頁列上看得到的東西」。
把 `batch` 留在 `_TAB_LABELS` 裡，`tab_label('batch')` 就會回一個**分頁列上不存在**
的名字 —— 那正是本 repo 已經發作**兩次**的同一種病（2026-08-05 必修 2、
2026-08-14 sidebar 三處死指路）。第三次發作只會更難查，因為前兩次的修法
（收進 SSOT）這次幫不上忙：SSOT 本身就是錯的。

故 2026-08-31 起：
- **`_TAB_LABELS` 只留 5 個真正存在於 `st.tabs` 的分頁**；
- `tab_label('fund' / 'batch' / 'manage' / 'ref')` **當場 `KeyError`**，
  而且錯誤訊息直接指名該改用 `section_label()` / `where_to_find()`；
- 指路文案要指到頁內分區時，用 **`where_to_find()`** ——
  它會自動帶上頂層分頁名與站號（`③ 🔍 標的探索 → 📦 批次掃描`），
  **站號由 `_TAB_LABELS` 的順序推導，不寫死**（寫死的站號正是線框點名的
  「Tab2＝個基深掘（實際第 4）」那顆地雷）。

純展示、零資料依賴；內容（`*_markdown`）與渲染（`render_*`）分離以便單元測試。
"""
from __future__ import annotations

# 導覽列標籤帶 ①②③④ 序號(動線第幾站),`st.tabs` 的分頁名不帶 —— 兩者只差前綴,
# 故由同一份來源導出,避免 app.py 與本檔各自維護一份而漂移。
_ORDINAL_PREFIXES = "①②③④⑤⑥⑦⑧⑨⑩"


# ══════════════════════════════════════════════════════════════════════════
# 1) 分頁名 SSOT — 全部 5 個頂層分頁（2026-08-31 客戶拍板線框，七→五）
# ══════════════════════════════════════════════════════════════════════════
# 這個 dict 的**順序就是 `app.py` `st.tabs` 的順序**，站號 ①②③④⑤ 由它推導
# （`_tab_ordinal`）。改順序 = 改站號，兩者不可能漂移，因為只有一份。
#
# 七→五的對映（舊 key 的去處逐一寫明，避免後人以為是漏刪）：
#   macro     → macro（不變）
#   health    → health（不變）
#   batch     → ③ research 的「📦 批次掃描」模式   ← 降級為分區
#   fund      → ③ research 的「🔍 單檔深掘」模式   ← 降級為分區
#   portfolio → portfolio（改名「📊 我的配置」）
#   manage    → ⑤ settings 的「🗄️ 資料維護與通報」分區  ← 降級為分區
#   ref       → 拆成 ⑤ settings 的「🔭 資料診斷」+「📖 說明書」兩個分區
# ⚠️ 2026-09-01 五分頁動線重構（客戶拍板線框 `ia-wireframe.html`）：**四個分頁改名**。
#    這是**有意識的政策變更，不是漏改**（日期 2026-09-01 · 決策者：客戶）。
#    改的只有**顯示名**：key、順序、站號、每個 key 對應的 render 函式**一律未動**，
#    所以這不是「換分頁」，是「同一個分頁換一個更準的名字」。
#    舊名 → 新名（舊名已同步進 `RETIRED_TAB_LABELS`，見下）：
#      🌐 市場定調 → 🌐 市場總覽   （原名像在講「定調」這個動作，新名講的是內容）
#      💊 組合健診 → 💊 持倉體檢   （線框：只診斷、不建議，「體檢」比「健診」更貼）
#      🔍 基金研究 → 🔍 標的探索   （這裡的標的**不預設持有**，「研究」會被讀成研究我的）
#      📊 我的配置 → 📊 資產配置   （④ 收了換股顧問與帳本，是「動作」頁不是「我的東西」頁）
#      ⚙️ 設定與診斷 —— **未改**（線框與現行同名）
#    ⚠️ emoji 前綴沿用舊值，線框沒有指定 emoji；證據是 ⑤「⚙️ 設定與診斷」現行值
#       就是「emoji ＋ 線框名」，故其餘四個比照，不另行發明。
#    ⚠️ **① 的名字有一個未解的來源衝突，據實登記**：派工單的 IA 表寫「大盤總經」，
#       客戶逐字確認的線框寫「**市場總覽**」。本組取線框（它是客戶實際看過並拍板的
#       那份視覺，且派工單自陳線框為規範性文件）。**這是本組的判斷，未經第二組驗證**
#       （`CLAUDE.md §-2` 規則 6）—— 若總管認定以派工單為準，改本行一個字串即可，
#       並把「🌐 市場總覽」移進 `RETIRED_TAB_LABELS`。
_TAB_LABELS: dict[str, str] = {
    "macro":     "🌐 市場總覽",
    "health":    "💊 持倉體檢",
    "research":  "🔍 標的探索",
    "portfolio": "📊 資產配置",
    "settings":  "⚙️ 設定與診斷",
}


# ══════════════════════════════════════════════════════════════════════════
# 1-A) 失效分頁名字表 — 給守衛用的**黑名單 SSOT**（不參與任何渲染）
# ══════════════════════════════════════════════════════════════════════════
# 存在的理由（讀之前先看這段，否則會以為它只是註解垃圾）
# --------------------------------------------------------
# 本 repo 的「指路文案指到一個不存在的分頁」已經發作**三次**（2026-08-05 必修 2、
# 2026-08-14 sidebar 三處、2026-08-31 七→五共 6 處）。每一次的修法都是「把那幾處
# 收進 SSOT」，而每一次的守衛都是**一份白名單**（`_SECTION_HINT_SITES` 自己就寫著
# 「這張表不是窮舉」）—— 白名單結構上抓不到名單外的第 N+1 處，所以病照樣復發。
#
# 這張表是**黑名單那一半**的唯一出處。守衛
# （`tests/test_wpf_five_tab_wiring.py::test_no_live_string_hardcodes_a_tab_name`）
# 拿 `set(_TAB_LABELS.values()) | RETIRED_TAB_LABELS | MISWRITTEN_TAB_NAMES`
# 去掃全 repo 的活字串。
#
# ⚠️ **黑名單不夠，這一點必須寫在這裡而不是只寫在測試裡**：
# `MISWRITTEN_TAB_NAMES` 的存在本身就是證據 ——「組合配置」**從來沒有進過
# `_TAB_LABELS`**，任何「比對歷史分頁名」的字表都不可能事先知道它。
# 所以守衛還有**形態向**那一條（活字串帶指路詞卻沒經過本模組求值 → 紅），
# 它不依賴任何字表。**兩條並行，缺一不可。**

#: 已退役的分頁名（七→五之前的 `_TAB_LABELS` 值）。
#: **出處**：本檔在 `origin/main` 上的 `_TAB_LABELS`（七分頁時期）——
#: `git show origin/main:ui/helpers/story_nav.py` 可逐字覆核。
#: `macro` / `health` 兩個 key 的值七→五未變，故不在此表（它們沒有退役）。
#: ⚠️ **本表現在有兩批來歷，不要當成同一批**（2026-09-01 補）：
#:   **(a) 七→五**（2026-08-31）—— 下方前 5 筆，出處如上一段所述。
#:   **(b) 五分頁改名**（2026-09-01，客戶拍板線框 `ia-wireframe.html`）—— 下方後 4 筆。
#:       這一批**沒有任何分頁被裁撤**，退役的只有「名字」；每個 key 都還在
#:       `_TAB_LABELS` 裡，只是值換了。**兩批混在一起讀會以為 ① 被砍過，並沒有。**
#: ⚠️ (b) 的出處**不是** `origin/main` 的 `_TAB_LABELS`（那裡是七分頁時期的值），
#:    而是本檔改名前一版的 `_TAB_LABELS` —— 覆核指令：
#:    `git show origin/main:ui/helpers/story_nav.py` 只能覆核 (a)，(b) 要看本批的 diff。
RETIRED_TAB_LABELS: frozenset = frozenset({
    # (a) 七→五（2026-08-31）
    "📦 批次分析",      # → 降級為 ③ 的「📦 批次掃描」模式
    "🔍 個基深掘",      # → 降級為 ③ 的「🔍 單檔深掘」模式
    "📊 配置 & 帳本",   # → 改名「📊 我的配置」，2026-09-01 再改名「📊 資產配置」
    "📋 我的管理室",    # → 降級為 ⑤ 的「🗄️ 資料維護與通報」分區
    "📖 參考 / 診斷",   # → 拆成 ⑤ 的「🔭 資料診斷」+「📖 說明書」兩個分區
    # (b) 五分頁改名（2026-09-01）—— 分頁都還在，退役的只有名字
    "🌐 市場定調",      # → 改名「🌐 市場總覽」
    "💊 組合健診",      # → 改名「💊 持倉體檢」
    "🔍 基金研究",      # → 改名「🔍 標的探索」
    "📊 我的配置",      # → 改名「📊 資產配置」
})

#: **從來就不是任何時期的分頁名**、卻在程式碼裡被當成分頁名寫出來的名字。
#: 與 `RETIRED_TAB_LABELS` 的差別很重要：退役的名字**曾經是對的**，
#: 這些是**憑印象手寫、從一開始就指向不存在的東西**。
#: ⚠️ 這一類**無法用「比對歷史值」的方法事先發現** —— 它們不在任何一版的
#: `_TAB_LABELS` 裡。收在這裡是為了「修掉之後不准再犯」，
#: **不是**為了宣稱這張表窮舉（新的錯名字要靠守衛的形態向那一條抓）。
#: 已知來歷：
#:   「組合配置」—— 2026-08-31 由線框調查組發現，命中 4 處
#:     （`ui/tab_fund_grp_health.py` ×2、`ui/helpers/fund_grp_health/columns.py` ×2）。
#:     ④ 在七→五之前叫「📊 配置 & 帳本」、之後叫「📊 我的配置」，
#:     **兩個時期都沒有**叫「組合配置」的分頁 → 屬既有債，不是七→五打壞的。
MISWRITTEN_TAB_NAMES: frozenset = frozenset({
    "組合配置",
})


# ══════════════════════════════════════════════════════════════════════════
# 1-B) 分區名 SSOT — 合併頁**頁內**的分區（不是分頁，分頁列上看不到）
# ══════════════════════════════════════════════════════════════════════════
# ⚠️ 這些字串必須與合併頁實際畫出來的字**一模一樣**，否則指路又會指到
#    使用者找不到的地方（同一種病的第三次發作）：
#      fund / batch  → `ui/tab_fund_research.py` 的 `MODE_SINGLE` / `MODE_BATCH`
#      manage        → `ui/tab_settings_diag.py::_render_maintain_section` 的分區標題
#      diag          → 同檔 `_render_diag_section`
#      manual        → 同檔 `_render_manual_section`
#      switch        → `ui/helpers/fund_grp_health/switch_advisor_section.py::`
#                      `render_switch_advisor_section` 的分區標題（渲染於 ④ 資產配置）
#      pf_add        → `ui/tab3_portfolio.py` 的「加入與管理基金」區塊標題
#    ⚠️ 上面**前五個**合併頁**目前仍各自持有自己的字面值**（它們不在當時那一批的
#    檔案邊界內）。本表是**唯一真相源**，那些頁應在後續批次改吃它 —— 已列入 PR
#    描述的待辦，`tests/test_story_nav.py::test_section_labels_match_merged_pages`
#    以實際檔案內容比對，兩邊漂移時會**當場轉紅**（不是靠人記得）。
#    ⚠️ **`switch` 不一樣，不要跟前五個混為一談**：它**已經**吃這張表
#    （`section_label("switch")`），沒有第二份字面值。故它的漂移鎖走 **AST 接線驗證**
#    而不是字串比對 —— 見 `tests/test_ia_switch_advisor_moved_to_portfolio.py::`
#    `test_section_heading_uses_the_ssot_label_and_a_stable_anchor`。
#    ⚠️ **`pf_add` 目前仍是前五個那一類**（`ui/tab3_portfolio.py` 自己持有字面值，
#    本批未改該行）—— **它沒有字串比對漂移鎖**，據實寫在這裡而不是假裝有。
_SECTION_LABELS: dict[str, str] = {
    "fund":   "🔍 單檔深掘",
    "batch":  "📦 批次掃描",
    "manage": "🗄️ 資料維護與通報",
    "diag":   "🔭 資料診斷",
    "manual": "📖 說明書",
    # 2026-09-01（客戶拍板線框 `ia-wireframe.html` Tab 04）：換股顧問自 ② 持倉體檢
    # 搬到 ④ 資產配置。理由是客戶逐字給的 —— **它產出的是「要執行的動作」，
    # 而 ② 全篇只診斷、不建議**。線框 p2「這裡不放什麼」明列
    # 「換股建議與再平衡試算 → 04（那是決策，不是診斷）」。
    # ⚠️ 名字取線框的「換股顧問」（不是舊的「換股池顧問」）—— 線框是客戶看過並
    #    拍板的那份視覺，其餘四個分區名同樣以線框為準（見 `_TAB_LABELS` 的同型註記）。
    "switch": "🎯 換股顧問",
    # ④ 頁內既有的「加入基金」區塊。收進本表**只為了讓指路文案有 SSOT 可吃** ——
    # 換股顧問在「一檔持倉都還沒載入」時要告訴使用者「去哪補」，而那個地方就是它。
    # 手抄「➕ 加入與管理基金」六個字正是本模組整篇在防的事。
    "pf_add": "➕ 加入與管理基金",
}

# 分區 → 它住在哪個頂層分頁。`where_to_find()` 與導覽的 key 解析都吃這張表。
_SECTION_TO_TAB: dict[str, str] = {
    "fund":   "research",
    "batch":  "research",
    "manage": "settings",
    "diag":   "settings",
    "manual": "settings",
    "switch": "portfolio",
    "pf_add": "portfolio",
}


# ══════════════════════════════════════════════════════════════════════════
# 2) 決策動線四站
# ══════════════════════════════════════════════════════════════════════════
# key → 這站在幹嘛。標籤本身從 `_TAB_LABELS` 導出（不再手抄一份）。
_DECISION_FLOW: tuple[tuple[str, str], ...] = (
    ("macro",     "看懂景氣位階,決定加碼或防禦"),
    ("health",    "先看手上哪幾檔健康 / 吃本金"),
    # 2026-08-31：原 `fund`(個基深掘) → `research`(當時名「基金研究」，
    # 2026-09-01 改名「標的探索」)。合併頁把「單檔深掘」
    # 與「批次掃描」收在同一站,故提示語一併從「被點名的那檔」擴為線框的一句話職責。
    ("research",  "還沒放進組合前,查一檔或掃一批的體質"),
    ("portfolio", "記帳 + 再平衡,調整持倉"),
)

# (key, 帶序號的導覽標籤, 提示) —— 對外形狀維持 3-tuple（既有測試依賴）。
# 序號取自 `_TAB_LABELS` 的分頁順序（不是本 tuple 的索引）——「決策動線第 N 站」
# 與「分頁列第 N 個」必須是同一個數字,否則指路文案講的站號與畫面對不上。
_STEPS: tuple[tuple[str, str, str], ...] = tuple(
    (_k, f"{_ORDINAL_PREFIXES[list(_TAB_LABELS).index(_k)]} {_TAB_LABELS[_k]}", _hint)
    for _k, _hint in _DECISION_FLOW
)
_VALID = {s[0] for s in _STEPS}


# ══════════════════════════════════════════════════════════════════════════
# 3) 四層流程（對齊系統流程圖）
# ══════════════════════════════════════════════════════════════════════════
# (層代號, 短標題, 這層在做什麼, 屬於這層的**導覽 key**)
#
# ⚠️ 這裡的 key **可以是分頁 key、也可以是分區 key** —— 流程層講的是「系統心智
#    模型」，與分頁怎麼切無關。2026-08-31 七→五之後 `fund` / `batch` 降級成 ③
#    標的探索**頁內**的兩個模式，但它們在流程圖上仍然同屬 L2「基金核心分析」；
#    `manage` 降級成 ⑤ 的分區，但它承載的「觀察池 Watchlist」仍屬 L3。
#    **把它們從這裡拿掉會讓流程圖失真**，故刻意保留分區 key。
# ⚠️ `manage` 實際橫跨 L3 與 L4：選股池 = 流程圖的「觀察池 Watchlist」屬 L3；
#    換股通報 = 「LINE 智慧分層推送」屬 L4。這裡把它的**主層**定在 L3
#    （Watchlist 是它最主要的資料職責），L4 的說明再指回它 —— 刻意不讓一個
#    區塊同時掛兩層，否則導覽列會出現「你在兩個地方」的矛盾。
# ⚠️ `diag` / `manual`（資料診斷 / 說明書）是支援型，不在流程圖任何一層 → 不列。
_LAYERS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("L1", "市場與全球總經",
     "全球總經 & 股債風向 → 美債殖利率 & USD/TWD → 全系統風控係數",
     ("macro",)),
    ("L2", "基金核心分析",
     "單/多筆即時診斷 · 策略選股引擎 · 已持有資產穿透",
     ("fund", "batch")),
    ("L3", "監控與評分",
     "觀察池 Watchlist + 持股組合 Portfolio → Health Score 0-100",
     ("health", "portfolio", "manage")),
    ("L4", "行動閉環",
     "每日 LINE 分層推送 → 你的二次判斷 → 轉換 / 申購扣款 → 回饋觀察池",
     ()),
)

# 導覽 key → 主層代號（由 `_LAYERS` 導出，不手寫第二份對照表）
_TAB_TO_LAYER: dict[str, str] = {
    _tab: _lid for _lid, _, _, _tabs in _LAYERS for _tab in _tabs
}


# ══════════════════════════════════════════════════════════════════════════
# 對外 API
# ══════════════════════════════════════════════════════════════════════════
def tab_label(key: str) -> str:
    """回傳該**頂層分頁**的 `st.tabs` 分頁名（不帶 ①②③④ 序號前綴）。

    §1 Fail Loud：未知 key 直接 `KeyError`，**不回退**成空字串或猜測名稱 ——
    回退只會讓「指到不存在的分頁」這類 bug 再次靜默發生。

    ⚠️ 2026-08-31 起，`fund` / `batch` / `manage` / `ref` **不再是分頁** ——
    傳它們進來一律 `KeyError`，錯誤訊息會指名改用 `where_to_find()`。
    這是刻意的：它們現在是**頁內分區**，回一個分頁名等於再次指到
    分頁列上不存在的東西（本 repo 同型 bug 已發作兩次）。
    """
    try:
        return _TAB_LABELS[key]
    except KeyError:
        _hint = ""
        if key in _SECTION_LABELS:
            _hint = (f"；'{key}' 在 2026-08-31 七→五之後是**頁內分區**不是分頁,"
                     f"請改用 where_to_find('{key}') = 「{where_to_find(key)}」")
        raise KeyError(
            f"story_nav.tab_label: 未知的分頁 key '{key}';"
            f"合法值 = {sorted(_TAB_LABELS)}{_hint}"
        ) from None


def section_label(key: str) -> str:
    """回傳該**頁內分區**的標題字（不含所屬分頁名）。

    §1 Fail Loud：未知 key 直接 `KeyError`（理由同 `tab_label`）。
    只要「分區叫什麼」，用本函式；要**指路**請用 `where_to_find()`。
    """
    try:
        return _SECTION_LABELS[key]
    except KeyError:
        _hint = ""
        if key in _TAB_LABELS:
            _hint = f"；'{key}' 是頂層分頁,請改用 tab_label('{key}')"
        raise KeyError(
            f"story_nav.section_label: 未知的分區 key '{key}';"
            f"合法值 = {sorted(_SECTION_LABELS)}{_hint}"
        ) from None


def _tab_ordinal(tab_key: str) -> str:
    """頂層分頁的站號（①②③④⑤），由 `_TAB_LABELS` 的**順序**推導。

    ⚠️ 站號**絕不寫死**：線框點名的「Tab2＝個基深掘（實際第 4）」正是寫死站號
    在分頁增刪後留下的地雷。這裡只要 `_TAB_LABELS` 順序對，站號就一定對。
    """
    return _ORDINAL_PREFIXES[list(_TAB_LABELS).index(tab_key)]


def where_to_find(key: str) -> str:
    """指路字串：**帶頂層分頁名（含站號）的完整路徑**。

    - 分區 key → `③ 🔍 標的探索 → 📦 批次掃描`
    - 分頁 key → `① 🌐 市場總覽`（沒有下一層可指）

    這是**指路文案唯一該用的函式**。直接寫「請至『📦 批次分析』分頁」這種句子，
    在七→五之後會指到一個分頁列上不存在的名字 —— 本 repo 同型 bug 已發作兩次，
    第三次的差別只在於：這次連 SSOT 都會是錯的（見模組 docstring）。

    §1 Fail Loud：未知 key 直接 `KeyError`。
    """
    if key in _SECTION_LABELS:
        _tab = _SECTION_TO_TAB[key]
        return f"{_tab_ordinal(_tab)} {_TAB_LABELS[_tab]} → {_SECTION_LABELS[key]}"
    if key in _TAB_LABELS:
        return f"{_tab_ordinal(key)} {_TAB_LABELS[key]}"
    raise KeyError(
        f"story_nav.where_to_find: 未知的 key '{key}';"
        f"合法分頁 = {sorted(_TAB_LABELS)}、合法分區 = {sorted(_SECTION_LABELS)}"
    )


def _nav_label(key: str) -> str:
    """導覽用標籤：分頁 key 走 `_TAB_LABELS`，分區 key 走 `_SECTION_LABELS`。

    只給本檔的流程導覽用（`_LAYERS` 的成員可能是任一種，見該處註解）。
    §1 Fail Loud：兩張表都沒有 → `KeyError`。
    """
    if key in _TAB_LABELS:
        return _TAB_LABELS[key]
    if key in _SECTION_LABELS:
        return _SECTION_LABELS[key]
    raise KeyError(
        f"story_nav._nav_label: '{key}' 既不是分頁也不是分區;"
        f"分頁 = {sorted(_TAB_LABELS)}、分區 = {sorted(_SECTION_LABELS)}"
    )


def _as_tab_key(key: str) -> str:
    """把**分區 key** 解析成它所屬的**分頁 key**；本來就是分頁 key 則原樣回傳。

    存在的理由（重要，不是方便用的糖）：七→五之後，`ui/tab2_single_fund.py`
    等子頁仍然呼叫 `render_story_nav("fund")` —— 它們現在是合併頁的一個模式，
    但「我在決策動線第幾站」這個問題的正確答案是**它所屬的那個分頁**（③）。
    在這裡解析，等於讓那些 caller **一個字都不用改**就得到正確的高亮，
    而不是靜默不畫（`_VALID` 檢查會讓它整條導覽消失，那是無聲的功能退化）。

    未知 key 原樣回傳 —— 呼叫端各自有自己的「不認得就不畫」路徑（見
    `render_story_nav` / `flow_nav_markdown`），不在這裡搶著 raise。
    """
    return _SECTION_TO_TAB.get(key, key)


def layer_of(key: str) -> str:
    """導覽 key → 流程層代號（`L1`~`L4`）。不屬任何層（如 `diag`）回空字串。"""
    return _TAB_TO_LAYER.get(key, "")


def story_nav_markdown(current: str) -> str:
    """決策動線麵包屑 markdown（純函式、可測）。current 為目前站 key。

    目前站用藍色粗體 highlight，其餘灰色；尾端附目前站的一句話提示。
    `current` 可以是分頁 key，也可以是**分區 key**（自動解析成所屬分頁，
    理由見 `_as_tab_key`）。
    """
    _cur = _as_tab_key(current)
    parts: list[str] = []
    for _key, _label, _hint in _STEPS:
        if _key == _cur:
            parts.append(f"**:blue[{_label}]**")
        else:
            parts.append(f":gray[{_label}]")
    line = "　→　".join(parts)
    _cur_hint = next((h for k, _, h in _STEPS if k == _cur), "")
    return f"{line}　·　_{_cur_hint}_" if _cur_hint else line


def flow_nav_markdown(current: str) -> str:
    """四層流程導覽 markdown（純函式、可測）。

    第 1 行：四層流程，目前所在層藍色粗體、其餘灰色。
    第 2 行：目前層在做什麼 + 這層有哪些分頁 / 分區 + 下一層是什麼。

    `current` 可以是導覽 key（分頁或分區，自動對應到主層）或直接給層代號
    （`L1`~`L4`）。不屬任何層（如 `diag`）→ 只畫流程、不 highlight，
    並說明本頁是支援型。
    """
    _cur_layer = current if current.startswith("L") else layer_of(current)

    _parts: list[str] = []
    for _i, (_lid, _title, _, _) in enumerate(_LAYERS, start=1):
        _txt = f"{_ORDINAL_PREFIXES[_i - 1]} {_title}"
        _parts.append(f"**:blue[{_txt}]**" if _lid == _cur_layer
                      else f":gray[{_txt}]")
    _line1 = "🧭 " + "　▸　".join(_parts)

    _meta = next((m for m in _LAYERS if m[0] == _cur_layer), None)
    if _meta is None:
        return _line1 + "　·　_本頁為支援 / 診斷用，不在決策流程的任何一層_"

    _lid, _title, _what, _tabs = _meta
    _line2 = f"**{_title}**：{_what}"
    # 本層還有哪些**其他**分頁 / 分區 —— 只列出「你現在不在的那些」，避免廢話
    _siblings = [_nav_label(t) for t in _tabs if t != current]
    if _siblings:
        _line2 += f"　·　本層另有：{'、'.join(_siblings)}"
    # 下一層
    _idx = next(i for i, m in enumerate(_LAYERS) if m[0] == _lid)
    if _idx + 1 < len(_LAYERS):
        _nxt = _LAYERS[_idx + 1]
        _line2 += f"　·　下一層 → {_ORDINAL_PREFIXES[_idx + 1]} {_nxt[1]}"
    return f"{_line1}\n\n{_line2}"


def render_story_nav(current: str) -> None:
    """在 tab 頂部渲染決策動線麵包屑（無效 key 時不渲染、不佔版面）。"""
    if _as_tab_key(current) not in _VALID:
        return
    import streamlit as st
    st.caption(story_nav_markdown(current))


def render_flow_nav(current: str) -> None:
    """在 tab 頂部渲染四層流程導覽。

    與 `render_story_nav` 的差別：後者只涵蓋決策動線 4 站（⑤ 設定與診斷不在
    其中），本函式涵蓋**整個系統**，回答「我在哪一層」。
    兩者可並存 —— 流程層是巨觀定位，決策動線是微觀順序。
    """
    import streamlit as st
    st.caption(flow_nav_markdown(current))
