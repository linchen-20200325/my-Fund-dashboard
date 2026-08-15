"""ui/helpers/story_nav.py — 分頁名 SSOT + 決策動線 + **四層流程導覽**

本檔提供三件互相關聯、但語意不同的東西：

1. **`tab_label(key)` — 全部 7 個分頁名的唯一來源**
   `app.py` 的 `st.tabs([...])` 與各處「請至 X 分頁」指路文案共用它。
   2026-08-05 稽核 🔴 必修 2 的根因就是「標籤沒有 SSOT」，三處文案指向不存在
   的分頁名；2026-08-14 稽核又抓到 `ui/sidebar.py` 三處漏網。

2. **決策動線四站（`_STEPS` / `story_nav_markdown`）**
   🌐 市場定調 → 💊 組合健診 → 🔍 個基深掘 → 📊 配置 & 帳本。
   回答「照順序讀，我下一步該看哪」。

3. **四層流程導覽（`_LAYERS` / `flow_nav_markdown`）— 2026-08-14 新增**
   對齊 user 提供的系統流程圖：
       ① 市場與全球總經層 → ② 基金核心分析模組
       → ③ 監控與評分區 → ④ 行動閉環（LINE 推送 → 用戶動作 → 回饋觀察池）
   回答「我現在在整個系統的哪一層、這層在做什麼、資料往哪流」。

   為什麼是「導覽」而不是「把 7 分頁合併成 4 個」（2026-08-14 user 拍板）：
   流程圖的價值是**心智模型**，不必等於分頁數量。v19.405 才做完 6→5 重排、
   v19.433 又加了「我的管理室」變 7，分頁結構動盪已多；且真合併會踩到
   user 自訂的「去重 ≠ 合併資料」原則。

純展示、零資料依賴；內容（`*_markdown`）與渲染（`render_*`）分離以便單元測試。
"""
from __future__ import annotations

# 導覽列標籤帶 ①②③④ 序號(動線第幾站),`st.tabs` 的分頁名不帶 —— 兩者只差前綴,
# 故由同一份來源導出,避免 app.py 與本檔各自維護一份而漂移。
_ORDINAL_PREFIXES = "①②③④⑤⑥⑦⑧⑨⑩"


# ══════════════════════════════════════════════════════════════════════════
# 1) 分頁名 SSOT — 全部 7 個頂層分頁
# ══════════════════════════════════════════════════════════════════════════
# 2026-08-14：原本只有決策動線 4 站在這裡，`📦 批次分析` / `📋 我的管理室` /
# `📖 參考 / 診斷` 三個字面值寫死在 `app.py` 的 `st.tabs([...])` 裡 ——
# 那就是「第二份標籤」，正是本檔存在要防的東西。一併收進來。
_TAB_LABELS: dict[str, str] = {
    "macro":     "🌐 市場定調",
    "health":    "💊 組合健診",
    "batch":     "📦 批次分析",
    "fund":      "🔍 個基深掘",
    "portfolio": "📊 配置 & 帳本",
    "manage":    "📋 我的管理室",
    "ref":       "📖 參考 / 診斷",
}


# ══════════════════════════════════════════════════════════════════════════
# 2) 決策動線四站
# ══════════════════════════════════════════════════════════════════════════
# key → 這站在幹嘛。標籤本身從 `_TAB_LABELS` 導出（不再手抄一份）。
_DECISION_FLOW: tuple[tuple[str, str], ...] = (
    ("macro",     "看懂景氣位階,決定加碼或防禦"),
    ("health",    "先看手上哪幾檔健康 / 吃本金"),
    ("fund",      "被點名的那檔,細看買賣點"),
    ("portfolio", "記帳 + 再平衡,調整持倉"),
)

# (key, 帶序號的導覽標籤, 提示) —— 對外形狀維持 3-tuple（既有測試依賴）。
_STEPS: tuple[tuple[str, str, str], ...] = tuple(
    (_k, f"{_ORDINAL_PREFIXES[_i]} {_TAB_LABELS[_k]}", _hint)
    for _i, (_k, _hint) in enumerate(_DECISION_FLOW)
)
_VALID = {s[0] for s in _STEPS}


# ══════════════════════════════════════════════════════════════════════════
# 3) 四層流程（對齊系統流程圖）
# ══════════════════════════════════════════════════════════════════════════
# (層代號, 短標題, 這層在做什麼, 屬於這層的分頁 key)
#
# ⚠️ `manage`（我的管理室）實際橫跨 L3 與 L4：選股池 = 流程圖的「觀察池
#    Watchlist」屬 L3；換股通報 = 「LINE 智慧分層推送」屬 L4。這裡把它的
#    **主層**定在 L3（Watchlist 是它最主要的資料職責），L4 的說明再指回它 ——
#    刻意不讓一個分頁同時掛兩層，否則導覽列會出現「你在兩個地方」的矛盾。
# ⚠️ `ref`（參考 / 診斷）是支援型，不在流程圖任何一層 → 主層留空。
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

# 分頁 key → 主層代號（由 `_LAYERS` 導出，不手寫第二份對照表）
_TAB_TO_LAYER: dict[str, str] = {
    _tab: _lid for _lid, _, _, _tabs in _LAYERS for _tab in _tabs
}


# ══════════════════════════════════════════════════════════════════════════
# 對外 API
# ══════════════════════════════════════════════════════════════════════════
def tab_label(key: str) -> str:
    """回傳該分頁的 **st.tabs 分頁名**（不帶 ①②③④ 序號前綴）。

    §1 Fail Loud：未知 key 直接 `KeyError`，**不回退**成空字串或猜測名稱 ——
    回退只會讓「指到不存在的分頁」這類 bug 再次靜默發生。
    """
    try:
        return _TAB_LABELS[key]
    except KeyError:
        raise KeyError(
            f"story_nav.tab_label: 未知的分頁 key '{key}';"
            f"合法值 = {sorted(_TAB_LABELS)}"
        ) from None


def layer_of(key: str) -> str:
    """分頁 key → 流程層代號（`L1`~`L4`）。不屬任何層（如 `ref`）回空字串。"""
    return _TAB_TO_LAYER.get(key, "")


def story_nav_markdown(current: str) -> str:
    """決策動線麵包屑 markdown（純函式、可測）。current 為目前站 key。

    目前站用藍色粗體 highlight，其餘灰色；尾端附目前站的一句話提示。
    """
    parts: list[str] = []
    for _key, _label, _hint in _STEPS:
        if _key == current:
            parts.append(f"**:blue[{_label}]**")
        else:
            parts.append(f":gray[{_label}]")
    line = "　→　".join(parts)
    _cur_hint = next((h for k, _, h in _STEPS if k == current), "")
    return f"{line}　·　_{_cur_hint}_" if _cur_hint else line


def flow_nav_markdown(current: str) -> str:
    """四層流程導覽 markdown（純函式、可測）。

    第 1 行：四層流程，目前所在層藍色粗體、其餘灰色。
    第 2 行：目前層在做什麼 + 這層有哪些分頁 + 下一層是什麼。

    `current` 可以是分頁 key（自動對應到主層）或直接給層代號（`L1`~`L4`）。
    不屬任何層（如 `ref`）→ 只畫流程、不 highlight，並說明本頁是支援型。
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
    # 本層還有哪些**其他**分頁 —— 只列出「你現在不在的那些」，避免廢話
    _siblings = [_TAB_LABELS[t] for t in _tabs if t != current]
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
    if current not in _VALID:
        return
    import streamlit as st
    st.caption(story_nav_markdown(current))


def render_flow_nav(current: str) -> None:
    """在 tab 頂部渲染四層流程導覽。

    與 `render_story_nav` 的差別：後者只涵蓋決策動線 4 站（批次分析 / 管理室 /
    參考診斷不在其中），本函式涵蓋**整個系統**，回答「我在哪一層」。
    兩者可並存 —— 流程層是巨觀定位，決策動線是微觀順序。
    """
    import streamlit as st
    st.caption(flow_nav_markdown(current))
