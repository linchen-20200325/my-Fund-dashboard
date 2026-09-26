# 交接本（2026-09-26 最新）

最後更新：2026-09-26 15:52:19 UTC（`date -u` 實測）

---

## 進度總表

| 階段 | 基準 | 完成 | % |
|---|---|---|---|
| UI 設計 | 5 頁 | 5 | 100% |
| 假資料版 | 5 頁 | 5 | 100% |
| 接真資料 | 5 頁 | 1 | 20% |
| 收斂 | 3 步 | 0 | 0% |
| 上線 | 1 次 | 0 | 0% |

註：接真資料：已 merge 的只算 mkt（#850）；set 在 feat/set-live-ui，尚未 merge，不計入。收斂 3 步的內容由客戶定義，本表照客戶給的基準。

---

## 1. 當前位置

- 主工作樹：`/home/user/my-Fund-dashboard`
- 分支：`feat/set-live-ui`
- HEAD：`22564db`（`22564db94b5ecee4db61082ae04f7dde83752b3c`），已推到 origin（`origin/feat/set-live-ui` 同為 `22564db`）
- main：`origin/main` = `12cd1ab`（#851 合併點）
- 未 commit 的改動（`git status --short` 實測，7 檔，皆為修改、無新增檔）：
  - `services/v2_tables/settings_store.py`
  - `tests/test_v2_tables_settings_store_page.py`
  - `tests/ui_v2/test_set_live_logic.py`
  - `ui_v2/set/live.py`
  - `ui_v2/set/logic.py`
  - `ui_v2/set/source.py`
  - `ui_v2/set/spec.py`
- 註：這些未 commit 的改動是前端/UI 組本輪回修，還在進行中。

## 2. 進行中

### set 頁正式模式 UI
- 分支：`feat/set-live-ui`（已推 `104398d` → `22564db`）
- 狀態：**實作中**
- 負責組：前端/UI 組
- 經過：
  - 第 1 輪稽核：必修 8 項已修完。
  - 兩組複驗：必修 0。
- 本輪回修四項：
  1. `alo_basis` 定型別為 list 枚舉（成本／市值）；客戶已裁示。
  2. 拒收 `[1e999]`。
  3. `changed_settings` 補測試。
  4. 前後帶空白的值判為型別不符、不存檔（依 44 SET-4「逐字相同」）；只有空白＝清除該鍵。
- 下一步誰動：前端/UI 組交回後，總管送最終複驗（兩組）；通過就開 PR，並依常設授權判斷是否 merge。

### 交接本
- 狀態：已建立，持續維護
- 負責組：交接本書記組
- 交接本規則：派工／回報／commit 前／每則回覆前／收到新指令時更新
- 下一步誰動：總管有更新時通知書記組

### 登記待辦（已登記下一輪，總管判斷不需要客戶裁示）
- 寫表失敗的原因寫不進取數紀錄（50 B14）
- 同一個空分頁被同時寫入時，標頭可能重複
- float32 誤差被判成主鍵矛盾
- 冷卻時燈號、SET-1、SET-2、SET-6 仍顯示紅色「還剩…rate_limited」（L1 既有字串，草稿沒訂）
- 標題為空時會進冷卻
- 取數後會清掉市場總覽共用的 yf 快取
- 非 SettingsSheetError 的例外會顯示為 Streamlit 錯誤畫面
- 舊 App 保單頁有兩處「未指定 Sheet ID」
- FX 日期查證、AST 守衛還有 6 種動態 import 漏網等舊登記（見 docs/v2/49 §8）

## 3. 已完成（未 merge）

- `feat/set-live-ui`：set 頁正式模式接真資料，照已核准草稿（10 處新文案），重新取數只接市場指標。
  - 未 merge 原因：本輪回修尚未完成、最終複驗尚未跑。

## 4. 已完成（已 merge）

- #845～#850：共同底座、mkt 正式模式、遮蔽等（前幾輪）。
- #851（`12cd1ab`）：設定試算表 L1 讀寫、user_setting／fetch_log 契約、market_indicator 寫表 sink，已合 main。

## 5. 待客戶裁示

- 目前無新的待裁示題。
- 總管判斷不需客戶裁示的技術項，見第 2 節末「登記待辦」。
