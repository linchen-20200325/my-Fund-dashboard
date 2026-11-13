# `calc_metrics` 1Y 估算路徑獨立驗證（客戶任務 2）

> **性質聲明**：本檔是**唯讀獨立驗證**，**不是客戶裁示、不修改任何公式或程式、不是授權施工**。
> 基準：origin/main `6dcb51f8dee3af7536211b3deda4676c3439ed56`（本機工作樹乾淨，`git status --short` 無輸出）。
> 作者：單組獨立驗證 AI（未參與撰寫 D2／先前稽核文件）；**尚待非作者 QA**。
> 先前發現 N1 出自 `docs/evidence/d2_contract_approval_prep_2026_11_12.md` §0 第 18 行與 `R-PERF-5` ④；本組先自己讀碼、實跑，再比對，**不把 N1 當前提**。
> 標記：CONFIRMED／PARTIAL／REFUTED／NOT VERIFIED。「總管讀法」＝可被客戶推翻。

---

## §0 結論（回答四個客戶問題）

1. **估算值與真實值可區分嗎？** 不可區分。`ret_1y_window_days` 是單一整數，量測值、估算值、`or 365` 預設值**同型、同鍵、無旗標**；解析器 `resolve_1y_total_return` 對三者給出**同一個** `status="ok"`／同一個標籤。估算分支甚至**連 stderr 都不印**（比 N1 說的更靜默）。
2. **日期窗口可能造成誤判嗎？** 有，但**主要風險不是 N1**。N1 的估算路徑在「日頻或更粗的日期索引」上**不可達**（實跑證實，見 §2）；真正可達、可重現的是**窗口無上界**：稀疏／長跨度序列會得到 `window_days`＝1757、1796 天仍判 `ok` 的「1Y 含息」（實跑 B1／B2）。
3. **違反 Missing≠0／估算必須標示嗎？** N1 的估算與 `or 365`：**若觸發，違反 CLAUDE.md §1 精神（估值未標示）；Missing≠0 字面不違反（沒有填 0）**；判為「灰色偏違反」，且**可達性目前無證據**。長窗無上界：**違反 1B「近一年」語意的標示**（屬已登記待裁的 BL-0427 (4)）。另發現三處 UI 直讀 `metrics.ret_1y_total` 繞過 350 天閘門（§1 補充 F-C；其中 `ui/tab5_data_guard.py` 診斷格僅 `perf["1Y"]` 缺值時的 fallback）。
4. **影響 New UI2 接線嗎？** 目前**無影響**（New UI 對 `calc_metrics`／`ret_1y_total`／`resolve_1y_total_return` 0 消費）。**未來接線前**必須先處理：窗口定義（行數窗 vs 日曆月窗）、上界、窗口證據欄；N1 本身優先級低於長窗無上界。

**對 N1 的總評：PARTIAL**——程式碼描述全部屬實，但「機率可能很低」應改寫為「在目前已知的日期粒度 NAV 來源下，觸發條件（同日內多筆唯一時間戳）**不可達**；唯一可達路徑需要盤中／次日內時間戳索引」。

---

## §1 窗口生成路徑全表

位置皆為 `services/fund_service.py::calc_metrics`（約 L820–L902）。「log」欄依 CLAUDE.md §1「填補必須 (2) 寫入 log」判讀：**stderr `print` 不算結構化 log，但本檔 `fund_service.py` 全檔 27 處 `print(`、0 處 `logging`，stderr print 是該檔的事實 log 慣例**（灰色，見 §3-3）。

| # | 路徑 | 觸發條件（讀碼） | 產出 `ret_1y_window_days` | 量測／估算 | 下游可區分？ | log？ | 測試鎖定？ | 實跑（§2.3） |
|---|---|---|---|---|---|---|---|---|
| P0 | 不建窗 | `len(s)<20` 或 `now<=0`；或 `len≥20` 但跨度 `<30` 天 | `None` | — | 是（None→resolver `no_restored_value`／`no_series`） | 無需 | 有：`test_ret_1y_total_too_short`（`tests/test_fund_metrics.py`） | — |
| P1 | ≥252 列、量測成功 | `len(s)≥252`、`(index[-1]-index[-252]).days>0` | `(最後日-倒數第252列日).days` | **量測**（行數取窗，非日曆窗） | 不需區分 | 成功時 stdout 印一行 | 有：`test_ret_1y_total_full_year_marks_window_365`（只斷言 ≥350） | A1 351；A2(253) 351 |
| P2 | ≥252 列、解析例外 | `pd.to_datetime(...)` 或相減 raise → `_window_actual_days=365` | 365 | **預設值**（非量測） | **否** | stderr print（L843） | **無** | 結構性不可達（見 §2.4）；僅能注入式模擬 |
| P3 | ≥252 列、跨度為 0 天 | `(...).days==0` → `0 or 365` | 365 | **預設值**（0 被 falsy `or` 改寫） | **否** | **無（連 print 都沒有）** | **無** | C2、C3：window 365、`ok` |
| P4 | <252 列、跨度≥30 天（量測） | 日期索引正常 | `(最後日-首日).days`（**無上限**） | 量測，但**可遠超一年** | 僅靠 `window_days` 大小；標籤相同 | 無 | 有：`test_ret_1y_total_short_window_NOT_annualized`（只驗 <350）；**無上界測試** | A2、B1（252 列週頻 1757 天）、B2（60 列月頻 1796 天）、B3 |
| P5 | <252 列、跨度<7 天 → 估算 | `_days_span<7`（含「解析例外後 `_days_span=0`」）→ `max(int(len*1.4),14)`；之後若 ≥30 走 P4 分支 | `int(len*1.4)`（22 列起 ≥30） | **估算**（把列數當交易日換成日曆日） | **否** | **無（連 print 都沒有）** | **無** | C1：250／251 列 → 350／351、`ok` |
| P6 | 例外／`_mask` 空／`adj_start<=0` | `_tr` 還原失敗 | `window_days` 維持已設的值，`ret_1y_total=None` | — | 是（resolver → `no_restored_value`） | stdout 印失敗 | 部分 | — |
| P7 | 外層守門 | `schema` 先驗（`validate_fund_nav_data_only`，L413）失敗 → `raise` | （進不了視窗碼） | — | — | stdout 印 | 有（schema 測試） | E：stub 驗 tz-aware／重複／RangeIndex 皆被擋 |

補充事實：
- `_days_span<7` 這個 `if` **沒有任何 print、沒有旗標**；N1 寫「只有 stderr print」對 P2 為真，對 P3／P5 **不精確**（P3／P5 完全靜默）。
- 350 門檻位於 `shared/signal_thresholds.py:235`（`RET_1Y_RESTORED_MIN_WINDOW_DAYS: int = 350`，註解自述「值 350 自 inline 搬入 SSOT，值未改」）；解析器只做**下限**判斷（`services/fund_total_return.py` L305：`wd_i < 350 → window_short`），`git grep` 無任何上界常數或比較（G5 輸出為空）。

---

## §2 對 N1 的獨立驗證

### 2.1 逐句判定

| N1 原句 | 判定 | 證據 |
|---|---|---|
| 例外時 `_window_actual_days = 365` | **CONFIRMED（程式碼）／PARTIAL（可達性）** | `fund_service.py` L845。進入該段前 `validate_fund_nav_data_only` 已要求 index 為 `datetime64[ns]`、單調遞增、唯一（`shared/schemas.py` `FundNavSchema`），`pd.to_datetime(Timestamp)` 不會 raise → 結構上不可達（真 pandera 未跑，見 §5） |
| `or 365` 讓 0 天也變 365 | **CONFIRMED**（實跑 C2：252 列 5 分鐘間隔，`index[-1]-index[-252]` 為 0 天，輸出 `window_days=365`、`status=ok`） | 0 天需 252 個**同一日曆日內**的唯一時間戳＝盤中資料 |
| 跨度<7 天用 `max(int(len(s)*1.4),14)` 估跨度 | **CONFIRMED（程式碼）／PARTIAL（可達性）** | L832–833。日頻以上索引：≥20 個**不重複日期**至少跨 19 天（實跑 D：20 個營業日跨 27 天）→ `_days_span<7` 不成立。僅盤中／次日內時間戳可觸發 |
| 列數 250～251 時估算值恰好過 350 | **CONFIRMED（算術與實跑）／PARTIAL（可達性）** | §2.2、§2.3 C1：250→350、251→351、`resolver.status=ok`。但同樣只在 span<7 天時成立；**日頻 250 列的實際走法是量測 347 天 → `window_short`**（A2 bday250） |
| 只有 stderr print、無旗標 | **PARTIAL** | P2 有 stderr print；P3／P5 連 print 都沒有。「無旗標」成立 |
| 現有測試未見鎖定 | **CONFIRMED（單組 grep）** | `grep -rnE "1\.4\|or 365\|_days_span\|days_span" tests/*.py`（G1）無任何相關命中；26 個測試檔引用 `ret_1y_window_days`，無一斷言 365 預設或 ×1.4 估算，亦無長窗上界斷言（G3 於 2026-11-13 整合時重跑，僅命中三處 `< 350` 短窗斷言，見附錄 C）。全稱句，**單組未驗** |
| 機率可能很低 | **PARTIAL（改寫）** | 不給機率數字。情境論述見 §2.5：已知 NAV 取數路徑皆日期粒度，觸發需盤中／次日內時間戳索引 |

### 2.2 邊界算術（純 Python 模擬 A）

腳本 `sim_arith.py`（全文見附錄 A）**是複製邏輯，不是 import 原檔**。逐行對照原碼確認等價處：

| 模擬 | 原碼 |
|---|---|
| `days_span = max(int(span_days), 0)` | L826 `max(int((_ts_last - _ts_first).days), 0)` |
| `if days_span < 7: days_span = max(int(n_rows*1.4), 14)` | L832–833 |
| `if n_rows >= 252:` 取 `index[-252]` 差 | L835–839 |
| 例外 → `wad = 365`；`wd = wad or 365` | L845–846 |
| `elif days_span >= 30:` 窗口＝`days_span` | L847–853 |
| 進入條件 `n_rows >= 20 and now > 0` | L820 |

輸出（節錄，完整見附錄 C）：`rows=248→347 False`、`249→348 False`、`250→350 True`、`251→351 True`；`rows=22→30`（22 列起估算值 ≥30 就建窗）；`rows=252, idx252_days=0 → 365`。

### 2.3 實跑原函式（模擬 B）

腳本 `sim_real.py`（附錄 B）**import 原檔** `services.fund_service.calc_metrics` 與 `services.fund_total_return.resolve_1y_total_return` 實跑。**揭露**：(i) 本機 pandera 未安裝，故以 stub 取代 `shared.schemas` 的兩個 validator（NAV：tz-naive datetime64、單調、唯一、>0、無 NaN；配息：no-op）；(ii) 本機 pandas 3.0.5，而 `requirements.txt` 釘 `pandas>=2.3.3,<3.0`；(iii) 以 `PYTHONDONTWRITEBYTECODE=1` 執行，未寫入 repo。結果（節錄）：

| 情境 | 列數／實際跨度 | `ret_1y_window_days` | resolver |
|---|---|---|---|
| A1 營業日 300 列 | 300／417 天 | 351 | ok |
| A2 營業日 248／249／250 列 | —／345／346／347 天 | 345／346／347 | **window_short** |
| A2 營業日 251／252／253 列 | —／350／351／352 天 | 350／351／351 | ok |
| A3 日曆日頻 251 列、A4 252 列、A5 366 列 | 250／251／365 天 | 250／251／251 | **window_short**（日曆日頻恆拒＝BL-0427 (3)） |
| **B1 週頻 252 列** | 約 4.8 年（1757 天） | **1757** | **ok** |
| **B2 月頻 60 列** | 約 5 年（1796 天） | **1796** | **ok** |
| B3 週頻 60 列 | 413 天 | 413 | ok |
| **C1 40 分鐘間隔 250／251 列** | 實際跨度 6 天 | **350／351（估算）** | **ok** |
| C1 40 分鐘間隔 30 列 | 0 天 | 42（估算） | window_short |
| **C2 5 分鐘間隔 252 列** | 0 天 | **365（`0 or 365`）** | **ok** |
| C3 5 分鐘間隔 300 列 | 1 天 | 365 | ok |
| E tz-aware／重複日期／RangeIndex | — | 被 schema 擋，進不了窗口碼 | — |

### 2.4 實際資料來源與觸發情境可達性

- **NAV 序列來源**：`calc_metrics` 的 `s` 來自 `finalize_fund_metrics`（`fund_service.py` L1304–L1367），為 live 取數序列與 `services/nav_history_gs.load_series` 累積序列的 union（`_merge_nav_history_series`）。
- **索引保證**：`calc_metrics` 入口先過 `validate_fund_nav_data_only` → `FundNavSchema.validate`（`datetime64[ns]`、單調遞增、唯一、>0、無 NaN），失敗即 `raise`（L413–418）。`load_series` 對壞日期 `errors="coerce"` 後**顯式丟棄**（`s = s[s.index.notna()]`）。故 NaT／缺日期欄／重複日期／週資料形態的「亂索引」進不了視窗碼（週資料可進，但走量測分支 P4，不是估算）。
- **取樣檢視 live 取數器**（`repositories/fund/sources.py`，非窮舉）：多數以 `pd.Timestamp(str(d_val)[:10])`（取前 10 字元＝日期粒度）、`ts.normalize()` 建索引；另有 `pd.Timestamp(ts, unit="s")`（epoch 秒，約 L2278）可能帶時分秒，但屬日 K。**未發現盤中粒度來源**；全部 fetcher 是否皆日期粒度＝**NOT VERIFIED**（未逐一閱讀）。
- **結論**：P2／P3／P5（N1 所指三條）需要「同一日曆日內多個唯一時間戳」的索引。以目前已讀到的來源，**不可達**；若日後有盤中或次日內序列（例如把即時估值點寫進 `nav_history`），三條會同時變可達且完全靜默。這是**條件式風險，不是現況缺陷**。
- **觸發情境清單（情境論述，不給機率）**：

| 資料形態 | 能否進 P2／P3／P5？ | 說明 |
|---|---|---|
| 日期欄缺失／全 NaT | 否 | `load_series` 丟棄；schema 要求 datetime64 |
| 重複日期 | 否 | schema 要求唯一；`load_series` `groupby.last()` |
| 週頻／月頻 | 否（走 P4） | 但引發長窗問題（§3-2） |
| tz-aware 時間戳 | 否（本組以 stub 驗；真 pandera 行為 NOT VERIFIED） | 真 pandera `pa.Index("datetime64[ns]")` 對 tz-aware 的處理未驗 |
| 盤中／次日內時間戳 | **是** | 唯一可達情境 |

### 2.5 本組與先前說法的差異

先前說法暗示「250～251 列有估算風險」。本組實測：**日頻 250 列實際得到量測值 347 天並被正確拒判**；N1 的 350／351 只在跨度<7 天時成立。**更大的、先前（在 R-PERF-5 內）只以「讀字面、未實跑」記載的風險是 BL-0427 (4)「350 只是下限」**，本組已以實跑重現（B1／B2），見 §3。

---

## §3 四個客戶問題逐題回答

### 3-1 估算值與真實值可區分嗎？

**否**。
- `ret_1y_window_days`（`int`）與 `ret_1y_total`（`float`）之外，`calc_metrics` 輸出**沒有** `window_basis`／`is_estimated` 之類旗標（`git grep` 於 `fund_service.py` 無此類鍵；輸出區 L1128–L1146 僅 `ret_1y_total`、`ret_1y_window_days`、`ret_1y_div_count`）。
- `resolve_1y_total_return` 回傳鍵：`value_pct／status／reason／source／window_days／div_count_in_window／official_1y_pct／label`；`ok` 的 `source` 恆為 `SRC_SELF_RESTORED`、`label` 恆為 `自算（還原含息淨值）`（或附「數值異常大」警語），**與窗口是量測 351 天、估算 350 天、或 1757 天完全相同**（§2.3 表 A1／C1／B1 的 label 欄皆為同一字串）。
- 下游若讀 `window_days` 可看出長短，但**看不出它是量測還是估算**。

### 3-2 日期窗口可能造成績效誤判的具體情境與誤差方向（邏輯推導，未實測下游燈號）

| 情境 | 可達性 | 誤差方向（邏輯） |
|---|---|---|
| **S1 長窗無上界**（稀疏／月頻／週頻或「短 live ＋ 稀疏累積」合併序列；實跑 B1／B2） | **可達**：`_merge_nav_history_series` 會把稀疏累積點併入；`finalize` 的稀疏處理（L1374–L1420）只砍 `sortino／calmar／sharpe／std_*`，**不動 `ret_1y_total`**（`_killed` 清單可證）。實際有多少檔基金落入此形態＝**NOT VERIFIED**（BL-0427 (4) 已記「production 還沒查」） | 窗口＝k 倍一年時報酬約為 (1+r)^k−1：算術示例——若每年 8%、k≈4.8，約 44.7%（**示例算術，不是實測資料**）。r>0 → 高估；r<0 → 報酬更負（低估）；與 12M 年化配息率（日曆窗 365 天，L952）比較時，吃本金燈號可能 r>0 假 🟢、r<0 假 🔴 |
| **S2 估算窗**（P5） | **目前不可達**（需盤中索引） | 把數日報酬當一年報酬：量級被低估；與年化配息率比，傾向使覆蓋率偏低 → 偏假 🔴（推導） |
| **S3 `0 or 365`**（P3） | 同上不可達 | 零跨度被當 365 天：極短窗被標成一年，同 S2 |
| **S4 行數窗 vs 日曆窗** | **可達（常態）** | 窗口以「倒數第 252 列」取，不是日曆 365 天。純營業日 252 列＝351 天（A1）；含假日的真實市場可能 >365。窗口落在 350～~375 天之間浮動，報酬差約等於 (窗口差天數/365)×年化報酬（量級小，方向隨報酬正負） |
| **S5 日曆日頻序列** | 可達 | 252 列只跨 251 天 → `window_short`（A3–A5）：**不是誤判，是過度拒判**（BL-0427 (3)） |
| **S6 12M 配息窗與還原窗不同窗** | 可達 | 見 BL-0427 (2)，本組不重驗 |

### 3-3 是否違反 Missing≠0／估算必須標示

規則原文（引自本 session 載入的 `CLAUDE.md` §1 與 `PROJECT_RULES.md` §13.1）：
- §1：「禁止…自行『估一個合理值』當常數」；「任何填補必須：(1) 顯式呼叫、(2) 寫入 log、(3) 在輸出帶旗標」。
- §13.1「禁止」：「不得把 Missing 轉成 0／中性／HOLD／安全／未觸發」。
- 1B（`DEC-2026-10-23-02`）：「資料不足 → ⬜…不得 fallback 成純 NAV、0、中性或估算值；純 NAV／外推不得掛『含息』名」。
- `PROJECT_RULES.md` 第 13 條對照表第 8 列「不得 fake precision」：**repo 內無以此為名的既有條文**（該表自述），本組不引用為規則。

| 路徑 | §1 禁自行估值 | §1 填補三要件（顯式／log／旗標） | §13.1 Missing≠0 | 1B 不得 fallback 為估算值 | 判定 |
|---|---|---|---|---|---|
| P5 估算跨度 | 估算的是**窗口天數**（日曆日），不是 NAV 值；但此估算直接決定 350 閘門是否放行 | 顯式：程式碼可見但輸出不可見；log：**無**；旗標：**無** | 未填 0 | `ok` 值由估算窗口放行，違反精神 | **灰色偏違反**（若觸發）；目前不可達 |
| P3 `0 or 365` | 同上，把 0 天改寫為 365 | log 無、旗標無 | 0 並非 Missing，但把「退化值」改寫成合理值；與本檔 L1000–1003 自己修過的 `or` falsy-0 家族同型（註解：provenance 說謊） | 同上 | **灰色偏違反**；不可達 |
| P2 例外→365 | 同上 | **有 stderr print**（log 慣例），旗標無 | — | 同上 | **灰色**（log 有、旗標無）；不可達 |
| P4 長窗（量測值，非估算） | 不是估算 | — | 不涉及 | **違反「近一年」標示**：1757 天掛「1Y 含息」，label 無窗口提示 | **違反 1B 精神（已由 BL-0427 (4) 登記待裁）** |
| 三處直讀 raw（F-C） | — | — | 窗口 <350 的值被當 1Y 報酬傳遞 | — | **灰色偏違反**（見下） |

**F-C（本組新增發現，讀碼＋實跑佐證）**：以下三處**直讀 `metrics.ret_1y_total`、未經 `resolve_1y_total_return` 閘門**：
- `ui/tab3_portfolio.py`（約 L2448）：組合 AI 快照，字串 `1Y 報酬 {ret_1y}%`——**窗口 <350（如 345 天，A2 實跑 `ret_1y_total=-16.07` 仍有值）仍以「1Y 報酬」送進 AI prompt**；
- `ui/tab3_portfolio.py`（約 L779）：原始資料傾印欄 `1Y含息%(還原淨值)`；
- `ui/tab5_data_guard.py`（約 L1397）：診斷格 `1Y含息報酬（還原淨值）[本地·cache]`（僅 `perf["1Y"]` 缺值時的 fallback）。
原因：`calc_metrics` 對 30～349 天窗口**仍算並輸出** `ret_1y_total`（短窗累積），閘門只存在於解析器。這與 `fund_total_return.py` 檔頭「同一檔基金在不同分頁會因為走到不同層而出現不同數字」的 SSOT 目標相悖。是否已在 BACKLOG 登記：`docs/BACKLOG.md` 僅 1 行含 `ret_1y_total` 字樣（BL-0428 列），**本組未逐字判讀其是否涵蓋這三處＝NOT VERIFIED**。

> **整合時事實更正（2026-11-13，落盤者以 `git grep -n "ret_1y_total" docs/BACKLOG.md` 實查）**：該行為 **BL-0523 列**（非 BL-0428 列）。BL-0523 登記「tab2 快照與 tab3 表欄讀原始 `ret_1y_total`，繞過 SSOT 門檻」，**未涵蓋**本節的 tab3 AI prompt 與 `ui/tab5_data_guard.py` 診斷格，故另登記 BL-0547（與 BL-0523 部分重疊）。上段原文保留不改。

### 3-4 是否影響未來 New UI2 接線

- **現況**：`git grep -nE "calc_metrics|ret_1y_total|ret_1y_window_days|resolve_1y_total_return|compute_1y_total_return|fund_service|fund_total_return|ret_1y\b"` 於 `ui_v2／ui_v3／services/v2_tables／services/v2_domain／mcp_server` 的 `.py` **0 命中**（唯一相關字樣是 `services/v2_tables/nav_dividend.py:651` 提到 `fund_service.py::_merge_nav_history_series` 的註解，非呼叫）。New UI 目前**未消費**本路徑 → **現況零影響**。這與 D2 準備檔「17 列中 `R-PERF-2／4／5／7／8` 只存在於舊站」一致。
- **New UI 自己的「1Y」定義不同**：`services/v2_domain/periods.py::slice_period` 以**日曆月**往回推（`PERIOD_MONTHS["1Y"]=12`）、期間不足回 `STATUS_INSUFFICIENT`、不縮短冒充。若未來把 `resolve_1y_total_return`（行數窗）與 `slice_period`（日曆窗）並列，會形成**同畫面兩套「1Y」**（對應 BL-0524 G-RET-2）。
- **未來接 1Y 績效前須先處理（依優先序，皆須客戶 Gate）**：(1) 窗口定義與上界（BL-0427 (3)(4)、BL-0524）；(2) 輸出須帶窗口證據（`window_days` 之外還需窗口基礎／起訖日，但 D2-B 明禁由 `window_days` 推起日）；(3) 不得直讀 raw `ret_1y_total`（F-C）；(4) N1 三條估算路徑：優先級低（目前不可達），但若 New UI 引入任何盤中／次日內序列，會同時變可達。
- 與既有項目關係：`DEC-2026-11-09-01` D2-B「不代表核准舊站 1Y 含息算法延伸至 New UI2」；`DEC-2026-11-11-04`「不授權…報酬窗、門檻（含 350）…皆不改」；D2 準備檔 `R-PERF-5` 推薦 B（維持 Pending）——**本組結論支持維持 Pending，且建議把 `R-PERF-5` ④ 的 N1 敘述改為「估算路徑僅盤中索引可達；主要風險為長窗無上界（BL-0427 (4)，已實跑重現）」**（文件建議，非本檔執行）。

---

## §4 風險分級與建議的後續（只限研究／文件／測試草案層級；**不修改公式**）

| 風險 | 內容 | 分級（總管讀法，可被客戶推翻） |
|---|---|---|
| R1 長窗無上界 → 稀疏序列「1Y」實為多年 | 可達；實跑重現；frequency NOT VERIFIED | **高**（若 production 有稀疏／合併序列基金；BL-0427 (4) 已列待裁） |
| R2 三處 UI 直讀 raw `ret_1y_total` | 可達；短窗值以「1Y」進 AI prompt | **中** |
| R3 N1 三條估算／預設路徑（P2／P3／P5） | 目前不可達，靜默；日後盤中索引會可達 | **低（目前）／潛在中** |
| R4 行數窗 vs 日曆窗浮動 350～375 天 | 常態，量級小 | **低** |

| 方案 | 內容 | 優點 | 缺點 | 風險 | 涉及公式修改？ | 推薦 |
|---|---|---|---|---|---|---|
| **A 文件層** | 在 D2 `R-PERF-5` 與 BL-0427 (4) 補記：N1 僅盤中索引可達、日頻不可達（附 §2.3 實跑表）；長窗無上界已實跑重現；F-C 三處清單；`window_days` 不可區分量測／估算的事實 | 零風險、立即降低誤導；對齊既有 Gate | 不降低實際風險 | 文件組讀碼誤差 | **否** | **推薦（總管讀法）** |
| **B 測試草案層** | 提出（不落地）特徵化測試草案：① 釘住現況「窗口 1757 天仍 ok」為 `xfail(strict)`（待上界裁示後翻轉）；② 釘住「日頻 250 列＝window_short」；③ 釘住「盤中索引 span<7 天會走估算」並標 `DOCUMENTED_LIMITATION`；④ 守衛：禁止 UI 直讀 `metrics["ret_1y_total"]`（AST）；另唯讀盤點 production NAV 形態（BL-0427 (4) 已要求） | 讓行為變化可被偵測；盤點能把「機率」換成實測 | 測試落地須走正常 PR／稽核；盤點需資料存取授權 | 守衛誤報 | **否**（不改公式，但新增測試須客戶／總管同意落地） | **推薦與 A 併行（總管讀法）** |
| **C 程式／公式修補** | (i) 估算與 `or 365` 改為 `None`＋原因或新增 `window_basis` 旗標；(ii) 為窗口加上界；(iii) 改日曆窗 | 根除 R1／R3 | (ii)(iii) 屬正式 threshold／公式口徑；與 BL-0427／BL-0524 糾纏 | 改動 SSOT 會連動 `health/dividend`、吃本金、finalize 對帳、多處 consumer | **是 → 須客戶 Decision Gate，本批不授權** | 不推薦現在做；待 A／B 的盤點結果與 BL-0427 (4) 裁示 |

**明確聲明：本檔不修改任何公式、門檻、程式；上界天數、日曆窗與否皆屬客戶裁示，本檔不提具體數值。**

---

## §5 盲點與 NOT VERIFIED

| # | 項目 | 狀態 |
|---|---|---|
| 1 | 未跑 pytest（本機 `pytest` 位於 uv tool venv，該直譯器無 pandas；`/usr/local/bin/python3` 有 pandas 3.0.5 但無 pytest）。「現有測試未鎖」僅靠 grep＋讀斷言 | NOT VERIFIED（未實跑測試套件） |
| 2 | 無 pandera：以 stub 取代 `shared.schemas`，「schema 保證索引為 datetime64／單調／唯一」是**讀碼＋stub 對照**，非真 pandera 行為；tz-aware、`datetime64[us]`（pandas 3）在真 pandera 下的結果未驗 | NOT VERIFIED |
| 3 | pandas 3.0.5 ≠ 專案釘的 `<3.0`；本機實跑數值可能與 pandas 2.3.x 有細微差（窗口算術不依賴版本） | 揭露 |
| 4 | 模擬 A 為複製邏輯；模擬 B 為實跑原檔（含 stub）。兩者結果互相一致（C1／C2） | 揭露 |
| 5 | 未 live、未連網、未查 Google Sheet；production 有多少基金落入稀疏／長窗形態＝未知；未量測任何真實 NAV | NOT VERIFIED |
| 6 | 取數器日期粒度僅取樣 `repositories/fund/sources.py`，未逐一閱讀所有 fetcher；`nav_history` 寫入端（`record` 路徑）是否可能寫入帶時間的索引未查 | NOT VERIFIED |
| 7 | 「下游燈號會假 🟢／假 🔴」為邏輯推導，未對 `check_eating_principal_1y_mk` 實跑 | NOT VERIFIED |
| 8 | 「F-C 三處是否已登記」撰稿時未逐字比對 BACKLOG／HANDOFF（整合時已補比對 BACKLOG：僅 BL-0523 部分涵蓋，見 §3-3 整合更正；HANDOFF 仍未比對） | BACKLOG 已實查；HANDOFF NOT VERIFIED |
| 9 | 「`git grep` 無上界常數」「New UI 0 消費」「測試未鎖」皆為單組全稱句，附指令，**單組未驗** | 單組未驗 |
| 10 | 本檔為單組作者，尚待非作者 QA；未經客戶審閱 | 揭露 |

---

## 附錄 A：`sim_arith.py`（複製邏輯，非 import 原檔）

```python
"""模擬 A：純 Python 複製 calc_metrics 1Y 窗口生成段（fund_service.py 約 L820-L856）的決策邏輯。"""
def window_branch(n_rows, span_days, idx252_days=None, span_parse_fail=False, win_parse_fail=False, now_pos=True):
    if not (n_rows >= 20 and now_pos):
        return ("no_window_block", None)
    days_span = 0 if span_parse_fail else max(int(span_days), 0)
    est = False
    if days_span < 7:
        days_span = max(int(n_rows * 1.4), 14); est = True
    if n_rows >= 252:
        if win_parse_fail:
            wad = 365; tag = "except->365"
        else:
            wad = idx252_days; tag = "measured"
        wd = wad or 365
        if (not win_parse_fail) and wad == 0: tag = "0_or_365"
        return (f"rows>=252/{tag}", wd)
    elif days_span >= 30:
        return (f"rows<252/span>=30/{'ESTIMATED' if est else 'measured'}", days_span)
    else:
        return ("rows<252/span<30/no_window", None)

GATE = 350
for n in (248, 249, 250, 251):
    b, wd = window_branch(n, span_days=0)
    print(n, b, wd, wd is not None and wd >= GATE)
print(window_branch(252, 5, idx252_days=0))
print(window_branch(252, 400, win_parse_fail=True))
print(window_branch(250, 349), window_branch(250, 350))
```

## 附錄 B：`sim_real.py`（import 原檔實跑；stub pandera；腳本全文）

```python
"""模擬 B：import 原檔 services.fund_service.calc_metrics 實跑（唯讀 repo；PYTHONDONTWRITEBYTECODE=1）。
揭露：(1) 本機 pandera 未安裝 -> 以 stub 取代 shared.schemas 的兩個 validator（NAV：datetime64 index、單調遞增、唯一、>0、無 NaN；
配息：no-op）。這使『schema 保證』本身未被真 pandera 驗證（NOT VERIFIED）。(2) 本機 pandas 3.0.5，repo requirements 釘 pandas<3.0。
"""
import sys, types, io, contextlib
sys.dont_write_bytecode = True
sys.path.insert(0, "/home/user/my-Fund-dashboard")
import numpy as np, pandas as pd

stub = types.ModuleType("shared.schemas")
def validate_fund_nav_data_only(s):
    assert pd.api.types.is_datetime64_any_dtype(s.index) and getattr(s.index.dtype, "tz", None) is None, "index must be tz-naive datetime64"
    assert s.index.is_monotonic_increasing and s.index.is_unique and s.notna().all() and (s > 0).all()
    return s
stub.validate_fund_nav_data_only = validate_fund_nav_data_only
stub.validate_fund_dividends_data_only = lambda d: d
sys.modules["shared.schemas"] = stub
from services.fund_service import calc_metrics
from services.fund_total_return import resolve_1y_total_return

def mk(idx, seed=1, drift=0.0003, vol=0.01):
    rng = np.random.default_rng(seed)
    r = rng.normal(drift, vol, len(idx))
    return pd.Series(10*np.exp(np.cumsum(r)), index=idx)

def run(label, s, divs=None):
    err = io.StringIO(); out = io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
        m = calc_metrics(s, divs or [])
    r = resolve_1y_total_return({"metrics": m, "series": s, "moneydj_raw": {}})
    span = (s.index[-1]-s.index[0]).days
    true_cum = (float(s.iloc[-1])/float(s.iloc[0])-1)*100
    print(f"[{label}] rows={len(s)} real_span_days={span} | ret_1y_total={m.get('ret_1y_total')} ret_1y_window_days={m.get('ret_1y_window_days')} "
          f"| resolver.status={r['status']} reason={r['reason']} window_days={r['window_days']} label={r['label']!r} "
          f"| stderr_len={len(err.getvalue())}")
    return m, r

print("=== A. 日頻營業日（正常資料形態）===")
run("A1 bday 300", mk(pd.bdate_range("2024-01-01", periods=300)))
for n in (248, 249, 250, 251, 252, 253):
    run(f"A2 bday {n}", mk(pd.bdate_range("2024-01-01", periods=n)))
run("A3 calendar-daily 251 (freq D)", mk(pd.date_range("2025-01-01", periods=251, freq="D")))
run("A4 calendar-daily 252 (freq D)", mk(pd.date_range("2025-01-01", periods=252, freq="D")))
run("A5 calendar-daily 366 (freq D)", mk(pd.date_range("2025-01-01", periods=366, freq="D")))

print("=== B. 稀疏/長跨度（nav_history 累積形態）===")
run("B1 weekly 252 rows (~4.8y)", mk(pd.date_range("2020-01-03", periods=252, freq="W-FRI")))
run("B2 monthly 60 rows (~5y)", mk(pd.date_range("2020-01-31", periods=60, freq="ME")))
run("B3 weekly 60 rows (~1.15y)", mk(pd.date_range("2025-01-03", periods=60, freq="W-FRI")))

print("=== C. N1 觸發形態：盤中/次日內時間戳（unique 但跨度<7 天）===")
for n in (30, 250, 251):
    run(f"C1 40min-step {n}", mk(pd.date_range("2025-06-02 09:00", periods=n, freq="40min")))
run("C2 5min-step 252 (idx252 days==0)", mk(pd.date_range("2025-06-02 09:00", periods=252, freq="5min")))
run("C3 5min-step 300", mk(pd.date_range("2025-06-02 09:00", periods=300, freq="5min")))

print("=== D. 日頻但每日不重複：>=20 列的最小跨度 ===")
s = mk(pd.bdate_range("2025-01-01", periods=20)); print("20 bdays span =", (s.index[-1]-s.index[0]).days)
print("=== E. 壞 index 能否進入 calc_metrics？（stub 與 schema 契約一致：應 AssertionError）===")
for name, idx in (("tz-aware", pd.date_range("2025-01-01", periods=260, freq="B", tz="Asia/Taipei")),
                  ("duplicate", pd.DatetimeIndex(["2025-01-02"]*30)), ("RangeIndex", pd.RangeIndex(260))):
    s = pd.Series(np.linspace(10, 11, len(idx)), index=idx)
    try:
        calc_metrics(s, []); print(name, "-> entered calc_metrics")
    except Exception as e:
        print(name, "-> rejected before window code:", type(e).__name__)
```

（執行：`cd /tmp && PYTHONDONTWRITEBYTECODE=1 python3 -I <腳本>`；腳本內寫死的 `sys.path.insert(0, "/home/user/my-Fund-dashboard")` 為撰稿環境的 repo 根，換環境須改。本 PR 不入庫 `sim_arith.py`／`sim_real.py` 檔案本身，全文以本附錄 A、B 為準。）

## 附錄 C：關鍵指令與輸出

```
G1  grep -rnE "1\.4|or 365|_days_span|days_span" tests/*.py   -> 無任何與估算相關命中（僅無關的 1.41／1.496 等數值）
G3  grep -rnE "ret_1y_window_days[^=]{0,12}(<=|<)\s*[0-9]{3}" tests/*.py   （2026-11-13 整合時重跑；原稿 pattern 以 [...] 省略、原稿標「無輸出」，經重跑更正如下）
    -> tests/test_fund_metrics.py:152、tests/test_risk_metrics_p0_fixes.py:497、tests/test_xview_characterization.py:595，三處皆為 `< 350` 短窗斷言；無長窗上界斷言
G4  grep -rl "ret_1y_window_days" tests/*.py | wc -l -> 26
G5  grep -n "RESTORED_MAX|window_days >|wd_i >" services/fund_total_return.py services/health/dividend.py -> 無輸出
G6  sparse 砍除清單（fund_service.py L1374-L1392）：sortino、calmar、sharpe(self_calc)、std_1y/2y/3y/5y；不含 ret_1y_total
New UI 0 消費：grep -rnE "calc_metrics|ret_1y_total|ret_1y_window_days|resolve_1y_total_return|compute_1y_total_return|fund_service|fund_total_return|ret_1y\b" --include=*.py ui_v2 ui_v3 services/v2_tables services/v2_domain mcp_server
   -> 僅 services/v2_tables/nav_dividend.py:651 一行註解
模擬 A 輸出：rows=248→347 False｜249→348 False｜250→350 True｜251→351 True｜(252, idx252_days=0)→365｜(252, 例外)→365
模擬 B 輸出（節錄）：
 [A2 bday 250] ... ret_1y_window_days=347 | window_short
 [A2 bday 251] ... ret_1y_window_days=350 | ok
 [B1 weekly 252 rows] real_span_days=1757 | ret_1y_window_days=1757 | status=ok label='自算（還原含息淨值）'
 [B2 monthly 60 rows] real_span_days=1796 | ret_1y_window_days=1796 | status=ok
 [C1 40min-step 250] real_span_days=6 | ret_1y_window_days=350 | status=ok
 [C1 40min-step 251] real_span_days=6 | ret_1y_window_days=351 | status=ok
 [C2 5min-step 252] real_span_days=0 | ret_1y_window_days=365 | status=ok
 D: 20 個營業日跨度 = 27 天
```
