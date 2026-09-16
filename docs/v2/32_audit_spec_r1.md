# `spec/UI_SPEC.md` 獨立稽核報告

**受檢對象**：`scratchpad/spec/UI_SPEC.md`（md5 `8cb513f17747bc6af91e3a31c8184d75`，量測日 2026-09-16）
**基準**：`origin/main = 9cbf03776f2a0ee6bdb5a649efb93352c40baba6`（`git rev-parse origin/main` 實測）
**產出者**：規格稽核組（單組產出）
**⛔ 本報告不裁決任何一條。** 每條寫成「A 說 X（出處）／B 說 Y（出處）／兩者不能同時為真」。
**零寫入**：未改 repo 任何檔案、未 commit／push／merge／fetch、未跑任何 workflow、
未連任何外部 API、**未讀寫任何 Google Sheets（連唯讀都沒有）**。
git 只用了 `rev-parse` / `show` / `archive`。工作樹 HEAD `d0c2a8d` 與 `pr829`~`pr834` 六個本地分支**全程未碰**。
**未列出任何 token、金鑰、sheet id、帳號或其片段**（過程中有一次 grep 輸出把某個 baked sheet id 印到終端，
本報告**刻意不轉載**，一律寫「值不列出」）。

**方法註記（2026-09-16 補）**：負控字串不得寫進文件；掃描時須排除自身檔案。

---

## 0. 方法（每條附正控與負控，並寫明它結構上看不到什麼）

**唯讀快照**：`/home/user/fund-specaudit`（`git archive origin/main`，**747 檔**）。
完整性自驗：`repositories/policy/v2.py` / `services/macro/weights_store.py` / `app.py`
三檔 md5 與 `git show origin/main:<path>` 逐一比對**相符**。

### 五種機制

| # | 機制 | 正控（應命中） | 負控（應不命中） | **結構上看不到什麼** |
|---|---|---|---|---|
| **M1** | **規格自身的機械結構解析**（自寫 parser：`### ` 切塊、`^- (來源\|規則\|空狀態\|回答)：` 抽四件、量每件字數） | 12 塊全部解出、四件全部抽到 | 第五種小標 → 0 | **只看得到「有沒有填、填了多長」，看不出內容對不對** —— 這就是為什麼還要 M2~M5 |
| **M2** | **逐塊回查盤點表**（`inv/DB_INVENTORY.md` 逐表逐欄比對狀態欄） | `indicators` → 15 命中 | `<負控串>` → 0 | ⚠️ **原本想用的負控（盤點組上一輪用過的那個串）在該檔有 9 命中** —— 那是盤點組自己的負控字串，**它同時是本檔的內容**。負控與受檢文件撞名 ＝ 負控失效，已換成本組自訂的新隨機串（`<負控串>`，依規則不寫進文件） |
| **M3** | **從消費端反查**（不信規格的宣稱，直接讀 `ui/views/page_0*.py` 與其委派對象，逐函式看它到底讀哪幾個 key） | `invest_twd` 在 `page_02_health.py` 15 命中 | 同上 → 0 | **只看得到字面出現的 key**；`getattr` 動態取名、以及「A 包 B、B 包 C」的間接封裝要人工逐層追 |
| **M4** | **別名 import 先列表**（先跑 `grep -rn "import .* as " ui/views/*.py` 再掃符號） | 抓到 `coverage_status as fetch_nav_coverage`（`page_05_settings.py:323`）、`NEAR_DIVIDEND_WARNING_PCT as _gap` | 同上 → 0 | **只涵蓋 `import ... as`**；`x = some_module.f` 這種賦值別名掃不到 |
| **M5** | **行號一律單獨印**（`git show origin/main:<path> \| awk 'NR==N'`，**不經 `grep -v`、不在一段輸出裡數序號**） | `services/fund_service.py:1095` → `s_hist = load_series(code, oauth_client=oauth_client)` | — | **只驗「那一行是不是它自稱的東西」**，不驗它所在函式還有沒有人叫得到 |

### 子字串陷阱的處置

掃 `color` / `series` / `prev` 一律用 `grep -o "\b<token>\b"` 取 **token 邊界**，不是裸子字串。
中文詞（`建議` / `推薦` / `水位`）命中後**逐行讀原文判讀**，不以命中數下結論 —— 見 §2 第 (4) 項。
`載入總經資料` 一掃命中 15 檔，那是它被包在更長字串裡的假陽性，已逐一判讀剔除。

### 本方法**結構上看不到**的（誠實劃界）

1. **runtime 走不走得到**：本組只做靜態閱讀，**一次 Streamlit 都沒跑**。
   所有「新 ⑤ 會呼叫 X」這類話，只代表**程式碼路徑存在**。
2. **`data_cache/*.parquet` 的實際列內容**：本機 `python3` **沒有 pandas／pyarrow**，
   且**不得 `pip install`** → 只能以位元組層明文比對推論（見 §2 第 (5) 項 M20）。
3. **規格的「應然」與程式的「實然」之間的界線**：本規格是要送客戶的草稿，
   它**可以**規定新行為。本報告一律把兩邊**並陳**，**不判定哪一邊該改**。
4. **「本規格沒有第 21 個問題」本組不宣稱** —— 下列 20 條是分類敘述，不是窮舉。

---

## 1. 七件事逐項結論

| # | 項目 | 結論 |
|---|---|---|
| **(1)** | 四件是否真的齊全 | **機械層面齊全，內容非佔位**（12/12）。但 **3 塊的「來源」不完整**：①-1 有一個來源未掛標籤、②-2 漏列主要來源、④-1 的「目標％」沒有任何來源欄位供給。見 M11 / M15 / M17 |
| **(2)** | 「沿用」標籤是否成立 | **12/12 都掛了「沿用」（機械確認）。但至少 5 塊的來源在盤點表上的狀態是「未落地」而不是「活的」**（①-1／①-2／①-3 的 `indicators`；②-1／②-2 的 `.metrics`／`.dividends`），另有 4 塊的具名欄位在對應的新頁**查不到讀取點**。見 M8 / M9 / M14 / M16 |
| **(3)** | 盤點表對應是否真實存在 | **`v01_macro_indicators` 確實被誠實標示了**（盤點表 0 命中，規格就地寫「盤點表未列」）✓。**但同型的第二筆沒有被標**：④-1「目標％」所需的 `portfolio_core_pct` 在盤點表 **0 命中**，規格未提、整行掛「沿用」。見 M11 |
| **(4)** | 母法禁令（獨立重掃） | **關鍵字命中 8 個詞，逐行讀後 0 條違規**。「推薦」「一鍵再平衡」「最佳配置」三個詞各 1 次、**全部在禁令句或排除清單裡**，與生產組自稱相符（本組獨立複核）。語意閱讀亦**未發現**沒踩關鍵字的買賣建議句。⚠️ 另見 M5：規格把「📐 建議資產水位」排除，但**那張卡在 `origin/main` 上是已渲染的**，並印「錢該放在哪一類資產的建議」—— 那是 repo 現況，不是本規格新增的 |
| **(5)** | 排除清單是否誠實 | **「逐檔體檢表」那一條確實有被另外標明「四件是齊的」** ✓，且本組**沒有找到第二條「四件齊卻混進四件不齊堆」的**。**但 L98 那句「以下才是四件不齊的」對至少 3 條不成立**（L109／L111／L112 的理由分別是「需新建路徑」「改用 ④-3」「需新建寫入路徑」，都不是缺四件中的任何一件）。另有 **8 個被排除的區塊，其排除理由與 `origin/main` 上的實況相反**。見 M1~M6 / M18 |
| **(6)** | 硬約束是否真的帶進去 | **四條全部帶進去了，逐條實測全部屬實** ✓。**第二條沒有被違反** —— ④-3 走 `_T7_State.ledger_json` 而不是 `_Ledgers`，正是盤點表 §3.1 指定的那條路。⚠️ 但 ④-3 給出的 8 欄清單與新 ④ 的「欄位是客戶 gate」守衛衝突（M12），且「無現成讀取路徑」一語在兩份上游文件裡寫法相反（M19） |
| **(7)** | 尺寸 | **112 行**（上限 120）✓。**字元數要看用哪把尺**：`wc -c` ＝ **8,845 位元組**；`LC_ALL=C.UTF-8 wc -m` ＝ **4,412 Unicode 字元**。生產組宣稱的「8,845 字元」**實際是位元組數**。兩種讀法都在 9,000 以下 ✓ |

---

## 2. 逐項實測（指令與真實輸出）

### (1) 四件是否真的齊全

**指令**（自寫 parser，repo 無關，直接吃規格檔）：

```
python3 -c "<parser>"   # ### 切塊 → ^- (來源|規則|空狀態|回答)： 抽四件
```

**真實輸出（節錄，12 塊全部 `missing=NONE`）**：

```
block count = 12
①-1 總經結論（一句話）   L15  missing=NONE
   來源 L16 len=129  `indicators`（§3.5，沿用）＋`_macro_weights.B(payload_json)`。⚠️ 新 ① 實際用鍵 `v01_macro_indicators`，
   規則 L17 len=41   彙總分數落在哪一段 cutoff → 印該段位階字；撐不住 → 只印分數、不給等級
   空狀態 L18 len=27 `尚未載入總經資料。` ＋ 指到「📡 載入總經資料」鈕
   回答 L19 len=21   現在市場整體在什麼位階，這個判斷撐不撐得住
… （其餘 11 塊同樣 missing=NONE，最短的一件 len=16、最長 len=136）
```

**逐塊人工判讀「有沒有真的填」**：**12 塊的「來源」全部具體到 `表.欄位` 或 `表.欄位群`**，
**沒有**任務說明舉的那種佔位（「來源：持倉資料」「規則：依情況顯示」）。
最接近佔位的是 ①-3 的「欄位以實作的 5 欄為準」—— 它**沒有列出那 5 欄的名字**，
但它指名了一個可解析的實作物件，**本組判定不算佔位**（那 5 欄的實際值見 M10）。

**三處來源不完整**，逐一見 **M11 / M15 / M17**。

### (2)「沿用」標籤是否成立

**機械確認（12/12 掛了沿用）**：

```
=== 來源 lines carrying 沿用 ===
L16 沿用 ✓   L22 沿用 ✓   L28 沿用 ✓   L36 沿用 ✓   L42 沿用 ✓   L50 沿用 ✓
L56 沿用 ✓   L65 沿用 ✓   L72 沿用 ✓   L78 沿用 ✓   L86 沿用 ✓   L92 沿用 ✓
標籤字頻：沿用 13 / 需新建路徑 2 / 查不到 5
```

**逐塊回查盤點表 ＋ 自查消費端（12/12 全查，這是本節的主要工作）**：

| 塊 | 規格宣稱的來源 | 盤點表狀態（`inv/DB_INVENTORY.md` 實測） | 新頁消費端（本組自查） | 判定 |
|---|---|---|---|---|
| ①-1 | `indicators` ＋ `_macro_weights.B` | `indicators` ＝ **未落地**（§3.5）；`_macro_weights.B` ＝ **只讀不寫**（§1.9） | `page_01_macro.py:203 _SK_IND = "v01_macro_indicators"`、`:310` 寫入 | **M16 / M17** |
| ①-2 | `indicators` 的 value/prev/unit/signal/**color**/**series** | 同上 ＝ 未落地 | `_ind_signal`（`:373`）讀 `signal`、`_fmt`（`:378`）讀 `value`＋`unit`；**`color` 全檔 1 命中且在註解、`series` 0 命中** | **M9 / M16** |
| ①-3 | 同 ①-2；「欄位以實作的 5 欄為準」 | 同上 ＝ 未落地 | `EVIDENCE_COLUMNS`（`beginner_view.py:795`）＝ 面向／判讀／讀數／說明／詳細在下方哪一段，**逐桶非逐指標、無「前值」欄** | **M10 / M16** |
| ②-1 | `.invest_twd`／`.policy_tier`／`.metrics` | `invest_twd` 活的、`policy_tier` 活的、**`metrics` 未落地**（§3.2） | `page_02_health.py`：`invest_twd` 15 命中、`metrics` 8 命中（`:1113`）、**`policy_tier` 0 命中** | **M7 / M8 / M16** |
| ②-2 | `.metrics`／`.dividends` | **兩者皆未落地**（§3.2） | 主要 adr 來源是 `moneydj_raw.moneydj_div_yield`（未列），`.dividends` 是第 3 層 fallback | **M15 / M16** |
| ③-1 | `_fund_pool` 6 欄 | **6 欄全部「活的」**（§1.7）✓ | `page_03_research.py` **沒有任何 `pool_repository` 呼叫**（唯一命中 `:2441` 是一句「不去選股池查名字」的註解）；`_fund_pool` 在別的畫面（`ui/tab_manage.py` 等）有 production 消費端 | 表層成立；新 ③ 無現成接線 |
| ③-2 | `nav_history` 4 欄 ＋ `load_series` | **全部「活的」**（§1.6）✓ | `services/nav_history_gs.py:818 def load_series(`；`services/fund_service.py:1094-1095` 實際呼叫 ✓ | ✅ **查了沒問題** |
| ④-1 | `.invest_twd`／`.policy_tier`／`.is_core` | **全部「活的」**（§3.2）✓ | `page_04_portfolio.py:2048 _tier = str(_f.get("policy_tier") or "").strip().lower()` ✓ | 三欄成立；但「目標％」無來源 → **M11** |
| ④-2 | `<保單分頁v2>` 6 欄 | **全部「活的」**（§1.2b）✓ | 讀路徑 `ui/helpers/cloud_io.py:156,325` 等（盤點表列，本組未逐一重跑） | ✅ **查了沒問題** |
| ④-3 | `_T7_State.ledger_json` → `transactions[]` 8 欄 | `ledger_json` **活的**（§1.3）；8 欄在 §3.1 **全部「活的（有落地）」**，欄名逐字相符 ✓ | 新 ④ 把這一塊維持灰態，理由是「欄位清單是客戶 gate」 | 8 欄名正確；**M12** |
| ⑤-1 | `nav_history` 3 欄 ＋ 別名 `fetch_nav_coverage` | **全部「活的」**（§1.6）✓ | `page_05_settings.py:323 coverage_status as fetch_nav_coverage`、`:1313 _coverage = fetch_nav_coverage()` ✓ | ✅ **查了沒問題** |
| ⑤-2 | `secrets.*` 9 欄 | **9 欄全部「活的」**（§4.1）✓ | 7/9 在新 ⑤ 或其委派的 `ui/tab5_data_guard.py` 有命中；**`POLICY_SHEET_ID` / `POOL_SHEET_ID` 兩處皆 0** | **M14** |

**`CALIBER_SWEEP.md` 的 3 條「方向 B（標活的但到不了畫面）」逐條對照** —— 這是任務特別點名要打的：

| 條 | 對象 | 規格有沒有拿它當「沿用」？ | 實測 |
|---|---|---|---|
| **B1** | `nav_history` 的**寫入端** `ui/helpers/nav_history_hook.py:138`（兩個入口都被註解掉） | **否。** 規格只用 `nav_history` 的**讀**（③-2 / ⑤-1），沒有宣稱任何寫入端 | `nav_history` 另有 2 個活的 UI 寫入端 ＋ 1 個 CI 寫入端，表本身仍是「活的」→ **③-2 / ⑤-1 不受 B1 影響** |
| **B2** | `data_cache/*.parquet` | **否，規格把它排除了**（L110：`data_cache/*.parquet` 唯一 production 讀取端在離線 script、產物本 repo 不讀）✓ | 與 B2 的結論方向一致 |
| **B3** | `config/preset_funds.json` | **否，規格把它排除了**（L110：`config/preset_funds.json` 讀回值零消費者）✓ | 本組獨立複驗 `get_history_df` → **非測試呼叫 0**（`services/fund_history.py:158 def get_history_df()`，另一處 `:10` 是 docstring） |

→ **3 條方向 B **沒有一條**被規格拿去當「沿用」。這一項本組查了，沒有問題。**

### (3) 盤點表對應是否真實存在

```
$ grep -c "v01_macro_indicators" inv/DB_INVENTORY.md      → 0
  正控 $ grep -c "indicators" inv/DB_INVENTORY.md          → 15
  負控 $ grep -c "<負控串>" inv/DB_INVENTORY.md → 0
$ grep -rn "v01_macro_indicators" --include=*.py .（排除 tests）
  → ui/views/page_01_macro.py:203:_SK_IND: str = "v01_macro_indicators"   （唯一一處）
$ awk 'NR==310' ui/views/page_01_macro.py
  →     st.session_state[_SK_IND] = fetch_all_indicators(fred_key)
```

→ **規格 L16 的三個宣稱全部屬實**：盤點表沒列 ✓、新 ① 實際用這個鍵 ✓、同一支 `fetch_all_indicators` 產出 ✓。
**這種情形有被誠實標示。** ✓

**但同型的第二筆沒有被標** —— 見 **M11**：

```
$ grep -c "portfolio_core_pct" inv/DB_INVENTORY.md         → 0
$ grep -rn "portfolio_core_pct" --include=*.py .（排除 tests，節錄）
  ui/helpers/portfolio/allocation.py:60: CORE_TARGET_SESSION_KEY = "portfolio_core_pct"
  ui/helpers/session.py:79:     "portfolio_core_pct": 75,
```

**規格其餘每一個 `表.欄位` 引用，本組都在盤點表裡找到了對應列**（見 (2) 的 12 列表格）。
**指不到的只有 `portfolio_core_pct` 這一個，而它根本沒被寫進規格。**

### (4) 母法禁令 —— 獨立重掃，未引用生產組的自掃結果

```
=== FORBIDDEN TERM SCAN（24 個詞，含任務指定 7 個 ＋ 本組自加 17 個）===
HIT 推薦=1  一鍵再平衡=1  最佳配置=1  再平衡=2  買進=1  賣出=1  建議=1  水位=1
未命中：建議買進 / 立即出清 / 應該加碼 / 必漲 / 目標價 / 加碼 / 減碼 / 出清 /
        停利 / 停損 / 應該 / 提高現金 / 布局 / 進場 / 出場 / 逢低 / 逢高
正控 「來源」=21    負控 <負控串>=0
```

**逐行讀，自己判（關鍵字表的鑑別力很低，這一步才是主要手段）**：

| 行 | 原文 | 判讀 |
|---|---|---|
| L69 | `⛔ **只陳述現況與偏離；不出買賣動作、不出「一鍵再平衡」鈕。**` | **禁令句**，不是建議 |
| L81 | `回答：每筆買進／賣出／配息的日期、金額、當時匯率與淨值` | **歷史紀錄的欄位描述**（帳本已經發生的事），不是動作指示 |
| L99 | `①「📐 建議資產水位」— 缺合法規則 — 母法⛔嚴禁預設最佳配置推薦；門檻恆為固定 +1.75／−1.00` | **排除清單 ＋ 禁令引述**。「建議資產水位」是被排除的**區塊名**（帶「」），「最佳配置推薦」出現在「母法⛔嚴禁…」這個句型裡 |
| L105 | `④「再平衡試算」— 規則落在母法紅線邊界 —…**須客戶裁決**` | **排除 ＋ 上呈**，不是建議 |

→ **0 條違規。** 生產組自稱的「三個詞各 1 次、都在禁令句裡」**經本組獨立複核為真**。

**語意閱讀（沒踩關鍵字但可能是買賣建議的句子）**：逐行讀完 112 行，
**沒有找到**「此時應提高現金水位」這一類的句子。
最接近紅線的是 ②-2 的「含息報酬 < 年化配息率 → **列入警示**」與 ④-1 的「印現況％、目標％、**偏離±％**」——
本組判讀**兩者都是狀態分類與差值陳述，沒有動作指示**；且 ④-1 自己在 L69 掛了禁令。

⚠️ **但要並陳一件本組查到的事**（**不裁決**）：規格把「📐 建議資產水位」排除掉，
而**那張卡在 `origin/main` 上是已經渲染的**，它印的是
`"value": (f"股票 {_a['equity']}％ ・債券 {_a['bond']}％ ・現金 {_a['cash']}％")`、
`"note": ("錢該放在哪一類資產的建議（不是「核心／衛星」那種角色分配）。…停利 Z ≥ …、加碼 Z ≤ …")`
（`ui/views/page_01_macro.py:812-815`，渲染於 `:2183`）。
**規格比現況嚴，不是比現況鬆。** 詳見 **M5**。

### (5) 排除清單是否誠實

```
排除 bullet 數 = 14 ✓（與生產組自稱一致）
但 14 個 bullet 裡點名了 20 個區塊：
  L99 n=1  L100 n=1  L101 n=1  L102 n=1  L103 n=1  L104 n=1  L105 n=1
  L106 n=5 ['⚡ ③ 例外','🔍 ④ 可信度','組合績效','穿透式持股／產業集中度','總經曝險聯動']
  L107 n=2 ['影子基金重疊','配息月曆']
  L108 n=1  L109 n=1  L110 n=2  L111 n=1  L112 n=1
```

→ **「14 條」是 bullet 數，不是被排除的區塊數（20）。** 讀者容易把它讀成後者。

**「四件是齊的卻被排掉」那一類**：規格已在 L98 另外標明「逐檔體檢表」那一條 ✓，
**本組沒有找到第二條同型的**（逐條讀完 14 個 bullet）。
**但 L98 的「以下才是四件不齊的」對至少 3 條不成立**（M18），
且 **8 個被排除的區塊，排除理由與 `origin/main` 實況相反**（M1~M6）。

**逐條查證結果（14 條全查，只寫命中不寫清白就看不出這把尺有沒有往內用）**：

| 行 | 區塊 | 本組查證 |
|---|---|---|
| L99 | 📐 建議資產水位 | ⚠️ **M5**。但「+1.75／−1.00」**屬實**：`shared/signal_thresholds.py:409 ZSCORE_STOP_GAIN_DEFAULT: float = 1.75`、`:410 ZSCORE_ADD_DEFAULT: float = -1.0`；且 `_card_allocation` 一律傳 `ndc_score=None`（`:786`），故「恆為固定」成立 ✓ |
| L100 | PPI／銅價歷史值 | ✅ **後半屬實**：`grep -c PPI services/macro/validation.py` → **0**、`COPPER` → **0** ⇒ `load_indicators_from_parquet` 確無此分支。⚠️ 前半「離線倉 0 列」字面與 `metadata.json` 衝突 → **M20** |
| L101 | ② 衛星連續落後 | ✅ **屬實**：`ui/views/page_02_health.py:16-22` 逐字給的兩個理由，其中 (b) 就是規格寫的那一個 |
| L102 | ②「🧾 ② 依據」區頭 | ✅ **屬實**：`### 🧾 ② 依據` 在該檔**只出現 1 次、在 module docstring 內**（`:57`）；模組層只有 `CONCLUSION_HEADING`（`:623`）被 `st.markdown` 渲染（`:932`），**沒有**任何 `② 依據` 的渲染 |
| L103 | ③ 搜尋結果 | 本組**查不到**反例（未深挖） |
| L104 | ③ 批次分析 | `v03_research_batch_rows` 確為 session key（`page_03_research.py:669`）；規格說的是它的**欄位清單**查不到，本組**未獨立驗證** |
| L105 | ④ 再平衡試算 | ⚠️ 與 ④-1 的「目標％」互相衝突 → **M11**；其「須客戶裁決」的上呈本身合規 |
| L106 | 5 個區塊 | ⚠️ **M3 / M4**：其中 4 個有完整實作與渲染點，第 5 個（組合績效）的真實理由是成本不是規則 |
| L107 | 2 個區塊 | ⚠️ **M1 / M2**：兩個都有實作，且 repo 明文寫「原因不是沒有來源」 |
| L108 | ⑤ 資料來源健康度 | ⚠️ **M6** |
| L109 | 全站 最近查過的基金 | ✅ **屬實**：`get_history_df` 非測試呼叫 **0**（與 `CALIBER_SWEEP` B3 獨立同結論） |
| L110 | 2 個區塊 | ✅ **與 `CALIBER_SWEEP` B2／B3 方向一致** |
| L111 | 全站 逐筆交易流水 | ✅ 改用 ④-3 的作法**與盤點表 §3.1 的指示一致**（「做畫面時要從 `_T7_State` 那條取，不要從 `_Ledgers`」）。⚠️ 但它不是「四件不齊」→ **M18**；且「無現成讀取路徑」→ **M19** |
| L112 | 全站 總經權重編輯 | ✅ **屬實**：盤點表 §1.9 逐字「寫：**查不到**…payload 要使用者自己在 Google Sheets 上手填」 |

### (6) 硬約束是否真的帶進去

| 條 | 規格逐字 | 本組實測 | 判定 |
|---|---|---|---|
| 1 | `_持倉總覽` **只寫不讀** → 新 UI 資料源用 `_T7_State.ledger_json`（`load_holdings_overview` 0 命中） | `grep -rn "load_holdings_overview" .` → **count = 0**（正控 `save_holdings_overview` → `ui/helpers/cloud_io.py:27,289` / `ui/tab3_t7_ledger.py:57,461` / `repositories/snapshot_repository.py:222`；負控 → 0） | ✅ **屬實，且替代來源選對了** |
| 2 | `_Ledgers` **寫得進、讀不回** → 逐筆流水**無現成讀取路徑**（唯一讀取點只取 `len()`） | 與 `inv/CONTRADICTIONS_RESOLUTION.md` 約束 2 逐字一致 | ✅ 帶進去了。⚠️ **未被違反**（④-3 走 `_T7_State`）。⚠️ 但「無現成讀取路徑」→ **M19** |
| 3 | 說明書 **9 張分頁、4 本 Sheet**，不准照舊說明書刪分頁 | 盤點表 §8 逐字「**實際 9 種、分屬 4 本**」；本組另從 `app.py:581-587` 確認 9 格 `st.tabs`（**那是分頁 UI，與 Sheet 分頁無關，不要混淆**） | ✅ **屬實** |
| 4 | 級別字面不一致：中文「核心/衛星」（`_持倉總覽.級別`）vs 英文 `core`/`satellite`（`保單分頁v2.tier`） | `repositories/snapshot_repository.py:250-251` 逐字 `tier = ("核心" if f.get("is_core") / else "衛星" if f.get("is_core") is False else "")`；`repositories/policy/v2.py:511` 逐字 `"tier",              # "core" \| "satellite" \| ""` | ✅ **逐字屬實** |

**⚠️ 一個影響全篇解讀、但規格沒有寫進去的事實（據實登記，不裁決）**：
`app.py:581-587` 一次開 **9 格分頁**，而 `wiring_grp/DATA_WIRING_SPEC.md §1.3` 逐字：
「⛔ **不是「5 舊 ＋ 4 新」。① 是新的，②③④⑤ 是舊的，⑥⑦⑧⑨ 是預覽。**」
本組逐行複驗 `app.py:636/648/662/673/688`（① 新軌 ＋ ②③④⑤ 舊軌）與
`:720/728/752/776`（⑥⑦⑧⑨ 預覽）**完全相符**。
→ **本報告所有「新 ②／③／④／⑤」一律指 `ui/views/page_0*.py` 那四個預覽頁**，
它們**有被渲染**，但**不是線上正式的 ②③④⑤**。**規格通篇沒有交代這件事。**

### (7) 尺寸

```
$ wc -lmc spec/UI_SPEC.md                      →  112  8845  8845
$ locale                                       →  LC_CTYPE="POSIX"   ⚠️ 預設 locale 下 wc -m == wc -c
$ LC_ALL=C.UTF-8 wc -lm spec/UI_SPEC.md        →  112  4412
$ python3: bytes=8845  unicode chars=4412  lines=112  ends_with_newline=True
```

**行數 112 ≤ 120 ✓。**
**「8,845 字元」實際是位元組數；Unicode 字元數是 4,412。** 兩種讀法都 ≤ 9,000 ✓。
⚠️ 生產組若是在同一個 POSIX locale 下量的，`wc -m` 會**靜默退化成 `wc -c`** —— 數字沒錯，**標籤錯了**。

---

## 3. 矛盾清單（20 條，**一律不裁決**）

> 每條格式固定：**A 說 X（出處）／B 說 Y（出處）／兩者不能同時為真**。
> 所有 `file:line` 一律 `git show origin/main:<path> \| awk 'NR==N'` 單獨印出後照抄。

### M1｜②「影子基金重疊」被排除為「缺來源」，但新 ② 自陳已接真資料

- **A 說**（`spec/UI_SPEC.md:107` 逐字）：
  `②「影子基金重疊」／④「配息月曆」— 缺來源 — 靠 `portfolio_funds[].moneydj_raw`／`.dividends`（皆未落地），查不到欄位結構與讀取規則`
- **B 說**（`ui/views/page_02_health.py:8` 逐字）：
  `接上真資料的三塊：**吃本金警示**、**影子基金重疊**、**逐檔體檢表**。`
  實作在同檔 `:1254` 起（`# ── 影子基金重疊 ──`），`:1333` 逐字 `from services.portfolio_service import calc_holdings_overlap`
- **兩者不能同時為真。**

### M2｜④「配息月曆」被排除為「缺來源」，而 repo 明文寫「原因不是沒有來源」並警告不要再找一次

- **A 說**：同 M1 的 `spec/UI_SPEC.md:107`
- **B 說**（`ui/views/page_04_portfolio.py:1035-1039` `REASON_DIVIDEND_CAL` 逐字）：
  `"（預估除息日與誤差天數）。"` / `"原因不是沒有來源：推估算得出來，但一組月配基金要算**約五秒**，"` /
  `"而這一頁每次互動都會整頁重跑 —— 所以預設不算，勾了才算"`
  同檔 `:188-190` 逐字：`- **配息月曆的資料其實拿得到，而且不必連網** —— 已載入持倉的 `dividends` 就在 session 裡…**卡住它的是成本不是來源**` /
  `- ⛔ **兩者都不是「沒有來源」。** 下一批不要再從頭找一次來源。`
  同檔 `:2637` 逐字：`               "dividends": _f.get("dividends") or []}`
- **兩者不能同時為真。**

### M3｜L106 把 4 個已渲染的區塊列為「缺規則／內容未展開」

- **A 說**（`spec/UI_SPEC.md:106` 逐字）：
  `①「⚡ ③ 例外」「🔍 ④ 可信度」／④「組合績效」「穿透式持股／產業集中度」「總經曝險聯動」— 缺規則 — 線框自陳只讀到小標與呼叫點，內容未展開`
- **B 說**：
  - `ui/views/page_01_macro.py:817` 逐字 `def _card_exceptions(ev: dict) -> dict:`（⚡ ③ 例外，含 ~70 行判讀規則與兩處已修 bug 的記載）
  - 同檔 `:901` 起（🔍 ④ 可信度，`:938` 逐字 `"title": "🔍 ④ 可信度",`）
  - 同檔 `:2183` 逐字 `    # ── 層 3：📐 建議資產水位 ／ ⚡ ③ 例外 ／ 🔍 ④ 可信度（三欄）──`
  - `ui/views/page_04_portfolio.py:2784-2787` 逐字：
    `    st.markdown(f"#### {BLOCK_CONCENTRATION}")` / `    safe_section(BLOCK_CONCENTRATION, _render_concentration)` /
    `    st.markdown(f"#### {BLOCK_MACRO_LINK}")` / `    safe_section(BLOCK_MACRO_LINK, _render_macro_link)`
  - `_render_concentration` 實際讀 `(_f.get("moneydj_raw") or {}).get("top_holdings")` 與 `.get("sector_alloc")`
- **兩者不能同時為真。**

### M4｜L106 把「組合績效」列為「缺規則」，而 repo 的理由是成本／網路往返

- **A 說**：同 M3 的 `spec/UI_SPEC.md:106`
- **B 說**（`ui/views/page_04_portfolio.py:1102-1106` `REASON_PERF` 逐字）：
  `"（年化報酬 / 波動 / Sharpe / 最大回撤，以及效率前緣）。"` /
  `"原因不是算不出來：既有那一支**一渲染就打一次匯率 API、還會落盤快取**，"` /
  `"而這一頁每次互動都會整頁重跑 —— 接上去等於每次互動一次網路往返。"` /
  `"要接得先像配息月曆那樣加一道「按了才算」的開關；在那之前，它在下面這個地方看得到"`
- **兩者不能同時為真。**

### M5｜①「📐 建議資產水位」被排除為「缺合法規則」，但它在 `origin/main` 上是已渲染的卡

- **A 說**（`spec/UI_SPEC.md:99` 逐字）：
  `- ①「📐 建議資產水位」— 缺合法規則 — 母法⛔嚴禁預設最佳配置推薦；門檻恆為固定 +1.75／−1.00`
- **B 說**（`ui/views/page_01_macro.py:767` 逐字 `def _card_allocation(ev: dict) -> dict:`；
  `:812-815` 逐字回傳 `"value": (f"股票 {_a['equity']}％ ・債券 {_a['bond']}％ "` / `f"・現金 {_a['cash']}％"),` /
  `"note": ("錢該放在哪一類資產的建議（不是「核心／衛星」那種角色分配）。"` ；渲染於 `:2183`）
- **兩者不能同時為真。**
- 📌 **附記（不裁決，但要讓客戶看見）**：B 這張已上線的卡與母法「⛔ 嚴禁預設『最佳配置推薦』」之間**本身也有張力**，
  而那是 `origin/main` 的現況，**不是本規格帶進來的**。規格在這一點上**比現況嚴**。
- ✅ A 的數字本組查證為真（見 §2 (5) L99 那一列）。

### M6｜⑤「資料來源健康度」被排除，理由是「新 ⑤ 共不共用查不到」，但新 ⑤ 明文呼叫它

- **A 說**（`spec/UI_SPEC.md:108` 逐字）：
  `- ⑤「資料來源健康度」— 缺來源 — `data_registry` 是舊 Tab5 的鍵，新 ⑤ 共不共用**查不到**`
- **B 說**（`ui/views/page_05_settings.py:1244-1252` 逐字）：
  `    # caller 契約（`ui/tab5_data_guard.py` 的 docstring）：呼叫前先更新 data_registry。` /
  `    from ui.helpers.data_registry import _update_data_registry` /
  `    from ui.tab5_data_guard import render_data_guard_tab` /
  `    _update_data_registry()` /
  `    with settings_page_owns(DATA_GUARD_HEADER, NAV_HISTORY):` / `        render_data_guard_tab()`
- **兩者不能同時為真。**

### M7｜②-1 被列為 12 塊之一且規則已定，但新 ② 說那條規則是尚未答覆的業務規格

- **A 說**（`spec/UI_SPEC.md:35-39`）：②-1「組合健康總分」列入草稿，
  `規則：逐檔指標加權彙總成總分；必要項算不出的檔不計入並標示`，來源標「沿用」
- **B 說**（`ui/views/page_02_health.py:10-15` 逐字）：
  `- **組合健康總分** —— 線框寫「五桶評等加權」，而本站的「五桶」是**總經**概念（`shared/macro_buckets.py`），**沒有逐檔基金版本**；逐檔真正存在的是 `services/health/grade.py::compute_4d_health` 的 4D/5D Grade（A～F）。該用哪一個屬**業務規格**，已送客戶、尚未答覆 → 不自行拍板（§-1.5 v3 `03`-2 ②）。`
- **兩者不能同時為真。**

### M8｜②-1 的來源列 `.policy_tier`，但新 ② 全檔 0 命中

- **A 說**（`spec/UI_SPEC.md:36` 逐字）：
  `- 來源：`portfolio_funds[].invest_twd`／`.policy_tier`／`.metrics`（沿用）`
- **B 說**（實測）：
  ```
  $ for f in ui/views/page_0*.py; do echo -n "$f: "; grep -c "policy_tier" $f; done
    page_01_macro.py: 0    page_02_health.py: 0    page_03_research.py: 0
    page_04_portfolio.py: 7    page_05_settings.py: 0
  正控 $ grep -c "invest_twd" ui/views/page_02_health.py   → 15
  負控 $ grep -c "<負控串>" ui/views/page_02_health.py → 0
  ```
  `page_04_portfolio.py` 那 7 個裡唯一的**讀取**是 `:2048` 逐字
  `        _tier = str(_f.get("policy_tier") or "").strip().lower()`，其餘 6 個是註解。
- **兩者不能同時為真**（若「沿用」意指該塊已有既存的讀取路徑）。

### M9｜①-2 的來源與規則都用 `color`／`series`，但新 ① 兩個欄位都沒讀

- **A 說**（`spec/UI_SPEC.md:22,23` 逐字）：
  `- 來源：`indicators` 各指標的 `value`／`prev`／`unit`／`signal`／`color`／`series`（沿用）` /
  `- 規則：每卡取對應指標組依 `signal`／`color` 上燈號；PPI 需 FRED key，銅價走 Yahoo 免 key`
- **B 說**（實測，token 邊界比對）：
  ```
  $ grep -on "\bcolor\b"  ui/views/page_01_macro.py | wc -l  → 1   （唯一命中 :415，在註解裡）
  $ grep -on "\bseries\b" ui/views/page_01_macro.py | wc -l  → 0
  正控 \bvalue\b → 35   \bsignal\b → 5   \bunit\b → 8
  ```
  六張卡的燈號只走 `:373` 逐字 `def _ind_signal(ind: dict, key: str) -> str:` →
  `:375` `    return str(_d.get("signal") or "") if isinstance(_d, dict) else ""`；
  數值只走 `:378 def _fmt(...)` 讀 `value` ＋ `unit`。
- **兩者不能同時為真。**
- 📌 **`fetch_all_indicators` 確實產出這兩個 key**（`services/macro/us_indicators.py` 內 `color=` 26 處、`series=` 28 處）
  → 這是「**有資料、新 ① 沒接**」，不是「沒有資料」。

### M10｜①-3 的規則與它自稱要沿用的那 5 欄對不上

- **A 說**（`spec/UI_SPEC.md:28,29` 逐字）：
  `- 來源：同 ①-2 的 `indicators`（沿用）；欄位以實作的 5 欄為準` /
  `- 規則：逐指標一列，印值／前值／燈號；新聞桶一律 ⬜「未掃描」，**不是綠燈**`
- **B 說**（`ui/helpers/macro/beginner_view.py:795` 逐字）：
  `EVIDENCE_COLUMNS = ("面向", "判讀", "讀數", "說明（這個數字怎麼讀）", "詳細在下方哪一段")`
  `build_evidence_rows` 是**逐桶**產列（`_BUCKET_ORDER` ＋ 綜合健康度那一列），**不是逐指標**；
  **五欄裡沒有「前值」。** 畫面上唯一有「前值」欄的是風險雷達表
  （`ui/views/page_01_macro.py:1392-1398`，資料源是 `_SK_RADAR`／`detect_risk_radar`，**不是** `indicators`）。
- **兩者不能同時為真。**
- ✅ 規則後半「新聞桶一律 ⬜『未掃描』」**本組查證為真**：`page_01_macro.py:742` 逐字
  `    _5b = compute_five_bucket_summary(ind, phase, news_items=None)` —— `news_items` 寫死 `None`。
- ✅ 空狀態那句也**查證為真**：同檔 `:740` 一帶 `_icon, _level, _action = "⬜", "", ""`。

### M11｜④-1 要印「目標％／偏離±％」，但三個來源欄位都不含目標，而同一份規格又說目標比例誰填須客戶裁決

- **A1 說**（`spec/UI_SPEC.md:65,66` 逐字）：
  `- 來源：`portfolio_funds[].invest_twd`／`.policy_tier`／`.is_core`（沿用）；級別字面見硬約束第 4 條` /
  `- 規則：比例＝Σ `invest_twd` 加權（**Sheet 端不存 0~1 權重**）；印現況％、**目標％**、偏離±％`
- **A2 說**（`spec/UI_SPEC.md:105` 逐字）：
  `- ④「再平衡試算」— 規則落在母法紅線邊界 — **目標比例誰填**、要不要出執行鈕，**須客戶裁決**`
- **B 說**（`ui/helpers/portfolio/allocation.py:60` 逐字 `CORE_TARGET_SESSION_KEY = "portfolio_core_pct"`；
  `:63` 逐字 `def get_core_target_pct(session_state) -> float:`；
  `ui/helpers/session.py:79` 逐字 `    "portfolio_core_pct": 75,`；
  `ui/views/page_04_portfolio.py:1476` 逐字 `       目標**一律讀 `portfolio_core_pct`**。這正是「核心／衛星現況 vs 目標」。`）
- **三者不能同時為真。**
- 📌 且 `portfolio_core_pct` 在 `inv/DB_INVENTORY.md` **0 命中**（正控 `indicators` 15、負控 0）
  → **這是第二個「盤點表裡沒有」的來源，而它沒有被就地標示，整行掛著「沿用」。**
  （對照 ①-1 的 `v01_macro_indicators` —— 那一個**有**標。）

### M12｜④-3 給出 8 欄具名清單，但新 ④ 把「要顯示哪幾欄」列為客戶 gate 並以守衛禁止

- **A 說**（`spec/UI_SPEC.md:78` 逐字）：
  `- 來源：`_T7_State.ledger_json` → `transactions[]` 8 欄（`txn_type`／`txn_date`／`amount_twd`／`fx_rate`／`nav`／`div_per_unit`／`new_units`／`note`）（沿用）`
- **B 說**（`ui/views/page_04_portfolio.py:1040-1048` 逐字）：
  `#: 交易帳本：**線框沒有給欄位規格。**` /
  `#: 線框對它只寫了**內容類型**（買賣紀錄／成本／已實現損益／對帳），沒有像 Tab 02` /
  `#: 那樣逐欄列舉；憑印象補一份欄位表就是自己發明規格，而**欄位增減是客戶 gate**` /
  `#: （`CLAUDE.md §-1.5.1c` v3 §03-2 ①）。` /
  `#: ⛔ 這一條由 `test_the_ledger_invents_no_column_list` 機械釘住（禁止出現名字帶` /
  `#:    `COLUMN` 的模組層常數），本說明只是把**為什麼**寫下來。`
  守衛實體：`tests/test_wf04_portfolio_skeleton.py:2571 def test_the_ledger_invents_no_column_list():`
- **兩者不能同時為真。**
- ✅ 附帶查證：**那 8 個欄名本身完全正確** —— 盤點表 §3.1 逐列列出
  `txn_type`／`txn_date`／`amount_twd`／`fx_rate`／`nav`／`div_per_unit`／`new_units`／`note`，
  狀態全部「活的（有落地）」，出處 `services/ledger_service.py:165-172` ＋ `models/ledger.py:44-51`。

### M13｜①-1 的空狀態手抄「📡 載入總經資料」，而 repo 有一個 SSOT 模組就是為了禁止這種手抄而存在

- **A 說**（`spec/UI_SPEC.md:18` 逐字）：
  `- 空狀態：`尚未載入總經資料。` ＋ 指到「📡 載入總經資料」鈕`
- **B 說**（`shared/ui_control_labels.py:27-29` 逐字）：
  `#: Tab ① 總經載入表單的送出鈕 —— **字是動態的**,依 `st.session_state.macro_done`。` /
  `#: 快覽卡網格只在 `macro_done` 為真時渲染,故卡片的「去哪補」**必須**指名下面那個` /
  `#: `AGAIN` 版本;指名 `FIRST` 版本 = 指一個當下不存在的按鈕。`
  同檔 `:11` 表格逐字把「📡 載入總經資料」列為**已修正的錯誤文案**；
  `ui/views/page_01_macro.py::_where_to_load` docstring 逐字：
  `⚠️ **2026-09-05 修正：本函式原本寫死 `MACRO_LOAD_BTN_FIRST`，那是錯的。**` …
  `AppTest 實測（修正前）：載入後畫面上的按鈕是「🔄 更新總經資料」，而灰態說明寫「請先到：… → 「📡 載入總經資料」」—— 指一顆當下不存在的按鈕。`
- **兩者不能同時為真。**

### M14｜⑤-2 說 9 欄全部沿用，但其中 2 欄查不到任何顯示面

- **A 說**（`spec/UI_SPEC.md:92` 逐字）：
  `- 來源：`secrets.*` 9 欄（`FRED_API_KEY`／`GEMINI_API_KEY`／`FINMIND_TOKEN`／4 本 Sheet 各自的 id／`google_service_account.*`／`PROXY_URL`）（沿用，**值不列出**）`
- **B 說**（實測，含新 ⑤ 委派的 `ui/tab5_data_guard.py`）：
  ```
  key                      page_05_settings.py   tab5_data_guard.py
  FRED_API_KEY                    1                   13
  GEMINI_API_KEY                  0                    4
  FINMIND_TOKEN                   0                    2
  NAV_SHEET_ID                    1                    0
  macro_weights_sheet_id          0                    3
  google_service_account          1                    5
  PROXY_URL                       0                    2
  POLICY_SHEET_ID                 0                    0     ← 兩處皆 0
  POOL_SHEET_ID                   0                    0     ← 兩處皆 0
  ```
  全 `ui/` 內 `POLICY_SHEET_ID` 僅 3 命中（`policy_admin_section.py:164` 註解、
  `oauth_state.py:40` 一次 `_safe_secret(...)` 讀取、`tab_manage.py:68` 錯誤字串）；
  `POOL_SHEET_ID` 僅 2 命中（`tab_manage.py:7` docstring、`:77` caption 文字）。
  **兩者都沒有「有設／沒設」的狀態顯示。**
- **兩者不能同時為真**（若「沿用」要求「到得了畫面」）。
- 📌 盤點表 §4.1 把這 9 欄**全部**標「活的」—— 那把尺量的是「程式有沒有讀它的值」，
  **不是**「畫面上有沒有它的有／無狀態」。**兩把尺量的是不同的東西。**

### M15｜②-2 的主要來源沒有被列出，而它正是同一份規格用來排除別塊的那個欄位

- **A 說**（`spec/UI_SPEC.md:42` 逐字）：
  `- 來源：`portfolio_funds[].metrics`（近一年含息報酬）、`.dividends`（年化配息率）（沿用）`
- **B 說**（`services/health/dividend.py::_resolve_adr_with_fallback` docstring 逐字）：
  `    precedence(最權威 → 次選):` /
  `        1. **MoneyDJ wb05 官方** `moneydj_div_yield`(支援 nested moneydj_raw 與 flat shape)` /
  `        2. **本地自算** `metrics.annual_div_rate`` /
  `        3. **歷史推算** `divs[]` 12 個月累積配息 / `metrics.nav`(或 `moneydj_raw.nav_latest`)`
  也就是 `.dividends` 是**第 3 層 fallback**，第 1 層是 `moneydj_raw`（規格未列）。
- **A2 說**（`spec/UI_SPEC.md:107`）：`moneydj_raw`「未落地…查不到欄位結構與讀取規則」
- **三者不能同時為真。**

### M16｜「沿用＝盤點表判活」與盤點表對這三個欄位給的狀態不同

- **A 說**（`spec/UI_SPEC.md:4` 逐字）：
  `來源標籤：**沿用**＝盤點表判活且到得了畫面／**需新建路徑**＝讀得回但無畫面消費者／**查不到**。`
- **B 說**（`inv/DB_INVENTORY.md` §0 狀態表把「**活的**」與「**未落地**」列為**兩個不同的狀態值**；
  §3.5 逐字 `| `indicators` | 未落地 | `app.py:378` 等 14 處 | 總經指標全集，Tab ① 的資料源 |`；
  §3.2 逐字 `| `portfolio_funds[].metrics` | **未落地** | `ui/helpers/portfolio/load.py:239` | |`
  與 `| `portfolio_funds[].dividends` | **未落地** | `ui/helpers/portfolio/load.py:238` | |`）
- **兩者不能同時為真**（若「盤點表判活」指狀態欄的值等於「活的」）。
- **影響 5 塊**：①-1／①-2／①-3（`indicators`）、②-1／②-2（`.metrics`／`.dividends`）。
- 📌 並陳另一半：盤點表 §0.2 逐字寫「**未落地** → 根本沒有持久化，**沒有位元組可讀** ⇒ 恆為「否」」，
  但它同時在 §3.5 備註欄寫 `indicators` 是「**Tab ① 的資料源**」——
  也就是**「未落地」講的是持久化，不是「到不了畫面」**。**這兩種讀法本報告一併登記，不選邊。**

### M17｜①-1 的第二個來源沒有任何標籤

- **A 說**（`spec/UI_SPEC.md:4`）：來源標籤只有三種（沿用／需新建路徑／查不到），且生產組自陳「12 塊全部標沿用」
- **B 說**（`spec/UI_SPEC.md:16` 逐字）：
  `- 來源：`indicators`（§3.5，沿用）＋`_macro_weights.B(payload_json)`。⚠️ 新 ① 實際用鍵 `v01_macro_indicators`，**盤點表未列**，同一支 `fetch_all_indicators` 產出`
  —— 括號「（§3.5，沿用）」在文法上**只掛在 `indicators` 上**，
  `_macro_weights.B(payload_json)` **沒有標籤**；
  而 `inv/DB_INVENTORY.md` §1.9 給它的狀態是「**只讀不寫**」，**不在那三種標籤裡的任何一種**。
- **兩者不能同時為真。**

### M18｜排除清單自稱「以下才是四件不齊的」，但至少 3 條不是

- **A 說**（`spec/UI_SPEC.md:98` 逐字）：
  `> ②「逐檔體檢表」**四件是齊的**，但為守住兩頁上限而未列入；要加回來請客戶說一聲。以下才是四件不齊的。`
- **B 說**（同檔）：
  - `:111` 逐字：`- 全站「逐筆交易流水」— **改用 ④-3** — `_Ledgers` 唯一讀取點只取 `len()`，`_sheet_stats` 零讀取端`
    → 理由是「已由 ④-3 承接」，**不是缺四件中的任何一件**
  - `:109` 逐字：`- 全站「最近查過的基金」— **需新建路徑** — …`
  - `:112` 逐字：`- 全站「總經權重編輯」— **需新建寫入路徑** — …`
    → `需新建路徑` 是 `:4` 定義的**來源標籤**，不是「四件不齊」
- **兩者不能同時為真。**

### M19｜`_Ledgers`「無現成讀取路徑」在兩份上游文件裡寫法相反（規格是繼承方，不是發明方）

- **A 說**（`spec/UI_SPEC.md:9` 逐字，承 `inv/CONTRADICTIONS_RESOLUTION.md` 約束 2）：
  `- `_Ledgers` **寫得進、讀不回** → 逐筆流水**無現成讀取路徑**（唯一讀取點只取 `len()`）。`
- **B 說**（`inv/DB_INVENTORY.md` §1.4 逐字）：
  `**要做「交易流水」畫面，不必新寫任何取數，接上那個 DataFrame 即可。**`
  （前一句逐字：`load_all_ledgers` 已經把 9 欄整張讀成 DataFrame 並做完型別正規化（`:127-139`），現在只被 `len()` 用掉。）
- **兩者不能同時為真。**
- ⚠️ **這一條的來源是上游兩份文件，不是規格自己新增的。** 規格照抄了其中一邊。

### M20｜「離線倉 0 列」的字面與 `data_cache/metadata.json` 的 13,654 列

- **A 說**（`spec/UI_SPEC.md:100` 逐字）：
  `- ①「PPI／銅價**歷史值**」— 缺來源 — 離線倉 0 列且 `load_indicators_from_parquet` 無此分支（即時值可畫，見 ①-2）`
- **B 說**（`data_cache/metadata.json` 逐字）：
  `    "fred_indicators": {` / `      "name": "fred_indicators",` / `      "last_updated": "2026-09-10",` / `      "row_count": 13654,`
- **兩者不能同時為真（就字面而言）。**
- 📌 **若把 A 讀成「PPI／銅價這兩個 series 在離線倉 0 列」，本組的獨立量測支持它**：
  `scripts/update_macro_history.py:65-73` 的 `FRED_SERIES_IDS` 共 11 個 id，
  其中 **9 個以明文出現在 `data_cache/fred_indicators.parquet` 的位元組裡**
  （`DGS10`／`DGS2`／`DGS3MO`／`BAMLH0A0HYM2`／`M2SL`／`WALCL`／`CPIAUCSL`／`UNRATE`／`DTWEXBGS`），
  而 **`PPIACO` 與 `PCOPPUSDM` 各 0 命中**。
  ⚠️ **這是位元組層推論，不是讀表** —— 本機無 pandas／pyarrow 且**不得 `pip install`**。
  ✅ A 的後半「`load_indicators_from_parquet` 無此分支」**確定為真**：
  `grep -c "PPI" services/macro/validation.py` → **0**、`grep -c "COPPER"` → **0**。

---

## 4. 查了但沒問題的（只寫命中不寫清白，看不出這把尺有沒有真的往內用）

**12 塊全部查過**，其中下列**完全沒有找到問題**：

| 塊 | 查了什麼 | 結果 |
|---|---|---|
| **③-2 單一基金淨值走勢** | 4 個欄位在盤點表 §1.6 的狀態、`load_series` 是否存在且被呼叫、「唯一不可再生／NAS crontab」那句警語 | 全部屬實。`services/nav_history_gs.py:818 def load_series(` ＋ `services/fund_service.py:1095 s_hist = load_series(code, oauth_client=oauth_client)`；警語與盤點表 §1.6 的 2026-09-16 更正逐字同義 ✓ |
| **④-2 保單與扣款標的** | 6 個欄位在盤點表 §1.2b 的狀態、「同保單同檔多筆 → 加總」的業務語意 | 6 欄全部「活的」；加總語意與 `CLAUDE.md §4.6`（複合鍵 `(policy_id, fund_url)` → `invest_twd` 加總）一致 ✓ |
| **⑤-1 NAV 累積狀態** | 3 欄狀態、別名 import、「不以 dict 空不空決定畫不畫」那條規則、閘門灰態 | `page_05_settings.py:323 coverage_status as fetch_nav_coverage`、`:1313` 呼叫、`:1314-1318` 逐字寫著「展開器開不開，看的是『有沒有可渲染的行』，不是『dict 空不空』」—— **規格那句是照實作寫的** ✓ |
| **③-1 的 6 個欄位** | `_fund_pool` 在盤點表 §1.7 的狀態 | 6 欄全部「活的」✓（⚠️ 新 ③ 無現成接線，已記於 §2 (2) 表格，本組**不判定**那算不算問題） |
| **④-1 的 3 個欄位** | `invest_twd` / `policy_tier` / `is_core` 狀態與新 ④ 讀取點 | 三欄全部「活的」；`page_04_portfolio.py:2048` 確有 `policy_tier` 讀取 ✓ |
| **④-3 的 8 個欄名** | 逐欄比對盤點表 §3.1 | **8 欄逐字相符、狀態全部「活的（有落地）」** ✓ |
| **⑤-2 的其中 7 欄** | 在新 ⑤ 或委派對象的顯示面 | 7/9 有命中 ✓（另 2 欄見 M14） |
| **四條硬約束** | 全部逐條實測 | **四條全部屬實**，第二條**未被違反** ✓（見 §2 (6)） |
| **母法禁令** | 24 個關鍵字 ＋ 112 行逐行語意閱讀 | **0 條違規** ✓ |
| **`CALIBER_SWEEP` 的 3 條方向 B** | 逐條比對規格有沒有拿它們當「沿用」 | **一條都沒有** ✓ |
| **排除清單 L101／L102／L109／L110／L112** | 逐條回查原始碼 | **5 條全部屬實** ✓ |
| **L99 的「+1.75／−1.00」** | `shared/signal_thresholds.py` 逐行印 | `:409 ZSCORE_STOP_GAIN_DEFAULT: float = 1.75`、`:410 ZSCORE_ADD_DEFAULT: float = -1.0`，且 `ndc_score` 恆傳 `None` → **「恆為固定」成立** ✓ |
| **①-3 的兩條規則細節** | 新聞桶一律 ⬜、綜合健康度只印分數 | `page_01_macro.py:742 news_items=None`（寫死）、`:740 _icon, _level, _action = "⬜", "", ""` → **兩條都屬實** ✓ |
| **尺寸** | `wc -lmc` ＋ locale ＋ python3 三法交叉 | 112 行 ✓；字元數的標籤問題見 §2 (7) |

**另記（不是問題，但客戶應該知道）**：
12 塊的「空狀態」文字裡，**只有 3 句在 `origin/main` 上已經存在**
（`尚未載入總經資料。`、`🔍 載入抓取診斷細節`、`讀一次雲端累積狀態`）；
**其餘 6 句是規格新寫的文案**（`雲端還沒有任何累積`／`還沒有保單分頁`／`這本帳還沒有任何交易紀錄`／
`這一檔還沒累積到淨值`／`對照表沒有這個代號`／`本金欄是空的` 全 repo 0 命中）。
**這不違反任何規則**（`:4` 的標籤只約束「來源」），登記在此**是為了讓客戶知道他在審什麼**。

---

## 5. 我沒查到什麼（一律寫「查不到」）

1. **規格描述的畫面實際長什麼樣 —— 查不到。** 本組**一次 Streamlit 都沒跑**（也不該跑，凍結令）。
   所有「新 X 頁會呼叫 Y」只代表**程式碼路徑存在**。
2. **`data_cache/fred_indicators.parquet` 的實際列內容 —— 查不到。**
   本機無 pandas／pyarrow 且不得 `pip install`；M20 的結論是**位元組層推論**，不是讀表。
3. **④-2 的讀路徑本組沒有獨立重跑** —— 那 4 個讀取點（`ui/helpers/cloud_io.py:156,325` 等）
   是照抄盤點表 §1.2b，**本組未逐一 `awk` 印出**。
4. **L103「③ 搜尋結果走外部 API」的反例 —— 查不到**（本組未深挖搜尋鏈）。
5. **L104「`v03_research_batch_rows` 欄位清單查不到」是否為真 —— 本組未獨立驗證。**
   只確認了那個 session key 存在（`ui/views/page_03_research.py:669`）。
6. **「新 ③ 沒有接 `_fund_pool`」算不算問題 —— 本組不判定。**
   規格是**應然**文件，可以規定新接線；本報告只記事實。
7. **「本規格沒有第 21 個問題」—— 本組不宣稱。**
   上列 20 條是**分類敘述**，不是窮舉。本組的字面掃描**結構上看不到**：
   `getattr` 動態取名、跨檔多層封裝、`x = mod.f` 式賦值別名、以及「意思到了但用詞不同」的句子。
8. **`inv/DB_INVENTORY.md` 在本輪稽核期間仍在被另一組編輯**（開工時 1,115 行、收工時實測 **1,380 行**）。
   **本報告引用該檔一律原文照抄句子與節號，不用行號**；
   若那一組在本報告之後又改了 §3.2／§3.5／§1.4／§1.6／§1.9 的任何一列，**M16 與 M19 須重驗**。
