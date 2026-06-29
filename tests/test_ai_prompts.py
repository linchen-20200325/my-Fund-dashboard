"""test_ai_prompts.py — services/ai_prompts.py 5 個 builder smoke 測試（v18.112 AI-2）

純函式測試：每個 builder 應回傳含關鍵 section header 與必要欄位的 prompt 字串。
"""
from __future__ import annotations

from services.ai_prompts import (
    build_mk_advisor_prompt,
    build_structured_summary_prompt,
)


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
# v18.214 build_structured_summary_prompt — 逐章節白話結論 + 時事
# ════════════════════════════════════════════════════════════
def test_build_structured_summary_prompt_lists_sections_and_news():
    out = build_structured_summary_prompt(
        tab_label="組合戰情室",
        snapshot="- 核心 8 檔 / 衛星 2 檔",
        sections=["組合配置與健康度", "與同類比較"],
        headlines=["Fed 維持利率", "台股創高"],
    )
    assert "組合戰情室" in out
    assert "核心 8 檔 / 衛星 2 檔" in out
    # 章節清單逐項列出
    assert "組合配置與健康度" in out
    assert "與同類比較" in out
    # 新聞 headlines 帶入
    assert "Fed 維持利率" in out
    assert "台股創高" in out
    # 逐節雙塊 + 末段一句話總結
    assert "白話結論" in out
    assert "最近新聞影響" in out
    assert "一句話總結" in out
    # 白話風格守則
    assert "白話" in out


def test_build_structured_summary_prompt_no_news_placeholder():
    out = build_structured_summary_prompt(
        tab_label="單一基金", snapshot="- Sharpe: 1.2",
        sections=["風險指標"], headlines=[],
    )
    assert "這次沒有抓到相關新聞" in out
    assert "風險指標" in out


def test_build_structured_summary_prompt_empty_sections_safe():
    out = build_structured_summary_prompt(
        tab_label="X", snapshot="- a", sections=[],
    )
    assert "請依快照自行分段" in out
