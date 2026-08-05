"""ui/tab1_macro_midcycle.py — v19.262 P3-A3 從 tab1_macro.py 抽出的 📈 中期循環區塊。

從 `ui/tab1_macro.py:render_macro_tab()` body 內抽出獨立 section,降低主檔 LOC:
- `render_mid_cycle_section(ind, show_l3, show_l2_plus)` — render 入口

內容包含:
- Z-Score 矩陣(卡片 + Raw data expander;指標數一律由 `len(_ZS_INDICATORS)` 導出) — L3 only
- L3 情境判斷卡(Situation A 庫存調整 / Situation B 極端乖離) — L3 only

設計:
- 不依賴 render_macro_tab 的 closure local var,全部走參數注入
- `_render_macro_indicator_card` lazy import(避免循環依賴 tab1_macro)
- `_PMI_SITUATION_BELOW` 從 shared.macro_thresholds_v2 自取(與主檔同源)
- §8.2:L3 UI helper,純渲染 + ind 讀取(不寫 session_state)
"""
from __future__ import annotations

import html as _html

import streamlit as st

from shared.colors import (
    BG_DARK_AMBER_2,
    BG_DARK_RED_2,
    GH_FG_PRIMARY,
    GRAY_CC,
    MATERIAL_ORANGE,
    MATERIAL_RED,
    MD_AMBER_300,
    MD_GREEN_A200,
    MD_ORANGE_A200,
    TRAFFIC_GREEN,
    TRAFFIC_NEUTRAL,
    TRAFFIC_RED,
    TRAFFIC_YELLOW,
)
from shared.macro_thresholds_v2 import PMI_THRESHOLDS as _PMI_THR

_PMI_SITUATION_BELOW = _PMI_THR["alert_generation"]["contraction_below"]  # 50.0

# ── Z-Score 矩陣指標盤(SSOT)────────────────────────────────────────────────
# spec: (key, 顯示名 fallback, 單位, 小數位, high_is_bad, z>0 白話, z<0 白話)
# ⚠️ 「顯示名」只是 **fallback** —— 卡片標題一律優先吃 `ind[key]["name"]`
#    (服務層 SSOT,見 `_card_title`)。原本 UI 完全不讀 name,造成:
#    (a) PMI 走 Phil Fed 代理時服務層已改名「ISM 製造業 PMI（Phil Fed 替代）」,
#        畫面仍寫「ISM PMI」→ 63.8 被讀成官方 ISM(官方 2026-07 實際 55.6);
#    (b) FED_BS 自 v19.193 起輸入已換成淨流動性(WALCL−RRP−TGA),服務層 name 已改
#        「淨流動性 (YoY)」,畫面仍寫「Fed 資產負債表 YoY」且白話寫死「QT 縮表」。
#    2026-08-05 稽核 🔴 必修 1(§1 造假違憲)。
# ⚠️ 本表筆數 = 畫面上寫的「N 指標」,三處文案一律 `len(_ZS_INDICATORS)` 導出,
#    禁止再寫死數字(§3.3;原本 caption 寫 18、標題與 expander 寫 23,實際 18)。
_ZS_INDICATORS: list = [
    ("SLOOS",        "SLOOS 銀行放款意願", "%",   1,  True,  "銀行緊縮放貸",     "銀行寬鬆放貸"),
    ("ADL",          "RSP/SPY 廣度",        "%",   2,  False, "廣度健康",          "大型股獨撐"),
    ("PMI",          "ISM PMI",             "",    1,  False, "製造業擴張",        "製造業收縮"),
    ("LEI",          "⭐ CFNAI 領先指標",   "",    2,  False, "景氣加速",          "景氣放緩"),
    ("CPI",          "CPI 通膨率",          "%",   1,  True,  "物價壓力升溫",      "通膨壓力減退"),
    ("PPI",          "PPI 生產者物價",      "%",   2,  True,  "上游成本升溫",      "上游成本回落"),
    ("INFL_EXP_5Y",  "⭐ 5Y 通膨預期",      "%",   2,  True,  "通膨預期升溫",      "通膨預期降溫"),
    ("FED_RATE",     "聯準會利率",          "%",   2,  True,  "資金成本上升",      "資金成本下降"),
    ("UNEMPLOYMENT", "失業率",              "%",   1,  True,  "勞動市場惡化",      "勞動市場改善"),
    ("CONT_CLAIMS",  "⭐ 持續失業金週頻",   "萬",  0,  True,  "失業惡化",          "就業改善"),
    ("COPPER",       "銅博士月漲跌",        "%",   1,  False, "全球景氣轉熱",      "全球景氣轉冷"),
    ("CONSUMER_CONF","消費者信心",          "",    1,  False, "消費信心強",        "消費信心弱"),
    ("JOBLESS",      "初領失業金",          "萬",  1,  True,  "裁員壓力升溫",      "裁員壓力降溫"),
    ("M2",           "M2 YoY",              "%",   1,  False, "貨幣供給寬鬆",      "貨幣供給緊縮"),
    ("M2_WEEKLY",    "⭐ M2 週頻 YoY",      "%",   2,  False, "貨幣供給寬鬆",      "貨幣供給緊縮"),
    # FED_BS:本格輸入是**淨流動性**(WALCL−RRP−TGA),不是毛額 Fed 資產 —— 原白話
    # 寫死「QE 擴表 / QT 縮表」會把 TGA 重建(財政部發債補庫存的機械性抽水)誤讀成 Fed 縮表。
    # 用語刻意不寫死「淨」:服務層在淨流動性序列不足 53 週時有 §1 降級回毛額 WALCL 的
    # 路徑,寫死「淨流動性」在降級時就變成新的錯標籤;「流動性轉寬/轉緊」兩條路徑皆為真,
    # 真正是哪一條由卡片標題(吃服務層 name)與 desc 分解說明。
    ("FED_BS",       "Fed 資產負債表 YoY",  "%",   2,  False, "流動性轉寬",        "流動性轉緊"),
    ("DXY",          "美元指數",            "",    2,  True,  "美元走強（外幣壓力）","美元走弱（外幣受益）"),
    ("PERMIT_HOUSING","⭐ 建照核發",         "千",  0,  False, "房市領先強",        "房市領先弱"),
]


def _card_title(spec_name: str, zd: dict) -> str:
    """卡片標題 = ⭐ 前綴(若有)+ ⚠️(代理值)+ **服務層 name**(缺則退 spec fallback)。

    - **服務層 name 優先**:name 是指標身分的 SSOT,代理 / 升級來源時服務層會改名
      (PMI→「ISM 製造業 PMI（Phil Fed 替代）」、FED_BS→「淨流動性 (YoY)」)。
    - **保留 ⭐**:⭐ 是本表自有語意(v16.1 高頻替代源,見矩陣下方 caption),
      服務層 name 不帶,直接整條換掉會讓那行 caption 變成空話。
    - **is_proxy → ⚠️ 前綴**:§1「代理值不可偽裝成本尊」。不依賴 name 字串裡剛好有
      「替代」二字(那是文案,會改),旗標才是契約。
    """
    _spec = str(spec_name or "")
    _star = "⭐ " if _spec.startswith("⭐") else ""
    _fallback = _spec[1:].strip() if _star else _spec
    _name = str((zd or {}).get("name") or "").strip() or _fallback
    _proxy = "⚠️ " if (zd or {}).get("is_proxy") else ""
    return f"{_star}{_proxy}{_name}"


def _card_note(verdict: str, zd: dict) -> str:
    """卡片註腳 = 白話判讀 +（代理註記）+ 服務層 `desc`,以 `<br>` 分行。

    原本 UI 完全沒渲染 `desc`,服務層寫好的口徑說明(含 FED_BS 的
    「Fed資產 +x% / TGA 抽水 / RRP 釋水」分解)在畫面上 **0 consumer**
    (`PROCESS.md §4`:算對了但沒接出去)。此處把它接出來。
    文字一律 HTML-escape:desc 內含 `>50` / `<45` 等符號,直接塞進
    `unsafe_allow_html` 的卡片會被當標籤解析。
    """
    _parts = [str(verdict or "")]
    _pn = str((zd or {}).get("proxy_note") or "").strip()
    if (zd or {}).get("is_proxy") and _pn:
        _parts.append(f"⚠️ {_pn}")
    _desc = str((zd or {}).get("desc") or "").strip()
    if _desc:
        _parts.append(_desc)
    return "<br>".join(_html.escape(p) for p in _parts if p)


def render_mid_cycle_section(
    ind: dict,
    show_l3: bool = True,
    show_l2_plus: bool = True,
) -> None:
    """渲染 📈 中期循環 section(Z-Score 矩陣 + L3 情境判斷)。

    Args:
        ind: indicators dict(總經指標)
        show_l3: L3 toggle,False 跳過 Z-Score 矩陣 + 情境判斷
        show_l2_plus: L2+ toggle(保留為相容語意,目前無實際 gating)
    """
    from ui.tab1_macro import _render_macro_indicator_card  # lazy 避循環

    # 2026-08-05 稽核 🟡 必修 3:指標數三處寫死且已漂移(caption 18 / 標題 23 /
    # expander 23,實際 18)→ 一律由 `len(_ZS_INDICATORS)` 導出(§3.3 反捏造)。
    _n_zs = len(_ZS_INDICATORS)

    st.divider()
    st.markdown("## 📈 中期循環")
    st.caption(f"景氣循環 3-12 月 ｜ Z-Score 矩陣({_n_zs} 指標)+ 情境判斷")

    # L3 指標 Z-Score 矩陣 — L3 only
    # ══════════════════════════════════════════════════
    if show_l3:
        # v17.2：Z-Score 矩陣升級 — 燈號儀表 + 白話判讀 + |Z| DESC 排序
        st.markdown(f"**🔬 Z-Score 矩陣（{_n_zs} 指標 ｜ 異常先看）**")
        # 四色說明條（HTML，避免破壞 Streamlit theme）
        st.markdown(
            "<div style='display:flex;gap:6px;flex-wrap:wrap;margin:4px 0 8px'>"
            f"<span style='background:#0a3d1f;color:{MD_GREEN_A200};padding:3px 10px;"
            "border-radius:4px;font-size:12px'>🟢 正常 |Z|&lt;1</span>"
            f"<span style='background:#3d3408;color:{MD_AMBER_300};padding:3px 10px;"
            "border-radius:4px;font-size:12px'>🟡 關注 |Z|≥1</span>"
            f"<span style='background:#4a2a08;color:{MD_ORANGE_A200};padding:3px 10px;"
            "border-radius:4px;font-size:12px'>🟠 警示 |Z|≥1.5</span>"
            "<span style='background:#4a0d0d;color:#ff8a80;padding:3px 10px;"
            "border-radius:4px;font-size:12px'>🔴 極端 |Z|≥2</span>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.caption("📖 已依 |Z| 由大至小排序，最異常的指標置頂。⭐ = v16.1 高頻替代源")
        import pandas as _pd_zs
        _zs_rows = []
        for _zk, _zname, _zunit, _zdec, _zhigh_bad, _z_pos_phrase, _z_neg_phrase in _ZS_INDICATORS:
            _zd = ind.get(_zk) or {}
            _zv = _zd.get("value")
            _zs_raw = _zd.get("series")
            # 標題吃服務層 name(代理 / 升級來源時卡片才不會沿用舊標籤)— §1 必修 1
            _ztitle = _card_title(_zname, _zd)
            # 預設行：資料不足時佔位（不參與 |Z| 排序，會 sink 到表尾）
            if _zv is None:
                _zs_rows.append({
                    "_abs": -1, "_key": _zk, "指標": _ztitle, "當前值": "—",
                    "白話判讀": "⬜ 資料不足，待補",
                    "_note": _card_note("⬜ 資料不足，待補", _zd),
                    "_color": TRAFFIC_NEUTRAL, "_trend": [], "_signal": "⬜ 無資料",
                })
                continue
            try:
                _zv_f = float(_zv)
            except (TypeError, ValueError):
                _zs_rows.append({
                    "_abs": -1, "_key": _zk, "指標": _ztitle, "當前值": str(_zv)[:10],
                    "白話判讀": "⬜ 數值格式異常",
                    "_note": _card_note("⬜ 數值格式異常", _zd),
                    "_color": TRAFFIC_NEUTRAL, "_trend": [], "_signal": "⬜ 格式異常",
                })
                continue
            _z_score = None
            _trend_list = []  # v19.187 sparkline 用近 8 期
            if _zs_raw is not None:
                try:
                    _zser = (_zs_raw if isinstance(_zs_raw, _pd_zs.Series)
                             else _pd_zs.Series(_zs_raw)).dropna()
                    try:
                        _trend_list = [float(_x) for _x in _zser.tail(8).tolist()]
                    except Exception:
                        _trend_list = []
                    if len(_zser) >= 10:
                        _zmu, _zsig = float(_zser.mean()), float(_zser.std())
                        if _zsig > 0 and not (_zsig != _zsig):  # NaN guard
                            _z_cand = (_zv_f - _zmu) / _zsig
                            if _z_cand == _z_cand:  # NaN guard
                                _z_score = _z_cand
                except Exception:
                    pass  # smoke-allow-pass
            _unit_s = f" {_zunit}" if _zunit else ""
            _val_s  = f"{_zv_f:.{_zdec}f}{_unit_s}"
            # 燈號 + 白話 + 卡片邊框色（對齊四色說明條）
            if _z_score is None:
                _verdict = "⬜ 樣本不足，無法判讀"
                _abs_z = -1
                _zcolor = TRAFFIC_NEUTRAL
                _zsig_txt = "⬜ 樣本不足"
            else:
                _abs_z = abs(_z_score)
                _phrase = _z_pos_phrase if _z_score > 0 else _z_neg_phrase
                if _abs_z >= 2:
                    _icon, _zcolor = "🔴 極端", TRAFFIC_RED
                elif _abs_z >= 1.5:
                    _icon, _zcolor = "🟠 警示", MD_ORANGE_A200
                elif _abs_z >= 1:
                    _icon, _zcolor = "🟡 關注", TRAFFIC_YELLOW
                else:
                    _icon, _zcolor = "🟢 正常", TRAFFIC_GREEN
                _verdict = f"{_icon}（{_phrase}，Z={_z_score:+.2f}）"
                _zsig_txt = _icon
            _zs_rows.append({
                "_abs": _abs_z, "_key": _zk, "指標": _ztitle, "當前值": _val_s,
                "白話判讀": _verdict, "_note": _card_note(_verdict, _zd),
                "_color": _zcolor,
                "_trend": _trend_list, "_signal": _zsig_txt,
            })
        if _zs_rows:
            # |Z| DESC，資料不足（_abs=-1）一律沉底
            _zs_rows.sort(key=lambda r: r["_abs"], reverse=True)
            # v19.187 — 小圖卡片(範本:短線雷達):Z 可算的指標(異常先看)做成卡片格,每排 5
            _zs_carded = [r for r in _zs_rows if r["_abs"] >= 0]
            for _ci in range(0, len(_zs_carded), 5):
                _cz = st.columns(5)
                for _cc, _r in zip(_cz, _zs_carded[_ci:_ci + 5]):
                    with _cc:
                        _render_macro_indicator_card(
                            title=_r["指標"], signal=_r["_signal"], color=_r["_color"],
                            value_str=_r["當前值"], note=_r["_note"], label="Z-Score 矩陣",
                            trend=_r["_trend"], spark_key=f"zs_{_r['_key']}")
            # Raw data:完整指標表收進 expander(user:Raw data 縮起來,要看時候才打開)
            # 表格欄位維持純文字 `白話判讀`(dataframe cell 不解析 `<br>`),
            # 服務層 desc 只在卡片註腳呈現。
            with st.expander(f"📋 Z-Score 完整矩陣（{_n_zs} 指標表 ｜ Raw data）", expanded=False):
                _zs_df = _pd_zs.DataFrame([
                    {"指標": r["指標"], "當前值": r["當前值"], "白話判讀": r["白話判讀"]}
                    for r in _zs_rows])
                st.dataframe(_zs_df, use_container_width=True, hide_index=True,
                             column_config={
                                 "指標":     st.column_config.TextColumn(width="small"),
                                 "當前值":   st.column_config.TextColumn(width="small"),
                                 "白話判讀": st.column_config.TextColumn(width="large"),
                             })

    # ══════════════════════════════════════════════════
    # L3 情境判斷卡（Logic A / B）— L3 only
    # v19.137: 物理重排後本區在 War Room 之前執行,_sahm_v/_adl_v
    #          需在此自行從 ind 取(不依賴下方 ⚠️ 拐點桶 War Room 定義)
    # ══════════════════════════════════════════════════
    if show_l3:
        _pmi_v = float((ind.get("PMI") or {}).get("value") or 0)
        _sahm_v = float((ind.get("SAHM") or {}).get("value") or 0)
        _adl_v = float((ind.get("ADL") or {}).get("value") or 0)
        _l3_sit_cards = []
        if _pmi_v > 0 and _pmi_v < _PMI_SITUATION_BELOW and _sahm_v < 0.5:
            _l3_sit_cards.append({
                "icon": "🟡", "border": MATERIAL_ORANGE, "bg": BG_DARK_AMBER_2,
                "title": "【Situation A — 庫存調整，非衰退】",
                "body": (f"PMI={_pmi_v:.1f}（<{_PMI_SITUATION_BELOW:.0f} 收縮）但薩姆規則={_sahm_v:.2f}（<0.5 安全線）。"
                         f"製造業庫存去化壓力，消費端仍撐盤，非系統性衰退訊號。"
                         f"策略：維持衛星資產比重，等待 PMI 觸底回升確認後加碼。"),
            })
        if _adl_v < -2:
            _l3_sit_cards.append({
                "icon": "🔴", "border": MATERIAL_RED, "bg": BG_DARK_RED_2,
                "title": "【Situation B — 極端乖離警報】",
                "body": (f"RSP/SPY 市場廣度={_adl_v:.2f}%（< -2% 危險線）。"
                         f"大型權值股虛假拉抬，等權重指數嚴重落後。"
                         f"策略：啟動衛星部位分批停利，降低集中型/主題型基金配置。"),
            })
        if _l3_sit_cards:
            st.markdown("##### 🧭 L3 情境判斷")
            for _sc in _l3_sit_cards:
                st.markdown(
                    f"<div style='background:{_sc['bg']};border-left:4px solid {_sc['border']};"
                    f"border-radius:0 10px 10px 0;padding:12px 16px;margin:6px 0'>"
                    f"<span style='font-size:16px'>{_sc['icon']}</span> "
                    f"<b style='color:{GH_FG_PRIMARY}'>{_sc['title']}</b><br>"
                    f"<span style='color:{GRAY_CC};font-size:13px'>{_sc['body']}</span></div>",
                    unsafe_allow_html=True)

    # ── L2 視角到此結束，L3 繼續顯示完整儀表板 ──────────────────
    if not show_l2_plus:
        pass  # L1 只看 Gauge + 清單，不繼續渲染下方 L3 內容
