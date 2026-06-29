"""services/ai_prompts.py — AI prompt 模板層（v18.112 AI-2 抽出）

設計原則：
- **純函式**：不 import streamlit / 不發 API 請求
- 接收「已格式化字串」當參數，回傳完整 prompt — caller (services/ai_service.py)
  負責資料 reshape (dedup / clean / format)，本層只組裝最終文字
- 一個 builder 對應一個 ai_service 公開函式，名字鏡像對齊（build_<name>_prompt）

分層歸位：
- services/ai_service.py    — 資料 reshape + _gemini 呼叫
- services/ai_prompts.py    — prompt 模板（本檔）
- services/prompts.* 未來可進一步拆檔，但目前 4 個 builder 共 ~200 行單檔即可

公開 API：
- build_mk_advisor_prompt       — analyze_portfolio_mk_advisor (策略3 組合 4 節)
- build_structured_summary_prompt — v18.214 通用：吃該 Tab 全章節快照,逐章節
                                    白話結論 + 時事(取代舊 4 視角散文 builder)

v18.238：移除 `build_fund_json_prompt` / `build_fund_json_structured_prompt`
        + 整個 `services/ai_models.py`(dead code 自 v18.209 起 zero live caller)。
v19.239：R7 EX-AI-1 連動 — 移除 `build_global_prompt` + `build_event_impact_prompt`
        (對應 ai_service.py 的 analyze_global / event_impact_analysis dead code 一併清)。
"""
from __future__ import annotations


# ════════════════════════════════════════════════════════════
# 3. analyze_portfolio_mk_advisor — 策略3 組合 4 節 + Phase 4/3-B 引用
# ════════════════════════════════════════════════════════════
def build_mk_advisor_prompt(*, phase: str, score, alloc_str: str,
                            ind_str: str, driver_str: str, subcycle_str: str,
                            news_str: str, n_sys: int, n_gen: int,
                            pf_snap: str, loaded_count: int,
                            tot_inv_twd: int,
                            holdings_str: str = "") -> str:
    """組合「MK 策略3 組合深度建議」prompt（4 節，含 Phase 4 / 3-B + v18.135 持股 × 新聞引用）。

    v18.135 新增 holdings_str：逐基金 top10 持股快照，要求 AI 第二節「換股建議」
    跨基金 × 新聞做底層持股級別分析（哪檔基金的 X 持股最受 Y 新聞衝擊）。
    """
    _hold_section = (f"\n═══ 各基金底層前 10 大持股（v18.135 跨基金持股 × 新聞影響用）═══\n{holdings_str}\n" if holdings_str.strip() else "")
    return f"""你是「策略3 以息養股」方法論的高階教練。針對以下組合給結構化建議，禁止籠統廢話。

═══ 當前景氣位階 ═══
位階：{phase}（評分 {score}/10）
建議配置：{alloc_str}

═══ 關鍵總經指標 ═══
{ind_str}

═══ 領先指標排名（Phase 4 lag-correlation Top 5 — 哪個 driver 最能預測 target 未來變化）═══
{driver_str}

═══ 子領域燈號歷史回測（Phase 3-B — 紅/綠燈出現後 target 平均變化的實證統計）═══
{subcycle_str}

═══ 近期國際財經新聞（{n_sys + n_gen} 條：{n_sys} 系統性風險 + {n_gen} 一般財經，已過濾關鍵字）═══
{news_str}

═══ 投資組合 — **目前主帳本實際持倉**（共 {loaded_count} 檔｜投入合計 NT${tot_inv_twd:,}）═══
（注意：以下是使用者已經落帳的實際投入，**不包含** A/B/C 再平衡分頁中尚未提交的試算金額）
{pf_snap}
{_hold_section}

═══ 輸出格式（繁體中文，4 節必出，每節用 ### 開頭）═══

### 🚨 一、目前組合的 3 大缺點
針對以上組合，列出 3 個最嚴重問題（例：⚠️ JFZN3 吃本金 5pp、ACDD01 占比過低 1% 失去 satellite 意義、整體 USD 占比 90% 匯率風險）。
每點用「**缺點**：... → **影響**：... → **建議行動**：...」格式。

### 🔄 二、根據景氣位階「{phase}」+ 領先指標排名 + 近期新聞 + 底層持股的換股建議
列出 2-3 檔**該減碼**的標的（指明代碼 + 原因；若新聞顯示該標的所在區域/題材有系統性風險，優先點名）+ 2-3 檔**該補進**的類型（不必指名，給類別如「長天期美債基金」「均衡配置型」）。
**必須引用上方「領先指標排名」前 3 名 driver**（例：「Top 1 SLOOS 反向 -0.62 → 銀行緊縮放貸領先 target 下行 3 個月 → 減碼景氣循環衛星」），對應當前景氣位階「{phase}」+ 新聞事件特性。
**v18.135 必引用：若上方有「各基金底層前 10 大持股」資料**，必須點名 2-3 檔具體**底層個股**（用持股名稱），分析它們在哪些基金內、被哪條新聞衝擊；評估「若繼續持有這些基金 6-12 個月」，底層個股的最大可能損益。

### ⚖️ 三、建議配置比例（核心 / 衛星 / 現金）
給出具體 % 比例與每個 bucket 該放什麼類型基金。
若使用者組合與建議差距 > 20pp，明確標「需大幅調整」。
**參考上方「子領域燈號歷史回測」**：若多個子領域顯示「✅ 紅燈確實領先衰退」且當前燈號為紅，明確要求提高現金比例至 25%+；若新聞顯示「系統性風險升高」（銀行倒閉/戰爭升級/大規模拋售）同樣加碼現金。

### 🎯 四、兩種操作策略 — 高賣低買 vs 跌就買
**策略 A：高賣低買（順勢操作）**
- 何時賣（觸發條件）
- 何時買（觸發條件）
- 適合什麼樣的市場狀態（VIX 多少 / NBER 衰退否）

**策略 B：跌就買（左側交易，定期定額）**
- 什麼條件下這策略更適合（系統性風險高時）
- 注意事項（必要現金水位 / 不超過總資產 X%）

最後一段用「⚠️ **系統性風險警示**」開頭，**必須引用：(1) 1-2 條上方新聞、(2) Phase 4 領先 driver 前 2 名的方向與幅度、(3) Phase 3-B 至少一個子領域的紅燈歷史回測結論**，加上 VIX / 殖利率倒掛 / NBER 等指標，給「目前該偏向 A 還是 B」的明確結論。
═══════════════════════════════════════════════
【嚴格規則】只能引用上方資料（含新聞 / driver 排名 / 燈號回測）；禁止編造未提及的基金 / 數字 / 統計結論。"""


# ════════════════════════════════════════════════════════════
# v18.214 通用「Tab 白話總體檢」結構化摘要 builder
# - 吃該 Tab「全章節快照」+ 章節清單 + 新聞，逐章節給白話結論 + 時事
# - 取代 v18.159 的 4 視角散文 builder（trend/allocation/beginner/news）
# - 風格：很白話、像跟朋友聊天，盡量不用專業術語（非用不可時用括號解釋）
# ════════════════════════════════════════════════════════════
def build_structured_summary_prompt(*, tab_label: str, snapshot: str,
                                    sections: list[str],
                                    headlines: list[str] | None = None,
                                    stale_note: str = "") -> str:
    """通用『白話總體檢』：逐章節結論 + 時事影響 + 一句話總結。

    sections：該 Tab 的章節名稱清單（依顯示順序），AI 必須逐節各給一段。
    headlines：近期新聞標題；用於「最近新聞影響」段，無則明說沒新聞。
    """
    _secs = [str(s).strip() for s in (sections or []) if str(s).strip()]
    _sec_block = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(_secs)) \
        if _secs else "  （未指定章節，請依快照自行分段）"
    _hl = [str(h) for h in (headlines or []) if str(h).strip()][:8]
    _h_block = "\n".join(f"- {h}" for h in _hl) if _hl else "（這次沒有抓到相關新聞）"
    return f"""你是一位很親切的理財小幫手，講話像在跟剛入門的朋友聊天。

【最重要的講話規則】
- 全程用「很白話」的繁體中文，像長輩在跟晚輩解釋，盡量不要用專業金融術語。
- 真的非用某個術語不可時，後面一定要用括號補一句生活化的白話解釋
  （例：夏普值（就是「冒這麼大風險、到底值不值得」的分數））。
- 可以多用生活比喻：天氣、體檢、紅綠燈、考試成績、買菜挑水果…。
- 不要長篇大論，每段 2-4 句講重點就好。

【嚴格規則】只能根據下面的「資料快照」與「最近新聞」來講，
禁止上網搜尋、禁止杜撰任何沒出現的數字、基金或公司名。資料缺就老實說「這項目前沒資料」。

[分析範圍] {tab_label}

[資料快照]
{snapshot}{stale_note}

[最近新聞（時事）]
{_h_block}

═══════════════════════════════════════════
請用繁體中文，**依照下面的章節順序逐節輸出**，每一節都用 `### ` 開頭當標題，
而且每一節都要包含這兩塊：
  •【白話結論】這一節的數字在說什麼、現在算好還是壞、該不該擔心（2-4 句白話）。
  •【最近新聞影響】上面的新聞跟「這一節」有沒有關係？有就講利多/利空/沒差，
    沒有相關新聞就寫「這部分最近沒看到相關新聞」。

需要逐節輸出的章節：
{_sec_block}

最後再加一節：

### ✅ 一句話總結 & 下一步
- 用一句最白話的話總結「現在整體狀況」。
- 給 1-2 個很具體、新手也做得到的下一步（例：這個月繼續定期定額、先別急著加碼、某檔可以考慮換掉）。

【再次提醒】只能引用上面快照與新聞裡的內容，不要編造；能多白話就多白話。"""
