"""services/ai_models.py — AI 結構化輸出 schema 與 markdown 渲染（v18.114 AI-4）

定位：service 層的「契約模型」— 規範 LLM 輸出格式（JSON schema 描述）
     並提供 JSON → markdown 反向組裝（給既有 UI 用 st.markdown 渲染）。

設計：
- **plain dict** — 不引入 Pydantic 新依賴；只用 stdlib + 防禦性 .get()
- JSON parse 失敗 → 回 None，caller fallback 回原 raw 字串（zero UX 回歸）
- markdown render 與既有 build_fund_json_prompt 輸出格式一致（同 4 節 / 同 emoji header）

公開 API：
- FUND_JSON_SCHEMA_HINT     — 餵 LLM 的 JSON schema 描述（嵌進 prompt）
- parse_llm_json(text)      — tolerant JSON parser（剝 ```json fence、找首個 {）
- fund_analysis_to_markdown(data) — 4 節 dict → markdown 字串

JSON 契約（fund_analysis）：
{
  "sections": [
    {"title": "🌡️ 一、景氣位階 × 基金類別建議", "bullets": ["..."], "is_checklist": false},
    {"title": "🩺 二、基金體質診斷",            "bullets": ["..."], "is_checklist": false},
    {"title": "📍 三、量化買賣點分析",          "bullets": ["..."], "is_checklist": false},
    {"title": "🔄 四、本週操作待辦清單",        "bullets": ["..."], "is_checklist": true}
  ]
}
"""
from __future__ import annotations

import json
import re


# ── LLM prompt 內嵌的 schema 範例 ────────────────────────
FUND_JSON_SCHEMA_HINT = """請以**有效 JSON 物件**輸出（禁止 markdown / 禁止 ```json 包圍），結構如下：
{
  "sections": [
    {
      "title": "🌡️ 一、景氣位階 × 基金類別建議",
      "bullets": ["每行一個重點", "至少 2-3 條"],
      "is_checklist": false
    },
    {
      "title": "🩺 二、基金體質診斷",
      "bullets": ["..."],
      "is_checklist": false
    },
    {
      "title": "📍 三、量化買賣點分析",
      "bullets": ["..."],
      "is_checklist": false
    },
    {
      "title": "💎 四、持股 × 新聞影響評估",
      "bullets": ["點名 2-3 檔持股 + 對應新聞", "繼續持有 6-12 個月損益情境", "減碼/觀察/持有建議"],
      "is_checklist": false
    },
    {
      "title": "🔄 五、本週操作待辦清單",
      "bullets": ["具體行動（含觸發條件或目標數字）", "至少 3-5 條", "最後一條必須是本週核心原則"],
      "is_checklist": true
    }
  ]
}

【嚴格規則】
- 必須 5 個 section，title 完全照抄上方五個字串
- 第五節 is_checklist=true，其餘為 false
- 若持股或新聞資料不足，第四節 bullets 應為 ["資料不足，建議重抓基金持股 + 載入新聞後重試"]
- bullets 每行純文字，不含項目符號 "-" 或 checkbox（service 端會自動加）
- 整體只回 JSON，無前後綴文字"""


# ════════════════════════════════════════════════════════════
# JSON parser（tolerant）
# ════════════════════════════════════════════════════════════
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def parse_llm_json(text: str) -> dict | None:
    """Tolerant JSON parser：剝 ```json fence、找首個 { ... }，json.loads。

    Returns:
        dict on success / None on failure（caller fallback markdown raw）
    """
    if not text or not isinstance(text, str):
        return None
    s = text.strip()
    # 1. 嘗試直接 parse（理想情況）
    try:
        v = json.loads(s)
        return v if isinstance(v, dict) else None
    except (json.JSONDecodeError, TypeError):
        pass
    # 2. 剝 ```json ... ``` fence
    m = _JSON_FENCE_RE.search(s)
    if m:
        try:
            v = json.loads(m.group(1).strip())
            return v if isinstance(v, dict) else None
        except (json.JSONDecodeError, TypeError):
            pass
    # 3. 找首個 { 到最後一個 }
    i = s.find("{")
    j = s.rfind("}")
    if i >= 0 and j > i:
        try:
            v = json.loads(s[i:j+1])
            return v if isinstance(v, dict) else None
        except (json.JSONDecodeError, TypeError):
            pass
    return None


# ════════════════════════════════════════════════════════════
# fund_analysis：dict → markdown 反向組裝
# ════════════════════════════════════════════════════════════
def fund_analysis_to_markdown(data: dict | None) -> str | None:
    """4 節 dict → markdown 字串（與既有 build_fund_json_prompt 4 節格式一致）。

    Args:
        data: parse_llm_json 結果；若 None 或 schema 不對 → 回 None（caller fallback）

    Returns:
        markdown 字串 / None（schema 不合）

    格式：
        ### <title>
        - <bullet>             (is_checklist=False)
        - [ ] <bullet>         (is_checklist=True)
        (空行分隔節)
    """
    if not data or not isinstance(data, dict):
        return None
    sections = data.get("sections")
    if not isinstance(sections, list) or not sections:
        return None
    parts: list[str] = []
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        title = str(sec.get("title", "")).strip()
        if not title:
            continue
        bullets = sec.get("bullets") or []
        is_checklist = bool(sec.get("is_checklist", False))
        parts.append(f"### {title}")
        for b in bullets:
            b_text = str(b).strip()
            if not b_text:
                continue
            # 防 LLM 提前加項目符號；正規化掉
            b_text = re.sub(r"^[-*•]\s*", "", b_text)
            b_text = re.sub(r"^\[\s*[\sx✓]?\s*\]\s*", "", b_text)
            if is_checklist:
                parts.append(f"- [ ] {b_text}")
            else:
                parts.append(f"- {b_text}")
        parts.append("")   # 節間空行
    out = "\n".join(parts).rstrip()
    return out or None
