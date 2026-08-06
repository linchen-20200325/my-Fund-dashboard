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

卡片四個欄位的取值來源(全部走服務層,UI 不自建第二份真相 — §3.3):
- 標題 → `ind[key]["name"]`(`_card_title`)
- 單位 → `ind[key]["unit"]`(`_card_unit`;spec 欄僅剩 fallback)
- 分類 → `ind[key]["type"]`(`_card_label`;缺則誠實標未分類)
- 註腳 → `ind[key]["desc"]` + `MACRO_EDU[key]["historical_anchor"]`(`_card_note`)
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
from shared.converters import safe_num as _safe_num
from shared.macro_thresholds_v2 import PMI_THRESHOLDS as _PMI_THR
# 教學語料(唯讀)。CLAUDE.md §8.3 F-GRAY-4 已裁決該檔敘事 by-design 不收 SSOT,
# 本檔**只讀不寫**;缺內容一律回報請 user 決定,不在 UI 層自寫指標語意字串。
from ui.components.macro_card_edu import MACRO_EDU as _MACRO_EDU

_PMI_SITUATION_BELOW = _PMI_THR["alert_generation"]["contraction_below"]  # 50.0

# 卡片左下 label 的固定前綴 + 服務層未給分類時的誠實佔位(§1:不猜桶)
_ZS_MATRIX_LABEL = "Z-Score 矩陣"
_ZS_TYPE_UNKNOWN = "未分類"

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
    # ADL:本格 value 是 **RSP 收盤 ÷ SPY 收盤的比值**(無因次,量級 ~0.29),不是百分比。
    # spec 原本硬寫 "%" → 畫面印成「值 0.29 %」(§4.1 量綱陷阱);服務層 `unit` 標的是
    # 空字串,才是這個數字的權威單位。單位改吃服務層(見 `_card_unit`),本欄僅剩 fallback。
    # 小數位 2 → 4:對齊服務層 round(v, 4);比值的月變動量級約 0.003,留 2 位會被
    # 四捨五入成「永遠不動」,等於畫面上看不出廣度變化。
    ("ADL",          "RSP/SPY 廣度",        "",    4,  False, "廣度健康",          "大型股獨撐"),
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

# 歷史錨點的適用範圍。原為 3 張樣張(`{"PMI","CPI","SLOOS"}`)給 user 看效果;
# 2026-08-05 稽核 🟡 建議 7:user 核准後**鋪滿全表**,改由 `_ZS_INDICATORS` 導出
# (§3.3:名單只有一份,矩陣增減指標時自動跟上,不必記得改第二處)。
#
# `MACRO_EDU` 缺 `historical_anchor` 的 key 不會因此多出假錨點:`_card_note` 與
# `_decoration_coverage` 兩邊的條件都是「在本名單內 **且** 語料真的有非空錨點」,
# 缺語料者照樣不掛、也不計入覆蓋率(§1 不補假內容)。
# 這也是覆蓋率 caption 存在的原因 —— 鋪滿名單後,覆蓋率仍誠實反映實際有幾張。
_EDU_ANCHOR_PILOT: frozenset = frozenset(_row[0] for _row in _ZS_INDICATORS)


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


def _card_unit(spec_unit: str, zd: dict) -> str:
    """卡片單位 = **服務層 `unit` 欄**優先,服務層沒給該欄才退 spec fallback(§3.3 SSOT)。

    `unit` 與 `value` 在服務層同一個 dict literal 產出,是該數值單位的唯一權威。
    UI 另寫一份 = 第二份真相,必然漂移 —— ADL 就是實例:服務層標無單位(比值),
    spec 硬寫百分比,畫面把 0.29 的比值印成「0.29 %」(§4.1 量綱陷阱)。

    ⚠️ 判存在用 `in` 而非 falsy:服務層對無因次指標(ADL / DXY / PMI / LEI /
    CONSUMER_CONF)明確給空字串,那是**有意義的答案**(此值無單位)。用
    `.get(...) or spec_unit` 會把它誤讀成「服務層沒給」而退回 spec 的錯單位。
    """
    _zd = zd or {}
    _u = _zd["unit"] if "unit" in _zd else spec_unit
    return str(_u or "").strip()


def _card_label(zd: dict) -> str:
    """卡片左下第二行 = 矩陣名 + **服務層 `type`**(該指標的分類)。

    問題:整盤卡片全掛在「📈 中期循環（景氣循環 3-12 月）」底下,但依服務層 `type`,
    只有一部分真的是中期循環指標(美元指數是資金流向、RSP/SPY 是市場廣度、
    M2 / 淨流動性是流動性)。初學者會問「為什麼美元指數屬於景氣循環 3-12 月」。
    這裡不做物理搬移(那會打散「異常先看」的 |Z| 排序),只把分類標在卡上。

    **分類一律讀服務層 `type`,UI 不自建對照表**(§3.3):
    `shared.macro_buckets.SPECS_BY_KEY` 雖也是桶 SSOT,但其 key 與本矩陣的
    indicator key 大量不同名(cpi_yoy / m2_yoy / fed_bs_yoy / cfnai …),
    本表僅少數 key 能直接對上,要接就得在 UI 層再寫一份別名表 —— 那正是
    §3.3 禁止的第二份真相。服務層 `type` 則本表全覆蓋且零轉換。
    服務層沒給 `type` → 誠實顯示未分類佔位,不猜(§1)。
    """
    _t = str((zd or {}).get("type") or "").strip()
    return f"{_ZS_MATRIX_LABEL} · {_t or _ZS_TYPE_UNKNOWN}"


def _card_note(verdict: str, zd: dict, edu: dict | None = None) -> str:
    """卡片註腳 = 白話判讀 +（代理註記）+ 服務層 `desc` +（歷史錨點）,以 `<br>` 分行。

    原本 UI 完全沒渲染 `desc`,服務層寫好的口徑說明(含 FED_BS 的
    「Fed資產 +x% / TGA 抽水 / RRP 釋水」分解)在畫面上 **0 consumer**
    (`PROCESS.md §4`:算對了但沒接出去)。此處把它接出來。
    文字一律 HTML-escape:desc 內含 `>50` / `<45` 等符號,直接塞進
    `unsafe_allow_html` 的卡片會被當標籤解析。

    **`edu` 為選填第三參數**(預設 None → 與既有兩參數呼叫行為完全相同,
    既有 caller 與測試不受影響)。傳入 `MACRO_EDU[key]` 時附掛其 `historical_anchor`:
    單句、帶危機定錨與安全區,直接回答初學者最缺的那一題「這個數字算大算小」。
    該語料在 `ui/components/macro_card_edu.py` 已寫好 24 指標卻全站 0 consumer,
    本次是把它接出來,**不在 UI 層新寫任何指標語意字串**(該檔只讀不寫,
    CLAUDE.md §8.3 F-GRAY-4 已裁決其敘事不收 SSOT)。
    """
    _parts = [str(verdict or "")]
    _pn = str((zd or {}).get("proxy_note") or "").strip()
    if (zd or {}).get("is_proxy") and _pn:
        _parts.append(f"⚠️ {_pn}")
    _desc = str((zd or {}).get("desc") or "").strip()
    if _desc:
        _parts.append(_desc)
    _anchor = str((edu or {}).get("historical_anchor") or "").strip()
    if _anchor:
        _parts.append(f"📊 {_anchor}")
    return "<br>".join(_html.escape(p) for p in _parts if p)


def _decoration_coverage(spec_key_of) -> tuple:
    """回 `(有歷史錨點的張數, 畫得出警戒線的張數)` —— 兩個數字**一律導出**。

    2026-08-05 稽核 🟡 建議 5:18 張同款卡只有少數幾張帶裝飾,而且卡片依 |Z|
    排序 → 有裝飾的那幾張每次載入都出現在不同位置,使用者歸納不出規則,看起來
    像壞掉。實際是**四種狀態並存**(錨點✓線✓ / 錨點✓線✗ / 錨點✗線✓ / 兩者皆無),
    要在 caption 誠實揭露覆蓋率,把「系統壞了」變成「這功能還在鋪」。

    §3.3:pilot 名單日後會擴充,寫死張數必然漂移 —— 故兩個數字都**照渲染時的
    真實條件重算**:
      - 錨點:key 在 pilot 名單內 **且** `MACRO_EDU` 真的有非空 `historical_anchor`
        (與 `_card_note` 附掛錨點的條件同一條,不另立標準)
      - 警戒線:走呼叫端傳進來的 `spec_key_of` 解析器(= `ui.tab1_macro.
        _zs_danger_spec_key`),不在本檔重寫一份「key 轉小寫查 registry」的規則
        —— 那正是該函式 docstring 明令禁止的第二份真相

    `spec_key_of` 以參數注入而非直接 import:本檔對 `ui.tab1_macro` 只能 lazy
    import(循環依賴),注入後這個純函式也才單獨可測。
    """
    _keys = [_row[0] for _row in _ZS_INDICATORS]
    _n_anchor = sum(
        1 for _k in _keys
        if _k in _EDU_ANCHOR_PILOT
        and str((_MACRO_EDU.get(_k) or {}).get("historical_anchor") or "").strip()
    )
    _n_line = sum(1 for _k in _keys if spec_key_of(f"zs_{_k}"))
    return _n_anchor, _n_line


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
    # lazy 避循環。`_zs_danger_spec_key` 是「卡片小圖畫不畫得出警戒線」的**唯一**
    # 判定規則(見該函式 docstring:刻意不建別名表),覆蓋率揭露直接用它,不另寫一份。
    from ui.tab1_macro import (
        _render_macro_indicator_card,
        _zs_danger_spec_key,
    )

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
        # 覆蓋率兩個數字皆導出(§3.3):pilot 擴充 / registry 補 spec 後會自己跟著動。
        _n_anchor, _n_line = _decoration_coverage(_zs_danger_spec_key)
        st.caption(
            "📖 已依 |Z| 由大至小排序，最異常的指標置頂。⭐ = v16.1 高頻替代源。"
            "卡片左下第二行 = 該指標在服務層的分類（並非每一張都屬 3-12 月中期循環）。"
            "📊 = 歷史錨點，給這個數字一把比例尺。"
            f"｜**目前覆蓋率**：{_n_zs} 張裡有 {_n_anchor} 張帶歷史錨點、"
            f"{_n_line} 張的小圖畫得出警戒線，且**兩批不是同一批**；其餘尚未鋪到，"
            "不是資料壞掉。卡片依 |Z| 排序，所以有裝飾的那幾張每次載入位置都不同。")
        import pandas as _pd_zs
        _zs_rows = []
        for _zk, _zname, _zunit, _zdec, _zhigh_bad, _z_pos_phrase, _z_neg_phrase in _ZS_INDICATORS:
            _zd = ind.get(_zk) or {}
            _zv = _zd.get("value")
            _zs_raw = _zd.get("series")
            # 標題吃服務層 name(代理 / 升級來源時卡片才不會沿用舊標籤)— §1 必修 1
            _ztitle = _card_title(_zname, _zd)
            # 分類標記吃服務層 type;歷史錨點吃 MACRO_EDU(pilot 3 張,核准後再全鋪)
            _zlabel = _card_label(_zd)
            _zedu = _MACRO_EDU.get(_zk) if _zk in _EDU_ANCHOR_PILOT else None
            # 預設行：資料不足時佔位（不參與 |Z| 排序，會 sink 到表尾）
            if _zv is None:
                _zs_rows.append({
                    "_abs": -1, "_key": _zk, "指標": _ztitle, "當前值": "—",
                    "白話判讀": "⬜ 資料不足，待補",
                    "_note": _card_note("⬜ 資料不足，待補", _zd, _zedu),
                    "_label": _zlabel,
                    "_color": TRAFFIC_NEUTRAL, "_trend": [], "_signal": "⬜ 無資料",
                })
                continue
            try:
                _zv_f = float(_zv)
            except (TypeError, ValueError):
                _zs_rows.append({
                    "_abs": -1, "_key": _zk, "指標": _ztitle, "當前值": str(_zv)[:10],
                    "白話判讀": "⬜ 數值格式異常",
                    "_note": _card_note("⬜ 數值格式異常", _zd, _zedu),
                    "_label": _zlabel,
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
            # 單位吃服務層(§3.3 SSOT / §4.1 量綱);spec 欄僅為服務層沒給 unit 時的 fallback
            _zunit_ssot = _card_unit(_zunit, _zd)
            _unit_s = f" {_zunit_ssot}" if _zunit_ssot else ""
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
                "白話判讀": _verdict, "_note": _card_note(_verdict, _zd, _zedu),
                "_label": _zlabel,
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
                            value_str=_r["當前值"], note=_r["_note"], label=_r["_label"],
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
    # v19.137: 物理重排後本區在 War Room 之前執行,薩姆 / 廣度兩個值
    #          需在此自行從 ind 取(不依賴下方 ⚠️ 拐點桶 War Room 定義)
    # ══════════════════════════════════════════════════
    if show_l3:
        _pmi_v = float((ind.get("PMI") or {}).get("value") or 0)
        _sahm_v = float((ind.get("SAHM") or {}).get("value") or 0)
        # §4.1 量綱 / §1 假訊號:ADL 的 `value` 是 RSP÷SPY **比值**(恆為正,量級 ~0.29),
        # `prev` 才是服務層算好的**月變動百分比**。原本讀 value 去比下方的負數門檻,
        # 條件恆假 → Situation B 這張警報卡自建立起從未觸發過一次。
        # 缺值取 None(不 `or 0`):沒資料就不判,不拿捏造的 0 去撞門檻。
        _adl_mom_pct = _safe_num((ind.get("ADL") or {}).get("prev"))
        _l3_sit_cards = []
        if _pmi_v > 0 and _pmi_v < _PMI_SITUATION_BELOW and _sahm_v < 0.5:
            _l3_sit_cards.append({
                "icon": "🟡", "border": MATERIAL_ORANGE, "bg": BG_DARK_AMBER_2,
                "title": "【Situation A — 庫存調整，非衰退】",
                "body": (f"PMI={_pmi_v:.1f}（<{_PMI_SITUATION_BELOW:.0f} 收縮）但薩姆規則={_sahm_v:.2f}（<0.5 安全線）。"
                         f"製造業庫存去化壓力，消費端仍撐盤，非系統性衰退訊號。"
                         f"策略：維持衛星資產比重，等待 PMI 觸底回升確認後加碼。"),
            })
        if _adl_mom_pct is not None and _adl_mom_pct < -2:
            _l3_sit_cards.append({
                "icon": "🔴", "border": MATERIAL_RED, "bg": BG_DARK_RED_2,
                "title": "【Situation B — 極端乖離警報】",
                "body": (f"RSP/SPY 市場廣度月變動={_adl_mom_pct:.2f}%（< -2% 危險線）。"
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
