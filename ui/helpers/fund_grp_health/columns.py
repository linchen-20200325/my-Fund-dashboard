"""ui/helpers/fund_grp_health/columns.py — 健診大表 / 批次大表**共用** column_config SSOT。

問題(2026-08-06 稽核 🔴 必修 4):組合健診大表(Tab②)有一份 40+ 欄的
`TextColumn(width=)` + `help=` 設定;**批次大表(Tab③)用同一組欄位卻裸 render**
(`st.dataframe(df, ...)` 無 column_config)—— 48 個中文欄名全無 tooltip,而最長的
「備註」欄放的是**唯一的失敗原因揭露**(§1),實測會被截斷且不換行,使用者看到
「NameResolut…」無從判斷該不該按「🔁 重試失敗檔」。

本模組把設定抽成純函式,兩張表同源:
- `base_column_config()`      ③ 實際購買結果(持有 meta / 全期實際·年化 %)
- `health_column_config()`    ① 健康分析 + σ/捕捉/換標/景氣/匯率(原 `_health_cfg`)
- `dividend_column_config()`  ② 配息相關(原 `_div_cfg`)
- `extra_column_config()`     σ位階 / MK 買賣點 / 風險對比等原本**沒有** cfg 的欄
- `batch_column_config()`     批次專屬:狀態 / 備註 / 淨值日期 / 淨值新鮮度
- `unified_column_config(batch=)` 以上合併(dict 後者覆蓋前者)

⚠️ 只放「顯示設定」,不含任何門檻運算 —— help 字串裡的數字一律從
`shared/*` SSOT import 進來格式化,禁止寫死(§3.3)。
"""
from __future__ import annotations


def _cc():
    from streamlit import column_config
    return column_config


def base_column_config() -> dict:
    """③ 實際購買結果欄(原 `tab_fund_grp_health._render_health_table` 內的 `_col_cfg`)。"""
    cc = _cc()
    return {
        "code": cc.TextColumn("代號", width="small"),
        "基金名": cc.TextColumn("基金名", width="medium"),
        "ccy": cc.TextColumn("幣別", width="small",
            help="MoneyDJ wb05「計價幣別」正規化後的 ISO 代碼;抓不到 → 該檔整列失敗(不矇 USD)。"),
        "幣別偵測": cc.TextColumn("幣別偵測", width="small",
            help="自動 = 由 MoneyDJ 計價幣別欄判定(目前唯一路徑,無人工 fallback)。"),
        "fx_spot": cc.NumberColumn("FX", format="%.4f", width="small",
            help="1 原幣 = ? TWD(即期)。台幣計價固定 1.0000。"),
        "principal_ccy 🧮": cc.NumberColumn("原幣本金 🧮", format="%,.0f",
            help="本金 TWD ÷ 買進日匯率 = 原幣本金。🧮 = 本站換算,非官方欄位。"),
        "units 🧮": cc.NumberColumn("單位 🧮", format="%,.2f",
            help="原幣本金 ÷ 買進日 NAV = 持有單位數。"),
        "配息次數": cc.NumberColumn("配息次數", format="%d", width="small",
            help="買進日之後、MoneyDJ 有記錄的除息次數(不是每年幾次)。"),
        "累積 TWD 配息 🧮": cc.NumberColumn("累積 TWD 配息 🧮", format="%,.0f",
            help="各次配息 × 持有單位 × 當期匯率 加總。"),
        "年均配息 TWD 🧮": cc.NumberColumn("年均配息 TWD 🧮", format="%,.0f",
            help="累積 TWD 配息 ÷ 持有年數。"),
        # v19.180:全期實際(不年化,短歷史也顯示真實累計值)
        "配息率% (全期實際)": cc.NumberColumn(
            "配息率% (全期實際)", format="%.2f %%",
            help="自買進日起累積配息 / 本金 × 100(不年化)。短歷史也顯示真實累計。verdict 不採。"),
        "淨值% (全期實際)": cc.NumberColumn(
            "淨值% (全期實際)", format="%.2f %%",
            help="自買進日起累積淨值漲跌幅(不年化)。短歷史也顯示真實累計。verdict 不採。"),
        "含息% (全期實際)": cc.NumberColumn(
            "含息% (全期實際)", format="%.2f %%",
            help="全期實際淨值% + 全期實際配息%(不年化)。短歷史也顯示真實累計。verdict 不採。"),
        # v19.148/v19.180:年化 3 軸(< 0.5 年顯示 None,避免幻象);verdict 仍走 1Y MK SSOT
        "配息率% (年化)": cc.NumberColumn(
            "配息率% (年化·對買進成本)", format="%.2f %%",
            help="(累積配息 / **買進時本金** / 持有年數)× 100。需持有 ≥ 0.5 年。"
                 "⚠️ 與「年化配息率 %」欄**分母不同**:本欄除的是買進成本,"
                 "那一欄(MoneyDJ wb05)除的是**現價**。verdict 不採。"),
        "淨值% (年化)": cc.NumberColumn(
            "淨值% (年化)", format="%.2f %%",
            help="累積淨值變化 / 持有年數。需持有 ≥ 0.5 年。verdict 不採。"),
        "含息% (年化)": cc.NumberColumn(
            "含息% (年化)", format="%.2f %%",
            help="年化淨值% + 年化配息%。需持有 ≥ 0.5 年。verdict 不採。"),
        "吃本金燈號 (1Y · MK)": cc.TextColumn(
            "吃本金燈號 (1Y · MK)", width="medium",
            help="MK 老師 1Y 體檢:近一年含息報酬 vs MoneyDJ wb05 年化配息率。"
                 "與下方「健診摘要表」同源 SSOT。"),
        # v19.153:MK 3-3-3 原則(長線核心資產輔助)
        "MK 3-3-3 篩": cc.TextColumn(
            "MK 3-3-3 篩", width="medium",
            help="MK 老師 3-3-3 長線挑核心資產篩選:成立 ≥ 3 年 + 過去 3 年平均年化報酬 > 7%。"
                 "✅ 通過 / ❌ 未通過(**有明確反證**)/ ⬜ 資料不足(缺成立年數或缺 3 年年化)。"
                 "3 年平均年化由 metrics.ret_3y(累計)用 (1+R)^(1/3)-1 換算。"
                 "本欄為長線輔助,非吃本金主判定。"),
        "MK 倉位": cc.TextColumn("MK 倉位", width="small",
            help="MoneyDJ metrics 的倉位標籤(pos_label)直出,不重算。"),
        "最高經理費%": cc.TextColumn("最高經理費%", width="small",
            help="MoneyDJ 公開說明書揭露的經理費上限字串,原樣顯示(不轉數值以免誤讀區間值)。"),
        "配息頻率": cc.TextColumn("配息頻率", width="small",
            help="優先用 metrics.div_freq_n(月/季/半年/年配);缺 → MoneyDJ 原始字串。"),
        "換匯資訊 🧮": cc.TextColumn("換匯資訊 🧮", width="medium",
            help="買進當下 100 萬 TWD 換到多少原幣、用哪個匯率(§4.1 跨幣別可追溯)。"),
    }


def health_column_config() -> dict:
    """① 健康分析 + σ 捕捉 / 換標 / 景氣 / 匯率欄(原 `_health_cfg`)。"""
    cc = _cc()
    from shared.signal_thresholds import (  # v19.419 捕捉率 help 文字用(SSOT,非 magic)
        CAPTURE_MIN_MONTHS as _CAP_MIN,
        CAPTURE_ROBUST_MONTHS as _CAP_ROB,
    )
    # 換標策略分 help 文字用的綠燈門檻(SSOT,不在 help 字串寫死,§3.3)
    from shared.switch_thresholds import SWITCH_GREEN_SCORE as _SW_GREEN
    # Sharpe 自算樣本門檻(help 文字要照實說「自算需 ≥ N 筆」,不寫死數字)
    from services.fund_service import MIN_OBS_SHARPE_SORTINO as _MIN_SS
    return {
        "code": cc.TextColumn("代號", width="small"),
        "基金名": cc.TextColumn("基金名", width="medium"),
        # v19.327:核心/衛星資產分類(類別 + MK 3-3-3 兩層,見「分類依據」欄)
        "基金類別": cc.TextColumn("基金類別", width="small",
            help="MoneyDJ 投資標的 / 基金類型原始值(核心/衛星判定依據)"),
        "核心/衛星": cc.TextColumn("核心/衛星", width="small",
            help="🟦 核心=廣泛分散/穩健長線(可重壓);🟠 衛星=集中/主題/高波動(小部位);"
                 "⬜ 待定=類別+3-3-3 皆無法判定"),
        "分類依據": cc.TextColumn("分類依據", width="small",
            help="類別=依基金類型;3-3-3=通過 MK 3-3-3 達核心標準;—=資料不足"),
        "4D Grade": cc.TextColumn("4D Grade", width="small",
            help="A≥80 / B≥65 / C≥50 / D≥35 / F<35(SSOT v19.177)"),
        "4D Score": cc.NumberColumn("4D Score", format="%.1f", width="small",
            help="4 維(報酬 / 配息覆蓋 / Sharpe / σ)加權 0-100。缺維度 → 留白,不以 0 充數。"),
        # ⚠️ 原 help 斷言「自計算(NAV 序列);**非** MoneyDJ 公布值」—— 與事實相反:
        #    `services/fund_service.py` 的 `_sharpe_out` 優先序是
        #    **wb07 一年 > wb07 六個月 > 本地自算**,只要 MoneyDJ wb07 有值(境外基金常態)
        #    這欄顯示的就是官方公布值;wb07 **六個月**命中時欄名還寫死「1Y」。
        #    → 標籤去掉硬掛的 1Y,期間/來源改由旁邊的「Sharpe 來源」欄逐檔照實顯示。
        "Sharpe 1Y": cc.NumberColumn("Sharpe", format="%.2f",
            help=("來源優先序:**MoneyDJ wb07 官方一年 > wb07 官方六個月 > 本地自算**"
                  f"(自算需 NAV ≥ {_MIN_SS} 筆)。逐檔實際來源見右邊「Sharpe 來源」欄。"
                  "⚠️ 同一欄可能**混不同期間**(wb07 六個月不是 1Y),跨檔比大小前請先看來源;"
                  "4D 評分與換標策略分皆吃此值。")),
        "Sharpe 來源": cc.TextColumn("Sharpe 來源", width="small",
            help=("此列 Sharpe 的**實際**來源與期間(§2.2 血緣):wb07 1Y(官方)/ "
                  "⚠️ wb07 6M(非1Y,期間比別檔短)/ 自算 Nd(本地 NAV 序列)/ ⬜ —(無值)。"
                  "本欄由 calc_metrics 的 risk_metric_meta 直出,不重算。")),
        "Sortino": cc.NumberColumn("Sortino", format="%.2f",
            help="下檔波動版 Sharpe(只罰下跌波動)。缺 → 留白。"),
        "Calmar": cc.NumberColumn("Calmar", format="%.2f",
            help="年化報酬 ÷ |最大回撤|。越高 = 每承受 1 單位回撤換到越多報酬。"),
        "Alpha %": cc.NumberColumn("真實收益 %", format="%.2f %%",
            help="含息報酬率 − 年化配息率（≠ CAPM Alpha）"),
        "費用率 %": cc.NumberColumn("費用率 %", format="%.2f %%",
            help="MoneyDJ 揭露的總費用率;缺則退回經理費。越低越好。"),
        "Max DD %": cc.NumberColumn("Max DD %", format="%.2f %%",
            help="期間最大回撤(負值)。NAV 序列太短算不出 → 留白,換標策略分會退出分母。"),
        "3Y 年化 %": cc.NumberColumn("3Y 年化 %", format="%.2f %%",
            help="三年平均年化報酬。metrics 缺 → 由 wb01 三年期累計開立方根換算。"
                 "MK 3-3-3 篩吃此值,抓不到時 3-3-3 顯示 ⬜(不判 ❌)。"),
        "5Y 年化 %": cc.NumberColumn("5Y 年化 %", format="%.2f %%",
            help="五年平均年化報酬(metrics 缺 → wb01 五年期累計換算)。"),
        "MK 3-3-3": cc.TextColumn("MK 3-3-3", width="medium",
            help="成立 ≥ 3 年 + 過去 3 年平均年化 > 7% → 通過"),
        # v19.414 經理人操作能力;v19.419 放寬門檻 6→3(help 註明參考值,§1 誠實)
        "上檔捕捉%": cc.NumberColumn("上檔捕捉%", format="%.1f %%",
            help=("大盤上漲月:基金複利 / 大盤複利 × 100(越高 = 越追得上漲)。"
                  f"需漲、跌月各 ≥ {_CAP_MIN} 才算;{_CAP_MIN}–{_CAP_ROB - 1} 月為參考值。")),
        "下檔捕捉%": cc.NumberColumn("下檔捕捉%", format="%.1f %%",
            help="大盤下跌月:基金複利 / 大盤複利 × 100(越低 = 越抗跌)。"),
        "操盤評分": cc.NumberColumn("操盤評分", format="%d",
            help=("經理人操作評分 clamp(50 +(上檔 − 下檔)/2, 0, 100)。"
                  f"需漲、跌月各 ≥ {_CAP_MIN};{_CAP_MIN}–{_CAP_ROB - 1} 月為參考值(低信心)。"
                  "**跨檔比大小前務必先看右邊「捕捉樣本」欄** —— 3 個跌月的 92 分"
                  "與 40 個跌月的 92 分在本欄長得一模一樣。")),
        # 捕捉率樣本旗標(§1 第 3 項:低信心必須逐列可見,不能只寫在欄位 help)
        "捕捉樣本": cc.TextColumn("捕捉樣本", width="small",
            help=(f"上/下檔捕捉率與操盤評分的**實際樣本月數**:✅ = 漲跌月皆 ≥ {_CAP_ROB}(穩健);"
                  f"⚠️ = 有一邊只有 {_CAP_MIN}–{_CAP_ROB - 1} 月(參考值,雜訊大);"
                  f"⬜ = 月數不足 {_CAP_MIN} 或缺基準 → 左邊三欄留白。")),
        # v19.420 vs 大盤%(近1Y純價格報酬差;純淨值對純指數,公平不含息)
        "vs 大盤%": cc.NumberColumn("vs 大盤%", format="%+.1f %%",
            help=("近 1 年**純價格**報酬 − 大盤(TWD→台股 / USD→S&P500)。"
                  "正 = 跑贏。純淨值對純指數(公平,兩邊都不含息)。"
                  "⚠️ **非 TWD / USD 計價的基金一律留白** —— 原幣報酬減 USD 指數報酬"
                  "等於把匯率變動算成經理人績效(§4.1 跨幣別),寧可不給也不給錯。"
                  "共同歷史不足 1 年 → 改用全期,見右邊「vs 大盤期間」欄。")),
        "vs 大盤期間": cc.TextColumn("vs 大盤期間", width="small",
            help=("左欄 vs 大盤% 實際量測的窗口:近 1 年 / ⚠️ 全期(共同歷史不足 1 年,"
                  "**跨檔不可比**,3 個月的 +14% 與整年的 +14% 不是同一件事)/ ⬜ 無(留白)。")),
        # v19.421 基期標籤(由 σ rank 分類,一眼挑高/低基期標的;門檻同輪動配對)
        "基期": cc.TextColumn("基期", width="small",
            help=("現價 vs 期間高點的 σ 位階:🔴 高基期(σ ≥ −0.5,貼近高點、偏貴)/ "
                  "⚪ 中性 / 🟢 低基期(σ ≤ −1.5,跌深、可能均值回歸)/ ⬜ 資料不足。"
                  "⚠️ 與上方「🎯 選基金(低基期)」篩選器**不是同一套定義**:那邊 σ 為"
                  "**正數深度**且倍數可調(1/2σ),本欄是**負數 σ rank** 且固定 −1.5σ,"
                  "同一檔可能一邊 ✅ 一邊 ⚪。NAV 完全不動(停售)→ ⬜,不判高基期。"
                  "可點欄排序,一次挑出所有高基期或低基期標的。")),
        # v19.423 換標決策(策略燈號 + 策略分;獨立於 4D,專為買賣/換標設計)
        "策略燈號": cc.TextColumn("策略燈號", width="small",
            help=("換標燈號:🔴 賣出/平轉(1Y含息<0 且 Sharpe<0,或 嚴重吃本金)/ 🟡 觀望 / "
                  f"🟢 續抱加碼(分≥{_SW_GREEN} 且 吃本金健康**且四維證據夠**)/ ⬜ 資料不足。"
                  "⚠️ 缺 MaxDD / vs大盤 時,**缺的維度全以 0 計仍要 ≥ "
                  f"{_SW_GREEN}** 才給綠燈 —— 證據不全一律降 🟡,不給加碼訊號(§1)。"
                  "可篩選一次挑出所有紅燈檔。")),
        "換標策略分": cc.NumberColumn("換標策略分", format="%d",
            help=("滿覆蓋時 = 1Y含息35 + Sharpe30 + MaxDD20 + vs大盤15 = 0-100。"
                  "⚠️ **分母不是固定 100**:缺 MaxDD(NAV 太短算不出)或 vs大盤 時,該維"
                  "**退出分母**後放回 0-100(缺值≠壞值),所以 100 分可能只代表"
                  "「有證據的 65 分裡拿滿 65」—— 實際分母/缺哪幾維請看右邊「策略分覆蓋」欄。"
                  "**獨立於 4D 健康度**;缺 Sharpe/含息 → 留白(灰燈)。")),
        "策略分覆蓋": cc.TextColumn("策略分覆蓋", width="medium",
            help=("換標策略分的**證據覆蓋率**(§1 缺值須帶旗標):✅ 100/100 = 四維齊全;"
                  "⚠️ 65/100(缺 …) = 分母被收斂,分數只反映有證據的部分,跨檔比大小要小心;"
                  "`·不給綠燈` = 缺的維度即使全拿 0 也跨不過綠燈門檻 → 燈號已強制降 🟡;"
                  "⬜ 未評分 = 核心維度(1Y含息/Sharpe)缺。")),
        # v19.425 景氣適配(依資產屬性+捕捉對照當前景氣;參考傾向非買賣建議)
        "景氣適配": cc.TextColumn("景氣適配", width="small",
            help=("依資產類別 + 抗跌/追漲能力,對照**當前景氣位階**(頁首 Phase):✅ 順風 / "
                  "⚠️ 逆風 / ⚪ 全景氣(核心/平衡)/ ⬜ 無法判定(缺類別或景氣未偵測)。"
                  "**參考傾向,非買賣建議、非 % 配置**。")),
        "適配傾向": cc.TextColumn("適配傾向", width="small",
            help="此基金資產屬性最適合的景氣位階(復甦/擴張/高峰/衰退;全景氣=平衡多重)。"),
        # v19.426 淨值×匯率二維買賣切換(外幣基金;台幣計價 ➖)
        "匯率位階": cc.TextColumn("匯率位階", width="small",
            help=("USDTWD 現值相對**近一年均值**的位階(z-score):台幣強(換匯便宜,進場有利)/ "
                  "中性 / 台幣弱(換回台幣划算,出場有利)。`*` = 樣本較短僅供參考。"
                  "➖ 台幣計價 / ⬜ 無法判定(非美元或缺料)。**參考傾向,非擇時保證**。")),
        "淨值×匯率": cc.TextColumn("淨值×匯率", width="medium",
            help=("淨值位階 × 匯率位階 二維買賣:🟢 雙便宜(淨值低+台幣強=進場佳)/ "
                  "🔴 雙貴(淨值高+台幣弱=出場佳)/ ⚪ 觀望(一好一壞或中性)。"
                  "➖ 台幣計價 / ⬜ 無法判定。匯率比淨值難預測 —— **非買賣建議**。")),
    }


def dividend_column_config() -> dict:
    """② 配息相關欄(原 `_div_cfg`)。"""
    cc = _cc()
    return {
        "code": cc.TextColumn("代號", width="small"),
        "基金名": cc.TextColumn("基金名", width="medium"),
        "1Y 含息 %": cc.NumberColumn("1Y 含息 %", format="%.2f %%",
            help="近一年含息總報酬(淨值變化 + 配息)。來源見右邊「1Y 來源」欄。"),
        "1Y 來源": cc.TextColumn("1Y 來源", width="small",
            help="wb01 / local_calc / ret_1y_total / NAV 年化"),
        "年化配息率 %": cc.NumberColumn("年化配息率 %", format="%.2f %%",
            help="MoneyDJ wb05 年化配息率(分母為**現價**)。"
                 "⚠️ 與「配息率% (年化)」欄分母不同,那欄除的是買進成本。"),
        # v19.326:每月配息金額(TWD 現金)= 最近一筆實配 × 持有單位 × 匯率(來源同「配息來源」欄)
        "每月配息 (TWD)": cc.NumberColumn("每月配息 (TWD)", format="%.0f",
            help="每月實領台幣現金 = 最近一筆實際配息 × 持有單位 × 匯率。"
                 "健診 Tab 全檔以 100 萬 TWD 為基準;Tab3 為各檔實際投入本金。"),
        # v19.324:每月配息單位數 = 最近一筆實際配息 × 持有單位 / NAV(真實記錄優先)
        # v19.325:真實記錄缺 → 年化配息率估算 fallback,「配息來源」欄註記真實/估算
        "每月配息單位數": cc.NumberColumn("每月配息單位數", format="%.2f",
            help="= 最近一筆實際配息(原幣/單位) × 持有單位 / NAV。"
                 "優先用 MoneyDJ 真實配息記錄;缺則以年化配息率估算(見「配息來源」欄)。"
                 "健診 Tab 全檔以 100 萬 TWD 為基準比較;Tab3 為各檔實際投入本金。"),
        "配息來源": cc.TextColumn("配息來源", width="small",
            help="真實=最近一筆實際配息記錄;估算=年化配息率÷12 攤平(季配/年配某些月實際為 0)"),
        "吃本金燈號 (1Y·MK)": cc.TextColumn("吃本金燈號 (1Y·MK)", width="medium"),
        "換標的建議": cc.TextColumn("換標的建議", width="medium",
            help="MK 4 規則綜合判定(hover 看細節)"),
    }


def extra_column_config() -> dict:
    """σ 位階 / 風險對比 / MK 買賣點欄 —— 原本**完全沒有** column_config 的一批。

    值皆為 by-code data 函式預先格式化好的**字串**(缺 → '—'),故一律 TextColumn。
    """
    cc = _cc()
    return {
        "現價": cc.TextColumn("現價", width="small",
            help="最新一筆 NAV(原幣)。"),
        "HWM": cc.TextColumn("HWM", width="small",
            help="過去 252 交易日的歷史最高 NAV(High Water Mark)。"),
        "距 HWM %": cc.TextColumn("距 HWM %", width="small",
            help="(現價 − HWM) / HWM × 100。負值 = 目前在高點下方。"),
        "σ rank": cc.TextColumn("σ rank", width="small",
            help="現價在 HWM 下方第幾個 σ(負值愈深愈跌深)。"
                 "NAV 完全不動(停售/清算)→ '—',**不回 0**(0 會被誤判成貼近高點)。"),
        "HWM 位階": cc.TextColumn("HWM 位階", width="medium",
            help="σ rank 的文字帶:接近 HWM / −1σ 觀察 / −2σ 加碼參考 / −3σ+ 深度超跌;"
                 "⬜ 開頭 = 算不出來(NAV 不足 30 天 / 報酬序列不足 / NAV 無波動)。"),
        "σ (年化%)": cc.TextColumn("σ (年化%)", width="small",
            help="年化標準差。metrics 本地算優先,缺則取 MoneyDJ wb07 風險表。越低越穩。"),
        "Beta": cc.TextColumn("Beta", width="small",
            help="MoneyDJ wb07 風險表的 Beta(對其自訂基準),非本站重算。"),
        "資產屬性": cc.TextColumn("資產屬性", width="small",
            help="MK 買賣點模型對此檔的資產分類(股/債/平衡…),缺景氣位階時為 '—'。"),
        "操作訊號": cc.TextColumn("操作訊號", width="medium",
            help="MK 買賣點模型依**當前景氣位階**給的操作標籤;景氣未偵測 → '—'。"),
        "買 3 (深跌)": cc.TextColumn("買 3 (深跌)", width="small",
            help="MK 買賣點第 3 檔買進參考價(最深)。"),
        "買 1 (小跌)": cc.TextColumn("買 1 (小跌)", width="small",
            help="MK 買賣點第 1 檔買進參考價。"),
        "賣 1 (小漲)": cc.TextColumn("賣 1 (小漲)", width="small",
            help="MK 買賣點第 1 檔賣出參考價。"),
        "賣 3 (大漲)": cc.TextColumn("賣 3 (大漲)", width="small",
            help="MK 買賣點第 3 檔賣出參考價(最高)。"),
        "現價位階": cc.TextColumn("現價位階", width="medium",
            help="現價落在買 3 / 買 1 / 區間內 / 賣 1 / 賣 3 哪一段;缺 NAV → '—'。"),
    }


def batch_column_config() -> dict:
    """批次大表專屬欄:狀態 / 備註 / 淨值日期 / 淨值新鮮度。

    「備註」是**唯一的失敗原因揭露**(§1),必須給足寬度,否則
    「NameResolutionError…」被截成看不出是網路問題還是基金停售,
    使用者無從判斷該不該按「🔁 重試失敗檔」。
    """
    cc = _cc()
    return {
        "狀態": cc.TextColumn("狀態", width="small",
            help="✅ 成功 / ❌ 抓取失敗 / ⚠️ 無效代號。失敗檔仍完整留在表裡(數值留白,不填 0)。"),
        "備註": cc.TextColumn("備註", width="large",
            help="失敗原因原文(最多 100 字):例外類型 + 訊息。"
                 "連線 / DNS 類 → 可按「🔁 重試失敗檔」;"
                 "「NAV 抓不到」/「幣別未知」/ 403 類 → 多半是基金停售或子網域封鎖,重試通常無效。"),
        "淨值日期": cc.TextColumn("淨值日期", width="small",
            help="MoneyDJ 最新一筆淨值的日期(非抓取時間)。"),
        "淨值新鮮度": cc.TextColumn("淨值新鮮度", width="medium",
            help="今天(台北)− 淨值日期 的天數。🟢/🟠 = 正常(基金 NAV 為 T+1~T+3 公布,"
                 "週末假日不更新屬正常);🔴 = 明顯過期,**該檔很可能已停售 / 清算** —— "
                 "此時同一列的 σ rank / 操盤評分 / 策略燈號都是用死掉的 NAV 算出來的,勿當現況。"
                 "可點欄排序一次挑出所有 🔴。"),
    }


def unified_column_config(*, batch: bool = False) -> dict:
    """健診大表(batch=False)/ 批次大表(batch=True)的完整 column_config。

    合併順序:base(③)→ health(①)→ dividend(②)→ extra(σ/MK)→ batch 專屬。
    後者覆蓋前者;`code` / `基金名` 三份定義相同故無爭議。
    呼叫端仍需自行 `{k: v for k, v in cfg.items() if k in df.columns}` 過濾。
    """
    cfg = {
        **base_column_config(),
        **health_column_config(),
        **dividend_column_config(),
        **extra_column_config(),
    }
    if batch:
        cfg.update(batch_column_config())
    return cfg
