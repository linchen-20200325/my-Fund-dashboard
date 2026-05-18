"""services/ai_service.py — AI 分析引擎 Service Layer
（v11.0 C-17 從 ai_engine.py 搬入）

AI 分析引擎 v13 — 單次呼叫 · 含風險預警快照 · 六因子評分輸入 · 容錯降級

公開 API：
  - assign_asset_role — 核心/衛星關鍵字分類
  - _gemini           — Gemini API 單次呼叫（含 retry / 容錯降級）
  - _build_snapshot   — 整合 indicators + phase + 風險快照
  - analyze_global    — 全球總經分析
  - analyze_fund_json — 單一基金 AI 分析
  - analyze_portfolio_correlation — 組合相關性分析
  - analyze_portfolio_mk_advisor   — MK 智能戰情室 AI 建議
  - build_stale_flags  — Data Guard STALE 旗標注入
  - event_impact_analysis — 持股 × 新聞交叉比對警報
  - analyze_macro_structured — v10 六章節輸出

v11.0 分層歸位：本檔屬於 Service Layer，業務邏輯 + Gemini API 呼叫。
（Gemini HTTP 呼叫雖屬 I/O，但與 prompt 構造 / 輸出解析緊耦合，整檔保留服務層
 是常見做法 — 類似 fetch_stock_three_ratios 的處理；未來可拆 LLM client 到 infra/）
向後相容：根目錄 ai_engine.py 保留 shim re-export，既有 caller 零修改。
"""
import requests, json

from infra.llm import call_llm
from services.ai_models import (
    FUND_JSON_SCHEMA_HINT,
    fund_analysis_to_markdown,
    parse_llm_json,
)
from services.ai_prompts import (
    build_event_impact_prompt,
    build_fund_json_prompt,
    build_fund_json_structured_prompt,
    build_global_prompt,
    build_macro_structured_prompt,
    build_mk_advisor_prompt,
)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

# ── 核心/衛星關鍵字分類 ──────────────────────────────────────
_CORE_KW  = ["債", "收益", "配息", "平衡", "高息", "公用", "多元",
             "income", "bond", "dividend", "balanced", "utility"]
_SAT_KW   = ["ai", "科技", "半導體", "成長", "主題", "印度", "越南",
             "生技", "醫療", "能源", "原物料", "中國", "新興",
             "tech", "innovation", "growth", "emerging"]

def assign_asset_role(fund_name: str, manual_override: str = "") -> str:
    """
    優先序：手動設定 > 名稱關鍵字 > 預設衛星
    回傳 'core' 或 'satellite'
    """
    if manual_override in ("core", "satellite"):
        return manual_override
    name_lower = (fund_name or "").lower()
    if any(kw in name_lower for kw in _CORE_KW):
        return "core"
    if any(kw in name_lower for kw in _SAT_KW):
        return "satellite"
    return "satellite"   # 未知預設衛星（較保守）


# ── Gemini API 呼叫（容錯版）───────────────────────────────
def _gemini(api_key: str, prompt: str, max_tokens: int = 2000,
            retry: int = 2, force_json: bool = False):
    """單次 API 呼叫，容錯降級，不崩潰 App"""
    if not api_key:
        return "⚠️ 請先填入 Gemini API Key"
    import time
    for attempt in range(retry + 1):
        try:
            gen_cfg = {
                "temperature": 0.7,       # 較高溫：輸出更完整自然
                "maxOutputTokens": max_tokens,
            }
            # gemini-2.5-flash 是 thinking 模型：thinkingBudget=0 關閉思考鏈
            # 讓全部 token 用於實際輸出而非內部推理
            body = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": gen_cfg,
            }
            if "2.5" in GEMINI_URL or "flash" in GEMINI_URL:
                body["generationConfig"]["thinkingConfig"] = {"thinkingBudget": 0}
            if force_json:
                gen_cfg["responseMimeType"] = "application/json"
            r = requests.post(
                f"{GEMINI_URL}?key={api_key}",
                json=body,
                headers={"Content-Type": "application/json"},
                timeout=90,
            )
            if r.status_code == 200:
                cands = r.json().get("candidates", [])
                if cands:
                    parts = cands[0].get("content", {}).get("parts", [])
                    return "\n".join(p.get("text","") for p in parts if "text" in p).strip()
                return "⚠️ Gemini 回傳空結果，請重試"
            elif r.status_code == 429:
                wait = 20 * (attempt + 1)
                if attempt < retry:
                    time.sleep(wait); continue
                return (
                    "❌ **Gemini 配額已達上限（HTTP 429）**\n\n"
                    "請等待 1-2 分鐘後重試，或至 Google AI Studio 確認用量。"
                )
            else:
                if attempt < retry:
                    time.sleep(5); continue
                return f"❌ HTTP {r.status_code}：{r.text[:150]}"
        except requests.exceptions.Timeout:
            if attempt < retry:
                time.sleep(5); continue
            return "❌ 請求逾時，請重試"
        except Exception as e:
            return f"❌ {e}"
    return "❌ 重試次數已達上限"


# ── 數據快照建構（極致精簡，不傳歷史 Array）─────────────────
def _build_snapshot(indicators: dict, phase_info: dict,
                    portfolio_funds: list, focus_fund: dict,
                    news_headlines: list) -> str:
    """
    將所有數據壓縮為純文字快照，不傳歷史淨值數組。
    目標：整個快照 < 800 tokens
    """
    pi = phase_info or {}
    lines = ["【數據快照 — AI 只能根據此快照分析，嚴禁自行搜尋外部資訊】"]

    # ── 1. 總經（只留關鍵 5 指標 + 位階）────────────────
    lines.append("\n[總經位階]")
    lines.append(
        f"位階:{pi.get('phase','?')} 評分:{pi.get('score','?')}/10 "
        f"趨勢:{pi.get('trend_arrow','?')}→{pi.get('next_phase_name','?')} "
        f"衰退率:{pi.get('rec_prob','?')}%"
    )
    alloc = pi.get("allocation", {})
    if alloc:
        lines.append("建議配置:" + " ".join(f"{k}{v}%" for k,v in alloc.items()))
    alloc_t = pi.get("alloc_transition", {})
    if alloc_t:
        lines.append("轉位階後調整:" + " ".join(
            f"{k}:{v['from']}%→{v['to']}%" for k,v in alloc_t.items()))
    alerts = pi.get("alerts", [])
    if alerts:
        lines.append("⚠️ 警報:" + " | ".join(str(a) for a in alerts[:2]))

    # 只傳最關鍵 5 指標數值
    KEY_IND = ["PMI","HY_SPREAD","YIELD_10Y2Y","VIX","CPI"]
    ind_vals = []
    for k in KEY_IND:
        v = (indicators or {}).get(k, {})
        if v:
            ind_vals.append(f"{k}:{v.get('value','?')}{v.get('unit','')} {v.get('signal','')}")
    if ind_vals:
        lines.append("指標:" + " | ".join(ind_vals))

    # ── 2. 最新新聞標題（最多 3 則，只傳標題）───────────
    if news_headlines:
        lines.append("\n[最新新聞（僅標題）]")
        for h in news_headlines[:3]:
            lines.append(f"• {str(h)[:60]}")

    # ── 3. 組合基金（每檔精簡 1 行）────────────────────
    loaded = [f for f in (portfolio_funds or []) if f.get("loaded")]
    if loaded:
        lines.append(f"\n[投資組合 — {len(loaded)} 檔]")
        for f in loaded:
            m   = f.get("metrics", {}) or {}
            mj  = f.get("moneydj_raw", {}) or {}
            rt  = (mj.get("risk_metrics") or {}).get("risk_table", {}) or {}
            yr  = rt.get("一年", {}) or {}
            pf  = mj.get("perf", {}) or {}
            adr = mj.get("moneydj_div_yield") or m.get("annual_div_rate", 0) or 0
            tr1 = pf.get("1Y")
            eat = "🔴吃本金" if (tr1 is not None and tr1 < adr and adr > 0) else "✅"
            role_raw = "core" if f.get("is_core") else "satellite"
            role = assign_asset_role(f.get("name",""), role_raw)
            role_icon = "🛡️核心" if role == "core" else "⚡衛星"
            pos  = m.get("pos_label", "?")
            inv  = f.get("invest_twd", 0) or 0
            name = f.get("name","") or f.get("code","?")
            lines.append(
                f"  {role_icon} {name[:18]} | "
                f"配息{adr:.1f}% TR1Y:{tr1 if tr1 is not None else 'N/A'}% {eat} | "
                f"σ:{yr.get('標準差','?')}% Sharpe:{yr.get('Sharpe','?')} "
                f"DD:{m.get('max_drawdown','?')}% NAV位置:{pos}"
                + (f" NT${inv:,}" if inv else "")
            )

    # ── 4. 個別基金（僅摘要，不傳歷史淨值）─────────────
    if focus_fund:
        m3  = focus_fund.get("metrics", {}) or {}
        mj3 = focus_fund.get("moneydj_raw", {}) or {}
        pf3 = mj3.get("perf", {}) or {}
        adr3 = mj3.get("moneydj_div_yield") or m3.get("annual_div_rate",0) or 0
        tr3  = pf3.get("1Y")
        eat3 = "🔴吃本金" if (tr3 is not None and tr3 < adr3 and adr3>0) else "✅"
        name3 = focus_fund.get("fund_name","") or "?"
        lines.append(f"\n[個別基金診斷 — {name3}]")
        lines.append(
            f"  NAV:{m3.get('nav','?')} 位置:{m3.get('pos_label','?')} | "
            f"買1σ:{m3.get('buy1','')} 買2σ:{m3.get('buy2','')} 停利:{m3.get('sell1','')}"
        )
        lines.append(f"  配息:{adr3:.1f}% TR1Y:{tr3 if tr3 is not None else 'N/A'}% {eat3}")


    # ── 5. 風險預警快照（v13 新增）────────────────────────────────
    try:
        from services.portfolio_service import risk_alert as _ra
        _regime_info = pi.get("regime_info", {}) or {}
        _regime      = _regime_info.get("regime", "")
        _hy          = (indicators or {}).get("HY_SPREAD", {}).get("value")
        _vix_v       = (indicators or {}).get("VIX", {}).get("value")
        _fed_v2      = (indicators or {}).get("FED_RATE", {}).get("value")
        _fed_p2      = (indicators or {}).get("FED_RATE", {}).get("prev")
        _fed_dir     = "up" if (_fed_v2 and _fed_p2 and _fed_v2 > _fed_p2) else "down"
        _alerts      = _ra(regime=_regime, hy_spread=_hy, vix=_vix_v, fed_direction=_fed_dir)
        red_alerts = [a for a in _alerts if a["level"] == "red"]
        if red_alerts:
            lines.append("\n[風險預警]")
            for a in red_alerts[:2]:
                lines.append(f"  {a['message']}")
    except Exception:
        pass

    return "\n".join(lines)


# ── 全局投資決策（主函數）───────────────────────────────────
def analyze_global(api_key: str, indicators: dict, phase_info: dict,
                   portfolio_funds: list = None, focus_fund: dict = None,
                   news_headlines: list = None, core_target_pct: int = 80) -> str:
    """
    v12 唯一 AI 入口：單次呼叫，輸出四節投資決策
    - 不自行搜尋任何外部資訊
    - 輸入 < 800 tokens，輸出 < 1500 tokens
    """
    snapshot = _build_snapshot(indicators, phase_info,
                               portfolio_funds, focus_fund, news_headlines)
    pi = phase_info or {}
    phase = pi.get("phase","?")
    alloc = pi.get("allocation", {})
    alloc_str = " / ".join(f"{k}{v}%" for k,v in alloc.items()) if alloc else "未知"

    prompt = build_global_prompt(
        snapshot=snapshot, phase=phase, alloc_str=alloc_str,
        core_target_pct=core_target_pct,
    )
    return call_llm(prompt, max_tokens=8192, gemini_key=api_key)


def analyze_fund_json(api_key, fund_name, metrics, perf_data, phase_info,
                      risk_metrics=None, holdings=None, currency="USD",
                      view_mode: str = "🔴 L3 老手沙盤",
                      news_items: list = None):
    """
    基金教練 AI 分析 v3.0 + V5.0 動態 Prompt + v18.135 持股 × 新聞交叉
    五節結構：景氣×基金類別 / 體質診斷 / 量化買賣點 / 持股×新聞影響 / 操作待辦
    回傳 Markdown 字串（直接供 st.markdown 顯示）
    view_mode: "🟢 L1 新手導航" | "🟡 L2 學徒覆盤" | "🔴 L3 老手沙盤"
    holdings: dict（如 moneydj_raw.get("holdings")）or list；自動 format 給 prompt
    news_items: RSS 抓的近期新聞（與 MK advisor 同 schema）；自動 format
    """
    m  = metrics   or {}
    pf = perf_data or {}
    pi = phase_info or {}

    # risk_metrics 可能被誤傳為 dividends list，安全取 risk_table
    _rm = risk_metrics if isinstance(risk_metrics, dict) else {}
    rt  = (_rm.get("risk_table") or {})
    yr1 = rt.get("一年", {}) or {}

    # ── 基礎指標 ──────────────────────────────────────────────
    adr    = m.get("annual_div_rate", 0) or 0
    tr1y   = pf.get("1Y")
    eating = (tr1y is not None) and (tr1y < adr) and (adr > 0)
    std    = yr1.get("標準差") or m.get("std_1y", "N/A")
    sharpe = yr1.get("Sharpe") or m.get("sharpe", "N/A")
    nav    = m.get("nav", "N/A")
    pos    = m.get("pos_label", "N/A")
    buy1   = m.get("buy1", "N/A")
    buy2   = m.get("buy2", "N/A")
    sell1  = m.get("sell1", "N/A")
    maxdd  = m.get("max_drawdown", "N/A")
    mgmt_fee = m.get("mgmt_fee") or m.get("total_expense_ratio") or "N/A"
    category = m.get("category") or m.get("fund_type") or "未知"
    phase  = pi.get("phase", "未知")
    score  = pi.get("score", "?")
    alloc  = pi.get("allocation", {})
    alloc_s = " / ".join(f"{k}{v}%" for k, v in alloc.items()) if alloc else "未知"

    # ── -2σ 超跌機會判斷 ──────────────────────────────────────
    sigma_alert = ""
    try:
        if float(nav) <= float(buy2):
            sigma_alert = (
                f"⚡ **超跌機會訊號**：NAV({nav}) 已觸及 -2σ 買點({buy2})，"
                "為策略1「左側交易」加碼區！"
            )
    except (ValueError, TypeError):
        pass

    # ── 景氣位階 → 基金類別對應表 ──────────────────────────────
    _phase_map = {
        "衰退": "長天期美債基金、高評級投資等級債（Beta 最低、抗跌首選）",
        "復甦": "市值型 ETF、中小型股基金、成長型股票基金（早鳥佈局）",
        "擴張": "均衡配置；衛星可佈局科技/主題基金（趨勢追蹤）",
        "高峰": "核心配息基金優先；壓縮衛星部位落袋為安（居高思危）",
    }
    phase_rec = _phase_map.get(phase, "均衡配置（景氣位階待確認）")

    # ── Sharpe 評語 ───────────────────────────────────────────
    try:
        _sh = float(sharpe)
        sharpe_comment = "優秀（>0.5，策略2：經理人長期控風能力佳）" if _sh > 0.5 else \
                         "普通（0~0.5，尚可持有，密切觀察）" if _sh >= 0 else \
                         "差勁（<0，承擔風險未獲報酬，考慮替換標的）"
    except (ValueError, TypeError):
        sharpe_comment = "資料不足，無法評估"

    # ── V5.0 動態 Prompt 語氣調整 ──────────────────────────────────
    _tone_map = {
        "🟢 L1 新手導航": (
            "[語氣要求：白話文，用天氣/球賽比喻，完全禁止出現 Z-Score/標準差等術語。"
            "第四節待辦清單是重點，讓新手看完立刻知道做什麼。]"
        ),
        "🟡 L2 學徒覆盤": (
            "[語氣要求：解釋因果邏輯，必須引用歷史案例（2008/2020/2022）對比當前數據。"
            "鼓勵用歷史驗證建立信任，適當提及指標但用比喻解釋。]"
        ),
        "🔴 L3 老手沙盤": (
            "[語氣要求：專業量化，直接點出乖離率/Z-Score/Sharpe 數值，"
            "分析背離訊號，給出精確進出場條件。]"
        ),
    }
    _tone_directive = _tone_map.get(view_mode, _tone_map["🔴 L3 老手沙盤"])

    # v18.135: 持股 + 新聞 format 給 prompt 第四節「持股 × 新聞影響」交叉分析
    holdings_text = _format_fund_holdings(holdings)
    news_text = _format_news_for_fund_ai(news_items or [])

    # v18.114 AI-4: 結構化 JSON 輸出（試水溫，僅本函式）
    # 流程：structured prompt → call_llm(response_format=json) → tolerant parse
    #      → fund_analysis_to_markdown 組回 markdown 給 UI（caller 零修改）
    #      → 任一步失敗 → fallback 原 markdown prompt，確保不破 UX
    structured_prompt = build_fund_json_structured_prompt(
        fund_name=fund_name, category=category, currency=currency,
        nav=nav, pos=pos, sigma_alert=sigma_alert,
        buy1=buy1, buy2=buy2, sell1=sell1,
        adr=adr, tr1y=tr1y, std=std, sharpe=sharpe,
        sharpe_comment=sharpe_comment, maxdd=maxdd, mgmt_fee=mgmt_fee, pf=pf,
        phase=phase, score=score, alloc_s=alloc_s, phase_rec=phase_rec,
        eating=eating, tone_directive=_tone_directive,
        holdings_text=holdings_text, news_text=news_text,
        schema_hint=FUND_JSON_SCHEMA_HINT,
    )
    raw = call_llm(structured_prompt, max_tokens=1800, gemini_key=api_key,
                   response_format="json")
    # raw 若以 ❌/⚠️ 開頭 → call_llm 已是錯誤訊息字串，直接返回讓 UI 顯示錯誤
    if raw and str(raw).lstrip().startswith(("❌", "⚠️")):
        return raw
    parsed = parse_llm_json(raw)
    md = fund_analysis_to_markdown(parsed)
    if md:
        return md
    # ── JSON parse 或 schema 不合 → fallback：用原 markdown prompt 重打 ──
    fallback_prompt = build_fund_json_prompt(
        fund_name=fund_name, category=category, currency=currency,
        nav=nav, pos=pos, sigma_alert=sigma_alert,
        buy1=buy1, buy2=buy2, sell1=sell1,
        adr=adr, tr1y=tr1y, std=std, sharpe=sharpe,
        sharpe_comment=sharpe_comment, maxdd=maxdd, mgmt_fee=mgmt_fee, pf=pf,
        phase=phase, score=score, alloc_s=alloc_s, phase_rec=phase_rec,
        eating=eating, tone_directive=_tone_directive,
        holdings_text=holdings_text, news_text=news_text,
    )
    return call_llm(fallback_prompt, max_tokens=2400, gemini_key=api_key)


# ────────────────────────────────────────────────────────────────
# v18.135: 持股 / 新聞 format helper（fund_json + mk_advisor 共用）
# ────────────────────────────────────────────────────────────────
def _format_fund_holdings(holdings) -> str:
    """把 moneydj_raw.holdings 結構（含 top_holdings / sector_alloc）轉為
    AI prompt 用的 markdown 區塊。空輸入回空字串。"""
    if not holdings:
        return ""
    # 支援兩種 schema：
    #  - dict: {"top_holdings": [{"name", "weight", ...}], "sector_alloc": [...]}
    #  - list (legacy): [{"name", "weight"}, ...]
    if isinstance(holdings, list):
        tops, sectors = holdings, []
    elif isinstance(holdings, dict):
        tops = holdings.get("top_holdings") or []
        sectors = holdings.get("sector_alloc") or []
    else:
        return ""
    if not tops and not sectors:
        return ""
    lines = ["  [基金前 10 大持股]"]
    for i, t in enumerate(tops[:10], 1):
        if not isinstance(t, dict):
            continue
        _nm = str(t.get("name", "") or t.get("stock", "") or "?")[:30]
        _wt = t.get("weight") or t.get("percentage") or t.get("pct")
        _wt_s = f" {_wt}%" if _wt is not None else ""
        lines.append(f"    {i}. {_nm}{_wt_s}")
    if sectors:
        lines.append("\n  [產業配置 Top 5]")
        for s in sectors[:5]:
            if not isinstance(s, dict):
                continue
            _sn = str(s.get("name", "") or s.get("sector", "") or "?")[:20]
            _sw = s.get("weight") or s.get("percentage")
            _sw_s = f" {_sw}%" if _sw is not None else ""
            lines.append(f"    - {_sn}{_sw_s}")
    return "\n".join(lines)


def _format_news_for_fund_ai(news_items: list, max_n: int = 6) -> str:
    """RSS news → AI prompt markdown 區塊（簡版，max 6 條）。"""
    if not news_items:
        return ""
    import re as _re
    import html as _html
    lines = ["  [近期國際財經新聞]"]
    n = 0
    for h in news_items:
        if n >= max_n:
            break
        if not isinstance(h, dict):
            continue
        _t = str(h.get("title", "") or "").strip()
        if not _t:
            continue
        _t = _re.sub(r"<[^>]+>", "", _t)
        _t = _html.unescape(_t)
        _t = _re.sub(r"\s+", " ", _t)[:80]
        _src = str(h.get("source", "") or "?")[:20]
        _is_sys = bool(h.get("is_systemic", False))
        _icon = "🚨" if _is_sys else "•"
        lines.append(f"    {_icon} [{_src}] {_t}")
        n += 1
    return "\n".join(lines) if n > 0 else ""

def analyze_portfolio_correlation(api_key, funds_list, phase_info, data_text=""):
    try:
        import streamlit as st
        _ind = st.session_state.get("indicators", {})
    except Exception:
        _ind = {}
    return analyze_global(api_key, _ind, phase_info, portfolio_funds=funds_list)


# ══════════════════════════════════════════════════════════════════
# v18.81 MK 老師深度組合建議 — 結構化「缺點 / 更換 / 配置 / 策略」
# 比 analyze_global 更聚焦：
#   - 點名具體缺點（吃本金 / 低 Sharpe / 過度集中 / NAV 過高）
#   - 給標的更換建議（按景氣位階）
#   - 提供高賣低買 + 跌就買兩條策略
#   - 評估系統性風險
# ══════════════════════════════════════════════════════════════════
def analyze_portfolio_mk_advisor(api_key: str, portfolio_funds: list,
                                  phase_info: dict, ledgers: dict = None,
                                  indicators: dict = None,
                                  news_headlines: list = None,
                                  driver_ranking: dict = None,
                                  subcycle_lights: list = None) -> str:
    """
    策略3 深度組合建議 — 結構化 4 節：缺點 / 換股 / 配置 / 策略
    portfolio_funds: [{code, name, currency, invest_twd, metrics, moneydj_raw, ...}]
    phase_info: {phase, score, allocation}
    ledgers: {pk_str: Ledger} 可選 — 有則計算當前市值 / P&L
    indicators: {key: {value, score}} 總經指標快照
    news_headlines: [{title, summary, source, published}] 可選 — RSS 抓的近期新聞
                    （v18.85 新增：讓 AI 判斷系統性風險時有實證依據，而非空談）
    driver_ranking:  rank_macro_drivers() 輸出（Phase 4）— 哪個 driver 最能預測 target 變化
    subcycle_lights: backtest_sub_cycle_lights() 輸出（Phase 3-B）— 7 子領域燈號歷史回測
                    （v18.110 新增：把剛修好的 Phase 4 / Phase 3-B 量化結論餵 AI，建議更有實證根據）
    """
    pi = phase_info or {}
    phase = pi.get("phase", "未知")
    score = pi.get("score", "?")
    alloc = pi.get("allocation", {})
    alloc_str = " / ".join(f"{k}{v}%" for k, v in alloc.items()) if alloc else "未知"

    # ── 組合 snapshot：每檔關鍵指標一行 ───────────────────────────
    # v18.88: dedup by code（同 code 跨保單 = 同基金，合併 invest_twd 省 token）
    #         19 條 → ~7 unique code，prompt 縮 ~60%
    loaded = [f for f in (portfolio_funds or []) if f.get("loaded")]
    tot_inv_twd = sum(int(f.get("invest_twd", 0) or 0) for f in loaded)

    # 按 code 聚合：同 code 多保單合併 invest_twd，policies 列表保留
    _by_code: dict = {}
    for f in loaded:
        _c = str(f.get("code", "?")).strip() or "?"
        if _c not in _by_code:
            _by_code[_c] = {
                "fund": f,   # 取第一個樣本當代表（NAV/配息等同 code 都一樣）
                "total_inv": 0,
                "policies": [],
            }
        _by_code[_c]["total_inv"] += int(f.get("invest_twd", 0) or 0)
        _pid = str(f.get("policy_id") or "(未綁)").strip()
        if _pid not in _by_code[_c]["policies"]:
            _by_code[_c]["policies"].append(_pid)

    _lines = []
    for _c, _agg in list(_by_code.items())[:20]:   # cap 20 unique codes
        f = _agg["fund"]
        m = f.get("metrics") or {}
        mj = f.get("moneydj_raw") or {}
        perf = mj.get("perf") or {}
        nm = (f.get("name") or _c)[:16]
        ccy = f.get("currency", "USD")
        inv = _agg["total_inv"]
        pct = round(inv / tot_inv_twd * 100, 1) if tot_inv_twd > 0 else 0
        adr = m.get("annual_div_rate") or mj.get("moneydj_div_yield") or 0
        tr1y = perf.get("1Y")
        try:
            tr1y_f = float(tr1y) if tr1y is not None else None
            adr_f = float(adr) if adr else 0.0
        except Exception:
            tr1y_f, adr_f = None, 0.0
        eating = ""
        if tr1y_f is not None and adr_f > 0 and tr1y_f < adr_f:
            eating = f" ⚠️吃本金({adr_f-tr1y_f:.1f}pp)"
        sharpe = m.get("sharpe", "—")
        is_core = "核心" if f.get("is_core") else "衛星"
        _n_pol = len(_agg["policies"])
        _pol_tag = f"｜跨 {_n_pol} 保單" if _n_pol > 1 else ""
        _lines.append(
            f"- [{is_core}] `{_c}` {nm} ({ccy})"
            f"｜投入 NT${inv:,} ({pct}%){_pol_tag}"
            f"｜配息率 {adr_f:.1f}% / 1Y含息 {tr1y if tr1y is not None else 'N/A'}%"
            f"{eating}｜Sharpe {sharpe}"
        )
    pf_snap = "\n".join(_lines) if _lines else "(尚未載入任何基金)"

    # ── 關鍵總經指標摘要（3-5 個最具決策意義的）────────────────
    ind = indicators or {}
    _key_inds = ["VIX", "T10Y2Y", "PMI", "FED_RATE", "SP500", "USDJPY"]
    _ind_lines = []
    for k in _key_inds:
        v = (ind.get(k) or {}).get("value")
        if v is not None:
            _ind_lines.append(f"  - {k}: {v}")
    ind_str = "\n".join(_ind_lines) if _ind_lines else "  (總經指標未載入)"

    # ── v18.88: 新聞 prompt 大幅瘦身 + 字元清理 ──────────────
    # 使用者反饋「其他 AI 還可以使用，但這邊的突然無法使用，是不是資料過於龐大，
    # 新聞要先處理過才能給 AI 讀取」
    # 修法：(a) RSS summary 常含 HTML tag / 換行 / 特殊 unicode，先清理
    #      (b) 把 news 從 15 條 → 最多 8 條（5 systemic + 3 general 主流）
    #      (c) summary 從 160 → 80 字元，title 從 120 → 100 字元
    import re as _re_news, html as _html_news
    def _clean_news_text(_s: str, maxlen: int) -> str:
        if not _s:
            return ""
        # strip HTML tags
        _s = _re_news.sub(r"<[^>]+>", "", str(_s))
        # decode HTML entities (&amp; &nbsp; ...)
        _s = _html_news.unescape(_s)
        # normalize whitespace / newlines
        _s = _re_news.sub(r"\s+", " ", _s).strip()
        # truncate
        return _s[:maxlen]

    _sys_lines, _gen_lines = [], []
    _n_sys = 0
    _n_gen = 0
    for h in (news_headlines or []):
        # v18.88: 限制 systemic ≤ 5、general ≤ 3，總共 ≤ 8
        _is_sys = bool(h.get("is_systemic", False))
        if _is_sys and _n_sys >= 5:
            continue
        if not _is_sys and _n_gen >= 3:
            continue
        _t = _clean_news_text(h.get("title", ""), 100)
        if not _t:
            continue
        _sm = _clean_news_text(h.get("summary", ""), 80)
        _src = _clean_news_text(h.get("source", ""), 20)
        _pub = _clean_news_text(h.get("published", ""), 16)
        line = (f"  - [{_pub}｜{_src}] {_t}"
                + (f" - {_sm}" if _sm else ""))   # 改一行不換行，省空間
        if _is_sys:
            _sys_lines.append("🚨 " + line.lstrip())
            _n_sys += 1
        else:
            _gen_lines.append(line)
            _n_gen += 1
    if _sys_lines or _gen_lines:
        news_str = ""
        if _sys_lines:
            news_str += (f"  ⚠️ 系統性風險事件（{_n_sys} 條，最高優先級）：\n"
                          + "\n".join(_sys_lines) + "\n\n")
        if _gen_lines:
            news_str += "  📰 一般財經新聞：\n" + "\n".join(_gen_lines)
    else:
        news_str = "  (未提供新聞，無法評估即時系統性風險)"

    # ── v18.110: Phase 4 變數重要性 — 哪個 driver 最能預測 target lag 後變化 ──
    _drv = driver_ranking or {}
    if _drv.get("ok") and _drv.get("ranked"):
        _drv_target = _drv.get("target", "?")
        _drv_lag = _drv.get("lag_months", "?")
        _drv_lines = []
        _medals = ["🥇", "🥈", "🥉"]
        for i, r in enumerate(_drv["ranked"][:5]):   # Top 5
            _m = _medals[i] if i < 3 else "  "
            _dir = "同向 📈" if r.get("direction") == "+" else "反向 📉"
            _drv_lines.append(
                f"  {_m} {r.get('name', r.get('key', '?'))} "
                f"(corr={r.get('corr', 0):+.2f}, |corr|={r.get('abs_corr', 0):.2f}, "
                f"{_dir}, n={r.get('n_overlap', 0)}, 權重={r.get('weight', '?')})"
            )
        driver_str = (f"  target={_drv_target}, lag={_drv_lag} 個月\n"
                      + "\n".join(_drv_lines))
    else:
        driver_str = f"  (driver 排名不可用：{_drv.get('note', '無資料')})"

    # ── v18.110: Phase 3-B 細項燈號歷史回測 — 紅/綠燈出現後 target 平均變化 ──
    _sub = subcycle_lights or []
    if _sub:
        _sub_lines = []
        for r in _sub:
            _nm = r.get("name", "?"); _ic = r.get("icon", "")
            _n = r.get("n_obs", 0)
            _r_chg = r.get("fwd_chg_red"); _g_chg = r.get("fwd_chg_green")
            if _n == 0 or (_r_chg is None and _g_chg is None):
                _sub_lines.append(f"  {_ic} {_nm}: (樣本不足，無歷史回測結論)")
                continue
            _bits = []
            if _r_chg is not None:
                _bits.append(f"🔴 燈後 {_r_chg:+.2f}")
            if _g_chg is not None:
                _bits.append(f"🟢 燈後 {_g_chg:+.2f}")
            if _r_chg is not None and _g_chg is not None:
                _diff = _r_chg - _g_chg
                _verdict = ("✅ 紅燈確實領先衰退" if _diff < -0.05
                            else ("⚠️ 燈號訊號不顯著" if abs(_diff) < 0.05
                                  else "❓ 紅燈反向於預期"))
            else:
                _verdict = ""
            _sub_lines.append(
                f"  {_ic} {_nm}: {' / '.join(_bits)} (n={_n})  {_verdict}"
            )
        subcycle_str = "\n".join(_sub_lines)
    else:
        subcycle_str = "  (子領域燈號回測不可用)"

    # v18.135: 為每檔 loaded 基金 format top-10 持股快照（max ~20 fund × 5 line ≈ 100 行）
    _hold_lines: list = []
    for _f in loaded[:20]:
        _hp = (_f.get("moneydj_raw") or {}).get("holdings") or {}
        _hb = _format_fund_holdings(_hp)
        if _hb:
            _nm = (_f.get("name") or _f.get("code", "?"))[:24]
            _cd = _f.get("code", "?")
            _hold_lines.append(f"\n【{_cd} {_nm}】\n{_hb}")
    holdings_str = "\n".join(_hold_lines)

    prompt = build_mk_advisor_prompt(
        phase=phase, score=score, alloc_str=alloc_str,
        ind_str=ind_str, driver_str=driver_str, subcycle_str=subcycle_str,
        news_str=news_str, n_sys=_n_sys, n_gen=_n_gen,
        pf_snap=pf_snap, loaded_count=len(loaded), tot_inv_twd=tot_inv_twd,
        holdings_str=holdings_str,
    )
    return call_llm(prompt, max_tokens=5000, gemini_key=api_key)


# ====================================================
# AI Automated Error Feedback Loop
# Every Streamlit error intercepted -> LLM reflection -> AI_Error_Ledger.md
# [Tutorial] This is the AI memory system. Dashboard errors are auto-analyzed.
# ====================================================
import os as _os_el, traceback as _tb_el, datetime as _dt_el

def _write_error_ledger(error, context, api_key=""):
    _tb_str = _tb_el.format_exc()
    _ts = _dt_el.datetime.now().strftime("%Y-%m-%d %H:%M")
    _ledger_path = "/content/AI_Error_Ledger.md"
    _reflection = "(no API Key, skip AI reflection)"
    if api_key:
        _prompt = (
            "You are a Python Streamlit dashboard debug expert.\n\n"
            f"[Location] {context}\n"
            f"[Error] {type(error).__name__}: {str(error)[:200]}\n"
            f"[Traceback]\n{_tb_str[:600]}\n\n"
            "Output 3 items (Traditional Chinese, concise):\n"
            "**根本原因**：(1 sentence)\n"
            "**防範規則**：(1 rule)\n"
            "**快速修法**：(1-3 lines in ```python ```)\n"
        )
        try:
            _reflection = _gemini(api_key, _prompt, max_tokens=400)
        except Exception:
            _reflection = "(AI reflection failed)"
    _entry = (
        "\n\n---\n"
        f"## [{_ts}] `{type(error).__name__}` in `{context}`\n\n"
        f"**Error:** {str(error)[:300]}\n\n"
        "<details><summary>Traceback</summary>\n\n"
        f"```\n{_tb_str[:800]}\n```\n\n</details>\n\n"
        f"**AI Reflection:**\n\n{_reflection}\n"
    )
    try:
        if not _os_el.path.exists(_ledger_path):
            with open(_ledger_path, "w", encoding="utf-8") as _f:
                _f.write("# AI_Error_Ledger\n\n> Auto-maintained error log.\n")
        with open(_ledger_path, "a", encoding="utf-8") as _f:
            _f.write(_entry)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════
# v18.1 三節結構化總經 AI 摘要
# 依需求輸出：【現狀解讀】【潛在系統性風險評估】【未來一週觀察重點】
# ══════════════════════════════════════════════════════════════════
def build_stale_flags(data_registry: dict) -> str:
    """
    T3: 掃描 data_registry，回傳月度指標 > 50 天 / 季度 > 110 天的 STALE 標記字串。
    格式: "[STALE: PMI=72d, CPI=68d]"  或空字串

    閾值放寬說明（v16.1）：
    - 月度資料常因「次月中下旬才發布」自然滯後 30-55 天，原 40 天閾值會誤報
    - 改為 50 天（>= 1.5 個發布週期才算 stale），降低 AI 章節零警示噪音
    """
    import datetime as _dt
    today = _dt.date.today()
    stale = []
    monthly_keys = {"PMI","CPI","UNEMPLOYMENT","M2","FED_RATE","PPI","SAHM",
                    "UMCSENT","CONSUMER_CONF","NEW_HOME","PERMIT_HOUSING"}
    quarterly_keys = {"SLOOS"}
    for key, info in (data_registry or {}).items():
        date_str = info.get("latest_date") or info.get("date")
        if not date_str:
            continue
        try:
            d = _dt.date.fromisoformat(str(date_str)[:10])
            age = (today - d).days
        except Exception:
            continue
        if key in monthly_keys and age > 50:
            stale.append(f"{key}={age}d")
        elif key in quarterly_keys and age > 110:
            stale.append(f"{key}={age}d")
    return f"[STALE: {', '.join(stale)}]" if stale else ""


def event_impact_analysis(
    api_key: str,
    news_items: list,
    fund_holdings_text: str = "",
    fund_name: str = "",
) -> str:
    """
    T1: 事件驅動影響分析 — 新聞事件 × 基金底層持股交叉比對
    輸出: Markdown 格式的衝擊警報（若無重大事件，回傳空字串）
    """
    if not api_key or not news_items:
        return ""

    headlines = [item.get("title", "")[:80] for item in news_items[:10] if item.get("title")]
    if not headlines:
        return ""

    holdings_ctx = f"\n[基金持股摘要]\n{fund_holdings_text[:400]}" if fund_holdings_text else ""
    fund_ctx = f"分析標的：{fund_name}" if fund_name else "分析所有持倉基金"

    prompt = build_event_impact_prompt(
        fund_ctx=fund_ctx, headlines=headlines, holdings_ctx=holdings_ctx,
    )

    try:
        result = call_llm(prompt, max_tokens=400, gemini_key=api_key)
        if "無重大事件" in result or "無顯著" in result:
            return ""
        return result
    except Exception:
        return ""


def analyze_macro_structured(
    api_key: str,
    indicators: dict,
    phase_info: dict,
    news_items: list = None,
    systemic_risk: dict = None,
    data_registry: dict = None,
    driver_ranking: dict = None,
    subcycle_lights: list = None,
    sub_cycle_now: list = None,
    max_tokens: int = 2000,
) -> str:
    """
    七節結構化總經 AI 摘要（v10.0 → v18.120）
    T2: 新增「新手行動指引」與「老手量化推演」雙軌輸出
    T3: 自動注入 STALE 標記（月度指標 > 40 天）
    v18.119 issue 3: 接 Phase 4 driver_ranking + Phase 3-B subcycle_lights，
                    AI 解讀總經時必引用這兩段量化證據
    v18.120 issue 1: 加 sub_cycle_now (當下 7 子領域燈號) + 新增第七節「綜合判讀」
                    要求 AI 串連所有資料給統一結論
    """
    if not api_key:
        return "⚠️ 未設定 GEMINI_API_KEY，AI 摘要功能關閉"

    pi  = phase_info or {}
    ind = indicators or {}

    # ── 量化數據快照（精簡版，< 500 tokens）──────────────────
    KEY_FIELDS = [
        ("PMI",          "ISM PMI"),
        ("LEI",          "LEI 領先指標 ⭐"),         # v16.1 高頻替代源
        ("YIELD_10Y2Y",  "10Y-2Y 利差"),
        ("YIELD_10Y3M",  "10Y-3M 利差"),
        ("HY_SPREAD",    "HY 信用利差"),
        ("VIX",          "VIX"),
        ("CPI",          "CPI YoY"),
        ("INFL_EXP_5Y",  "5Y 通膨預期(日) ⭐"),       # v16.1 高頻替代源
        ("FED_RATE",     "Fed Rate"),
        ("M2",           "M2 YoY"),
        ("M2_WEEKLY",    "M2 週頻 YoY ⭐"),           # v16.1 高頻替代源
        ("UNEMPLOYMENT", "失業率"),
        ("JOBLESS",      "初領失業金(萬)"),
        ("CONT_CLAIMS",  "持續失業金(萬) ⭐"),         # v16.1 高頻替代源
        ("CONSUMER_CONF","密大信心"),
        ("PERMIT_HOUSING","建照核發(千) ⭐"),          # v16.1 高頻替代源
        ("DXY",          "美元指數"),
        ("COPPER",       "銅博士 MoM"),
        ("ADL",          "市場廣度 RSP/SPY"),
    ]
    ind_lines = []
    for key, label in KEY_FIELDS:
        v = ind.get(key, {})
        if not v:
            continue
        val  = v.get("value")
        prev = v.get("prev")
        sig  = v.get("signal", "")
        unit = v.get("unit", "")
        if val is None:
            continue
        val_str  = f"{val:.2f}{unit}" if isinstance(val, float) else str(val)
        prev_str = f"（前：{prev:.2f}{unit}）" if isinstance(prev, (int, float)) else ""
        ind_lines.append(f"  {label}: {val_str}{prev_str} {sig}")

    # 殖利率利差公式說明（供 LLM 理解）
    # 利差 = 10年期美債殖利率 - 2年期美債殖利率
    # 公式：Spread = R(10Y) - R(2Y)；倒掛 < 0 = 歷史衰退前兆

    # ── 新聞標題（最多 5 則，含風險評分）───────────────────
    news_section = ""
    if news_items:
        titles = [item.get("title","")[:70] for item in news_items[:5] if item.get("title")]
        if titles:
            news_section = "\n[近期財經新聞標題（最多5則）]\n" + "\n".join(f"• {t}" for t in titles)

    # ── 系統性風險偵測結果 ─────────────────────────────────
    risk_section = ""
    if systemic_risk:
        rl    = systemic_risk.get("risk_level", "LOW")
        rs    = systemic_risk.get("risk_score", 0)
        kws   = [t["keyword"] for t in systemic_risk.get("triggered", [])[:5]]
        risk_section = (
            f"\n[新聞系統性風險偵測]\n"
            f"  評級: {rl}（加權分數: {rs}）\n"
            + (f"  命中關鍵字: {', '.join(kws)}\n" if kws else "")
        )

    # ── 景氣位階摘要 ──────────────────────────────────────
    alloc     = pi.get("allocation", {})
    alloc_str = " / ".join(f"{k}{v}%" for k, v in alloc.items()) if alloc else "未知"
    phase     = pi.get("phase", "未知")
    score     = pi.get("score", "?")
    rec_prob  = pi.get("rec_prob")
    alerts    = pi.get("alerts", [])

    # ── v18.119 issue 3: Phase 4 領先指標排名（lag-correlation Top 5）─────
    drv_section = ""
    _drv = driver_ranking or {}
    if _drv.get("ok") and _drv.get("ranked"):
        _drv_target = _drv.get("target", "?")
        _drv_lag = _drv.get("lag_months", "?")
        _drv_lines = []
        _medals = ["🥇", "🥈", "🥉"]
        for i, r in enumerate(_drv["ranked"][:5]):
            _m = _medals[i] if i < 3 else "  "
            _dir = "同向" if r.get("direction") == "+" else "反向"
            _drv_lines.append(
                f"  {_m} {r.get('name', r.get('key', '?'))} "
                f"(corr={r.get('corr', 0):+.2f}, {_dir}, n={r.get('n_overlap', 0)})"
            )
        drv_section = (
            f"\n[Phase 4 領先指標排名 — target={_drv_target}, lag={_drv_lag} 個月]\n"
            + "\n".join(_drv_lines)
        )

    # ── v18.120 issue 1: 當下 7 子領域燈號（calc_sub_cycle_lights 結果）─
    now_section = ""
    _now = sub_cycle_now or []
    if _now:
        _now_lines = []
        for c in _now:
            _nm = c.get("name", "?"); _ic = c.get("icon", "")
            _sig = c.get("signal", "")
            _ver = c.get("verdict", "")
            _z   = c.get("z_avg")
            _z_s = f"z={_z:+.2f}" if _z is not None else "z=—"
            _now_lines.append(f"  {_ic} {_nm}: {_sig} {_ver} ({_z_s})")
        now_section = "\n[7 子領域當下燈號（Z-Score 健康度）]\n" + "\n".join(_now_lines)

    # ── v18.119 issue 3: Phase 3-B 7 子領域燈號歷史回測 ─────────────
    sub_section = ""
    _sub = subcycle_lights or []
    if _sub:
        _sub_lines = []
        for r in _sub:
            _nm = r.get("name", "?"); _ic = r.get("icon", "")
            _n = r.get("n_obs", 0)
            _r_chg = r.get("fwd_chg_red"); _g_chg = r.get("fwd_chg_green")
            if _n == 0 or (_r_chg is None and _g_chg is None):
                _sub_lines.append(f"  {_ic} {_nm}: (樣本不足)")
                continue
            _bits = []
            if _r_chg is not None:
                _bits.append(f"🔴後{_r_chg:+.2f}")
            if _g_chg is not None:
                _bits.append(f"🟢後{_g_chg:+.2f}")
            _verdict = ""
            if _r_chg is not None and _g_chg is not None:
                _diff = _r_chg - _g_chg
                _verdict = (
                    "✅紅燈領先衰退" if _diff < -0.05
                    else ("⚠️訊號弱" if abs(_diff) < 0.05 else "❓反向")
                )
            _sub_lines.append(
                f"  {_ic} {_nm}: {' / '.join(_bits)} (n={_n}) {_verdict}"
            )
        sub_section = "\n[Phase 3-B 子領域燈號歷史回測]\n" + "\n".join(_sub_lines)

    snapshot = f"""
【量化數據快照 — AI 只能依據此快照分析，嚴禁引用外部資訊】

[景氣位階]
  當前位階: {phase}（評分 {score}/10）
  建議配置: {alloc_str}
  衰退機率: {rec_prob if rec_prob is not None else 'N/A'}%
  風險警報: {' | '.join(alerts[:3]) if alerts else '無'}

[量化指標]
{chr(10).join(ind_lines) or '（無資料）'}
{now_section}
{drv_section}
{sub_section}
{news_section}
{risk_section}
""".strip()

    # ── T3: STALE 標記注入 ─────────────────────────────────────
    stale_str = build_stale_flags(data_registry or {})
    stale_note = f"\n⚠️ 資料新鮮度警告 {stale_str}（標記指標已逾 40 天，分析結論可靠性下降）" if stale_str else ""

    # ── 六節結構 Prompt（v10.0，T2 新手/老手雙軌；v18.112 模板抽至 ai_prompts）
    prompt = build_macro_structured_prompt(snapshot=snapshot, stale_note=stale_note)

    return call_llm(prompt, max_tokens=max_tokens, gemini_key=api_key)
