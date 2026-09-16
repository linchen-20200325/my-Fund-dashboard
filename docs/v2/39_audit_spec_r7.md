# SPEC R7 獨立稽核報告

**稽核組**：獨立稽核組（R7），單組產出，**沒有第二組驗過**
**日期**：2026-09-16
**工作樹 HEAD**：`d0c2a8d`（`claude/fund-handover-verification-89o6ys`）· **全程唯讀，結束時 `git status --porcelain` 空輸出**
**基準**：`origin/main` ＝ `9cbf03776f2a0ee6bdb5a649efb93352c40baba6`（實測，與受稽核文件宣告一致）
**母法**：`5569d85`（`origin/docs/v2-constitution-governance` tip；`docs/v2/CONSTITUTION.md` **不在 origin/main**，實測 `git show origin/main:docs/v2/CONSTITUTION.md` → does not exist）
**受稽核對象（實測行數）**：
```
UI_DRAFT_01_MACRO.md  1110 行 / 109187 bytes / 61309 chars
UI_SPEC.md            1091 行 / 161770 bytes /  86472 chars
DECISION_LOG.md        560 行 / 124140 bytes /  67367 chars
PROPOSAL_4a.md         187 行 /  15542 bytes /   8480 chars
PROPOSAL_4b.md         159 行 /  13587 bytes /   6975 chars
```
（`LC_ALL=C.UTF-8 wc -m`；`wc -l` 與派工單宣告的 1091／560／187／159 **四項全部吻合**。）

**工作檔**：`scratchpad/audit/r7/`（`extract.py` `verify_quotes.py` `tablecheck.py` `prefixcheck.py` `multiquote.py` `mq2.py` `closure.py` `cscan.py` `cscan2.py` `ast16.py`、`src/`＝`git archive origin/main` 展開樹、`CONSTITUTION.md`＝`git show 5569d85:docs/v2/CONSTITUTION.md`）

---

## 判決摘要

| 級別 | 筆數 | 項目 |
|---|---|---|
| **擋下（不修不能交）** | **2** | X-1 反向掃描漏掉 `services/macro/us_indicators.py`（0 次出現在五檔任一份）；X-2 `PROPOSAL_4b §2(b)` 的「63 行命中」指令**不可複跑** |
| **要改（不擋）** | **7** | Y-1 ~ Y-7（見下） |
| **查了但沒問題** | **11 類** | Z-1 ~ Z-11（見下），含 E 節全部計數、A 節 71 筆表格引文與 28 條重複引文一致性 |

**先講最重要的一句**：**B 節（補標 8 處是不是真的）全部成立** —— 8 處的引文、鏈路、凍結面我逐條實跑重印比對，**沒有一處造假、沒有一處引錯**。擋下的兩筆都是「**掃描形狀盲**」與「**指令不可複跑**」，不是「寫的內容是假的」。

---

# A. 引文忠實度

## A-0 方法（兩種形狀取聯集，各自的盲點寫在末節）

**形狀 1（容器掃描）** `r7/extract.py` —— 把五份文件的引文容器**四種**一起抽：fenced code block、單反引號 code span、`「」`／`『』`、ASCII `"..."`。抽出 spans：
```
UI_DRAFT_01_MACRO.md: 1553 (fence 355 / code1 950 / cjk 207 / cjk2 4 / dq 37)
UI_SPEC.md          : 2169 (fence  10 / code1 1581/ cjk 455 / cjk2 11 / dq 112)
DECISION_LOG.md     : 1602 (fence   0 / code1 1154/ cjk 397 / cjk2 11 / dq 40)
PROPOSAL_4a.md      :  165 / PROPOSAL_4b.md: 144
```
**形狀 2（定位前綴）** `r7/prefixcheck.py` —— 專吃 `` `<path>:<N> <code>` `` 與 `` `:<N> <code>` `` 這種「位置＋程式碼」複合 span，剝掉前綴後與該行逐字比對。

**正控／負控（`r7/verify_quotes.py` 內建，assert 擋住）**
- 正控：`st.markdown("### 🧾 ① 結論 — 現在該加碼還是防禦")` → 在 haystack 命中 `ui/views/page_01_macro.py` 與 `CONSTITUTION.md@5569d85` ✅（**會亮的正控**）
- 負控（本輪現編）：`贅碼鶮溤XQ42` → 0 命中 ✅

`r7/tablecheck.py` 另外解析**表格列**的 `(檔, 行, 引文)` 三元組 —— **`split("|")` 用自寫的逃脫感知切法**（遇 `\|` 不切），不是 `line.split("|")`。解析出 71 列，**44 列逐字相符，27 列進人工判讀**。

## A-1 27 列人工判讀結果

**26 列是我的 parser 造成的假陽性**（表格列同時出現兩個 `檔:行`、parser 取了第一個；或 `同檔 :N` 的 last-file 追蹤跨行漂移）。逐一回查原文後**全部無誤**，其中三筆特別值得記：

| 我的 parser 報 | 實際 | 判讀 |
|---|---|---|
| `UI_SPEC:13` 「`app.py:688` 卻引 `render_settings_and_diagnostics()`」 | 那一列是 **⑤ 一列兩格**：正式格 `:688 render_settings_diag_tab()`／預覽格 `:728 render_settings_and_diagnostics()` | 文件**自己在 `:6` 就警告過**「兩份行號不是依序對應的，不要用並列去配（原寫法會讓 `:728` 被讀成 ③）」。實測 `app.py` 五行全對。**無誤** |
| `PROPOSAL_4b:49-52` 「`CONSTITUTION.md:3239` 超出檔尾」 | 實際指 `ui/tab3_t7_ledger.py`，parser 的 last-file 漂移 | 四行逐字實測 **全對**（見 B-4b） |
| `UI_SPEC:119` 「`page_04_portfolio.py:1851` 沒有 `safe_section("組合健康總分")`」 | `:1851` 在 **`page_02_health.py`**（實測 `safe_section("組合健康總分", _render_health_score)`），`:2783` 才在 `page_04_portfolio.py` | 事實無誤，**但那一句把兩個檔的行號並排卻一個檔名都沒寫** → 列為 **Y-4** |

**真正的字元層差異只有 1 筆**（下）。

## A-2 粗體層：**逐筆列出**（`verify_quotes.py` 的 `BOLD_ADDED` 分支）

全五檔共 **15 筆**「原文沒有 `**`、文件加了粗體」。逐筆核對後**15 筆全部落在 `「…」` 引述內、且被引的原文本身在母法／`CLAUDE.md` 裡就是強調句**，屬中文引述的強調慣例，**不是竄改程式碼引文**：

```
UI_DRAFT:622  「**一個位元組都不准動**」          ← CONSTITUTION F1 現況欄
UI_DRAFT:857  「現在是好是壞、**下一步怎麼做**」   ← page_01_macro.py:1869
UI_DRAFT:933  「**不畫空表格外框**，改用空狀態三要素」
UI_SPEC:113   「**層 3：📐 建議資產水位 ／ ⚡ ③ 例外 ／ 🔍 ④ 可信度（三欄）**」 ← page_01_macro.py:765 註解
UI_SPEC:257   「**提案 1｜`composite_verdict` 的五句 `action_text` …**」        ← CONSTITUTION:1836
UI_SPEC:629   「**G3 最嚴重的一種**」                                          ← CONSTITUTION:1096
DECISION_LOG:284 「**v2 不繼承 `action_text`，只取 `level`**」                 ← CONSTITUTION §8 提案 1
PROPOSAL_4a:10,139,144 / PROPOSAL_4b:10,88,107,115,152（同型）
```
⚠️ **其中 `UI_DRAFT:857` 與 `UI_SPEC:113` 的被引原文是 `.py` 檔內容**（`page_01_macro.py:1869`／`:765`），加粗是**引述者加的**。**文件在那兩處沒有標「粗體為本組所加」** → 列為 **Y-5**（不擋：兩處都不是「現況引文・待修」表格列，不會被當成待改的程式碼字面照抄）。

⚠️ **「現況引文・待修」那幾張表格裡的粗體全部是原文自帶的**，逐筆實測：
- `ai_prompts.py:72` 原文就有 `**該減碼**`／`**該補進**`
- `ai_prompts.py:73` 原文就有 `**必須引用上方「領先指標排名」…**`
- `ai_prompts.py:137` 原文就有 `**依照下面的章節順序逐節輸出**`
- `page_01_macro.py:2031` 原文就有 `**逐檔的加減碼建議請到 …**`
- `page_01_macro.py:2067` 原文就有 `**現在市場環境該進攻還是防守？**`

## A-3 同一行被引用多次 → 呈現一致嗎（`r7/mq2.py`）

拿 **28 條**已登記的違規原文字串，在五檔裡找出**每一次**出現，比較渲染（`plain` vs `BOLD-INSERTED`）。

正控：`AI 4 節結構` 必須在 `PROPOSAL_4b` 出現 → True ✅
負控（本輪現編）：`嘅魯踬ZZ7砻` → 0 ✅

**結果：28 條全部 `kinds=['plain']`，沒有任何一條出現「幾處忠實、一處加粗」。** 出現次數最多的幾條：
```
ai_prompts.py:148   6 次（UI_DRAFT×3 / UI_SPEC×2 / DECISION_LOG×1）—— 全部一致
turning_points:155  5 次（UI_DRAFT×3 / UI_SPEC×2）           —— 全部一致
story_nav.py:332    4 次（全在 UI_DRAFT）                     —— 全部一致
page_01_macro:2067  4 次（全在 UI_DRAFT）                     —— 全部一致
ai_prompts.py:150   4 次 / midcycle:401,409 各 3 次 / action_light 五句各 2-3 次 —— 全部一致
```
**A-3 判決：通過。這一輪沒有重演「同一行三處引用、兩處忠實一處加粗」。**

## A-4 字元層：唯一一筆真差異

| 位置 | 文件寫 | 原文 |
|---|---|---|
| `UI_SPEC.md:864` 引 `ui/helpers/portfolio/load.py:240` | `"moneydj_raw": pf_raw,`（**一個空格**） | `"moneydj_raw":  pf_raw,`（**兩個空格**，該檔該區塊是對齊排版） |

實測：`sed -n '240p' ui/helpers/portfolio/load.py` → `                "moneydj_raw":  pf_raw,`
→ **Y-6（不擋）**：語意零影響，但它出現在一段自稱「逐行重印核對」的文字裡。

## A-5 兩筆「攤平引用」與一筆「置換識別字」

| # | 位置 | 文件寫 | 原文 |
|---|---|---|---|
| a | `UI_SPEC:113` 引 `page_01_macro.py:2185` | `render_cards([_card_allocation(_ev), _card_exceptions(_ev), _card_credibility(_ind, _ev)])` 一行 | `:2185-2189` **五行**（`render_cards([` ＋三個 arg ＋ `])`） |
| b | `UI_SPEC:311` 引 `:809-810` | `f"股票 {_a['equity']}％ ・債券 {_a['bond']}％ ・現金 {_a['cash']}％"` 一行 | 兩行，`:809` 尾端有空白、`:810` 另起一個 `f"` |
| c | `UI_SPEC:313` 引 `:804-806` | `"這兩個門檻已依台灣景氣{light}燈調整。"` | `f"這兩個門檻已依台灣景氣{_al['light']}燈調整。"` —— **`_al['light']` 被換成 `light`** |

(a)(b) 是「把跨行合成一行」，**位置欄已寫成範圍**（`:809-810`），可接受；(c) **改了識別字**，而那一格的欄名是「現況引文・待修（**原樣引用**）」→ **Y-6 合併計入**。

---

# B. 補標的 8 處是不是真的

**方法**：對 `DECISION_LOG:60`（B29）列出的八處，逐行 `git show origin/main:<path> | awk 'NR==N'` 重印、比對引文、追鏈路、對母法 F 表核凍結面。**F 表出處**：`5569d85:docs/v2/CONSTITUTION.md:72-77`（實測重印，F1 `16 個 ui/tab*.py`／F2 五個 `ui/views/page_0*.py`／F3 `app.py`／F4 `services/**`／F5 Schema／F6 遷移鏈）。

| # | 登記 | 引文逐字 | 鏈路（我自己從 `page_01_macro.py` 的 import 面追到底） | 凍結面 | 判決 |
|---|---|---|---|---|---|
| ①-1 抬頭 | `page_01_macro.py:676`／`:2123` | ✅ 兩行都是 `st.markdown("### 🧾 ① 結論 — 現在該加碼還是防禦")` | 頁內直接渲染 | **F2** ✅（`:73`） | **成立** |
| ①-1 本文 | `action_light.py:164,176,186,187,188` | ✅ 五行逐字相符（含 `:176`／`:188` 的**半形逗號**，文件有就地標註） | `page_01_macro.py:160` import `macro_action_light` → `:677` 呼叫 → `:693 business_alert(...)`／`:696 st.markdown(...)` | **F4** ✅（`:75`） | **成立** |
| ①-3 | `composite_score.py:305,308,311,314,316` → `beginner_view.py:974` | ✅ 六行全對 | `:164` import `composite_verdict` → `:736` → `:748/:751/:758` → `:759 render_evidence_table` | F4 ＋ `ui/helpers/**` **不在 F1~F6**（`:1860` 實測逐字） ✅ | **成立** |
| ①-6 | `page_01_macro.py:2030-2034` ＋ 守衛 X3 | ✅ `:2031`／`:2033` 逐字；守衛 `tests/test_wf01_detail_zone_order.py:135 _SIGNPOST_MARK: str = "加減碼建議"`、`:439-440` 逐字；`_SIGNPOST_MARK` 實測 **5 個位點**（`:135/:439/:540/:662/:670`）與文件一致 | `:1986 safe_section(_title,_render)` 迴圈結束 → `:1987 _render_matrix_signpost()`（實測 `:1990 def`） | F2 ＋ `tests/` 不在 F1~F6 但依 §6.5-P 同批 ✅ | **成立** |
| ①-8 | `tab1_macro_midcycle.py:401,409` | ✅ 兩行逐字 | **`page_01_macro.py:1117` lazy `from ui.tab1_macro_midcycle import render_mid_cycle_section` → `:1118` 呼叫**（實測，這是該檔唯一的 `ui/tab*` import）；`:396-410` 填 `_l3_sit_cards`、`:411-420` `st.markdown(..., unsafe_allow_html=True)` | **F1** ✅ —— 實測 `git ls-tree` 16 檔，`tab1_macro_midcycle` **字典序第 5**，與文件一致 | **成立** |
| ①-9 | `liquidity_engine.py:482-483,485` | ✅ 三行逐字；`:487` 「不命中」的判讀我逐行讀過，同意 | `:150-155` import `liquidity_verdict`（實測住在 `:452-488`）→ `:1479`（**只在 `not _partial` 時**，`:1475 _partial = 0 < _n_on < _n_all` 實測）→ `:1480-1482 st.caption` | **F4** ✅ | **成立** |
| ①-10 | `turning_points.py:155` | ✅ 逐字；`:217-218` 的補入列亦逐字 | `:158` import `detect_turning_points` → `:1560 render_cards([_tp_card(...)])` → `:1669 _sig` ＋ `:1674 "note"` ＋ `:1676 STATE_BUSINESS if _sig.startswith("🔴")`（**實測 `"⚠️ 衰退末期，布局反彈"` 不以 🔴 開頭 ⇒ 走 `STATE_OK` 綠卡**，文件的判讀正確） | **F4** ✅ | **成立** |
| ①-11 | `ai_prompts.py:148-150` | ✅ 三行逐字 | `build_structured_summary_prompt` production import **實測恰好 2 個**（`ui/helpers/ai_summary.py:37`／`ui/views/page_01_macro.py:146`，其餘命中為同檔 def/docstring 與 `tests/`）→ `:1873` 呼叫 → `:1894 st.markdown(_text)` | **F4**；`:1869` caption 為 **F2**；`ai_summary.py:69` 不在 F1~F6 ✅ | **成立** |

**＋①-4 卡 1 ＝ 9 的對帳**：實測 `page_01_macro.py:767-814 _card_allocation`，`:809-810`／`:811`／`:801`／`:804-806`／`:785` 五列引文全部存在且位置正確；`shared/signal_thresholds.py:409` 實測 `ZSCORE_STOP_GAIN_DEFAULT: float = 1.75`。**8 ＋ 1 ＝ 9 的算式成立。**

**B-4b（`PROPOSAL_4b` 的四行）**：`git show origin/main:ui/tab3_t7_ledger.py | awk 'NR==3237||NR==3239||NR==3263||NR==3291'` → 四行**逐字全對**（含 `:3263` 句尾的**半形分號**，文件有標）。`:3402` 免責 caption 逐字存在。`:3232-3242`／`:3261-3268`／`:3290-3296` 三段結構全對。`tab3_t7_ledger.py` 總行數 **3402**，`3402 − 4 = 3398` ✅ 與 `PROPOSAL_4b:35` 的「其餘 3,398 行」吻合；字典序第 9 ✅。

---

# C. 反向掃描：有沒有第 9、第 10 處被漏掉

## C-0 方法

1. `r7/closure.py` —— **AST** 建 `ui/views/page_01_macro.py` 的**遞移 import 閉包**（含函式內 lazy import），得 **116 個模組**。
2. `r7/cscan.py` —— 對閉包跑派工單指定的**寬字表**，**兩種形狀取聯集**：
   - 形狀 1 = 逐行 grep（看得到註解／docstring，看不到跨行字面值的真實歸屬）
   - 形狀 2 = AST 字串字面值（看得到 f-string 片段與跨行合併，**看不到註解**）
   實測：形狀 1 命中 **316 行／50 檔**，形狀 2 命中 **178 行／47 檔**；`只在形狀1` 204 行、`只在形狀2` 66 行 —— **任一形狀單獨跑都會漏掉一大塊**。
3. `r7/cscan2.py` —— **加寬字表**後對「渲染可達集」重跑。
4. 逐一人工判讀「這段字面像行動建議」vs「它真的會渲染／進 prompt」，用 AST 找 enclosing function 再回查消費端。

**正控**：`減碼` 必須命中 `services/macro/action_light.py`（assert）✅；`布局` 必須命中 `services/macro/turning_points.py`（assert）✅
**負控**（本輪現編，兩支腳本各用一個不同的）：`贅碼鶮溤XQ42`／`齋騎鷸QQ9931溤` → 0 ✅

## C-1 ⛔ 擋下 X-1：`services/macro/us_indicators.py` —— 五檔文件 **0 次出現**

```
$ grep -c "us_indicators" UI_SPEC.md DECISION_LOG.md UI_DRAFT_01_MACRO.md PROPOSAL_4a.md PROPOSAL_4b.md
UI_SPEC.md:0   DECISION_LOG.md:0   UI_DRAFT_01_MACRO.md:0   PROPOSAL_4a.md:0   PROPOSAL_4b.md:0
```
而 `page_01_macro.py:156-161` 直接 `from services.macro import calc_macro_phase, detect_turning_points, fetch_all_indicators, macro_action_light`，實測 `services/macro/__init__.py:44,47` 這兩支 **就定義在 `us_indicators.py`**，且 `page_01_macro.py:2147 _phase = calc_macro_phase(_ind)` 是 ① 每次渲染都會跑的。

**該檔的行動型字面（AST enclosing-function 實測）**：
```
:151  _detect_inflection    signals.append({"type":"buy","text":f"⚡ 10Y-2Y 由負翻正（…）— 策略3 最強黃金買點！"})
:174  _detect_inflection    {"type":"buy","text":f"VIX … 恐慌高位 — 逢低加碼時機"}
:227-228 _detect_inflection "🚀 強力買進拐點" / "✅ 買進拐點形成" / "建議逢低布局"
:601  fetch_all_indicators  desc="倒掛(<0)=衰退 | 由負翻正=黃金買點"
:844  fetch_all_indicators  desc=f"<{…}平靜 | >{…}恐慌=逢低加碼時機"
:1245 get_market_phase      "Z 低位 + 斜率翻正，景氣底部確認，逢低布局機會"
:1467-1483 calc_macro_phase advice/strategy 八句：「適度獲利了結」「逐步減碼高估值成長股」
                            「設嚴格停利點」「衛星資產設15%停利出場」「最高勝率買點！逐步加碼」
                            「積極佈局中小型成長股…金融股底部」「等待落後指標見頂為進場訊號」
:1992/:1997 detect_systemic_risk 「建議立即提高現金比重，核心部位 ≥80%，衛星部位設停損」
```

**到得了 ① 的是哪幾個（逐條追過消費端）**：

| 字面 | 到得了嗎 | 實測依據 |
|---|---|---|
| `:601` `desc="…由負翻正=黃金買點"` | **✅ 到得了 —— 經 AI prompt** | `desc` 在 `ui/views/page_01_macro.py` 的**唯一**出現處是 `:1762`：`f"…｜{_v.get('signal') or ''} {_v.get('desc') or ''}".rstrip()`，住在 `_ai_snapshot()`（`:1715-1802`）；`:1753 _real = {k:v for … if not is_meta_key(k)}`，而 `is_meta_key` 實測是 `str(key).startswith("_")` ⇒ **`YIELD_10Y2Y`／`VIX` 都在 `_real` 裡**。快照 → `:1873 build_structured_summary_prompt(snapshot=_snapshot…)` → `:1894 st.markdown(_text)` |
| `:844` `desc="…恐慌=逢低加碼時機"` | **✅ 同上** | 同上 |
| `:1467-1483` advice／strategy | ❌ 到不了 ① | `calc_macro_phase` 回傳 dict 含 `advice=`／`strategy=`（`:1587`），但實測 `page_01_macro.py` 只讀 `phase.get('phase')`／`('score')`／`('support')`；`grep '\["advice"\]\|get("advice")'` 的消費端是 `ui/components/mk_clock.py:222`、`ui/tab1_macro.py:612`、`ui/tab2_single_fund.py:1707` —— **都不在 ①** |
| `:151/:174/:227-228` `_detect_inflection` | ❌ 到不了 ① | 進 `phase["mk_signals"]`／`["signals"]`（`:1588`／`:1602`），`page_01_macro.py` 不讀這兩個鍵 |
| `:1992/:1997` `detect_systemic_risk` | ❌ 到不了 ① | 該 fn 未被 `page_01_macro` import |
| `:1245` `get_market_phase` | ❌ 到不了 ① | 同上 |

⚠️ **另一半的盲點，一併記**：`ui/tab1_macro_midcycle.py::_card_note`（`:161-187`）**會把 `ind[key]["desc"]` 印在 ①-8 的 Z-Score 卡上**（`:181-183`）。我逐一比對 `_ZS_INDICATORS`（`:66-95`，18 項）與那 17 個 `desc=`，**`YIELD_10Y2Y` 與 `VIX` 都不在 `_ZS_INDICATORS` 裡**，其餘 18 個 desc 逐行讀過**沒有行動動詞**（「利多／利空／健康／警戒」是市況描述）⇒ **這條路目前乾淨**，但它是一條**沒有人登記過的渲染路徑**，`_ZS_INDICATORS` 一改就會通。

**⚠️ 字表盲點（必須寫下來）**：派工單給的 28 詞字表**沒有「買點」**（只有「買進」）。`:601` 的「黃金買點」**用派工單的字表掃不到**。我加寬字表後才撈到（`cscan2.py` 實測：加寬後多出 **72 行**是原字表完全看不到的，其中 14 行在 `us_indicators.py`）。**這正是本 session 已犯四次的同一個病。**

**判決**：⛔ **擋下**。八處補標的**鏈路追法本身是對的**，但**追的範圍沒有涵蓋 `_ai_snapshot()` 這條「字面 → prompt → 畫面」的間接路徑**，於是整支 `us_indicators.py`（① 每次渲染都會呼叫兩支的那個檔）從頭到尾沒有進過任何一份文件。**這不是「多標一處」的問題，是「有一整個檔沒被看見」。**

## C-2 三處「DRAFT 標了、UI_SPEC 沒標」

`UI_DRAFT_01_MACRO.md:947-966` 的 H-1 ~ H-11 總表，`UI_SPEC 標了嗎` 欄對 **H-1／H-2／H-8** 都是 ❌，而**它們到今天仍然只在草稿裡**：
```
$ grep -n "2067\|麵包屑\|進攻還是防守\|觀望 / 中性" UI_SPEC.md DECISION_LOG.md
(無輸出)
```

| DRAFT 編號 | 位置 | 我的實測 |
|---|---|---|
| **H-1** | `ui/helpers/story_nav.py:332 ("macro", "看懂景氣位階,決定加碼或防禦")` | **到得了 ①**：`page_01_macro.py:195` import → `:2065 render_story_nav("macro")`（住在 `render_market_overview` `:2060-2192`）→ `story_nav.py:584 st.caption(story_nav_markdown(current))` → `:538-539` 把 `_cur_hint` 接在尾端。**我實跑了那支純函式**：`story_nav_markdown('macro')` → `'…　·　_看懂景氣位階,決定加碼或防禦_'` |
| **H-2** | `page_01_macro.py:2067 st.caption("回答一個問題：**現在市場環境該進攻還是防守？** …")` | 逐字存在、頁內直接渲染。**與 ①-1 抬頭是同一個形狀**（母法 `:1346` T1「行動問句抬頭 → 狀態抬頭」） |
| **H-8** | `services/us_liquidity_engine.py:182 color, label = TRAFFIC_YELLOW, "➖ 觀望 / 中性"` | 逐字存在；`page_01_macro.py:168` import `fetch_us_liquidity_snapshot`，`label` 經 `:1800-1801` 進 AI 快照 |

**UI_SPEC 的〈待確認〉11 項我逐項讀過，沒有任何一項是這三個。** 換言之：**權威規格裡它們既不在 ⛔ 清單、也不在待確認清單、也不在排除清單 —— 沒有落點。**
→ **Y-1（要改，不擋）**：三處都是 DRAFT 自己判「⚠️ 待判讀」的，不是漏查；缺的是**把待判讀事項搬進權威規格**的動作。

## C-3 死碼：`synthesize_dual_verdict`（**派工單問題 1 的答案在 F 節**）

`services/risk_radar.py:627-739` 的 `synthesize_dual_verdict` 內有 6 句行動指令（`:666 "立即減倉防守"`／`:679 "雙速分歧：降槓桿"`／`:683 "倉位降至 50-60%、暫緩定額、停利收緊"`／`:694 "現金 25-30%、停止加碼、衛星部位獲利了結"`／`:717 "維持持倉、暫緩單筆加碼"`／`:727 "分批進場、倉位 60-70%、定期定額減半"`）。
**production caller ＝ 0**（見 F-1）。→ **不算當前違規**，但**單獨列**在此。
✅ **UI_DRAFT_01_MACRO.md:1002-1004 已經自己寫下這一筆**（「實測到不了 ① 的畫面…那是『查了、沒問題』，照實寫下來」）—— **我獨立重跑，結論相同。**

## C-4 另一處 SSOT 破口（不是 ① 的違規，但會讓 ①-3 的修法失效）

`services/macro/explain.py:238-258 _verdict_for()` 是 `composite_verdict` 的**逐字複製品**（docstring 自陳「同 macro_helpers.composite_verdict 但避免循環 import」），**五句 action_text 一字不差**：
```
:247 多頭市場強勁：可滿倉持有，衛星部位積極佈局成長題材
:250 景氣穩定擴張：核心持有不動，定期定額正常進行
:253 市場震盪整理：分批進場，避免重押單一題材
:256 風險正在集結：拉高現金水位至 15-25%，衛星部位設停利
:258 避險情緒高漲：現金 30%+，核心轉防守型（投資等級債/全球均衡）
```
**到不了 ①**（`explain.py` ← `daily_key_alerts.py` ← `ui/tab1_macro.py`，① 不走這條），但 **①-3 若照母法 §8 提案 1 去改 `composite_score.py` 的五句，這一份會原封活著**。五檔文件 0 提及。→ **Y-2**

## C-5 我掃過、確認「到不了 ①」的（照實寫，不省）

`services/decision_matrix.py`（`加碼/減倉/全撤` 動作標籤，只從 `ui/tab1_macro.py:1614 realtime_signal` 進去）／`services/allocation_ladder.py:89 "action_text"`（`_card_allocation` 只取 `allocation`／`stop_gain_z`／`add_z`／`light`／`status`／`reason`，實測不取 `action_text`）／`ui/components/macro_card_edu.py:92,97`「黃金買點」（`_card_note` 只讀 `historical_anchor`，實測不讀 `meaning`／`how_to_read`）／`services/macro/causal_sankey.py:673,675`「建議降低風險暴露」「建議減碼至中性」（`verdict` 無 ① 消費端）／`ui/tab1_macro_inflection.py:161,372,440`（① 不呼叫）。

---

# D. 兩張提案單 vs 母法 §5.1 範本

**範本出處**：`5569d85:docs/v2/CONSTITUTION.md:510-545`（實測重印）。要求：四個抬頭欄（提案人／日期／射程固定值／base commit）＋ 五個小節（1 變更條款／2 阻礙原因／3 替代方案／4 影響評估〔五個 bullet〕／5 總管推薦方案）。

| 檢查項 | 4a | 4b |
|---|---|---|
| 四個抬頭欄齊 | ✅ | ✅ |
| 射程＝固定值「基金儀表板（my-Fund-dashboard）」 | ✅ | ✅ |
| base commit 正確（`9cbf0377`／母法 `5569d85c`） | ✅ 實測相符 | ✅ |
| §1 寫出**修改後的完整條文**（不是「建議放寬 X」） | ✅ 寫出 §6.4.4-P 全文，並明寫「⛔ 本單不請求放寬 F4 這一格本身」 | ✅ 寫出 F1 第二格豁免全文（射程寫死四行） |
| §3 至少一個「不改母法也能做」＋為何不採用 | ✅ 五個（a~e），(b) 是真正的「不改母法」選項且附實測 | ✅ 五個（a~e），(c) 明寫「這是一個真的選項，不是陪襯」 |
| §4 五個 bullet 齊（凍結邊界／合規／機敏資料／回滾／未涵蓋） | ✅ | ✅ |
| §5 明確表態、不丟選擇題 | ✅ 「推薦採 (a)」＋三條理由 | ✅ 「推薦採 (a)」＋三條理由 |

## D-1 §2 的指令，我逐條重跑

**4a —— 全部可複跑，輸出一致** ✅
```
git show origin/main:services/ai_prompts.py | awk 'NR>=70 && NR<=79'   → :72~:79 八行逐字相符
git grep -n 'build_mk_advisor_prompt' origin/main -- '*.py'
      → production import 恰好 1（services/ai_service.py:23）＋ tests 1（tests/test_ai_prompts.py:8）
git grep -n 'analyze_portfolio_mk_advisor' origin/main -- '*.py'
      → 下游 production import 恰好 1（ui/tab3_t7_ledger.py:59）
git show origin/main:services/ai_prompts.py | grep -cE '非投資建議|教學|僅供|免責'  → 0
（同批對 services/ai_service.py）                                                 → 0
六禁用詞掃 ui/tab3_t7_ledger.py:3284-3402                                        → 0（exit=1）
全檔唯一命中                                                                      → :1990 help="A 推薦：…"
git grep -n 'mk_advisor\|analyze_portfolio_mk' origin/main -- 'ui/views/**'       → 0
正控 build_structured_summary_prompt in ui/views/**  → page_01_macro.py:146 / :1818 / :1873（恰 3 行）
```
鏈路 `ai_prompts.py:30 → ai_service.py:23 → :334 → tab3:59 → :3290-3296 → :3355 → :3401`，以及 `tab3_portfolio.py:78/:2141`、`app.py:673 render_portfolio_tab()` —— **逐行重印全對**。

**4b —— 有一條不可複跑** ⛔（**X-2**）
```
✅ git show origin/main:ui/tab3_t7_ledger.py | awk 'NR==3237||NR==3239||NR==3263||NR==3291'  → 四行全對
✅ git ls-tree -r --name-only origin/main | grep -E '^ui/tab[^/]*\.py$'                       → 16
✅ 正控「換股建議」                                                                            → 恰 2 行（:3239 / :3263）
⛔ 「寬字表掃描（45 詞：加碼／減碼／換股／停利／配置比例／下一步／水位／降槓桿／抄底／接刀／布局／再平衡…）掃全檔 → 63 行命中」
```
**問題**：宣稱 45 詞，**只列出 12 個再加一個 `…`**。我用兩種可得的字表重跑：
```
$ git show origin/main:ui/tab3_t7_ledger.py | grep -cE '<UI_DRAFT §2.1 公布的 43 詞全表>'  → 60
$ git show origin/main:ui/tab3_t7_ledger.py | grep -cE '<4b 自己列出的那 12 詞>'            → 42
```
**60 ≠ 63，42 ≠ 63。** 字表沒有公布 ⇒ **這個數字沒有任何人能複驗**。
母法 §5.1 §2 欄逐字要求「**必須是實測，附指令與輸出**」—— 附了輸出、沒附能產生它的指令。
⚠️ **同一句話在 `DECISION_LOG.md:63`（B30-a）又寫了一次**，兩處同病。
⚠️ 對比：**4a 的每一條指令我都跑得出一模一樣的輸出**，4b 其餘四條也都跑得出來 —— **壞的只有這一條**。

## D-2 4a §2(f)／§4 的「未驗」項，我用靜態方式驗完了（**比 4a 自陳的更嚴重**）

4a 寫：「`tests/test_ai_prompts.py:16` **從函式名看可能**鎖著 `:73` …**未驗，請先驗再用**」。
我 `git show origin/main:tests/test_ai_prompts.py | awk 'NR>=14&&NR<=44'` 逐行讀完，**不必跑 pytest 就能定案**：

| 測試行 | 斷言 | 被它鎖住的來源行 | 該來源行在 4a 射程內？ |
|---|---|---|---|
| `:37` | `assert "必須引用上方「領先指標排名」" in out` | **唯一出處 `:73`**（我在 `:30-93` 全段 grep 過） | ✅ **在**（`:72-79`）→ **改 `:73` 一定轉紅**，4a 猜對了 |
| `:34` | `for h in ("### 🚨 一、","### 🔄 二、","### ⚖️ 三、","### 🎯 四、"): assert h in out` | `### ⚖️ 三、` **唯一出處 `:76`** | ✅ **在** —— **4a 沒有提到這一條** |
| `:29`／`:39` | `assert "子領域燈號歷史回測" in out` | `:54`（射程外）**與** `:79`（射程內）**兩處** | ⚠️ 只刪 `:79` **不會**轉紅（`:54` 還在） |

→ **Y-3**：4a §4「可能要加進射程的一項」只寫了 `:73`，**應為兩項**（`:73` ＋ `:76` 的章節編號前綴）。
⚠️ 據實說清楚：`:34` 斷言的是**前綴** `### ⚖️ 三、`，4a 提的改法是「改寫」不是「刪節」，**若改寫保留「### ⚖️ 三、」編號就不會紅**。所以這是「**射程要寫進去、風險要講明**」，不是「一定會紅」。

## D-3 4b §2(f) 自陳「未跑」的那條，我替它跑了

```
$ git grep -n 'btn_mk_advisor\|策略3' origin/main -- 'tests/**'
origin/main:tests/test_cards_chrome.py:13:  """tab2_single_fund.py:359 策略3 訊號 banner…"""   ← docstring，另一功能
origin/main:tests/test_tab_manage.py:153: """v19.461…美林時鐘(策略3 景氣時鐘觀測站)…"""        ← docstring，另一功能
$ git grep -n '策略3 深度組合建議\|AI 4 節結構\|給不出景氣位階\|生成 策略3 深度建議' origin/main -- 'tests/**'
(0 命中)
```
→ **那四行畫面字沒有任何守衛鎖著**。4b 說「施工前必查」是對的，**查完的結論是：沒有。** 這一條可以從 4b 的待驗清單移除。

---

# E. 計數與尺寸（**逐筆自己數，不相信宣稱值**）

## E-1 42 塊／50 標籤／168 四件

**先跑文件自己那支腳本**（`UI_SPEC.md:70-84` 內附，我逐字照抄執行）：
```
42 {'**沿用（部分）**': 4, '**沿用**': 27, '**新建**': 10, '**不標標籤**': 9, '**查不到**': 0} 50
```

**正控／負控（`r7` 內 inline 探針，實際插進文件副本跑）** ——
- **正控**：附加一個 `### ①-99` 區塊、`- 來源：**新建**` → `(43, …新建 11…, 51)` ✅ **探針真的會亮**
- **負控（證明盲點，不是證明無誤）**：附加 `### ①-98`、把標籤放在 `- 規則` 行 → `(43, …新建 10…, 50)` —— **n 變 43 但標籤沒動** ⇒ 該腳本**只看 `- 來源` 行**，這一點文件自己寫明了（「標籤依定義就住在來源」），是設計不是瑕疵。

**我自己的獨立實作**（不同形狀：先切出每個 `### ` 區塊的完整 body，再分類）：
```
### 標題總數      : 50    （grep -c '^### ' 亦為 50 ✅）
  live ①-N 區塊   : 42
  退役 ~~①-N~~     : 2   （~~①-5~~ / ~~②-2~~）✅ 與文件一致
  排除清單小標     : 6   （甲乙丙丁戊己）✅ 與文件「減六個」一致
逐頁區塊數        : ①10 ②12 ③4 ④8 ⑤8 = 42  ✅ 與文件逐字一致
四件（獨立重數）  : 168 ；per-block shape 分布 {(1,1,1,1): 42}；不是 1/1/1/1 的區塊 = []  ⇒ 缺漏 0、重複 0 ✅
標籤（只數來源行）: 沿用 27 / 沿用（部分）4 / 新建 10 / 不標標籤 9 / 查不到 0 = 50 ✅
多標籤區塊        : ①-1(2) ①-4(3) ②-1(3) ②-13(2) ④-2(2) ④-5(2) → 超出 1 的總量 = 8 ✅
                    ⇒ 50 = 42 + 8 內部自洽 ✅；0 標籤的區塊 = [] ✅
```
**另一個形狀（掃整個區塊 body 而非只掃來源行）** 得 52，多出 2 筆，逐一看過：
- `UI_SPEC:870`（④-6）—— 散文裡的「**查不到**」四個字，不是標籤
- `UI_SPEC:917`（⑤-2）—— **被刪除線劃掉的舊句**裡的「**沿用（部分）**」
**兩筆都是文件自己在 `:66-68` 點名警告過的超算來源**（「戊段的對照表也帶粗體標籤…劃掉的舊句也帶一個」）。

**E-1 判決：42／50／168 三個數字，以及 27/4/10/9/0 的分解、+8 的對帳、逐頁 10/12/4/8/8 —— 全部成立，一筆不差。**

## E-2 §1.6 交叉掃描：**我的獨立 AST 多數到 1 個**（→ Y-7）

`r7/ast16.py` 獨立重跑五種掃描：

| 檔 | safe_section | render_cards | card_row/grid | st.tabs | H2~H4（我） | H2~H4（文件） |
|---|---|---|---|---|---|---|
| page_01_macro | 1 | 8 | 0 | 0 | 8 | 8 ✅ |
| page_02_health | 13 | 1 | 0 | 0 | 5 | 5 ✅ |
| page_03_research | 5 | 1 | 1 | 0 | 4 | 4 ✅ |
| page_04_portfolio | 10 | 0 | 2 | 0 | 9 | 9 ✅ |
| page_05_settings | 7 | 1 | 0 | 0 | **9** | **8** ❌ |

前四種合計 **50**（9/14/7/12/8）✅ 與文件逐格相符；H2~H4 我得 **35**、文件 **34**，總計 **85 vs 84**。

**差在哪（`r7` shape-B 掃描，正控/負控齊）**：
```
POSCTL: page_05_settings.py:1487 必須出現 → True（assert 擋住）
NEGCTL: 接收者名 'zzq_nonexistent_slot' → 0
全五頁「非 st. 接收者」的 H2~H4 標題，實測恰好 1 筆：
  page_05_settings.py:1487   _heading_slot.markdown(f"### {nav_manual_label()}")
```
`:1476 _heading_slot = st.empty()` → `:1483 if not st.checkbox(...)` 的**灰態分支**裡由**本檔**畫 ⑤-6 的標題；gate 打開時才由 `:1493 render_nav_manual_section()` 畫。

⚠️ **文件那句註解只講了一半**：`UI_SPEC` 寫「⑤-6 的標題不在第 5 種掃描的命中裡，**那不是漏掉** —— 標題**刻意由被委派的 `render_nav_manual_section()` 自己畫**」。實測是：**灰態路徑上 `page_05_settings.py` 自己也畫了一次**（`:1487`），只是走的是 `st.empty()` 的 delta-generator，**文件的掃描 5 寫死 `st.markdown/write/subheader/header`，結構上看不到 `<slot>.markdown`**。
**區塊數不受影響**（`:1487` 對回 ⑤-6，本來就是一塊），受影響的是 **34 → 35、84 → 85**，以及那句「不是漏掉」的理由。
→ **Y-7**。**這正是 §1.6 自己寫的那個失效模式（「單一掃描方向在結構上看不到別種呼叫形態」）的第三個實例。**

---

# F. 三條要我獨立重跑的（**我先跑完才去看總管的結論**）

## F-1 `services/risk_radar.py::synthesize_dual_verdict` 有幾個 production 呼叫端？

**答：0 個。**
```
$ grep -rn "synthesize_dual_verdict" --include=*.py .
./services/risk_radar.py:627:def synthesize_dual_verdict(          ← 定義
./tests/test_risk_radar.py:872,884,892,899,906,914,923,929,937,945,951   ← 全部是測試
```
**換兩種形狀確認沒有別名／動態派送**：
```
$ grep -rn "dual_verdict\|synthesize_dual" --include=*.py . | grep -v '^./tests/'   → 只有定義那一行
$ grep -rn "getattr(rr\|getattr(risk_radar\|risk_radar," --include=*.py .
   → ui/views/page_01_macro.py:167 / ui/tab1_macro.py:1958,1960 / ui/tab1_macro_radar.py:89 / tests/test_render_smoke.py:142
   → 這四處 import 的都是 detect_risk_radar, summarize_radar，沒有一個帶到 synthesize_dual_verdict
NEGCTL: grep -rn "synthesize_triple_verdict_qq"  → 0
```
⇒ `:666/:679/:683/:694/:717/:727` 那六句行動指令是**死碼**，**不算當前違規**（已列 C-3 單獨登記）。

## F-2 `page_01_macro.py:801` 與 `:809-810` 那張卡，是不是已經登記在某個既有編號底下？哪一個？

**答：是，兩處都在 —— 而且分別掛在兩個不同的編號下。**
1. **本規格側：`UI_SPEC.md` ①-4「卡 1 📐 建議資產水位」**。實測 `:767 def _card_allocation(ev)` ~ `:814`，`:801 _gate = (...)` 與 `:807-814 return {...}`（`value` 就是 `:809-810`）都在同一支函式內；`UI_SPEC:310-315` 的現況引文表逐列就是 `:809-810`／`:811`／`:801`／`:804-806`／`:785`。渲染點 `:2185-2189 render_cards([_card_allocation(_ev), …])`。
   ⇒ 它是「**本輪之前就已標妥的 ①-4 卡 1**」，`DECISION_LOG` **B21**（客戶裁示 2，另開 `page_01_macro.py` 僅限 ①-4 那一格 F2 豁免），P0 施工第一批**第三項**。
2. **母法側：`:801` 另外被 `CONSTITUTION.md:897` 單獨登記為「待判讀」**。逐字重印：
   `| ui/views/page_01_macro.py:801 | f"停利 Z ≥ {...:+.2f}、加碼 Z ≤ {...:+.2f}（…）" | ⚠️ 門檻說明；**動詞是門檻的名字**，非祈使 —— 本組**不裁決**，列為待判讀 |`
   ⚠️ **兩邊判得不一樣**：母法 `:897` 判「待判讀、不裁決」，`UI_SPEC:312` 判「**G3 具體處置方向**」。
   ⇒ **這個不一致沒有任何一份文件點出來** → **Y-8**（併入 Y 清單，見下）。

## F-3 `services/liquidity_engine.py:483` 那句，從 ① 到得了畫面嗎？經過哪個函式？

**答：到得了。經過 `liquidity_verdict()`。**
```
AST enclosing def of :483  →  liquidity_verdict  (:452 - :488)
$ grep -rn "liquidity_verdict" --include=*.py . | grep -v '^./tests/'
  ui/views/page_01_macro.py:154   （from services.liquidity_engine import ... liquidity_verdict）
  ui/views/page_01_macro.py:1479  if _partial else liquidity_verdict(_score, _factors))
  ui/tab1_macro_radar.py:221,226,239   （舊頁，不是 ①）
```
**完整鏈（逐行重印）**：
`page_01_macro.py:150-155` import → `:1475 _partial = 0 < _n_on < _n_all` → `:1476-1479 _verdict = (…  if _partial else liquidity_verdict(_score, _factors))` → `:1480-1482 st.caption(f"壓力分數 **{…}**（{…}；{_n_on}/{_n_all} 壓力因子在線）：{_verdict}")`。
**閘門**：只有**三軌全部量到（非 partial）**才會走到 `liquidity_verdict()`；partial 時印的是本檔自己寫的「不足以判讀多軌共振，本輪不下研判。」
⇒ **`UI_SPEC` ①-9 對這一點的描述（「衝突在資料最完整的那一支上，不是在降級路徑上」）我獨立重跑後完全同意。**

---

# G. 文件自我一致性

## G-1 ⚠️ `UI_DRAFT_01_MACRO.md:6` 的「787 行」是假的（→ Y-1 併記）
```
> **權威規格**：`spec/UI_SPEC.md`（787 行）§① 的 **10 塊**
$ wc -l spec/UI_SPEC.md  → 1091
```
「① 的 10 塊」✅ 正確（我獨立數到 ①10）。**只有行數是舊的。**
**連帶後果**：DRAFT §2 總表的 `UI_SPEC 標了嗎` 欄對 **H-3~H-11 九列全部寫 ❌**，並在表下寫「**`UI_SPEC` 只標了 1 處（①-4 卡 1）**」——
**這句話對今天的 `UI_SPEC` 是假的**：`UI_SPEC` 現在 ①-1／①-3／①-6／①-8／①-9／①-10／①-11 七塊都掛著 ⛔【母法衝突・待修】，加上 ①-4 ＝ 8+1。
⇒ **同一批交付物裡，一份說「只標了 1 處」，另一份實際標了 9 處。**

## G-2 其他自我一致性（**查了沒問題**）
- `PROPOSAL_4a`／`4b` 互指的編號（#6／#7）與「§8 現有提案 1／2／~~3~~／~~4~~／5，新提案接續編號為 `提案 5`，不填 3／4 的空缺」—— 母法原文逐字核對 ✅
- `DECISION_LOG` B25（「需 F1 ＋ F4 兩個豁免通道」）→ B30（拆 4a／4b）→ 兩張提案單的凍結邊界欄 —— 前後一致 ✅
- `UI_SPEC §0` 的 9 格分頁表：`app.py:581-587` 實測開 9 格（5 正式＋4 預覽）、`:636 render_market_overview()`、`:648/:662/:673/:688` 與 `:720/:728/:752/:776` 逐行相符 ✅
- F2 五頁行數 **2192／1858／2755／2789／1763**（合計 11,357）＋ `__init__.py` **67** —— 與母法 `:73` 逐字相符 ✅
- `PROPOSAL_4b:35`「其餘 3,398 行」＝ 3402 − 4 ✅
- 母法 2,419 行 ✅；`CONSTITUTION.md` 不在 `origin/main`、只在 `origin/docs/v2-constitution-governance`（tip `5569d85`）✅ —— DRAFT `:1093-1094` 的登記屬實
- `CONSTITUTION.md` 被引的 13 個行號（`:72/:73/:75/:580/:582/:801/:895/:896/:897/:1096/:1346/:1348/:1836/:1839/:1840/:1860`）**逐行重印，全部相符** ✅

---

# 判決清單

## ⛔ 擋下（不修不能交）

**X-1｜反向掃描漏掉整支 `services/macro/us_indicators.py`，而 ① 每次渲染都呼叫它兩支函式**
- 證據：五檔文件 `grep -c "us_indicators"` 全 0；`page_01_macro.py:156-161` 直接 import `calc_macro_phase`／`fetch_all_indicators`，兩者實測定義在該檔（`services/macro/__init__.py:44,47`）。
- 至少兩處**到得了 ①**：`:601 desc="…由負翻正=黃金買點"`、`:844 desc="…恐慌=逢低加碼時機"`，路徑 `_ai_snapshot()`（`page_01_macro.py:1762`，`desc` 在該檔的唯一出現處）→ `:1873` prompt → `:1894 st.markdown(_text)`。
- **要做的**：把這條「字面 → `_ai_snapshot` → prompt → 畫面」的間接路徑補進鏈路追法，並就 `:601`／`:844` 給出判定（判違規、判待判讀、或判不命中都可以，但不能沒有落點）。
- ⚠️ 派工單給的 28 詞字表**沒有「買點」**，`:601` 用它掃不到 —— **字表要一併加寬**。

**X-2｜`PROPOSAL_4b §2(b)` 的「63 行命中」不可複跑（`DECISION_LOG:63` B30-a 同病）**
- 宣稱 45 詞、只列 12 詞加 `…`。我用 DRAFT 公布的 43 詞全表得 **60**、用 4b 自己列的 12 詞得 **42**，**都不是 63**。
- 母法 §5.1 §2 欄逐字要求「必須是實測，**附指令與輸出**」。
- **要做的**：把 45 詞全表寫進去（或改成可貼可跑的單行指令），兩處一起改。
- ⚠️ 對照：**4a 的每一條指令我都跑出一模一樣的輸出**，4b 其餘四條也是。壞的只有這一條。

## 要改（不擋）

- **Y-1｜三處「DRAFT 標了、權威規格沒有落點」**：`story_nav.py:332`／`page_01_macro.py:2067`／`us_liquidity_engine.py:182`（DRAFT 的 H-1／H-2／H-8）在 `UI_SPEC.md` 與 `DECISION_LOG.md` **0 命中**，也不在 UI_SPEC〈待確認〉11 項裡。**併記**：`UI_DRAFT:6` 的「`UI_SPEC.md`（787 行）」實測 1091，連帶讓 DRAFT §2 那句「`UI_SPEC` 只標了 1 處」在交付當下為假。
- **Y-2｜`services/macro/explain.py:238-258` 是 ①-3 五句 action_text 的逐字複製品**，五檔 0 提及。到不了 ①，但 ①-3 的修法若只動 `composite_score.py`，這一份會原封活著（SSOT 破口）。
- **Y-3｜4a §4 的守衛射程只寫了 `:73`，應為兩項**。`tests/test_ai_prompts.py:34` 的 `assert "### ⚖️ 三、" in out` 鎖住 `:76`（唯一出處）。另據實記：`:29/:39` 的「子領域燈號歷史回測」在 `:54` 也有一份，**只刪 `:79` 不會轉紅** —— 4a 沒說錯，但也沒說到。
- **Y-4｜`UI_SPEC:119` 一句話並排兩個檔的行號、一個檔名都沒寫**：`甲-1 ＝ :1851`（實測在 `page_02_health.py`）與 `乙-1 ＝ :2783`（在 `page_04_portfolio.py`）。同一份文件 `:6` 才剛警告過「兩份行號不是依序對應的，不要用並列去配」。
- **Y-5｜兩處 `.py` 引文被引述者加了粗體、沒有標註**：`UI_DRAFT:857`（引 `page_01_macro.py:1869`）、`UI_SPEC:113`（引 `page_01_macro.py:765`）。不擋，因為兩處都不在「現況引文・待修」表格裡。
- **Y-6｜三筆字元層不忠實，全部發生在自稱「逐行重印核對／原樣引用」的段落**：
  (a) `UI_SPEC:864` 把 `"moneydj_raw":  pf_raw,` 的**雙空格壓成單空格**；
  (b) `UI_SPEC:313` 把 `f"…{_al['light']}燈調整。"` 的識別字**換成 `{light}`**；
  (c) `UI_SPEC:693` 的 code span 寫成 `` `…每一節都用 \`### \` 開頭當標題，` `` —— **CommonMark 的 code span 內不吃反斜線逃脫**，這一格會渲染成破的。原文字面本身是對的。
- **Y-7｜§1.6 掃描 5 的形狀盲，數字少 1**：`page_05_settings.py:1487 _heading_slot.markdown(f"### {nav_manual_label()}")` 是 `st.empty()` 的 delta-generator，文件寫死 `st.markdown/write/subheader/header` ⇒ 看不到它。⑤ 的 H2~H4 應為 **9**、總計 **35**、grand **85**。**區塊數 42 不變**（對回 ⑤-6）。連帶：「⑤-6 的標題不在命中裡，那不是漏掉 —— 由委派畫」**只講了 gate 開的那一半**，灰態路徑上本檔自己畫了一次。
- **Y-8｜`page_01_macro.py:801` 母法與規格判得不一樣，沒有人點出來**：母法 `:897` 判「⚠️ 待判讀、本組不裁決」，`UI_SPEC:312` 判「**G3 具體處置方向**」。兩份文件對同一行給了兩個答案。

## 查了但沒問題（照實寫下來）

- **Z-1** 補標 8 處的**引文**：29 行來源逐行重印，**逐字全對**，含 `action_light.py:176/:188` 的半形逗號、`tab3:3263` 的半形分號（文件都有就地標註）。
- **Z-2** 補標 8 處的**鏈路**：八條我都從 `page_01_macro.py` 的 import 面追到 `st.*`，**八條全部成立**。其中 ①-8 的關鍵一步（`:1117` lazy import `ui.tab1_macro_midcycle`）我確認那是該檔**唯一**一個 `ui/tab*` import。
- **Z-3** 補標 8 處的**凍結面**：對 `5569d85:CONSTITUTION.md:72-77` 的 F 表逐格核，**八處全對**；①-8 是其中唯一踩 F1 的，文件的宣稱正確。
- **Z-4** `8 + ①-4 = 9` 的對帳成立；①-4 卡 1 的五列引文與 `signal_thresholds.py:409` 的 1.75 都對。
- **Z-5** E 節全部計數：42／50／168／27-4-10-9-0／+8／①10 ②12 ③4 ④8 ⑤8／`grep -c '^### '`＝50／退役 2／排除小標 6 —— **一筆不差**（用與文件不同的實作重數）。
- **Z-6** A-3 重複引文一致性：28 條核心引文、共 70+ 次出現，**沒有任何一條出現「幾處忠實一處加粗」**。
- **Z-7** 15 筆 BOLD_ADDED 逐筆看過，**13 筆是引述母法／`CLAUDE.md` 的強調句，屬中文引述慣例**；剩 2 筆列 Y-5。
- **Z-8** 4a §2 的**全部**指令我重跑，輸出逐字一致（含 `mk_advisor` in `ui/views/**` → 0 與它的正控 3 行）。
- **Z-9** 4b §2(f) 自陳「未跑」的守衛掃描，我替它跑完：**那四行畫面字沒有任何守衛鎖著**（唯二 `策略3` 命中是別的功能的 docstring）。
- **Z-10** `risk_radar.synthesize_dual_verdict` 0 production caller（三種形狀確認）—— **DRAFT 已自己寫下這一筆，我獨立重跑結論相同**。
- **Z-11** `decision_matrix` 的動作標籤／`allocation_ladder` 的 `action_text`／`macro_card_edu` 的「黃金買點」／`causal_sankey` 的「建議減碼至中性」／`tab1_macro_inflection` 三處 —— **逐條追消費端，全部到不了 ①**。

---

# 我這套方法掃不到什麼（誠實列，不美化）

1. **沒有跑任何測試、沒有啟動 Streamlit。** 所有「到得了畫面」都是**靜態鏈路推導**（AST ＋ 逐行讀），不是實跑渲染。`_ai_snapshot → prompt → 模型輸出` 那一段我只驗到「字串進得了 prompt」，**模型會不會把它講出來，我沒有驗、也沒有辦法在這裡驗**。
2. **import 閉包 ≠ 渲染可達。** `closure.py` 給的 116 個模組是 import 面；我是靠人工逐條回查消費端來收斂的。**我沒有做完整的 call-graph 可達性分析**，所以「某某到不了 ①」這一類句子**取決於我有沒有漏看某個消費端**，屬全稱句。
3. **字表永遠追不上措辭。** 我加寬了字表（多 34 詞）才撈到「黃金買點」；下一個措辭（例如「甜蜜點」「上車」「下車」「布局良機」）我這一輪同樣掃不到。**「① 沒有第 11、第 12 處」我不宣稱。**
4. **動態組出的字串我看不到。** `f"…{fn()}"` 裡函式回傳的文案、`getattr`／dict 派送、runtime 才決定的 label —— AST 一律看不到。`story_nav.py:332` 那一條我是**實跑純函式**才確認的，其餘沒有一條這樣做。
5. **引文比對只覆蓋「我能配對到 `(檔, 行)` 的那些」。** `tablecheck.py` 解析出 71 列表格引文、`prefixcheck.py` 另 100+ 條前綴式引用；**散文裡不帶行號的轉述我沒有系統性查**（只在讀到時順手核）。
6. **`verify_quotes.py` 的 ABSENT 分支我沒有逐筆判讀完。** 五檔合計 1497 條「在原始碼樹裡找不到逐字對應」的 span，我只篩出「看起來像程式碼」的 88 條逐一看過，其餘（絕大多數是文件自己的散文）**沒看**。
7. **`UI_PAGE_TODAY.md` 不在受稽核清單，我沒有掃它** —— 但它就躺在同一個 `spec/` 目錄裡，如果它也宣稱了計數，那份沒有被任何人對過。
8. **我沒有讀完 `CONSTITUTION.md` 全文**（2,419 行），只逐行重印核對了被引用到的 16 個行號與 §5.1 範本、§1.1 F 表。**「母法沒有第 17 處相關條文」我不宣稱。**
9. **`DECISION_LOG.md` 我只查了被交叉引用到的 B 條目**（B2／B8／B21／B21-a／B25／B28／B29／B30／B30-a）與 §H 的存在性，**560 行沒有逐行通讀**。
10. **單組產出，沒有第二組驗過。** 本報告裡的每一個「全部」「唯一」「0 命中」都是**取決於我有沒有漏看**的句子。上面每一條我都附了指令與原始輸出，**請照著重跑，不要引用我的結論**。
