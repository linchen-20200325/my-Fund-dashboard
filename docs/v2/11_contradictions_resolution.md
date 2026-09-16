# 8 條矛盾的處理結果（盤點生產組，2026-09-16）

**基準**：`origin/main = 9cbf03776f2a0ee6bdb5a649efb93352c40baba6`
（一律 `git show origin/main:<path>` / `git grep … origin/main` 讀取；工作樹 HEAD `d0c2a8d` **全程未碰**）
**對象**：`inv/DB_INVENTORY.md`（盤點生產組）✕ `audit/DB_INVENTORY_AUDIT.md`（盤點稽核組）
**產出者**：盤點生產組（**單組產出，沒有第二組看過**）

**⛔ 本輪零程式碼變動**：未改 repo 任何檔案、未 commit／push／merge、未碰 `pr829`~`pr834`、
未連任何外部 API、**未讀寫任何 Google Sheets（連唯讀都沒有）**、未觸發任何 workflow、未 `pip install`。
git 只用了唯讀動詞（`show` / `grep` / `ls-tree` / `rev-parse`）。
**只動了兩個檔**：`inv/DB_INVENTORY.md`（就地改）與本檔（新建）。
⛔ **`ui/tab6_manual.py` 一個 byte 都沒有動**（客戶凍結令）。

**方法註記（2026-09-16 補）**：負控字串不得寫進文件；掃描時須排除自身檔案。

---

## 0. 怎麼讀這份文件

- **A 立場** ＝ 盤點表 `inv/DB_INVENTORY.md` 的原文。
- **B 立場** ＝ 稽核報告 `audit/DB_INVENTORY_AUDIT.md` 的原文。
- **我的實測** ＝ 本輪自己重跑，**每條都附正控與負控**，指令與真實輸出照抄。
- **判定**：
  - **已解** ＝ 兩邊其實可以同時為真（用詞／口徑不同），或其中一邊有明確事實錯誤 → **已就地把盤點表改對**。
  - **不解** ＝ 需要客戶／總管的**定義決定**才能定案 → **本組不裁決**，理由寫在下方「不解區」。
- ⚠️ **行號說明**：A 立場引的行號是**本輪改動前**的 `inv/DB_INVENTORY.md`（＝稽核報告引用的那一版，870 行）。
  本輪改完後該檔為 1115 行，行號整體下移；**引用時請改用節號**（§1.4 / §2.1 …），不要用行號。
  B 立場引的行號是 `audit/DB_INVENTORY_AUDIT.md`，**本輪一個字都沒動它**，行號仍有效。
- ⚠️ **本文件不含任何實際 token／金鑰／sheet id／帳號或其片段**。需要指涉時一律寫「值不列出」。

---

## 1. 總表

| # | 主題 | 判定 | 一句話 |
|---|---|---|---|
| 1 | `cache/nav/*` 8 列標「活的」 | **已解** | 盤點表 §0 自己的定義加上它自己的兩個同型前例（§2.12／§2.14）都指向「只讀不寫」，§2.1 是唯一沒套到的地方 → 已改 |
| 2 | `accumulate_nav_tw.py` 列在「寫（CI 排程）」 | **已解** | workflow 0 命中（正控命中），repo 三處都說它是使用者 NAS crontab → 已移出並改記 |
| 3 | `_Ledgers` 標「活的」 | **不解** | 爭點是「production **讀取**」的定義（位元組讀回來 vs 資料到得了消費者），§0 沒有界定，而盤點表自己在 §1.4 與 §2.3 用了相反的兩把尺 → **定義權不在本組** |
| 4 | `fund.db` 8 列標「活的」 | **已解** | §0 把 production 界定在**本 repo 之內**，讀取端在下游 repo → 「只寫不讀」；已就地大聲註明「不是沒人用」 |
| 5 | `env.ANTHROPIC_API_KEY`／`OPENAI_API_KEY` 標「查不到」 | **已解** | 事實錯誤：**寫入端與讀取端都在 production**（`app.py:335-338` 寫、`infra/llm.py:71,72` 讀，UI 鏈實測可達）→ 改為「活的」 |
| 6 | §3 節標題「只活在記憶體、沒有落地的」 | **已解** | 三處（§0 `未落地` 定義／§3 標題／§5.1 摘要）一起改；**自己重數後是 32 列有落地，不是 18** |
| 7 | `templates/` 4 列標「只讀不寫（人讀）」 | **已解** | §0 的封閉集合沒有「人讀」，且無 production 讀取端（正控命中 15 行）→ 改為「查不到」，價值說明留在備註 |
| 8 | PPI／銅價「沒有資料可畫」 | **已解** | 「一列都沒有」為真、「沒有資料可畫」為假 → 拆成「即時值可畫／歷史值不可畫」兩列，並補上一個單位陷阱 |
| ＋ | 說明書「這 6 種分頁」 | **已解（文件端）** | 實際 **9 種、分屬 4 本**；盤點表已寫完整，`.py` 的替換全文見下方「待施工的更正」 |

**已解 7 條、不解 1 條。**

---

## 2. 逐條

### 矛盾 1｜`cache/nav/*` 8 列標「活的」 → **已解**

**A 立場**（盤點表 §2.1，改動前 `:260-267` 8 列、`:269-270`）：
8 列狀態欄逐列寫 `活的`；同一節的散文寫
> 「寫：`scripts/fetch_nav_cache.py:539`（`save_cache`）—— ⚠️ **`.github/workflows/fetch_nav_cache.yml` 不存在**
> （`git ls-tree -r --name-only origin/main | grep '^.github/workflows/'` 共 8 個，無此檔）→ **只剩手動觸發**」

同表 §0（改動前 `:14`、`:21-22`）：
> 「**活的** ＝ 有 production 寫入 **且** 有 production 讀取」
> 「『production』＝ 從 `app.py` 可達的 UI 路徑，或 `.github/workflows/` 有排程的 script。
> **手動 CLI script**（沒有 workflow 掛它）另行註明，不當 production。」

**B 立場**（稽核報告 `:39-45`）：
> 「**兩者不能同時為真**：若 §0 的定義成立，寫入端不是 production，該 8 列應落在「只讀不寫」；
> 若 8 列的「活的」成立，§0 那條定義就不成立。」
> 「**旁證（同一把尺在別處是往另一邊倒的）**：盤點表對 `data_cache/macro_thresholds_global.json`（§2.12）
> 與 `snap.json`（§2.17）**確實**套用了「手動 CLI 不算 production」…… **同一條規則在 §2.1 沒有套用。**」

**我的實測**（repo 根，指令與真實輸出照抄）：

```
$ git ls-tree -r --name-only origin/main | grep '^.github/workflows/'
.github/workflows/dividend_calendar_notify.yml
.github/workflows/export_db.yml
.github/workflows/fill_pool_currency.yml
.github/workflows/pr-check.yml
.github/workflows/update_macro_history.yml
.github/workflows/watchlist_verify.yml
.github/workflows/weekly_nav_backfill.yml
.github/workflows/weekly_switch_notify.yml          ← 8 個，無 fetch_nav_cache.yml

$ git grep -n "fetch_nav_cache" origin/main -- '.github/workflows/*'
origin/main:.github/workflows/update_macro_history.yml:4:  # 每週日 UTC 00:00（台灣時間 週日 08:00）— 與 fetch_nav_cache 每日 cron 錯開
                                                     ← 1 行，而且是註解

正控 $ git grep -n "export_fund_db" origin/main -- '.github/workflows/*'
origin/main:.github/workflows/export_db.yml:39:        run: python scripts/export_fund_db.py --no-live --output fund.db

負控 $ git grep -n "<負控串>" origin/main -- '.github/workflows/*'
（無輸出，exit=1）
```

**判定：已解。**
**理由**：這**不是**「活的」這個詞的定義之爭 —— §0 已經把定義寫死，而且**同一份盤點表在另外兩個同型情境都照著做了**：
§2.12 `macro_thresholds_global.json`（手動 CLI 寫、production 讀）標 **只讀不寫**；
§2.14 `config/preset_funds.json`（只能人手改檔＋git commit、production 讀）標 **只讀不寫**。
§2.1 是**同一條規則唯一漏套的地方**，屬「A 的明確事實錯誤（自己的規則沒一致套用）」，不是治理問題。

**改在哪**：盤點表 §2.1 —— 8 列 `活的` → `只讀不寫`，並在該節末加就地更正註（含上列指令輸出、兩個同型前例、
以及「⚠️ 這不代表這份快取沒在用」的反誤讀提醒）。§5.2 統計同步重算。

**⛔ 什麼情況會翻回去**：若客戶／總管決定「**已 commit 進 repo 的資料檔**也算 production 寫入」，
那是 **§0 定義的修改**，本列會翻回「活的」——**而且 §2.12／§2.14 必須一起翻**。本組不代為裁決該定義。

---

### 矛盾 2｜`accumulate_nav_tw.py` 被列在「寫（CI 排程）」 → **已解**

**A 立場**（盤點表 §1.6，改動前 `:173`）：
> 「寫（CI 排程）：`scripts/weekly_nav_backfill.py`（`.github/workflows/weekly_nav_backfill.yml`）、`scripts/accumulate_nav_tw.py`」

**B 立場**（稽核報告 `:47-52`）：
> 「`git grep -n "accumulate_nav_tw" -- '.github/workflows/*'` → **0 命中**……該腳本在 repo 內被記載為
> **使用者自己 NAS／本機的 crontab**：`docs/NAV_NAS_CRON_SETUP.md:89`……`STATE.md:1404` 同一句、
> `scripts/accumulate_nav_tw.py:18` 自己的 docstring 也是同一句。」

**我的實測**：

```
$ git grep -n "accumulate_nav_tw" origin/main -- '.github/workflows/*'
（無輸出，exit=1）
正控 $ git grep -n "export_fund_db" origin/main -- '.github/workflows/*'
origin/main:.github/workflows/export_db.yml:39:        run: python scripts/export_fund_db.py --no-live --output fund.db
負控 $ git grep -n "<負控串>" origin/main -- '.github/workflows/*'
（無輸出，exit=1）

逐行原文（awk 'NR==N' 直接印，未經任何 grep -v）：
docs/NAV_NAS_CRON_SETUP.md:89 →
30 18 * * 1-5  cd /path/to/my-Fund-dashboard && python scripts/accumulate_nav_tw.py >> /var/log/nav_accumulate.log 2>&1
STATE.md:1404 →
  `30 18 * * 1-5 cd <repo> && python scripts/accumulate_nav_tw.py`(台灣時間傍晚,NAV T+1 多傍晚更新)。
scripts/accumulate_nav_tw.py:18 →
     30 18 * * 1-5  cd /path/to/my-Fund-dashboard && python scripts/accumulate_nav_tw.py

它寫到哪：scripts/accumulate_nav_tw.py:73-74 →
        from services.nav_history_gs import append_points
        append_fn = append_points          ← 寫 nav_history（淨值本）
```

**判定：已解。** A 把「有 cron」讀成「有 CI 排程」，是明確事實錯誤。
**兩者的差別是誰在跑**：GitHub Actions 在 repo 裡看得到、查得到上次執行時間；NAS crontab **不在 repo、也不在 Actions**。

**改在哪**：盤點表 §1.6 —— 拆成兩行（「寫（CI 排程）」只留 `weekly_nav_backfill.py`；
新增一行「寫（**使用者自己的 NAS／本機 crontab —— 不在本 repo 的 CI 內**）」），加就地更正註。
**`nav_history` 7 欄的「活的」沒有動**：它另有 3 個 production UI 寫入端 ＋ 1 個真正掛 workflow 的 CI 寫入端。

**⚠️ 這一條的份量（不要只看分類改了）**：`nav_history` 是盤點表標為「**唯一不可再生**」的那張表。
它每天有沒有在累積，**取決於使用者 NAS 上那條 crontab 有沒有在跑** —— **本盤點查不到它現在的狀態。**

---

### 矛盾 3｜`_Ledgers` 9 列標「活的」 → **不解**

**A 立場**（盤點表 §1.4，改動前 `:128-130`）：9 列狀態欄逐列寫 `活的`；
> 「讀：`ui/helpers/portfolio/policy_admin_section.py:825`（`load_all_ledgers`，`ledger_repository.py:111`）」

**B 立場**（稽核報告 `:54-61`）：
> 「`ui/helpers/portfolio/policy_admin_section.py:825-832` 只取 `_led_ct = len(_led_df)` 塞進
> `st.session_state["_sheet_stats"]`；**同一個檔案 `:843-845` 的註解逐字寫著**：
> 「本處寫入的 `_sheet_stats` **全 repo 沒有任何讀取端**（AST + grep 窮舉：只有這一行寫、無人讀）」」
> 「**同一把尺在 §2.3 是往另一邊倒的**：盤點表把 `cache/fund_history.json` 6 列標成「**只寫不讀**」，
> 理由逐字是「唯一讀到檔案內容的是 `record_fund` 自己的 read-modify-write，**沒有任何下游消費者**」。」

**我的實測**（三項全部成立）：

```
$ git show origin/main:ui/helpers/portfolio/policy_admin_section.py | awk 'NR>=824 && NR<=834'
824:                        try:
825:                            _led_df = load_all_ledgers(_cli, _sheet_id)
826:                            _led_ct = len(_led_df)
827:                        except (PolicySheetError, OAuthError):
828:                            _led_ct = "—"
829:                        st.session_state["_sheet_stats"] = {
830:                            "tabs": len(_tabs_x),
831:                            "t7_state": _meta_x.get("row_count", 0),
832:                            "ledgers": _led_ct,
833:                            "last_sync": _meta_x.get("latest_updated_at", ""),
834:                        }
        → 9 個欄位的內容一個都沒被使用，只用了 len()

$ git grep -n "_sheet_stats" origin/main -- .
.py 內僅 policy_admin_section.py 的 :819(註解) / :820(def) / :829(唯一寫入) / :843(註解) / :871(呼叫)
另 3 筆在 ARCHITECTURE.md:1046、SPEC.md:1312、SPEC.md:1321（文件）
        → 零讀取端
正控 $ git grep -c "portfolio_funds" origin/main -- 'ui/helpers/portfolio/policy_admin_section.py' → 5
負控 $ git grep -n "<負控串>" origin/main -- .  → 無輸出，exit=1

$ git show origin/main:ui/tab3_portfolio.py | grep -n "load_all_ledgers"
42:    load_all_ledgers,
        → 全檔只出現 1 次，就是 import 本身，從未呼叫
（另查根目錄 shim：git ls-tree origin/main -- ledger_store.py → 無輸出，該 shim 已不存在，沒有第二條 import 路徑）
```

**判定：不解。**

**為什麼不能就地解 —— 這條的爭點不是事實，是「production 讀取」的定義**：
§0 只寫「有 production **讀取**」，**沒有界定「讀取」是指哪一種**：

| 讀法 | 意思 | 對 `_Ledgers` 的結論 |
|---|---|---|
| **甲（位元組）** | gspread 真的把那張分頁抓回來了 | **活的**（現行值） |
| **乙（到得了消費者）** | 資料要真的被下游用到 | **只寫不讀** |

**而盤點表自己在 §2.3 用的正是讀法乙**（`cache/fund_history.json` → 只寫不讀，理由是「沒有任何下游消費者」）。
**同一把尺在兩節給出相反結果，這件事是真的；但該用哪一把尺是治理決定，不在本組權限內。**

⚠️ **這不是「查不清楚」，是「查清楚了但沒有判準」。** 上面三項事實本組全部實測、全部成立；
卡住的是把事實對到哪個狀態詞。**定義權在客戶／總管。**

**要客戶決定的是一句話**：
> 「**production 讀取**」是指「**程式真的把資料讀回來了**」，還是「**讀回來的資料真的被用到了**」？

**兩種裁定的連帶後果（先講清楚，免得只改一處）**：
- 裁「讀法甲」 → `_Ledgers` 維持「活的」，**但 §2.3 `cache/fund_history.json` 6 欄要從「只寫不讀」翻成「活的」**
  （它同樣有「真的讀回來」的動作：`record_fund` 的 read-modify-write）。
- 裁「讀法乙」 → `_Ledgers` 9 列改「只寫不讀」，§2.3 維持不動。

**本輪在盤點表做了什麼**：§1.4 **狀態欄一格未動**，只就地補上三項實測事實，並註明爭點與出口指回本節。

---

### 矛盾 4｜`fund.db` 8 列標「活的」 → **已解**

**A 立場**（盤點表 §2.18，改動前 `:503-510`）：`global_index`／`fred_macro`／`fund_universe` 共 8 列寫 `活的`。

**B 立場**（稽核報告 `:63-68`，引盤點表同一節改動前 `:514-515` 與 §6 發現 8 改動前 `:775`）：
> 「⚠️ 消費者是**下游另一個 repo**（`export_fund_db.py:4` 明文「供下游 2026_strategy_0719 多智能體系統讀取」），
> **本 repo 的 UI 不讀它**」

**我的實測**：

```
$ git grep -nE "fund\.db|FUND_DB|sqlite3|sqlite" origin/main -- '*.py'   （排除 tests/）
→ 13 行，全部在 scripts/export_fund_db.py（生產者）：:2 :19 :31 :58 :69 :75 :102 :137 :164 :179 :180 :184 :188
  外加 infra/asset_publish.py:15 —— 一行註解（講 force-push 慣例，不是讀取）
正控 $ git grep -cE "parquet" origin/main -- '*.py'  → 8 檔命中（含 services/macro/validation.py、
      services/us_liquidity_engine.py 等真讀取端）
負控 $ git grep -n "<負控串>" origin/main -- .  → 無輸出，exit=1

$ git show origin/main:scripts/export_fund_db.py | awk 'NR==4'
供下游 2026_strategy_0719 多智能體系統讀取。「各源專案各自 export」架構(my-Fund 段)。
```

**判定：已解。** §0 把「production」界定在**本 repo 之內**（「從 `app.py` 可達的 UI 路徑，
或 `.github/workflows/` 有排程的 script」），而「活的」要求**兩端都是 production**。
寫入端 ✅（`export_db.yml`，cron `0 21 * * *`）；讀取端 ❌（在別的 repo）→ 依 §0 ＝ **只寫不讀**。
**A 的狀態欄與它同一節的散文本來就互相打架**，這是內部不一致，不是定義之爭。

**⛔⛔ 已在盤點表就地大聲註明，這裡再講一次**：
**「只寫不讀」＝「本 repo 內沒有讀取端」，不是「沒人用」。**
它真正的消費者是下游 repo `2026_strategy_0719`，那個消費者是真的、而且是這支 script 的存在理由。
**任何人拿這三個字去刪 `export_fund_db.py` 或停掉 `export_db.yml`，都是誤讀。**

**改在哪**：盤點表 §2.18 —— 8 列 `活的` → `只寫不讀`，加就地更正註（含反誤讀警語與翻回條件）。

---

### 矛盾 5｜`env.ANTHROPIC_API_KEY` / `env.OPENAI_API_KEY` 標「查不到」 → **已解**

**A 立場**（盤點表 §4.2 最後一列，改動前 `:690`）：
> 「| `env.ANTHROPIC_API_KEY` / `env.OPENAI_API_KEY` | 查不到（本 repo 無消費路徑） | `infra/llm.py:71,72` |
> 只在 `infra/llm.py` 內取；本 repo 的 AI 走 Gemini |」

**B 立場**（稽核報告 `:70-79`）：
> 「讀取端存在且在 production 路徑上（每次 AI 顧問都會執行那兩行 `os.environ.get`），與「兩端都查不到」互斥。
> 「key 沒設定」與「沒有消費路徑」是兩件事。」

**我的實測（逐段追，比 B 多查到一件事：寫入端也在 production）**：

```
讀取端 $ git show origin/main:infra/llm.py | awk 'NR>=69 && NR<=80'
69:    keys = {
70:        "gemini":    gemini_key    or os.environ.get("GEMINI_API_KEY", ""),
71:        "anthropic": anthropic_key or os.environ.get("ANTHROPIC_API_KEY", ""),
72:        "openai":    openai_key    or os.environ.get("OPENAI_API_KEY", ""),
73:    }
74:    chain = provider_chain or _DEFAULT_CHAIN
75:    errors: list[str] = []
76:    for provider in chain:
        （:33 _DEFAULT_CHAIN = ["gemini", "anthropic", "openai"]；:85-93 真的會 caller(key, ...)）
        → 這三行在 call_llm 內，每次呼叫都執行，與 key 有沒有值無關

★ 寫入端（B 沒查到這一段）$ git show origin/main:app.py | awk 'NR>=333 && NR<=341'
333:    # v18.113 AI-3: 多 LLM provider fallback chain — 額外載 Anthropic / OpenAI keys
334:    # 有設就匯出到 env，infra/llm.py::call_llm 會自動讀；缺則該 provider 在 chain 中 skip
335:    for _llm_key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
336:        _v = _secret(_llm_key)
337:        if _v:
338:            os.environ[_llm_key] = _v
339:    return fred, gem
340:
341: FRED_KEY, GEMINI_KEY = _load_keys()      ← module top-level，無條件執行

UI 可達鏈（逐段實測）：
app.py:673  render_portfolio_tab()                        （app.py:157 import）
  → ui/tab3_portfolio.py → ui/tab3_t7_ledger.py:3355 analyze_portfolio_mk_advisor(...)  （:59 import）
  → services/ai_service.py:341  return call_llm(prompt, max_tokens=5000, gemini_key=api_key)
                                （def ＠:130；:22 from infra.llm import _call_gemini, call_llm）
  → infra/llm.py:71,72

正控 $ git grep -n "call_llm" origin/main -- '*.py'（排除 tests）→ 5 行（app.py:334 註解、infra/llm.py:13,39、
       services/ai_service.py:22,341）—— 命中，不是 0
負控 $ git grep -n "<負控串>" origin/main -- .  → 無輸出，exit=1
```

**判定：已解（A 的明確事實錯誤）。**
**兩端都在 production**：寫入端 `app.py:335-338`（module top-level 無條件跑）、讀取端 `infra/llm.py:71,72`
（`call_llm` 內每次都跑，且 gemini 失敗時**真的會輪到** anthropic／openai）。
依 §4 這一節的既有慣例（該節其餘 32 列的「活的」＝「有 production 消費路徑」），本列 → **活的**。

**改在哪**：盤點表 §4.2 最後一列 —— 狀態 `~~查不到（本 repo 無消費路徑）~~ → **活的**`，
出處補上寫入端 `app.py:335-338`，備註寫完整 UI 鏈。

**⚠️ 附帶發現（本輪只登記、不加列）**：§4.1 `st.secrets` **沒有列**
`secrets.ANTHROPIC_API_KEY` / `secrets.OPENAI_API_KEY` —— `app.py:336` 的 `_secret()` 讀的就是它們。
這是**漏盤**。本批任務是處理矛盾、不是重新盤點，**加列會動到 264 這個已被稽核複核過的總數**，
故只在 §4.2 該列的備註裡登記，留給下一輪補。

---

### 矛盾 6｜§3 節標題「只活在記憶體、沒有落地的」 → **已解，但 B 的數字也錯了**

**A 立場**：§3 節標題（改動前 `:544`）「**只活在記憶體、沒有落地的**（`st.session_state`）」；
§5.1 統計表（改動前 `:710`）「§3 **只活在 session** 的表格狀結構｜6｜60」；
§0 分類定義（改動前 `:19`）「**未落地**｜算得出來但沒有持久化（只活在 session）」。

**B 立場**（稽核報告 `:81-86`）：
> 「§3.1 標題（第 549 行）「`t7_ledgers` — ⚠️ **這一項要更正：它其實有落地**」，其 **15 列狀態全為「活的（有落地）」**；
> §3.3 標題（第 605 行）「`batch_codes` / `batch_rows` — 批次分析（**有落地**，見 §2.11）」，其中 3 列為「活的」。」
> 「**本組重數**：§3 共 60 列，其中 **18 列**（15 ＋ 3）標為活的／有落地 ＝ 30%。」

**我的實測 —— 重點在這裡：`18` 不對，實數是 `32`。**

**數法（可複跑，不經任何 `grep -v`）**：以 markdown 表格列 parser 逐列取第 2 欄，
去掉 `**` 與全形括號補語後，**只認 §0 那六個封閉狀態值**；跳過表頭列（第一欄 ＝「表 . 欄位」）與分隔列。

| 小節 | 列數 | 活的 | 未落地 |
|---|---|---|---|
| §3.1 `t7_ledgers` | 15 | **15** | 0 |
| §3.2 `portfolio_funds` | 22 | **14** | 8 |
| §3.3 `batch_codes` / `batch_rows` | 6 | **3** | 3 |
| §3.4 `t7_scenarios` | 8 | 0 | 8 |
| §3.5 其他 session 表 | 9 | 0 | 9 |
| **合計** | **60** | **32** | **28** |

15 ＋ 14 ＋ 3 ＝ **32**；8 ＋ 3 ＋ 8 ＋ 9 ＝ **28**；32 ＋ 28 ＝ **60** ✅（＝ 53% / 47%，不是 30%）

**差在 §3.2 那 14 列**：稽核組（以及本輪派工單）都只數了 §3.1 與 §3.3，**漏掉 `portfolio_funds`**。
那 14 列的狀態欄逐列寫「活的」，出處指向 `repositories/policy/v1.py:248-255,262,265` 與
`ui/helpers/portfolio/load.py:126,128,130,242`，**全是真的落到 Sheet 的欄位**：
`code` / `invest_twd` / `policy_id` / `policy_name` / `currency` / `invest_date` / `fx_at_buy` /
`policy_tier` / `div_cash_pct` / `avg_nav_with_div` / `avg_nav` / `fx_avg` / `units` / `is_core`。
§3.2 的小標本來就寫著「**未落地：只有部分欄位落地**」—— 它從一開始就是混合的，只是沒有人把數字數出來。

**判定：已解。** 三處一起改：
1. **§3 節標題** → `## 3. 走 st.session_state 的表格狀結構（60 列中 32 列另有落地、28 列重繪即消失）`，
   舊標題加刪除線保留 ＋ 分小節計數表 ＋ 數法。
2. **§0 `未落地` 定義** → 原定義保留，補限定：「這是**單一欄位**的狀態，**不是 §3 整節的性質**」。
3. **§5.1 摘要表那一列** → `~~§3 只活在 session 的表格狀結構~~ → §3 走 session_state 的表格狀結構（60 列中 32 列另有落地）`。

**⚠️ §3 任何一列的狀態欄本輪一格未動** —— 改的是標題與分類名的全稱性。

---

### 矛盾 7｜`templates/` 4 列標「只讀不寫（人讀）」 → **已解**

**A 立場**（盤點表 §2.20，改動前 `:533` 節標題、`:537-540` 4 列）：
節標題「範本 CSV／JSON（`templates/`，供使用者複製，**程式不讀**）」，4 列狀態寫 `只讀不寫（人讀）`。
§0 定義（改動前 `:16`）：「**只讀不寫** ＝ 有 production 讀取，查不到寫入端」。

**B 立場**（稽核報告 `:88-93`）：
> 「若「程式不讀」成立，依 §0 這 4 列應為「查不到」；若「只讀不寫」成立，就得有一個 production 讀取端。
> （括號「（人讀）」是盤點表自創的補充，§0 的封閉集合沒有授權這種放寬。）」

**我的實測**：

```
$ git grep -nE "nav_history_sample|preset_funds_sample|portfolio_backup_sample|fund_history_sample" origin/main -- .
origin/main:templates/README.md:10   ← 文件表格
origin/main:templates/README.md:11
origin/main:templates/README.md:12
origin/main:templates/README.md:13
origin/main:templates/README.md:14
origin/main:tests/test_preset_funds_drift.py:13   ← 測試
origin/main:tests/test_preset_funds_drift.py:30
        → 7 行，.py production 端 0 行

正控 $ git grep -n "preset_funds.json" origin/main -- '*.py'（排除 tests）→ 15 行
      （含 services/fund_history.py:31,38、scripts/export_fund_db.py:76 等真讀取端）
負控 $ git grep -n "<負控串>" origin/main -- .  → 無輸出，exit=1
```

**判定：已解。** 兩個理由：
1. **`只讀不寫（人讀）` 不在 §0 的封閉集合裡**（六個狀態：活的／只寫不讀／只讀不寫／查不到／已停用／未落地）。
2. **`只讀不寫` 要求「有 production 讀取」，而這四個檔沒有。**

**改在哪**：盤點表 §2.20 —— 4 列 `只讀不寫（人讀）` → `查不到`，加就地更正註。
**節標題「供使用者複製，程式不讀」保留不動**，它本來就是對的。

**⚠️ 不要誤讀**：這四個檔**沒有變沒用**。`templates/README.md:10-14` 逐檔標明它對應 App 裡的哪個上傳入口。
**狀態欄描述的是「程式端」，不是「有沒有價值」。**
**⛔ 若客戶／總管要為「給人複製的樣板」另立一個狀態值**（例如 `人讀`），那是 **§0 的修改**，本組不自行擴充封閉集合。

---

### 矛盾 8｜PPI／銅價「沒有資料可畫」 → **已解（拆成兩列）**

**A 立場**（盤點表 §6 發現 9，改動前 `:778-781`）：
> 「**發現 9｜`fred_indicators` 宣告 11 支 FRED series，實際只有 9 支有資料。**
> `PPIACO`（PPI）與 `PCOPPUSDM`（銅價）在 parquet 與 fund.db 裡**一列都沒有**……
> 要在畫面上放 PPI / 銅價，現在**沒有資料可畫**。」

**B 立場**（稽核報告 `:170-179`，承重宣稱 ④）：
> 「「`PPIACO`（PPI）與 `PCOPPUSDM`（銅價）一列資料都沒有」→ **本組用兩種與生產組不同的方法驗，成立**」
> 「字典頁（offset 35360）→ `page_type=2 (DICTIONARY_PAGE)`、`num_values=9`、PLAIN 編碼……
> **無 `PPIACO`、無 `PCOPPUSDM`。**……只有**一個** `DATA_PAGE`，encoding **`RLE_DICTIONARY`**，
> **沒有任何 PLAIN 回退頁**。字典編碼沒有 fallback ⇒ 字典即該欄的完整值域。」
> 「`series_id='PPIACO'` → **0**、`='PCOPPUSDM'` → **0**、`LIKE '%PPI%'` → **0**、`LIKE '%COPP%'` → **0**；
> 同一批 `='CPIAUCSL'` → **178**、`='WALCL'` → **797**」

**⚠️ 注意 B 只驗了前半句**（「一列都沒有」），**沒有驗後半句**（「沒有資料可畫」）。

**我的實測（四個點逐一，指令與輸出照抄）**：

```
① services/macro/us_indicators.py:907  df = _fred_iso(FRED_PPI, fred_api_key, 144)
   （shared/fred_series.py:42  FRED_PPI: str = "PPIACO"           # PPI all commodities）
   :908  if len(df) >= 13:
   :910      yoy = (s / s.shift(12) - 1) * 100
   :911      s24 = yoy.dropna().tail(120)                ← 120 個月序列
   :914      R["PPI"] = dict(name="PPI 生產者物價 (YoY)", value=round(v,2),
   :915-922     prev=…, unit="%", type="領先", date=…, desc=…, trend=…,
                signal=…, color=…, score=…, weight=0.5, series=s24)

② services/macro/us_indicators.py:925  s_cu = _yf_iso("HG=F","5y")     ← Yahoo，不是 FRED
   :927  now = float(s_cu.iloc[-1]); prev = float(s_cu.iloc[-22])
   :929  monthly = s_cu.resample("ME").last().pct_change(fill_method=None)*100   # §1 不補值
   :930  R["COPPER"] = dict(name="銅博士（月漲跌）", value=chg, prev=None,
   :931-937   unit="% MoM", type="領先", date=…, desc=f"現價 {now:.3f} USD/lb | 漲=工業需求增",
              signal=…, color=…, score=…, weight=0.5, series=monthly.dropna().tail(60))

   （兩者都在 fetch_all_indicators 內：def ＠:399、return R ＠:1199 → st.session_state["indicators"]）

③ services/calibration/macro_score.py:216    ("PPI",          0.5, _s_ppi,         False),
   services/calibration/macro_score.py:217    ("COPPER",       0.5, _s_copper,      False),  # 餵月變化（%）

④ services/macro/evidence.py:49    "CPI": 0.5, "PPI": 0.5, "INFL_EXP_5Y": 1.0,
   services/macro/evidence.py:57    "VIX": 1.0, "DXY": 1.0, "ADL": 1.0, "COPPER": 0.5,

★ 本組另外查到一件 A 與 B 都沒提的事（決定性）：
$ git show origin/main:services/macro/validation.py | awk 'NR>=170 && NR<=231'
   load_indicators_from_parquet 的對映只有 8 個 key：
     YIELD_10Y2Y(:190) / YIELD_10Y3M(:192) / HY_SPREAD(:195) / M2(:200) /
     FED_BS(:205) / CPI(:210) / UNEMPLOYMENT(:213) / VIX(:227)
   → 沒有 PPI、沒有 COPPER 分支。就算把兩支補進 parquet，離線路徑也讀不到。

正控 $ git grep -n "COPPER\|PPI" origin/main -- 'services/macro/us_indicators.py' → 14 行命中（非 0）
負控 $ git grep -n "<負控串>" origin/main -- . → 無輸出，exit=1
```

**判定：已解。「一列都沒有」為真、「沒有資料可畫」為假。**
**被權衡掉的是 A 的射程**：它把「離線倉沒有」直接推成「畫不出來」，
而 production 的 PPI／銅價**根本不是從那個離線倉來的**。

**改在哪**：
- 盤點表 §6 **發現 9 重寫成兩列**：
  **① 即時值** → ✅ 畫得出來，且已有活的消費者與權重（PPI 走 FRED 即時 API；銅價走 Yahoo `HG=F`）；
  **② 歷史值（離線倉）** → ⛔ 畫不出來（倉裡 0 列，而且對映表根本沒有分支）。
- 盤點表 §2.8 的 `fred_indicators.parquet.series_id` 那一列備註**補上射程**（指回發現 9）。

**⚠️ 一個必須一起講的單位陷阱（A、B 都沒提）**：
production 畫的「銅價」**不是** `PCOPPUSDM`。後者是 FRED 的「Global Price of Copper，**USD per Metric Ton**、月頻」
（`scripts/update_macro_history.py:73` 自己的註解就這樣寫）；而 `R["COPPER"]` 走的是
**Yahoo `HG=F`（COMEX 銅期貨、USD/lb、日頻）**，`desc` 直接印 `現價 {now:.3f} USD/lb`。
**不同序列、不同單位、不同頻率** —— 即使哪天把 `PCOPPUSDM` 補進 parquet，**也不能直接接到畫面上那條線**。

---

## 3. 不解區

**只有一條：矛盾 3（`_Ledgers` 的狀態）。**

| 項目 | 內容 |
|---|---|
| **卡在哪** | 不是事實不清楚，是**沒有判準**。§0 只寫「有 production **讀取**」，沒界定是「位元組被讀回來」還是「資料到得了消費者」。 |
| **事實（本組已全部實測，見上）** | (1) `_Ledgers` 的 9 欄資料**寫得進去**（逐筆 `append_ledger_row`）；(2) 唯一讀取端只取 `len()`；(3) 它餵的 `_sheet_stats` **全 repo 零讀取端**（該檔自己的註解就這樣寫）；(4) `ui/tab3_portfolio.py:42` 只 import 不呼叫。 |
| **為什麼本組不能裁** | 盤點表**自己在 §1.4 與 §2.3 用了相反的兩把尺**。選哪一把尺是**治理決定**，而且**會連帶翻動另一節**（見下），不是本組權限。 |
| **要客戶／總管答的一句話** | 「**production 讀取**」是指「**程式真的把資料讀回來了**」，還是「**讀回來的資料真的被用到了**」？ |
| **裁定的連帶後果** | 裁「讀回來就算」 → `_Ledgers` 維持活的，**但 §2.3 `cache/fund_history.json` 6 欄要從「只寫不讀」翻成「活的」**；裁「要被用到才算」 → `_Ledgers` 9 列改「只寫不讀」，§2.3 不動。 |
| **本輪做了什麼** | §1.4 **狀態欄一格未動**，只補三項實測事實 ＋ 註明爭點 ＋ 出口指回本節。 |

⚠️ **不論怎麼裁，有一件事不受影響**：逐筆交易**確實**一列一列被寫上雲
（`repositories/ledger_repository.py:165` `ws.append_row(_row_values(clean))`）。
**爭的是「有沒有人把它讀回來用」，不是「有沒有寫進去」。**

---

## 4. 新 UI 硬約束（帶進規格，**本階段不解**）

> ⛔ **本區只寫約束，不寫解法。** 設計是規格生產組的事，而且客戶還沒放行。
> 下面每一條都是**已實測的現況**，不是建議。

### 約束 1｜`_持倉總覽` 只寫不讀 —— 這 13 欄成本資料，程式讀不回來

**事實根據（含出處）**
- 盤點表 §1.5：13 欄全部 `只寫不讀`；欄位 SSOT `repositories/snapshot_repository.py:41-44`。
- **寫入端 2 處（production）**：`ui/helpers/cloud_io.py:289`、`ui/tab3_t7_ledger.py:461`
  （皆呼叫 `save_holdings_overview`，`repositories/snapshot_repository.py:222`；**clear ＋ 整批覆寫**）。
- **讀取端 0 處**。本組實測：
  ```
  $ git grep -n "load_holdings_overview" origin/main -- .      → 無輸出，exit=1
  正控 $ git grep -l "save_holdings_overview" origin/main -- .  → 8 個檔：
        ARCHITECTURE.md / SPEC.md（文件）、repositories/snapshot_repository.py（def）、
        tests/test_cloud_io.py / tests/test_ledger_snapshot_store.py / tests/test_wf05_settings_skeleton.py（測試）、
        ui/helpers/cloud_io.py:27,289 / ui/tab3_t7_ledger.py:57,461（production 呼叫）
  負控 $ git grep -n "<負控串>" origin/main -- .   → 無輸出，exit=1
  $ git show origin/main:repositories/snapshot_repository.py | grep -n "^def "
        :67 _with_quota_retry / :75 ensure_state_worksheet / :113 save_all_ledgers_snapshot /
        :192 _ensure_overview_worksheet / :222 save_holdings_overview / :296 load_all_ledgers_snapshot /
        :332 get_state_metadata        ← 整個模組沒有任何 load_holdings_*
  ```
- **稽核組用不同方法（從 gspread 呼叫端反查，不 grep 分頁名）獨立驗過，結論相同**
  （稽核報告 `:154-160`）：全 repo 每一個 gspread 讀取原語開的分頁都指向別的具名常數，
  **沒有任何一處開 `HOLDINGS_TAB`**；且 `load_all_policy_worksheets` 以 `_` 前綴把底線開頭分頁**濾掉**
  （`repositories/policy/v2.py:203-205`），沒有「讀全部分頁時順便讀到它」的路徑。
- **它是 by design**：`ui/tab6_manual.py:641` 自陳「給**人看**的完整成本帳本（`_T7_State` 是機器格式，這張是可讀版）」。

**對新 UI 的意思**
- **新 UI 不能把 `_持倉總覽` 當資料來源** —— 程式沒有讀它的函式，寫一個等於新增取數路徑。
- 同一批成本資料**程式讀得回來的版本**在別的地方：`_T7_State.ledger_json`
  （`repositories/snapshot_repository.py:152` 寫、`:296` `load_all_ledgers_snapshot` 讀）
  與 session 的 `t7_ledgers`（§3.1，15 欄含完整 `transactions[]`）。
- ⚠️ **「級別」在兩邊字面不同**：`_持倉總覽.級別` 是中文「核心」／「衛星」（`snapshot_repository.py:250`），
  `Policies.policy_tier` / `保單分頁v2.tier` 是英文 `core`／`satellite`。**跨表讀級別會踩到這個。**

### 約束 2｜`_Ledgers` 寫得進去、讀不回應用 —— 逐筆流水目前沒有畫面消費者

**事實根據（含出處）**
- **寫**：`ui/tab3_t7_ledger.py:699`（`append_ledger_row`，逐筆一列）、`:1030`（`replace_ledgers_for_policy`）。
  ⚠️ **兩個寫入端都在 OAuth 登入分支內**（`:693` / `:1027` 先建 OAuth client）。
- **讀**：唯一呼叫點 `ui/helpers/portfolio/policy_admin_section.py:825`，
  **只取 `len()`**（`:826`）塞進 `st.session_state["_sheet_stats"]`（`:829-834`）。
- **`_sheet_stats` 全 repo 零讀取端**（本組實測；該檔 `:843-848` 的註解自己就寫著這句）。
- `ui/tab3_portfolio.py:42` 只 import、**從未呼叫**（全檔該 token 只出現 1 次）。
- **狀態詞待裁定**（見上方「不解區」）—— **但上面這些事實不待裁定，已經成立。**

**對新 UI 的意思**
- **想在畫面上顯示「逐筆交易流水」，現在沒有現成的讀取路徑可以接** ——
  `load_all_ledgers`（`repositories/ledger_repository.py:111`）**函式存在**，但目前唯一的呼叫只拿它算列數。
- **另一份逐筆資料是讀得回來的**：`_T7_State.ledger_json` 內含完整 `transactions[]`（8 欄 × N 筆），
  由 `load_all_ledgers_snapshot` → `Ledger.from_dict` 原樣還原（§3.1）。
  **兩份的差別**：`_Ledgers` 是 append-only 流水（每筆一列，9 欄）；`_T7_State` 是整本帳的 JSON blob 快照。
- ⚠️ **登入狀態會改變「有幾份」**：`_Ledgers` 的兩個寫入端都要 OAuth；`_T7_State` 走 service account 也寫得成。
  **沒登入時只有一份，不是兩份**（稽核報告 `:152` 同一結論）。

---

## 5. 待施工的更正（`ui/tab6_manual.py`，**本批未動 `.py`**）

> ⛔ **這是待施工項。本批一個 byte 都沒有動 `ui/tab6_manual.py`**（客戶凍結令：草稿 OK 前不得改 `.py` / UI）。
> 下面是**可直接套用的替換內容**，客戶一說可以動工就能貼上去。

**要改的位置**：`ui/tab6_manual.py` 的 `st.markdown("""…""")` 區塊，
現行內容在 `:630-657`（`:631` 是那句「這 6 種分頁」、`:634-641` 是 6 列表格、`:647` 是「上表其他 5 種」）。
**上方 `:624-629` 的常駐橘框警語不用動**（它是對的）。

### (a) 把 `:631` 那一句換掉

**現行（`awk 'NR==631'` 原文）**：
```
系統目前會讀寫**這 6 種分頁**，平時各動作（批次加入、T7 套用、CSV 匯入）會自動同步到對應分頁。
```
**換成**：
```
系統目前會讀寫**這 9 種分頁**，而且它們**分散在 4 本不同的 Google Sheet**（下表最後一欄）。
平時各動作（批次加入、T7 套用、CSV 匯入）會自動同步到對應分頁。
```

### (b) 把 `:634-641` 的表格整段換掉（**下面是全文，可直接貼**）

```
| 分頁 | 命名規則 | 用途 | 同步來源 | 可以刪嗎 | 在哪一本 |
|---|---|---|---|---|---|
| 📋 **保單分頁** | 自訂保單名稱 | 一張保單 = 一個分頁，放該保單下的基金清單 / 級別 / 幣別 / 本金 | Tab3「保單管理」批次加入 | ✅ 可自由增減（刪掉 = 刪掉那張保單） | 持倉本 |
| 📄 **`Policies`** | 固定名稱、**無底線** | 舊版（v1）平面 schema：一列 = 一組（保單, 基金）。升級 v2 後仍保留供對照 | 舊版寫入路徑 | ⚠️ 已升級 v2 才可刪；不確定就別動 | 持倉本 |
| 📸 **`_T7_State`** | 固定底線開頭 | T7 持倉的單位數 / 平均成本 / 匯率快照，重啟 app 用此還原部位 | Tab3「T7 套用」自動寫入 | ❌ 不要刪 | 持倉本 |
| 📜 **`_Ledgers`** | 固定底線開頭 | 所有 buy / sell / dividend 事件的流水帳（append-only） | Tab3 所有交易動作（**需先用 Google 登入**） | ❌ 不要刪 | 持倉本 |
| 📊 **`_持倉總覽`** | 固定底線開頭 | 給**人看**的完整成本帳本（`_T7_State` 是機器格式，這張是可讀版） | 與 `_T7_State` 同時寫入 | ❌ 不要刪 | 持倉本 |
| 🗂️ **`nav_history`** | 固定名稱、**無底線** | **逐日累積的歷史淨值**（主鍵 = 代碼 + 日期）。長期報酬 / 3Y / 5Y / 低基期全靠它。**手動編輯只需填 `code｜date｜nav` 三欄**（日期 `2020/1/2` 或 `2020-01-02` 都吃）；後面 `fund_name｜source｜recorded_at` 留空即可，**系統會自動補**、也容忍空白 | 每日自動累積 + Tab5「NAV 歷史匯入」+ 📋 管理室 CSV 匯入 | 🚨 **絕對不要刪** | **淨值本（另一本）** |
| 🎯 **`_fund_pool`** | 固定底線開頭 | 換股顧問的選股池，**同時是全站唯一的「基金代號 → ISIN / 晨星代碼 / 幣別」對照表** | Tab「換股顧問」加入/更新選股池 | ❌ **絕對不要刪**（刪掉會讓「找不到淨值」變成常態） | **選股池本（第三本）** |
| 📈 **`_portfolio_perf_history`** | 固定底線開頭 | 組合績效的永久快照（每次記錄一列：報酬 / 波動 / Sharpe / 最大回撤 / 權重…） | Tab「換股顧問」按下記錄快照時 | ❌ 不要刪（刪掉等於丟掉歷史績效曲線） | **總經本（第四本）** |
| ⚖️ **`_macro_weights`** | 固定底線開頭 | 總經評分的權重覆寫（只有 `active` 一列，放在 B3 那一格） | **沒有 App 入口 —— 只能你自己在 Google Sheet 上手填** | ❌ 不要刪 | **總經本（第四本）** |
```

### (c) 把 `:647` 那一句的數字改掉

**現行**：
```
  上表其他 5 種一律不要手動改名或刪除。
```
**換成**：
```
  上表其他 8 種一律不要手動改名或刪除。
```

### (d) 在「保護規則（更正版）」那一段（`:643-653`）加兩條

```
- ⚠️ **這 9 種分頁不在同一本 Sheet 裡**：持倉本 5 種、淨值本 1 種（`nav_history`）、
  選股池本 1 種（`_fund_pool`）、總經本 2 種（`_portfolio_perf_history` / `_macro_weights`）。
  **在某一本裡找不到某張分頁，不一定是被刪了 —— 可能它本來就在另一本。**
- ⚠️ **`_macro_weights` 是唯一沒有 App 寫入入口的分頁**：總經權重要生效，
  只能自己到 Google Sheet 上填 B3 那一格。
```

**每一條的出處（逐項實測，Sheet ID 一律值不列出）**

| 分頁 | 哪一本 | 本子的 ID 由誰決定（出處） |
|---|---|---|
| 保單分頁 / `Policies` / `_T7_State` / `_Ledgers` / `_持倉總覽` | 持倉本 | `st.session_state["policy_sheet_id"]`／secret `POLICY_SHEET_ID` |
| `nav_history` | 淨值本 | secret `NAV_SHEET_ID` → baked 預設（`services/nav_history_gs.py:76-85` `_nav_sheet_id()`；`:68-72` 註解自陳「v19.472：NAV 淨值存進**獨立一本**」） |
| `_fund_pool` | 選股池本 | secret `POOL_SHEET_ID` → baked 預設（`repositories/pool_repository.py:178-180`；`:36-38` 註解自陳「與持倉 `POLICY_SHEET_ID` **不同本**」） |
| `_portfolio_perf_history` | 總經本 | secret `macro_weights_sheet_id`（`repositories/portfolio_perf_repository.py:213` `require_secret("macro_weights_sheet_id")`） |
| `_macro_weights` | 總經本 | secret `macro_weights_sheet_id`（`services/macro/weights_store.py:67` `get_secret("macro_weights_sheet_id")`） |

**表格內容的其他出處**：
- `_fund_pool` ＝ 全站唯一對照表：`repositories/pool_repository.py:31` 明文（「退役獨立 id_map_repository」）；
  盤點表 §1.7 / §6 發現 3。
- `_macro_weights` 沒有寫入入口：`services/macro/weights_store.py` **無 `save_active`**，
  `_gs_get_worksheet(for_write=True)` 零 call site；盤點表 §1.9 / §6 發現 4。
- `_Ledgers` 需先登入：兩個寫入端都在 OAuth 分支內（`ui/tab3_t7_ledger.py:693` / `:1027`）；盤點表 §1.4。
- `_portfolio_perf_history` 15 欄：`repositories/portfolio_perf_repository.py:39`；
  寫 `ui/helpers/fund_grp_health/switch_advisor_section.py:343`、讀 `:460`；盤點表 §1.8。

⚠️ **(b) 那段表格，本組動了什麼、沒動什麼 —— 逐項講清楚，不要只看「只是補三列」**：
- **沒動**：現行 6 列的**每一格文字逐字沿用** `:636-641`（本組以 `awk` 逐行取出後比對）。
  **本組沒有重寫使用者已經看習慣的說明。**
- **動了 4 件事**：
  (1) **新增 3 列**（`_fund_pool` / `_portfolio_perf_history` / `_macro_weights`）；
  (2) **新增一欄「在哪一本」**（9 列都要填）；
  (3) **`_Ledgers` 的「同步來源」補上「需先用 Google 登入」**
      —— 依據：兩個寫入端都在 OAuth 分支內（`ui/tab3_t7_ledger.py:693` / `:1027`），現行說明書沒提；
  (4) ⚠️ **列序改了**：`nav_history` 由現行的第 3 列**移到第 6 列**，改成**依 Sheet 本分組**
      （持倉本 5 列 → 淨值本 1 列 → 選股池本 1 列 → 總經本 2 列）。
      **理由**：新增的「在哪一本」欄如果配上原本的交錯順序，讀者要跳著看才知道哪幾張在同一本。
      ⚠️ **這一項是本組的版面判斷，不是事實更正** —— 若客戶希望保留原列序（`nav_history` 仍排第 3），
      **把該列移回去即可，其餘內容不受影響**。

---

## 6. 我沒查到什麼（一律寫「查不到」，不寫成推測）

1. **真實 Google Sheets 上的實際欄位，查不到。** 本輪**沒有讀寫任何 Google Sheets**（連唯讀都沒有）。
   所有分頁／欄位都是**讀程式碼常數**推出來的。真實試算表上有沒有人手加的欄、有沒有多出來的分頁 —— **查不到**。
2. **runtime 可達性，查不到。** 沒有跑 app、沒有跑 pytest。所有「走得到／走不到」都是靜態
   （import 鏈 ＋ 呼叫點）。特別是矛盾 3 的 `_Ledgers` 讀取、矛盾 5 的 AI 鏈、以及所有 OAuth 分支內的寫入 ——
   **實際執行時走不走得到，查不到。**
3. **`scripts/accumulate_nav_tw.py` 的 NAS cron 現在有沒有在跑，查不到。** 那條 crontab 在使用者的 NAS 上。
4. **`_持倉總覽` 有沒有被 repo 以外的東西讀（例如使用者自己開 Sheet 看、或別的 repo），查不到。** 只掃本 repo。
5. **PPI / 銅價有沒有第三條取數路徑，查不到、也不宣稱。** 本組查的是派工單點名的四個點加上離線倉那條，
   **不是窮舉**。
6. **`ui/tab6_manual.py` 那份說明書除了「6 vs 9」與「本數」之外還有沒有別的錯，查不到。**
   本組只查了派工單點名的那兩件事，**沒有逐句稽核整份說明書**。
7. **本文件是單組產出，沒有第二組看過。** 上列 8 條判定、所有實測、以及「新 UI 硬約束」兩條，
   都是本組自己的判讀。其中「`load_holdings_overview` 0 命中」「`_sheet_stats` 零讀取端」
   「`fund.db` 無本 repo 讀取端」這幾句**取決於有沒有漏看**，已各附正控與負控，**但不宣稱窮舉**。
