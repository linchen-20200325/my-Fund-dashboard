"""test_ai_models.py — services/ai_models.py 測試（v18.114 AI-4）

涵蓋：
- parse_llm_json: tolerant parser（純 JSON / ```json fence / 含前後雜訊）
- fund_analysis_to_markdown: 4 節 dict → markdown（含 checklist 行為）
- end-to-end: schema_hint → mock LLM → parse → render（往返一致）
"""
from __future__ import annotations

from services.ai_models import (
    FUND_JSON_SCHEMA_HINT,
    fund_analysis_to_markdown,
    parse_llm_json,
)


# ════════════════════════════════════════════════════════════
# parse_llm_json
# ════════════════════════════════════════════════════════════
def test_parse_llm_json_pure_object():
    out = parse_llm_json('{"a": 1, "b": "x"}')
    assert out == {"a": 1, "b": "x"}


def test_parse_llm_json_with_fence():
    text = "```json\n{\"a\": 1}\n```"
    assert parse_llm_json(text) == {"a": 1}


def test_parse_llm_json_with_noise_before_after():
    text = "Sure, here is the JSON:\n{\"a\": 1, \"b\": 2}\nLet me know."
    assert parse_llm_json(text) == {"a": 1, "b": 2}


def test_parse_llm_json_returns_none_on_malformed():
    assert parse_llm_json("not json at all") is None
    assert parse_llm_json("") is None
    assert parse_llm_json(None) is None    # type: ignore[arg-type]


def test_parse_llm_json_rejects_array():
    """頂層是 array → 回 None（schema 要求 dict）。"""
    assert parse_llm_json("[1, 2, 3]") is None


# ════════════════════════════════════════════════════════════
# fund_analysis_to_markdown
# ════════════════════════════════════════════════════════════
def test_fund_analysis_to_markdown_4_sections():
    data = {
        "sections": [
            {"title": "🌡️ 一、景氣位階 × 基金類別建議",
             "bullets": ["當前擴張中段適合衛星", "可保留"], "is_checklist": False},
            {"title": "🩺 二、基金體質診斷",
             "bullets": ["Sharpe 0.8 優秀", "回撤 -10% 抗跌"], "is_checklist": False},
            {"title": "📍 三、量化買賣點分析",
             "bullets": ["距離買2 還有 5%"], "is_checklist": False},
            {"title": "🔄 四、本週操作待辦清單",
             "bullets": ["定期定額繼續", "本週原則：持有"], "is_checklist": True},
        ]
    }
    out = fund_analysis_to_markdown(data)
    assert out is not None
    assert "### 🌡️ 一、景氣位階 × 基金類別建議" in out
    assert "### 🔄 四、本週操作待辦清單" in out
    # 一般 bullet
    assert "- 當前擴張中段適合衛星" in out
    # checklist bullet（is_checklist=True）
    assert "- [ ] 定期定額繼續" in out
    assert "- [ ] 本週原則：持有" in out


def test_fund_analysis_to_markdown_strips_existing_bullet_prefix():
    """LLM 偷偷在 bullet 前加 -/*/✓ → renderer 應自動剝掉避免雙重項目符號。"""
    data = {
        "sections": [
            {"title": "T", "bullets": ["- 已有 dash", "* 已有 asterisk",
                                        "[ ] 已有 checkbox"], "is_checklist": False},
        ]
    }
    out = fund_analysis_to_markdown(data)
    assert "- 已有 dash" in out
    assert "- 已有 asterisk" in out
    assert "- 已有 checkbox" in out
    # 不應出現雙重項目符號
    assert "- - " not in out
    assert "- * " not in out


def test_fund_analysis_to_markdown_returns_none_on_bad_schema():
    assert fund_analysis_to_markdown(None) is None
    assert fund_analysis_to_markdown({}) is None
    assert fund_analysis_to_markdown({"sections": []}) is None
    assert fund_analysis_to_markdown({"sections": "not a list"}) is None


def test_fund_analysis_to_markdown_skips_empty_bullets():
    data = {
        "sections": [
            {"title": "T", "bullets": ["valid", "", "  ", "another"],
             "is_checklist": False},
        ]
    }
    out = fund_analysis_to_markdown(data)
    assert "- valid" in out
    assert "- another" in out
    # 不該渲染空白 bullet
    assert "- \n" not in out
    assert "-  \n" not in out


# ════════════════════════════════════════════════════════════
# Roundtrip：模擬 LLM 給 JSON → parse → render
# ════════════════════════════════════════════════════════════
def test_end_to_end_llm_output_to_markdown():
    mock_llm_output = '''```json
{
  "sections": [
    {"title": "🌡️ 一、景氣位階 × 基金類別建議", "bullets": ["bullet 1", "bullet 2"], "is_checklist": false},
    {"title": "🩺 二、基金體質診斷", "bullets": ["health 1"], "is_checklist": false},
    {"title": "📍 三、量化買賣點分析", "bullets": ["bs 1"], "is_checklist": false},
    {"title": "🔄 四、本週操作待辦清單", "bullets": ["todo 1", "原則"], "is_checklist": true}
  ]
}
```'''
    parsed = parse_llm_json(mock_llm_output)
    assert parsed is not None
    md = fund_analysis_to_markdown(parsed)
    assert md is not None
    assert md.count("### ") == 4
    assert "- [ ] todo 1" in md
    assert "- [ ] 原則" in md
    # 第三節非 checklist
    assert "- bs 1" in md
    assert "- [ ] bs 1" not in md


def test_schema_hint_contains_5_sections():
    """v18.135: schema_hint 5 個 title（新增「持股 × 新聞影響評估」）。"""
    h = FUND_JSON_SCHEMA_HINT
    assert "🌡️ 一、景氣位階 × 基金類別建議" in h
    assert "🩺 二、基金體質診斷" in h
    assert "📍 三、量化買賣點分析" in h
    assert "💎 四、持股 × 新聞影響評估" in h
    assert "🔄 五、本週操作待辦清單" in h
    assert "is_checklist" in h
