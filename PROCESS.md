# 核心開發與治理協議 (Core Protocol v3.0)

> v2.0 → v3.0 沿革(2026-07-23,user 核准):§1~§5 為原 v2.0 骨幹不變;新增
> §6 動態重規劃與條件分支、§7 全自動自我修正迴圈、§8 多 Agent 分工與 UAT 閉環,
> 將本 session 逐步確立的自動化治理機制成文。**§-1 停手準則(見 CLAUDE.md)凌駕全篇**:
> 沒實際 bug / 沒具體需求 → 不主動找事。以下機制只在 user 已指派任務時啟動。

## §1 狀態與記憶管理 (State & Memory)
- **冷熱資料分離**：專案根目錄必須維持極簡 `STATE.md`。每次任務**僅限讀取此檔與目錄結構**來理解專案目標，嚴禁要求使用者重複解釋。
- **防幻覺機制**：對話超過 10 輪時，修改程式碼前**必須重新讀取目標檔**（不准信任記憶）。
- **主動壓縮**：階段任務完成時，主動提醒我執行 `/compact` 指令，保留核心決策並清理無用推理鏈。

## §2 精準讀寫與檢索 (Precision I/O)
- **大檔案防截斷**：讀取超過 500 行的檔案，強制使用 `offset` 與 `limit` 分段讀取；搜尋結果超過 2000 bytes 時，必須用 `grep` 進行二次精確驗證。
- **動工前大掃除**：重構前優先清理 Dead code 與 Unused imports，極大化釋放 Token 空間。
- **局部編輯**：閉嘴寫扣 (No-Yapping)。嚴禁整檔覆蓋，僅針對特定函數或行數進行精準替換。

## §3 規劃與多線程 (Plan & Parallel Execute)
- **嚴格三步法**：Explore Agent（唯讀探索環境） -> 提出 Plan（3 句話藍圖）與我確認 -> 獲准後才 Execute（動手改 code）。
- **並行處理**：若任務牽涉超過 5 個檔案，主動拆分成子任務並行處理，極致利用 API Context Cache 共享快取。

## §4 鋼鐵自省與交付 (Audit & Auto-Delivery)
- **強制驗證機制**：修改後必須通過 Type check 與 Lint，確認無誤後輸出簡短報告：[邏輯]、[邊界]、[效能]、[Debug]。
- **接線驗證 (Wiring Test) — v19.428 新增**：新增**側車容器 / 旗標 / provenance 欄位 / meta dict**（如 `coverage_out=` / `provenance_out=` / `risk_metric_meta` / `superseded_by`）時，**必須同批附一條「production caller 真的讀到它」的測試**，不得只測產生端。
  - **判準**：這條測試要能在「產生端完全正確、但沒接出去」時**變紅**。若拿掉呼叫端那一行而測試仍綠 → 這條測試無效，重寫。
  - **為什麼獨立成條**：以下四個案例全部通過 lint、通過既有單元測試、每一段單獨看都正確，卻**完全沒有效果**，只有端到端接線測試會紅 ——

    | 案例 | 程式碼看起來 | 實際 |
    |---|---|---|
    | M2 去重 | `weight = 0` | 呼叫端 `float(v.get("weight",1) or 1)` → `0 or 1` = 1，**falsy 回退還原了權重** |
    | 風險指標期間修正 | 提高本地自算樣本門檻 | 值優先取 wb07 官方欄位，門檻只影響一個沒人讀的 meta → **畫面數字零變化** |
    | 換標分 `coverage_out` | 側車算得完整、log 也印得出來 | **漏 `coverage_out.update(_cov)` 一行**，呼叫端拿到空 dict → 綠燈閘門讀不到 `rescaled` → 缺資料的基金照樣拿到「可加碼」建議 |
    | ruff 未定義名白名單 | 死碼地雷已刪除 | `_KNOWN_FALSE_POSITIVES` 沒同步清 → 變成**指向不存在程式碼的永久豁免**，日後同型錯誤被靜默放行 |

  - **共同形狀**：四次都不是「算錯」，而是**算對了但沒接出去**。這類缺陷對 lint / type check / 產生端單元測試**全部免疫**，是本 repo 迄今重工成本最高的失效模式。
  - **稽核落地**：`grep` 該欄位名，若 production 端 **0 consumer**，等同 §1「填補須帶旗標」未達標，**不得算完成**；同時檢查它是不是 `CLAUDE.md §8.1 step 6` 的「用不到的抽象」（若確實不需要 → 刪除，而不是留著假裝有揭露）。
  - **例外登記**：若刻意分兩波交付（本波只產生、下波才接線），必須在 PR 描述**明寫「本波 0 consumer，接線於 X」**，否則視為未完成。

- **測試自身的可執行性 (Test Liveness) — v19.429 新增**：測試若因**環境缺件**而無法執行，必須 **fail 而不是 skip**；`skip` 只保留給「這個平台/情境本來就不適用」，不得用來吸收「工具沒裝」。
  - **判準**：把測試依賴的外部工具移除後，測試應該**變紅**。若只是變 skip 而總結仍顯示 `passed` → 這條測試等於不存在，且會製造「有測試守著」的假象。
  - **為什麼獨立成條**：以下三條測試都寫得很認真、都 commit 進 repo、都被當成保護網，但**從來沒有真正執行過** ——

    | 測試 | 表面上守什麼 | 實際狀況 |
    |---|---|---|
    | `tests/test_undefined_name_scan.py`（ruff F405/F821） | 全站「呼叫了但沒 import 到」的 bare name | Windows 未安裝 dev 依賴 → `FileNotFoundError`。**潛伏一顆 `Path` NameError 地雷直到 v19.424 才被抓到** |
    | `tests/test_provenance_phase2.py`（`subprocess grep`） | 無 caller 對 `source == 'FinMind'` 嚴格比對 | Windows 無 `grep` 執行檔；且正則尾端 `['\"]\b` 的 `\b` 接在引號後 → **即使在 Linux 也永遠不匹配**，雙重空轉 |
    | `tests/test_app_playwright.py`（pixel diff） | Tab1/Tab3 視覺回歸 | 三道關卡任一即 skip（未裝 playwright / 未裝 chromium / 未起 streamlit），CI 兩條 lane 都跑不到；**且 `tests/__snapshots__/` 從未 commit，無基準可比** |

  - **共同形狀**：與 §4 上一條「算對了但沒接出去」是**同一種病的另一半** —— 那條是 production 的失敗被偽裝成成功，這條是**測試的失敗被偽裝成通過**。兩者都對 lint、type check、`pytest` 總結行完全免疫。
  - **正確寫法（`test_undefined_name_scan.py` 已示範，v19.291 踩坑後學會）**：
    ```python
    try:
        proc = subprocess.run([...], ...)
    except FileNotFoundError as e:
        raise AssertionError(f"ruff 未安裝或無法執行——本測試需要它才能掃描：{e}")
    # 工具跑了但沒輸出 → 同樣不可當成「0 findings」
    if not proc.stdout.strip():
        raise AssertionError(f"exit={proc.returncode} 但 stdout 空，工具可能沒真的執行")
    ```
  - **稽核落地**：新增依賴外部工具 / 外部服務 / 基準檔的測試時，必須回答「**缺件時它是紅還是綠？**」。答「skip」→ 要嘛改成 fail，要嘛在 `pytest.ini` marker 說明與檔案 docstring **雙處**標明「本組未啟用、不提供保護」，避免下一個人誤以為有保護網（`tests/test_app_playwright.py` 為此類標記的範例）。
  - **禁止**：把「測試 skip 了」寫進報告當作「測試通過」。統計行的 `skipped` 數字要逐項知道是誰、為什麼。
- **線上驗收 (Deployment Verification) — 2026-08-11 新增**：改動推上 main 後，**在確認新 code 真的在線上跑之前，不得根據畫面結果判斷「功能有沒有效」**。
  - **三步，缺一不可**：
    1. `git log --oneline -1` 對得上 GitHub main 最上面那筆（確認 commit 真的推上去，不是只 commit 沒 push、或根本沒 staged）
    2. **手動 Reboot app**（Streamlit Cloud → Manage app → ⋮ → Reboot app）。**自動部署對本 app 不可靠** —— 實測連續兩批 push 後 log 都沒有 `Pulling code changes`，reboot 後才生效。app 內建的「強制同步 GitHub 最新邏輯」按鈕**只查版本、不能觸發部署**（且常回「無法查 remote main（網路或 IP 限制）」）。
    3. 觸發一次功能，到 Manage app 的 log 找**這批新增的診斷訊息**在不在。**訊息在 = 新 code 真的在跑**；訊息不在就**停止判斷功能是否有效**，回到第 2 步。
  - **⚠️ 先決條件：診斷訊息必須寫 `stderr`。** Streamlit Cloud 的 log 面板**只顯示 stderr**，`print()` 預設的 stdout **完全看不到**。實測佐證：同一次抓取中只有帶 `file=sys.stderr` 的 `[holdings:...]` 出現，`[fetch]` / `[orchestrator]` / `[src_*]` 一行都沒有。
    → 這代表本 repo 依 `CLAUDE.md §1` Fail Loud 寫的大量診斷，在 production **等於沒印**。新增關鍵路徑診斷時一律 `file=sys.stderr`。
  - **⚠️ 查線上檔案內容一律用 commit-pinned URL，禁用 branch ref。** `raw.githubusercontent.com/<owner>/<repo>/**main**/<path>` 會回**過期內容** —— 2026-08-11 那一輪騙到 **4 次**，最嚴重一次差點得出「這個 commit 沒包含該檔案」的錯誤結論（實際上包含，只是 raw 的 `main` 是舊的）。
    - **正確**：先從 commit 列表取短 SHA，再 `raw.githubusercontent.com/<owner>/<repo>/**<sha>**/<path>`。
    - 判準：**任何「線上到底是哪一版」的問題，都要用不可變的 ref 回答**。`main` 是會動的指標，拿它當證據等於沒有證據。
  - **為什麼獨立成條**：2026-08-11 那一輪，同一個症狀（「每檔淨值只有 30 點」）**兩次**被誤判 ——
    | 觀察到的 | 當下的結論 | 事實 |
    |---|---|---|
    | 推完 code、畫面數字沒變 | 「修的方向錯了」 | 部署根本沒生效（reboot 後同一份 code 立刻見效） |
    | log 裡找不到 `[fetch]` / `[orchestrator]` | 「這條路徑沒執行」 | 執行了，只是印到 stdout，面板看不到 |
  - **共同形狀**：與上面兩條同一種病的第三半 —— 那兩條是 production / 測試的失敗被偽裝成成功，這條是**成功被偽裝成失敗**，代價是往正確的修法上打叉、回頭改錯地方。
  - **斷言訊息也算**：測試紅掉時，錯誤訊息若指錯方向（例：接線測試不解 import alias，卻報「production 必須呼叫 X」），比漏測更糟 —— 它會主動把人推去改沒壞的東西。寫斷言訊息時要問：**這句話為真的前提，我驗證過了嗎？**

- **註解錨點陷阱 (Comment Anchor) — 2026-08-11 新增**：用**原始碼字串比對**寫測試時（`X in src` / `src.index()` / `re.search`），比對到的可能是**註解或 docstring**，不是實際邏輯。本 repo 已踩 **5 次**，兩個方向都有：
  - **恆真（漏測）**：`re.search(r"st\.dataframe\(\s*\n?\s*df,.*?\)")` 命中的是上一行的說明註解 → 斷言永遠通過，實際 production 沒接 `column_config`。
  - **恆假（誤導）**：`assert "已由 MoneyDJ 算好" not in src` —— 但**更正後的註解為了說明必須引用那句錯話**，子字串照樣在檔案裡 → 明明已經修好卻永遠紅，還把人指向「production 沒改」。
  - **判準**：問「我要守的是**邏輯**還是**文字**？」
    - 守邏輯 → **一律走 AST**（`ast.Call` / `ast.Compare` / `ast.ImportFrom`…）。AST 看不到註解，天生免疫。掃 keyword argument 要記得解 **import alias**（`from x import f as g` 後呼叫點叫 `g()`）。
    - 守文字（例如「這段更正說明不許被 revert 掉」）→ **守「更正在不在」，不要守「錯的不存在」**。引用錯話以保留脈絡是合法且應該的；revert 回裸主張時，更正說明會一起消失，那才是該紅的訊號。
  - **禁止**：對 production 原始碼寫 `assert "<某句話>" not in src` 來表達「這個錯誤觀念已修正」—— 除非你同時確定沒有任何地方需要引用它。
- **環境與效能**：限用 `.py` 腳本（禁 `.ipynb`），維護 `requirements.txt`。確保 `st.cache_data` 的正確使用。
- **自動交付與合併 (Auto-Ship)**：功能完成後，必須使用 `gh pr create --fill` 建立請求，並**主動執行** `gh pr merge <PR號碼> --merge --delete-branch`。
- **合併後驗證與存檔**：合併後必須自動 `git checkout main && git pull`，使用 `git status` 與 `git log -1` 驗證合併成功，最後自動更新 `STATE.md` 的進度。嚴禁在未驗證成功的情況下回報完成。

## §5 卡關救援 (Anti-Loop Protocol)
- 針對同一個報錯，若連續重試 2 次未果，**立即停機**。
- 啟動除錯協議，並交由我詢問其他 AI 進行雙重驗證。

## §6 動態重規劃與條件分支 (Dynamic Re-planning & Conditional Branching)
- **先盤點再動 (§8.4)**：批次任務逐項**查證**現況再執行；驗證推翻假設時（例：稽核疑似死碼，實測 0-caller 不成立）→ **據實記 WONTFIX，不製造 churn**，禁止為湊數硬改。
- **條件分支**：每項任務依查證結果走三態 —— ✅ 確定可改（改）／⚠️ 需設計或風險（分開提案，等核准）／🔵 查無問題（WONTFIX 登記）。禁止把「文件待議」當必做。
- **一次一單元 + 分開提案**：每個邏輯單元獨立 commit + 自審；「為這次必須改」vs「建議但可延後」分開讓 user 定範圍，禁自作主張大重構。

## §7 全自動自我修正迴圈 (Autonomous Self-Correction Loop)
- **迴圈**：Plan → Execute → 內部 QA/Audit → 自我修正（同一問題至多 3 次）→ 收斂後才交付經理報告。
- **只在兩種情況中斷問 user**：(a) **無任何真實資料來源**可接（§1 禁造假，不得用 mock/example 頂替）；(b) 需求**真正語意歧義**、選擇會實質改變產出。其餘一律自走不中斷。
- **交付報告內容**：改動檔案清單 + QA 抓到什麼 + 如何自修 + 殘留風險 / WONTFIX 理由。**未通過驗證禁報「完成」**（呼應 §4）。

## §8 多 Agent 分工與 UAT 閉環 (Multi-Agent Division + UAT Loop)
> user 指定「多 Agent 分工」時啟動；總管 Agent 負責派工與收斂，不獨攬全部實作。
- **角色鏈**：🏛️ Architect（唯讀掃描 → 規格書）→ 💻 Coder（精準改碼，**嚴禁假資料**）→ 🔍 QA Auditor（**獨立**審查：死碼／假資料／Bug／越權）→ 👤 UAT User（模擬真實使用者，評 UX 流暢度）。
- **退回閘門**：QA 抓到問題 → **強制退回 Coder 重寫**直到 Pass；UAT 體驗不佳 → 退回優化。只有 UAT 滿意才由總管交付。
- **獨立性**：QA / UAT 必須是**獨立 subagent**（非 Coder 自評），確保審查中立；退回迴圈同樣受 §7「至多 3 次」與 §5「連 2 次無進展即停機回報」約束。
- **就地執行原則**：進行中、已設計妥當且小範圍的收尾，總管可直接完成再送獨立 QA/UAT，避免半成品跨 agent 交接的協調損耗（§2「動工前大掃除」精神）。
