# BL-0558 Visual Fidelity Cloud 擷取目標：實作影響分析（唯讀）

> 單組作者分析，未經第二組複驗；全稱句一律「單組字面搜尋，未驗」。**登記／分析不構成動工授權**（`CLAUDE.md` §-1）。
> 基準：origin/main `747c7585`（#1290）。本檔只新增這一份 docs，未改任何程式、tests、workflow。
> 本機只實跑了 `python3 -m pytest tests/visual_fidelity/test_layout_checks_logic.py tests/visual_fidelity/test_workflow_logic.py -q --noconftest` → 43 passed（現況基線；**未**實跑 Cloud 擷取、**未**做任何網路請求）。

## 1. 現行工具如何選擇目標（FACT，讀碼）

| 項 | 位置 | 現況值 |
|---|---|---|
| 預設 Cloud 網址 | `tests/visual_fidelity/vf_config.py::CLOUD_PREVIEW_URL` | 單一常數，註解「B 線預覽站」，host 前綴 `my-fund-dashboard-3atbd…`（客戶 2026-10-29 提供；`docs/evidence/decisions/2026-10-29_batch_a_rulings.md` 逐字存檔，只稱「B 線預覽站」） |
| 擷取腳本 | `tests/visual_fidelity/cloud_capture.py::main` | `--out`（必填）、`--url`（預設＝上列常數）、`--path`（頁面路徑，預設空）、`--timeout-ms`（預設 45000） |
| 目標組成 | `cloud_capture.py::capture` | `url.rstrip("/") + ("/" + path)`；報告 `report_text(url=target…)` 只印網址，**不印「世代／入口檔」** |
| 環境變數 | `UI_V2_CHROMIUM`（`cloud_capture.py::capture`，指定 Chromium）；`VISUAL_FIDELITY_OUT`（`vf_config.ENV_OUT_DIR`，**只給 CI fixture 用**） | Cloud 擷取沒有任何「目標選擇」環境變數 |
| 輸出命名 | `vf_config.CLOUD_FILE_PREFIX="cloud-preview"` → `cloud-preview__{desktop|mobile390}.png`、`cloud-preview__report.md` | 檔名不含世代 |
| workflow 步驟 | `.github/workflows/pr-check.yml` job `visual-fidelity-safety-net`（`continue-on-error: true`、`needs: fast-checks`） | 步驟「Cloud capture (manual dispatch only; production-like)」`if: github.event_name == 'workflow_dispatch'`，`run: python tests/visual_fidelity/cloud_capture.py --out visual-fidelity-out/cloud`——**不傳 `--url`**，即永遠走 `CLOUD_PREVIEW_URL` |
| 觸發 | `on.workflow_dispatch:`（第 8 行，**無 `inputs:`**） | 手動觸發無法選目標；pull_request／push 不跑 Cloud 步驟 |
| artifact | `cloud-preview-screenshots-production-like`（`if` 同為 dispatch）；CI 層 `ci-fixture-screenshots-NOT-production-cloud` | 名稱不含世代 |
| 失敗語意 | `cloud_capture.py`：`net::ERR_*`→「blocked」exit 0；Timeout／403→exit 3；休眠頁／無 `stApp`→exit 4；無 playwright→exit 2 | 目標是否為 `ui_v2`／`ui_v3` **完全不在判定內** |

**鎖住「網域只能出現在 vf_config.py」的守衛（FACT）**：
- `test_layout_checks_logic.py::test_URL只登記在一處`：掃 `tests/**/*.py`＋`ui_v2/**/*.py`＋`.github/**/*.yml`，host 字串（寫死在該測試內）命中檔案集合必須**恰為** `{vf_config.py, test_layout_checks_logic.py}`。對「新增的第二個網域」**無約束**（只認舊 host）。
- `test_config_標示與URL`：斷言 `CLOUD_PREVIEW_URL` 存在且 `https://…streamlit.app/`——**改名／改成 None 會直接紅**。
- `test_config不含任何疑似credential`：`vf_config.py` 只准 `import __future__`（不得 import enum／typing 等）。
- `test_workflow_logic.py`（fast lane）：Cloud 步驟恰一個且 `if` 精確等於 `github.event_name == 'workflow_dispatch'`；cloud artifact 名單**恰為** `["cloud-preview-screenshots-production-like"]`；沒有 curl／wget 步驟；job `continue-on-error is True`、`needs == "fast-checks"`。
- **反向約束（與本案直接相關）**：`tests/ui_v3/test_ui_v3_preview_not_formal_guard.py::test_config_dirs_do_not_reference_ui_v3` 掃 `.github/`、`.streamlit/`、`.devcontainer/` 所有文字檔，**字串 `ui_v3` 出現即紅**。⇒ workflow 本體**不得寫出 `ui_v3`**（含註解、input 選項值）。tests/ 不在該守衛掃描範圍（`_PY_DIRS`／`_TEXT_DIRS` 不含 `tests`）。

**CI fixture 與世代（FACT）**：`test_ci_fixture_screenshots.py` 的情境來自 `tests/ui_v2/test_live_390_page.py::_SCRIPTS`（mkt／hld／exp／alo／set）、`ui_v2.presentation_view`（primitives）、`_ast_fixture`（ast）；`git grep ui_v3 -- tests/visual_fidelity` **0 命中**。CI fixture 層**完全綁 `ui_v2`**，與 Cloud 層網址是否改動無關，也**不是** `ui_v3` 的畫面證據。

## 2. 是否存在合法且已存在的 `ui_v3` Cloud URL（全 repo 檢索）

指令（worktree 根目錄實跑）：`git grep -n -o -h -E "https?://[A-Za-z0-9._<>-]+\.streamlit\.app…"`；`git grep -n -i -E "ui_v3.*(cloud|部署|url|streamlit\.app|main file)|…"`（範圍 docs／PROJECT_RULES／*.md）。

| 網址／來源 | 判定 |
|---|---|
| `…3atbd….streamlit.app`（`vf_config.py`、`batch_a_rulings.md`） | 客戶稱「B 線預覽站」；`docs/v2/71` §7 與 `PROJECT_RULES.md` §0.4 已註為 `ui_v2` B 線，**不是 `ui_v3`**；其部署的 main file／SHA：NOT VERIFIED |
| `…ca8sp….streamlit.app`（`PHASE1_LIVE_VERIFICATION.md`、`PHASE1_UX_AUDIT_PROPOSAL.md`） | 2026-08-14 舊版部署站紀錄，早於 `ui_v2`／`ui_v3`；歷史證據，**不是 `ui_v3`** |
| `<app>`／`<your-app>` 佔位（`infra/oauth.py`、`docs/OAUTH_SETUP.md`、`ARCHITECTURE.md`、`ui/helpers/portfolio/policy_admin_section.py`） | 佔位字樣，不是網址 |
| `PROJECT_RULES.md` §0.4「NOT VERIFIED」列、`docs/v2/71` §7 註、`docs/HANDOFF.md`、`audit_record_2026_11_20_ui_source_correction.md` | 一致記載「`ui_v3` Cloud URL／部署 SHA／Cloud 像素驗收尚未登記，不得猜網址」 |
| `ui_v3/app_preview.py` docstring | 「絕不可設為 Streamlit Cloud 的 main file」（守衛 `test_ui_v3_preview_not_formal_guard.py`）；`DEC-2026-11-02-06`／`-03-04`：preview ≠ 正式 |

**結論**：repo 內**沒有**任何已核實的 `ui_v3` Cloud URL 或部署 SHA（單組字面搜尋，未驗；Streamlit Cloud 平台端設定不在 repo，不可見）。⇒ `ui_v3` Cloud 擷取＝**NOT VERIFIED／NOT RUN**。**不得以舊網址（B 線或 ca8sp 站）fallback 充當 `ui_v3`，也不得推測或拼湊網址**；`ui_v3` 目前的視覺證據只有隔離環境的離線 Preview／AppTest，不等於 Cloud。另：`ui_v3` 入口不可作 Cloud main file，表示「`ui_v3` Cloud 預覽」若要存在，需客戶另行裁示其部署形態（本分析不提議、不授權）。

## 3. 安全參數化方案比較

共通的最小前提：Cloud 目標必須**自帶世代標示**，且 `ui_v3` 目標在 URL 未登記時**fail loud**，而不是悄悄落到舊網址。

| 面向 | 方案 A：UI_GENERATION 維度＋per-target URL（建議候選） | 方案 B：不參數化，只加護欄 | 方案 C：移除預設 URL，強制每次顯式傳入 |
|---|---|---|---|
| 改動 | `vf_config.py` 新增 `CLOUD_TARGETS`（key 用中性名，如 `b-line`／`new-ui2`；每個含 `generation`、`entry`、`url`；`new-ui2.url=None`）；`CLOUD_PREVIEW_URL` 保留為 `b-line` 的別名（相容既有測試）。`cloud_capture.py` 新增 `--target`（預設 `b-line`，行為不變）；`--url` 與 `--target` 互斥，單獨 `--url` 時報告標「世代：未宣告（自訂 URL）」 | 保留單一常數，改名／加註 `…_UI_V2_BLINE`，報告與 stdout 固定印「世代：ui_v2（B 線）；不是 ui_v3 驗收」；workflow 步驟名與 artifact 名帶 `bline` | 刪預設值，`--url` 必填；workflow 以 `workflow_dispatch.inputs.url` 取值 |
| Fail Loud | `new-ui2` 且 url 為 None → 印「NOT RUN：該目標尚未登記 Cloud URL／部署 SHA（NOT VERIFIED）」並**exit 非 0**（新碼，例如 5；不得是 0，否則被讀成通過）；報告第一行必含 target＋generation | 無法擋「有人傳 `--url` 指到 `ui_v3`，報告仍寫 ui_v2」 | 沒傳 URL 就 usage error（exit 2）；但世代標示仍靠人自填 |
| workflow | `workflow_dispatch` 加 `inputs.target`（choice：`b-line`／`new-ui2`）；步驟以 `--target` 傳入；`new-ui2` 且 URL 未登記時步驟明確 skip／NOT RUN 並寫 job summary。**workflow 內不得出現 `ui_v3` 字樣**（見 §1 反向守衛） | 只改步驟名、artifact 名、註解 | 加 `inputs.url`；URL 變成 workflow 輸入，不再登記於 `vf_config`，與「單一位置」原則牴觸 |
| 對 CI fixture 影響 | **無**（fixture 不讀 `CLOUD_*`、不 import `cloud_capture`；情境綁 `ui_v2`）。但需**另補**一個 `ui_v3` 目標不得由 fixture 結果背書的標示 | 無 | 無 |
| required checks | 無影響：job 名稱不變、`continue-on-error: true`、Cloud 步驟只在 dispatch 跑；PR 事件不執行新分支。但**改 `pr-check.yml` 屬 workflow 變更，PR 模板要求「未碰 workflow 與 required checks（除非本 PR 即為授權）」**；branch protection 是否設 required：NOT VERIFIED（API 403，見 `quality_batch2_production_health_acceptance_2026_11_13.md` 第 160 行） | 同左 | 同左 |
| 可逆性 | 高（單一 PR revert；舊 `--url`／預設行為保留） | 最高 | 中（改變手動使用習慣） |
| 主要風險 | 範圍較大；`vf_config` 不得 import 任何模組（enum／typing 皆禁）；目標 key 命名須避開 `.github` 的字串守衛 | 沒解決根因：`ui_v3` URL 出現時仍要改，且最容易被「傳 `--url` 繞過」 | 可能把 URL 散落到 workflow／聊天，違反「不要只留在聊天」（2026-10-29 客戶規則） |

**建議（候選，單組判斷，可被推翻）**：方案 A；方案 B 僅在客戶不授權 workflow 修改時作最小替代（只改 `tests/visual_fidelity/*` 與文件，**不碰** `.github/`）。

## 4. 最小修改清單與守衛／回歸測試（皆為候選斷言，現在不實作）

**方案 A 檔案**：`tests/visual_fidelity/vf_config.py`、`tests/visual_fidelity/cloud_capture.py`、`tests/visual_fidelity/test_layout_checks_logic.py`、`tests/visual_fidelity/test_workflow_logic.py`、`.github/workflows/pr-check.yml`；文件同步 `docs/v2/71` §7.1、`docs/BACKLOG.md`（BL-0558 狀態）。**不動**：`ui_v2/**`、`ui_v3/**`、`test_ci_fixture_screenshots.py`、`layout_checks.py`。

斷言（fast lane、不需瀏覽器、不需網路）：
1. `CLOUD_TARGETS` 每一項皆含 `generation`／`entry`／`url`；`b-line.generation=="ui_v2"`、`new-ui2.generation=="ui_v3"`；`CLOUD_PREVIEW_URL == CLOUD_TARGETS["b-line"]["url"]`（相容性）。
2. **`new-ui2.url is None`**，且 `cloud_capture.resolve_target("new-ui2")` 拋錯／回 NOT RUN 並以**非 0** 結束；斷言訊息含 `NOT VERIFIED`；**不得**回傳 `b-line` 的 URL（防 fallback）。
3. 負控概念：用 `monkeypatch` 把 `new-ui2.url` 換成一個**自訂隨機串（指令內現編、不寫進檔案）**，驗證報告首行含 `new-ui2`／`ui_v3`、且不含 `ui_v2` 世代字樣——證明標示由 target 驅動而非寫死；再把它換回 None 驗證回到 NOT RUN。
4. 報告與 stdout 首段必含 target 與 generation；`--url` 單獨使用時含「世代：未宣告」；`--url` 與 `--target` 同時給 → usage error（exit 2）。
5. `test_URL只登記在一處` 改為：除舊 host 外，**任何** `*.streamlit.app` 字面量只能出現在 `vf_config.py`（以 regex 掃 `tests/`、`ui_v2/`、`.github/`，排除佔位 `<…>`）；保留舊 host 斷言。
6. `test_config_標示與URL` 更新為經由 `CLOUD_TARGETS["b-line"]` 驗證 `https://…streamlit.app/`，並新增「`new-ui2.url` 若非 None 必須是 https＋`.streamlit.app/` 且不等於 b-line URL」。
7. `test_workflow_logic.py`：cloud artifact 名單隨設計更新（單一固定名或每目標一個）；新增斷言「`pr-check.yml` 全文不含 `ui_v3`」（與既有 `tests/ui_v3` 守衛雙保險）、`inputs.target` 選項集合＝`CLOUD_TARGETS` 的 key、Cloud 步驟 `if` 仍限 dispatch。
8. 既有 `tests/ui_v3/test_ui_v3_preview_not_formal_guard.py` 必須維持綠（本案最容易誤踩的守衛）。

驗證責任：fast lane 跑上列測試；`workflow_dispatch` 路徑**只能在 GitHub 上手動觸發才能實測**（本分析禁止觸發，**NOT RUN**）；`new-ui2` 分支的 NOT RUN 行為可用單元測試覆蓋，無需網路。

## 5. 需要的正式授權差異

- 方案 B（只動 `tests/visual_fidelity/*` ＋文件）屬測試工具鏈；方案 A／C 另含 `.github/workflows/pr-check.yml`＝**workflow 變更，須客戶或總管明示授權**（`docs/BACKLOG.md` BL-0558「屬程式／工作流，須客戶或總管授權後才能處理」；PR 模板第 35 行）。
- 候選授權文字（**候選，非裁示**）：「授權開一個獨立 PR，修改 `tests/visual_fidelity/` 與 `.github/workflows/pr-check.yml` 的 Cloud 擷取步驟，使目標可依世代參數化；未登記 Cloud URL 的世代必須 NOT RUN 且不得 fallback 至其他網址；不得新增或猜測任何 Cloud 網址，不改 required checks，不觸發 workflow。」
- 另：登記任何 `ui_v3` Cloud URL／部署 SHA 需客戶提供並由 DECISIONS／BACKLOG 正式登記，**不在此授權內**。

## 6. 與其他工作的關係

- **不阻擋** New UI2（`ui_v3`）視覺工作：該工作使用 `ui_v3` 自己的離線 Preview／AppTest 與隔離環境，不讀 `vf_config.CLOUD_PREVIEW_URL`、不經 `cloud_capture.py`（`git grep` 於 `ui_v3/`、`tests/ui_v3/` 對 `visual_fidelity`／`cloud_capture`／`vf_config` 0 命中；單組字面搜尋，未驗）。
- 風險只在**人為誤用**：把 B 線擷取結果或舊網址當 `ui_v3` Cloud 驗收。**在 BL-0558 處理前的暫行做法（紀律，不是程式）**：任何 `ui_v3` 視覺 PR 不引用 `cloud-preview-*` artifact 當證據，Cloud 欄一律寫 NOT VERIFIED／NOT RUN（`PROJECT_RULES.md` §0.4）。
- 本案與 BL-0536（`ui_v3` 實作）、BL-0535（cutover 守衛）、`docs/v2/71` §7 互相獨立；H5 README 過期註記（BL-0558 末句）為純文件，可併入同一 PR 或另開。

## 無法確認項（NOT VERIFIED／NOT RUN）

1. `ui_v3` 的 Cloud URL、部署 SHA、Cloud 像素驗收；B 線預覽站實際 main file 與部署 SHA。
2. branch protection／required checks 設定（API 先前 403）。
3. `workflow_dispatch` 實跑結果（禁止觸發）；Cloud 網址連線（禁止網路）；`test_ci_fixture_screenshots.py` 瀏覽器情境（本機未跑）。
4. 「repo 內沒有其他 `ui_v3` URL」「`ui_v3/` 與 `tests/ui_v3/` 不引用 Cloud 工具」皆為單組字面搜尋，未經第二組驗證。
