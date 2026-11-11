# -*- coding: utf-8 -*-
"""palette dict → scoped CSS（只由 `build_css(palette)` 產生；本檔不寫任何色碼，全部取自 palette）。

- scoped：只在 PoC 頁的那一輪腳本以 `st.markdown(<style>)` 注入；不改 `.streamlit/config.toml`、不用 JS、不寫檔。
- 選擇器用 Streamlit 的 `data-testid`（升級改 DOM 時，`tests/poc_dual_theme/` 的瀏覽器測試會轉紅）。
- `color-scheme` 讓瀏覽器原生元件（捲軸、原生表單）跟著模式；Streamlit 的 portal 選單（主選單 popover）與頁首工具列的 chrome 能覆蓋到多少，
  以瀏覽器測試實測為準，見 evidence（不靠 JS 硬改）。
"""
from __future__ import annotations


def build_css(p) -> str:
    t = p["tones"]
    tone_rules = "\n".join(
        f".poc-tone-{k}{{color:{t[k]['text']};background:{t[k]['background']};border-color:{t[k]['border']}}}" for k in t)
    return f"""<style data-poc-theme="{p['mode']}">
:root{{color-scheme:{p['color_scheme']}}}
body,.stApp,[data-testid="stApp"]{{background:{p['page_bg']};color:{p['text']}}}
[data-testid="stHeader"]{{background:{p['page_bg']}}}
/* 原生元件各自帶 config.toml 的文字色；主區與頁首一律繼承，文字色單一來源＝palette.text */
[data-testid="stMain"],[data-testid="stMain"] *,[data-testid="stHeader"],[data-testid="stHeader"] *{{color:inherit}}
[data-testid="stSidebar"],[data-testid="stSidebar"] > div{{background:{p['sidebar_bg']}}}
[data-testid="stSidebar"],[data-testid="stSidebar"] *{{color:{p['sidebar_text']}}}
[data-testid="stSidebar"]{{border-right:1px solid {p['sidebar_border']}}}
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]{{background:{p['sidebar_bg']};border:1px solid {p['sidebar_border']}}}

/* 版面與卡片 */
.block-container{{max-width:1100px;padding-left:16px;padding-right:16px;padding-top:3.4rem}}
h1{{font-size:1.7rem !important;padding:.2rem 0 !important}}
h3{{font-size:1.2rem !important;margin:0 0 4px 0 !important;padding:0 !important}}
h4{{font-size:15px !important;margin:0 0 4px 0 !important;padding:0 !important}}
[class*="st-key-poc-card-"],.poc-card-html{{border:1px solid {p['card_border']};border-radius:8px;padding:10px 12px;margin-bottom:8px;background:{p['surface']};box-shadow:none}}
[data-testid="stMain"] [data-testid="stBaseButton-secondary"]:disabled,[data-testid="stMain"] [data-testid="stBaseButton-secondary"]:disabled *{{color:{p['disabled_text']} !important;cursor:not-allowed}}
.poc-card-html{{margin:6px 0}}
/* Streamlit markdown 容器帶 margin-bottom:-1rem：卡內最後一個 markdown 歸零，避免文字壓到下邊線（同既有預覽頁的處置） */
[class*="st-key-poc-card-"] > [data-testid="stElementContainer"]:last-child [data-testid="stMarkdownContainer"]{{margin-bottom:0}}
.poc-row{{margin:4px 0;line-height:1.55}}
.poc-note{{font-size:13px;color:{p['text2']};line-height:1.5;margin:.15rem 0}}
[data-testid="stMain"] .poc-note{{color:{p['text2']}}}
.poc-chip{{display:inline-block;border:1px solid {p['card_border']};border-radius:12px;padding:1px 10px;font-size:14px;margin:1px 6px 1px 0;white-space:normal}}
{tone_rules}

/* 圖：色一律由 class 決定（SVG 內無色碼） */
.poc-chart{{width:100%;max-width:720px;height:auto;display:block}}
.poc-axis{{stroke:{p['text2']};stroke-width:1}}
.poc-line{{stroke:{p['primary']};stroke-width:2}}
.poc-dash{{stroke:{p['text']};stroke-dasharray:6 4}}
.poc-tick,.poc-endlabel{{fill:{p['text']};font-size:12px}}
.poc-legend{{font-size:13px;color:{p['text2']};margin:4px 0}}
.poc-legend-item{{margin-right:14px;white-space:nowrap}}
.poc-legend-sample{{margin-right:4px;letter-spacing:-1px}}

/* 原生 radio：選取＝primary 實心；未選＝control_border 圓環＋surface 內圈 */
[data-testid="stMain"] label[data-testid="stRadioOption"][data-selected="true"] > div > div > div:first-child{{background-color:{p['primary']} !important}}
[data-testid="stMain"] label[data-testid="stRadioOption"]:not([data-selected="true"]) > div > div > div:first-child{{background-color:{p['control_border']} !important}}
[data-testid="stMain"] label[data-testid="stRadioOption"]:not([data-selected="true"]) > div > div > div:first-child > div{{background-color:{p['surface']} !important}}

/* 原生 radio 的 hover／focus：Streamlit 原生用半透明灰（取自 config.toml 舊 theme）；改由 palette 決定（hover 底＋鍵盤 focus 外框） */
[data-testid="stMain"] label[data-testid="stRadioOption"]:not([data-disabled="true"]):hover{{background:{p['hover_bg']}}}
[data-testid="stMain"] label[data-testid="stRadioOption"][data-focus-visible="true"]{{background:{p['hover_bg']};outline:2px solid {p['focus_ring']};outline-offset:1px}}

/* 停用的 radio：字改 disabled_text、圓點淡化、游標提示不可用（disabled 本來就免於 WCAG 對比要求，仍保持可讀） */
[data-testid="stMain"] label[data-testid="stRadioOption"][data-disabled="true"],[data-testid="stMain"] label[data-testid="stRadioOption"][data-disabled="true"] *{{color:{p['disabled_text']} !important;cursor:not-allowed}}
[data-testid="stMain"] label[data-testid="stRadioOption"][data-disabled="true"] > div > div > div:first-child{{opacity:.6}}

/* 原生 expander */
[data-testid="stMain"] [data-testid="stExpander"] details{{border-color:{p['card_border']};background:{p['surface']}}}
[data-testid="stMain"] [data-testid="stExpander"] summary:hover{{background:{p['hover_bg']}}}
/* 展開且未 hover 的 summary：Streamlit 原生給一個固定淺灰底（不隨 palette），暗色下字與底只有約 1.07:1；改為透明（透出 details 的 surface）。
   鍵盤 focus 與 hover 同用 hover_bg。 */
[data-testid="stMain"] [data-testid="stExpander"] details[open] > summary:not(:hover){{background:transparent}}
[data-testid="stMain"] [data-testid="stExpander"] summary:focus-visible{{background:{p['hover_bg']};outline:2px solid {p['focus_ring']};outline-offset:-2px}}

/* 原生 button（主區） */
[data-testid="stMain"] [data-testid="stBaseButton-secondary"]{{background:{p['surface']};border:1px solid {p['control_border']}}}
[data-testid="stMain"] [data-testid="stBaseButton-secondary"]:hover:not(:disabled){{background:{p['hover_bg']};border-color:{p['primary']}}}
[data-testid="stMain"] [data-testid="stBaseButton-secondary"]:focus-visible{{outline:2px solid {p['focus_ring']};outline-offset:2px;box-shadow:none}}

/* 頁首主選單（portal popover，不在 stMain 內）：**刻意不覆寫**。
   實測：只用 CSS 把它改成深色時，內部「Auto rerun」開關的軌道（半透明深色）在深底上幾乎看不見；
   不覆寫時它維持 Streamlit 原生淺色面板＋深色字（可讀），所以 PoC 選擇保持原生並於 evidence 記錄為「深色模式下仍是淺色」。 */
</style>"""
