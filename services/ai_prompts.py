"""services/ai_prompts.py — AI prompt 模板層（v18.112 AI-2 抽出）

設計原則：
- **純函式**：不 import streamlit / 不發 API 請求
- 接收「已格式化字串」當參數，回傳完整 prompt — caller (services/ai_service.py)
  負責資料 reshape (dedup / clean / format)，本層只組裝最終文字
- 一個 builder 對應一個 ai_service 公開函式，名字鏡像對齊（build_<name>_prompt）

分層歸位：
- services/ai_service.py    — 資料 reshape + _gemini 呼叫
- services/ai_prompts.py    — prompt 模板（本檔）
- services/prompts.* 未來可進一步拆檔，但目前 5 個 builder 共 ~200 行單檔即可

公開 API：
- build_global_prompt           — analyze_global (4 節結構)
- build_fund_json_prompt        — analyze_fund_json (單檔基金 4 節)
- build_mk_advisor_prompt       — analyze_portfolio_mk_advisor (策略3 組合 4 節)
- build_event_impact_prompt     — event_impact_analysis (新聞衝擊評估)
- build_macro_structured_prompt — analyze_macro_structured (總經六節)
"""
from __future__ import annotations


# ════════════════════════════════════════════════════════════
# 1. analyze_global — 4 節結構（位階 / 配置 / 警示 / 待辦）
# ════════════════════════════════════════════════════════════
def build_global_prompt(snapshot: str, phase: str, alloc_str: str,
                        core_target_pct: int) -> str:
    """組合「全域投資建議」prompt。

    Args:
        snapshot: _build_snapshot() 輸出（含指標 / 持倉 / 新聞快照）
        phase: 當前景氣位階（如 "擴張中段"）
        alloc_str: 建議配置字串（如 "股票60% / 債券30% / 現金10%"）
        core_target_pct: 使用者目標核心配置 %
    """
    return f"""你是採用「策略3 以息養股」方法論的台灣財經顧問。
你必須輸出完整的 4 個段落，缺少任何一段都是錯誤。
⚠️ 嚴格規則：只能根據以下快照分析，禁止搜尋或引用任何外部資訊。

{snapshot}

═══════════════════════════════════════
請用繁體中文，依序輸出以下【全部4節】，每節用 ### 開頭標題：

### 📍 一、景氣位階判讀
- 當前位階：{phase}，說明評分與趨勢方向
- 主要依據：列出3個關鍵指標數值與解讀
- 拐點觸發條件：何時需要調整配置？

### ⚖️ 二、資產配置建議
- 當前建議：{alloc_str}
- 你的目標：核心{core_target_pct}% / 衛星{100-core_target_pct}%
- 轉換位階後，如何調整？（給具體%數字）

### 🔴 三、持倉警示
每檔基金一行，格式：[基金名] → 🔴減碼/🟡持有/🟢加碼 [一句理由]
（必須涵蓋吃本金、NAV位置偏高、低Sharpe等問題）

### 🔄 四、本週操作待辦清單
請用 Markdown checkbox 格式輸出3-5個具體行動項目：
- [ ] 哪檔需要減碼？減多少？轉入什麼？
- [ ] 哪檔接近-1σ買點，等待加碼？
- [ ] 有無吃本金基金需要處理？
- [ ] 每月定期扣款是否繼續執行？
═══════════════════════════════════════
【必須輸出完整4節，不可提前結束。第四節必須使用 - [ ] checkbox 格式】"""


# ════════════════════════════════════════════════════════════
# 2. analyze_fund_json — 單檔基金 4 節（位階 × 類別 / 體質 / 買賣點 / 待辦）
# ════════════════════════════════════════════════════════════
def build_fund_json_prompt(*, fund_name: str, category: str, currency: str,
                           nav, pos: str, sigma_alert: str,
                           buy1, buy2, sell1,
                           adr: float, tr1y, std, sharpe, sharpe_comment: str,
                           maxdd, mgmt_fee, pf: dict,
                           phase: str, score, alloc_s: str, phase_rec: str,
                           eating: bool, tone_directive: str,
                           holdings_text: str = "",
                           news_text: str = "") -> str:
    """組合「單檔基金深度分析」prompt（v18.135：4 節 → 5 節，新增「持股 × 新聞影響」）。

    所有數值參數以 caller 預先 format 過的型態傳入（None → "N/A" 在此處 fallback）。
    v18.135：holdings_text + news_text 可選；若都空則第五節要求 AI 標示「資料不足」。
    """
    _has_holdings = bool(holdings_text.strip())
    _has_news = bool(news_text.strip())
    _section5_block = ""
    if _has_holdings or _has_news:
        _section5_block = f"""
【持股 × 新聞 (用於第四節交叉分析)】
{(holdings_text or '  （無持股資料）')}

{(news_text or '  （無近期新聞）')}"""
    # 避免 f-string 內 backslash — 提前 build 第四節指令
    if _has_holdings or _has_news:
        _section4_directive = (
            "**必須對上方【持股 × 新聞】資料逐條交叉**：\n"
            "- 點名 2-3 檔具體持股（用持股名稱），分析該標的是否被近期新聞**直接衝擊**\n"
            "  （例：Fed 升息利空科技股、地緣政治衝擊半導體供應鏈）\n"
            "- 評估「如果繼續長期持有」這幾檔，未來 6-12 個月最大可能損益情境\n"
            "- 給出「該標的減碼/觀察/持有」具體建議，並指明觸發條件"
        )
    else:
        _section4_directive = "- ⚠️ 持股或新聞資料不足，本節暫無法分析。建議重新抓取基金資料 + 載入新聞後重試。"
    return f"""你是整合「策略1 以息養股」與「策略2 基金績效評估」方法論的台灣基金教練。
{tone_directive}
⚠️ 嚴格規則：只能根據以下快照分析，禁止引用外部資訊，禁止杜撰數字。

【基金快照】
基金名稱：{fund_name}  類別：{category}  計價幣：{currency}
目前 NAV：{nav}  位階：{pos}  {sigma_alert or '（NAV 在正常區間）'}
買1（年低+σ）：{buy1}  買2（年低）：{buy2}  停利（年高-σ）：{sell1}
配息年化率：{adr:.1f}%  含息 TR1Y：{tr1y if tr1y is not None else 'N/A'}%  {'🔴吃本金警報' if eating else '✅ 含息報酬健康'}
標準差(1Y)：{std}%  Sharpe(1Y)：{sharpe}（{sharpe_comment}）
最大回撤：{maxdd}%  管理費/內扣費：{mgmt_fee}
績效：1M={pf.get('1M','N/A')}%  3M={pf.get('3M','N/A')}%  1Y={pf.get('1Y','N/A')}%  3Y={pf.get('3Y','N/A')}%  5Y={pf.get('5Y','N/A')}%

【總經位階】{phase}（{score}/10）建議配置：{alloc_s}
此階段適合基金類型：{phase_rec}
{_section5_block}
═══════════════════════════════════════════
請用繁體中文完整輸出以下【五節】，每節用 ### 開頭標題：

### 🌡️ 一、景氣位階 × 基金類別建議
- 當前「{phase}」位階，最有利的基金類型為何？給出明確類別名稱
- 這檔「{category}」基金在此位階的合理性：適合 / 偏多 / 偏保守？
- 教練建議：維持持有 / 轉換類別 / 增加哪類補充標的（一句話結論）

### 🩺 二、基金體質診斷
{'- 🔴 **吃本金警報**：配息率（' + f'{adr:.1f}' + '%）高於含息 TR1Y（' + str(tr1y or 0) + '%）。策略1 警示：高配息不等於高報酬，本金失血要當心！' if eating else '- ✅ 配息安全：含息報酬高於配息率，資產未失血'}
- Sharpe 持久性評語：{sharpe}（{sharpe_comment}）
- 最大回撤 {maxdd}% 說明經理人抗跌能力評估
- 費用率 {mgmt_fee}：與同類型基金相比是否具競爭力？（0.5%以下低成本）

### 📍 三、量化買賣點分析
{sigma_alert if sigma_alert else '- 目前 NAV 處於正常區間，非極端買賣點'}
- 第一買點 {buy1}（年低+σ）：距離當前 NAV 尚有空間嗎？
- 第二買點 {buy2}（年低，歷史超跌區）：觸及時建議單筆大買
- 停利點 {sell1}（年高-σ）：是否接近，需要準備減碼？
- 策略1 心法：依位置給出「定期定額持續」或「單筆等回調」具體建議

### 💎 四、持股 × 新聞影響評估（v18.135 新增）
{_section4_directive}

### 🔄 五、本週操作待辦清單
請輸出 3-5 個 Markdown Checkbox：
- [ ] 具體行動（含觸發條件或目標數字）
- [ ] 最後一項必須是「本週核心原則」一句話
═══════════════════════════════════════════
【必須完整輸出五節，每節至少 2 個要點，第五節必須含 Checkbox 格式】"""


# ════════════════════════════════════════════════════════════
# 2b. analyze_fund_json — JSON 結構化版本（AI-4 v18.114）
# ════════════════════════════════════════════════════════════
def build_fund_json_structured_prompt(*, fund_name: str, category: str, currency: str,
                                       nav, pos: str, sigma_alert: str,
                                       buy1, buy2, sell1,
                                       adr: float, tr1y, std, sharpe, sharpe_comment: str,
                                       maxdd, mgmt_fee, pf: dict,
                                       phase: str, score, alloc_s: str, phase_rec: str,
                                       eating: bool, tone_directive: str,
                                       schema_hint: str,
                                       holdings_text: str = "",
                                       news_text: str = "") -> str:
    """build_fund_json_prompt 的 JSON 結構化版本（v18.135：4→5 節）。

    schema_hint: 由 caller 從 services.ai_models.FUND_JSON_SCHEMA_HINT 傳入。
    holdings_text / news_text: 持股 + 新聞快照（v18.135 新增交叉分析用）
    """
    eating_msg = (
        f"⚠️ 吃本金警報：配息率 {adr:.1f}% 高於含息 TR1Y {tr1y or 0}%（本金失血）"
        if eating else
        "✅ 配息安全：含息報酬高於配息率"
    )
    sigma_msg = sigma_alert or "目前 NAV 處於正常區間，非極端買賣點"
    _has_data = bool(holdings_text.strip() or news_text.strip())
    _section5_block = (f"""

【持股 × 新聞 (供第四節交叉分析)】
{(holdings_text or '  （無持股資料）')}

{(news_text or '  （無近期新聞）')}""" if _has_data else "")
    return f"""你是整合「策略1 以息養股」與「策略2 基金績效評估」方法論的台灣基金教練。
{tone_directive}
⚠️ 嚴格規則：只能根據以下快照分析，禁止引用外部資訊，禁止杜撰數字。

【基金快照】
基金名稱：{fund_name}  類別：{category}  計價幣：{currency}
目前 NAV：{nav}  位階：{pos}  {sigma_msg}
買1（年低+σ）：{buy1}  買2（年低）：{buy2}  停利（年高-σ）：{sell1}
配息年化率：{adr:.1f}%  含息 TR1Y：{tr1y if tr1y is not None else 'N/A'}%
{eating_msg}
標準差(1Y)：{std}%  Sharpe(1Y)：{sharpe}（{sharpe_comment}）
最大回撤：{maxdd}%  管理費/內扣費：{mgmt_fee}
績效：1M={pf.get('1M','N/A')}%  3M={pf.get('3M','N/A')}%  1Y={pf.get('1Y','N/A')}%  3Y={pf.get('3Y','N/A')}%  5Y={pf.get('5Y','N/A')}%

【總經位階】{phase}（{score}/10）建議配置：{alloc_s}
此階段適合基金類型：{phase_rec}
{_section5_block}
═══════════════════════════════════════════
{schema_hint}

【內容指引】
- 第一節「景氣位階 × 基金類別建議」：當前「{phase}」位階下這檔「{category}」是否合理 / 維持或轉換
- 第二節「基金體質診斷」：{'吃本金警報、' if eating else ''}Sharpe 評語、最大回撤、費用率
- 第三節「量化買賣點分析」：距離買1/買2/停利點的相對位置、策略1 心法
- 第四節「持股 × 新聞影響評估」（v18.135 新增）：{(
    "點名 2-3 檔具體持股 + 對應近期新聞 → 評估「繼續長期持有」未來 6-12 個月可能損益情境 → 給出減碼/觀察/持有建議"
) if _has_data else "若持股或新聞資料不足，本節輸出「資料不足，建議重抓基金資料」"}
- 第五節「本週操作待辦清單」：3-5 條具體行動，最後一條必須是本週核心原則總結"""


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
# 4. event_impact_analysis — 新聞衝擊評估（短回應）
# ════════════════════════════════════════════════════════════
def build_event_impact_prompt(*, fund_ctx: str, headlines: list[str],
                              holdings_ctx: str) -> str:
    """組合「事件衝擊評估」prompt（簡短，≤200 字）。"""
    nl = chr(10)   # 字串內插不能放 backslash
    return f"""你是一位機構級基金風險分析師。{fund_ctx}
⚠️ 嚴格規則：只根據以下提供的新聞標題和持股資訊分析，禁止杜撰或引用外部資訊。

[近期市場新聞標題]
{nl.join(f'• {h}' for h in headlines)}
{holdings_ctx}

請完成以下分析（如無顯著衝擊事件，直接回覆「⚪ 無重大事件衝擊」即可）：

### ⚠️ 事件衝擊評估
1. 哪些新聞事件對基金底層持股有直接衝擊？（點名具體標題）
2. 衝擊程度：🔴高 / 🟡中 / 🟢低，並說明理由
3. 建議立即關注的風險點（1-2 條）

【輸出必須簡短，整體不超過 200 字】"""


# ════════════════════════════════════════════════════════════
# 5. analyze_macro_structured — 總經六節（新手 + 老手雙軌）
# ════════════════════════════════════════════════════════════
def build_macro_structured_prompt(*, snapshot: str, stale_note: str) -> str:
    """組合「總經結構化六節」prompt（位階 / 配置 / 警示 / 新手 / 老手 / 待辦）。"""
    return f"""你是一位精通景氣循環、「策略3 以息養股」方法論的台灣財經分析師。
⚠️ 嚴格規則：只能根據以下快照分析，禁止搜尋或引用任何外部資訊，禁止杜撰數字。

{snapshot}{stale_note}

═══════════════════════════════════════════
請用繁體中文輸出以下【完整六節】，必須依序且每節使用 ### 開頭標題：

### 📍 一、景氣位階判讀
- 2-3 句話總結當前位階核心特徵
- 引用快照中至少 3 個指標數值（含單位）
- 說明殖利率利差（10Y-2Y）當前訊號意義

### ⚖️ 二、資產配置建議
- 核心/衛星建議佔比（%）與調整方向
- 整合系統性風險評級（LOW/MEDIUM/HIGH）說明是否影響配置

### 🔴 三、持倉警示
- 列出 2-3 個具體風險觸發條件（含數字臨界值）
- 若新聞無高危信號，明確說明「新聞面暫無系統性警示」

### 🟢 四、新手行動指引（白話版）
- 用天氣/溫度比喻說明現在適不適合進場（禁止使用 Z-Score 等術語）
- 一個具體的行動建議（例：每月繼續定期扣款 / 暫停加碼）
- 常見新手錯誤提醒（1 條）

### 📐 五、老手量化推演（進階版）
- 列出 2 個 Z-Score 關鍵數值與交易意義
- σ 位階判斷：若有 HWM 資訊，說明現在距離 HWM 幾個 σ
- 乖離率與均值回歸預估（若資料充足）
- **必引用**：若快照含 [Phase 4 領先指標排名]，點出前 2 名 driver 名稱 + 同/反向 + corr 強度
- **必引用**：若快照含 [Phase 3-B 子領域燈號歷史回測]，挑出至少 1 個「✅紅燈領先衰退」的子領域或「⚠️訊號弱」的子領域並解釋意義

### 🌐 六、跨領域綜合判讀（v18.120 新增）
**必須串連快照中的所有資料**，整合下列來源給出**統一結論**（不可遺漏）：
- [景氣位階] 當前 phase + score
- [量化指標] 至少 3 個關鍵指標數值
- [7 子領域當下燈號] 哪幾個亮 🔴/🟠 警示？哪幾個 🟢/🟡 健康？
- [Phase 4 領先指標排名] 前 3 名 driver 共同指向什麼方向？
- [Phase 3-B 子領域燈號歷史回測] 歷史紅燈是否確實領先衰退？
- [新聞] 系統性風險事件是否與上述量化訊號相印證？
- 結尾用一句話總結：「目前處於 X 階段，建議偏向 Y 操作」

### 🔄 七、本週操作待辦清單
- Markdown Checkbox 格式，4-6 項具體行動：
  - [ ] 行動描述（含觸發條件或目標數字）
- 最後一項必須是「本週核心操作原則」一句話總結
═══════════════════════════════════════════
【必須輸出完整七節，不可提前結束，第七節必須含 Checkbox】
【嚴格規則】只能引用快照內資料（含 7 子領域當下燈號、Phase 4 driver 排名、
            Phase 3-B 燈號回測、新聞）；禁止編造未提及的基金 / 數字 / 統計結論。"""
