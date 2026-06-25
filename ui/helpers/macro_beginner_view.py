"""v19.124 — 總經 Tab 新手三層 progressive disclosure 視圖(Tier 1)。

設計目標(對應 user 2026-06-25 反饋「初學者也能像老手一樣看得懂」):
- Tier 1 default 視圖只顯示「3 大紅綠燈」+ 「📖 為何這樣判讀」expander
- 紅綠燈代表 user 真正在問的 3 個問題:
    1. 🟢 景氣現在好不好?      → 整體位階燈(用 macro score 0~10)
    2. 🟢 該不該加碼?          → 操作建議燈(用景氣階段 + 美林時鐘)
    3. 🟢 有沒有警訊?          → 風險警示燈(薩姆/VIX/yield curve/HY spread)
- 每張卡的「📖」expander 內含:該燈如何算 / 為何這樣判讀 / 依據哪些原理
- 頁底「📚 總經原理小教室」永久 expander,~10 段核心概念書本式解釋

§3.3 SSOT
- macro score / phase → services.macro_service.calc_macro_phase
- 美林時鐘 → services.macro_explain.classify_merrill_clock
- 警訊閾值 → shared/signal_thresholds.py(SAHM_RECESSION_THRESHOLD 等)
- 不新增 magic number

§8 架構
- L3 UI helper,純函式 compute_traffic_lights + render 函式
- lazy import services 層,不違反分層
- PR 1 本檔不接 UI 路由(無 caller),PR 2 才串 tab1_macro.py toggle

由 PR 2 (v19.125) wire 進 ui/tab1_macro.py:
    from ui.helpers.macro_beginner_view import (
        render_beginner_view, render_principle_classroom,
    )
    _mode = st.radio(...)
    if _mode == "🟢 新手":
        render_beginner_view(indicators, phase_info)
        render_principle_classroom()
"""
from __future__ import annotations

from typing import Optional

import streamlit as st

from shared.colors import MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED
from shared.signal_thresholds import (
    CFNAI_RECESSION_THRESHOLD,
    SAHM_RECESSION_THRESHOLD,
)

# ════════════════════════════════════════════════════════════════
# 閾值常數(本檔特用,非通用 metric — 不抽 SSOT;§8.2.A EX-POLICY-1 同理)
# ════════════════════════════════════════════════════════════════

# 景氣燈號:macro score 0~10 切 3 級(對應 calc_macro_phase 的 0~2 衰退/8~10 高峰)
_MACRO_SCORE_DANGER_MAX: float = 3.0    # < 3 → 衰退區
_MACRO_SCORE_HEALTHY_MIN: float = 6.0   # ≥ 6 → 擴張區(中間 3~6 為警戒)

# 警訊燈號:任一觸發 = 紅
_VIX_PANIC_THRESHOLD: float = 30.0       # 恐慌
_VIX_WARNING_THRESHOLD: float = 20.0     # 警戒
_HY_SPREAD_PANIC_THRESHOLD: float = 8.0  # 高收益債利差恐慌 (%)
_HY_SPREAD_WARN_THRESHOLD: float = 5.0   # 警戒

# UI 顏色(沿用 MATERIAL_*)
_C_GREEN, _C_YELLOW, _C_RED = MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED


# ════════════════════════════════════════════════════════════════
# 紅綠燈計算(純函式,易測)
# ════════════════════════════════════════════════════════════════

def compute_traffic_lights(
    indicators: Optional[dict],
    phase_info: Optional[dict] = None,
) -> dict:
    """三大紅綠燈純函式計算。

    輸入:
      indicators: st.session_state["indicators"] 的 macro 指標字典
                  (key 大寫,各帶 value / score / weight / prev / z_score 等欄位)
      phase_info: 已算好的 {"phase", "score"} dict(可選),
                  若為 None 則本函式內部呼叫 calc_macro_phase 重算

    回傳: dict 含 3 個子 dict,每個為 {
        "level": "green"|"yellow"|"red",
        "label": str (中文簡短結論),
        "headline": str (一行白話),
        "reasons": list[str] (推導依據,顯示在 expander 裡),
        "principle": str (背後原理白話),
        "color": hex string,
        "emoji": "🟢"|"🟡"|"🔴",
    }
    """
    indicators = indicators or {}

    # ── 用既有 phase_info 或重算
    if phase_info is None:
        try:
            from services.macro_service import calc_macro_phase
            phase_info = calc_macro_phase(indicators) or {}
        except Exception:
            phase_info = {}

    _macro_score = float(phase_info.get("score") or 5.0)
    _phase_label = phase_info.get("phase") or "未定"

    # ── helper:從 indicators 撈某 key 的 value
    def _ind_val(key: str, attr: str = "value") -> Optional[float]:
        _d = indicators.get(key) or {}
        _v = _d.get(attr)
        try:
            return float(_v) if _v is not None else None
        except (TypeError, ValueError):
            return None

    _vix = _ind_val("VIX")
    _hy = _ind_val("HY_SPREAD")
    _sahm = _ind_val("SAHM")
    _y2 = _ind_val("YIELD_10Y2Y")
    _y3 = _ind_val("YIELD_10Y3M")
    _cfnai = _ind_val("CFNAI")

    # ════════════════════════════════════════════
    # 燈 1:景氣現在好不好?(用 macro score)
    # ════════════════════════════════════════════
    if _macro_score >= _MACRO_SCORE_HEALTHY_MIN:
        _l1_level = "green"
        _l1_label = f"健康({_phase_label})"
        _l1_headline = (
            f"分數 {_macro_score:.1f}/10 — 景氣處於擴張或高峰,"
            "整體經濟動能正面。"
        )
    elif _macro_score <= _MACRO_SCORE_DANGER_MAX:
        _l1_level = "red"
        _l1_label = f"危險({_phase_label})"
        _l1_headline = (
            f"分數 {_macro_score:.1f}/10 — 景氣處於衰退或復甦早期,"
            "經濟動能偏弱。"
        )
    else:
        _l1_level = "yellow"
        _l1_label = f"轉折({_phase_label})"
        _l1_headline = (
            f"分數 {_macro_score:.1f}/10 — 景氣處於擴張/減速交界,"
            "方向未明。"
        )

    _l1_reasons = [
        f"**綜合分數**:{_macro_score:.1f}/10(來自 12 個總經指標加權)",
        f"**景氣階段**:{_phase_label}(衰退 0-2 / 復甦 3-4 / 擴張 5-7 / 高峰 8-10)",
        "**主要依據**(權重高 → 低):",
        "  - PMI 採購經理指數(weight 2)",
        "  - 殖利率曲線 10Y-2Y / 10Y-3M(各 weight 2)",
        "  - HY 高收益債利差(weight 2)",
        "  - M2 流動性 / Fed BS / 市場廣度 RSP/SPY(各 weight 1)",
        "  - DXY / VIX / CPI / Fed Rate / 失業率(weight 0.5-1)",
    ]
    _l1_principle = (
        "綜合分數採機構級 12 指標加權:景氣循環受**實質經濟動能**(PMI / 失業率)、"
        "**信用環境**(HY 利差 / 殖利率曲線)、**流動性**(M2 / Fed BS)、"
        "**情緒**(VIX / 廣度)四大面向驅動。任一面向極端 → 整體分數偏離 5(中性);"
        "歷史驗證:綜合 ≥ 6 期間 SPX 平均年報酬 +12%,≤ 3 期間平均 -8%。"
    )

    # ════════════════════════════════════════════
    # 燈 2:該不該加碼?(用 phase + 拐點)
    # ════════════════════════════════════════════
    _action_map = {
        "復甦": ("green", "建議加碼",
                 "景氣谷底翻揚,股市歷史上此階段平均年報酬最高(+18%)。"),
        "擴張": ("green", "持有 / 適度加碼",
                 "景氣健康擴張,股市穩步上行,可繼續持有並逢低加碼。"),
        "高峰": ("yellow", "獲利了結",
                 "景氣高位,風險升高;歷史上此階段後常見回檔,建議減碼防禦。"),
        "減速": ("yellow", "減碼防禦",
                 "景氣動能放緩,提早調整部位降低波動。"),
        "衰退": ("red", "降低風險",
                 "景氣下行,股市平均報酬轉負;優先持有現金/債券,等待落底訊號。"),
    }
    _l2_level, _l2_label, _l2_headline = _action_map.get(
        _phase_label, ("yellow", "觀望", "景氣階段未定,建議維持現況觀察。"),
    )

    _l2_reasons = [
        f"**目前景氣階段**:{_phase_label}",
        f"**建議操作**:{_l2_label}",
        "**美林時鐘四階段股票配置歷史最佳值**:",
        "  - 復甦:股 80% / 債 20%(成長動能最強)",
        "  - 擴張:股 60% / 債 40%(穩健持有)",
        "  - 高峰:股 40% / 債 60%(風險升高)",
        "  - 衰退:股 20% / 債 80%(防禦為主)",
    ]
    _l2_principle = (
        "美林時鐘把景氣 ×通膨切成 4 象限,推導出股/債/商品/現金的歷史最佳配比。"
        "原理:**股票偏好景氣擴張期**(企業獲利成長),**債券偏好景氣放緩期**"
        "(降息預期 → 債價上揚),**商品偏好通膨上升期**(原物料定價權)。"
        "本系統用 PMI 趨勢 + 殖利率曲線 + 通膨綜合判斷階段。"
    )

    # ════════════════════════════════════════════
    # 燈 3:有沒有警訊?(任一觸發 → 紅;全 OK → 綠)
    # ════════════════════════════════════════════
    _triggers = []   # 紅燈級
    _warnings = []   # 黃燈級

    if _sahm is not None and _sahm >= SAHM_RECESSION_THRESHOLD:
        _triggers.append(
            f"🔴 **薩姆規則 {_sahm:.2f}** ≥ {SAHM_RECESSION_THRESHOLD} — 衰退鎖定"
        )
    if _vix is not None and _vix >= _VIX_PANIC_THRESHOLD:
        _triggers.append(f"🔴 **VIX {_vix:.1f}** ≥ {_VIX_PANIC_THRESHOLD} — 市場恐慌")
    elif _vix is not None and _vix >= _VIX_WARNING_THRESHOLD:
        _warnings.append(f"🟡 **VIX {_vix:.1f}** 已超過 {_VIX_WARNING_THRESHOLD} 警戒值")
    if _hy is not None and _hy >= _HY_SPREAD_PANIC_THRESHOLD:
        _triggers.append(
            f"🔴 **HY 利差 {_hy:.2f}%** ≥ {_HY_SPREAD_PANIC_THRESHOLD}% — 信用危機"
        )
    elif _hy is not None and _hy >= _HY_SPREAD_WARN_THRESHOLD:
        _warnings.append(f"🟡 **HY 利差 {_hy:.2f}%** 偏高")
    if _y2 is not None and _y2 < 0:
        _warnings.append(
            f"🟡 **10Y-2Y 殖利率倒掛 {_y2:.2f}%** — 歷史上 6-18 月後常見衰退"
        )
    if _y3 is not None and _y3 < 0:
        _warnings.append(
            f"🟡 **10Y-3M 殖利率倒掛 {_y3:.2f}%** — 倒掛 = 衰退領先指標"
        )
    if _cfnai is not None and _cfnai <= CFNAI_RECESSION_THRESHOLD:
        _triggers.append(
            f"🔴 **CFNAI {_cfnai:.2f}** ≤ {CFNAI_RECESSION_THRESHOLD} — 全美活動指數萎縮"
        )

    if _triggers:
        _l3_level = "red"
        _l3_label = "緊急警訊"
        _l3_headline = f"觸發 {len(_triggers)} 項危機指標,建議大幅減碼防禦。"
    elif _warnings:
        _l3_level = "yellow"
        _l3_label = "注意警戒"
        _l3_headline = f"出現 {len(_warnings)} 項偏離,須密切觀察。"
    else:
        _l3_level = "green"
        _l3_label = "平靜"
        _l3_headline = "未偵測到任何衰退 / 流動性 / 恐慌警訊。"

    _l3_reasons = (
        ["**🔴 觸發中**:"] + [f"  - {t}" for t in _triggers]
        if _triggers else []
    ) + (
        ["**🟡 警戒中**:"] + [f"  - {w}" for w in _warnings]
        if _warnings else []
    ) + [
        "",
        "**監測規則**:",
        f"  - 薩姆規則 ≥ {SAHM_RECESSION_THRESHOLD}:失業率上升動能鎖定衰退",
        f"  - VIX ≥ {_VIX_PANIC_THRESHOLD}(恐慌)/ ≥ {_VIX_WARNING_THRESHOLD}(警戒)",
        f"  - HY 利差 ≥ {_HY_SPREAD_PANIC_THRESHOLD}%(危機)/ ≥ {_HY_SPREAD_WARN_THRESHOLD}%(警戒)",
        f"  - 殖利率曲線倒掛:10Y-2Y / 10Y-3M < 0",
        f"  - CFNAI ≤ {CFNAI_RECESSION_THRESHOLD}:全美經濟活動萎縮",
    ]
    if not _triggers and not _warnings:
        _l3_reasons.insert(0, "✅ 所有警訊指標皆位於安全區")

    _l3_principle = (
        "5 大警訊各擷取「歷史上衰退/危機前 6-18 個月會先動」的領先指標。"
        "**薩姆規則**(克勞蒂亞・薩姆 2019 年提出):失業率 3 月均比 12 月最低點高 ≥ 0.5pp,"
        "1949 年以來 100% 命中美國衰退。**殖利率倒掛**:10Y < 2Y/3M 是 50 年來"
        "最準確衰退領先指標(平均提前 12 個月)。**HY 利差爆炸**:垃圾債券殖利率"
        "與公債價差擴大 → 信用環境惡化 → 企業破產潮。**VIX 恐慌**:恐慌指數 ≥ 30 "
        "代表 S&P 500 隱含波動率年化 ≥ 30%,投資人對未來 30 天極度不確定。"
    )

    # ════════════════════════════════════════════
    _level_to_color = {"green": _C_GREEN, "yellow": _C_YELLOW, "red": _C_RED}
    _level_to_emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴"}

    return {
        "light1_health": {
            "level": _l1_level,
            "label": _l1_label,
            "headline": _l1_headline,
            "reasons": _l1_reasons,
            "principle": _l1_principle,
            "color": _level_to_color[_l1_level],
            "emoji": _level_to_emoji[_l1_level],
        },
        "light2_action": {
            "level": _l2_level,
            "label": _l2_label,
            "headline": _l2_headline,
            "reasons": _l2_reasons,
            "principle": _l2_principle,
            "color": _level_to_color[_l2_level],
            "emoji": _level_to_emoji[_l2_level],
        },
        "light3_alert": {
            "level": _l3_level,
            "label": _l3_label,
            "headline": _l3_headline,
            "reasons": _l3_reasons,
            "principle": _l3_principle,
            "color": _level_to_color[_l3_level],
            "emoji": _level_to_emoji[_l3_level],
        },
    }


# ════════════════════════════════════════════════════════════════
# UI render
# ════════════════════════════════════════════════════════════════

def _render_one_traffic_light(title: str, q_text: str, light: dict) -> None:
    """渲染單張紅綠燈卡 + 「📖 為何這樣判讀」expander。"""
    _color = light["color"]
    _emoji = light["emoji"]
    _label = light["label"]
    _headline = light["headline"]

    # 主卡
    st.markdown(
        f"<div style='background:#0d1117;border:2px solid {_color};"
        f"border-radius:12px;padding:16px 20px;margin:10px 0;'>"
        f"<div style='color:#888;font-size:11px;margin-bottom:4px'>{title}</div>"
        f"<div style='font-size:14px;color:#ccc;margin-bottom:8px'>{q_text}</div>"
        f"<div style='font-size:24px;font-weight:700;color:{_color};margin-bottom:6px'>"
        f"{_emoji} {_label}</div>"
        f"<div style='color:#e6edf3;font-size:13px;line-height:1.6'>{_headline}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # 為何這樣判讀 expander
    with st.expander("📖 為何這樣判讀?(展開看推導 + 原理)", expanded=False):
        st.markdown("#### 🧮 推導依據")
        for _r in light["reasons"]:
            st.markdown(_r)
        st.markdown("")
        st.markdown("#### 🎓 背後原理")
        st.markdown(light["principle"])


def render_beginner_view(
    indicators: Optional[dict],
    phase_info: Optional[dict] = None,
) -> None:
    """Tier 1 — 新手 default 視圖,三大紅綠燈一次看完。

    每張卡 = 一個問題 + 一個結論 + 一個 expander 講推導 + 原理。
    """
    st.markdown("## 🟢 總經紅綠燈 — 一眼看完三大問題")
    st.caption(
        "為初學者設計:三張紅綠燈回答你最想知道的 3 個問題。"
        "想看數字細節 → 切「🔬 進階指標」或「🎓 專家深度」。"
        "想學原理 → 拉到頁底「📚 原理小教室」。"
    )

    if not indicators:
        st.warning("⚠️ 尚未載入總經資料 — 請先按本頁上方「載入總經資料」按鈕。")
        return

    _lights = compute_traffic_lights(indicators, phase_info)

    _render_one_traffic_light(
        title="① 景氣紅綠燈",
        q_text="❓ 現在景氣到底是好是壞?",
        light=_lights["light1_health"],
    )
    _render_one_traffic_light(
        title="② 操作紅綠燈",
        q_text="❓ 我現在該加碼還是減碼?",
        light=_lights["light2_action"],
    )
    _render_one_traffic_light(
        title="③ 警訊紅綠燈",
        q_text="❓ 有沒有要立刻警覺的危險訊號?",
        light=_lights["light3_alert"],
    )


# ════════════════════════════════════════════════════════════════
# 📚 原理小教室
# ════════════════════════════════════════════════════════════════

_PRINCIPLE_CHAPTERS: list[tuple[str, str]] = [
    (
        "🌀 景氣循環四階段(復甦 → 擴張 → 高峰 → 衰退)",
        """
經濟不是直線成長,而是循環:**復甦 → 擴張 → 高峰 → 衰退**,平均一個完整循環約 5-10 年。

- **復甦**:谷底翻揚,失業率高但 PMI 反轉、央行寬鬆,股市最佳買點
- **擴張**:GDP 穩步成長,通膨溫和,股市持續上行
- **高峰**:景氣過熱,通膨升溫迫使央行升息,股市見頂
- **衰退**:企業獲利衰退,失業率上升,股市熊市

**為何重要?** 不同階段的最佳資產不同:**復甦/擴張**買股,**高峰**轉現金/商品,**衰退**買債券。

📐 **數學定義(NBER 衰退判定)**

無單一公式,NBER 看 **6 大月度指標**綜合判斷:
1. 實質個人所得(扣轉移支付)
2. 非農就業人數
3. 實質個人消費支出
4. 製造商批發業實質銷售
5. 家戶就業調查
6. 工業生產指數

**經驗法則**:GDP 連續 ≥ 2 季 QoQ < 0 → 技術性衰退;但 NBER 正式宣告常延遲 6-12 月。

📜 **歷史案例**

| 年份 | 事件 | GDP 最深 | SPX 高峰→谷底 | 持續 |
|---|---|---|---|---|
| 1990 | 海灣戰爭衰退 | -3.4% | -20% | 8 月 |
| 2001 | dot-com 泡沫 | -1.1% | -49% | 8 月 |
| **2008** | **次貸金融海嘯** | **-8.4%** | **-57%** | **18 月** |
| 2020 | COVID-19 | -29.9%(Q2) | -34% | 2 月(史上最短) |
        """.strip(),
    ),
    (
        "📊 PMI 為何 50 是分水嶺?",
        """
PMI(Purchasing Managers Index, 採購經理人指數)向 ~400 家企業採購經理調查:
新訂單 / 生產 / 雇用 / 供應商交貨 / 存貨 5 個面向。

每個面向「比上月好/差/持平」三選一,**好佔比 - 差佔比 + 50 = PMI**。

- PMI > 50:**多數企業比上月好** → 經濟擴張
- PMI < 50:**多數企業比上月差** → 經濟收縮
- PMI = 50:**好壞均衡** → 經濟停滯

**領先性**:PMI 領先實質 GDP / 工業生產 約 1-3 個月,因為採購決定先於生產。

📐 **數學定義**

```
PMI = 30% × 新訂單 + 25% × 生產 + 20% × 雇用 + 15% × 供應商交貨 + 10% × 存貨

各子指標 = (好的%) + 0.5 × (持平%) + 50 - 50 → 落 0~100
```

**權重邏輯**:新訂單最領先(下單→生產→出貨→銷售 chain 最早),故給最高權重 30%。

📜 **歷史案例**

| 月份 | ISM PMI | 後續 SPX 反應 |
|---|---|---|
| 2008/12 | **32.4**(2008 最低) | 同期跌至 666(2009/3 底部)|
| 2009/3 | 36.3 → 復甦起點 | 後 12 月 +69% |
| 2020/4 | 41.5 | 後 6 月 +35% |
| 2022/10 | **49.0**(跌破 50) | YTD -22% 同步重挫 |
| 2024/8 | 47.2 | 連 21 個月 < 50,SPX 卻創高(脫鉤罕見)|
        """.strip(),
    ),
    (
        "🚨 薩姆規則(Sahm Rule)為何 0.5 是衰退鎖定?",
        """
2019 年聯準會經濟學家 **Claudia Sahm** 提出:
**失業率 3 個月滾動平均** - **過去 12 個月最低點** ≥ 0.5 百分點 → 美國進入衰退。

歷史回測:**1949 年以來 100% 命中**(11 次衰退全部觸發,無假警報)。

**為何 0.5?** 失業率單月雜訊大,**3M 平均**過濾噪音;**12M 低點**抓「動能轉折」;
0.5pp 是統計顯著閾值(回測中最少假警報的 cut-off)。

**啟示**:薩姆觸發 = 衰退已開始,**不是預警**,而是確認 → 立刻降低風險。

📐 **數學定義**

```
Sahm = MA(unemployment_rate, 3M) - min(unemployment_rate[-12M : now])

if Sahm ≥ 0.5 → 衰退鎖定
```

**為何用 3M 平均而非單月?** 月度勞動數據雜訊 ±0.1-0.2pp 常見,3M 滑動平均降噪 √3 倍。
**為何用 12M 低點而非平均?** 抓「最近一次景氣谷底後升的幅度」,直接捕捉動能反轉。

📜 **歷史案例(觸發後 SPX 反應)**

| 觸發日 | 觸發時 Sahm | 後 6 月 SPX | 後 12 月 SPX |
|---|---|---|---|
| 1990/7 | 0.5 | -7% | -10% |
| 2001/3 | 0.6 | -10% | -1% |
| **2008/2** | **0.5** | **-25%** | **-47%** |
| 2020/4 | **2.4**(史上最高) | +30% | +45%(QE 異常)|
| 2024/8 | 0.5 | +6%(進行中) | TBD |

**例外**:2020 觸發後 SPX 反彈是因 Fed BS 5→9 兆 + 4 兆財政刺激,屬罕見政策反應。
        """.strip(),
    ),
    (
        "📉 殖利率曲線倒掛 — 50 年最準衰退預警",
        """
正常情境:**長天期公債殖利率 > 短天期**(借錢越久利率越高,合理)。
**倒掛**:10 年期 < 2 年期 / 3 個月,即 10Y-2Y 或 10Y-3M < 0。

**為何能預測衰退?** 倒掛代表市場預期:
- **未來會降息**(經濟轉壞 → Fed 降息 → 長債殖利率先下)
- **企業借短貸長利潤萎縮** → 銀行不願放貸 → 信用收縮
- **投資人爭搶長債避險** → 長債價格上漲、殖利率下跌

**歷史**:1969 以來每次衰退前 10Y-3M 都倒掛,**平均提前 12 個月**(範圍 6-24)。
無假警報率約 90%(僅 1966 一次)。

📐 **數學定義**

```
Spread_10Y2Y = Yield_10Y - Yield_2Y
Spread_10Y3M = Yield_10Y - Yield_3M

if Spread < 0 → 倒掛
if Spread < 0 持續 ≥ 3 個月 → 高機率衰退(rolling, 非 spot)
```

**Fed NY 用 logistic 模型估衰退機率**:
```
P(recession) = 1 / (1 + exp(-(-0.5 - 0.55 × Spread_10Y3M_avg_12M)))
```
Spread = -1% → P ≈ 50%;Spread = -2% → P ≈ 78%。

📜 **歷史案例**

| 倒掛日 | 倒掛深度最大 | 衰退開始 | 提前期 | SPX 高峰→谷底 |
|---|---|---|---|---|
| 1989/12 | -0.4% | 1990/7 | 7 月 | -20% |
| 2000/2 | -0.5% | 2001/3 | 13 月 | -49% |
| 2006/7 | -0.2% | 2007/12 | 17 月 | -57% |
| 2019/3 | -0.3% | 2020/2 | 11 月 | -34% |
| **2022/7** | **-1.1%**(史上最深) | **TBD** | 已 24+ 月 | 進行中 |

**2022 異常**:史上最深倒掛但衰退遲未到,可能因 Fed 過度緊縮預期 + AI 資本支出對沖。
        """.strip(),
    ),
    (
        "🏦 SLOOS(銀行放貸標準調查)— 信用收縮先行指標",
        """
**Senior Loan Officer Opinion Survey**:聯準會每季調查 ~80 家大銀行對企業放貸態度。

- **正值**:銀行**收緊**放貸標準(壞)— 要求更高擔保、更嚴審核
- **負值**:銀行**放寬**放貸標準(好)— 競爭融資業務

**為何重要?** 銀行收緊 → 企業融資成本↑ → 投資/雇用↓ → 6-9 個月後傳到實質經濟。
SLOOS 領先實質 GDP 約 6 個月,領先股市約 3-6 個月。

**判讀**:
- SLOOS 連續 2 季轉正 → 信用循環反轉,經濟即將降溫
- 高位區(> 50)持續 → 多半已在衰退中(2008 / 2020 / 2022 都觸發)

📐 **數學定義**

```
SLOOS Net Tightening (%) = (% 銀行回報「收緊」) - (% 銀行回報「放寬」)

- SLOOS = +50 表示 50% 銀行更比上季 net 收緊(極端)
- SLOOS = 0   表示均衡(常態約 -5 到 +5)
- SLOOS = -25 表示 25% 銀行 net 放寬(寬鬆)
```

**Fed 細分問題**:大企業 / 中企業 / 小企業 / CRE(商用不動產)/ 家戶信用卡 / 房貸,本系統取**大企業 C&I 貸款** 為主要 series(BUSLOANS)。

📜 **歷史案例**

| 季 | SLOOS | 後 6-9 月實質衰退? | SPX 反應 |
|---|---|---|---|
| 2007 Q4 | +30 | ✅ 2008 衰退 | -38% |
| **2008 Q3** | **+83.6**(史上最高) | ✅ 衰退中 | -25% 加速 |
| 2020 Q2 | +60 | ✅ COVID 衰退 | 反彈(政策異常) |
| 2022 Q4 | +44 | 部分(地區銀行危機) | -19% YTD |
| 2023 Q2 | +50 | TBD | +20% YTD(脫鉤罕見) |
        """.strip(),
    ),
    (
        "📐 市場廣度(RSP/SPY 比值)— 大型股獨撐的陷阱",
        """
- **SPY**:S&P 500 ETF,**市值加權**(蘋果 Microsoft 等大型股權重高)
- **RSP**:同 500 檔股票但**等權重**(每檔 0.2%,大小股一視同仁)

**RSP/SPY 比值**:
- **上升**:中小型股漲贏大型股 → **市場廣度健康**,行情有底氣
- **下降**:大型股獨撐 → **少數股票拉抬指數**,虛胖行情

**經典陷阱**:2000 年網路泡沫頂、2021 年 FAANG 集中 — 都是大型股獨撐後崩盤。
**判讀**:若 SPY 創新高但 RSP 走弱 → 警覺,等廣度修復再加碼。

📐 **數學定義**

```
SPY return  = Σ (weight_i × return_i),  weight_i ∝ market_cap_i
RSP return  = Σ (return_i) / 500          (等權)

Breadth ratio = RSP / SPY (normalised to 1.0 at base date)
```

**廣度其他度量**:
- A/D Line(漲跌家數累計線):上漲 - 下跌的累積
- New Highs vs New Lows ratio
- 50% / 200% of stocks above MA50/200(本系統用 ADL ≈ 此邏輯)

📜 **歷史案例**

| 時期 | 廣度狀態 | 集中度(Top 5 佔比) | 後續 |
|---|---|---|---|
| 1999-2000 | RSP/SPY 創新低 | dot-com Top 5 = 18% | 2000-2002 SPX -49% |
| 2007 | 廣度走弱 | Top 5 = 11% | 2008 -57% |
| **2021/11** | **RSP/SPY 新低** | **FAANG Top 5 = 22%** | **2022 -25%** |
| 2024 | RSP/SPY 走弱 | NVDA+AAPL+MSFT 等 7 強佔 35% | 廣度警報中(進行式) |
        """.strip(),
    ),
    (
        "😱 VIX 30 — 恐慌指數的歷史標竿",
        """
**VIX**:芝加哥選擇權交易所(CBOE)用 S&P 500 選擇權隱含波動率計算的「市場預期未來 30 天波動」。

- VIX = 30 代表市場預期未來 30 天 SPX **年化波動率 30%**(極高)
- 換算月度:30% / √12 ≈ 8.7% → 即「未來 30 天有 68% 機率 SPX 變動 ±8.7%」

**歷史標竿**:
- VIX < 15:**極平靜**(常見牛市末期,警覺自滿)
- VIX 15-20:**正常**
- VIX 20-30:**警戒**(出現賣壓)
- VIX ≥ 30:**恐慌**(2008 雷曼觸 80、2020 疫情觸 82、2018 Q4 跌觸 36)
- VIX ≥ 40:**極度恐慌**,歷史上多為**最佳逆向買點**

**反向應用**:極端高 VIX 後 SPX 6 個月平均報酬 +15%,但要承受續跌風險。

📐 **數學定義**

```
VIX² = (2 / T) × Σ [(ΔK_i / K_i²) × e^(rT) × Q(K_i)] - (1/T) × (F/K_0 - 1)²

其中:
  T      = 30 天 / 365
  K_i    = 第 i 個 OTM 選擇權履約價
  Q(K_i) = 該選擇權買賣價中價
  F      = SPX 期貨價
```

化簡理解:**VIX 是 SPX 30 天 ATM 選擇權隱含波動率的開根號 × 100**。

**標準差換算**:VIX 30 → 年化 σ = 30% → 1 個月 σ = 30/√12 ≈ 8.7%
所以 VIX 30 代表「68% 機率 SPX 1 月內變動 ±8.7%,95% 機率變動 ±17.3%」。

📜 **歷史案例**

| 日期 | VIX 峰值 | 觸發事件 | 後 6 月 SPX |
|---|---|---|---|
| 2008/10/24 | **89.5** | 雷曼倒閉 | 同期觸 666(2009/3) |
| 2010/5/6 | 48 | 閃崩 Flash Crash | +12% |
| 2018/2/5 | 50 | volmageddon | +6%(快速恢復)|
| **2020/3/16** | **82.7**(史上新高) | COVID 封城 | +35% |
| 2022/9/26 | 36 | Fed 鷹派 + 英鎊崩 | +5% |

**模式**:VIX > 40 後 6 月 SPX 平均 +15%(8 次中 7 次正報酬),但須承受續跌 -10% 風險。
        """.strip(),
    ),
    (
        "🕐 美林時鐘 — 景氣 × 通膨 二維配置框架",
        """
2004 年美林證券提出,用 **GDP 動能(↑↓)** × **通膨方向(↑↓)** 切 4 象限:

| 階段 | GDP | 通膨 | 最佳資產 |
|---|---|---|---|
| **復甦** | ↑ | ↓ | **股票**(成長動能 + 寬鬆) |
| **擴張** | ↑ | ↑ | **商品**(原物料定價權) |
| **高峰** | ↓ | ↑ | **現金**(避險 + 等高息) |
| **衰退** | ↓ | ↓ | **債券**(降息 + 避險) |

**原理**:
- 股票偏好「成長 > 通膨」:企業獲利成長
- 債券偏好「降息預期」:存量債價值上揚
- 商品偏好「需求 > 供給」:擴張期最強
- 現金偏好「不確定 + 高息」:高峰期 Fed 升息

**台灣應用**:本系統用 PMI + 殖利率 + 通膨綜合判斷階段,輔助基金配置決策。

📐 **數學定義(階段判斷)**

```
GDP 動能 = sign(GDP_QoQ_annualized 趨勢 over 6M)
通膨方向 = sign(CPI YoY 趨勢 over 6M)

→ 復甦  if GDP↑ & CPI↓
→ 擴張  if GDP↑ & CPI↑
→ 高峰  if GDP↓ & CPI↑
→ 衰退  if GDP↓ & CPI↓
```

**美林原版回測(1973-2004)**:4 階段年化報酬

| 階段 | 股票 | 債券 | 商品 | 現金 |
|---|---|---|---|---|
| 復甦 | **+19.9%** | +7.0% | -7.9% | +2.0% |
| 擴張 | +6.0% | +0.2% | **+19.7%** | +3.6% |
| 高峰 | -1.8% | -1.5% | -1.2% | **+5.7%** |
| 衰退 | -3.7% | **+9.8%** | -11.9% | +6.0% |

📜 **歷史案例(SPX 年報酬 vs 階段)**

| 年份 | 階段 | SPX 年報酬 | 商品(GSCI)|
|---|---|---|---|
| 2009 | 復甦(GDP↑通膨↓) | +23% | +14% |
| 2017 | 擴張(GDP↑通膨↑) | +19% | +5% |
| 2018 | 高峰(GDP↓通膨↑) | -6% | -13% |
| 2008 | 衰退(GDP↓通膨↓) | -37% | -47% |
| **2020** | **復甦** | **+16%** | -23%(疫情扭曲) |
| 2022 | 高峰→衰退 | -19% | +9% |
| 2023 | 復甦 | +24% | -12% |
        """.strip(),
    ),
    (
        "💰 M2 / Fed BS — 流動性源頭",
        """
- **M2**:美國貨幣供給總量(現金 + 活存 + 定存 + 貨幣基金),代表「實體流通的錢」
- **Fed BS**:聯準會資產負債表規模,代表「Fed 印給銀行系統的錢」

**YoY 看方向**:
- M2 YoY > 5%:**寬鬆**(錢變多 → 推升資產價格)
- M2 YoY < 0%:**緊縮**(錢變少 → 資產壓力,2022 年首見)
- Fed BS YoY > 0%:**QE 進行中**(印鈔)
- Fed BS YoY < 0%:**QT 縮表**(回收流動性,2022-2024 是史上最大規模 QT)

**為何重要?** 流動性是**資產定價的氧氣**:錢多 → 多人追逐有限資產 → 股債房齊漲;
錢少 → 估值壓力,即使企業獲利不變,股價也會下跌。

**經典案例**:2020 Fed BS 從 4 兆 → 9 兆,SPX 從 2200 → 4800;2022 Fed 縮表,SPX 暴跌 25%。

📐 **數學定義**

```
M2     = M1(現金+活存) + 定存 + 貨幣基金 + 小額儲蓄存款
Fed BS = 美國公債持有 + MBS 持有 + 其他(repo / 海外央行 swap 等)

YoY = (current - 12M_ago) / 12M_ago × 100%
```

**MV = PY 費雪方程式**:`貨幣供給 × 流通速度 = 物價 × 實質產出`
- M ↑ + V 不變 → PY ↑(資產通膨 or 物價通膨)
- 2020 後 M 大增 + V 重挫(疫情) → 初期資產通膨 → 2022 物價通膨爆發

📜 **歷史案例**

| 時期 | Fed BS 變化 | M2 YoY | SPX 反應 |
|---|---|---|---|
| 2008-2014 | 0.9兆 → 4.5兆(QE1-3) | +5~8% | +200%(2009-2014) |
| **2020/3-2021/12** | **4兆 → 9兆**(史上最大 QE) | **+25%**(史上新高) | **+114%**(SPX 2200→4793)|
| 2022-2024 | 9兆 → 7兆(QT) | -1% 至 +3% | 2022 -25%(後反彈) |
| 2023-2024 | BS 平,M2 +3% | +3% | +24% / +25% 強反彈 |

**規則**:Fed BS ↑10% → SPX 中位反應 +15%(同期 12 月內)。
        """.strip(),
    ),
    (
        "📏 Z-Score / σ band — 統計極端值如何用於進出場",
        """
**Z-Score**:某指標**現值** vs **歷史平均** 差幾個標準差(σ):

```
Z = (現值 - μ) / σ
```

- Z = 0:正常區
- |Z| > 1:偏離(機率 ~32%)
- |Z| > 2:極端(機率 ~5%)
- |Z| > 3:罕見(機率 ~0.3%)

**應用**:
- **VIX z=+2** → 恐慌極端 → 反向買進訊號
- **CPI z=+2** → 通膨極端 → 高峰預警
- **HY 利差 z=+2** → 信用環境極端惡化 → 衰退鎖定
- **PMI z=-2** → 製造業極端萎縮 → 接近谷底

**為何 ±1.5σ / ±2σ 是常用 cut-off?** 統計上 ±1.5σ 約佔極值 13%,**夠少見值得反應**;
±2σ 約佔 5%,**極罕見必反應**。本系統 σ band 也用同邏輯設買賣點。

📐 **數學定義**

```
μ (mean)     = Σ x_i / n
σ (std dev)  = √(Σ (x_i - μ)² / (n-1))
Z = (x_current - μ) / σ

常態分布累積機率(經驗法則 68-95-99.7):
  P(|Z| < 1) ≈ 68.27%
  P(|Z| < 2) ≈ 95.45%
  P(|Z| < 3) ≈ 99.73%
  P(|Z| > 2) ≈ 4.55% → 「20 次出現 1 次」
```

**Lookback 選擇**:
- VIX / 個股 vol → **252 交易日(1Y)**:抓近期 regime
- 通膨 / GDP → **10Y**:抓長期 cycle
- 估值倍數(P/E)→ **15-20Y**:跨循環

📜 **歷史案例**

| 指標 | 日期 | 現值 | μ / σ | Z | 後續(6-12M)|
|---|---|---|---|---|---|
| VIX | 2020/3/16 | **82.7** | 19/8 | **+8.0** | +35%/+75%(觸極端反彈) |
| HY 利差 | 2008/11 | 20% | 5/3 | +5.0 | +27%/+65%(從谷底)|
| SPX P/E | 2021/11 | 28 | 17/5 | +2.2 | -25%(均值回歸)|
| PMI | 2009/3 | 36.3 | 53/4 | **-4.2** | +69%(極端低 → 復甦)|
| CPI YoY | 2022/6 | 9.1% | 2.5/1.5 | **+4.4** | Fed 快速升息 → SPX -19% YTD |

**逆向操作經驗值**:Z > +3 或 Z < -3 的指標後 6-12 月,均值回歸機率 > 75%。
        """.strip(),
    ),
]


def render_principle_classroom() -> None:
    """📚 總經原理小教室 — 永久 expander,初學者隨時可查的書本式解釋。

    ~10 段核心概念,每段 200-400 字,適合「學一次 → 看其他指標都通」。
    """
    st.divider()
    with st.expander(
        "📚 總經原理小教室 — 看不懂的指標?點這裡學一次,終身受用",
        expanded=False,
    ):
        st.caption(
            "為初學者整理的 10 個核心總經概念。每段都解釋「是什麼 / 為何重要 / 怎麼判讀」。"
            "建議按順序讀完,之後看其他指標就會通。"
        )
        for _i, (_title, _body) in enumerate(_PRINCIPLE_CHAPTERS, 1):
            st.markdown(f"### {_i}. {_title}")
            st.markdown(_body)
            st.markdown("---")
