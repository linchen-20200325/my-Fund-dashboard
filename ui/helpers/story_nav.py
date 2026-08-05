"""ui/helpers/story_nav.py — 決策動線「敘事導覽列」(v19.405 Phase 4 對齊 6→5 分頁)

讓使用者順著決策動線閱讀 —
🌐 市場定調 → 💊 組合健診 → 🔍 個基深掘 → 📊 配置 & 帳本。
各決策 tab 頂部放一行麵包屑、highlight 目前所在站,建立連貫動線。
純展示、零資料依賴;內容(`story_nav_markdown`)與渲染分離以便單元測試。
"""
from __future__ import annotations

# 決策動線四站：key → (emoji+標籤, 這站在幹嘛)。v19.405 Phase 4:對齊 app.py 6→5 分頁順序。
_STEPS: tuple[tuple[str, str, str], ...] = (
    ("macro",     "① 🌐 市場定調",    "看懂景氣位階,決定加碼或防禦"),
    ("health",    "② 💊 組合健診",    "先看手上哪幾檔健康 / 吃本金"),
    ("fund",      "③ 🔍 個基深掘",     "被點名的那檔,細看買賣點"),
    ("portfolio", "④ 📊 配置 & 帳本",  "記帳 + 再平衡,調整持倉"),
)
_VALID = {s[0] for s in _STEPS}

# 導覽列標籤帶 ①②③④ 序號(動線第幾站),`st.tabs` 的分頁名不帶 —— 兩者只差前綴,
# 故用同一份 `_STEPS` 導出,避免 app.py 與本檔各自維護一份而漂移(2026-08-05 稽核
# 必修 2:三處指路文案指向不存在的分頁名,根因就是「標籤沒有 SSOT」)。
_ORDINAL_PREFIXES = "①②③④⑤⑥⑦⑧⑨⑩"


def tab_label(key: str) -> str:
    """回傳該站的 **st.tabs 分頁名**(去掉 ①②③④ 序號前綴)。

    `app.py` 的 `st.tabs([...])` 與各 Tab 內「請至 X 分頁」指路文案共用本函式,
    確保畫面上的分頁名與文案永遠同一份來源(§3.3 反捏造:不得各自寫死字串)。

    §1 Fail Loud:未知 key 直接 `KeyError`,**不回退**成空字串或猜測名稱 ——
    回退只會讓「指到不存在的分頁」這類 bug 再次靜默發生。
    """
    for _k, _label, _ in _STEPS:
        if _k == key:
            return _label.lstrip(_ORDINAL_PREFIXES).strip()
    raise KeyError(
        f"story_nav.tab_label: 未知的決策動線 key '{key}';合法值 = {sorted(_VALID)}")


def story_nav_markdown(current: str) -> str:
    """組敘事麵包屑 markdown（純函式、可測）。current 為目前站 key。

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


def render_story_nav(current: str) -> None:
    """在 tab 頂部渲染敘事導覽列（無效 key 時不渲染、不佔版面）。"""
    if current not in _VALID:
        return
    import streamlit as st
    st.caption(story_nav_markdown(current))
