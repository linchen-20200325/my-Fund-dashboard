"""test_ai_prompts.py — services/ai_prompts.py 5 個 builder smoke 測試（v18.112 AI-2）

純函式測試：每個 builder 應回傳含關鍵 section header 與必要欄位的 prompt 字串。
"""
from __future__ import annotations

from services.ai_prompts import (
    build_allocation_diagnosis_prompt,
    build_beginner_guide_prompt,
    build_event_impact_prompt,
    build_fund_json_prompt,
    build_global_prompt,
    build_macro_structured_prompt,
    build_mk_advisor_prompt,
    build_news_driven_prompt,
    build_trend_action_prompt,
)


# ════════════════════════════════════════════════════════════
# build_global_prompt
# ════════════════════════════════════════════════════════════
def test_build_global_prompt_has_4_sections() -> None:
    out = build_global_prompt(
        snapshot="[snapshot block]",
        phase="擴張中段",
        alloc_str="股票60% / 債券30% / 現金10%",
        core_target_pct=80,
    )
    assert "[snapshot block]" in out
    assert "擴張中段" in out
    assert "股票60% / 債券30% / 現金10%" in out
    # 4 節皆出現
    for header in ("### 📍 一、", "### ⚖️ 二、", "### 🔴 三、", "### 🔄 四、"):
        assert header in out
    # core/satellite 算式正確
    assert "核心80%" in out
    assert "衛星20%" in out
    # checkbox 規範
    assert "- [ ]" in out


# ════════════════════════════════════════════════════════════
# build_fund_json_prompt
# ════════════════════════════════════════════════════════════
def test_build_fund_json_prompt_eating_warning() -> None:
    """eating=True 時應顯示「🔴 吃本金警報」段，且引用 adr / tr1y 數字。"""
    out = build_fund_json_prompt(
        fund_name="JFZN3", category="高配息債券", currency="USD",
        nav=75.33, pos="中位", sigma_alert="",
        buy1=72.5, buy2=70.0, sell1=78.0,
        adr=5.0, tr1y=3.5, std="12", sharpe="0.45",
        sharpe_comment="普通", maxdd="-15", mgmt_fee="1.2%", pf={"1Y": 3.5},
        phase="衰退", score=4, alloc_s="債70%", phase_rec="長天期美債",
        eating=True, tone_directive="[L3 老手沙盤]",
    )
    assert "🔴 **吃本金警報**" in out
    assert "5.0" in out  # adr
    assert "3.5" in out  # tr1y
    assert "JFZN3" in out
    assert "[L3 老手沙盤]" in out
    # v18.135 改為 5 節（新增「持股 × 新聞影響評估」）
    for h in ("### 🌡️ 一、", "### 🩺 二、", "### 📍 三、", "### 💎 四、", "### 🔄 五、"):
        assert h in out


def test_build_fund_json_prompt_no_eating_safe_msg() -> None:
    """eating=False → 顯示「✅ 配息安全」分支。"""
    out = build_fund_json_prompt(
        fund_name="ACDD", category="均衡型", currency="USD",
        nav=12.0, pos="低位", sigma_alert="",
        buy1=11.0, buy2=10.5, sell1=14.0,
        adr=2.0, tr1y=8.0, std="8", sharpe="0.8",
        sharpe_comment="優秀", maxdd="-10", mgmt_fee="0.5%", pf={},
        phase="復甦", score=7, alloc_s="股60%", phase_rec="市值型 ETF",
        eating=False, tone_directive="",
    )
    assert "✅ 配息安全" in out
    assert "🔴 **吃本金警報**" not in out


# ════════════════════════════════════════════════════════════
# build_mk_advisor_prompt
# ════════════════════════════════════════════════════════════
def test_build_mk_advisor_prompt_requires_phase4_3b_citation() -> None:
    """v18.110 要求：prompt 必須包含 Phase 4 driver 排名 + Phase 3-B 燈號回測段，
    並在第二/三/四節要求 AI 引用。"""
    out = build_mk_advisor_prompt(
        phase="擴張中段", score=7, alloc_str="股60%",
        ind_str="  - VIX: 18",
        driver_str="  🥇 SLOOS (corr=-0.62)",
        subcycle_str="  🏭 製造業: 🔴 燈後 -0.35 / 🟢 燈後 +0.21",
        news_str="  📰 sample news", n_sys=1, n_gen=2,
        pf_snap="- JFZN3 投入 NT$100,000", loaded_count=1, tot_inv_twd=100000,
    )
    # 兩段新增 section 都在
    assert "領先指標排名" in out
    assert "子領域燈號歷史回測" in out
    # caller 提供的格式化資料原樣穿透
    assert "SLOOS" in out
    assert "🏭 製造業" in out
    # 4 節
    for h in ("### 🚨 一、", "### 🔄 二、", "### ⚖️ 三、", "### 🎯 四、"):
        assert h in out
    # 第二節必須要求引用 driver
    assert "必須引用上方「領先指標排名」" in out
    # 第三節必須要求引用燈號回測
    assert "子領域燈號歷史回測" in out
    # 第四節結尾必須引用 (1)新聞 + (2)driver + (3)燈號回測
    assert "(1) 1-2 條上方新聞" in out
    assert "(2) Phase 4 領先 driver" in out
    assert "(3) Phase 3-B 至少一個子領域" in out


# ════════════════════════════════════════════════════════════
# build_event_impact_prompt
# ════════════════════════════════════════════════════════════
def test_build_event_impact_prompt_joins_headlines() -> None:
    out = build_event_impact_prompt(
        fund_ctx="分析標的：JFZN3",
        headlines=["Fed 升息", "雷曼破產", "戰爭升級"],
        holdings_ctx="\n[基金持股摘要]\nApple 5%",
    )
    assert "• Fed 升息" in out
    assert "• 雷曼破產" in out
    assert "• 戰爭升級" in out
    assert "Apple 5%" in out
    assert "事件衝擊評估" in out
    assert "不超過 200 字" in out


def test_build_event_impact_prompt_no_holdings() -> None:
    out = build_event_impact_prompt(
        fund_ctx="分析所有持倉基金",
        headlines=["Single headline"],
        holdings_ctx="",
    )
    assert "• Single headline" in out


# ════════════════════════════════════════════════════════════
# build_macro_structured_prompt
# ════════════════════════════════════════════════════════════
def test_build_macro_structured_prompt_has_7_sections() -> None:
    out = build_macro_structured_prompt(
        snapshot="[macro snapshot]", stale_note="",
    )
    assert "[macro snapshot]" in out
    # v18.120: 7 節（多了第六節「跨領域綜合判讀」）
    for h in ("### 📍 一、", "### ⚖️ 二、", "### 🔴 三、",
              "### 🟢 四、", "### 📐 五、", "### 🌐 六、", "### 🔄 七、"):
        assert h in out
    assert "- [ ]" in out   # checkbox 在第七節
    # 綜合判讀第六節必須要求引用所有來源
    assert "跨領域綜合判讀" in out
    assert "7 子領域當下燈號" in out
    assert "Phase 4 領先指標排名" in out
    assert "Phase 3-B 子領域燈號歷史回測" in out


def test_build_macro_structured_prompt_stale_note_appended() -> None:
    out = build_macro_structured_prompt(
        snapshot="[snap]",
        stale_note="\n⚠️ 資料新鮮度警告 PMI:42d",
    )
    assert "⚠️ 資料新鮮度警告 PMI:42d" in out


# ════════════════════════════════════════════════════════════
# v18.159 新增 4 視角 builder smoke 測試
# ════════════════════════════════════════════════════════════
def test_build_trend_action_prompt_has_3_sections():
    out = build_trend_action_prompt(
        tab_label="總經位階", snapshot="- VIX: 18.5\n- PMI: 50.2",
    )
    assert "### 📈 一、近期趨勢解讀" in out
    assert "### ⚠️ 二、風險警示" in out
    assert "### 🎯 三、行動建議" in out
    assert "總經位階" in out
    assert "VIX: 18.5" in out


def test_build_allocation_diagnosis_prompt_has_4_sections():
    out = build_allocation_diagnosis_prompt(
        tab_label="組合戰情室", snapshot="- 核心 8 檔 / 衛星 2 檔",
    )
    assert "### ⚖️ 一、核心衛星比例診斷" in out
    assert "### 🌐 二、地理 / 產業集中度" in out
    assert "### 💰 三、現金水位與彈性" in out
    assert "### 🔄 四、再平衡操作清單" in out
    assert "80/20" in out   # MK 建議錨點


def test_build_beginner_guide_prompt_bans_jargon():
    out = build_beginner_guide_prompt(
        tab_label="單一基金", snapshot="- Sharpe: 1.2",
    )
    assert "### 🧒 一、這頁在告訴我什麼" in out
    assert "### 📖 二、KPI 逐項白話文翻譯" in out
    assert "禁止使用 Z-Score" in out   # 風格守則保留
    assert "天氣" in out   # 比喻提示


def test_build_news_driven_prompt_joins_headlines():
    out = build_news_driven_prompt(
        tab_label="總經位階", snapshot="- VIX: 28",
        headlines=["Fed 鷹派發言", "中東情勢升溫", "AI 題材續熱"],
    )
    assert "Fed 鷹派發言" in out
    assert "中東情勢升溫" in out
    assert "### 📰 一、新聞重點摘要" in out
    assert "### 🔗 二、新聞 × 持有資產的交叉影響" in out


def test_build_news_driven_prompt_no_headlines_shows_placeholder():
    out = build_news_driven_prompt(
        tab_label="總經位階", snapshot="- VIX: 18", headlines=[],
    )
    assert "（無新聞快照）" in out
