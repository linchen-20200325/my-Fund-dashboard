# -*- coding: utf-8 -*-
"""Design token → CSS（G3 批）。**ui_v3 的 CSS 只能經由本檔從 `design/tokens.py` 取值**，`pages/mkt.py`、`shell/nav.py` 不得另寫色碼或尺寸。

- 只用標準函式庫；零 streamlit import；import 零副作用（只有 def）。
- 取值一律 Fail Loud：`tokens.value()` 對沒有核准值的 token 直接 raise，不給預設。
- 只注入在 ui_v3 頁面（`shell.nav.shell_css()` 由 `pages/chrome.render_navigation` 輸出；`pages/mkt.CSS`）。
  ⚠️ 這裡的 `app_css()` 會覆寫 Streamlit 在 `.streamlit/config.toml` 設的 theme 色（背景／文字／側欄／primary 單選點）：
  config.toml 為全 repo 共用（正式入口與 `ui_v2` 也讀它），G3 批不改它，所以覆寫只能住在 ui_v3 自己的 CSS。
  覆寫的選擇器是 Streamlit 的 `data-testid`；Streamlit 升級若改了 DOM，瀏覽器守衛（`test_ui_v3_market_page_browser.py` 的
  「token 實際套用」測試）會轉紅，不會靜默退回 config.toml 的舊色。
"""
from __future__ import annotations

from typing import Mapping

from ui_v3.design import tokens


def v(name: str) -> str:
    """純量 token 值（字串）。複合 token 請用 `m()`。"""
    out = tokens.value(name)
    if not isinstance(out, str):
        raise TypeError(f"token {name!r} 不是純量值：{type(out).__name__}")
    return out


def m(name: str) -> Mapping[str, str]:
    """複合 token 值（唯讀 Mapping）。"""
    out = tokens.value(name)
    if isinstance(out, str):
        raise TypeError(f"token {name!r} 不是複合值")
    return out  # type: ignore[return-value]


def card_css(selector: str, *, margin_bottom: str = "") -> str:
    """卡片外框規則（候選 A 尺寸＋B 色票）：邊 1px、面 `color.surface`、圓角 `radius.card`、內距 10×12、下距（預設 `space.2`）、無陰影。
    `selector` 同時用在 HTML 卡（`.uv3-card`）與 Streamlit 具名容器（`.st-key-uv3-card-*`），兩者同一組值；
    具名容器之間已有 Streamlit 的區塊間距（flex gap），所以它傳 `margin_bottom="0"`。"""
    shape = m("card.detail")
    return (f"{selector}{{border:{shape['border_width']} solid {v('color.card.border')};border-radius:{v('radius.card')};"
            f"padding:{shape['padding']};margin-bottom:{margin_bottom or v('space.2')};background:{v('color.surface')};"
            f"box-shadow:{v('elevation.none')}}}")


def tone_css() -> str:
    """chip 形狀與 tone 色（字／底／邊；neutral／grey 共用同組值）。"""
    chip = m("chip.neutral")
    rows = [f".uv3-chip{{display:inline-block;border-radius:{chip['radius']};padding:{chip['padding']};font-size:{chip['font_size']};"
            f"border:1px solid {m('color.tone.neutral')['border']};background:{m('color.tone.neutral')['background']};"
            f"color:{m('color.tone.neutral')['text']};margin:1px 6px 1px 0;white-space:normal}}"]
    for tone in tokens.TONE_KEYS:
        t = m(f"color.tone.{tone}")
        rows.append(f".uv3-tone-{tone}{{border-color:{t['border']};background:{t['background']};color:{t['text']}}}")
    return "\n".join(rows)


def app_css() -> str:
    """覆寫 Streamlit theme 色（只在 ui_v3 頁面；理由見檔頭）：主內容淺色、側欄深藍；primary 單選點；expander 邊線。"""
    page, text, primary = v("color.page.bg"), v("color.text.primary"), v("color.primary")
    sb_bg, sb_bg2, sb_text = v("color.sidebar.bg"), v("color.sidebar.bg2"), v("color.sidebar.text")
    sb_border = v("color.sidebar.border")
    return f"""
body,.stApp,[data-testid="stApp"]{{background:{page};color:{text}}}
[data-testid="stHeader"]{{background:{page}}}
/* Streamlit 原生元件（單選標籤、markdown、expander…）各自帶 theme 的舊文字色；主區與頁首一律改為繼承，文字色單一來源＝`color.text.primary`。
   與後面同權重的 `.uv3-*` 色規則比來源順序（本段在最前面），所以 tone／label／note 的明確色不受影響。 */
[data-testid="stMain"],[data-testid="stMain"] *,[data-testid="stHeader"],[data-testid="stHeader"] *{{color:inherit}}
[data-testid="stSidebar"]{{background:{sb_bg};color:{sb_text};border-right:1px solid {sb_border}}}
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]{{border-color:{sb_border}}}
/* 側欄目前頁的連結字色：Streamlit 以 primary 衍生一個淡紫（舊 theme）→ 改回側欄文字色；「目前頁」由粗體＋左側色條表示，不靠這個顏色 */
[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"],[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] *{{color:{sb_text}}}
[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover{{background:{sb_bg2}}}
/* 單選的圓點（原生控制項；config.toml 的 primaryColor／背景是舊值）：選取＝primary 實心；未選＝卡片邊線色的 1px 圓環＋卡面色內圈 */
[data-testid="stMain"] label[data-testid="stRadioOption"][data-selected="true"] > div > div > div:first-child{{background-color:{primary} !important}}
[data-testid="stMain"] label[data-testid="stRadioOption"]:not([data-selected="true"]) > div > div > div:first-child{{background-color:{v('color.card.border')} !important}}
[data-testid="stMain"] label[data-testid="stRadioOption"]:not([data-selected="true"]) > div > div > div:first-child > div{{background-color:{v('color.surface')} !important}}
[data-testid="stMain"] [data-testid="stExpander"] details{{border-color:{v('color.card.border')}}}
"""
