# UI 規格第三輪獨立稽核（R3）

> **受檢**：`spec/UI_SPEC.md`（265 行）、`spec/DECISION_LOG.md`（144 行），量測日 2026-09-16。
> **基準**：`origin/main` ＝ `9cbf0377`。工作樹 HEAD 是 `d0c2a8d`（落後 220 個 commit），
> **本組全程不碰共用工作樹的工作區** —— 以 `git archive origin/main | tar -x` 解到 `/home/user/r3audit/main/` 後唯讀分析。
> **本組未改任何 `.py`／未改 `spec/`／未改 `inv/`／未改既有 `audit/`／未 commit／未開 PR／未跑任何 workflow／未打任何外部 API。**
> **本組不裁決。** 矛盾一律「A 說 X（出處）／B 說 Y（出處）／兩者不能同時為真」。

---

## 0. 方法

### 用了哪幾種機制
1. **AST 歸屬**（`ast.parse` ＋ `lineno/end_lineno` 取最內層函式）—— 把行號對回所屬函式。
   用在第 (4) 項的 `#####` 歸屬、`_render_keys` 邊界、`tab5_data_guard.py:1175` 的歸屬。
   **理由**：固定行數的上下文窗會把相隔數百行的兩段接在一起讀。
2. **渲染端反查**（不從欄位名正向掃）—— 查「這一欄有沒有上畫面」一律從 `st.*` 呼叫、
   `render_cards([...])` 的 builder 清單、`pd.DataFrame(_rows)` 的欄名往回追。
   **理由**：屬性存取與 `asdict()` 掃不到。
3. **逐行原文重印**：`awk 'NR==N'` 單獨印出後照抄，**不經 `grep -v` 數序號**。
4. **結構掃描**：`grep -n "safe_section(" ui/views/page_0*.py` 取每頁的頂層區塊序列，
   再與規格的「畫面順序」逐格對。**這是本輪找到最多東西的一條。**
5. **四法量尺寸**（見第 10 項）。

### 正控（每條掃描同批跑）
| 掃描 | 正控 | 結果 |
|---|---|---|
| 規格標籤計數 | `grep -c "規則" spec/UI_SPEC.md` → **41** | 中文 grep 有效 |
| 區塊名是否在規格內 | `逐檔體檢表`→1／`換股顧問`→2／`組合健康總分`→1／`配息月曆`→1 | 全部 >0 |
| 盤點表鍵名 | `grep -c "v03_research_batch_rows" inv/DB_INVENTORY.md` → **2** | 命中 |
| 已失效負控字串仍找得到 | 同一條 grep 在 `audit/` `inv/` 共 **5 檔**命中 | grep 本身會命中 |
| 長字串（id）掃描 | 同一條 regex 對 `services/nav_history_gs.py` **有命中**（內容不列出） | regex 有效 |
| `.py` 符號存在性 | `grep -rn "calc_holdings_overlap" --include=*.py .` → **48 行** | 命中 |

**負控**：本組自訂隨機串（**不列出**，客戶裁示 6）。實測在 `spec/` 兩檔、以及全 repo `*.py` **皆 0**。
⛔ **本組刻意不使用 brief 點名的那個舊負控**（它已被寫進本專案多份文件、掃文件時會命中，已失效）。

### ⚠️ 這個方法結構上看不到什麼
1. **沒跑任何測試、沒啟動 Streamlit。** 所有「到不到得了畫面」都是靜態讀碼；
   **條件分支在真實 session 下走不走得到 —— 查不到。** 第 (2) 項那條最重的矛盾受此限制。
2. **沒讀線框 `docs/wireframes/*.html`。** 規格與 repo 多處自稱「線框逐字」，
   **那是不是真的逐字 —— 查不到。**
3. **沒有回頭重驗盤點表自己的逐欄判定**，只**引用**它去對規格。
4. **沒有重驗 M1–M20 與 R1–R14 當初的判定本身是否正確**，只驗「這一輪有沒有照著改」。
5. **`grep -n "safe_section("` 只看得到字面呼叫** —— 動態組出的區塊、
   或不走 `safe_section` 的渲染點（例如裸 `st.markdown` / `render_cards`），這條掃不到。
   本輪已就此補了人工通讀，但**「每頁沒有第 N+1 個區塊」本組不宣稱。**

---

## 1. 34 塊四件是否真的齊全

**結論：34 個區塊、136 個小標，一個都沒缺，也沒有佔位句。**

```
grep -c '^### ' spec/UI_SPEC.md        → 38
grep -n '^### ' spec/UI_SPEC.md        → 38 行（其中 4 行是 甲／乙／丙／丁）
38 − 4 = 34 ✓   ①11 ＋ ②4 ＋ ③4 ＋ ④7 ＋ ⑤8 = 34 ✓
```
AST 切出 34 塊後逐塊數四個小標（`- 來源：` / `- 規則：` / `- 空狀態：` / `- 回答：`）：
**34 塊 × 4 ＝ 136，missing 清單為空。**

最短的四個（逐一人工讀過，**全部指得到具體東西，不是佔位**）：
| 位置 | 最短那一件 | 字數 | 內容 |
|---|---|---|---|
| ⑤-5 | 來源 | 49 | 模組常數 `EVIDENCE_HEADING`（不標標籤：純版面分界） |
| ⑤-2 | 規則 | 36 | 逐項只印「有設／沒設」與它擋住哪一塊，永不回顯值或片段 |
| ①-5 | 空狀態 | 22 | 灰態「這一輪一項指標都沒取到。」 |
| ③-4 | 回答 | 13 | 我要查的是哪一檔 |

📌 **一處「填了但比同類淡」的（不算缺，登記）**：**③-4 的來源寫「送出後存 session」，
沒有寫是哪一個 session 鍵**；同性質的 ④-2 寫出了 `_FORM_KEY`＝`v04_portfolio_rebalance_form`
與 `_SK_APPLIED`＝`v04_portfolio_applied_plan`。**兩塊的具體度不一致。**

---

## 2. 三標籤是否照定義、逐欄判

### 2.1 計數（R13）—— 本組重跑，四個數字全部重現
```
grep -o '\*\*沿用\*\*'        spec/UI_SPEC.md | wc -l → 20  − 定義句(:18) = 19 ✓
grep -o '\*\*沿用（部分）\*\*' spec/UI_SPEC.md | wc -l →  6  − 定義句(:19) =  5 ✓
grep -o '\*\*新建\*\*'        spec/UI_SPEC.md | wc -l →  7  − 定義句(:20) =  6 ✓
grep -o '\*\*不標標籤\*\*'    spec/UI_SPEC.md | wc -l →  7  − 定義句(:24) =  6 ✓
19+5+6+6 = 36；逐塊數後 ①-1（沿用＋新建）與 ④-2（新建＋沿用）各帶兩個，其餘 32 塊各一個
→ 36 = 34 + 2 ✓ **內部自洽，且與實況相符。**
```
⚠️ `\*\*沿用\*\*` **不會**誤命中 `**沿用（部分）**`（後者「沿用」之後是 `（`）—— 已確認無子字串汙染。

### 2.2 brief 指定的那條測試：「標沿用、但該欄的『誰讀它』是內部或無」
**逐塊對回 `inv/DB_INVENTORY.md` 的「誰讀它」欄，本組沒有找到這種情形。**

| 規格塊（標沿用） | 盤點表出處 | 狀態 ／ 誰讀它 |
|---|---|---|
| ②-4／④-1 `portfolio_funds[].invest_twd` | `:1228` | 活的 ／ **UI** |
| ④-1 `.policy_tier` ／ `.is_core` | `:1234`／`:1246` | 活的 ／ **UI** |
| ④-3 `<保單分頁v2>` 6 欄 | `:385-390` | 6 欄全部 活的 ／ **UI** |
| ⑤-1 `nav_history.code/.date/.nav` | `:532-534` | 活的 ／ **UI** |
| ②-1／②-2／④-5／④-6 的 `.moneydj_raw`／`.metrics`／`.dividends` | `:1242-1244` | 未落地 ／ **UI** |
| ⑤-3 `data_registry` | `:1284` | 未落地 ／ **UI** |
| ①-* 的 `indicators` | `:1281` | 未落地 ／ **UI** |
| ④-4 `transactions[]` 8 欄 | `:1170-1177` | 只寫不讀 ／ **內部** → 規格標 **新建** ✓ |

「未落地 ／ UI」那幾列，規格 `:22` 已就地寫明「盤點表『未落地』量的是持久化、不是到不到得了畫面」——
**該讀法已揭露，本組不裁決它對不對，只記錄它被揭露了。**

### 2.3 R3／R4／R5 三塊重點打（brief 指定）

**R3｜②-1 由「沿用（部分）」改「沿用」—— 本組逐層實跑，成立。**
三層 fallback 的 SSOT 是 `services/health/dividend.py:311-381 _resolve_adr_with_fallback`，
逐行原文：
```
343  _mj_dy = _safe_float(_mj.get("moneydj_div_yield"))      ← 層 1
348  _local = _safe_float(_metrics.get("annual_div_rate"))   ← 層 2
353  _divs = fund.get("dividends") or _mj.get("dividends")   ← 層 3
```
到畫面的路徑：`_eating_tally()`（`page_02_health.py:1223`）→ `_eat_card`（`:1536`/`:1543`）
→ `render_cards([...])`（`:1585`）。**三層都到得了畫面 ✓。**

**R4｜②-2 改「沿用」—— 成立。**
```
page_02_health.py:1317  _h = _mj(_f).get("holdings") or {}
              :1318  _tops = _clean_holdings(_h.get("top_holdings"))
              :1319  _sects = _h.get("sector_alloc") or []
              :1336  return calc_holdings_overlap(_rows), _blind
              :1580  "value": f"{len(_pairs)} 對",      ← 兩欄的結果上了卡
              :1585  render_cards([_eat_card, _lag_card, _shadow_card])
```
**兩欄都經 SSOT 算出 `shadow_pairs` 並印在卡上 ✓。**

**R5｜④-6 改「沿用」—— ⛔ 與實作衝突。見第 11 節矛盾 C-1。**

---

## 3. R9 三類分得對不對

### 3.1 算術
R2 的 R9 表共 8 列，展開成 **14 個項目**（其中一列 5 個 `#####`、一列 3 個 ⑤ 區塊）。
生產組的 **刻意砍 7 ＋ 補回 6 ＋ 不確定 1 ＝ 14** ✓ **對得起來。**
補回 6 展開成區塊：詳細區整區 → ①-6～①-11（6 塊）、②結論 → ②-4、⑤結論 → ⑤-4、
⑤依據 → ⑤-5、⑤手動補資料 → ⑤-6、⑤使用手冊 → ⑤-7 ＝ **11 塊**；
加不確定那 1 項補回的 ⑤-8 ＝ **12 塊**，與 丁段「以上 12 塊出自 R9」✓。
丁段 12 ＋ ③-4 ＝ **13** ✓；丙段 11 塊 ✓（數 `／` 分隔：10 個 → 11 項）。
甲 9 項 ＋ 乙 4 項 ＝ **13** ✓（`grep -cE '^[0-9]+\. '` 分段數：9 / 4）。

### 3.2 刻意砍的 7 項 —— 逐條自己 `awk 'NR==N'` 重印，**7 條出處全部逐字成立**
| 項 | 引用 | 本組重印的原文 |
|---|---|---|
| `#####` ×5 的分節規則 | `page_01_macro.py:1136-1141` | `1137 - 塊**標題**用 \`####\`；` `1138 - 塊**內部**的分節一律用 \`#####\`（H5）—— 守衛刻意不收 H5，` |
| 5 個 `#####` 本體 | `:1281/:1365/:1408/:1539/:1550` | 逐行皆為 `st.markdown("##### …")`，字面與 R2 所列一致 |
| 總經燈號全表 | `:2046-2054` | `2046 empty_state(` `2047 "總經燈號全表（值／位階／資料日期／來源）—— 已拍板不做",` |
| 同上「只有 1 項指標」 | `:2048-2049` | `2048 "「來源」欄目前**只有 1 項指標**帶得回來源標記，其餘全部會是「—」；"` `2049 "而「位階」欄兩份線框都沒有定義過它的意思",` |
| 換股顧問阻擋理由 | `:933-934` | `933 #: ⛔ **阻擋結論不變**：\`pool_rows\` 這一個就足以擋住 —— 它要 OAuth 往返 Google Sheets，` `934 #:    而本頁禁 import \`repositories/**\`。` |
| 換股顧問理由常數 | `:939` | `939 REASON_SWITCH: str = (` |
| 換股顧問渲染點 | `:1656` ／ `:2778` | `1656                 switch_block_label(), state=STATE_NOT_READY,`；`2778     safe_section("動作卡", _render_action_cards)` |

另外實測佐證：`grep -n 'ZSCORE_STOP_GAIN_DEFAULT' shared/signal_thresholds.py` → `:409 = 1.75`、`:410 ZSCORE_ADD_DEFAULT = -1.0`；
乙-2 說的「上游一律傳 `None`」在 `page_01_macro.py:785 allocation_from_composite(ev.get("score"), None)` **成立**。

### 3.3 補回的 12 塊 —— 四件已齊（見第 1 節），來源符號全部存在於 `origin/main`
```
_SK_IND   = "v01_macro_indicators"        page_01_macro.py:203   ✓
_SK_RADAR = "v01_macro_risk_radar"        :211  ✓   _SK_USLIQ = "v01_macro_us_liquidity"  :219 ✓
_SK_LIQ   = "v01_macro_liquidity_stress"  :221  ✓   _SK_TP    = "v01_macro_turning_points" :223 ✓
_SK_AI    = "v01_macro_ai_text"           :231  ✓   _SK_DIAG_GATE = "v05_diag_gate"  page_05_settings.py:352 ✓
_DETAIL_TITLES :1028-1033（5 塊）✓  _DETAIL_HEADING :1036 ✓  _DETAIL_ZONE :1937 ✓
_DETAIL_HORIZON_KEYS :1024 = tuple(_k for _k in BUCKET_ORDER if _k != "news")
   → ①-6「順序由 BUCKET_ORDER 導出、不得手排」✓（BUCKET_ORDER 在 shared/macro_buckets.py:74）
EVIDENCE_COLUMNS = 5 欄（ui/helpers/macro/beginner_view.py:795）✓ 與 ①-3「5 欄」相符
render_mid_cycle_section（ui/tab1_macro_midcycle.py）✓  _ZS_INDICATORS ✓
CONCLUSION_HEADING  page_02_health.py:623 ✓ / page_05_settings.py:509 ✓
EVIDENCE_HEADING    page_05_settings.py:513 = "### 🧾 ② 依據 — 逐項狀態" ✓
BACKFILL_GATE_LABEL :459 = "🗄️ 載入手動補資料" ✓  MAINTAIN_GATE_LABEL :462 ✓  MANUAL_GATE_LABEL :472 ✓
```
**⑤ 的 6 個區塊表行（`:27`–`:30`）也逐行重印無誤。**

### 3.4 不確定那 1 項（⑤-8）
✅ 規格 `:231` 有「⚠️ **待確認（不自行拍板）**」，且**寫明不確定的是什麼**
（「線框 Tab 05 沒有這一塊」＋「選股池歸 ⑤ 還是歸 ④」），並在 `DECISION_LOG` F-5 立案。
實作原文佐證：`page_05_settings.py:1756-1757` 逐字「線框沒有給這一塊位置（(D-5)）…
它裁的是『這一塊放在哪、怎麼收』，不是『線框有沒有它』」✓ **與規格的敘述一致。**

### 3.5 ⛔ 但 R9 那份清單本身不是窮舉 —— 見第 11 節矛盾 A

---

## 4. 生產組「就地更正稽核一處」是否成立

### ✅ **成立。本組用 AST 獨立重跑，數字與歸屬完全一致。**
```python
ast.parse(page_01_macro.py) → 取每個 ##### 行號的最內層函式
1281 -> (1235, 1313, '_detail_long')        🌳 長期座標   × 1
1365 -> (1347, 1506, '_detail_short')       🎯 短線雷達   ┐
1408 -> (1347, 1506, '_detail_short')                     ┘ × 2
1539 -> (1512, 1567, '_detail_inflection')  ⚠️ 拐點警報   ┐
1550 -> (1512, 1567, '_detail_inflection')                ┘ × 2
→ 5 個 ##### 分佈在 3 塊裡（長期 1 ／ 短線 2 ／ 拐點 2）
```
而詳細區的五塊是 `_DETAIL_TITLES`（`:1028-1033`：🌳 長期座標／📈 中期循環／🎯 短線雷達／
⚠️ 拐點警報／🤖 AI 景氣判斷總結），由 `_DETAIL_ZONE`（`:1937-1948`）
＝ `(*_DETAIL_HORIZON_KEYS, _DETAIL_AI_KEY)` 導出，在 `:1970-1986` 逐塊 `safe_section` 渲染。
**兩者層級不同、數字碰巧都是 5 —— 生產組的更正正確，R2 那句「詳細區其下 5 個具名小節」確實會被誤讀成「詳細區＝那五塊」。**

---

## 5. R1–R14 逐條

| R | 生產組稱 | 本組實測 | 結論 |
|---|---|---|---|
| **R1** | 修了 | ④-4 標籤實為 **新建** ✓；「§3.1 全活」字樣在 `spec/UI_SPEC.md` **0 命中** ✓；`transactions[]` 8 欄在盤點表 `:1170-1177` 逐欄 `~~活的~~ → **只寫不讀** ｜ **內部**` ✓；`.position.*` 4 欄（`:1178-1181`）活的／UI ✓ | **實質成立**；**但出處行號指錯，見矛盾 B-1** |
| **R2** | 修了 | `page_04_portfolio.py:557 _FORM_KEY: str = "v04_portfolio_rebalance_form"`／`:560 _SK_APPLIED: str = "v04_portfolio_applied_plan"`／`:575 _DEFAULT_CORE_PCT: int = 70` **三行逐字命中**；`grep -n "portfolio_core_pct" page_04_portfolio.py` → **只有 `:1294`／`:1476`，兩處皆註解／docstring** ✓；`ui/helpers/session.py:79 "portfolio_core_pct": 75,` ✓；`:555 # ⚠️ 刻意**不**沿用舊 ④ 的鍵：…` ✓ | **全部成立** |
| **R3** | 修了 | 見 2.3 | **成立** |
| **R4** | 修了 | 見 2.3；`page_02_health.py:1317-1319` 逐行命中 | **成立** |
| **R5** | 修了 | `:2523-2524` 逐行命中，**但那兩行讀的路徑與渲染端不同** | ⛔ **見矛盾 C-1**；另 `:2529-2532` 的行號**差一格**（見 B-2） |
| **R6** | 進待裁示 | F-1 的三個行號全部逐字命中：`:1633 _mom_pct = _d.get("prev") …`、`:1648 return {…"value": f"{_pct:+.2f}%",`、`:1546 _breadth_card(_ind),`；且 `_ind = st.session_state.get(_SK_IND)`（`:1534`）**確實就是 `indicators`** | **兩邊陳述皆屬實，未選邊 ✓** |
| **R7** | 進待裁示 | `ui/helpers/portfolio_perf.py:34-37` 內 `fetch_usdtwd_frame(...)` **無 gate** ✓；`repositories/hot_money_repository.py:758-759` 逐字 `@register_st_cache` ＋ `@st.cache_data(ttl=TTL_10MIN, show_spinner=False)` ✓；`page_04_portfolio.py:1102-1106 REASON_PERF` 原文確含「一渲染就打一次匯率 API、還會落盤快取」與「每次互動一次網路往返」 ✓ | **兩邊陳述皆屬實，未選邊 ✓** |
| **R8** | 修了（改規則） | `grep -c "^[A-Z_][A-Z_0-9]*\s*:" shared/ui_control_labels.py` → **6**，逐行即規格 `:26` 所列那六個 ✓（該檔 41 行）；`DIVCAL_GATE_LABEL`（`page_04_portfolio.py:802`）／`DIAG_GATE_LABEL`（`page_05_settings.py:392`）／`FETCH_DIAG_GATE_LABEL`（`:484`）確實**都不住在共用檔** ✓；`NAV_GATE_LABEL`（`:411`，用於 `:1284`/`:1290`）✓；`where_to_find`（`ui/helpers/story_nav.py:464`）＋ key `pf_add`（`:248`）✓，`page_02_health.py:1085` 真的在用 ✓ | **成立**；**但規格自己的「一律」還有 4 塊沒照做，見 B-4** |
| **R9** | 修了 | 見第 3 節 | **三類分得對；清單本身非窮舉，見矛盾 A** |
| **R10** | 修了 | 甲 9 項 ／ 乙 4 項 ／ 標題寫 13 —— `grep -cE '^[0-9]+\. '` 分別回 **9** 與 **4** ✓；乙-4「全站總經權重編輯」的缺項寫「需新建寫入路徑，不是四件不齊」✓ 與段標題「四件齊，另有理由」一致 | **數字與內容對得起來 ✓（M18／R10 的病沒復發）** |
| **R11** | 修了 | ①-4 已就地寫「實際鍵 `v01_macro_risk_radar`，**盤點表 0 命中**」✓；§1 `:23` 已升成通則 ✓；實測 `grep -c "v01_" inv/DB_INVENTORY.md` → **0**（正控 `v03_research_batch_rows` → 2） | **成立** |
| **R12** | 修了 | `app.py` 九行逐行重印：`:581-587` 為 9 格 `st.tabs`（5 正式＋4 預覽）✓；`:636 render_market_overview()`／`:648 render_fund_grp_health_tab()`／`:662 render_fund_research_tab()`／`:673 render_portfolio_tab()`／`:688 render_settings_diag_tab()`／`:720 render_holdings_health()`／`:728 render_settings_and_diagnostics()`／`:752 render_fund_research()`／`:776 render_asset_allocation()` **全部逐字命中**，且表格四列的配對正確（②→720、⑤→728、③→752、④→776） | **成立，並列誤讀已不可能發生** |
| **R13** | 修了 | 見 2.1，四個數字本組重跑全部重現 | **成立** |
| **R14** | 修了（選說明） | `awk 'NR==590' ui/views/page_04_portfolio.py` → `BLOCK_MIX: str = "核心 ／ 衛星現況 vs 建議"` **逐字命中** ✓ | **成立** |

---

## 6. ③ 定為 4 塊是否成立

### ✅ **成立。三件事本組逐行印過。**
```
ui/views/page_03_research.py
2741    safe_section(BLOCK_FORM, _render_search_form)          ← BLOCK_FORM  :375 = "搜尋條件"
2747        safe_section("還沒開始搜尋", _render_not_searched_yet)   ← 空狀態（取代後三塊）
2751    safe_section(BLOCK_RESULTS, _render_results)           ← :379 = "搜尋結果"
2753    safe_section(BLOCK_DEEP, _render_deep_dive)            ← :404 = "單一基金深度"
2755    safe_section(BLOCK_BATCH, _render_batch)               ← :407 = "批次分析"
```
**檔頭兩句逐字**：
```
:8   **同一批恢復線框的「選定後展開」gate** —— 本頁**四塊全部是真資料或誠實的空狀態**，
:139 資料從哪裡來（**三塊都已接上真資料**）
```
**「量的不是同一件事」這個讀法有檔案結構支持，不是事後合理化**：`:139` 底下那一整節
依序處理 **單一基金深度**（`:141-168`）、**搜尋**（`:169-200`）、批次，**正好三塊**；
而 `:6` 劃掉的舊句「仍是灰態的只剩「搜尋結果」一塊」＋ `:7` 的「✅ 2026-09-08 搜尋結果也接上了」
說明 `搜尋結果` 是三塊中最後接上的那一塊。
⚠️ **另一種讀法（`:139` 是沒跟著更新的舊標題）無法從檔案本身排除** —— 本組並陳，不選邊。
✅ `DEEP_DIVE_CARDS`（`:410`，3 項）／`DEEP_DIVE_TABLES`（`:412`，2 項）／`DEEP_DIVE_PROVENANCE`（`:414`）
與規格 ③-2 的「3 卡＋2 表」**逐字相符**。

---

## 7. ⑤-2 兩欄「不顯示」＋理由

### 7.1 理由三條的事實基礎 —— 逐條實測
```
ui/helpers/io/oauth_state.py:40  _sheet_id_secret = _safe_secret("POLICY_SHEET_ID", "")   ← 真讀取 ✓
ui/tab_manage.py:68  return None, "找不到政策 Sheet ID(請先在 Tab④ 選帳本,或設 POLICY_SHEET_ID secret)。"  ← 指引文案 ✓
ui/tab_manage.py:77  "v19.472:存進**獨立一本 Sheet(`POOL_SHEET_ID`,與持倉不同本)的 `_fund_pool` 分頁**"   ← 指引文案 ✓
ui/helpers/portfolio/policy_admin_section.py:164  # Account 使用者(設了 POLICY_SHEET_ID secret、…)原本  ← 註解 ✓
```
**`DECISION_LOG` C-3 的四處分類全部正確。**
📌 **一處措辭精度差異（不影響結論）**：規格 `:199` 把 `:68,77` 合寫成「兩處只把**名字**寫進指引文案」，
但 `:77` 寫的是 `POOL_SHEET_ID` 的名字、不是 `POLICY_SHEET_ID` 的；`DECISION_LOG` C-3 寫得較精確。

### 7.2 「值不列出」—— ✅ 掃過，兩檔一個 id 值都沒有
```
grep -oE '[A-Za-z0-9_-]{20,}' spec/UI_SPEC.md | sort -u      → 42 筆，全部是 Python 識別字／session 鍵／測試檔名
grep -oE '[A-Za-z0-9_-]{20,}' spec/DECISION_LOG.md | sort -u →  8 筆，同上
正控：同一條 regex 對 services/nav_history_gs.py 有命中（該檔確有 baked id；本報告不列出其內容）
```
**沒有任何 sheet id／token／金鑰的值或片段。**

### 7.3 ⛔ 但 ⑤-2 的「來源」描述與實作對不上 —— 見矛盾 C-2

---

## 8. 決策日誌是否誠實

### ✅ 格式與計數
- A 段 **6 列**（`:15-20`）＋ B 段 **7 列**（`:28-34`）＝ **13 條決策** ✓ 與自稱相符。
- 五個欄位（日期／決策／誰決定／理由／出處）**13 列全部填滿，無空格**。
- F 段 **7 列**（`:123-129`）＝ 7 條待裁示 ✓。
- A-15／A-16 的出處 `inv/DB_INVENTORY.md:181-200`／`:127-140` **本組實測命中客戶原話逐字**
  （`:183`「顆粒度：**看欄，不看表**…」、`:129`「『有 production 讀取』＝ 資料到得了消費者。」）✓。

### ✅ 「scope 外」與新規則
- B1 標了 **scope 外**、C-2 整節交代 ✓；B2 立了新規則「scope 外改動一律先報再動」✓。
- 📌 **登記一件事實**：`grep -i "scope" spec/UI_SPEC.md` → **0 命中**。
  該標記只存在於 `DECISION_LOG`，規格本文的 ③-1 那句沒有帶標記。
  客戶裁示原文是「標『scope 外』，**寫進決策日誌**」—— **是否也該標在規格裡，取決於怎麼讀那句話，本組不裁決。**

### ⚠️ 七條待裁示有沒有「把該做的事推進去逃避」
逐條讀過：**F-1～F-6 都是「兩邊讀法並陳＋誰該決定」的形狀，且五條都先做了處置再送審**
（F-1 保留原標籤、F-2 不改 main、F-3 不改名、F-4 用暫行判法、F-6 選了一把尺並寫明）——
**本組沒有找到把已可自行完成的事推進待裁示區的例子。**
📌 **F-7 是例外，性質不同**：它寫的是「`SPEC.md` 等其他治理文件本組完全沒掃 —— **查不到**」，
那是**射程揭露**，不是一個待決定的事項；放在「待裁示」表裡與其餘六條不同類。

### ⛔ 一處出處對不上 —— 見矛盾 B-3

---

## 9. 母法禁令（獨立重掃，未引用生產組自掃）

### 9.1 關鍵字掃描（兩檔全掃，逐行人工判讀）

> ⚠️ **下表第一列的字表已依客戶用詞規則收斂成描述**；本報告其餘任何位置**不出現買賣動作字面**，
> 除非是**加引號的引文**（第 9.1 表「逐行判讀」欄內的引號句即屬此類）。
| 詞 | UI_SPEC | DECISION_LOG | 逐行判讀 |
|---|---|---|---|
| （母法點名的五個禁用詞，此處為**掃描字表**，非本報告的敘述） | **0** | **0** | — |
| 一鍵再平衡 | 1（`:147`）| 1（`:18`）| **兩處都是禁令**：「⛔ **不出買賣動作、無一鍵再平衡鈕**」／「母法⛔嚴禁…與一鍵再平衡」 |
| 最佳配置／推薦 | 1（`:249`）| 1（`:18`）| **兩處都是禁令或排除理由**：乙-2 把「📐 建議資產水位」**排除**，理由逐字「＝母法⛔嚴禁的預設最佳配置推薦…**本規格比現況嚴**」 |
| 建議 | 2（`:150`／`:249`）| 1（`:115`）| `:150`／`:115` 是**引述線框常數** `BLOCK_MIX: str = "核心 ／ 衛星現況 vs 建議"` 並說明**刻意不跟著改名**；`:249` 同上 |
| 換股 | 2（`:245`／`:258`）| 1（`:83`）| 皆為被排除區塊的名字（甲-9） |
| 買進／賣出／出清／加碼／減碼／停利／停損／現金水位／布局／進場／出場／該買／該賣 | **0** | **0** | — |

### 9.2 語意閱讀（主要手段）—— 34 塊的「回答」與「規則」逐行讀過
**沒有找到「沒踩關鍵字但語意是買賣建議」的句子。** 34 個「回答」全部是描述性的
（例：④-1「核心與衛星各佔多少、離目標多遠」、②-4「每月領多少、跟同類型比好不好」、
④-7「景氣位階對這組曝險的意義」）。
⚠️ **未涵蓋範圍**：本節只讀 `spec/` 兩檔，**沒有讀被規格指向的實作文案**
（例如 `page_01_macro.py:2067` 的頁面 caption「現在市場環境該進攻還是防守？」）——
**那些字在不在母法射程內，不在本輪受檢對象內。**

### 9.3 ④ 再平衡試算 —— brief 指定的兩條，逐字確認仍在
```
spec/UI_SPEC.md:152  - 來源：目標比例**由使用者輸入**（**新建**：…）
spec/UI_SPEC.md:153  - 規則：三欄皆使用者填：目標核心比例（滑桿）…⛔ **不出執行鈕**
spec/UI_SPEC.md:147  （④-1）⛔ **不出買賣動作、無一鍵再平衡鈕**
spec/UI_SPEC.md:180  （④-7）⛔ **不出買賣動作**
```
**兩條都寫死著。** 實作側佐證：`page_04_portfolio.py:575 _DEFAULT_CORE_PCT: int = 70` 是**滑桿預設值**，
不是系統算出來的「建議值」。

---

## 10. 尺寸與裁示 6

### 10.1 四法量尺寸（⚠️ 本機 `LANG` 與 `LC_ALL` 皆為空 —— 已實測確認 `wc -m` 會退化）
| 檔 | `wc -l` | `LC_ALL=C.UTF-8 wc -m` | python `len()` | `wc -c` | 預設 `wc -m`（退化） |
|---|---|---|---|---|---|
| `spec/UI_SPEC.md` | **265** | **16,625** | **16,625** | **33,099** | 33,099（＝位元組數） |
| `spec/DECISION_LOG.md` | **144** | **11,352** | **11,352** | **20,738** | 20,738（＝位元組數） |

**生產組自稱的 265 行／16,625 字元、144 行／11,352 字元 —— 四法互相印證，完全相符。**
⚠️ 預設 `wc -m` 確實靜默退化成位元組數（33,099 vs 16,625），**brief 的警告成立。**

### 10.2 裁示 6：負控字串
```
spec/UI_SPEC.md      : 舊負控 0 ／ 其三個子字串片段各 0 ／「負控」二字 0
spec/DECISION_LOG.md : 舊負控 0 ／ 其三個子字串片段各 0 ／「負控」二字 3（**只出現詞，沒有出現字串**）
本組自訂隨機負控      : 兩檔皆 0
正控（證明 grep 會命中）: 同一條 grep 在 audit/inv 的 5 個 .md 檔命中
```
✅ **裁示 6 達成。** `DECISION_LOG:5` 並已就地寫明「負控為本組自訂隨機串，未列出；
掃描時已先排除本檔與 `spec/UI_SPEC.md` 自身」——**自我排除也做了。**

---

## 11. 矛盾清單（⛔ 不裁決）

### A｜R9 的那份清單不是窮舉：② 有 8 個線上真的在渲染的頂層區塊，兩份清單都 0 命中

- **A 說**（`spec/UI_SPEC.md:27` 逐字）：`四件缺一 → 改列排除清單。`
- **A2 說**（同檔 `:234` 逐字）：`**13 個區塊被排除**（甲 9 ＋ 乙 4），數字與項目對得起來。`
- **B 說**（本組實測，`grep -n "safe_section(" ui/views/page_02_health.py` ＋ 人工逐行）：
  `render_holdings_health()`（`:1793` 起）的頂層序列是
  ```
  1839  safe_section("診斷條件", _render_filter_form)      ← 規格與排除清單皆 0 命中
  1844  safe_section("尚未設定持倉", _render_no_holdings)   ← 空狀態
  1850  safe_section("結論", _render_conclusion)            ← ②-4
  1851  safe_section("組合健康總分", _render_health_score)   ← 甲-1
  1852  safe_section("警示卡片", _render_alert_cards)        ← ②-1 ＋ ②-2 ＋ 甲-2
  1853  safe_section("逐檔體檢表", _render_health_table)     ← ②-3
  1858  _render_delegated_sections()                        ← 其下再 7 個 safe_section
  ```
  而 `_render_delegated_sections()` 底下逐行是：
  ```
  1750 safe_section("基金體檢",     …)    1751 safe_section("持倉互斥避險", …)
  1757 safe_section("真實收益矩陣", …)    1758 safe_section("持股相關性矩陣", …)
  1759 safe_section("−2σ 超跌警示", …)    1763 safe_section("配置回測",     …)
  1790 safe_section("AI 跨檔評論", …)
  ```
  **這 8 個名字在 `spec/UI_SPEC.md` 全部 0 命中**（正控：`逐檔體檢表`→1、`換股顧問`→2、
  `組合健康總分`→1、`配息月曆`→1；負控 0）。
- **兩者不能同時為真。**
- 📌 **並陳另一半**：規格**沒有一句話宣稱自己窮舉了 `origin/main` 的所有區塊**
  （R2 的 R9 已就此並陳過兩種讀法）。**但這一輪多了一件新事實**：
  R9 的原始清單是靠 `grep "詳細區\|雷達\|流動性\|…"` **一份字表**掃出來的，
  字表裡沒有這 8 個名字 —— **所以它們不是「射程外」，是「那條指令結構上看不到」。**
  ⚠️ 另有兩個同型的：① 的載入閘門 `applied_form(_FORM_KEY, …)`（`page_01_macro.py:2082-2088`，
  帶自己的 `st.caption`）同樣是規格 0 命中的渲染物，而 ③ 的同型物（`BLOCK_FORM`）
  **依客戶裁示 5 被補成了 ③-4**。**同一種東西在 ③ 是區塊、在 ①② 不是。**

### B｜出處與行號的四處對不上（全部是**指錯位置**，不是內容錯）

**B-1｜`DECISION_LOG` R1 的盤點表出處指到別的東西**
- **A 說**（`DECISION_LOG:102`）：`transactions[]` 8 欄…（`inv/DB_INVENTORY.md:1103-1110`）
- **B 說**（本組 `awk` 重印 `inv/DB_INVENTORY.md:1103-1110`）：那 8 行是
  `> ⚠️ **2026-09-16 標題更正（…起因：盤點稽核組矛盾 6）**` 起算的 **§3 節標題更正 blockquote**，
  一行 `transactions` 都沒有。**真正那 8 欄在 `:1170-1177`。**
- **兩者不能同時為真。** ⚠️ **R1 的實質內容（8 欄逐欄「只寫不讀 ／ 內部」）本組已在 `:1170-1177` 驗證為真**——
  **錯的只有座標。**

**B-2｜`DECISION_LOG` R5 的「各自獨立渲染」行號差一格**
- **A 說**（`DECISION_LOG:106`）：`…各自獨立渲染（`:2529-2532`）`
- **B 說**（逐行重印 `ui/views/page_04_portfolio.py`）：
  `2529 return`／`2530 if _has_holdings:`／`2531 render_concentration_summary(_funds)`／
  `2532 if _has_sectors:`／`2533 render_sector_concentration_summary(_funds)`
  → **獨立渲染是 `:2530-2533`**；`:2529` 是空狀態分支的 `return`，而 `:2533`（產業那支的呼叫）**被切在範圍外**。
- **兩者不能同時為真。**

**B-3｜`DECISION_LOG` B6 的出處不支持它自己**
- **A 說**（`DECISION_LOG:33`）：`B6 … R1–R14 中屬既有裁示機械後果的 12 條就地修掉…
  | **AI 總管**（依客戶裁示一-5／一-6 的分工）| … | §D、§E`
- **B 說**（客戶裁示一逐條）：**一-5 是「`page_03_research.py` 先查實作、以實作為準統一數字」**，
  **一-6 是「負控字串不得寫進文件」** —— **兩條都沒有講 R1–R14 的處置，也沒有講任何「分工」。**
  （裁示一裡與 R1–R14 最接近的是 **一-2**，但它只管 R9 那一批，已由 B3 承接。）
- **兩者不能同時為真。**

**B-4｜規格自訂的「一律」，自己有 4 塊沒照做**
- **A 說**（`spec/UI_SPEC.md:26` 逐字）：`⚠️ 空狀態指名控制項一律引**該控制項自己的 SSOT 常數並寫出它住哪個檔**，不手抄字面。`
- **B 說**（本組逐塊讀 34 個「空狀態」）：
  **①-7／①-9／①-10 寫「指到載入鈕」，①-11 寫「指到**那顆鈕實際用的變數**」——
  四塊都沒有寫出常數名，也沒有寫出檔名。**
  實際的東西存在且找得到：`ui/views/page_01_macro.py:263 def _where_to_load()`（前三塊）、
  同檔 `:248 _AI_BTN_FIRST` / `:249 _AI_BTN_AGAIN`（①-11）。
  **對照組**：①-1／②-3／④-5／⑤-1／⑤-2／⑤-3／⑤-6／⑤-7／⑤-8 **九塊都照做了**（常數＋檔名俱全）。
- **兩者不能同時為真**（「一律」與「四塊沒做」）。

### C｜兩處「規格說到得了／實作說到不了」

**C-1｜④-6 標「沿用（兩欄都到得了）」，而它的前提判斷讀的是一條沒有東西的路徑**
- **A 說**（`spec/UI_SPEC.md:174` 逐字）：
  `- 來源：`.moneydj_raw.top_holdings`／`.sector_alloc`（**沿用**：兩欄都到得了，且各自獨立判有無…）`
  ＋（`DECISION_LOG:106` R5）`並補上逐欄依據：page_04_portfolio.py:2523-2524`
- **B 說**（本組實測，五條指令）：
  1. `awk 'NR==2523,NR==2524'` → `_has_holdings = any((_f.get("moneydj_raw") or {}).get("top_holdings") …)`
     `_has_sectors  = any((_f.get("moneydj_raw") or {}).get("sector_alloc") …)` —— **扁平路徑**。
  2. 它委派的渲染端讀的是**巢狀路徑**：`ui/helpers/portfolio/concentration.py:45-46`
     `_h = ((_f.get("moneydj_raw") or {}).get("holdings") or {})` / `_tops = _h.get("top_holdings")`；
     同檔 `:93-94`、`:216-217` 同樣。
  3. `moneydj_raw` 的內容是整包 fetch result（`ui/helpers/portfolio/load.py:240 "moneydj_raw": pf_raw,`），
     而持股在 `repositories/fund/fund_orchestration.py:1313 result["holdings"] = holdings_data`；
     `repositories/fund/nav_metrics.py:970-977 def fetch_holdings(...)` 的 docstring 逐字
     `{"data_date":…, "sector_alloc": […], "top_holdings": […]}` —— **它們是 `holdings` 的子鍵。**
  4. `grep -rn 'result\["top_holdings"\]' --include=*.py .` → **0 命中**（負控同批 0）。
  5. `grep -rn 'moneydj_raw") or {}).get("top_holdings")' --include=*.py .` → **全 repo 只有 `page_04_portfolio.py:2523-2524` 兩行**；
     其他每一個消費端（`page_02_health.py:1317`、`ui/helpers/fund_grp_health/ai.py:176-177`、
     `services/ai_service.py:326`、`concentration.py`）**都走巢狀路徑**。
  → 依此，`_has_holdings` / `_has_sectors` 恆為假 → `:2526-2528 not_ready(…)` → `:2529 return`，
  **兩欄都到不了畫面。**
- **兩者不能同時為真。**
- 📌 **規格自己記下了這個形狀差異卻沒有改結論**：`:174` 同一行寫著
  `⚠️ 與 ②-2 形狀不同，那邊走 `.holdings.*``。**它看到了差異，標籤沒有跟著動。**
- ⚠️ **本組的限制**：**沒有啟動 Streamlit、沒有跑測試**，以上全部是靜態讀碼。
  「真實 session 下 `moneydj_raw` 會不會從別的路徑帶一個扁平 `top_holdings` 進來 —— 查不到。」

**C-2｜⑤-2 的「來源」寫的是一份逐項金鑰狀態清單，而 ⑤-2 的實作自陳那份清單不在它這裡**
- **A 說**（`spec/UI_SPEC.md:192` 逐字）：
  `- 來源：`secrets.*` 共 9 個（**沿用（部分）**，**值不列出**）—**顯示 7**：FRED／GEMINI／FINMIND key＋NAV／macro_weights sheet id＋service account／proxy；**不顯示 2**：…`
- **B 說**（本組實測）：⑤-2 的實作是 `ui/views/page_05_settings.py:1737 safe_section(BLOCK_KEYS, _render_keys)`，
  而 `_render_keys`（`:1334-1396`，AST 界定）整支只做兩件事 ——
  `:1355 render_policy_admin_bridge(sheet_client=None)` 與 `:1385` 的 gate 之後 `:1396 render_fetch_diag_from_session()`；
  它自己的 docstring `:1350-1353` **逐字**寫著
  `⚠️ **「API 金鑰狀態 / NAS Proxy 測試」仍住在 \`render_data_guard_tab()\` 深處**…
  故本塊只承接兩個已可承接的對象。**這是已知缺口，不是漏做。**`
  而那份清單實測在 `ui/tab5_data_guard.py:1175-1176`
  `_key_targets = ["FRED_API_KEY", "GEMINI_API_KEY", "FINMIND_TOKEN", "PROXY_URL", "GOOGLE_SHEET_ID"]`，
  AST 歸屬 → `render_data_guard_tab`（`:192-1685`），**那是 ⑤-3 委派的對象**
  （`page_05_settings.py:1191-1251 _render_source_health`）；
  另兩個（`google_service_account` / `macro_weights_sheet_id`）在同檔 `:1724` / `:1734`，
  AST 歸屬 → `render_nav_accumulation_status`（`:1687-1797`）。
- **兩者不能同時為真。**
- 📌 **同時登記兩件並陳事實**：(a) 該清單裡的名字是 **`GOOGLE_SHEET_ID`**，不是規格寫的「NAV sheet id」；
  (b) ⑤-2 的**空狀態**那一件寫的是 `FETCH_DIAG_GATE_LABEL`，**與 `_render_keys` 的 gate（`:1385-1391`）完全吻合** ✓ ——
  **同一塊裡「空狀態」對得上、「來源」對不上。**

### D｜④ 的「畫面順序」與實作順序不一致（三格）

- **A 說**（`spec/UI_SPEC.md:144` 逐字）：
  `**畫面順序**：④-1 → ④-2 → ④-3 → ④-4 → ④-5 → ④-6 → ④-7（動作卡區另含一張永久灰卡，見排除清單甲-9）。`
- **B 說**（逐行重印 `ui/views/page_04_portfolio.py:2774-2789`）：
  ```
  2775 safe_section(BLOCK_MIX,  _render_mix)            ← ④-1
  2777 safe_section(BLOCK_FORM, _render_rebalance_form) ← ④-2
  2778 safe_section("動作卡",   _render_action_cards)    ← 內含 ④-5（見下）＋ 甲-9
  2781 safe_section(BLOCK_POLICY,       _render_policy) ← ④-3
  2783 safe_section(perf_block_label(), _render_perf)   ← 乙-1
  2785 safe_section(BLOCK_CONCENTRATION,_render_concentration) ← ④-6
  2787 safe_section(BLOCK_MACRO_LINK,   _render_macro_link)    ← ④-7
  2789 safe_section(BLOCK_LEDGER,       _render_ledger)        ← ④-4
  ```
  `_render_action_cards`（`:1625-1668`）只有兩格：`:1656 switch_block_label()`（甲-9）與
  `:1668 _render_dividend_calendar_card()`（＝ ④-5 配息月曆，`BLOCK_DIVIDEND_CAL` 在 `:611`）。
  → **實作序為 ④-1 ／ ④-2 ／ ④-5 ／ ④-3 ／ ④-6 ／ ④-7 ／ ④-4。**
- **兩者不能同時為真**（④-5 在實作是第 3 位、規格寫第 5 位；④-4 在實作是**最後一位**、規格寫第 4 位）。
- 📌 **並陳另一半**：規格那行的括號**確實提到了「動作卡區」**，只是沒有把它放進箭頭序列；
  也可以讀成「箭頭序列只排本規格的七塊、動作卡另計」。**兩種讀法一併登記。**
- ✅ **對照組：①／③／⑤ 三頁的畫面順序本組逐行對過，全部與實作一致**（①`:2153→2157→2171→2185→2192`；
  ③`:2741/2751/2753/2755`；⑤`:1721/1723/1731/1734/1737/1748/1751/1763`）。

### E｜同一份規格對「幾張卡算幾個區塊」用了兩把尺

- **A 說**（`spec/UI_SPEC.md:258` ＋ `DECISION_LOG:80`）：① 詳細區底下那 5 個 `#####`
  **是塊內部的分節、不是區塊**，理由是 `page_01_macro.py:1136-1141` 的階層規則。
- **B 說**（實測）：② 的 `safe_section("警示卡片", _render_alert_cards)`（`:1852`）底下是**一次**
  `render_cards([_eat_card, _lag_card, _shadow_card])`（`:1585`）的三張卡，
  而規格把其中兩張**各自寫成一個獨立區塊**（②-1 吃本金警示、②-2 影子基金重疊），
  第三張（衛星連續落後）**寫成獨立的排除項甲-2**。
- **兩者不能同時為真**（在 ① 用的是 `safe_section` 顆粒度，在 ② 用的是卡片顆粒度）。
- 📌 **並陳另一半**：`DECISION_LOG` F-6 已經就「分界標題算不算區塊」立了一條待裁示，
  **但它問的是標題，沒有問卡片顆粒度** —— 本項不在 F-6 的射程內。

---

## 12. 查了但沒問題的（只寫命中不寫清白，看不出這把尺有沒有往內用）

**逐塊／逐條查過、結果無誤的：**

1. **34 塊四件齊全** —— 34 塊全查，136 個小標無一缺漏、無一佔位（第 1 節）。
2. **標籤計數四個數字** —— 本組重跑 `grep -o`，19／5／6／6／36／34 全部重現（第 2.1 節）。
3. **標籤 vs 盤點表「誰讀它」** —— 24 個沿用／沿用（部分）來源逐一回查，**沒有一個落在「內部」或「無」上**（第 2.2 節）。
4. **R3（②-1）三層** —— `services/health/dividend.py:343/348/353` 逐行，三層與規格逐字相符。
5. **R4（②-2）兩欄** —— `page_02_health.py:1317-1319` → `:1336` → `:1580` → `:1585` 全鏈打通。
6. **②-3 九欄** —— `HEALTH_TABLE_COLUMNS`（`page_02_health.py:278-281`）逐字就是規格寫的 9 欄；
   「五桶評等」整欄恆 ⬜ 由同檔 `:1402` 逐字佐證。**「到得了 8 ／ 到不了 1」正確。**
7. **①-2 的 `color`／`series` 判定** —— `grep '\.get("color")'`／`'\.get("series")'` 對 `page_01_macro.py` **各 0 命中**，
   規格寫「到不了」**正確**。
8. **①-5 的 `source`／`fetched_at`** —— 全檔只有 `:1305` 讀 `source`，但 AST 歸屬 `_detail_long`，
   其 `_entries` 來自 `_SK_USLIQ`（`:1263`）**不是 `indicators`** → **不構成反例，規格正確**。
   同理 `:1395` 的 `prev` 來自 `_SK_RADAR`（`:1366`），**也不是 `indicators`** → F-1 的舉例
   （`:1633` 的 `ind["ADL"]["prev"]`，`_ind` 由 `:1534` 取自 `_SK_IND`）**是唯一正確的那個** ✓。
9. **R2 六個座標** —— `:557`／`:560`／`:575`／`:555`／`:1294`／`:1476` ＋ `ui/helpers/session.py:79` 全部逐字命中。
10. **R8 的「只有 6 個常數」** —— `shared/ui_control_labels.py`（41 行）module-level 常數 **恰好 6 個**，
    名字與規格 `:26` 所列**一字不差**；三個閘門常數確實都住在 `ui/views/page_0*.py`。
11. **九個閘門字面** —— `MACRO_LOAD_BTN_AGAIN`「🔄 更新總經資料」／`DIAG_GATE_LABEL`「🔭 查一次資料來源狀態」／
    `FETCH_DIAG_GATE_LABEL`「🔍 載入抓取診斷細節」／`BACKFILL_GATE_LABEL`「🗄️ 載入手動補資料」／
    `MANUAL_GATE_LABEL`「📖 載入使用手冊」／`MAINTAIN_GATE_LABEL`「🗄️ 載入資料維護與通報」
    —— **規格逐字引的六個「現為」字面，六個全部與原始碼一致。**
12. **R12 的九個 `app.py` 行號** —— 九行逐行重印全中，表格四列配對正確。
13. **R14 的 `:590`** —— 逐字命中。
14. **R10 的 13＝9＋4** —— 分段 `grep -c` 得 9 與 4。
15. **丙 11 塊／丁 13 塊** —— 數 `／` 分隔得 11 與 12(+③-4)=13。
16. **硬約束 1** —— `grep -rn "load_holdings_overview" --include=*.py .` → **全 repo 0 命中** ✓。
17. **甲-5** —— `get_history_df` 定義在 `services/fund_history.py:158`，
    除該檔 docstring 與 `tests/` 外**無呼叫端** ✓。
18. **乙-2 的兩個門檻常數** —— `shared/signal_thresholds.py:409/410` ＝ 1.75 / −1.0 ✓；
    「上游一律傳 `None`」由 `page_01_macro.py:785` 佐證 ✓。
19. **①-6 的「順序由 `BUCKET_ORDER` 導出」** —— `page_01_macro.py:1024-1026` ＋ `shared/macro_buckets.py:74` ✓。
20. **③-2 的「3 卡＋2 表」** —— `DEEP_DIVE_CARDS`（3）／`DEEP_DIVE_TABLES`（2）逐字 ✓。
21. **②-4 的 SSOT** —— `ui/helpers/fund/checkup.py::_compute_fund_health_kpis`；
    `page_02_health.py:683-690` 逐字含「`invest_twd × 年化配息率 ÷ 12`」與「⛔ **不用齊頭本金**」✓。
22. **③-1 的 `_fund_pool` / `load_series` 0 命中** —— `page_03_research.py` 全檔 **0 命中**，
    正控兩符號在 `repositories/pool_repository.py` / `services/nav_history_gs.py` 仍在 ✓。
23. **⑤-1 的 `nav_history` 七欄拆分** —— `inv/DB_INVENTORY.md:532-538` 逐列：
    `code`/`date`/`nav` 活的/UI ✓、`fund_name`/`source`/`recorded_at` 只寫不讀/內部 ✓。
    📌 **第 7 欄 `currency`（`:538`，活的/UI）規格兩份名單都沒提**，規格也沒宣稱窮舉 —— 登記，不列為矛盾。
24. **④-4 的 `.position.*` 4 欄** —— `inv/DB_INVENTORY.md:1178-1181` 活的/UI ✓（`:1182` 那一欄是只寫不讀，規格說「4 欄」正確）。
25. **④-3 六欄** —— `inv/DB_INVENTORY.md:385-390` 六欄全部活的/UI ✓。
26. **裁示 6 與 id 值** —— 兩檔全掃，見第 10.2／7.2 節 ✓。
27. **甲-7 的「零消費者」** —— 📌 **查過，兩種讀法**：`config/preset_funds.json`
    **確實有一個 service 層讀取端**（`services/fund_history.py:37 _load_default_funds()`），
    但它的下游 `get_history_df()` **非測試 caller 0**。
    依客戶裁定 2（「有 production 讀取」＝資料到得了消費者）「零消費者」**成立**；
    若照字面讀成「零讀取」則**不成立**。**兩種讀法一併登記，本組不選邊。**

---

## 13. 我沒查到什麼（一律寫「查不到」）

1. **真實 session 下的渲染行為 —— 查不到。** 沒啟動 Streamlit、沒跑任何測試。
   矛盾 C-1（④-6 路徑）與 C-2（⑤-2 來源）都建立在靜態讀碼上。
2. **線框 `docs/wireframes/*.html` 的原文 —— 查不到。** 規格與實作多處自稱「線框逐字」，
   本組**一個字都沒讀**，無法判斷那些「逐字」是不是真的逐字。
3. **盤點表自己的逐欄判定對不對 —— 查不到。** 本組只**引用** `inv/DB_INVENTORY.md`，
   沒有回頭重驗它的任何一列（客戶裁示一-4 指明由另一組重判）。
4. **客戶裁示一的原始檔 —— 查不到。** 六條裁示本組只有轉述，repo 與 scratchpad 內沒有找到逐字出處檔；
   B-3 的認定是拿 brief 所載的六條逐字去比對，**不是拿一份客戶原文檔。**
5. **M1–M20 與 R1–R14 當初判定本身對不對 —— 查不到。** 本輪只驗「這一版有沒有照著改」。
6. **「每一頁沒有第 N+1 個區塊」 —— 本組不宣稱。** `grep "safe_section("` 看不到動態組出的區塊，
   也看不到不走 `safe_section` 的渲染物（矛盾 A 裡 ① 的 `applied_form` 就是靠人工通讀撿到的，
   不是掃出來的）。**這份清單的完整性靠有人回頭讀，不靠任何一次掃描。**
7. **`SPEC.md` / `ARCHITECTURE.md` / `STATE.md` / `docs/*.md` 是否另有與本規格牴觸的敘述 —— 查不到。**
   本輪授權只到 `spec/` 兩檔與其對照材料。
8. **本報告未經第二組獨立複驗。** 本節所有「本組實測」皆為單組產出。
